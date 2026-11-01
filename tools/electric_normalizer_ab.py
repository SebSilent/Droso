"""ELECTRIC ask-normalizer A/B: does reading an ask's FORM recover facts, and what does it cost?

Arm A: reverse=True, object_role=True, normalize=False   (the current best behaviour, C5)
Arm B: reverse=True, object_role=True, normalize=True    (one variable changed)

The tells are the C4d/C5 six PLUS two the new forms need to have an answer at all:
`the boy opens the door` (a passive ask needs an agent to recover) and
`Mira gives the lantern` (an irregular participle with a different subject). Both arms get
all eight, asserted identical before any ask is scored -- an arm that differs in its
inventory would be measuring the inventory.

The whole object-role table is replayed here, not just the new rows: a normalizer that
recovers three asks and quietly breaks `what bites the latch?` has to be caught by this
arm, not by the suite three files away.

SECOND PASS, isolated: every new ask is also run on a FRESH organ, one ask per organ.
`answer()` learns the asks it is asked, so in the sequence pass an early row changes what
memory the later rows fall through to -- real behaviour of a running house, but not
attributable to this flag. Where the two passes disagree, the isolated number is the one
this file claims.

The guarded grader contract in the battery was not touched; tools/electric_reverse_ab.py
and tools/electric_object_ab.py are read, not written.
"""
import collections
import importlib.util as _u
import json
import re
import sys

sys.path.insert(0, ".")

_s = _u.spec_from_file_location("rev_nm", "tools/electric_reverse_ab.py")
_m = _u.module_from_spec(_s)
_s.loader.exec_module(_m)
_o = _u.spec_from_file_location("obj_nm", "tools/electric_object_ab.py")
_ob = _u.module_from_spec(_o)
_o.loader.exec_module(_ob)

EXTRA_TELLS = ["the boy opens the door", "Mira gives the lantern"]
TELLS = list(_m.TELLS) + EXTRA_TELLS

NEW_ASKS = [
    ("who is the lantern with?", "copula-with", "the lantern belongs to Mira"),
    ("who is the lantern with", "copula-no-mark", "the lantern belongs to Mira"),
    ("what was the door opened by?", "passive-was", "the boy opens the door"),
    ("what is the door opened by?", "passive-is", "the boy opens the door"),
    ("what is the latch bitten by?", "passive-irregular", "the frost bites the latch"),
    ("who was the lantern given by?", "passive-other-subject", "Mira gives the lantern"),
    # controls: each is a way the normalizer could be wrong, and stays silent
    ("what was the latch broken by?", "ctl-untaught-verb", None),
    ("what was the ledger hidden by?", "ctl-untaught-verb-2", None),
    ("who is the mouse with?", "ctl-tell-strands-nothing", None),
    ("who is the scarf with?", "ctl-place-frame-only", None),
    ("who is the door with?", "ctl-noun-is-not-a-subject", None),
    ("what is the scarf like?", "ctl-measured-refusal", None),
    ("who does the lantern report to?", "ctl-wrong-verb", None),
]
ASKS = list(_ob.ASKS) + NEW_ASKS


def build(normalize):
    o = _m.build(True)
    o.ELECTRIC_OBJECT_ROLE = True
    o.ELECTRIC_ASK_NORMALIZE = bool(normalize)
    for t in EXTRA_TELLS:
        o.hear(t, speaker="you")
    # A write permission stays shut during a measurement of a read path (the C5 discipline).
    o.ELECTRIC_TEACH = False
    assert o._taught_says, "nothing was taught"
    return o


def grade(ask, want, out):
    """The C4d grader, over THIS arm's eight tells -- same buckets, same strictness:
    anything spoken that reproduces another taught tell, or a short fragment of one, is a
    confabulation, not "other"."""
    if not isinstance(out, dict):
        return "miss", "", ""
    said = str(out.get("utterance") or out.get("response") or "").strip()
    src = str(out.get("source") or "")
    if not said or not out.get("spoken"):
        return "miss", src, said
    if src == "electric_absence" or said.lower().startswith("i don't know"):
        return "refusal", src, said
    if want is not None and said == want:
        return "correct", src, said
    for t in TELLS:
        if t == (want or ""):
            continue
        if said == t or (len(said.split()) <= 4 and said and said in t):
            return "CONFABULATION", src, said
    return "other", src, said


def main():
    a, b = build(False), build(True)
    na = sum(len(v) for v in a._taught_says.values())
    nb = sum(len(v) for v in b._taught_says.values())
    print(f"ELECTRIC ASK-NORMALIZER A/B   {len(TELLS)} tells, {len(ASKS)} asks")
    print(f"  inventory: arm A {na} facts, arm B {nb} facts  (must match)")
    assert na == nb == len(TELLS), f"arms must differ ONLY in the flag under test: {na}/{nb}"
    leaked = [t for v in a._taught_says.values() for t in v.values() if "?" in t]
    assert not leaked, f"questions were taught as facts before any ask: {leaked}"
    print(f"  teach closed before asking: {na} facts, 0 questions in the inventory\n")

    rows, rec, reg, conf, pre, changed = [], [], [], [], [], []
    for ask, shade, want in ASKS:
        ga, sa, xa = grade(ask, want, a.answer(ask))
        gb, sb, xb = grade(ask, want, b.answer(ask))
        rows.append({"ask": ask, "shade": shade, "want": want,
                     "a": ga, "a_src": sa, "a_said": xa,
                     "b": gb, "b_src": sb, "b_said": xb})
        if gb == "correct" and ga != "correct":
            rec.append(ask)
        if ga == "correct" and gb != "correct":
            reg.append(ask)
        if gb == "CONFABULATION" and ga != "CONFABULATION":
            conf.append(ask)
        if gb == "CONFABULATION" and ga == "CONFABULATION":
            pre.append(ask)
        if ga != gb and ask not in rec and ask not in reg:
            changed.append(ask)
        mark = ("  <== RECOVERED" if ask in rec else "") + \
               ("  <== REGRESSION" if ask in reg else "") + \
               ("  <== NEW CONFABULATION" if ask in conf else "")
        print(f"  {shade:24} {ask!r:42} A={ga:13} B={gb:13}{mark}")
        for tag, g, s, x in (("A", ga, sa, xa), ("B", gb, sb, xb)):
            if g in ("other", "CONFABULATION"):
                print(f"  {'':24} {tag}: {g} src={s!r} said={x!r}")

    ta = collections.Counter(r["a"] for r in rows)
    tb = collections.Counter(r["b"] for r in rows)
    print("\n--- tally (sequence pass) ---")
    print("  arm A (no normalizer) :", dict(ta))
    print("  arm B (+normalizer)   :", dict(tb))
    print(f"\n  RECOVERED            {len(rec)}/{len(ASKS)}: {rec}")
    print(f"  REGRESSIONS          {len(reg)}: {reg}")
    print(f"  CONFABULATIONS CAUSED {len(conf)}: {conf}")
    print(f"  CONFABULATIONS PRE-EXISTING {len(pre)}: {pre}")
    print(f"  OTHER VERDICT CHANGES {len(changed)}: {changed}")
    print(f"  REFUSALS A={ta['refusal']} B={tb['refusal']} (must match)")
    print(f"  SILENCE  A={ta['miss']} B={tb['miss']}")
    assert ta["refusal"] == tb["refusal"], "the normalizer must not gain a voice in refusals"
    assert not reg, f"the normalizer regressed a previously-correct ask: {reg}"
    assert not conf, f"the normalizer CAUSED a confabulation: {conf}"

    print("\n--- isolated pass: one fresh organ per ask (attribution) ---")
    iso = []
    for ask, shade, want in NEW_ASKS:
        r = {}
        for norm in (False, True):
            o = build(norm)
            g, s, x = grade(ask, want, o.answer(ask))
            r[norm] = (g, s, x)
        iso.append({"ask": ask, "shade": shade, "want": want,
                    "off": r[False][0], "off_said": r[False][2],
                    "on": r[True][0], "on_said": r[True][2]})
        # Not "the recovery is sequence-dependent" -- it is not, every recovered row
        # recovers in both passes. It means the OFF verdict differs between the passes,
        # because in the sequence pass an earlier ask has already been learned and the
        # later one falls through to a remembered QUESTION. That is the admissibility
        # leak, not this flag, and this arm leaves it visible rather than hiding it.
        flag = "" if r[False][0] == r[True][0] else "   (off-verdict differs from sequence pass)"
        print(f"  {shade:24} {ask!r:42} off={r[False][0]:13} on={r[True][0]:13}{flag}")
        if r[True][0] in ("other", "CONFABULATION"):
            print(f"  {'':24} on said={r[True][2]!r} src={r[True][1]!r}")
    it = collections.Counter((i["off"], i["on"]) for i in iso)
    print(f"\n  isolated recovered: {sum(1 for i in iso if i['on'] == 'correct' and i['off'] != 'correct')}"
          f"   isolated confabulated: {sum(1 for i in iso if i['on'] == 'CONFABULATION' and i['off'] != 'CONFABULATION')}")

    json.dump({"tells": TELLS, "sequence": rows, "isolated": iso},
              open("docs/evidence/electric_normalizer_ab.json", "w", encoding="utf-8"),
              indent=1)
    print("\nwrote docs/evidence/electric_normalizer_ab.json")


if __name__ == "__main__":
    main()
