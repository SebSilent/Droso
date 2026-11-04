# MP-E10 — decision

Status as of 2026-08-10, at the tree carrying the tier-120 replay run. This file records what has been
measured, what is scoreable but unscored, and what is not instrumented. It does not upgrade any of those.

## Hypotheses

| | state | basis |
|---|---|---|
| **H1** — working memory over the mouth stages | **scoreable, UNSCORED** | D-MPE10-01 ruled the denominator (five stages: gating, mouth, recall, recall_untraced, shape_arbiter) and the k-sweep calibration ran at tier 40. No mouth-stage run has been executed, so there is no H1 figure. |
| **H2** — fluency improves | **scoreable in principle, UNSCORED** | D-MPE10-02 ruled a scalar: mean content words per emitted answer at the tier's live phase, with refusal rate and coverage as guardrails. The verbosity objection is registered against it and the ruling was conditional (D-MPE12-05 required the read-vs-inference ratio to be reported as a curve against generated-token count). Nothing has been scored. |
| **H3** — replay at tier 300 within the registered interference margin | **RUN AT TIER 300 AND VOIDED by the saturation guard at depths 2 and 3** | Two quantities per tier: interval 0.0000 pp (416 rows at tier 120, 1,046 at tier 300) AND row migration (66 rows at tier 120, 251 at tier 300, on the nine R13 identity fields). The guard pushed 72 entries to the 4.0 ceiling at depth 2 and 252 at depth 3 on the FIRST pass, so `void_for_H3` is true there and the 0.00 pp reading may not be quoted as satisfying the clause. Depth 1 is clean but is not the tier the clause names. |
| **H4** — update-rate counter | **NOT INSTRUMENTED** | `docs/h4_updates_counter_design.md` is a design with an inertness protocol attached. No counter exists in the write path. |

## H3 as measured — tier 120

From `experiments/MP-E10/results/replay_tier120_summary.json`, learn arm, clean restarted house, against the
same-tier unreplayed baseline `experiments/MP-E8/results/armA_tier120_curriculum.json`, extracted by the same
code path on both sides.

| depth | correct replayed | correct baseline | rows divided by | interference | within 2.0 pp |
|---|---|---|---|---|---|
| 1 | 122 | 122 | 416 | **0.0000 pp** | yes |
| 2 | 239 | 239 | 416 | **0.0000 pp** | yes |
| 3 | 347 | 347 | 416 | **0.0000 pp** | yes |

Reported as a measured quantity with its row count, per D-MPE10-04 condition 2 — not as a bare pass/fail.

**Saturation guard, per pass:** no entry reached the ceiling at any depth; `void_for_H3` false everywhere;
counters unmoved (`transitions` / `sequences_learned` identical before and after each pass). The registered
prediction held: maximum accumulation 0.70 (2 passes × 0.35) against a 4.0 ceiling, so no configuration should
be ceiling-limited, and none was.

**What this number does not mean.** H3 is an interference claim, not a strengthening claim. A replay pass as
registered adds one gain increment to every stored pair — a uniform translation of the whole chain — which can
show absence of interference and can show ceiling behaviour, and cannot show that consolidation works. The
0.00 pp result is exactly what a uniform translation predicts, and must not be written up as evidence that
re-experience strengthens anything.

**Named limitations of this number:**

- **D-MPE10-04 condition 3 is UNSPENT.** The tier-300 clone set was declined for cost (~2.7 h). The 2.0 pp
  margin therefore still rests on tier-40-derived clone noise (11 rows of 3,672 = 0.2996 pp; rule-of-three
  bound 1.887 pp from 0 regressions in 159 tier-40 exposures). If a future tier-300 number lands near the
  margin, it is not decidable without that re-measurement.
- **Single restart boundary.** `electric_learn_bench` restarts once per depth (save → boot → load), not twice,
  so the two registered passes ran at the one boundary the instrument has. Recorded in the artifact.
- **Scope of the run.** The replayed runs execute the learn arm only. The sealed baselines are 3-arm
  (control/teach/learn); control and teach were not re-run under replay, so nothing may be claimed about them.
- **rc=1 is pre-existing at tier 120.** The bench's own gate list is non-empty for this tier: the unreplayed
  baseline carries 13 distractor-gate failures and this run carried 12. That is a property of tier 120, not
  replay damage — and it is stated because a return code of 1 in a result line would otherwise read as failure.

## H3 as two quantities, per tier (2026-08-10, after tier 300)

| | tier 120 | tier 300 |
|---|---|---|
| **interference interval** (registered quantity) | 0.0000 pp at depths 1/2/3, divided by **416 rows** (380 taught probes at d3); correct 122/239/347 identical to baseline; within 2.0 pp | 0.0000 pp at depths 1/2/3, divided by **1,046 rows** (956 taught probes at d3); correct 292/548/784 identical; item retention identical (kept 80/129/176) |
| **row migration** (the quantity the protocol does not register) | **66 rows moved** of 3,222: 65 taught, 1 distractor. `refused → partial` dominates (3/7/14 restarted). 5 rows moved on `mech` alone (`refusal_silence → ask_not_recognized`); 1 distractor moved `invented → refusal_silence` (gate list 13 → 12) | **251 rows moved** of 8,199: 242 taught, 9 distractor. `refused → partial` 11/30/53. Distractor axis moved **both ways** at d3: `invented → refused` ×3 and `refused → invented` ×5 — the latter is the direction R6/C1/C2 care about. Also 1 `refused → correct` and 2 `correct → refused` on taught rows |
| **saturation guard** | silent everywhere; prediction held (0.70 max vs 4.0 ceiling) | **FIRED**: d2 pass 1 pushed **72** entries to the ceiling, d3 pass 1 pushed **252** → `void_for_H3` true at both, `passes_run` 1 (it stopped). d1 clean |
| **what may be quoted** | interval, with the migration beside it | **nothing as satisfaction of the clause** — a ceiling-limited configuration has no H3 number |

**The off-control is the reason the migration is not a replay result.** Same tree, same curriculum, same seed,
replay **OFF**: **58 of 3,222 rows moved** against the same sealed baseline — including the identical
`refused → partial` counts at d1 (3), d2/restarted (7) and d3/restarted (14). So most of tier 120's "migration"
is **run-to-run drift against a sealed single-run baseline (~1.8% of rows)**, not a treatment effect. The
replay-attributable residue at tier 120 is the one distractor `invented → refusal_silence` and the `mech`-only
rows. Tier 300's distractor movements have **no control yet** and must not be attributed to replay.

**Two named limitations, neither of them fixed here.** (a) The registered H3 quantity is too coarse to capture
class movement — it read 0.00 pp while 66 rows changed class, and read the same on a run the guard voided.
Whether H3 needs a second registered quantity is the PI's call about the protocol. (b)
`sealed_baseline_reproducibility` is now open: every arm-vs-baseline comparison in this program rests on sealed
single runs, and two identical runs differ on 1.8% of rows. Separating nondeterminism from environment drift
needs fresh-vs-fresh diffs, which this turn did not have budget for.

**rc note for both tiers:** the bench returns rc=1 whenever its own gate list is non-empty. Tier 120: 12
failures replayed vs 13 unreplayed. Tier 300: 92 vs 101. That is a pre-existing property of these tiers, not a
crash and not replay damage.

## The defect that made the first tier-120 run meaningless

The first tier-120 run reported `replay_present=False` at every depth and reproduced the unreplayed baseline
byte for byte (122/239/347 of 416). Cause: the `--replay` flag was set in the `__main__` guard, which executes
**before** the module reaches `REPLAY_REQUESTED = False` further down, so the assignment was overwritten. The
parse now happens at the definition site, and the fix was verified at tier 40 before any tier was re-run. The
lesson is in the artifact: an instrument that reports a treatment it did not apply is the failure this whole
ledger system exists to catch, and it was caught by reading the artifact rather than the exit code.

## Open defects and named-missing, with prices

| item | state | price |
|---|---|---|
| `licensed_absence_intermittence` | **OPEN, named, not closed.** Cleared as a gate on H3 because the flip lives in `reason`, which R13 tolerates, and the safety property (never spoken, never from the arbiter head) held under every seed tested. A green suite from an intermittent is not proof of absence. | hunt: N runs across seeds/contexts to estimate the flip rate, then make hit construction order-independent (`organs/neural_language.py:5387`, upstream of the list-iterating `_arbitrate_shape` at `:4129`). Needs a PI ruling and a re-baseline, because published evidence quotes `reason`. |
| **Tier 300 replay run** | RUN — guard-voided at depths 2/3 | done; what remains is a tier-300 OFF control and a replay entry that does not push a near-ceiling store over the ceiling. |
| **Tier-300 clone set** (‑04 condition 3) | UNSPENT, declined for cost | ~2.7 h; required before a near-margin tier-300 number is decidable. |
| **Episode tape** for selective replay | registered follow-on, not a blocker on H3 | an organ change plus a re-registered pass definition; belongs to MP-E10's consolidation ambition and MP-E12b's compiler. |
| **GPT-2 donor** for MP-E12 | absent | MP-E12's H2 curve is measured on a synthetic donor only. |
| **Routing house wiring** | named-missing | an organ change; not authorised by D-MPE10-03. |
| **H4 counter** | design-only | edits the write path; needs a ruling and the inertness proof in `docs/h4_updates_counter_design.md` §5. |
| **Mouth-stage run** for H1 | not executed | the k-sweep grid is calibrated; the scored run is the cost. |
| **D-MPE10-05 identifier collision** | both meanings documented at each path; renumber to D-MPE10-09 registered as a **dated amendment PROPOSAL**, not applied | seconds, once accepted. History is not renumbered in place (R5). |

## Quoting guard

`result_quoting_guard_while_blocked` remains in force. Its stated reason was corrected on 2026-08-10 — the
definitions are ruled — but what still binds it is that **no MP-E10 figure has been scored on the current
tree**. Nothing in this file may be quoted as a hypothesis verdict: H1 and H2 are unscored, H3 is measured only
at a tier the clause does not name, and H4 is not instrumented. Where a blocker is open, the guard applies to
the figure, not to the vocabulary.

## Not restated here

`gate_G3`'s conditions C1–C5 and the checklist states live in `experiments/MP-E10/registration.json` and are
not copied into this file: they were not re-read from the ledger before writing, and a decision document that
paraphrases a gate it has not re-checked is how this project's headline-and-table contradictions start. C5 is
the one condition quoted above, because its content is load-bearing for H3's interpretation — a variant-(ii)
win is an ablation result and does not show the drive worthless.
