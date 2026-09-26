"""Probe: can a task needing TWO facts from two categories be solved by the merge?

The previous session documented this as UNBUILDABLE: "the harness slots ONE fact into ONE
shape, so a body needing a sphere formula and a prime count is not expressible". That claim
was about a SUM of two independent facts. It is not true of a PIPELINE, and compose_against
already builds pipelines (`outer(inner(*a))`). So before accepting the documented gap, this
checks it against the machine.

Geometry fact (arm A): cube_Sum(n)          -- the cube sum of the first n even naturals
Number fact  (arm B): next_Perfect_Square(N) -- the next perfect square greater than N
Combined task: the next perfect square greater than the cube sum
               -> next_Perfect_Square(cube_Sum(n)), expressible as a pipeline, keyed to
                  NEITHER arm alone.

Seeded from GOLD so the answer does not depend on the provider, exactly as the transfer
test does.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INNER = "Write a python function to find the cube sum of first n even natural numbers."
OUTER = "Write a python function to find the next perfect square greater than a given number."

COMBINED_TASK = ("Write a python function to find the next perfect square greater than the "
                 "cube sum of the first n even natural numbers.")
COMBINED_CHECK = ("\nassert next_square_cube(2) == 81\n"
                  "assert next_square_cube(3) == 289\n"
                  "assert next_square_cube(4) == 841")


def _seed(loop, task, gold):
    ok, why = loop._attempt({"code": gold, "label": "gold"}, "")
    loop.learning.learn_from_task(task, gold,
                                  {"source": "corpus", "verified": True,
                                   "language": "python",
                                   "verifier_kind": "task_check"}, verified=True)
    return {"stored": True, "attempt": bool(ok), "why": str(why)[:80]}


def main() -> int:
    from tools.knowledge_run import _agent
    from tools.make_curriculum import load
    agent = _agent()
    loop = agent.reasoning_loop
    rows = load("holdout")
    inner_gold = [r for r in rows if r["task"] == INNER][0]["gold"]
    outer_gold = [r for r in rows if r["task"] == OUTER][0]["gold"]
    print("gold inner functions:", [l.split("(")[0].replace("def ", "")
                                    for l in inner_gold.splitlines() if l.startswith("def")])
    print("gold outer functions:", [l.split("(")[0].replace("def ", "")
                                    for l in outer_gold.splitlines() if l.startswith("def")])

    empty = dict(getattr(loop.learning, "store", {}) or {})
    out = {"base_store": len(empty)}
    for label, seed_inner, seed_outer in (("A_only", True, False),
                                          ("B_only", False, True),
                                          ("merged", True, True)):
        loop.learning.store = dict(empty)
        if seed_inner:
            out["seed_inner"] = _seed(loop, INNER, inner_gold)
        if seed_outer:
            out["seed_outer"] = _seed(loop, OUTER, outer_gold)
        o = loop.step(COMBINED_TASK, COMBINED_CHECK, learn=False)
        out[label] = {"outcome": o.get("outcome"),
                      "candidate": str(o.get("candidate"))[:60],
                      "store_size": len(loop.learning.store),
                      "reason": str(o.get("reason"))[:100]}
        print(label, "->", out[label])
    loop.learning.store = dict(empty)

    # And the one-step control: does the combined task yield the right answer by hand?
    from organs.local_solver import _functions_in
    ns: dict = {}
    try:
        exec(inner_gold + "\n" + outer_gold, ns)
        got = [ns["next_Perfect_Square"](ns["cube_Sum"](n)) for n in (2, 3, 4)]
        out["hand_composed"] = got
    except Exception as exc:
        out["hand_composed"] = "%s: %s" % (type(exc).__name__, exc)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
