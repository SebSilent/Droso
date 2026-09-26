import re
import time

from .api_oracle import NoAPIKeyError

PROCEDURE_REPLAY = "procedure_replay"
TRIAL_REPLAY = "trial_replay"
COMPOSITION = "composition"
DIRECT_API = "direct_api"
REASONING_LOOP = "reasoning_loop"

_CODE_SHAPE = re.compile(
    r"\b(implement|refactor|write|create|add|fix|patch|debug|test|verify|"
    r"deploy|migrate|optimi[sz]e|rename|extract|wrap|handle|support|ensure|"
    r"return|raise|class|function|method|endpoint|script|module)\b")
_FILE_SHAPE = re.compile(r"[\w./\\-]+\.(py|js|ts|tsx|jsx|html|css|json|yaml|"
                         r"yml|md|lua|cpp|h|rs|go|java|sh|toml|sql)\b")
_MULTI_REQ = re.compile(r";|\band\s+must\b|\bnever\s+\w+\b|\bmust\b.*\bmust\b|"
                        r"\bboth\b.*\band\b")
_QUESTION = re.compile(r"^\s*(what|how do i|how do you|how to|explain|define|"
                       r"why|when|where|which|who|is |are |can i|should i|"
                       r"difference between)\b")
_PROSE_ASK = re.compile(r"^\s*(explain|define|describe|summarise|summarize|"
                        r"list|compare|translate|show me|tell me|what does)\b")

class FastRouter:
    def __init__(self, api_oracle=None, local_solver=None, reasoning_agent=None,
                 replay_confidence: float = 0.9, min_patterns: int = 3,
                 simple_max_words: int = 8, fast_path: bool = True,
                 direct_api_max_tokens: int = 300):
        self.api = api_oracle
        self.local = local_solver
        self.agent = reasoning_agent
        self.replay_confidence = float(replay_confidence)
        self.min_patterns = max(2, int(min_patterns))
        self.simple_max_words = int(simple_max_words)
        self.fast_path = bool(fast_path)
        self.direct_api_max_tokens = int(direct_api_max_tokens)
        self.decisions: dict[str, int] = {}
        self.measured: dict[str, list] = {}
        self.last_learn: dict = {}
        self.skipped = 0
        self.runs = 0
        self.decision_ms: list = []
        self.last: dict = {}

    def route(self, task_description: str) -> dict:
        """Return the cheapest sufficient plan, with a zero-arg `handler`.

        Choosing has no side effects: nothing runs until `run()` says so, which
        is what lets the dashboard explain a decision before it is paid for.
        """
        t0 = time.perf_counter()
        plan = self._route(task_description)
        ms = (time.perf_counter() - t0) * 1000.0
        self.decision_ms.append(round(ms, 3))
        if len(self.decision_ms) > 200:
            del self.decision_ms[:len(self.decision_ms) - 200]
        plan["decision_ms"] = round(ms, 3)
        return plan

    def _route(self, task_description: str) -> dict:
        task = str(task_description or "")
        words = len(task.split())
        code_like = self.is_code_shaped(task)

        if not self.fast_path:
            return self._plan(REASONING_LOOP, task, 30000, 1500,
                              "fast path disabled by config",
                              lambda: self._loop(task))

        rec = None
        if self.local is not None:
            try:
                # Recall at the trial floor, not the trust floor. Deciding whether
                # to trust it is the next step, and it is decided by running it.
                rec = self.local.recall_procedure(
                    task, min_confidence=getattr(self.local, "trial_floor", 0.35))
            except Exception:
                rec = None
        if rec is not None:
            conf = float(getattr(rec, "confidence", 0) or 0)
            empty = {"solution": "", "method": "none", "api_calls": 0,
                     "tokens": 0}
            if conf >= self.replay_confidence:
                fresh = bool(getattr(rec, "verified", False))
                return self._plan(PROCEDURE_REPLAY, task, 5, 0,
                                  f"procedure at conf {conf:.2f}"
                                  + ("" if fresh else ", not verified now"),
                                  lambda: (rec.replay(require_verified=False)
                                           or empty))
            # Not trusted yet, and that is not a reason to ignore it. A trial is
            # cheap and it is the only way the record ever earns its confidence:
            # run it, and let the verdict promote or demote it. What fails to run
            # is dropped in run() and he goes and thinks instead.
            return self._plan(TRIAL_REPLAY, task, 60, 0,
                              f"procedure at conf {conf:.2f}, below the "
                              f"{self.replay_confidence:.2f} trust floor; "
                              f"replayed as a trial and judged by execution",
                              lambda: (rec.replay(require_verified=False)
                                       or empty))

        if self.local is not None and hasattr(self.local, "query_patterns"):
            try:
                pats = self.local.query_patterns(task) or []
            except Exception:
                pats = []
            if len(pats) >= self.min_patterns and code_like:
                return self._plan(COMPOSITION, task, 100, 0,
                                  f"{len(pats)} remembered patterns to assemble",
                                  lambda: self._compose(task, pats))
            if len(pats) >= self.min_patterns:
                return self._plan(COMPOSITION, task, 100, 0,
                                  f"{len(pats)} patterns, non-code: composition "
                                  "still gets first refusal",
                                  lambda: self._compose(task, pats))

        if self._is_simple_query(task) and not code_like:
            blocked = self._direct_affordable()
            if blocked:
                return self._plan(
                    REASONING_LOOP, task, 30000, 1500,
                    blocked + ": not proposing a rung that cannot run",
                    lambda: self._loop(task))
            return self._plan(DIRECT_API, task, 2000, 200,
                              f"question, {words} words, nothing to verify",
                              lambda: self._direct(task))

        why = "code-shaped task: the loop is what buys verification" if code_like \
            else ("multi-requirement task" if _MULTI_REQ.search(task.lower())
                  else f"{words} words, no fast rung qualified")
        return self._plan(REASONING_LOOP, task, 30000, 1500, why,
                          lambda: self._loop(task))

    def explain(self, task_description: str) -> dict:
        """The decision, without the closure -- for the dashboard."""
        r = self.route(task_description)
        out = {k: v for k, v in r.items() if k != "handler"}
        out["measured_ms_by_path"] = {k: self.median_ms(k)
                                      for k in self.measured if self.measured[k]}
        return out

    def run(self, task_description: str) -> dict:
        r = self.route(task_description)
        handler = r.pop("handler")
        t0 = time.perf_counter()
        try:
            res = handler()
        except Exception as exc:
            res = {"solution": "", "method": "error", "api_calls": 0,
                   "error": f"{type(exc).__name__}: {exc}"[:200]}
        ms = (time.perf_counter() - t0) * 1000.0
        self.runs += 1
        self.decisions[r["path"]] = self.decisions.get(r["path"], 0) + 1
        self.measured.setdefault(r["path"], []).append(round(ms, 3))
        if len(self.measured[r["path"]]) > 50:
            del self.measured[r["path"]][:len(self.measured[r["path"]]) - 50]
        if not isinstance(res, dict):
            res = {"solution": str(res), "method": "raw"}
        trial_failed = False
        if r["path"] == TRIAL_REPLAY and str(res.get("solution", "")).strip():
            # The whole bargain: he may reach for something he does not yet trust,
            # because reaching means executing, and execution is the only
            # authority on whether it was right. What does not hold is not handed
            # back -- it is dropped, demoted, and he goes and thinks.
            ok, kind = False, ""
            if self.local is not None:
                try:
                    ok, kind = self.local._verify_detail(
                        str(res.get("solution", "")), task_description)
                except Exception:
                    ok, kind = False, ""
            res = dict(res)
            res["trial_verified"] = bool(ok)
            if ok:
                # Fresh evidence beats the filed claim. The record's own verified
                # flag says whether it had succeeded when it was stored; a trial
                # that has just run and passed is newer information about the same
                # code. Trusting the stale flag demoted fifteen procedures that
                # worked and promoted nothing, so the loop oscillated instead of
                # converging.
                res["verified"] = True
                res["verifier_kind"] = kind or "execution"
            trial_failed = not ok
        if (r["path"] in (PROCEDURE_REPLAY, COMPOSITION) and not
                str(res.get("solution", "")).strip()) or trial_failed:
            self.skipped += 1
            loop = self.route(task_description + " ")
            if loop["path"] == r["path"]:
                loop = self._plan(REASONING_LOOP, task_description, 30000, 1500,
                                  f"{r['path']} returned nothing",
                                  lambda: self._loop(task_description))
            h2 = loop.pop("handler")
            t1 = time.perf_counter()
            try:
                res = h2()
            except Exception as exc:
                res = {"solution": "", "error": f"{type(exc).__name__}: {exc}"}
            ms += (time.perf_counter() - t1) * 1000.0
            res = dict(res or {})
            res["fell_back_from"] = r["path"]
            if trial_failed:
                # The verdict survives the fallback. That a trial was attempted and
                # did not hold is the evidence which demotes the procedure, and it
                # is also the only record that he reached for memory before he
                # reached for thought.
                res["trial_verified"] = False
            r["path"] = loop["path"]
        res = dict(res or {})
        res["route_path"] = r["path"]
        res["route_reason"] = r["reason"]
        res["routed_ms"] = round(ms, 3)
        res["estimated_ms"] = r["estimated_ms"]
        res["api_calls"] = int(res.get("api_calls", r.get("api_calls", 0) or 0))
        self.last = {k: v for k, v in r.items()}
        self.last["measured_ms"] = round(ms, 3)
        self._learn_from_result(task_description, res)
        return res

    def _learn_from_result(self, task: str, res: dict) -> dict:
        """Close the loop: work that ran becomes library.

        learn_from_task was wired only to the API path, so the procedure store
        filled only when the LLM had been paid, and every task he solved himself
        was forgotten. That is backwards from the whole point -- the library is
        what makes the *next* task local, which is the only route to needing the
        model less over time instead of more.

        The gate is execution, not provenance. Whatever ran and passed is worth
        keeping; whatever ran and failed is worth keeping as a failure, because a
        demoted confidence is the only thing that stops him replaying code he has
        already watched break.

        Prose is refused. A question answered in sentences is not a procedure,
        and filing it would put text into the library code is retrieved from.
        """
        out: dict = {"learned": False}
        try:
            res = dict(res or {})
            sol = str(res.get("solution") or "")
            if not sol.strip():
                self.last_learn = out
                return out
            from .local_solver import _looks_like_code
            if not (_looks_like_code(sol) or self.is_code_shaped(str(task or ""))):
                out = {"learned": False, "reason": "not code"}
                self.last_learn = out
                return out
            learning = getattr(self.agent, "learning_loop", None) \
                if self.agent is not None else None
            if learning is None:
                # The solver carries the same library. A router built without an
                # agent -- a drill, a test, a batch run -- still has to be able to
                # record what it executed, or the verdict goes nowhere and the
                # procedure is never promoted for having worked.
                learning = getattr(self.local, "learning", None)
            if learning is None:
                out = {"learned": False, "reason": "no learning loop"}
                self.last_learn = out
                return out
            verified = res.get("verified")
            kind = str(res.get("verifier_kind") or "")
            if verified is None and self.local is not None:
                try:
                    detail = self.local._verify_detail(sol, task)
                    verified, kind = bool(detail[0]), str(detail[1] or "")
                except Exception:
                    verified, kind = False, ""
            verified = bool(verified)
            method = str(res.get("method") or res.get("route_path") or "local")
            rec_sig = res.get("signature")
            from .learning_loop import signature as _sig
            # "learned" is what the store calls a recall; "procedure_replay" and
            # "procedure" are what the router and solver call the same event. All
            # three mean the answer came out of the library rather than being new.
            if rec_sig and (method in ("learned", "procedure_replay",
                                       "procedure") or res.get("replayed")):
                # The answer came out of the library, so this is a use and not a
                # new procedure. Only a phrasing whose trial actually held becomes
                # an alias: a fuzzy match that failed to run says the two tasks are
                # NOT the same, and merging them would be exactly the wrong recall
                # that gets believed.
                out = {"learned": False, "reused": str(rec_sig)[:48],
                       "verified": verified}
                if verified and str(rec_sig) != _sig(task):
                    try:
                        al = learning.alias_request(str(rec_sig), task)
                        out["aliased"] = bool(al.get("aliased"))
                    except Exception:
                        pass
                if hasattr(learning, "reinforce"):
                    try:
                        learning.reinforce(task, verified, sig=str(rec_sig))
                        out["reinforced"] = str(rec_sig)[:40]
                    except Exception:
                        pass
                self._feel_outcome(task, res, verified)
                self.last_learn = out
                return out
            rec = learning.learn_from_task(task, sol, {
                "source": method, "verified": verified,
                "language": res.get("language") or "python",
                "verifier_kind": kind or "none",
                "trusted": bool(res.get("trusted")),
                "trial": str(res.get("route_path") or "") == "trial_replay"},
                verified=verified) or {}
            record = rec.get("record") if isinstance(rec.get("record"), dict) else {}
            out = {"learned": bool(rec.get("stored")), "verified": verified,
                   "evidence": kind or "none",
                   "recallable": bool(rec.get("recallable")),
                   "confidence": record.get("confidence"),
                   "reason": rec.get("reason")}
            self._feel_outcome(task, res, verified)
        except Exception as e:
            out = {"learned": False, "error": str(e)[:140]}
        self.last_learn = out
        return out

    def _feel_outcome(self, task: str, res: dict, verified: bool) -> None:
        """An exit code is an event in his world, not only a row in a store.

        Passing execution lights the task on the projection neurons and counts as
        something learned; failing is adversity, carrying the error as its detail.
        Without this the connectome learns nothing at all about coding, because
        nothing about coding ever reaches it -- the library would fill while the
        animal stayed empty, which is a database and not a being.
        """
        agent = self.agent
        if agent is None:
            return
        lang = getattr(agent, "language", None)
        mod = getattr(agent, "modulation", None)
        try:
            if verified:
                if lang is not None and hasattr(lang, "experience"):
                    lang.experience("droso", "passes", str(task)[:60])
                elif lang is not None and hasattr(lang, "ground"):
                    lang.ground("task_passed", str(task)[:60])
                if mod is not None and hasattr(mod, "note_learning"):
                    mod.note_learning()
            else:
                detail = str(res.get("error") or res.get("stderr")
                             or "did not verify")[:160]
                # Failing is an act of his too, and it is the one worth
                # remembering with a doer attached: "droso fails <task>" is a
                # proposition he can be asked about later, where an adversity
                # level is only a mood.
                if lang is not None and hasattr(lang, "experience"):
                    lang.experience("droso", "fails", str(task)[:60])
                if lang is not None and hasattr(lang, "adversity"):
                    lang.adversity("code_failed", detail, 0.5)
        except Exception:
            pass

    def _compose(self, task, pats):
        hit = None
        try:
            hit = self.local.compose(pats, task)
        except Exception:
            hit = None
        if not hit:
            return {"solution": "", "method": "composition_declined",
                    "api_calls": 0, "tokens": 0,
                    "note": "assembled pieces did not verify; composition "
                            "refuses to hand back an unverified paste"}
        return hit

    def _direct(self, task):
        """Answer a question without the reasoning loop -- but not without the
        cheap rungs. The optimizer still gets first refusal, so a repeat question
        is a cache hit rather than a second payment. A fast path that skipped the
        cache would quietly break the cost guarantee it exists to protect.
        """
        agent = self.agent
        if agent is not None and getattr(agent, "token_optimizer", None) is not None:
            r = agent.ask_api(task) or {}
            return {"solution": r.get("solution", ""), "method": "direct_api",
                    "api_calls": int(r.get("api_calls", 0) or 0),
                    "tokens": int(r.get("tokens_used", 0) or 0),
                    "verified": bool(r.get("verified")), "route": r.get("route"),
                    "provenance": r.get("provenance"),
                    "reason": r.get("reason") or (r.get("reasons") or [None])[0]}
        if self.api is None:
            return {"solution": "", "method": "none", "api_calls": 0,
                    "reason": "no oracle configured"}
        try:
            r = self.api.query(task, max_tokens=self.direct_api_max_tokens,
                               purpose="direct")
        except NoAPIKeyError as e:
            return {"solution": "", "method": "none", "api_calls": 0,
                    "reason": str(e)}
        return {"solution": r.get("text", ""), "method": "direct_api",
                "api_calls": 1 if r.get("ok") else 0,
                "tokens": int(r.get("prompt_tokens_est", 0) or 0) +
                int(r.get("completion_tokens_est", 0) or 0),
                "verified": False,
                "mode": r.get("mode"), "reason": r.get("reason"),
                "provenance": ["direct_api(no verification available)"]}

    def _direct_affordable(self) -> str:
        """"" if direct_api can answer; otherwise the reason it cannot.

        The router once proposed direct_api under a 300-token per-query ceiling
        while asking for 300 completion tokens: every such call was refused before
        it started, and the user saw an empty "answered" result. Proposing a rung
        that cannot run is worse than proposing a slower one. The same reasoning
        covers a human switching the LLM off, a key that is not configured and a
        process fenced from the network -- all three make direct_api a rung that
        cannot run, so none of them is proposed, and the reason the router gave up
        is the reason it says out loud.
        """
        api = self.api
        if api is None:
            return "no oracle wired into this router"
        if not getattr(api, "has_key", True):
            return "no API credential configured"
        if getattr(api, "offline", False):
            return "this process is fenced from providers (HYBRIDLLM_OFFLINE)"
        agent = self.agent
        if agent is not None and not getattr(agent, "llm_enabled", True):
            return "the LLM switch is off"
        b = getattr(api, "budget", None)
        if b is None:
            return ""
        try:
            return "" if b.check(int(self.direct_api_max_tokens) + 128) is None \
                else "oracle budget ceiling is below what a direct answer costs"
        except Exception:
            return ""

    def _loop(self, task):
        if self.agent is None:
            return {"solution": "", "method": "none", "api_calls": 0,
                    "reason": "no reasoning agent attached"}
        out = self.agent.solve_task(task, fast_path=False)
        return out if isinstance(out, dict) else {"solution": str(out)}

    def is_code_shaped(self, task: str) -> bool:
        t = str(task or "").lower()
        return bool(_CODE_SHAPE.search(t) or _FILE_SHAPE.search(t) or
                    _MULTI_REQ.search(t))

    def _is_simple_query(self, task: str) -> bool:
        """A question -- not merely a short sentence.

        The brief's detector sent anything under eight words straight to the API,
        which includes "rename x and test it": an imperative with an artifact to
        get wrong. `direct_api` cannot verify, so the quality guarantee forbids
        routing it there. The line this draws is interrogative form, not length:
        questions bypass, jobs do not, however brief.
        """
        t = str(task or "").lower().strip()
        if not t:
            return False
        if self.is_code_shaped(t):
            return False
        if _QUESTION.search(t):
            return True
        return bool(_PROSE_ASK.match(t)) and len(t.split()) < \
            max(8, self.simple_max_words)

    def _plan(self, path, task, est_ms, est_tokens, reason, handler) -> dict:
        return {"path": path, "task": str(task)[:120], "handler": handler,
                "estimated_ms": est_ms, "estimated_tokens": est_tokens,
                "estimate_basis": "design-brief prior; see measured_ms for fact",
                "reason": reason, "api_calls": 1 if path == DIRECT_API else 0,
                "bypasses_reasoning_loop": path != REASONING_LOOP,
                "verified_output_possible": path != DIRECT_API}

    def note_execution(self, path: str, ms: float) -> None:
        """Record a run that happened through another door.

        solve_task executes handlers itself (it has to, to keep the loop's
        context and breaker wiring), so without this seam the per-path medians
        stayed empty forever and the speed guarantee could never accumulate the
        evidence it is stated in terms of.
        """
        self.runs += 1
        self.decisions[path] = self.decisions.get(path, 0) + 1
        self.measured.setdefault(path, []).append(round(float(ms), 3))
        if len(self.measured[path]) > 50:
            del self.measured[path][:len(self.measured[path]) - 50]

    def median_ms(self, path: str = None) -> float | None:
        xs = self.measured.get(path, []) if path else \
            [v for vs in self.measured.values() for v in vs]
        if not xs:
            return None
        xs = sorted(xs)
        return xs[len(xs) // 2]

    def median_decision_ms(self) -> float | None:
        """What routing itself costs. This is the number the speed guarantee
        actually has to pay: the loop bypass saves nothing if deciding takes
        longer than thinking."""
        if not self.decision_ms:
            return None
        xs = sorted(self.decision_ms)
        return xs[len(xs) // 2]

    def stats(self) -> dict:
        return {"decisions": dict(self.decisions), "runs": self.runs,
                "fast_path_enabled": self.fast_path,
                "fell_through": self.skipped,
                "median_ms_by_path": {k: self.median_ms(k)
                                      for k in self.measured if self.measured[k]},
                "decision_overhead_ms": self.median_decision_ms(),
                "samples_by_path": {k: len(v) for k, v in self.measured.items()},
                "replay_confidence": self.replay_confidence,
                "min_patterns_for_composition": self.min_patterns,
                "simple_max_words": self.simple_max_words,
                "code_shaped_tasks_never_bypass_verification": True,
                "last": {k: v for k, v in (self.last or {}).items()
                         if k != "handler"}}

def router_from_config(cfg: dict | None = None, api_oracle=None,
                       local_solver=None, reasoning_agent=None) -> FastRouter:
    c = dict((cfg or {}).get("connectome", {}) or {})
    f = dict(c.get("fast_path", {}) or {})
    return FastRouter(api_oracle=api_oracle, local_solver=local_solver,
                      reasoning_agent=reasoning_agent,
                      replay_confidence=float(f.get("replay_confidence", 0.9)),
                      min_patterns=int(f.get("min_patterns", 3)),
                      simple_max_words=int(f.get("simple_max_words", 8)),
                      fast_path=bool(f.get("enabled", True)),
                      direct_api_max_tokens=int(f.get("direct_api_max_tokens",
                                                      300)))