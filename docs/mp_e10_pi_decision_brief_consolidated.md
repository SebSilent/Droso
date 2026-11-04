# Decision brief: the consolidated PI list, as measured

One pass, every item the program is holding for a ruling. Shape follows
`docs/mp_e10_g3_decision_brief.md`, which got three rulings in one delivery: for each item -- the measured
state with the artifact it comes from, what the options actually are, what each costs in machine time, and
what stays blocked while it is unanswered.

**Nothing here is ruled.** Every recommendation quoted is the one already recorded in a ledger by the agent,
marked as such. The agent does not decide admissibility of its own evidence, does not widen a tolerance after
seeing which cells disagree, and does not choose between three readings of its own registered quantity.

---

## GATE STATUS, AS MEASURED

| gate | state | the measurement behind the word |
|---|---|---|
| **G0-prime** | **CLOSED, conditional** | The conditional is the gate's own wording: the organ works, the rhythm is real, and the closure stands on a corpus whose size is the caveat. Nothing moved today. |
| **G1** | **NOT MET** | The tell is verified on the frozen and guarded batteries (19/24 and 4/4) and off on paraphrase (0/14) and on the ELECTRIC path. What G1 lacks is the missing item categories -- coverage arithmetic -- not a mechanism. |
| **G2** | **evidence complete, and G2 DOES NOT PASS** | H1 fails at both required tiers (arm B's clause fails on the least favourable seed at 120 and 300) and the tier-300 drop has the **wrong sign**. H4 closes it; H2 is partial (clause 2 holds on counts, clause 1 fails at 3/5); H3 has no instrument. |
| **G3** | **open, and H3 is VOID at its own tier** | `experiments/MP-E10/results/replay_tier300_summary.json`: interference measured **0.0000 pp at every depth** against the operative 2.0 pp margin -- and the saturation guard voided depths 2 and 3, so the clause is unmet at tier 300 on named missing measurements, not on an adverse number. Scoreable only at depth 1. |
| **G4, G5, G6** | **not started** | No registration, no run. |

Covering suite, as published: **1,348 collected / 1,348 executed / 4 failures / 0 errors / 6 skipped, rc 1,
802.51 s** at `git_head cb61fc0`
(`experiments/MP-E10/results/suite_manifest_post_tier300_closure.json`). The four failures all name one path
and are the sealed-before-produced trap; they pass alone at the post-stamp tree. The badge is amber because
the covering run exited 1, and no greener total is claimed for it.

Seal state at delivery: all five ledgers stamped at anchor `ba99a70`, **180 sealed files each**,
`git_dirty_sealed` empty in every one, read back from the committed bytes.

---

## PART A -- can H3 be scored at the tier H3 is registered for?

These four items are one question wearing four names. Tier 300 is H3's tier by registration. Today it returns
0.0000 pp interference, which is a pass on the margin, and void on the guard.

### A1. The saturation guard: H3 void at tier-300 depths 2 and 3

**Measured state.** `replay_tier300_summary.json` `per_pass_ceiling_guard`:
- depth 1: `void_for_H3 = false`, 2 of 2 registered passes run, 0 entries pushed to the 4.0 ceiling,
  predicted max accumulation 0.70.
- depth 2: **`void_for_H3 = true`**, only 1 of 2 registered passes run, **72 entries pushed to the ceiling on
  the first pass**, predicted max accumulation 0.35.
- depth 3: **`void_for_H3 = true`**, 1 of 2 passes, **156 entries already at ceiling before the pass and 252
  pushed during it**.

The recorded consequence: `SUCCESSOR_FLOOR` and `SUCCESSOR_MARGIN` are **absolute** gates, so a readout taken
past the ceiling cannot be trusted -- "an unchanged tally from a run whose gates are saturated is not a null
result; it is a result that was not obtainable."

**This item is not yet a ledger decision entry.** It exists in the verdict artifact and in D-MPE10-05's
pre-registered guard, but there is no `D-MPE10-1x` key for it in `open_decisions_for_PI`. Naming that gap
rather than filing it quietly: the guard was registered to make a ceiling-limited configuration void, it
fired, and the question it raises -- whether H3 can be scored at its own tier at all under the registered
rule -- has no home in the ledger.

**The options.**
1. Re-run tier 300 with a replay gain or ceiling that keeps entries below 4.0 at depths 2 and 3, so the guard
   does not fire and the clause is scoreable at all three depths. This is an organ-parameter change against a
   pre-registered guard, so it needs a ruling before the run, not after.
2. Accept **depth 1 only** and register explicitly that H3 at tier 300 is scored on a single depth. The
   artifact already supports this reading; it is the cheapest honest option.
3. Keep the guard and let H3 stand void at tier 300, reporting the 0.0000 pp as unobtainable rather than as a
   pass. This is the strictest reading of the guard's own words.
4. Re-scope H3's registered tier to 120, where the guard does not fire, and say so in the hypothesis text.

**What each costs.** Option 1 is the only one that buys machine time: tier-300 arm A measured **53.65 min**
against a registered projection of **60.2 min** (-10.88%), plus the replay passes at roughly **1.3 h+ serial
per replay configuration** as priced in the G3 brief. Options 2, 3 and 4 cost **zero**; they are wording.

**What stays blocked while open.** H3 itself, and therefore G3's `go_if` = "H1-H4 hold". The 0.0000 pp figure
may not be quoted as satisfying the clause until one of these is chosen.

---

### A2. D-MPE10-11 -- tier 300 breaches the invention floor in every run on disk

**Measured state.** Invention counts over the full **9,414** graded asks: MP-E8's sealed baseline **91**
(0.97%), replay ON **92** (0.98%), replay-OFF control **100** (1.06%). The breach is present in all three,
control included, and is therefore not a treatment effect. Registered in AMD-MPE10-06; the tallies come from
`summary.learn[depth][phase]`, which counts every graded ask and does not depend on the row-key defect fixed
in AMD-MPE10-09.

**The options, as recorded in the ledger.**
1. Rule tier 300 admissible for H1/H2/H3 with the breach named in every quote, on the ground that it is
   tier-level and constant across arms and so cannot bias a between-arm comparison.
2. Rule tier 300 **not admissible** until the breach is understood, and spend a run classifying the 100
   invented rows -- which shapes are involved, and whether they are the distractor set or the taught set.
3. Re-scope tier 300's claims to the ones the breach cannot touch (organ-side: `||w||_F`, boundedness, read
   direction) and leave behavioural claims at tier 120, where the floor holds.

**What each costs.** Option 2's classification is **read-only against artifacts already on disk**
(`replay_tier300_armA.json` carries the rows), so it costs analysis time and **no timed bench run**; a fresh
replicate to bound the count would be ~54 min. Options 1 and 3 cost zero machine time.

**Recorded agent recommendation** (quoted, not endorsed): option 2 before the others, "because nothing on this
machine says yet WHAT they are."

**What stays blocked while open.** The admissibility of every tier-300 behavioural number, including the H3
verdict in A1 and the migration attribution in A4.

---

### A3. D-MPE10-10 -- which phase is H3's registered basis

**Measured state.** H3's taught-set triple has **three phase readings** at tier 300 and the registration does
not name the basis. In the replayed run: `live` (291, 546, 785), `restarted` (292, 548, 784), `reasked`
(283, 520, 757). At tier 120 `live` and `restarted` are the same triple (122, 239, 347), so the protocol never
had to choose and the ambiguity was never exercised.

**The options.** (1) register `restarted` as the basis, since the claim is about post-restart retention;
(2) register `live`, which makes the word "retention" do work the measurement does not do; (3) register both
as a named pair and require every quote to carry its phase label.

**What each costs.** **Zero machine time.** All three triples are already measured and on disk; option 1's own
text notes both read 0.0000 pp today, so **no verdict moves** whichever is chosen.

**Recorded agent recommendation:** option 3 for the record and option 1 for the scored quantity.

**What stays blocked while open.** Every quotation of an H3 number, because the number is not yet unique.

---

### A4. D-MPE10-09 -- the R6 guarded battery has no tier-300 instrument

**Measured state.** The four R6 guarded probes -- `P-numeral-final`, `R-count-moon`, `R-disj-reversed`,
`R-order-ofthe` -- **cannot be scored on the tier-300 run by any instrument on this machine**. They are turns
inside selection scripts (`tools/scripts_selection.json`), graded only by `tools/mp_e9_battery.py` from a
`run_generation` journal. The tier-300 run is the learn bench: its rows carry no probe field and no pass
field, it writes no journal, its curriculum contains none of the four asks, and `run_generation`'s `--tier`
means frozen/probe/open -- a battery axis, not a curriculum axis. H3's clause says retention holds **at the
invariant**, so the cell is required and empty.

**The options.** (1) give `run_generation` a curriculum input so tier-300 material can be taught through the
selection pipeline and the battery graded on the resulting journal -- a new pipeline input. (2) add the four
probes to the tier-300 curriculum manifest -- which changes `curriculum_sha256`, the identity every sealed
tier-300 artifact is keyed to, and breaks the comparison the verdict is computed against.

**What each costs.** A ruling costs zero. Route 1 costs a pipeline change plus the battery run over a tier-300
journal; **no measured cost exists for it** and this brief will not invent one. Route 2 costs no machine time
and buys a broken comparison. If neither: the recorded consequence is that H3's clause at tier 300 keeps an
**unmeasured floor**, and the write-up must say so in the same sentence as the 0.0000 pp.

**Recorded agent recommendation:** route 1, and only if the PI wants an R6 floor at scale -- route 2 "trades a
sealed baseline for a number, which is the trade this program has refused three times over."

**What stays blocked while open.** R6's "regression is a hard reject" at tier 300, and the completeness of the
tier-300 verdict in A1.

---

### A5. D-MPE10-04 condition 3 -- the margin applied at tier 300 is derived from tier-40 noise

**Measured state.** `margin_applied_pp = 2.0`, `margin_as_first_registered_pp = 5.0` (both carried in the
verdict artifact; the ruling's 2.0 governs, the 5.0 is retained as history). The 2.0 pp rests on tier-40 data:
clone noise 11 rows of 3,672 = **0.2996 pp**, rule-of-three bound **1.887 pp** from 0 regressions in 159
tier-40 exposures. Condition 3 asked for the clone-noise input to be **re-measured at the tier being judged**.
Its recorded status is **"UNSPENT -- declined for cost, not forgotten."**

**The options.** Buy the tier-300 three-clone set and re-derive the margin by amendment; or leave it unspent
and require every quote of the 2.0 pp at tier 300 to state that its basis is tier-40.

**What each costs.** The three-clone set is **~2.7 h** of exclusive wall-clock (each clone is a full
three-arm, three-depth bench run at ~54 min measured). This is the **same** run that would close G2's missing
tier-300 noise floor (B3 below), so one purchase can serve two items. Leaving it unspent costs zero.

**What stays blocked while open.** Nothing gates on it today -- 0.0000 pp is inside both 2.0 and 5.0 pp. It
binds the moment an interference result lands near the margin: a 3.x pp result passes the stale number and
fails the ruling, and on tier-40 noise neither is decidable at tier 300.

---

## PART B -- G2's loose ends, and the ordering question

### B1. D-MPE8-10 -- R13's tolerance cells do not cover the observed tier-300 instability

**Measured state.** Two runs of the same program at tier 300 show **zero** disagreement in the cells R13
tolerates (`learn/1/reasked`, `learn/1/restarted`) and **208 field differences elsewhere**, concentrated at
depths 2 and 3 and present in the `live` phase too. Evidence:
`experiments/MP-E8/results/armA_tier300_rerun_c3_diff.json`, `armA_tier300_rerun.json`,
`armA_tier300_curriculum.json`. Nothing has been widened; AMD-MPE8-13 names both artifacts.

**The options.** (1) register the spread as a **named quantity with its own cell**, and quote tier-300 arm A
aggregates beside it. (2) widen R13's tolerance list. (3) run tier 300 as **replicates**, the way arm B is
run. (4) leave it: quote tier-300 aggregates with the instability named each time.

**What each costs.** (1) and (4) cost **zero** -- the spread is computable from artifacts on disk. (2) costs
zero machine time and is the one the agent may not do: the tolerance list is part of the pre-registered
contract, and editing it after seeing which cells disagree is selecting the tolerance on the data it will be
used to excuse. (3) costs **~54 min per replicate** at tier 300 (measured precedent 53.65 min).

**Recorded agent recommendation:** option 1, because widening R13 "would excuse rows in cells whose
disagreement has no mechanism behind it."

**What stays blocked while open.** A defensible uncertainty band on every tier-300 arm A aggregate, including
the numbers A1 and A2 rest on.

### B2. D-MPE8-11 -- H2 clause 2 is satisfiable by blanket refusal

**Measured state.** Arm C satisfies H2's second clause at tiers 120 and 300 **while producing zero correct
answers at every tier**. The selectivity data that would set a companion floor already exists: the gate passes
taught asks **7.68 to 29.14 pp** more often than never-taught ones. Evidence:
`experiments/MP-E8/results/armC_h2_clause2_and_retrieval_empty.json`, `armC_tier300_curriculum.json`. Clause 2
is recorded as measured PASS at 120 and 300 with this limitation attached to the record.

**The options.** (1) register a companion **specificity floor** before arm C is cited for anything. (2) accept
clause 2 as written, and record that a system which never answers anything passes a refusal clause. (3) rewrite
clause 2, which is a plan amendment rather than a ruling.

**What each costs.** **Zero machine time** for (1) and (2) -- the discrimination is already measured and on
disk. (3) costs a re-seal of the hypothesis text.

**Recorded agent recommendation:** option 1, with the floor set from the existing 7.68-29.14 pp spread, "which
is a measured discrimination and not a chosen threshold."

**What stays blocked while open.** Any use of arm C as evidence, and H2 clause 2's meaning.

### B3. G2's T and N at tiers 120 and 300 -- named missing, not run

**Measured state.** `arms.T` and `arms.N` are registered and measured **at tier 40 only**. Neither holds a
120 or 300 field -- verified structurally, not inferred from prose. Recorded status: **"NOT RUN, and named
missing rather than glossed"** (AMD-MPE8-16).

**The options.** Buy the clones; or close G2 accepting that its time/size controls exist at one tier.

**What each costs.** **~2.7 h** for three noise-floor clones at tier 300 + **~1.2 h** at tier 120 = **~3.9 h**
of exclusive wall-clock. The ledger's own reason for not running them: it "cannot change H1's or H2's measured
outcome," so this is a completeness purchase, not a verdict-changing one. **The tier-300 half is the same run
A5 needs**, so buying both together costs 3.9 h, not 6.6 h.

**What stays blocked while open.** G2's wording names them; the gap is on the record either way.

### B4. D-MPE10-05_G2_is_not_closed -- the ordering question, still open and still numbered twice

**Measured state.** The ledger carries `D-MPE10-05` **twice**: `-05_G2_is_not_closed` (may MP-E10 run before
G2 closes) and `-05_replay_write_path` (which mechanism replay uses). Only the write path is ruled (option B,
2026-08-10). The ordering question is **still open**, and the collision is recorded in
`identifier_collision_recorded` rather than merged away. The plan's own ordering says "the duel precedes the
mouth because its tiers define the scale the mouth must consolidate" -- and MP-E10 has run tier 120 and tier
300 while G2 does not pass.

**The options.** (1) ratify retrospectively: G3's runs were legitimate because G2's evidence was complete even
though G2 does not pass. (2) hold: no further MP-E10 scoring until G2 is closed or explicitly waived. (3)
separate the identifiers properly so one number no longer carries two questions.

**What each costs.** **Zero machine time** for all three. Option 2 forgoes whatever MP-E10 would run next.

**What stays blocked while open.** The legitimacy of every MP-E10 figure already taken, and the next MP-E10
run.

---

## PART C -- hygiene items that are not about any hypothesis

### C1. Licensed-absence intermittence -- open, named, not closed

**Measured state.** `tests/test_electric_fragment_guard.py::test_the_guard_returns_the_licensed_absence_instead_of_the_fragment`
fails intermittently: `assert "asking" in str(out.get("reason"))` got `'nothing he remembers has that shape'`.
Two hypotheses were tested and **refuted**: ordering (no ordering plugin exists -- pytest 9.1.1, no
pytest-randomly, no pytest-order) and `PYTHONHASHSEED` alone (seed 6 failed once, the identical command failed
to reproduce next attempt, and a bare-interpreter child under all eight seeds named the correct absence every
time). The **safety property held in every observation**: `spoken = False`, source never the arbiter head.
Only which licensed absence he *names* moved. It lives at `organs/neural_language.py:5401` (the string) and
`:5439` (the ask-licensed-absence branch); `_arbitrate_shape` at `:4129` iterates `hits`, a list, so the flip
is upstream of the arbiter, in how candidate hits are built (`hits = kept`, `:5387`). Not located further.

**Why the agent cannot just fix it.** The fix **edits the answer path, which published evidence quotes**. It
needs a ruling and a re-baseline, not a unilateral edit.

**The options.** (1) authorise the targeted hunt: run the file N times under varied seeds and contexts to
estimate the flip rate, then make hit construction order-independent, then re-baseline. (2) leave it named and
keep the pinned test skipping with its reason recorded -- a test that asserts a reproduction which does not
hold manufactures a red or a green on demand. (3) close it as "safety property holds, cosmetic string varies,"
which is a characterisation, not a fix.

**What each costs.** The unit cost is measured: **`tests/test_electric_fragment_guard.py` alone runs in 12.6 s**
(this pass, as a read of the harness cost -- not a bench run). A 200-repetition hunt is therefore roughly
**42 minutes**, and each re-baseline is one covering suite at the measured **802.51 s (~13.4 min)**. Option 2
costs zero.

**Blast radius, as recorded:** any sealed evidence that quotes a `reason` string from the answer path; the
trustworthiness of any "0 failures" manifest over the full suite; H1/H2/H3 scored runs, which all read this
path. It does **not** gate H3 -- the flip is in `reason`, which R13 tolerates.

### C2. D-MPE9-05 -- promote the bound to BASE, and the entry has no `status` field

**Measured state.** `open_decisions_for_pi.5_promote_the_bound_to_BASE_D-MPE9-05` is a dict with `question`,
`measured_state`, `precondition_before_any_promotion`, `registered_at`, `scope_note` -- and **no `status`
field at all**. That is a record-keeping defect with a consequence: the stale-status guard can only correct
entries that declare a status, so this one cannot be caught if it goes stale. `BASE_ATTRS` is 3 attributes
(`ELECTRIC_TEACH`, `ELECTRIC_ANSWER`, `ABSENCE_INVENTORY`); both harnesses were booted and the flags read
back; the battery applies 0 of the candidate attributes on the battery path.

**The options.** (P-1) move `ELECTRIC_ARBITER_HEAD_BOUND` from CANDIDATE to BASE. (P-2) move it to the class
default. (P-3) leave it CANDIDATE. Plus, separately: **add a `status` field to this entry**, which is a
formatting correction the agent could make -- and has not, because touching the entry to add a field is one
edit too many without a ruling on the question it records.

**What each costs.** P-1/P-2 need an inertness proof and a re-baseline of the MP-E9 batteries -- the same
shape as the D-MPE8 flag work; **no measured cost exists** for the MP-E9 path and this brief will not invent
one. P-3 costs zero.

**What stays blocked while open.** Nothing that gates today; it is a question about what the default
configuration *is*.

### C3. requirements.txt pinning -- what the ledgers say versus what the file says

**Measured state.** Two ledger strings carry this item, both bare strings with **no status field**:
`G0-prime environment.requirements_txt` ("EXISTS and is UNPINNED: it named six packages...") and
`MP-E9 open_decisions_for_pi.4_requirements_txt_pinning` ("STILL OPEN. requirements.txt names six packages
with NO version pins... plus pypdf"). **Both are stale about the file as it now stands**: `torch==2.15.0+cpu`
**is pinned**, at `requirements.txt` line 23, committed in `37759d0`. The claim is true of the original six
packages and false of the file.

**The options.** (1) pin the six named packages and say what to do with the installed-but-unused ones.
(2) leave them unpinned and correct the two ledger strings to state that torch is now pinned, so the record
matches the file. (3) both.

**What each costs.** **Zero machine time.** Option 1 triggers a re-lock and a re-seal of the environment
block; the new MP-E8 lock (38 packages, 9 added, 0 removed, numpy/scipy untouched) is the precedent for what
that diff looks like.

**What stays blocked while open.** Nothing gates on it. It is a reproducibility claim, and right now the
ledger understates the pinning that exists -- which is the safer direction to be wrong in, but still wrong.

---

## PART D -- MP-E12, and the one item no ruling can move

### D1. MP-E12a cannot begin, and the reason is not a decision

**Measured state.** `MP-E12 status`: "REGISTERED BEFORE ANY RUN, per rule R2. No donor has been read. **The
weights are not on this machine.**" `pre_registered_failure_modes.named_external_blocker` records the machine
state, what is blocked and what must arrive -- and has **no `status` field**. What must arrive: GPT-2 124M
public weights (n_embd 768, n_layer 12, n_head 12, d_head 64, n_positions 1024, vocab 50257, MLP inner 3072,
`wte` tied to the unembedding) at `experiments/MP-E12/donor/gpt2/`, or a path recorded in the run's
environment block.

**What is NOT blocked:** the registration, the three extractions, their unit tests, the operation counts, the
schema, the threshold, and the benchmark's operation-count side.

**What is blocked:** B.6 item 1 against the real donor, every association figure, and therefore all of
MP-E12b and MP-E12c.

**What it costs.** No ruling, no budget and no session time changes it. The machine cost is **zero until the
weights arrive**, and undefined after.

### D2. D-MPE12-01 through -04 -- four open decisions, all downstream of D1

All four are bare strings with **no status field**, in a block keyed `open_decisions` (not
`open_decisions_for_pi` as in the other four ledgers -- the casing is not uniform across the program).

- **-01**: whether the sealed operation-count log from the synthetic donor satisfies B.6 item 1's "log and seal
  operation counts", or the log must be regenerated against the real donor.
- **-02**: how the energy estimate is produced. The plan names wall-clock, operation count **and energy
  estimate**; this repository has no energy instrument.
- **-03**: the probe list for the real donor (which tokens, how many, chosen how). It **cannot** be fixed
  against an absent model and must not be chosen after the weights arrive.
- **-04**: whether MP-E12b (the compiler) may be built against the synthetic graph before the real graph
  exists. Not started: stage b mutates connectome objects.

**What each costs.** -01 and -02 are definition questions: **zero machine time** to rule, and -02 may need an
instrument that does not exist. -03 is unanswerable until D1 resolves. -04 is a build decision whose cost is
the stage-b work itself.

**What stays blocked while open.** MP-E12b and MP-E12c, which are also blocked by D1 regardless.

---

## IF EVERYTHING IS BOUGHT: the machine-time total

| purchase | hours | note |
|---|---|---|
| Tier-300 three-clone noise floor | ~2.7 | serves **both** A5 (margin re-derivation) and B3 (G2's N at 300) |
| Tier-120 clones | ~1.2 | B3 |
| Tier-300 arm A re-run under a non-saturating gain | ~0.9 + ~1.3 per replay config | A1 option 1; 53.65 min measured, 60.2 min projected |
| Tier-300 replicate for D-MPE8-10 option 3 | ~0.9 each | B1 |
| Intermittence hunt, 200 reps | ~0.7 | measured unit cost 12.6 s |
| Each re-baseline (covering suite) | ~0.22 | measured 802.51 s |
| Tier-300 classification of the 100 invented rows | 0 | read-only from artifacts on disk |
| Every ruling itself | 0 | all of A2, A3, A4 (the ruling), B1's options 1/2/4, B2, B4, C2's P-3, C3, D2 |

**~6.9 h of exclusive machine time buys everything that is buyable**, and the largest single item serves two
open questions. The zero-cost rows are where the actual decisions are: A1, A2, A3, A4, B1, B2, B4, C1's
authorisation, C2, C3.

---

## What is NOT in this brief, deliberately

- **No figure from the superseded migration artifacts.** Since AMD-MPE10-09, the governing row-migration
  numbers are the five `*_row_migration_keyfix.json` artifacts, which compare **every** graded ask: 251 / 302 /
  111 of 9,414 at tier 300 and 66 / 58 of 3,744 at tier 120. The un-suffixed five remain sealed and unmodified
  and are superseded by reference under R5. The attribution conclusion survives the fix -- replay OFF moves
  more rows than replay ON (302 vs 251, 51 rows, 0.54 pp) on the same denominator, and the matched pair's
  transitions are near-symmetric (41 vs 32, 20 vs 13, 3 vs 3, with only 2 of 111 rows one-directional).
- **Nothing from MP-E12's synthetic donor is quoted as a real-donor figure.**
- **No MP-E11, MP-E12 or MP-E13 work has started**, and nothing here schedules it.
- **No item is ruled.** The recorded agent recommendations are quoted because they are in the ledger, not
  because the agent has settled anything. Where a cost is not measured, this brief says so instead of
  estimating.
- **The `||w||_F` and read-direction obligations (D-MPE10-06, -08) at tier 300** are named absent in the
  verdict artifact and were closed for tier 300 by `tier300_named_measurements_closure.json`; where they remain
  absent from the *summary* artifact, that is recorded there rather than papered over here.
