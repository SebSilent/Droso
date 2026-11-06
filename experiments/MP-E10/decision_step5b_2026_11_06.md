# MP-E10 decision — STEP 5b, the scored tier-120 replay run (2026-11-06)

**Supersedes by reference:** `experiments/MP-E10/decision.md` (118 lines). That file is **left sealed and
unaltered**; every figure in it remains the record of the runs that produced it. This file changes one thing about
how it should be read: H3 now has a tier-120 measurement made on the current instrument bytes against a floor
measured on those same bytes, which the old file did not have.

Status as of 2026-11-06, at the tree carrying the scored run. This records what has been measured. It does not
upgrade any of it.

## Why this run exists and the one before it does not count

The first attempt at STEP 5 is on disk at `experiments/MP-E10/results/step5_scored_tier120.json`, marked
`VOID_NOT_A_SCORED_REPLAY_RUN` inside the file. It stays there as measured and is **never quoted as a score**: its
replay arm never replayed, because the driver called the bench in-process and the bench parses `--replay` only
inside its `__main__` guard (`tools/electric_learn_bench.py:422-426`). The fix — each arm as its own subprocess —
was **proven on the cheapest registered tier before any scored minute was spent**:
`experiments/MP-E10/results/step5_replay_branch_proof_tier40.json` records a replay report at depths 1, 2 and 3
with `passes_run` 2 and `gain` 0.35, rc=0, 160.42 s.

## What was run, and what it cost

| arm | wall seconds | learn-arm seconds | rc | replay report |
|---|---|---|---|---|
| replay (`--replay`) | reused, see note | **488.30** | 1 | depths 1, 2, 3 |
| control (unreplayed) | **492.27** | 488.90 | 1 | none, by design |

Measured unit costs beside these: the PI's estimate was ~475 s; the pre-A10 pair measured 480.91 / 462.37 s;
pair 5, the sealed floor, measured 474.12 / 413.42 s. **Note on the replay arm's wall field:** its artifact was
produced by the immediately preceding launch of this driver, which completed the bench subprocess and then died
building its own record. The driver now verifies such an artifact before reusing it — a replay report at all three
depths, on the bytes the floor bounds — and records the reuse in the artifact rather than hiding it. The arm's own
`arms.learn.seconds` field is what is quoted above.

Both arms ran on harness `47f05c9c20ddeb75…`, the byte-set of the sealed floor.

## The floor it was scored against

Pair 5, sealed: **6 rows of 3,744 = 0.1603 %** on harness `47f05c9c20dd…`, four agreeing pid samples at 19308,
A10 sampler active. Pair 3 on the same bytes moved 5 rows (0.1335 %) but executed **without** the sampler, so pair
5 governs by executed path, not by which number is smaller. The older tier-120 floors — 17 rows and 4 rows —
bounded `5cf038c2…`, a byte-set that exists in no commit, and bind nothing here.

The two arms are **not** in one process, and that is correct: R17's same-process condition belongs to a
fresh-vs-fresh pair, where identical code must be shown to still differ. Treated and untreated arms are not
identical code — that is the comparison.

## H3 — interference, as measured at tier 120

Retention delta, replay minus control, at the registered phase basis (`reasked`) and at every phase:

| depth | phase | correct replay | correct control | rows | delta pp | interval at the floor |
|---|---|---|---|---|---|---|
| 1 | reasked | 122 | 122 | 416 | **0.0000** | [−0.1603, +0.1603] |
| 2 | reasked | 239 | 239 | 416 | **0.0000** | [−0.1603, +0.1603] |
| 3 | reasked | 344 | 344 | 416 | **0.0000** | [−0.1603, +0.1603] |

Same at `live` and `restarted` — all nine cells read 0.0000 pp, interval ± 0.1603 pp.

Row migration, replay vs control, on the nine R13 identity fields: **1 row of 3,744**. The floor is 6.

**What this means, stated without spin.** Every interval contains zero and the migration is *below* the floor, so
the instrument **cannot resolve a difference at this size in either direction**. That is not evidence that replay
strengthens anything — H3 is an interference claim, and an unresolvable difference is an unmeasured one, not a
positive one. Nor is the 0.0000 pp reading a satisfaction of the clause: it says retention did not move, and the
registered margin (2.0 pp) was never approached, but the resolution limit (0.1603 pp) is what bounds the claim.

**Ceiling guard, per pass, per depth — the guard did NOT fire at tier 120.** At all three depths, both passes:
`entries_at_ceiling_before` 0, `entries_pushed_to_ceiling_this_pass` 0, `void_for_H3` **false**,
`ceiling_limited` false, `reason_void` "no entry reached the ceiling". `passes_registered` 2, `passes_run` 2,
`gain` 0.35 everywhere. The registered prediction held (max accumulation 0.70 against a 4.0 ceiling). So unlike
tier 300, the tier-120 reading is **not voided by the guard** — it is bounded by the floor instead. Those are
different limitations and must not be conflated.

Tier 300 is not run here and is reported only as a capacity datum under C6.

## H2 — fluency, as ruled

Scalar: mean content words per emitted answer over the live phase, counted by `word_provenance.content_words` —
the same function MP-E8's descriptive figure uses.

| | mean content words | refusal rate | coverage |
|---|---|---|---|
| MP-E8 arm-A baseline, tier 120 | **3.0107** | 39.8237 % | 60.1763 % |
| STEP 5b control | 2.9739 | 38.7019 % | 61.2981 % |
| **STEP 5b replay** | **2.9764** | 38.7821 % | 61.2179 % |

**H2's clause FAILS on its own scalar.** Replay is 0.0343 content words *below* the same-tier baseline, not above
it. The guardrails moved the other way — coverage up 1.04 pp, refusal down 1.04 pp — and the ruling names those as
guardrails beside the scalar, not as the scalar, so they cannot rescue the clause. Note that the unreplayed
control is *lower* still (2.9739), so this is a property of the current tree at tier 120 rather than damage
attributable to replay; attributing it to replay would need a floor on the fluency quantity, which does not exist.

## H1 — the five-stage mouth denominator, and an instrument limitation found on this run

Graded rows per cell: 416 at every depth and phase (3,744 total). Failing rows and their stage attribution,
replay arm:

| depth/phase | failing | gating | mouth | recall | recall_untraced | shape_arbiter | other |
|---|---|---|---|---|---|---|---|
| 1/live | 280 | 0 | 0 | 0 | **280** | 0 | 0 |
| 1/reasked | 265 | 0 | 0 | 0 | **265** | 0 | 0 |
| 1/restarted | 280 | 0 | 0 | 0 | **280** | 0 | 0 |
| 2/live | 157 | 0 | 0 | 0 | 157 | 0 | 0 |
| 2/reasked | 154 | 0 | 0 | 0 | 154 | 0 | 0 |
| 2/restarted | 153 | 0 | 0 | 0 | 153 | 0 | 0 |
| 3/live | 47 | 0 | 0 | 0 | 47 | 0 | 0 |
| 3/reasked | 38 | 0 | 0 | 0 | 38 | 0 | 0 |
| 3/restarted | 38 | 0 | 0 | 0 | 38 | 0 | 0 |

`recall_untraced` is printed **as untraced**, per D-MPE10-01: it is a default attribution, not a measurement.
Mass in `other` is **0 rows** — named, not divided away — so the five-stage denominator covers this run's output.

**The limitation is the finding here, not the table.** Every failing row classified as `recall_untraced` because
the bench records `reason: ""` per row, and the registered classifier returns `recall_untraced` for an empty
reason. **The five-stage denominator therefore cannot discriminate on bench rows at all.** H1's real instrument is
`heldout_eval` over the held-out script set, which has no `--state-root` and cannot be pointed at a bench workdir.
H1 remains **UNSCORED**, and this table must not be read as its answer.

## A10 — the resource ledger, measured on a registered run

Available on both arms. Replay: 2,380 samples, whole-run peak 2,333,097,984 B. Control: 2,382 samples,
2,364,968,960 B. **VRAM asserted zero on both**: `torch.cuda.is_initialized()` is False, so no CUDA context exists
to hold a byte.

Peak RSS per phase and cost per retained item, replay arm (bytes; `cost/item` = peak RSS of the phase window
divided by taught rows answered `correct` in that phase):

| phase | peak RSS | retained | cost / retained item | samples |
|---|---|---|---|---|
| d1 teach | 502,976,512 | — | **none** | 29 |
| d1 live | 736,124,928 | 122 | 6,033,810.9 | 137 |
| **d1 replay** | **none** | — | **none** | **0** |
| d1 restarted | 890,441,728 | 122 | 7,298,702.7 | 267 |
| d1 reasked | 893,300,736 | 122 | 7,322,137.2 | 285 |
| d2 teach | 1,278,390,272 | — | none | 44 |
| d2 live | 1,444,360,192 | 239 | 6,043,348.1 | 136 |
| **d2 replay** | **none** | — | **none** | **0** |
| d2 restarted | 1,395,765,248 | 239 | 5,840,022.0 | 288 |
| d2 reasked | 1,399,083,008 | 237 | 5,903,303.8 | 300 |
| d3 teach | 1,776,549,888 | — | none | 61 |
| d3 live | 2,102,657,024 | 347 | 6,059,530.3 | 144 |
| **d3 replay** | **none** | — | **none** | **0** |
| d3 restarted | 2,248,671,232 | 347 | 6,480,320.6 | 337 |
| d3 reasked | 2,333,097,984 | 344 | 6,782,261.6 | 352 |

**Named rather than interpolated: no sample landed in any of the three replay-phase windows** (0 samples each).
The sampler interval is coarser than the replay window, so the phase that is the entire subject of H3 is the one
phase with no resource measurement. Cost per retained item is null there and is **not** filled from a neighbouring
window. The `teach` windows carry samples but no retained-row count, so their cost is null for a different reason.
This is an instrument gap to fix by shortening the interval or widening the window, not a finding about cost.

## R6 — the four named guarded probes

Probes: `P-numeral-final`, `R-count-moon`, `R-disj-reversed`, `R-order-ofthe`. **NOT MEASURED on this run, and the
reason is a missing precondition, not an omission.** They are scored by `tools/mp_e9_battery.py` over a generation
journal written by `tools/run_generation.py`; the bench produces no such journal. `run_generation.py` does accept
`--state-root`, so the route exists — it is a separate authorised step, not a flag on this run.

## G3 — position as measured

**G3 does not close.** Conditions and their state on this evidence:

- **H1 — UNSATISFIED, and unscoreable on this instrument path.** The five-stage denominator cannot discriminate on
  bench rows; the registered H1 instrument cannot reach a bench house. Not a failure of the organism — a gap in
  the instrumentation.
- **H2 — UNSATISFIED on its ruled scalar.** Replay 2.9764 vs same-tier baseline 3.0107 content words per emitted
  answer: it did not improve. Guardrails moved favourably and are guardrails, not the clause.
- **H3 — NOT ESTABLISHED, for a reason that is not the old one.** The saturation guard did **not** fire at tier
  120 at any depth or pass, so this is no longer the void-at-its-own-tier problem. What bounds it now is the
  floor: every interval is ±0.1603 pp and contains zero, and the replay-vs-control migration (1 row) is below the
  floor (6 rows). The instrument cannot resolve a difference at this size. **A 0.0000 pp reading inside the floor
  is not satisfaction of the clause**, and nothing here supports a claim that replay strengthens anything.
- **H4 — NOT INSTRUMENTED.** No update-rate counter exists in the write path.
- **R6 — UNMEASURED** at tier 120 on this run, precondition missing as stated.
- **A10 — MEASURED**, with the replay-window gap named above rather than interpolated.

The single load-bearing unsatisfied hypothesis for G3's purpose is **H2**: it has a ruled scalar, a same-tier
baseline, and a measurement, and the measurement is in the wrong direction. H1 and H4 are not instrumented
enough to fail; H3 is measured but unresolvable at the floor's width.

## What this does not do

No cap raised, nothing downloaded, no MP-E11, no MP-E12b/c, no answer-path edit. T and N was declined by the PI
for cost and is not started: **G2's evidence stays incomplete and nothing in this file rescues it.** The prior
decision.md is unmodified. The void run is unmodified and unquoted as a score.
