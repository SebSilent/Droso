"""E27 motivation probe: how far does `_absence_frame`'s positional subject key reach?

Read-only, no organ instance, no binder, no state, no genome. It calls the two pure
functions the ELECTRIC path is built from -- `_absence_frame` (write side) and
`_electric_answer` (read side) -- with an inventory built the same way `_absence_note`
builds `_taught_says` (subject -> relation -> first tell, verbatim, first tell wins).

The tells are the battery's OWN taught sentences, taken from the `taught_row` values
journalled in `state/selection/generation_19_asks.jsonl`, plus `the gate holds the door`.

WHAT THIS IS NOT: it is not a battery reproduction. It bypasses `answer()`, so it never
sees `_absence_licence`, the coverage gate, the shape arbiter or the mouth. Where it
disagrees with the gen-24 journal, the journal wins -- see the divergence section, which
is the first thing E27 has to resolve.
"""
import itertools
import sys

sys.path.insert(0, ".")
from organs.neural_language import _absence_frame, _electric_answer

TELLS = ["the coat is wet", "the frost bites the latch", "there are four eggs in the basket",
         "the copper bell turns twice", "the lantern is lit", "the scarf is on the hook",
         "the gate holds the door"]

# What the sentence is ABOUT, by hand. Not derived from the sentence -- deriving it is
# the thing under test.
EXPECTED_SUBJECT = {
    "the coat is wet": "coat",
    "the frost bites the latch": "frost",
    "there are four eggs in the basket": "eggs",
    "the copper bell turns twice": "bell",
    "the lantern is lit": "lantern",
    "the scarf is on the hook": "scarf",
    "the gate holds the door": "gate",
}

# The three read flags, in the order the call site passes them. `--electric` sets only
# TEACH+ANSWER; these three are separately gated and have never been on for a battery run.
FLAGS = ("reverse", "object_role", "normalize")
COMBOS = list(itertools.product([False, True], repeat=3))

print("== 1. write side: what key does each tell get stored under? ==")
says = {}
for t in TELLS:
    f = _absence_frame(t)
    if f is None:
        print(f"  NOT RECORDED                          <- {t!r}")
        continue
    rel, subj, obj = f
    says.setdefault(subj, {}).setdefault(rel, t)
    expected = EXPECTED_SUBJECT[t]
    flag = "" if subj == expected else f"   <- keyed on {subj!r}, the subject is {expected!r}"
    print(f"  subject={subj!r:<9} rel={rel:<9} obj={obj!r:<24} <- {t!r}{flag}")

print("\n== 2. read side: does an ask naming the SEMANTIC subject get answered? ==")
ASKS = ["what turns twice?", "which thing turns twice?", "how often does the bell turn?",
        "what number of eggs is left in the basket?", "what is bitten by the frost?",
        "what bites the latch?", "where did i say the scarf is?",
        "what is held by the thing the frost bites?",
        "what did i tell you about before the kettle?"]
for q in ASKS:
    hits = [_electric_answer(q, says, **dict(zip(FLAGS, c))) for c in COMBOS]
    n = sum(1 for h in hits if h)
    got = next((h for h in hits if h), None)
    print(f"  answered in {n}/8 combinations  {q!r}" + (f"  -> {got!r}" if n else ""))

print("\n== 3. same asks, shipped configuration (all three read flags OFF) ==")
off = [(q, _electric_answer(q, says)) for q in ASKS]
print(f"  {sum(1 for _, g in off if g)}/{len(off)} answered:")
for q, g in off:
    if g:
        print(f"    {q!r} -> {g!r}")

print("\n== 4. divergence from the gen-24 journal (the thing E27 must resolve) ==")
print("  the pure read side claims these, the organ did not:")
for q in ["what is held by the thing the frost bites?", "where did i say the scarf is?"]:
    for c in COMBOS:
        g = _electric_answer(q, says, **dict(zip(FLAGS, c)))
        if g:
            print(f"    {q!r} -> {g!r}   (flags {c})")
print("  gen 24 (`--electric`, read flags off) journaled instead:")
print("    'what is held by the thing the frost bites?'  stage=shape_arbiter, said=''")
print("    'where did i say the scarf is?'  spoke the ADMISSION 'i don't know, scarf was")
print("    told but no place was ever told for scarf' -- graded FAIL, silence was the contract")
print("  => the probe bypasses `_absence_licence` and the rest of `answer()`. Neither claim")
print("     above is a live defect until the same inventory runs through the real path.")
