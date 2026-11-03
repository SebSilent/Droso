# MP-E9 — decision

**Experiment:** MP-E9, the direct answer path formalised under executable bounds (B.2 step 3 was the
opening; steps 1–2 are the two treatments registered as PRE-1).
**Gate:** G1. **Status at this writing:** arms run, artifacts sealed, H1/H2/H4 hold, H3 fails and its
registered premise is falsified.
**Plan:** DROSO Master Plan v1.1, §6.2 and Table 6.

---

## 1. What was claimed, and what was measured

Every number below is a measurement from a committed artifact, not a quotation. The criterion for each
was registered in `experiments/MP-E9/registration.json` under `registered_predictions` at
`2026-11-03T07:53:05Z`, **before any treatment arm ran**, and none of those blocks has been edited
since. Where a measurement disagrees with its prediction, the disagreement is recorded beside it.

| | registered | measured | verdict |
|---|---|---|---|
| **H1** untraceable asserted rows | 0 in every arm, depth, phase | 16 → **0** under P1 | **HOLDS** |
| **H2** says rows flagged / 36 tell intact / no correct row lost | 0 / 36 / 0 | **0 / 36 / 0**; says-gap refused+echo 65 → **81**, the exact predicted value | **HOLDS** |
| **H3** toll class answered | ≥ 6 correct of 54, invented 0 | **0 of 54**, under two separate registered attempts | **FAILS** |
| **H4** invariants and guarded rows | 24/24 absence, 38/75/115 floor, battery 19/24 and 4/4 with ELECTRIC off | all four components measured, ELECTRIC verified off from run provenance | **HOLDS** |

The tripwire populations held under treatment: the 36 `arbiter tell` rows, the 24 `electric_absence`
rows, and the 6 `UNTRACEABLE_HEARD` rows that D-G0P-03 ruled non-aborting all stayed at their
pre-treatment values, row for row, in the P1 arm.

## 2. The A/B, and why the null result is a controlled one

A treatment effect is only evidence if the no-treatment arm is measured on the same comparison. That
half is instrumented, not assumed: `tools/ab_reproduction.py` keys every row by position
(arm, depth, phase, item, shape) and compares identity (ask, said, src, cls), because two artifacts
can agree on every tally while different rows hold those places.

| arm | rows differing from the pre-treatment artifact, of 3,672 |
|---|---|
| flag OFF (`ab_flag_off.json`) | **0** |
| P1 head bound | **16** — 14 outside the R13 cells, 2 inside |
| P2 global stemmer | **0** |
| F1 per-entry aliases | **0** |

The flag-OFF arm moved nothing, so P1's 16 rows are attributable to the flag and not to the run. The
registered R13 tolerance — differences confined to `learn/1/reasked` and `learn/1/restarted`, ≤ 11 rows,
the cells G0-prime measured as wall-clock dependent — was fixed in advance and was **not needed**: zero
rows moved even inside those cells.

P2 and F1 are not "insufficient". They are **indistinguishable from not being there**. That is a
stronger and more useful statement than `toll correct stayed 0`, and it is what falsifies the premise.

## 3. H3: the registered premise is falsified, and what actually blocks the class

H3 was registered on the premise that the toll class fails because the keyed store uses exact
characters — `tolls`, `tolling`, `tolled` never fold to `toll`. That premise is **true as a code
fact and false as a diagnosis of this bench**.

True as a code fact: measured with this project's own stemmer, `tolls/tolling/tolled → toll`, while
`says → says` and `said → said`. The kin classes (rings, hangs, carries, crosses, guards, bites) all
answer; toll alone does not.

False as a diagnosis, for one reason that is checkable in three lines:

```
qa_key("when does the bell toll?")  ->  "when does the bell toll"
qa_key("when does the bell toll")   ->  "when does the bell toll"      # identical
```

The stored question and the probe ask **already produce the same key**. Folding a key that already
matches changes nothing, and adding per-entry aliases to a lookup that already succeeds changes
nothing either — which is why both arms moved zero rows. The inflected form is not in the question,
it is in the **answer**: `it tolls at dusk`.

The ask dies downstream at the coverage gate. Every toll refusal in the artifact carries its own
reason: `the closest memory of his covers 32–33% of the question`, against
`ANSWER_COVERAGE_FLOOR = 0.6` (`organs/neural_language.py:2799`, refusal issued at `:5161-5190`).
`toll` is not among the memory's tokens as characters, so the coverage arithmetic never reaches a
store answer. `stem("tolls") == "toll"`, so folding the **coverage comparison** would recover the
class — and that is the denominator, not the key.

## 4. The second failure, and the residual the duel carries

Gate G1 licenses exactly one registered fallback per defect, then requires that a second failure
document the defect as an open problem rather than retry it:

> "one registered fallback per defect (tighter arbiter bound; per-entry morphological aliases instead
> of a global stemmer); a second failure documents the defect as an open problem and the duel runs
> with the residual measured and named."

The tighter bound was P1 and it worked. The per-entry aliases were F1 and it did not. **That is the
second failure.** The morphology defect closes MP-E9 as an open problem, with the residual measured
and named, and no third attempt is registered — `tests/test_mp_e9_gate.py` now asserts that there are
exactly two morphology attempts on the record.

**Residual, measured:** toll class 54 rows, 0 correct, 16 refused, 38 echo, present in all three arms
including control — the defect predates every treatment arm.

**Cause named for the next experiment:** morphology inside the coverage arithmetic. MP-E9 could not
address it because the coverage denominator is **E23/E25 territory** and out of scope by G2's
no-specification-edits-mid-run rule. The prior on that lever is on the record: E23 (`v_synt`) was
refuted because a guarded refusal *depended* on the denominator, and E24 phase 1 relocated that guard
onto the absence inventory, which is what makes the denominator re-testable at all. The next
experiment inherits that diagnosis rather than re-deriving it.

**What MP-E9 ruled out, so it is not re-attempted:** the store key form (P2, 0 of 3,672), and the
absence of per-entry aliases (F1, 0 of 3,672).

One note on method, because it is the part that earned the finding. F1's registration carried two
predictions and they resolved in opposite directions: its **success criterion** (H3's number) failed,
and its **mechanism prediction** — 0 rows would move, written from P2's post-mortem before F1 was
implemented or run — was confirmed exactly. The predicted falsifier was "any recovered toll row,
which would make P2's inertness a wiring failure rather than a premise failure". It did not occur.
Recording both is what turns two null results into a diagnosis.

## 5. Abort conditions, as measured

| | state | basis |
|---|---|---|
| **C1** untraceable word survives | **does not fire under P1** (0 rows); fired pre-treatment at 16 | `word_provenance` verdict counts |
| **C2** guarded row answers | **does not fire** — 24/24, row for row | src == `electric_absence` |
| **C3** learn-arm correct below pre-flag value | **does not fire** — 38/75/115 at the registered floor | `bench_noise_floor` headline |
| **C4** normalisation admits an unprovenanced pair | **NOT YET MEASURABLE** | see §6 |
| **C5** gains confined to one phrasing family | **VACUOUS** — no treatment produced gains to group | row movement |

C1 firing pre-treatment was never an abort of the experiment: it is the defect MP-E9 exists to close,
and P1 closing it is the experiment's positive result.

## 6. Known gaps, stated rather than left silent

**C4 remains NOT YET MEASURABLE, and the reason is that the population its threshold counts does not
exist yet.** C4 counts `qa_store` rows whose provenance is neither `person_marked` nor
`person_paraphrase`. No bench artifact exposes per-row store provenance — the rows carry `src`, not
`prov` — so there is no instrument for it, and neither morphology arm created the population because
neither arm reached a store answer. It is reported as `NOT YET MEASURABLE` in the gate output rather
than omitted, because a missing condition and a deliberate not-fired are different claims, and the
house rule that a missing key must never be read as a deliberate off applies to abort conditions too.

There is a second edge to C4 that is worth naming before anyone crosses it. F1's evidence ladder adds
two words — `typed_alias` and `person_alias` — which are **not** in C4's registered population. If the
alias path ever does produce an answer, those hits would be counted as violations by the threshold as
written. On this bench no alias ever reached an answer (0 rows moved), so the question is hypothetical
today. It is recorded here so that whoever makes the alias path fire widens C4's population
deliberately, with an amendment, instead of discovering it as an abort.

**`_qa_restore_report` is written and read by nothing.** The restore path records every fold collision
— two records re-deriving onto one key, first wins, loser named — and the bench never surfaces it.
The collision count is therefore a claim with an instrument behind it but no consumer: a restart
survival check would read it, and MP-E9 registered no such check. The mechanism is tested at unit
level (`tests/test_electric_qa_morph_aliases.py`: exact-first ordering, contested aliases dropped,
inert when off, index rebuilt at restore rather than persisted), but no run reports whether a real
house ever produced a collision.

**One line, one clone.** The battery clause is measured on a single clone (`operator=clone`, genome
`abffa2b7f101`), so unanimity across clones cannot be tested by it and an unstable ask would be
reported as stable by construction. Logged in `battery_pre_flag.json` under `limitations`.

**Chunked measurements, stated as such.** The battery ran as 6 `--only` chunks and each bench arm as 2
processes, because a single command is capped at 600 s against runs of ~18 min and ~8 min, and a
killed process writes nothing. Every merged artifact carries both input hashes and
`single_process_measurement: false`.

## 7. Disposition

**G1 is not met**, because H3 fails. The path is not abandoned on a null: P1 is a positive,
controlled result that closes the says leak at the head branch and satisfies H1 and H2 exactly as
registered, and H4 holds on freshly measured numbers.

What MP-E9 contributes to the duel is a **narrowed open problem**: the morphology defect is real, it
is not in the store key, it is in the coverage arithmetic, and the two candidate explanations that
were on the plan have each been measured and eliminated with zero rows moved. The residual is named,
the prior on the correct lever is cited, and the next experiment starts from that instead of from the
plan's original guess.

## 8. Artifacts

| file | what it is |
|---|---|
| `registration.json` | hypotheses, thresholds, `preconditions.PRE-1`, `registered_predictions` P1/P2/F1 with outcomes, `residual_for_the_duel`, `measured_states`, amendments |
| `baselines/bench_pre_arbiter_tell_HEAD.json` | the re-derived pre-flag snapshot |
| `results/battery_pre_flag.json` (+ `_rows.jsonl`) | H4's battery clause, measured; 42 rows preserved for recheck |
| `results/ab_flag_off.json` | flag-OFF arm, 3,672 rows |
| `results/ab_flag_off_reproduction.json` | the inertness proof: 0 differences |
| `results/treatment_arbiter_head_bound.json` | P1 |
| `results/treatment_arbiter_head_bound_effect.json` | P1 moved 16 rows |
| `results/treatment_qa_morph_normalize.json` | P2 |
| `results/treatment_qa_morph_normalize_effect.json` | P2 moved 0 rows |
| `results/treatment_per_entry_aliases.json` | F1 |
| `results/treatment_per_entry_aliases_effect.json` | F1 moved 0 rows |
| `results/gate_*.json` | the verdict computed over each arm |
| `organs_precondition.md` | PRE-1, the design step that gated B.2 |

Instruments: `tools/mp_e9_gate.py`, `tools/mp_e9_battery.py`, `tools/ab_reproduction.py`,
`tools/word_provenance.py`, `tools/bench_noise_floor.py`. Sealed by `tools/registration_seal.py`;
`--check` verifies worktree, index and anchor on every sealed entry; the count is in
`registration.json` under `harness_hashes.files` rather than repeated here, because a number copied
into prose is a number that can silently disagree with its own source.
