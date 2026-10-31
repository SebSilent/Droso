# E23 — excluding closed-class question syntax from the coverage denominator

**Status: PRE-REGISTERED, THEN REFUTED BY ITS OWN READ-ONLY PRE-TEST. NOT IMPLEMENTED.**

**Pre-test:** `docs/evidence/e23_pretest.py`, data `e23_pretest.json`. Read-only over the
generation-19 journal and the live binder dump — no brain build, no organ change, no score, no
genome.

**Headline: all three exclusion variants break the guarded scarf invariant, and the more syntax they
remove the harder it breaks (0.5797 → 0.6676 → 1.0 → 1.0 against a 0.6 floor). Variants that gain a
failing ask: 3. Variants that break no passing ask: 0. VIABLE: none. E23 is not implemented, and no
organ change, flag or test was added.**

---

## 1. Hypothesis

E19, E20, E21a and E22a closed every lever operating on retrieval or reinforcement of an existing
taught row. All four point at the same place: the gate retrieves the correct row — on 4 of 9 gate
asks it ranks it **first** — and refuses anyway, because `must` demands question syntax and passive
morphology a declarative tell can never contain.

> **H1.** Excluding closed-class question syntax from the coverage denominator raises coverage on
> content-bearing asks without changing the guarded invariants.

This is the one lever the evidence still supported. It is also a close relative of E12a's
`COVERAGE_ANSWERABLE_TERMS`, which was refuted on a single ask. E12a checked one ask; this
pre-registration checks the whole battery under three variants before any code is written.

## 2. Variants

Exclusion sets are **closed grammatical classes only** — function words, auxiliaries,
interrogatives, question verbs, question modifiers. No content vocabulary, per E16a's D4 and E10's
Finding 1.

| variant | removes | example: `where did i say the scarf is?` |
|---|---|---|
| `orig` | nothing | `[did, is, say, scarf]` |
| `v_synt` | function words + interrogatives | `[say, scarf]` |
| `v_frame` | + question verbs (`say/tell/mention/name/repeat`) | `[scarf]` |
| `v_all` | + question modifiers (`often/many/times/number/before/…`) | `[scarf]` |

Coverage is recomputed with the gate's own formula (`organs/neural_language.py:3464-3473`),
IDF-weighted by the live binder's document frequencies, against the gate's own top-ranked candidate.

## 3. Guard analysis — measured, not argued

The guarded scarf invariant is the **only passing ask in the battery that reaches the recall gate**.
Its recorded coverage is 0.5797, i.e. **0.0203 below the floor** — it passes *by refusing*.

| variant | scarf coverage | crosses 0.6? | guard |
|---|---|---|---|
| `orig` | 0.579691 | no | **intact** |
| `v_synt` | 0.667569 | **yes** | **BROKEN** |
| `v_frame` | **1.0** | **yes** | **BROKEN** |
| `v_all` | **1.0** | **yes** | **BROKEN** |

**Every variant breaks it.** The reason is structural and cannot be engineered around:

The scarf cue is `[did, is, say, scarf]`. Three of its four terms are closed-class. Its top row is
`the scarf is wet`, which contains `scarf` and `is`. Remove the function words and the denominator
collapses to `[say, scarf]`, of which the row matches `scarf` → 0.6676. Remove question verbs too and
the denominator collapses to `[scarf]` alone, which the row trivially contains → **1.0**.

**The guard depends on the denominator being "wrong" in exactly the way the failing asks need it
fixed.** The scarf ask is *supposed* to refuse — the user never said where the scarf is, only that
it is wet — and it refuses only because `did`, `is` and `say` drag its coverage below the floor.
Those terms are precisely the closed-class question syntax H1 proposes to remove. **The repair and
the guard are in direct arithmetic opposition, not in tension that a narrower exclusion set could
resolve.**

## 4. Gain analysis — the variants do work, which is what makes this a real trade-off

| variant | failing asks newly crossing 0.6 |
|---|---|
| `v_synt` | **2** — `how often does the bell turn?` 0.545→0.700; `what is held by the thing the frost bites?` 0.534→0.640 |
| `v_frame` | **3** — adds `how often did i say the coat is wet?` 0.457→0.718 |
| `v_all` | **5** — adds `what came before the kettle…` 0.475→0.679 and `what number of eggs is left…` 0.549→1.0 |

So the mechanism is real: excluding question syntax recovers up to 5 of 9 gate failures. It is not a
null result. **It is a repair that works and cannot be deployed**, because it buys those 5 by
converting a correct refusal into an incorrect answer.

Exclusion can also *hurt*. `what did i tell you about before the kettle?` falls 0.547 → 0.415 →
0.238 → **0.0** as more classes are removed, because its content words (`tell`, `about`, `before`,
`kettle`) are themselves question-framing terms the row does not contain. Removing them shrinks the
numerator faster than the denominator. A uniform "raise every score" model of the lever is wrong.

## 5. Verdict

```
variants that break no passing ask : none
variants that gain a failing ask   : ['v_synt', 'v_frame', 'v_all']
VIABLE (gain and guard-safe)       : none
```

**E23 is refuted by its pre-test and is not implemented.** No flag, no organ change, no test was
added. This is the E8 pattern: a pre-registered abort condition met before implementation, so the
mechanism is never built.

## 6. Abort conditions (pre-registered, and met)

| # | condition | status |
|---|---|---|
| **A1** | Any guarded invariant's coverage crosses the floor under the variant. | **MET** — all 3 variants, scarf 0.5797→0.6676/1.0/1.0. |
| **A2** | Any passing ask that currently refuses begins answering. | **MET** — the scarf ask is exactly that case. |
| **A3** | The exclusion set contains content vocabulary rather than closed grammatical classes. | not met — sets are function words, interrogatives, question verbs, modifiers only. |
| **A4** | A variant's behaviour is distinguishable only by a hand-written list of the failing asks. | not met — the sets are generic. |
| **A5** | Frozen passes fall below 19/24 or guarded below 4/4 in a battery run. | **unreachable** — A1/A2 abort before any run. |

A1 and A2 are sufficient. A3–A5 are recorded to show the refutation is not an artifact of a badly
chosen exclusion set: the sets are generic and grammatical, and the variants *do* gain asks.

## 7. Tests that would have been written

Recorded for completeness; **none was added**, because the pre-test aborts before implementation.

1. `test_e23_flag_default_off` — with the flag unset, coverage equals `orig` for every gate ask in
   the journal (byte-identical scores).
2. `test_e23_scarf_guard_holds` — the scarf ask's recomputed coverage stays **below** 0.6 and it
   still refuses. *This test fails for all three variants; it is the abort.*
3. `test_e23_exclusion_is_closed_class_only` — every removed term is in a closed grammatical class;
   no content noun/verb/adjective is removable (guards A3).
4. `test_e23_gain_is_measured` — the number of failing asks crossing the floor matches the
   pre-registered count for the chosen variant (guards against silent scope creep).
5. `test_e23_frozen_and_guarded_unchanged` — 19/24 frozen, 4/4 guarded (guards A5).

Test 2 is the one that decides it, and the pre-test has already answered it: **it cannot pass.**

## 8. Could a narrower variant work?

Considered and rejected on the measured data:

- **Exclude only auxiliaries (`did/is/are/was`), keep `say`.** That is `v_synt` minus interrogatives.
  The scarf cue still loses `did` and `is`, leaving `[say, scarf]` → 0.6676. Still broken.
- **Exclude only terms absent from every candidate row.** Adaptive, and it would spare the scarf ask
  only by accident of its candidate set — and it is ask-fitted, tripping A4/D4.
- **Raise the floor alongside the exclusion** so the scarf ask refuses again. This changes a tuned
  gene to compensate for a code change, and E6 already measured that the window between the best
  failing coverage (0.555) and the scarf's passing-by-refusal coverage (0.570) is **empty**. There is
  no floor value that admits the repaired asks and still excludes the scarf.
- **Apply the exclusion only to non-refusal candidates.** Circular: whether the gate refuses is what
  the coverage decides.

The obstruction is not the choice of exclusion set. It is that **the only passing gate ask in the
battery passes by refusing, and it refuses because of the syntax H1 removes.**

## 9. Where this leaves the programme

Six levers are now closed, five by measurement and one by pre-registered abort:

| lever | probe | verdict |
|---|---|---|
| eviction | E19 | falsified — 0/19 failures |
| cue omission | E20 | falsified — gate ranks the row first on 4/9, still refuses |
| cue dilution | E21a | falsified — de-framing recovers 0 of 4 |
| score / admission | E12a, E14a | closed — ceiling 0.5488 < 0.6 |
| reinforcement | E22a | falsified — count=3 gate ask below the count=1 mean |
| **denominator** | **E23** | **refuted pre-implementation — breaks the guard under every variant** |

E23 is the strongest result of the six, because it is the only lever that **works** — it recovers up
to 5 of 9 gate failures — and it is still undeployable. That is a sharper statement than "no repair
was found": **a repair was found, measured, and shown to be inseparable from breaking a correct
refusal.**

The implication is that the battery's single guarded refusal and its nine gate failures are governed
by one quantity, and no monotone change to that quantity separates them. Progress requires either a
mechanism that is not a coverage threshold — a way to represent *absence* so the scarf ask can
refuse for a reason other than a low ratio, which is what E8's abort condition originally demanded —
or a battery whose guarded invariants do not depend on the denominator being wrong.

Neither is pre-registered here. E23 was a pre-registration and a read-only pre-test, and the
pre-test says do not build it.

## 10. Limitations

- **10 gate asks.** Only asks where the recall gate ran have a recorded `required` cue and `nearest`
  candidate; the other 32 pass or fail elsewhere and cannot be scored by this pre-test.
- **One guarded gate ask.** The entire guard analysis rests on the scarf invariant. It is the only
  passing ask that reaches the gate, so "breaks no passing ask" and "breaks the scarf" are the same
  statement on this battery.
- **Recomputed, not replayed.** Coverage is recomputed from journaled cues and candidates with the
  gate's formula and live-binder IDF. E21a showed a probe's retrieval can diverge from the gate's;
  here the *candidate* is taken from the gate's own `nearest[0]`, so the divergence risk is confined
  to the IDF weights, which come from the live binder rather than the session binder.
- **`v_all`'s 5 gains are an upper bound.** Crossing the floor is necessary but not sufficient to
  pass — the ask must then survive the reply gate, shape arbiter and mouth. E23 was aborted before
  that could be measured.

## 11. Files

| file | change |
|---|---|
| `docs/evidence/e23_pretest.py`, `.json`, `e23_coverage_denominator_prereg.md` | new read-only pre-test, data, this file. |

**No change to `organs/`, `connectome/`, `tools/`, `tests/`, genomes or any score.** No flag was
added, because the mechanism it would gate is refuted.
