from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

DT_SUBSTEP_S = 0.005
SUB_STEPS_PER_DECISION = 10
NEURONS = 12867

FLY_NEURONS = 1e5
FLY_HZ = 5.0
FLY_DAY_EVENTS = FLY_NEURONS * FLY_HZ * 86400.0
FLY_LIFETIME_DAYS = 50.0
YEAR_S = 365 * 86400.0

@dataclass
class LivedTime:
    """Append-only ledger of simulated existence, by system name."""
    path: Path | None = None
    entries: dict = field(default_factory=dict)
    wall_start: float = field(default_factory=time.time)
    _session: dict = field(default_factory=dict)

    @staticmethod
    def neural_seconds(decisions: float, sub_steps: int = SUB_STEPS_PER_DECISION) -> float:
        return decisions * sub_steps * DT_SUBSTEP_S

    @staticmethod
    def neuron_events(decisions: float, neurons: int = NEURONS,
                      sub_steps: int = SUB_STEPS_PER_DECISION) -> float:
        return decisions * sub_steps * neurons

    def add(self, system: str, decisions: float, beings: int = 1, generations: int = 0):
        e = self.entries.setdefault(system, {"decisions": 0, "beings": 0, "generations": 0})
        e["decisions"] += int(decisions)
        e["beings"] += int(beings)
        e["generations"] += int(generations)
        s = self._session.setdefault(system, {"decisions": 0, "beings": 0})
        s["decisions"] += int(decisions)
        s["beings"] += int(beings)

    def totals(self) -> dict:
        dec = sum(e["decisions"] for e in self.entries.values())
        ev = self.neuron_events(dec)
        ns = self.neural_seconds(dec)
        return {
            "decisions": dec,
            "neural_seconds": ns,
            "neural_hours": ns / 3600.0,
            "neural_days": ns / 86400.0,
            "neural_years": ns / YEAR_S,
            "neuron_update_events": ev,
            "fly_days_equivalent": ev / FLY_DAY_EVENTS,
            "fly_lifetimes_equivalent": ev / (FLY_DAY_EVENTS * FLY_LIFETIME_DAYS),
            "beings": sum(e["beings"] for e in self.entries.values()),
            "generations": sum(e["generations"] for e in self.entries.values()),
            "by_system": self.entries,
        }

    def print_totals(self, wall_s: float | None = None):
        t = self.totals()
        wall = (time.time() - self.wall_start) if wall_s is None else wall_s
        print(f"\n=== LIVED TIME (ledger) ===", flush=True)
        for sysname, e in t["by_system"].items():
            print(f"  {sysname:28s} {e['decisions']:>14,} decisions  "
                  f"{self.neural_seconds(e['decisions'])/YEAR_S:>10,.1f} neural-years"
                  f"  beings={e['beings']:,} generations={e['generations']:,}", flush=True)
        print(f"  TOTAL {t['decisions']:,} decisions = {t['neural_hours']:,.0f} h = "
              f"{t['neural_days']:,.1f} d = {t['neural_years']:,.2f} yr of neural time",
              flush=True)
        print(f"        = {t['neuron_update_events']:.3e} neuron-update events "
              f"= {t['fly_days_equivalent']:,.1f} fly-days "
              f"= {t['fly_lifetimes_equivalent']:,.3f} fly-lifetimes", flush=True)
        if wall > 0:
            print(f"        simulated in {wall:,.0f} s wall-clock "
                  f"-> acceleration x{t['neural_seconds']/wall:,.0f}", flush=True)
        return t

    @classmethod
    def load(cls, path: Path) -> "LivedTime":
        lt = cls(path=path)
        if path.exists():
            lt.entries = json.loads(path.read_text(encoding="utf-8")).get("entries", {})
        return lt

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(exist_ok=True, parents=True)
        self.path.write_text(json.dumps({"entries": self.entries,
                                         "constants": {"dt_substep_s": DT_SUBSTEP_S,
                                                       "sub_steps_per_decision": SUB_STEPS_PER_DECISION,
                                                       "neurons": NEURONS}}, indent=1),
                             encoding="utf-8")

    def session_delta(self, wall_s: float) -> dict:
        """What THIS run added, for reporting alongside the cumulative ledger."""
        out = {}
        for sysname, s in self._session.items():
            ns = self.neural_seconds(s["decisions"])
            out[sysname] = {**s, "neural_seconds": ns, "neural_years": ns / YEAR_S,
                            "neuron_events": self.neuron_events(s["decisions"]),
                            "acceleration_x": ns / max(wall_s, 1e-9)}
        return out