
from __future__ import annotations

import json
import time
from pathlib import Path

EXO = Path("C:/Projects/HybridLLM/exocortex")

CRITERIA = ("simplicity", "integration", "robustness", "performance")

class EvaluatorOrgan:
    def __init__(self, llm_organ=None, terminal_organ=None,
                 log_path: str | Path = EXO / "evaluations.jsonl"):
        self.llm = llm_organ
        self.terminal = terminal_organ
        self.log_path = Path(log_path)
        self.history: list[dict] = []

    def evaluate_approach(self, approach, existing_code: str = "",
                          criteria: tuple = CRITERIA) -> dict:
        a = approach if isinstance(approach, dict) else {"name": str(approach)}
        op = a.get("op", "ADD_FUNCTION")
        scores = {}
        base = {"ADD_CONDITION": (0.9, 0.9, 0.7, 0.6),
                "WRAP_TRY_EXCEPT": (0.7, 0.8, 0.9, 0.5),
                "ADD_VARIABLE": (0.8, 0.7, 0.6, 0.8),
                "ADD_FUNCTION": (0.6, 0.6, 0.8, 0.7),
                "MUTATE": (0.7, 0.7, 0.7, 0.6)}.get(op, (0.5,) * 4)
        for c, b in zip(CRITERIA, base):
            scores[c] = round(b, 2)
        for rec in self._past():
            if rec.get("op") == op and "op_rate" not in scores:
                scores["op_rate"] = rec["op_rate"]
        priors = [r for r in self._past() if r.get("op") == op]
        if priors:
            r = sum(1 for p in priors if p["success"]) / len(priors)
            for c in criteria:
                scores[c] = round(min(1.0, scores[c] * 0.7 + r * 0.3), 2)
        total = round(sum(scores[c] for c in criteria if c in scores), 2)
        verdict = ("viable" if total >= 2.2 else
                   "marginal" if total >= 1.6 else "weak")
        return {"name": a.get("name", "?"), "op": op, "scores": scores,
                "total": total, "verdict": verdict}

    def compare_approaches(self, approaches, existing_code: str = "") -> list:
        scored = []
        for a in approaches:
            e = self.evaluate_approach(a, existing_code)
            item = dict(a) if isinstance(a, dict) else {"name": str(a)}
            item.update({"score": e["total"], "scores": e["scores"],
                         "verdict": e["verdict"]})
            scored.append(item)
        scored.sort(key=lambda x: -x["score"])
        return scored

    def evaluate_step_result(self, step, expected_outcome, actual) -> dict:
        ok = bool(actual.get("ok") if isinstance(actual, dict) else actual)
        issues = []
        if isinstance(actual, dict) and actual.get("error"):
            issues.append(str(actual["error"])[:120])
        v = str(step.get("verify", "")) if isinstance(step, dict) else ""
        code = (actual.get("code") if isinstance(actual, dict) else "") or ""
        if ok and "syntax ok" in v and code:
            try:
                compile(code, "step.py", "exec")
            except SyntaxError as e:
                ok = False
                issues.append(f"verify failed: syntax: {e}")
        if ok and "function defined" in v and "def " not in code:
            ok = False
            issues.append("verify failed: no def found")
        return {"success": ok, "match_score": 1.0 if ok else 0.0,
                "issues": issues}

    def evaluate_final_result(self, task, implemented_code: str) -> dict:
        """task: text or spec dict with a `run` test helper."""
        text = task if isinstance(task, str) else task.get("text", "")
        run = "" if isinstance(task, str) else task.get("run", "")
        tests = []
        success = False
        if self.terminal is not None and run:
            out = self.terminal.run(f'python -c "{run[:4000]}"')
            okc = bool(out.get("ok")) and "OK" in str(out.get("output", ""))
            tests.append({"cmd": "verifier run", "passed": okc,
                          "output": str(out.get("output", ""))[:200]})
            success = okc
        elif isinstance(task, dict) and task.get("run"):
            try:
                compile(implemented_code, "final.py", "exec")
                success = True
                tests.append({"cmd": "compile", "passed": True})
            except SyntaxError as e:
                tests.append({"cmd": "compile", "passed": False,
                              "output": str(e)})
        else:
            try:
                compile(implemented_code or text, "final.py", "exec")
                success = True
                tests.append({"cmd": "compile", "passed": True})
            except SyntaxError:
                tests.append({"cmd": "compile", "passed": False})
        score = 1.0 if success else 0.0
        return {"success": bool(success), "test_results": tests,
                "score": score}

    def should_backtrack(self, failure_count: int, attempts: int,
                         plan_progress: float) -> dict:
        if failure_count > 3:
            return {"backtrack": True,
                    "reason": f">{3} failed steps on this plan"}
        if attempts > 5:
            return {"backtrack": True, "reason": f"{attempts} attempts "
                                                 f"exhausted"}
        if plan_progress < 0.3 and failure_count > 2:
            return {"backtrack": True,
                    "reason": "low progress + repeated failures"}
        return {"backtrack": False, "reason": "fix locally and retry"}

    def record_outcome(self, task, approach, plan, success: bool):
        op = approach.get("op") if isinstance(approach, dict) else None
        rec = {"task": str(task if isinstance(task, str) else
                           task.get("text", ""))[:80],
               "approach": (approach.get("name") if isinstance(approach, dict)
                            else str(approach)),
               "op": op, "progress": self._prog(plan),
               "success": bool(success), "ts": time.time()}
        past = self._past()
        same = [p["success"] for p in past if p.get("op") == op] + [rec["success"]]
        rec["op_rate"] = round(sum(same) / len(same), 3)
        self.history.append(rec)
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
        except Exception:
            pass
        return rec

    def _past(self) -> list[dict]:
        if not getattr(self, "_cache", None):
            rows = []
            if self.log_path.exists():
                for line in self.log_path.read_text(
                        encoding="utf-8").splitlines()[-400:]:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
            self._cache = rows
        return self._cache

    def stats(self) -> dict:
        past = self._past()
        bt = getattr(self, "backtrack_events", 0)
        return {"evaluations": len(past),
                "success_rate": round(sum(p["success"] for p in past)
                                      / max(len(past), 1), 3),
                "by_op": {op: round(sum(p["success"] for p in past
                                         if p.get("op") == op)
                                    / max(sum(1 for p in past
                                              if p.get("op") == op), 1), 2)
                          for op in ("ADD_CONDITION", "WRAP_TRY_EXCEPT",
                                     "ADD_VARIABLE", "ADD_FUNCTION")
                          if any(p.get("op") == op for p in past)}}

    @staticmethod
    def _prog(plan):
        try:
            return round(sum(1 for s in plan if s["status"] == "complete")
                         / max(len(plan), 1), 2)
        except Exception:
            return None