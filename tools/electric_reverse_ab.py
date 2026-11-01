"""ELECTRIC reverse-role A/B: how much does ELECTRIC_REVERSE actually recover?

Two arms, one variable.  Both build a bare organ, teach the SAME tells in the same
order, and ask the SAME questions; arm A runs with ELECTRIC_REVERSE off, arm B with it
on.  Separate instances, because answer() wires as it reads (live(learn=True) inside),
and a question asked in one arm must not change the other.

The ask set is not a sample of English, it is a set of SHADES chosen to separate three
outcomes that a single "reverse-role" label would blur:

  WHO-STRANDED   "who does the lantern belong to?"  -- the new bind. Stranding is what
                 proves the middle noun is the tell's own subject, i.e. the key.
  WHO-BARE       "who does the mouse chase?"        -- must STAY a miss. The frame under
                 `mouse` is "the mouse chases the cat": answering it would be the wrong
                 fact about the right noun. This is the safety arm, not a failure arm.
  C3 H1-REVERSE  "what bites the latch?"            -- the shape C3 actually counted
                 (2 of 15). It names the OBJECT of the tell and carries no stranded
                 preposition, so the new rule does not reach it. If this recovers, the
                 rule is looser than designed and I want to see that here.

Grading distinguishes a MISS (silent / fell through) from a CONFABULATION (a DIFFERENT
taught tell spoken) -- the only outcome worse than silence -- and from a REFUSAL, which
must not be invented either.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import organs.neural_language as nl                       # noqa: E402
from connectome.engine import HybridEngine               # noqa: E402
from connectome.substrate import build_core_graph        # noqa: E402
from organs.tokenizer import TokenizerOrgan              # noqa: E402

TELLS = [
    "the scarf is on the hook",
    "the lantern belongs to Mira",
    "the mouse chases the cat",
    "the frost bites the latch",
    "the latch holds the door",
    "the ledger is under the desk",
]

# (ask, shade, the tell that would be the RIGHT answer, or None if nothing should come out)
ASKS = [
    ("who does the lantern belong to?", "who-stranded", "the lantern belongs to Mira"),
    ("who does the lantern belong to", "who-stranded", "the lantern belongs to Mira"),
    ("who does the mouse chase to?", "who-stranded", "the mouse chases the cat"),
    ("who does the mouse chase?", "who-bare", None),
    ("who does the ledger belong to?", "no-such-fact", None),
    ("who does the lantern report to?", "wrong-verb", None),
    ("who does the scarf belong to?", "wrong-frame", None),
    ("what bites the latch?", "c3-h1-reverse", None),
    ("what does the frost bite?", "forward-agent-inflected", "the frost bites the latch"),
    ("what does the scarf sit on?", "no-such-fact", None),
    ("where is the scarf?", "forward-place", "the scarf is on the hook"),
    ("where is the ledger?", "forward-place", "the ledger is under the desk"),
    ("what is the scarf like?", "absence-refusal", None),
    ("who does the lantern belong to and where is the scarf?", "ambiguous", None),
]


def build(reverse):
    o = nl.NeuralLanguage(HybridEngine(graph=build_core_graph()), TokenizerOrgan(),
                          state_path=None)
    o.persist = False
    o.ELECTRIC_TEACH = True
    o.ELECTRIC_ANSWER = True
    o.ABSENCE_INVENTORY = True
    o.ELECTRIC_REVERSE = bool(reverse)
    for t in TELLS:
        o.hear(t, speaker="you")
    return o


def grade(ask, want, out):
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
    # Anything spoken that is NOT the wanted tell is scored against the tell set: a
    # reply that reproduces some OTHER taught tell, or even one fragment of one, is
    # the failure mode this arm exists to catch. Bucketing it as "other" would let a
    # wrong claim slip past the headline number.
    for t in TELLS:
        if t == (want or ""):
            continue
        if said == t or (len(said.split()) <= 4 and said and said in t):
            return "CONFABULATION", src, said
    return "other", src, said


def main():
    a, b = build(False), build(True)
    print(f"ELECTRIC REVERSE A/B   {len(TELLS)} tells, {len(ASKS)} asks")
    print(f"inventory: arm A {sum(len(v) for v in a._taught_says.values())} facts, "
          f"arm B {sum(len(v) for v in b._taught_says.values())} facts  (must match)\n")
    rows = []
    for ask, shade, want in ASKS:
        ga, sa, xa = grade(ask, want, a.answer(ask))
        gb, sb, xb = grade(ask, want, b.answer(ask))
        rows.append({"ask": ask, "shade": shade, "want": want, "off": ga, "off_src": sa,
                     "off_said": xa, "on": gb, "on_src": sb, "on_said": xb})
        flag = "" if ga == gb else ("  <== RECOVERED" if gb == "correct"
                                    else "  <== REGRESSION" if ga == "correct"
                                    else "  <== CHANGED")
        print(f"  {shade:24} {ask!r:52} off={ga:13} on={gb:13}{flag}")
        # Show what was actually spoken on any row that is neither silence nor the
        # right fact. A verdict without the utterance is not checkable.
        for tag, g, s, x in (("off", ga, sa, xa), ("on", gb, sb, xb)):
            if g in ("other", "CONFABULATION"):
                print(f"  {'':24} {tag}: {g} src={s!r} said={x!r}")

    def tally(key):
        d = {}
        for r in rows:
            d[r[key]] = d.get(r[key], 0) + 1
        return d
    print("\n--- tally ---")
    print(f"  reverse OFF: {tally('off')}")
    print(f"  reverse ON : {tally('on')}")
    rec = [r for r in rows if r["off"] != "correct" and r["on"] == "correct"]
    reg = [r for r in rows if r["off"] == "correct" and r["on"] != "correct"]
    confoff = [r for r in rows if r["off"] == "CONFABULATION"]
    confon = [r for r in rows if r["on"] == "CONFABULATION"]
    print(f"\n  RECOVERED  {len(rec)}/{len(rows)}: {[r['ask'] for r in rec]}")
    print(f"  REGRESSIONS {len(reg)}: {[r['ask'] for r in reg]}")
    print(f"  CONFABULATIONS off={len(confoff)} on={len(confon)} "
          f"{[r['ask'] for r in confon]}")

    # attribution: which mechanism bought each recovery
    print("\n--- attribution (bind vs stem) ---")
    for r in rec:
        needs_who = nl._electric_bind(r["ask"], b._taught_says, broad_agent=True,
                                      who_agent=False) is None
        bound = nl._electric_bind(r["ask"], b._taught_says, broad_agent=True,
                                  who_agent=True)
        exact = ""
        if bound:
            rel, subj = bound
            tell = b._taught_says.get(subj, {}).get(rel)
            import re
            aw = set(re.sub(r"[^a-z ]", " ", r["ask"].lower()).split())
            tw = {w for w in re.sub(r"[^a-z ]", " ", str(tell).lower()).split()
                  if w and w not in nl._ABSENCE_STOP}
            exact = "stem-only" if not ((tw - {subj}) & {w for w in aw
                                                       if w not in nl._ABSENCE_STOP}) \
                  else "exact-match-would-have-passed"
        print(f"  {r['ask']!r:52} who-branch needed={needs_who}  guard={exact}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
