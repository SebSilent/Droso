# MP-E8 — The Duel: Arm A against Arm B against Arm C

**Experiment:** MP-E8, the three-arm duel at tiers 40 / 120 / 300 (DROSO Master Plan v1.1 §6.2, checklist B.3).
**Gate:** G2. **Status at this writing:** all three arms have complete artifacts at all three tiers, and the
battery regression guard has been run **once per arm, all three arms, ELECTRIC off, and all three pass the
clause** (frozen 19/24, guarded 4/4 — §8). **G2's evidence is closed out and the outcome is named: G2 does not
pass.** Not because an artifact is missing — because the hypotheses the artifacts test are not satisfied, and
one of them (H4) has no instrument for half its registered quantity.
**Registered in:** `experiments/MP-E8/registration.json` (16 amendments, AMD-MPE8-01 … 16; 8 PI rulings;
2 decisions still open: D-MPE8-10, D-MPE8-11).

---

## 1. What was claimed, and what was measured

Every number below is read out of a committed artifact by the script named beside it. No threshold in this
section was chosen after the measurement; the ones that were chosen before it are marked DERIVED in the
registration and carry their basis.

| | registered criterion | measured | verdict |
|---|---|---|---|
| **H1** arm B drops below its own session-1 by ≥ 5.0 pp, tiers 120 **and** 300 | drop ≥ 5.0 pp, least favourable seed | tier 120: **1.6827 pp**; tier 300: **−2.6769 pp** (the drop's sign is reversed) | **FAILS at both tiers, differently** |
| **H1** arm A holds its taught set across restarts (retention ≥ 1.0) | hard invariant, no margin to choose | tier 40 and 120: 100.0% at every depth; tier 300 depth 3: **99.87%**, two named rows lost | **WITHDRAWN at tier 300** (C3 executed, D-MPE8-09) |
| **H2** clause 1 — arm A refuses guarded-absence rows ≥ 24 | 24 rows | arm A has **0** guarded-absence rows; all 24 live in the teach arm | **INSTRUMENTALLY UNDEFINED** (D-MPE8-07) |
| **H2** clause 2 — arm C refuses never-taught rows more than arm A, at 120 **and** 300 | strictly greater | tier 120: **94.44% vs 79.32%**; tier 300: **80.37% vs 73.21%** | **PASSES**, under a reading the PI must rule on (§5) |
| **H3** fluency / open-ended composition | none — no instrument | descriptive figures only (mean content words per utterance, TTR) | **NOT YET MEASURABLE** (D-MPE8-04) |
| **H4** A_total < B_total at each tier, **in both updates and wall-clock** | both halves required | wall-clock: measured for all three arms at all three tiers. Updates per taught fact for arm A: **no instrument** | **PARTIAL** |

## 2. The withdrawal, stated as a ruling rather than as a footnote

C3's registered action is **abort**, and C3 fired at tier 300: two taught items — `3/tell0.26/object` and
`3/tell0.38/object` — were correct live at depth 3 and refused after a real restart. Zero rows at tier 40,
zero at tier 120. The PI ruled on D-MPE8-09 on 2026-11-04 (`pi_decisions.rulings['D-MPE8-09']`), and the
replication that settled it split the two rows:

* **`3/tell0.26/object` reproduces** on a re-run at the same seed, same harness hash, same curriculum hash.
  A real loss of taught-item availability. This is the row that falsifies H1's arm A clause at tier 300.
* **`3/tell0.38/object` does not reproduce.** It is registered as **restart-phase instability**. R13 was not
  edited to cover it — the registered cells were chosen before these runs, and widening them after seeing a
  row move is the R2 fault D-MPE8-05 refused to commit. The gap this leaves is D-MPE8-10's, put to the PI.

**What abort means here.** The tier-300 arm-A taught-set-holds claim is **withdrawn**; no further claim may
be built on arm A holding its taught set at tier 300, here or downstream. What abort does **not** mean: the
artifacts stay published (`armA_tier300_curriculum.json`, `armA_tier300_rerun.json`,
`armA_tier300_rerun_c3_diff.json` are all in the seal), and the experiment was not halted. The plan's own
gate text is the authority for that — *"The experiment succeeds regardless of which arm wins, because both
outcomes define paper 1"* — and G2's fallback action is *"Re-run the flawed arm only; no specification edits
mid-run"*, which is exactly what was done.

One detail the aggregate hides and should not: at tier 300 depth 3 arm A reads **785 live / 784 restarted**,
a net loss of one row, while C3 names **two** rows lost. A net tally can hide two losses and a gain. That is
why C3's registered `measured_by` says *"per item, named not counted"*.

## 3. The finding that frames everything else: the baseline never had the knowledge

Arm B is a 3.6 M-parameter sequential LM trained on the same curriculum files arm A reads. Its **session-1**
live correct rate — the level every "forgetting" claim is measured from — is:

| tier | arm B session-1 | arm A session-1 |
|---|---|---|
| 40 | 12 / 136 = **8.82%** | 38 / 136 = 27.94% |
| 120 | 29 / 416 = **6.97%** (seeds: 6.25–7.45%) | 122 / 416 = 29.33% |
| 300 | 17 / 1046 = **1.63%** (seeds: 1.15–1.63%) | 291 / 1046 = 27.82% |

**The small LM could not represent the curriculum at tiers 120 and 300.** It sits between 1% and 7% from the
first session, and at tier 300 it *improves* with exposure (1.63 → 3.73 → 4.30%) rather than decaying. H1's
arm B clause asks it to drop by at least 5.0 percentage points; from a 1.6% baseline that is arithmetically
almost the whole of its competence, and the measured curve goes the other way. So the duel did not compare a
forgetting baseline against a retaining one — **it compared an arm that holds knowledge against an arm that
never acquired enough of it to lose.** That is a finding about the comparison, not a win for arm A. A 5 pp
margin cannot separate *"forgot"* from *"never knew"* at this absolute level, and the honest statement is that
the instrument cannot answer the question H1 asks at tiers 120 and 300 as configured — not that the margin is
wrong, and the margin has not been moved.

Arm C, the frozen-verbalizer-plus-retrieval arm, scores **0.0% correct at every tier and every depth**
(0 of 136, 0 of 416, 0 of 1046). Per AMD-MPE8-12 that figure is inadmissible as evidence against
frozen-plus-retrieval as a class: correctness at this scale is capacity-bound, not architecture-bound, and arm
C was registered to be graded on its gate and near-miss measures instead. It is reported here because an
artifact that hides its score is worse than one that reports it and says what the score does not mean.

## 4. The four curve figures

`experiments/MP-E8/results/curves_four_figures.json` holds all four, generated by `_tmp/mp_e8_curves.py`
from the nine arm×tier artifacts. Summary:

**Exposure** (live correct % across depths 1/2/3) — arm A rises everywhere: 27.9→55.1→84.6 (t40),
29.3→57.5→83.4 (t120), 27.8→52.2→75.0 (t300). Arm B is flat or inverted: 8.8→9.6→4.4, 7.0→6.3→3.1,
1.6→3.7→4.3. Arm C is 0→0→0.

**Forgetting** (restarted as % of the same depth's live) — arm A: 100.0% at every depth at tiers 40 and 120;
at tier 300, 100.34% / 100.37% / **99.87%**. Arm B: **100.0% at every tier and depth** — a restart changes
arm B's answer set not at all, because there is nothing there to lose. Arm C: undefined (0/0).

**Interference** (answers produced out of competing taught material; invented + misattributed + cross-echo,
% of the battery) — arm A stays low and rises with tier: 0.74–2.94% (t40), 0.96–3.61% (t120),
2.58–4.30% (t300). Arm B confabulates between **14% and 66%** of the battery — it has no abstention path, so
every row gets an answer. Arm C's rate rises with depth (t300: 0% → 41.7% → 62.0%) because its gate lets more
rows through as more of the battery becomes taught. On the never-taught population specifically, arm A
answers **9.26 / 20.68 / 26.79%** of rows it was never taught at tiers 40/120/300, arm C answers
**0 / 5.56 / 19.63%**.

**Cost** — see §7.

**Cross-tier reading is ruled, not chosen.** `confounds.cross_tier_comparability_regime_break` measures that
tiers 120 and 300 satisfy constraint (b) strictly (0 asks using untaught content words) while the sealed tier-40
baseline does not (8 asks do). Tier 40→120 curves are therefore **CONFOUNDED** and 120→300 curves are
comparable. Nothing in §4 plots across that break as if it were one line.

## 5. H2: one clause undefined, one clause passed by an arm with zero correct answers

Clause 1 required arm A to refuse ≥ 24 guarded-absence rows. Measured on four trees including the sealed
baseline: **all 24 `src == electric_absence` rows are teach-arm rows; arm A has none.** A threshold of 24 on a
population of 0 is not a failure and not a pass — it is undefined, and D-MPE8-07 ruled it recorded that way
rather than re-scoped onto the teach arm's rows, which would have made arm A's claim about a different arm.

Clause 2 passed at both required tiers (§1). The limitation is on its face: **clause 2 compares refusal on
never-taught rows and requires nothing of the taught rows, so a system that never answers anything scores
100% on it** — and arm C, which scored 0.0% everywhere, did exactly that. The selectivity measurement is what
keeps this from being read as a calibration success: arm C's gate lets taught asks through **21.7 / 29.14 /
7.68 pp** more often than never-taught ones at tiers 40/120/300, so its abstention is not blanket. But the
similarity-floor Youden J falls from 0.1987 to 0.0446 at depth 1 as the tier grows — the fitted thresholds get
weakest exactly where the clause is claimed. Whether clause 2 needs a companion specificity requirement is
**D-MPE8-11**, open to the PI; the clause text was not edited, because adding a requirement to a registered
hypothesis after its first measurement is the same fault as removing one, in the other direction.

## 6. H3: not instrumented

There is no fluency / open-ended-composition instrument, and none was invented to fill the gap. D-MPE8-04
ruled H3 **descriptive and non-gating**: type-token ratio and mean content words per utterance are recorded
with the word DESCRIPTION attached and a `threshold: null`, and may not be used to score an arm. The plan's
gate wording was checked before treating H3 as a go criterion: G2 names artifacts and the four figures, not
H3. So the state is *NOT YET MEASURABLE*, stated the way MP-E9 stated C4 — *"the loss is recorded, not hidden"*.

## 7. H4: wall-clock measured, updates not, and no proxy substituted

| tier | arm A wall-clock | arm B train wall-clock (steps) | arm C train wall-clock (steps) |
|---|---|---|---|
| 40 | 481.3 s for 40 items (registration-quoted; the tier-40 artifact carries no timing block) | 15.549 s (360) | 36.738 s (—) |
| 120 | 23.47 min, −2.6% vs the 24.1 min projection | 35.100 s (900) | 85.152 s (900) |
| 300 | 53.65 min, −10.88% vs the 60.2 min projection | 165.731 s (2,340) | 208.653 s (2,340) |

Arm A's cost per learned fact **in updates** is **NOT MEASURED**. The organ exposes no counter for synapse
updates per taught fact; plastic-synapse counts (2,983 at build) are a state, not a rate. A before/after diff
of plastic weights was considered and rejected: it counts synapses whose *value* differs, not *update events*,
and cannot see an update that cancelled out or three writes to one synapse — so it is not the registered
quantity. Counting update events would mean instrumenting the write path, which is a Droso internal, and the
brief says do not modify Droso internals during the run. **No wall-clock-only number in this document implies
the updates half was measured**, and H4's registered comparison ("in both updates and wall-clock") therefore
cannot close. The two arms' wall-clock figures are not directly comparable either: arm A's is a whole
three-arm, three-depth bench run and arms B/C's are training loops, so the cost curve is reported per arm, not
as a single ratio.

## 8. The battery regression guard, once per arm

The plan's step 7: *"run the frozen battery once per arm as the regression guard, ELECTRIC off."* Two things
had to be settled before it could be run, and both are recorded rather than assumed:

1. **The recorded MP-E9 invocation cannot be copied here.** It reads `--only {count-frequency,order-first-last,…}`,
   which is bash brace expansion. This machine has no brace expansion, and `run_generation.py:546` filters with
   `only in script["name"]` — a substring test. The comma-joined string matched **0 asks**, the run built
   nothing, and `publish()` died looking for a journal that was never written. The first attempt at this guard
   is that failure; the fix is chunking, one generation number per script family, merged by the grader — which
   is what MP-E9's `generations: [9001..9006]` actually were.
2. **"Per arm" cannot mean the arm answering the battery.** 0 of the 24 frozen ask rows carry a `taught`
   context: the battery's questions are answered out of the house's episode state, so an arm cannot answer them
   without the house. The guard is therefore run as the house battery executed **in the same process as the
   arm's harness**, ELECTRIC off — which is the risk it exists to catch, because arms B and C brought torch
   into this environment and torch can move house numerics without any test of the arm itself noticing.

Results are graded by `tools/mp_e9_battery.py` against MP-E9's registered clause (frozen 19/24, guarded 4/4),
with ELECTRIC verified off from the journal's own `provenance.code_flags` rather than asserted:

| arm | artifact | frozen | guarded | paraphrase | ELECTRIC |
|---|---|---|---|---|---|
| A | `experiments/MP-E9/results/battery_pre_flag.json` (sealed, tree 5e1e663, pre-torch) | 19/24 | 4/4 | 0/14 | off, verified |
| B | `experiments/MP-E8/results/battery_guard_armB.json` | **19/24** | **4/4** | 0/14 | off, verified from `provenance.code_flags` |
| C | `experiments/MP-E8/results/battery_guard_armC.json` | **19/24** | **4/4** | 0/14 | off, verified from `provenance.code_flags` |

Both new runs graded 42 asked rows on one genome (`abffa2b7f101`), the same 24 frozen asks, and the
grader's `frozen_lost_vs_baseline` and `frozen_gained_vs_baseline` sets are **both empty** for both arms:
carrying torch in-process did not move a single frozen ask in either direction. `h4_battery_clause_pass`
is `true` for both. So the guard does its job — it found nothing to guard against, and that is a result,
not an absence of one.

**How arm B's run actually got finished, because the first attempt died.** The six-chunk loop died at
chunk 4 when this agent's process was recycled at 02:38:35 UTC, leaving generations 9101–9103 on disk and
9104–9106 unwritten; arm C had not started. It was resumed **one chunk per command**, each chunk writing
its own provenance file (`_tmp/batt_chunk_<gen>.json`) before it exits, so a death can cost one chunk and
is visible in the files instead of only in a log. All six chunks of an arm therefore ran on the same tree
— `HEAD` was `8200abb` throughout, and the only modified tracked files were `experiments/MP-E8/registration.json`
and `tools/registration_seal.py`, neither of which the battery's house path reads. The merge is still one
measurement by the grader's own criterion (it aborts if chunks disagree on genome; they do not), but it is
honest to say the six chunks are not six calls inside one process.

**A byte-size signal, stated at its true strength.** MP-E9's sealed artifact records the pre-deletion byte
size of each of its six chunk journals: 5,341 / 6,774 / 6,563 / 7,459 / 8,697 / 4,366. Arm B matches five
of the six and differs by **+2 bytes** on `order-first-last` (6,776 vs 6,774); arm C matches five of six and
differs by **−2 bytes** on `exact-repeat` (7,457 vs 7,459). The two mismatches fall on different families
and in opposite directions, so they are not a systematic shift — and the journals cannot be diffed against
the baseline at all, because MP-E9 deleted its own as scratch (`journals_deleted_scratch_not_for_recheck`),
leaving only the recorded sizes. So this is a hint, not a proof, and the verdict is not written from it: the
verdict is written from the empty lost/gained sets above, which say no frozen ask moved in either direction
for either arm.

Arm A's 19/24 is MP-E9's sealed artifact and predates the torch environment MP-E8's arm A runs actually used;
that gap is named here rather than papered over. Arm A's reproducibility *in the current environment* is
carried instead by `noise_floor_reverification_newenv.json` (0 and 0 rows differ outside R13's gated cell, 1
inside).

## 9. G2: what is complete, and what is named missing

G2 requires *"complete, valid, sealed artifacts for arms A, B, C at tiers 40/120/300 plus the teach-arm control
and noise floor; forgetting, interference, exposure and cost figures valid; battery regression guard run once
per arm"*, with the fallback *"re-run the flawed arm only"*.

**Complete:** A/B/C artifacts at all three tiers (9 artifacts); the four curve figures (§4); the battery guard
per arm (§8); T and N — `arms.T` measured at tier 40 on the current tree (24 guarded-absence rows, all in the
teach arm) and `arms.N` re-verified on the current tree within the registered noise floor.

**Named missing, not glossed:**
* **H4's updates half** — no instrument (§7). This is a missing instrument, not a missing run.
* **T and N at tiers 120 and 300** — both are registered and measured at tier 40 only. The plan's step 5 says
  to run them; MP-E8 ran them at the calibration tier and never carried them to scale, so G2's "plus the
  teach-arm control and noise floor" is satisfied at tier 40 and **unevidenced at 120 and 300**.
  **Cost if the PI buys it: roughly 2.7 hours of exclusive wall-clock for three noise-floor clones at tier
  300** (each clone is a full three-arm, three-depth bench run at ~54 min, the measured tier-300 figure),
  plus about 1.2 h for the three at tier 120. It is left unrun here because it cannot move a verdict: H1's
  arm B clause already fails on the least favourable seed at both required tiers, and H2's two clauses are
  settled by attribution and by the clause-2 comparison. Spending 3.9 hours of machine time on a control that
  cannot change an outcome is a decision to make deliberately, so it is stated with its price rather than
  run quietly or dropped quietly.
* **Arm C's paraphrase-recognition slice at tier 40** — 0 near-miss rows exist there by construction (the tier-40
  distractor population is 108 rows with no near-miss), so that figure has no population at that tier.
* **H3** — no instrument, by ruling (§6).

**Outcome.** G2 does not pass, and MP-E8 is not stalled: the artifacts exist, the abort was executed as a
withdrawal, and the plan says both outcomes define paper 1. What paper 1 is now built on is the finding in §3 —
that at 120 and 300 items the sequential baseline never held the knowledge the duel's hypotheses assume it
holds, and that the arm which *does* hold it lost two named taught items across a restart at tier 300.

## 10. Open decisions put to the PI

| id | question | agent's recommendation |
|---|---|---|
| D-MPE8-05 | R13's tolerance cells are incomplete (1 of 6 runs flipped outside them) | widen by measurement, not by argument |
| D-MPE8-10 | R13's cells do not cover the observed restart-phase instability | register a restart-phase cell class before any further tier-300 claim |
| D-MPE8-11 | H2 clause 2 is satisfiable by blanket refusal | register a companion specificity floor from the measured gate discrimination — but not by this agent, after the clause passed |

## 11. What this document does not do

It does not move a threshold, a margin, a tolerance cell or a tier. It does not drop tier 120 because tier 120
came out awkward, or drop the updates half of H4 because there is no counter. It does not destroy the aborted
claim's artifacts, and it does not read arm B's flat curve as evidence for arm A: §3 is the reason those two
are not the same finding. Every amendment it cites is in
`experiments/MP-E8/registration.json:registration_amendments`, and the seal
(`tools/registration_seal.py --check`) anchors each artifact to the commit that contains its bytes.
