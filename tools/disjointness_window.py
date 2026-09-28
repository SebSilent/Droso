"""Is re-deriving a solution more expensive than recalling it? Measure the window.

WHY THIS DECIDES ANYTHING. `exp_selftransfer` returned REFUSED because each arm re-derived the
other arms' slices -- the arms were not disjoint, so the merge could not have added anything.
Whether a self-compounding experiment is POSSIBLE AT ALL depends on one measured fact: is
re-derivation substantially more expensive than recall? If it is, there is a window in which
stored knowledge beats re-search and arms can be genuinely disjoint. If it is not, then
storing a solution confers no advantage and independent-task self-compounding is not
measurable with this architecture -- which is itself the finding.

THE THREE CAUSES THIS SEPARATES, which the ratio distinguishes:
  re-derivation >> recall   tasks are fine; the disjointness TEST BUDGET is too generous
  re-derivation ~  recall   tasks are too easy; storing them creates no advantage
  both near zero            the pool is saturated with trivial material and must be rebuilt

    python tools/disjointness_window.py --n 20
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CAND_KEYS = ("candidates", "n_candidates", "attempts", "tried", "steps", "n_attempts",
             "generated", "proposals", "search_steps")


def _cands(res: dict):
    """How many candidates the loop tried. The real measure of SEARCH cost.

    IT LIVES INSIDE res["loop"], not at the top level. The first version of this probe looked
    only at the top level, found nothing, and reported `null` for every task -- which would
    have read as "the loop tried no candidates" and is the kind of quiet zero this project
    keeps having to remove.
    """
    inner = res.get("loop") if isinstance(res.get("loop"), dict) else {}
    out = {}
    for name, src in (("top", res), ("loop", inner)):
        for k in ("attempts_total", "attempt", "candidates", "episodes", "proposals"):
            v = src.get(k)
            if isinstance(v, int):
                out[f"{name}.{k}"] = v
            elif isinstance(v, (list, tuple)):
                out[f"{name}.{k}"] = len(v)
    return out or None


def measure(n: int = 20, limit: int = 3000) -> dict:
    from tools.curriculum_run import _loop_agent
    from organs.harness import Harness
    from tools.make_generated_pool import _load, OUT

    rows = _load(OUT / "generated_selfdistill.jsonl")[:limit]
    agent = _loop_agent()
    loop = agent.reasoning_loop
    h = Harness(loop=loop, solver=loop.solver, sandbox=loop.sandbox,
                learning=getattr(agent, "learning_loop", None), channel=None)

    rep = {"tasks": 0, "rows": [], "field_probe": None}
    for r in rows:
        if rep["tasks"] >= n:
            break
        task, check = r["task"], r["check"]
        # 1. FROM SCRATCH, store untouched: this IS the re-derivation cost.
        t0 = time.time()
        r1 = h.solve(task, check, learn=False, oracle=False)
        t1 = time.time() - t0
        if rep["field_probe"] is None:
            rep["field_probe"] = sorted(r1.keys())
        # 2. LEARN it, so the store has the procedure/fact for this key.
        h.solve(task, check, learn=True, oracle=False)
        # 3. RECALL: the same task again, now that it is stored.
        t2 = time.time()
        r3 = h.solve(task, check, learn=False, oracle=False)
        t3 = time.time() - t2
        rep["tasks"] += 1
        rep["rows"].append({
            "id": r.get("id"), "task": task[:60],
            "rederive_s": round(t1, 3), "rederive_branch": r1.get("branch"),
            "rederive_solved": bool(r1.get("solved")), "rederive_cands": _cands(r1),
            "recall_s": round(t3, 3), "recall_branch": r3.get("branch"),
            "recall_solved": bool(r3.get("solved")), "recall_cands": _cands(r3),
            "ratio": (round(t1 / t3, 2) if t3 > 0 else None),
        })

    rows_out = rep["rows"]
    red = [x["rederive_s"] for x in rows_out]
    rec = [x["recall_s"] for x in rows_out]
    ratios = [x["ratio"] for x in rows_out if x["ratio"] is not None]
    rep["summary"] = {
        "n": len(rows_out),
        "rederive_median_s": round(statistics.median(red), 3) if red else None,
        "recall_median_s": round(statistics.median(rec), 3) if rec else None,
        "ratio_median": round(statistics.median(ratios), 2) if ratios else None,
        "ratio_min": min(ratios) if ratios else None,
        "ratio_max": max(ratios) if ratios else None,
        "rederive_median_cands": _median([x["rederive_cands"].get("loop.attempts_total")
                                          for x in rows_out if x["rederive_cands"]]),
        "recall_median_cands": _median([x["recall_cands"].get("loop.attempts_total")
                                        for x in rows_out if x["recall_cands"]]),
        "rederive_max_cands": max([x["rederive_cands"].get("loop.attempts_total") or 0
                                   for x in rows_out if x["rederive_cands"]] or [0]),
        "branches_rederive": _counts(x["rederive_branch"] for x in rows_out),
        "branches_recall": _counts(x["recall_branch"] for x in rows_out),
        "solved_rederive": sum(1 for x in rows_out if x["rederive_solved"]),
        "solved_recall": sum(1 for x in rows_out if x["recall_solved"]),
    }
    return rep


def _median(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 2) if xs else None


def _counts(it):
    out = {}
    for x in it:
        out[str(x)] = out.get(str(x), 0) + 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    a = ap.parse_args()
    rep = measure(a.n)
    Path("state/disjointness_window.json").write_text(json.dumps(rep, indent=1),
                                                      encoding="utf-8")
    s = rep["summary"]
    print(json.dumps(s, indent=1))
    print("\nres fields available:", rep["field_probe"])
    print("\nper task:")
    for x in rep["rows"]:
        dc = (x["rederive_cands"] or {}).get("loop.attempts_total")
        rc = (x["recall_cands"] or {}).get("loop.attempts_total")
        print(f"  {str(x['id']):16} rederive {x['rederive_s']:6.2f}s ({x['rederive_branch']},"
              f" cands={dc}) | recall {x['recall_s']:6.2f}s ({x['recall_branch']},"
              f" cands={rc}) | ratio {x['ratio']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
