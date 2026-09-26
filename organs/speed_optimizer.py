
from __future__ import annotations

import json
import math
import time
from pathlib import Path

EXO = Path("C:/Projects/HybridLLM/exocortex")

ARMS = ("A_PROCEDURE_REPLAY", "B_AST_MUTATION", "C_RESIDUAL_INJECTION",
        "D_FULL_STREAMING", "E_REASONING")
ARM_LABEL = {"A": "A_PROCEDURE_REPLAY", "B": "B_AST_MUTATION",
             "C": "C_RESIDUAL_INJECTION", "D": "D_FULL_STREAMING",
             "E": "E_REASONING"}

class SpeedOptimizer:
    def __init__(self, path: str | Path = EXO / "speed_routing.json",
                 time_cost: float = 0.02, seed: int = 0):
        self.path = Path(path)
        self.t: dict = json.loads(self.path.read_text(encoding="utf-8")) \
            if self.path.exists() else {}
        self.time_cost = time_cost
        self.rng = __import__("numpy").random.RandomState(seed)

    def save(self):
        self.path.write_text(json.dumps(self.t), encoding="utf-8")

    def _arm(self, task_type: str, arm: str) -> dict:
        return self.t.setdefault(task_type, {}).setdefault(
            arm, {"n": 0, "mean": 0.0, "last": 0.0})

    def choose(self, task_type: str, eligible: set[str] | None = None) -> str:
        arms = [a for a in ARMS if eligible is None or a in eligible]
        if not arms:
            arms = ["B_AST_MUTATION"]
        tab = self.t.get(task_type, {})
        for a in arms:
            if tab.get(a, {}).get("n", 0) == 0:
                return a
        t_tot = sum(tab[a]["n"] for a in arms) + 1e-9
        best, bv = None, -1e9
        for a in arms:
            e = tab[a]
            ucb = e["mean"] + math.sqrt(2.0 * math.log(max(t_tot, 2))
                                        / e["n"])
            if ucb > bv:
                best, bv = a, ucb
        return best

    def record(self, task_type: str, arm: str, seconds: float,
               success: bool):
        e = self._arm(task_type, arm)
        r = (3.0 if success else -0.6) - self.time_cost * seconds
        e["n"] += 1
        e["mean"] += (r - e["mean"]) / e["n"]
        e["last"] = time.time()
        self.save()

    def policy_view(self, task_type: str) -> dict:
        tab = self.t.get(task_type, {})
        if not tab:
            return {"task_type": task_type, "preferred_strategy": None}
        ranked = sorted(tab.items(), key=lambda kv: -kv[1]["mean"])
        pref, second = ranked[0][0], (ranked[1][0] if len(ranked) > 1 else None)
        never = [a for a, e in ranked if e["n"] >= 3 and e["mean"] < -0.5]
        n_tot = sum(e["n"] for e in tab.values())
        ok = sum(e["n"] for e in tab.values() if e["mean"] > 0)
        return {"task_type": task_type, "preferred_strategy": pref,
                "fallback_strategy": second, "never_use": never[:1],
                "pulls": n_tot,
                "success_rate_proxy": round(ok / max(n_tot, 1), 2)}

    def distribution(self) -> dict:
        out = {a: 0 for a in ARMS}
        for tab in self.t.values():
            for a, e in tab.items():
                out[a] = out.get(a, 0) + e["n"]
        tot = sum(out.values()) or 1
        return {a: round(v / tot, 3) for a, v in out.items()}

    def stats(self) -> dict:
        return {"task_types": len(self.t), "arm_distribution":
                self.distribution(),
                "policies": [self.policy_view(k)
                             for k in list(self.t)[:8]]}