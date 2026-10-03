"""Replace-vs-merge: what has the marginal-life curve actually been measuring?

THE QUESTION. `_eval_no_oracle` does `binder.facts = dict(extra_facts)` and
`learning.store = dict(store)` -- it REPLACES the receiver's knowledge rather than adding to
it -- and the marginal accumulator is built FROM EMPTY. So every curve point so far answers
"what can be solved with ONLY the other lives' knowledge", not "what does merging ADD to this
life's own knowledge". Those are different claims and everything citing these curves needs to
know which one it is reading.

This recomputes the number-slice curve twice on the same arms, changing only the starting
accumulator:
    from empty   -- as implemented
    keep-own     -- starting from the receiver's own facts and store

It does not touch the experiment code; it answers the question and leaves the design decision
where it belongs.

    python tools/merge_semantics_probe.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _eval_ids(arm, tasks, extra_facts, extra_sources, store):
    """Mirrors `_eval_no_oracle` but returns PER-TASK outcomes, so the dropped task can be
    named. `_eval_no_oracle` returns only a count, and a count cannot tell you which task
    changed -- which is why the anomaly has survived several rounds as a footnote.
    """
    import tools.population_experiment as PE
    from organs.harness import Harness
    loop = arm["loop"]
    binder = arm["binder"]
    saved = dict(getattr(binder, "facts", {}) or {})
    saved_sources = dict(getattr(binder, "fact_sources", {}) or {})
    learning = getattr(loop, "learning", None)
    saved_store = dict(getattr(learning, "store", {}) or {})
    if binder is not None:
        binder.facts = dict(extra_facts)
        binder.fact_sources = dict(extra_sources or {})
    if learning is not None:
        learning.store = dict(store)
    h = Harness(loop=loop, solver=loop.solver, sandbox=loop.sandbox,
                learning=learning, channel=None)
    out_map = {}
    for r in tasks:
        # WHAT THE FACT PATH ACTUALLY RETURNED, recorded before the solve. The count alone
        # said a task flipped; only this says whether the fact was found, and if it was,
        # whether its code still resolved out of the merged learning store.
        fdet = {}
        try:
            f = h._fact(r["task"], r["check"]) or {}
            lstore = getattr(learning, "store", {}) or {}
            fdet = {"found": bool(f.get("found")), "reason": str(f.get("reason"))[:44],
                    "ref": str(f.get("ref"))[:40],
                    "ref_in_store": (f.get("ref") in lstore) if f.get("ref") else None,
                    "code_len": len(str(f.get("code") or ""))}
        except Exception as exc:
            fdet = {"error": "%s: %s" % (type(exc).__name__, str(exc)[:50])}
        try:
            o = h.solve(r["task"], r["check"], learn=False)
            out_map[r["id"]] = {"solved": bool(o.get("solved")),
                                 "branch": o.get("branch"),
                                 "candidate": str(o.get("candidate") or "")[:60],
                                 "fact": fdet}
        except Exception as exc:
            out_map[r["id"]] = {"solved": False, "branch": "EXCEPTION",
                                 "candidate": "%s: %s" % (type(exc).__name__, str(exc)[:70]),
                                 "fact": fdet}
    if binder is not None:
        binder.facts = saved
        binder.fact_sources = saved_sources
    if learning is not None:
        learning.store = saved_store
    return out_map


def run(target: str = "number") -> dict:
    import tools.population_experiment as PE

    groups = ["geometry", "number", "string", "collection"]
    rows = PE._pool("generated_screened")
    slices, other = PE.slice_multi(rows, list(groups))
    arms = {g: PE._run_arm(slices[g], g) for g in groups if slices.get(g)}
    if target not in arms:
        return {"error": f"no arm for {target}"}
    recv_g = next(g for g in arms if g != target)
    receiver = arms[recv_g]
    # `_others` is a CLOSURE inside run_multi, not a module attribute. Replicated exactly:
    # it iterates `groups` in order and keeps only the ones that actually produced a slice.
    others = [g for g in groups if g != recv_g and slices.get(g)]

    def curve(keep_own: bool) -> list:
        acc_f, acc_s, acc_st = {}, {}, {}
        if keep_own:
            # THE ONLY CHANGE. Start from what the receiver already knows.
            acc_f.update(receiver["facts"])
            acc_s.update(receiver["fact_sources"])
            acc_st.update(receiver["store"])
        out = []
        for g in others:
            acc_f.update(arms[g]["facts"])
            acc_s.update(arms[g]["fact_sources"])
            acc_st.update(arms[g]["store"])
            m = _eval_ids(receiver, slices[target], dict(acc_f), dict(acc_s), dict(acc_st))
            out.append({"lives_giving": len(out) + 1,
                        "solved": sum(1 for v in m.values() if v["solved"]),
                        "map": m})
        return out

    return {"target_slice": target, "receiver_arm": recv_g, "n": len(slices[target]),
            "arm_sizes": {g: len(v) for g, v in slices.items()},
            "from_empty": curve(False),
            "keep_own": curve(True),
            "receiver_own_facts": len(receiver["facts"]),
            "receiver_own_store": len(receiver["store"])}


def main() -> int:
    rep = run("number")
    Path("state/merge_semantics.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    if rep.get("error"):
        print(json.dumps(rep, indent=1))
        return 1
    print(f"target slice {rep['target_slice']!r} (n={rep['n']}), receiver arm "
          f"{rep['receiver_arm']!r} (own facts {rep['receiver_own_facts']}, "
          f"own store {rep['receiver_own_store']})")
    print(f"arm sizes: {rep['arm_sizes']}")
    print()
    for label, key in (("AS IMPLEMENTED (from empty)", "from_empty"),
                       ("KEEP-OWN (from the receiver's own)", "keep_own")):
        c = rep[key]
        line = " | ".join(f"{p['lives_giving']}L->{p['solved']}" for p in c)
        drops = [f"{c[i]['lives_giving']}L->{c[i+1]['lives_giving']}L"
                 for i in range(len(c) - 1) if c[i + 1]["solved"] < c[i]["solved"]]
        print(f"  {label:34} {line}")
        print(f"       non-monotonic steps: {drops or 'none'}")
    print()
    a = [p["solved"] for p in rep["from_empty"]]
    b = [p["solved"] for p in rep["keep_own"]]
    print(f"drop under from-empty: {'YES' if any(a[i+1] < a[i] for i in range(len(a)-1)) else 'no'}")
    print(f"drop under keep-own  : {'YES' if any(b[i+1] < b[i] for i in range(len(b)-1)) else 'no'}")
    # NAME THE TASK. A count that changes without a name is what kept this a footnote.
    for label, key in (("from_empty", "from_empty"), ("keep_own", "keep_own")):
        c = rep[key]
        for i in range(len(c) - 1):
            before, after = c[i]["map"], c[i + 1]["map"]
            lost = [k for k, v in before.items() if v["solved"] and not after.get(k, {}).get("solved")]
            gained = [k for k, v in after.items() if v["solved"] and not before.get(k, {}).get("solved")]
            if lost:
                print(f"\n[{label}] {c[i]['lives_giving']}L -> {c[i+1]['lives_giving']}L "
                      f"LOST {len(lost)}, gained {len(gained)}")
                for k in lost:
                    print(f"    task {k}")
                    print(f"      {c[i]['lives_giving']}L: {before[k]}")
                    print(f"      {c[i+1]['lives_giving']}L: {after.get(k)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
