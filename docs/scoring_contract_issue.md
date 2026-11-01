# Open issue: the guarded grader scores a spoken admission of ignorance as a FAILURE

**Recorded, not acted on. The grader contract has NOT been changed.** Nothing in this
file is a fix in progress; it is the record the user asked to keep separate from the
capability work.

## The observation

Generation 24 (`--absence-inventory --coverage-exclude frame --electric`), ask
`where did i say the scarf is?`, script `conjunction-and-absence`:

| arm | what it said | graded |
|---|---|---|
| control (gen 21) | `''` — silence | **PASS** |
| treatment (gen 24) | `i don't know, scarf was told but no place was ever told for scarf` | **FAIL** |

The treatment utterance is **true, warranted and specific**: it names the subject, names
the relation that was never supplied, and asserts nothing about the world. The control
said nothing at all. The treatment is the better behaviour and the lower score.

## Why the score is not wrong

The grader encodes *silence-as-success* for this ask, and that was the **correct contract
for E24 phase 1**, whose entire purpose was to establish that the organism could detect a
missing relation and be prevented from asserting one. In that frame, saying nothing is
exactly the competence under test, and any utterance is a leak.

The contract has not been restated for a learner that is expected to **answer in words**.
So the two are not in conflict on the facts — they are in conflict about what success
means, and the definition predates the capability.

## Why it was not changed in this round

- `pass` on the frozen tier is the load-bearing quantity for **24 generations** of
  selection records. Redefining it silently invalidates every comparison of the form
  "gen N vs gen 21" that `docs/evidence/` contains, including E25 and E26.
- The user's instruction for this round was explicit: *do not change the guarded grader
  contract yet.*
- ELECTRIC is off for battery runs, so nothing currently in the selection record depends
  on the resolution.

## What changing it would actually require

Not a one-line patch. A grader edit here would have to distinguish, for a graded ask:

1. **correct silence** — nothing said, no answer available (current PASS),
2. **warranted admission** — spoke, asserted no fact, and named the missing relation,
3. **confabulation** — spoke and asserted a fact that does not answer the ask.

Category 3 must stay a FAIL and is the whole reason the instrument exists. Today 1 and 2
collapse together into "spoke", and 2 is punished. The distinction is expressible —
ELECTRIC's own return value (`neural_language.py:3653-3662`) already distinguishes the
three cases without any new machinery — it emits `source: "electric_absence"`,
`answered: False`, `licensed_refusal: True` and a `reason` string, against the direct
answer path's `source: "electric_taught"`, `answered: True`. A grader could key on that
tag instead of on whether the utterance string is empty. **Verified by reading the code,
not inferred.** What it still changes is the meaning of the frozen tier's denominator.

## Options for the user

| option | consequence |
|---|---|
| **A. Leave it** | ELECTRIC remains off for battery runs; the capability is demonstrated by `tools/electric_generalise.py` (20/20, 0 confabulations) and never enters the selection record. Zero risk to 24 generations of comparability. |
| **B. Add a third outcome alongside pass/fail** | Keeps every existing PASS/FAIL byte-identical and records warranted admission as its own column. Non-destructive, but the frozen tier's headline number still does not credit it. |
| **C. Redefine the scarf-class asks** | Credits the admission as a PASS and keeps confabulation a FAIL. Most accurate, and it breaks comparability with all pre-24 generation records unless they are re-scored. |

**Recommendation: B.** It records the behaviour the organism now has without rewriting
what "pass" has meant, and it leaves C as a deliberate, separate, re-scoring decision to
be taken once ELECTRIC is actually candidate for battery runs.

## Cross-references

- `docs/electric_result.md` §6b — the generation-24 run that surfaced this.
- `docs/evidence/electric_broken.py` — the diff that produced the two-line table above.
- `organs/neural_language.py` — the spoken-ignorance path (gated on `ELECTRIC_ANSWER`)
  that emits the utterance; it returns `answered: False`, so the record already carries
  the signal a grader would need.
