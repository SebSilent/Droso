"""Can two lives do something one life could not? An experiment that is allowed to say no.

WHY THE LAST ONE WAS WORTHLESS, AND WHAT CHANGED. The previous run declared "compounding"
off 3 held-out tasks against 1 -- z 1.01, inside the noise band -- and worse, every arm had
solved 97-100% of its own slice FROM THE CORPUS, so nothing had ever depended on which arm
you were in. The branch structure was never exercised. Two guards now refuse to speak in
that situation, and this file is what tries again with a split that might actually be
disjoint.

THE SPLIT IS BY FACT, NOT AT RANDOM. Tasks are partitioned by the (concept, subject) key
their own text yields: solids and figures to one arm, integers and numbers to the other.
The point of partitioning by fact is that each arm's fact store can then be genuinely
unable to answer the other's slice -- which is a property no random split has.

THE CHAIN THAT HAS TO HOLD, and each link is checked rather than assumed:

    arm A, no oracle, on slice B      ->  must be 0, or the split is not disjoint
    arm B, no oracle, on slice A      ->  must be 0, same check from the other side
    A's facts merged into one binder  ->  on slice B, must now be MORE than 0

If the first two are not zero, the split created no disjoint capability and THE VERDICT IS
REFUSED -- because then the merge could not have added anything, and a number would be
measuring the corpus instead of the arrangement of lives.

WHAT THIS CANNOT DO YET, stated here rather than discovered by a reader. The instruction
asked for one task needing a fact from BOTH categories combined. That task cannot be built
on this architecture: the harness slots ONE fact into ONE shape, so a body needing a sphere
formula and a prime count is not expressible as a candidate, and the merged individual would
fail it too -- for a reason that has nothing to do with lives. So the combined task is
replaced by the cross-slice test, which asks the same question at the resolution the machine
actually has: does a fact from the OTHER life make a task solvable that neither this life nor
the corpus could reach. The gap is real and is left visible.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GEOMETRY = {"sphere", "cylinder", "circle", "cone", "cube", "cuboid", "triangle",
            "rectangle"}
NUMBER = {"integer", "number"}


def _agent():
    from tools.knowledge_run import _agent as kagent
    return kagent()


def slice_by_fact(rows):
    from organs.concepts import extract_key
    a, b, other = [], [], []
    for r in rows:
        c, s, _sh = extract_key(r["task"], r["check"])
        if not c:
            other.append(r)
        elif s in GEOMETRY:
            a.append(r)
        elif s in NUMBER:
            b.append(r)
        else:
            other.append(r)
    return a, b, other


def _run_arm(tasks, label: str, max_calls: int = 1) -> dict:
    """A life that has only ever seen its own slice, with the oracle available."""
    from organs.knowledge import KnowledgeChannel
    from organs.harness import Harness
    agent = _agent()
    loop = agent.reasoning_loop
    ch = KnowledgeChannel(oracle=agent.api_oracle, loop=loop,
                          learning=getattr(agent, "learning_loop", None),
                          max_calls_per_task=int(max_calls))
    h = Harness(loop=loop, solver=loop.solver, sandbox=loop.sandbox,
                learning=getattr(agent, "learning_loop", None), channel=ch)
    for r in tasks:
        h.solve(r["task"], r["check"], learn=False)
    binder = getattr(getattr(agent.language, "cortex", None), "binder", None)
    facts = dict(getattr(binder, "facts", {}) or {})
    return {"label": label, "agent": agent, "loop": loop, "binder": binder,
            "facts": facts, "report": h.report(), "channel": ch.stats(),
            "store": dict(getattr(getattr(agent, "learning_loop", None), "store", {}) or {})}


def _eval_no_oracle(arm: dict, tasks, extra_facts=None, store=None) -> dict:
    """Evaluate with the oracle OFF. No oracle means a fact can only come from a store."""
    from organs.harness import Harness
    loop = arm["loop"]
    binder = arm["binder"]
    saved = dict(getattr(binder, "facts", {}) or {})
    learning = getattr(loop, "learning", None)
    saved_store = dict(getattr(learning, "store", {}) or {})
    if extra_facts is not None and binder is not None:
        binder.facts = dict(extra_facts)
    if store is not None and learning is not None:
        learning.store = dict(store)
    h = Harness(loop=loop, solver=loop.solver, sandbox=loop.sandbox,
                learning=learning, channel=None)   # channel=None IS the no-oracle fence
    for r in tasks:
        h.solve(r["task"], r["check"], learn=False)
    rep = h.report()
    if binder is not None:
        binder.facts = saved
    if learning is not None:
        learning.store = saved_store
    return rep


def run(limit: int | None = None) -> dict:
    from tools.make_curriculum import load
    rows = load("holdout")
    if limit:
        rows = rows[:int(limit)]
    A, B, other = slice_by_fact(rows)
    out = {"holdout": len(rows), "slice_geometry": len(A), "slice_number": len(B),
           "unkeyed_or_other": len(other), "note": "slices are small; see caveat"}

    t0 = time.time()
    arm_a = _run_arm(A, "geometry")
    arm_b = _run_arm(B, "number")
    out["arm_a"] = {"tasks": len(A), "facts_filed": len(arm_a["facts"]),
                    "channel": arm_a["channel"]}
    out["arm_b"] = {"tasks": len(B), "facts_filed": len(arm_b["facts"]),
                    "channel": arm_b["channel"]}

    # THE DISJOINTNESS CHECK, both directions, oracle off.
    a_on_b = _eval_no_oracle(arm_a, B)
    b_on_a = _eval_no_oracle(arm_b, A)
    out["arm_a_alone_on_slice_B"] = a_on_b["solved"]
    out["arm_b_alone_on_slice_A"] = b_on_a["solved"]

    # THE MERGE: one of them, given the other's facts and procedures.
    merged_facts = dict(arm_a["facts"])
    merged_facts.update(arm_b["facts"])
    merged_store = dict(arm_a["store"])
    merged_store.update(arm_b["store"])
    a_merged_on_b = _eval_no_oracle(arm_a, B, extra_facts=merged_facts,
                                    store=merged_store)

    # AND THE CONTROL: the same arm, same evaluation, WITHOUT the other life's facts. At
    # equal compute, so the only difference is where the knowledge came from.
    a_control_on_b = _eval_no_oracle(arm_a, B, extra_facts=dict(arm_a["facts"]),
                                     store=dict(arm_a["store"]))
    out["arm_a_control_on_slice_B"] = a_control_on_b["solved"]
    out["arm_a_merged_on_slice_B"] = a_merged_on_b["solved"]
    out["merged_solved_by"] = a_merged_on_b.get("counts")
    out["control_solved_by"] = a_control_on_b.get("counts")
    out["seconds"] = round(time.time() - t0, 1)

    # THE GUARD, BEFORE ANY VERDICT. If either arm could already do the other's work, the
    # split bought nothing and any difference below is the corpus, not the lives.
    if out["arm_a_alone_on_slice_B"] or out["arm_b_alone_on_slice_A"]:
        out["verdict"] = ("REFUSED: the split is not disjoint (arm A solved %d of B's "
                          "slice, arm B solved %d of A's), so nothing here is about "
                          "splitting work across lives"
                          % (out["arm_a_alone_on_slice_B"],
                             out["arm_b_alone_on_slice_A"]))
        return out
    if not arm_b["facts"]:
        out["verdict"] = ("REFUSED: arm B filed no facts, so the merge has nothing to "
                          "carry across")
        return out
    delta = out["arm_a_merged_on_slice_B"] - out["arm_a_control_on_slice_B"]
    out["delta"] = delta
    if delta > 0:
        out["verdict"] = ("COMPOUNDING: %d of %d tasks in slice B are solvable with the "
                          "other life's facts and %d without"
                          % (out["arm_a_merged_on_slice_B"], len(B),
                             out["arm_a_control_on_slice_B"]))
    elif delta == 0:
        out["verdict"] = ("POOLING, NOT COMPOUNDING: the split is disjoint and the other "
                          "life's facts change nothing (%d vs %d)"
                          % (out["arm_a_merged_on_slice_B"],
                             out["arm_a_control_on_slice_B"]))
    else:
        out["verdict"] = "merge WORSE than control: %d vs %d" % (
            out["arm_a_merged_on_slice_B"], out["arm_a_control_on_slice_B"])
    return out


def main() -> int:
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    res = run(lim)
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
