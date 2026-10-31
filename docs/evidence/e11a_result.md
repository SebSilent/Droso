# E11a result — session-provenanced term support does not separate the classes

**Verdict: A1 PASS, A2 FAIL, item 6 FAIL. The design is killed. E11b was not run, and no
organ change was made.**

Zero brain builds. Read-only. `docs/evidence/e11a_support_probe.py` →
`e11a_support_probe.json`.

The pre-registration in `comprehension_signal_design.md` §8 said: *"If E11a falsifies the
first clause, the design is wrong and nothing is built."* It did. **The second clause held
exactly as written**, and it is the substantive result.

---

## A loader bug invalidated the first run — and the first run's failure was not evidence

The first execution reported `A2 FAIL / item6 FAIL` too, but for a reason that made the
numbers meaningless: `tools/scripts_heldout.json` names scripts `count-frequency` while the
journal records `sel-count-frequency`. Every lookup missed, all 42 asks **silently fell back
to live-only rows**, and support was measured against droso's 466 prior rows instead of the
taught facts. The overlaps gave it away — `['is','the']`, `['which']`, `['in']` — function
words, no content.

Fixed by normalising the `sel-` prefix and, more importantly, by making the fallback **loud**:
the script now aborts if any ask's script is unresolved or if no tells precede an ask, rather
than substituting a different row set. After the fix, 102 tells resolve and the overlaps are
real content (`bell/copper/turns/twice`, `coat/is/the/wet`, `basket/eggs`, `frost/bites`).

This is the same class of bug as E10's `_CStub`, inverted: there a stub silently failed to
override the method under test so assertions passed for the wrong reason; here a lookup
silently missed so a refutation would have been recorded for the wrong reason. **A negative
result from a probe that did not measure the thing is not a negative result.** Both were
caught by checking that the mechanism actually engaged before trusting the verdict.

A second correction to the design doc: it claimed the session rows were already on disk in
the live binder. They are not — each ask is built fresh in scratch and the tells are replayed
into that scratch session, so the live binder's `you` census is 0 of 60,000. The tells had to
be synthesised from the script file. Still zero builds, but the doc's premise was wrong.

---

## Results

**A1 ask-dependence — PASS.** Range 0.1000–0.7500 across 42 asks, 21 distinct values.
Support genuinely varies with the question, which is the property `max(resonance)` lacks
(E9 measured the same attractors winning unrelated asks). Constraint 1 is satisfied.

**A2 separation — FAIL.** `min(mouth) = 0.2222`, `max(recall) = 0.5000`, margin **−0.2778**.
The distributions overlap; they do not separate.

| stage | n | min | max | mean |
|---|---|---|---|---|
| pass | 23 | 0.1000 | 0.7500 | 0.3639 |
| shape_arbiter | 2 | 0.4286 | 0.5000 | 0.4643 |
| **mouth** | 4 | 0.2222 | 0.6250 | **0.4229** |
| gating | 3 | 0.3333 | 0.4000 | 0.3694 |
| **recall** | 10 | 0.1667 | 0.5000 | **0.3355** |

Mouth *mean* is higher than recall mean, so the signal is not pure noise — but a mean
difference cannot be thresholded, and `understands` needs a threshold.

**Item 6 — FAIL.** Thresholds admitting all 4 mouth asks and no recall-gate failure: **0**.

---

## Why this is the pre-registered second clause, confirmed

The prediction was:

> no single floor separates `mouth` from the recall-gate failures without admitting them,
> **because both classes are questions the session taught material for** — the difference
> between them is coverage, not comprehension.

The overlap sets are the proof. The recall-gate asks are not questions he lacks material
for:

| support | ask | overlap with a taught row |
|---|---|---|
| 0.4444 | `how often did i say the coat is wet?` | `coat, is, the, wet` |
| 0.4444 | `what number of eggs is left in the basket?` | `basket, eggs, in, the` |
| 0.3750 | `what is held by the thing the frost bites?` | `bites, frost, the` |
| 0.3333 | `how often does the bell turn?` | `bell, the` |

He **was told** the coat is wet, the eggs, the frost biting, the bell. Provenanced support
finds it. These asks fail at the coverage floor anyway. So support is high on both sides of
the mouth/recall boundary because the boundary was never about having the material.

The falsified first clause is falsified **in the informative direction**: I predicted support
would rank mouth above recall because provenance is the axis resonance lacks. It does on
average — and that average is useless, because the recall-gate asks have provenance too.

Secondary checks: no ask's best row overlaps a known corpus attractor (`numbered`/`sold`),
confirming provenance does defeat frequency-domination (constraint 2 satisfied). The `the`
bias measured **+0.0531** (0.3755 with vs 0.3224 without) — a bias, as predicted, and small
relative to the 0.65 range, so it is not what killed A2.

---

## Disposition

**The comprehension-signal line is closed.** Three independent accounts of the `mouth` class
have now been tested and refuted:

1. resonance ranking — E9 (session scope), E10 (content scope): both refuted.
2. comprehension signalling — E11a: the signal is ask-dependent and frequency-independent as
   designed, and **still cannot separate the classes**, because the recall-gate asks are
   equally well-supported.
3. what remains is the coverage floor, whose exact thresholds are already measured
   (`kettle` 0.555, `scarf` 0.570, floor 0.6, **window empty**) and already known to be
   unmovable: g2-3 at 0.566857 lost the guarded scarf invariant at `shape_arbiter`, gen 6 at
   0.587206 was `no_gain`.

E11a cost **one binder read and no builds**, against E10's 88 builds and ~38 min. It killed a
design that would otherwise have needed a gene, nine unit tests and an 84-build battery to
refute — and the refutation would have been ambiguous, because a failed E11b could always be
blamed on the threshold. Making the pre-flight *be* the experiment is what makes the
negative clean.

No gene was written. `COMPREHENSION_SESSION_SUPPORT` and `COMPREHENSION_SUPPORT_FLOOR` do
not exist in the organ. The four refuted genes from E5/E7/E9/E10 remain default-off and
inert. Per the standing constraints: no multi-brain work, no broad refactor.

**Not attempted, and now the honest open question.** Every signal tried so far is a property
of *what he stores* — resonance over the vocabulary, provenance over the binder rows. All
three negatives point the same way: the `mouth`/`recall` boundary is not a property of his
stores at all, but of the **answer-coverage floor**, which is a property of the answer he
forms. Nothing in this line can move it, and lowering it is measured to break the guarded
scarf invariant. Any further work on this class has to address the floor or the answer
formation above it, not the comprehension test below it.
