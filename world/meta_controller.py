
from __future__ import annotations

import time

from core.action_space import ACTIONS_V5

FAST_CONF = 0.85
MEDIUM_SIM = 0.35

class MetaController:
    def __init__(self, exo_agent, reasoning_agent, speed_optimizer):
        self.exo = exo_agent
        self.reasoning = reasoning_agent
        self.speed = speed_optimizer
        self.routes = {"fast_ast": 0, "fast_reasoning_replay": 0,
                       "medium_ast": 0, "slow_reasoning": 0}
        self.outcomes = {k: [0, 0] for k in self.routes}

    def route_task(self, task, grade_fn=None) -> dict:
        spec = task if isinstance(task, dict) else {"text": str(task)}
        text = spec.get("text", "")
        start = time.time()
        exo_org = self.exo.exo
        sig = exo_org.signature(text)
        proc = exo_org.recall_procedure(sig)
        if proc and proc.get("confidence", 0) > FAST_CONF:
            if proc.get("type") == "REASONING_CHAIN":
                route = "fast_reasoning_replay"
                res = self.reasoning.replay_reasoning(spec, proc, grade_fn)
            else:
                route = "fast_ast"
                res = self.exo.solve(spec, grade_fn=grade_fn)
            return self._done(route, spec, res, start)
        sim = self._similarity(text)
        if sim >= MEDIUM_SIM:
            route = "medium_ast"
            res = self.exo.solve(spec, grade_fn=grade_fn)
            return self._done(route, spec, res, start)
        route = "slow_reasoning"
        res = self.reasoning.solve_task(spec, grade_fn=grade_fn)
        return self._done(route, spec, res, start)

    def _similarity(self, text: str) -> float:
        try:
            hits = self.exo.exo.search_concepts(text, k=1)
            for h in hits:
                s = h.get("score") or h.get("similarity") or 0.0
                if s:
                    return float(s)
        except Exception:
            pass
        return 0.0

    def _done(self, route, spec, res, start) -> dict:
        res = dict(res or {})
        ok = bool(res.get("success"))
        secs = time.time() - start
        res.setdefault("seconds", round(secs, 2))
        res["route"] = route
        self.routes[route] += 1
        self.outcomes[route][0] += int(ok)
        self.outcomes[route][1] += 1
        try:
            tt = (self.exo._analyze(spec.get("text", ""),
                                    spec.get("id", "?")).get("type")
                  if hasattr(self.exo, "_analyze") else "assemble")
        except Exception:
            tt = "assemble"
        arm = {"fast_ast": "A_PROCEDURE_REPLAY",
               "fast_reasoning_replay": "A_PROCEDURE_REPLAY",
               "medium_ast": "B_AST_MUTATION",
               "slow_reasoning": "E_REASONING"}[route]
        self.speed.record(tt, arm, secs, ok)
        return res

    def stats(self) -> dict:
        return {"routes": self.routes,
                "success_by_route": {k: [v[0], v[1]] for k, v in
                                     self.outcomes.items()},
                "thinking_rate": round(self.routes["slow_reasoning"] /
                                       max(sum(self.routes.values()), 1), 3)}