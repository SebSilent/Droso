# E16a result — ABORTED at D2. The structural guard works; the fillers are wrong

**Verdict: `ABORT D2`. Zero brain builds, no organ change, no gene written.**

`docs/evidence/e16a_relation_index.py` → `e16a_result.json`. Reads `tools/scripts_heldout.json`
only.

---

## The seven tests

| # | test | result |
|---|---|---|
| 1 | frame extraction total over the tells | **PASS** — 15/15, zero unextractable |
| 2 | subject binding (scarf query returns no coat relation) | **PASS** |
| 3 | composition bounded to two relations sharing one entity | **PASS** |
| 4 | morphology normalised at write time | **FAIL** |
| 5 | refusal is the default | **PASS** |
| 6 | no hand-written word list (C5 carried forward) | **PASS** |
| 7 | additivity, no organ state touched | **PASS** |

**Test 4 failed, and the failure is the most useful single result here.** A conservative
suffix-based normaliser maps `bites → bit`, not `bite` — it strips `es` from a word whose stem
ends in `e`. Write-time morphology cannot be derived from a suffix rule. The design's claim that
normalising "once, at write time, against the frame" avoids E10's corpus-skew problem is **half
right**: it avoids the skew, but it substitutes a different error, because English inflection is
not regular enough for a suffix rule and not irregular enough to enumerate. `bitten → bitten`
(correctly reported as a Class A gap) and `bites → bit` (silently wrong) are the same problem
from two sides.

## D1 — the guard holds, structurally. This is the positive result.

```
where did i say the scarf is?    refused
  why: subject 'scarf' is indexed but has NO locative relation -- only a property; refusing
```

**This is exactly what E15 could not do.** E15 licensed this ask from `the coat is on the hook`
— a locative row about a different subject. A subject-keyed relation index cannot: the coat's
locative relation is keyed on `coat`, and the scarf has only a property. The refusal is for the
right reason and is stable under reweighting, floor changes and admitting more candidates.

The architecture review's central claim — that write-time structure supplies the **subject
binding** that E15 and E11a both lacked — is **confirmed**. Test 2 pins it as a unit test.

## D2 — three licences with wrong fillers. ABORT.

| ask | filler | want | forbid |
|---|---|---|---|
| `what turns twice?` | `copper bell` | `bell` | **`copper`** |
| `how many eggs broke?` | `four` | `two` | **`four`** |
| `how many eggs are left in the basket?` | `four` | `two` | **`four`, `six`** |

Two distinct defects, neither fixable by tightening a threshold:

1. **Multi-word subjects.** The extractor took `copper bell` as the subject because the frame is
   `the A V the B` and `A` was two tokens. The expected answer is `bell`, and `copper` is
   explicitly **forbidden**. The index has no head/modifier distinction — the same gap E11a's
   `head` field was added for, reappearing one layer down.
2. **Quantity change over time.** The scripts tell `there are four eggs in the basket` and later
   that two broke. A relation index holding one `(eggs, count, four)` row answers `four` to
   `how many eggs are left`, which is **wrong and forbidden**. The index has no temporal
   semantics: it does not know that a later tell *updates* rather than *adds*. `how many eggs
   broke?` wants `two`, a value that appears in a different tell entirely.

Defect 2 is the deeper one. It is not a morphology or parsing problem — it is that **a static
relation index cannot represent a quantity that changes**, and the battery's quantity asks are
precisely about change. This is the `quantity-change` script class, which the *baseline* passes
4/4 by a different route, so the index would be **regressing** asks the organ already gets right.

## D3 — only 2 of the 9 recall-gate asks are in this file

`scripts_heldout.json` holds 6 scripts and 24 asks; the 9 recall-gate asks span the frozen and
probe batteries, so only 2 were evaluable here. Both refused:

- `what did i tell you about before the kettle?` — the shape parser yields verb `kettle`, a
  misparse; no relation matches.
- `how many times does the bell turn?` — a frequency question; the index has no `count` relation
  for `bell` because the tell is `the copper bell turns twice`, extracted as transitive with
  object `twice`, not as a quantity.

**D3 fires**, but on a probe-coverage limitation rather than a measured zero. The quantity share
among the evaluable gate asks is 50%, consistent with the review's pre-registered fork: these
asks need a **counting** primitive, not a relational one.

## D4, D5, D6 — clear

- **D4**: the extractor uses only determiners, copulas, place prepositions and numerals — closed
  grammatical classes, no content vocabulary, no ask-fitted rule.
- **D5**: zero unextractable tells across all 15.
- **D6**: the composition join is hard-bounded to exactly two transitive relations sharing one
  entity; it was never relaxed.

## Disposition — no E16b

**D2 fires, so no flag-gated implementation is proposed.** Per the pre-registered rule, the probe
stops and records the negative.

But E16a is not a null result, and the split matters:

- **The representation is right.** Subject-keyed relations produce the structural guard refusal
  that six prior mechanisms could not (D1 clear, test 2 passing). Subject binding *is* the axis
  E15 and E11a lacked, and write-time indexing *does* supply it.
- **The extractor is wrong in two specific, named ways.** Head/modifier structure (defect 1) and
  temporal update semantics for quantities (defect 2). Neither is a tuning problem; both are
  missing representational commitments.
- **Write-time morphology is not derivable from a suffix rule** (test 4). Class A needs a lexical
  resource, which is out of scope and which E10's lesson makes risky.

**The honest conclusion:** a relation index is the right *shape* of primitive and the wrong
*first* primitive. Defect 2 says the quantity asks — half the recall-gate class — need a counting
mechanism with update semantics, and the review's pre-registered fork resolves that way. Defect 1
says any relational index needs head/modifier structure before it can name an answer correctly.

The next safe step is therefore **narrower than E16b**: a counting primitive with temporal update
semantics, evaluated on the quantity-change asks the organ already passes, to establish that it
does not regress them — before any relational index is built on top.

Cost: **zero brain builds**, seconds of runtime. No core changes, no multi-brain work, no broad
refactors.
