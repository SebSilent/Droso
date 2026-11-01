"""ELECTRIC object-role A/B arm: one variable (ELECTRIC_OBJECT_ROLE), reverse held ON in
both arms so the new path is measured against the CURRENT best behaviour, not against the
oldest one. Bare organ, no corpus, no multi-brain.

Arm A: reverse=True, object_role=False   (the C4d configuration)
Arm B: reverse=True, object_role=True    (one variable changed)

`answer()` wires as it reads, so the two arms are SEPARATE organs: a question asked in one
arm must not change the other. Inventories are asserted equal before any ask is scored.

The grader is imported from tools/electric_reverse_ab.py -- the SAME grader, deliberately,
so the numbers here are comparable with C4d's. The guarded grader contract in the battery
was not touched by either tool.
"""
import importlib.util as _u
import sys

sys.path.insert(0, ".")

_s = _u.spec_from_file_location("rev_ab", "tools/electric_reverse_ab.py")
_m = _u.module_from_spec(_s)
_s.loader.exec_module(_m)

import organs.neural_language as nl                                    # noqa: E402

TELLS = _m.TELLS

# The ask that C4d's table recorded as `want=None` is the one this arm exists to answer,
# and leaving it at None makes grade() score a CORRECT reply as a confabulation -- which is
# exactly what the first run of this tool did. The expectation is corrected HERE, in this
# arm's table, and tools/electric_reverse_ab.py is not touched: its None was right for the
# question C4d asked (does the reverse flag reach this shape?), and rewriting a measured
# arm's expectations to suit a later one would quietly un-report C4d's result.
_OVERRIDES = {"what bites the latch?": "the frost bites the latch"}
ASKS = [(a, s, _OVERRIDES.get(a, w)) for a, s, w in _m.ASKS] + [
    ("what bites the latch", "object-role-no?", "the frost bites the latch"),
    ("what chases the cat?", "object-role", "the mouse chases the cat"),
    # irregular past: the stem rule covers regular inflection only, and this says so
    ("what bit the latch?", "object-role-irregular", None),
    ("what holds the door?", "object-role-other", "the latch holds the door"),
    ("what breaks the latch?", "object-role-nofact", None),
    # the pre-existing subject-path mis-bind shape: listed so this arm cannot be read as
    # having fixed it. want=None means any answer here is reported, not hidden.
    ("what holds the latch?", "hazard-preexisting", None),
]


def build():
    # Reuse the C4d builder -- same organ, same tells, same seed -- with the reverse flag
    # ON, so this arm measures the object-role path against the CURRENT best behaviour.
    # Only ELECTRIC_OBJECT_ROLE differs, and it is set per INSTANCE (an instance attribute
    # shadows the class one) so the two arms cannot leak into each other.
    #
    # C4d's builder leaves ELECTRIC_TEACH ON, and this arm closes it before asking. Not
    # because questions were found to leak into the inventory -- they cannot, `answer()`
    # never calls `hear()`, which is the only call site of `_absence_note`, and a probe
    # asking the same question three times with teach on held the inventory at 6 and the
    # answer identical. It is closed because a WRITE permission should not be open during a
    # measurement of a READ path: if `answer()` ever learns to write, this arm's numbers
    # would move for a reason the arm cannot see. The assertion below is what makes the
    # discipline observable rather than assumed.
    o = _m.build(True)
    o.ELECTRIC_TEACH = False
    assert o._taught_says, "nothing was taught"
    o._asks_taught = sum(len(v) for v in o._taught_says.values())
    return o


def main():
    a, b = build(), build()
    a.ELECTRIC_OBJECT_ROLE = False
    b.ELECTRIC_OBJECT_ROLE = True
    na = sum(len(v) for v in a._taught_says.values())
    nb = sum(len(v) for v in b._taught_says.values())
    print(f"ELECTRIC OBJECT-ROLE A/B   {len(TELLS)} tells, {len(ASKS)} asks")
    print(f"inventory: arm A {na} facts, arm B {nb} facts  (must match)\n")
    assert na == nb, "arms must differ ONLY in the flag under test"
    # Self-pollution guard, stated as a fact rather than trusted: a question that entered
    # the inventory would both answer nothing and make the next asking of it ambiguous.
    leaked = [t for v in a._taught_says.values() for t in v.values() if "?" in t]
    assert not leaked, f"questions were taught as facts before any ask: {leaked}"
    print(f"  teach closed before asking: {na} facts, 0 questions in the inventory\n")
    rows, rec, reg, conf, pre = [], [], [], [], []
    for ask, shade, want in ASKS:
        ga, sa, xa = _m.grade(ask, want, a.answer(ask))
        gb, sb, xb = _m.grade(ask, want, b.answer(ask))
        rows.append({"ask": ask, "shade": shade, "want": want,
                     "a": ga, "a_src": sa, "a_said": xa,
                     "b": gb, "b_src": sb, "b_said": xb})
        if gb == "correct" and ga != "correct":
            rec.append(ask)
        if ga == "correct" and gb != "correct":
            reg.append(ask)
        # Two different things were being conflated here, and the conflation is what made
        # the first run abort on a success. A confabulation in BOTH arms, or in arm A only,
        # is PRE-EXISTING harm that this feature did not cause -- `what holds the door?`
        # said the bare word `latch` from the arbiter head in arm A and the right tell in
        # arm B, so counting it against the new path would invert the finding. Only a
        # confabulation that appears WHEN THE NEW PATH IS ON and was not there before is
        # this arm's to answer for.
        if gb == "CONFABULATION" and ga != "CONFABULATION":
            conf.append(ask)
        if gb == "CONFABULATION" and ga == "CONFABULATION":
            pre.append(ask)
        print(f"  {shade:24} {ask!r:44} A={ga:13} B={gb:13}"
              + ("  <== RECOVERED" if ask in rec else "")
              + ("  <== REGRESSION" if ask in reg else ""))
        for tag, g, s, x in (("A", ga, sa, xa), ("B", gb, sb, xb)):
            if g in ("other", "CONFABULATION"):
                print(f"  {'':24} {tag}: {g} src={s!r} said={x!r}")
    import collections
    ta = collections.Counter(r["a"] for r in rows)
    tb = collections.Counter(r["b"] for r in rows)
    print("\n--- tally ---")
    print("  arm A (reverse only) :", dict(ta))
    print("  arm B (+object-role) :", dict(tb))
    print(f"\n  RECOVERED  {len(rec)}/{len(ASKS)}: {rec}")
    print(f"  REGRESSIONS {len(reg)}: {reg}")
    print(f"  CONFABULATIONS CAUSED BY THIS FEATURE {len(conf)}: {conf}")
    print(f"  CONFABULATIONS ALREADY PRESENT WITH THE FLAG OFF {len(pre)}: {pre}")
    print(f"  REFUSALS   A={ta['refusal']} B={tb['refusal']} (must match)")
    print(f"  SILENCE    A={ta['miss']} B={tb['miss']}")
    assert ta["refusal"] == tb["refusal"], "the new path must not gain a voice"
    # The abort condition this arm was pre-registered with, now stated against the right
    # baseline: the new path may not speak a wrong fact that was not already being spoken.
    assert not conf, f"object-role path CAUSED a confabulation: {conf}"
    import json
    open("docs/evidence/electric_object_ab.json", "w", encoding="utf-8").write(
        json.dumps(rows, indent=1))
    print("\nwrote docs/evidence/electric_object_ab.json")


if __name__ == "__main__":
    main()
