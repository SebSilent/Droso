from __future__ import annotations

import time

from .api_oracle import NoAPIKeyError, estimate_tokens
from .query_cache import QueryCache
from .task_decomposer import TaskDecomposer

ROUTES = ("learned", "local", "cache", "oracle", "none")

class TokenOptimizer:
    def __init__(self, api_oracle, local_solver=None, cache: QueryCache | None =
                 None, decomposer: TaskDecomposer | None = None,
                 learning_loop=None, verifier=None,
                 allow_approximate_cache: bool = False,
                 max_oracle_calls: int = 4, require_verified_local: bool =
                 False):
        self.oracle = api_oracle
        self.local = local_solver
        self.cache = cache or QueryCache()
        self.decomposer = decomposer or TaskDecomposer()
        self.learning = learning_loop
        self.verifier = verifier
        self.allow_approximate_cache = bool(allow_approximate_cache)
        self.max_oracle_calls = int(max_oracle_calls)
        self.require_verified_local = bool(require_verified_local)
        self.per_route = {r: 0 for r in ROUTES}
        self.tasks = 0
        self.partial = 0
        self.tokens_actual = 0
        self.seconds = 0.0
        self.cache_hits = 0
        self.budget_stops = 0

    def solve_with_minimal_tokens(self, task: str, context: str = "",
                                  language: str | None = None,
                                  files: list[str] | None = None,
                                  allow_oracle: bool = True) -> dict:
        t0 = time.perf_counter()
        task = str(task or "").strip()
        if not task:
            return {"solution": "", "route": "none", "reason": "empty_task",
                    "api_calls": 0, "tokens_used": 0}
        self.tasks += 1
        try:
            self.oracle.budget.start_task()
        except AttributeError:
            pass
        if self.learning is not None:
            hit = self.learning.recall(task)
            if hit and hit.get("solution"):
                return self._finish(hit["method"], hit["solution"], task,
                                    context, calls=0, t0=t0,
                                    provenance=[hit["provenance"]],
                                    confidence=hit.get("confidence"))
        if self.local is not None:
            hit = self.local.solve(task, context=context, language=language,
                                   require_verified=self.require_verified_local)
            if hit and hit.get("solution"):
                return self._finish("local", hit["solution"], task, context,
                                    calls=0, t0=t0, provenance=[hit["provenance"]],
                                    confidence=hit.get("confidence"),
                                    verified=hit.get("verified"))
        prov = []
        mode = getattr(self.oracle, "mode", "unknown")
        cached = self.cache.get(task, context=context,
                                provider=getattr(self.oracle, "provider", ""),
                                model=getattr(self.oracle, "model", ""),
                                approximate=self.allow_approximate_cache)
        if cached and cached.get("answer"):
            self.cache_hits += 1
            prov.append(f"cache({'exact' if cached.get('exact') else 'approx'},"
                        f"{cached.get('tokens_avoided', 0)} tokens avoided)")
            return self._finish("cache", cached["answer"], task, context,
                                calls=0, t0=t0, provenance=prov,
                                cached=True, approximate=cached.get(
                                    "approximate", False))
        dec = self.decomposer.decompose(task, context=context, files=files)
        askable = dec.oracle_parts + dec.unknown_parts
        escalated = False
        if not askable:
            askable = dec.local_parts or [{"id": "q0",
                                           "question": task,
                                           "context": context}]
            escalated = True
        answers, calls, notes = [], 0, []
        budget_stop = None
        if escalated:
            notes.append("escalated: decomposer found no oracle-worthy part "
                         "but nothing local answered the task")
        if not allow_oracle or not getattr(self.oracle, "has_key", True):
            why = ("llm_disabled" if not allow_oracle else "no_api_key")
            notes.append(f"oracle not consulted: {why}")
            return self._finish("none", "", task, context, calls=0, t0=t0,
                                provenance=notes + prov, verified=False,
                                partial=True, reasons=[why],
                                parts=dec.summary(), answers=[])
        for batch in self._batches(askable):
            if calls >= self.max_oracle_calls:
                notes.append(f"stopped at max_oracle_calls={self.max_oracle_calls}")
                break
            if not batch["questions"]:
                continue
            try:
                r = self.oracle.query(batch["prompt"],
                                      context=batch.get("context", ""),
                                      purpose="task_subquestion")
            except NoAPIKeyError as e:
                budget_stop = "no_api_key"
                self.budget_stops += 1
                notes.append(f"oracle refused: {e}")
                break
            if not r.get("ok"):
                budget_stop = r.get("reason", "oracle_failed")
                self.budget_stops += 1
                notes.append(f"oracle refused: {budget_stop}")
                break
            calls += 1
            answers.append({"ids": batch.get("ids", []),
                            "questions": batch["questions"],
                            "answer": r["text"], "mode": r.get("mode"),
                            "tokens": r["prompt_tokens_est"] +
                            r["completion_tokens_est"]})
            self.cache.put(batch["prompt"], r["text"],
                           provider=r["provider"], model=r["model"],
                           purpose="task_subquestion", mode=r.get("mode", "live"),
                           tokens_in=r["prompt_tokens_est"],
                           tokens_out=r["completion_tokens_est"])
        solution = _join(answers)
        if solution and not budget_stop and answers and self.cache is not None:
            self.cache.put(task, solution,
                           provider=getattr(self.oracle, "provider", ""),
                           model=getattr(self.oracle, "model", ""),
                           purpose="task", mode=answers[0].get("mode", "live"),
                           tokens_in=sum(int(a.get("tokens", 0)) for a in answers))
        verified = self._verify(solution, task)
        if self.learning is not None and solution:
            self.learning.learn_from_task(task, solution, {
                "source": answers[0]["mode"] if answers else "none",
                "verified": verified, "language": language or "python"})
        out = self._finish("oracle" if calls else "none", solution, task,
                           context, calls=calls, t0=t0, provenance=notes + prov,
                           verified=verified,
                           partial=bool(budget_stop) or not solution,
                           reasons=[budget_stop] if budget_stop else [],
                           parts=dec.summary(), answers=answers)
        return out

    def _batches(self, parts, max_per_call: int = 3) -> list[dict]:
        """Group questions so shared context is paid for once per call instead
        of once per question."""
        out = []
        rest = list(parts)
        while rest:
            grp, rest = rest[:max_per_call], rest[max_per_call:]
            ctx = next((g.get("context", "") for g in grp), "")
            if len(grp) == 1:
                prompt = grp[0]["question"]
            else:
                prompt = ("Answer each numbered question separately and "
                          "briefly, as `N: answer`.\n" +
                          "\n".join(f"{i + 1}. {g['question']}"
                                    for i, g in enumerate(grp)))
            out.append({"prompt": prompt, "context": ctx,
                        "questions": [g["question"] for g in grp],
                        "ids": [g.get("id", "") for g in grp]})
        return out

    def _verify(self, solution: str, task: str) -> bool:
        if not solution or self.verifier is None:
            return False
        try:
            v = self.verifier.verify(solution, language="python")
        except TypeError:
            v = self.verifier.verify(solution)
        except Exception:
            return False
        return bool(v.get("ok", v.get("valid")) if isinstance(v, dict) else v)

    def _finish(self, route, solution, task, context, calls, t0,
                provenance=None, confidence=None, verified=None,
                partial=False, reasons=None, parts=None, answers=None,
                cached=False, approximate=False) -> dict:
        self.per_route[route] = self.per_route.get(route, 0) + 1
        used = sum(a["tokens"] for a in (answers or []))
        self.tokens_actual += used
        secs = time.perf_counter() - t0
        self.seconds += secs
        if partial:
            self.partial += 1
        return {"solution": solution, "route": route, "api_calls": calls,
                "tokens_used": used, "task": task[:200],
                "seconds": round(secs, 3),
                "oracle_mode": getattr(self.oracle, "mode", "unknown"),
                "verified": bool(verified) if verified is not None else None,
                "confidence": confidence, "partial": bool(partial),
                "reasons": reasons or [], "provenance": provenance or [],
                "decomposition": parts or {}, "cached": cached,
                "approximate_answer": bool(approximate),
                "answers": answers or []}

    def report(self) -> dict:
        asked = self.oracle.stats() if hasattr(self.oracle, "stats") else {}
        rate = self.cache.stats()
        return {"tasks": self.tasks, "per_route": dict(self.per_route),
                "solved_without_api": self.per_route["learned"] +
                self.per_route["local"] + self.per_route["cache"],
                "local_solve_share": round(
                    (self.per_route["learned"] + self.per_route["local"] +
                     self.per_route["cache"]) / max(1, self.tasks), 3),
                "partial": self.partial, "budget_stops": self.budget_stops,
                "cache": dict(rate),
                "oracle": dict(asked),
                "seconds_total": round(self.seconds, 2)}

def _join(answers) -> str:
    parts = []
    for a in answers:
        q = a["questions"][0] if len(a["questions"]) == 1 else \
            " / ".join(a["questions"])
        parts.append(f"# {q}\n{a['answer']}")
    return "\n\n".join(parts)