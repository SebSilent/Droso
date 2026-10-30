# Selection design: a genome, a tuple, and a battery wide enough to select on

Written before `tools/run_generation.py` was run. This is the contract for the
generational harness; every later change to it needs a dated entry at the bottom.

Scope of this step: build the instrument. No multi-brain run, no breeding, no
mutation, no culling, and no edit to `connectome/`, `organs/`, `core/` or
`world/`. The only files this step adds are `tools/run_generation.py`,
`tools/scripts_selection.json`, `tools/selection_baseline.json` (written by the
harness), `tests/test_selection_harness.py` and this document.

## 0. What the previous selection work measured, and why this is not it

Three things are on the record in `docs/archive/experiment_log.md`, and each one
is a reason this harness is shaped the way it is.

1. **The composite had its ceiling on the incumbent's first neighbour.** The
   selection-lever run varied only how parents were chosen, over four conditions
   and five seeds, and improved nothing anywhere. The surface was then enumerated
   whole: `MAX IN SPACE 0.62500`, which is exactly what generation 1 already held.
   Selection was not too weak; there was nothing above it.
2. **The winner overfitted the material it was scored on.** The additive redesign
   bred a weighted head rule whose modifier class was closed at
   `{old, copper, heavy}`. Landed in the organ it named `small` as the head of
   `the small brass bell` and failed `tests/test_shape_filler_position.py`. The
   gate order caught it — pytest first, so the 24 was never run — but the rule had
   been selected as a winner before anyone found out.
3. **A shim scored the absence of a guard as capability.** `tools/_genome_patch.py`
   replaced `NeuralLanguage._shape_matches` and, where the organ returned `None`,
   returned the fly's filler instead. That produced 7/24. The instrument was fixed
   to let a veto stay a veto and the re-score came back 6/24, the organ baseline;
   the 7/24 was withdrawn.

So: no weighted sum, no synthetic component standing in for the real path, and no
patching. The three rules below are the whole design.

## 1. The genome

A genome is a JSON object with three parts. `genome_id` is the sha256 of the
canonical `genes` block, truncated to 12 hex — **genes only**, because provenance
describes the brain a genome ran on and changes when the lived state changes, so
hashing it would give one behaviour two ids and break the parent chain.

```
{"schema": 1,
 "genome_id": "abffa2b7f101",
 "genes": {"substrate": {...}, "plasticity": {...}, "decision": {...}, "answer": {...}},
 "provenance": {...}}
```

### 1.1 The line between a gene and teaching history

**A gene is a scalar the code sets once at construction and never restores from
persisted state.** That is the whole criterion, and it is not taste.

`social_drive` is a number sitting on the language organ, and it moves the
`gating` failure stage, so it looks like the most interesting gene in the file. It
is not a gene: `load_state()` writes it back
(`organs/neural_language.py:4419`), so a value set on it would not survive a
restart and could not be inherited. It is a mood the animal is in, not a
parameter the animal was built with. Everything on that side of the line is
**teaching history**, and teaching history is sealed by hash and never mutated.

This is the answer to "teaching history in the genome": it is in the genome
*record*, as `provenance.teaching_history`, and it is explicitly **not selectable
in this step**. Making it selectable means breeding on accumulated experience,
which is the population-and-merge question the README already marks unresolved.

### 1.2 The four gene blocks

| block | genes | where they live | mutable here |
|---|---|---|---|
| `substrate` | `control`, `seed`, `row_gain`, `n_actions` | `build_core_graph()` arguments | **no** — build-time |
| `plasticity` | the 14 `CoreParams` fields: `sub_steps`, `leak`, `tau_e`, `lr`, `gamma`, `weight_decay`, `w_cap`, `hysteresis`, `epsilon`, `epsilon_floor`, `epsilon_decay`, `temperature`, `temperature_decay`, `input_gain` | `engine.static.p` | yes |
| `decision` | `n_input_kc`, `k_code`, `code_seed` (`HybridEngineParams`); `engine_seed`, `ratecore_seed` | `engine.params`, `engine.rng`, `engine.static.rng` | seeds yes, params **no** — build-time |
| `answer` | instance: `ANSWER_COVERAGE_FLOOR`, `reply_threshold`, `reply_drive_min`, `max_sentence_words`, `speech_temperature`, `phrase_threshold`. module: `FRESH_TAU_S`, `FRESH_FLOOR_S`, `SAN_ROW_CAP`, `SAN_TOP_K`, `HEBB_LR`, `SAN_DECAY_PER_S` | `agent.language`, `organs.neural_language` | yes |

The base genome, snapshotted from a built brain at `8af3ed9`
(`state/selection/base_genome.json`, `genome_id abffa2b7f101`), carries the
committed values: coverage floor 0.6, reply threshold 0.55, reply drive min 0.30,
fresh tau 3600 s over a 300 s floor, SAN row cap 1024, top-k 512, Hebbian lr 0.10,
SAN decay 0.995/s; `lr` 3.0, `gamma` 0.9, `weight_decay` 3.2e-5, `epsilon` 0.15
over a 0.02 floor, `temperature` 0.02, `input_gain` 2.0, 10 sub-steps.

Adding a gene to this table is a logged change at the bottom of this file, not an
edit made because a run wants it.

### 1.3 Two gene classes, and why the build-time one is frozen

**Post-build genes** are applied by setting an attribute on the built brain.
Nothing is replaced, nothing is wrapped, no method is patched.

**Build-time genes** cannot be. `build_house_agent` constructs the engine itself
(`ReasoningAgent.__init__` → `HybridEngine(graph=_banc_graph())`), and
`_banc_graph()` calls `build_core_graph()` with default arguments and caches the
result in a module global. There are exactly two ways to give a brain a different
carve: edit `world/connectome_house.py` or `world/reasoning_agent.py` (core code,
out of scope by instruction), or pre-seed `world.reasoning_agent._BANC_GRAPH` from
a tool before the build. The second is a tool reaching into a module global to
change what the organ runs on — the same shape of move as `_genome_patch.py`, and
this project has already had to withdraw a number that produced.

So build-time genes are **recorded and verified, and refused if they differ from
base**. `apply_genome` returns them in `refused` and the ask is scored
`stage=genome_refused` rather than scored at all. Silently evaluating a genome
whose substrate genes were never applied is the same dishonesty as the shim, only
quieter.

The route that unlocks them later is named here so it is a decision rather than an
accident: pass an `engine=` through `build_house_agent`, in core code, in a step
whose whole purpose is that change, with the read-back verification below still
firing.

**A finding that empties half the obvious search space.** In `build_core_graph`,
`rng = np.random.default_rng(seed)` is constructed *inside* `if control:`. For the
experimental carve (`control=False`) the graph is a deterministic function of the
BANC tables and **`seed` does nothing**. A "substrate seed" gene only bites on a
degree-matched control brain. Anyone planning a substrate sweep should know that
before spending builds on it.

### 1.4 Birth values, not as-found values

`epsilon` and `temperature` are mutated in place on every decision
(`connectome/rate_core.py:119-120`): epsilon decays toward its floor, temperature
by its own factor. A genome that recorded what a lived core held would record a
value already partway to the floor, and two snapshots of the same brain would
disagree.

So `plasticity` genes are read from `CoreParams()` — the birth values, which is
what `RateCore.__init__` installs when no params are passed, and
`build_house_agent` passes none. The as-found values are recorded beside them in
`provenance.as_found`, together with `decisions`. Measured at snapshot:
`epsilon 0.15 == birth 0.15`, `temperature 0.02 == birth 0.02`, `decisions 0`.
That equality is a check, not a formality: if `as_found != birth`, something ran
decisions during construction and the birth-value assumption is false.

## 2. Apply, then verify, then score

Every gene is written and immediately read back through the same path. A gene that
reads back different is a `mismatch`; a build-time gene that differs from base is
a `refusal`. Either one fails the brain and it is **not scored**. The lineage row
carries `genome_verified`, which is true only if every ask in the line reported
its genome applied.

`shim_check()` runs before every build is scored and asserts that
`NeuralLanguage._shape_matches` is still named `_shape_matches` and still owned by
`NeuralLanguage`, and that `_question_shape`, `_arbitrate_shape`, `answer` and
`respond` are likewise themselves. It raises rather than warns.

This is not paranoia about a file that might be deleted. `tools/_genome_patch.py`
is **present and tracked** in the current tree and installs its patch at import
time, while `docs/STATE.md:59` records it as "moved out of `tools/`". The doc is
wrong about the tree. The check is therefore on the object, not on the absence of
an import, and it runs 126 times in a three-line generation.

Module-level `answer` genes (`FRESH_TAU_S` and the rest) are read as globals
inside the organ's methods, so setting one is **process-wide**: it moves every
brain in the interpreter. They are saved and restored around each line, the row
records which ones were touched in `process_wide`, and a mutation run that touches
one should use `--isolate`. The clone run touches none of them to any effect,
because a clone's values are the values already there.

## 3. Fitness is a tuple

There is no scalar fitness and no weighted sum. Four terms, recorded separately:

| term | what it is | role in selection |
|---|---|---|
| `capability` | the frozen 24, independent mode: `passed`, `score`, `pass_set`, and every failure with its stage | the only term that can *raise* a line |
| `regression` | `frozen_lost` against the baseline pass set, plus the regression-guard probes: `probe_guard_lost`, `verdict` | a **hard constraint**, first in the key |
| `generalisation` | the paraphrase probes: `passed`, `score`, `seal`, `seal_matches_baseline` | **report and veto only.** Not a term in `select_key`. It can cost a line the win via `phrasing_fitted`; it can never earn one |
| `stages` | the failure-stage distribution over all asks | diagnostic. Never a score, never selected on |

```
select_key = [1 if not (frozen_lost or probe_guard_lost) else 0,
              frozen_passed,
              guarded_probe_passed]
```

compared lexicographically. The first element is a gate, not a weight: a line that
lost a frozen pass sorts below every line that did not, whatever else it gained.

**The third term is the guarded-probe count and NOT the paraphrase count.** The
first version of this harness used `paraphrase_passed` there, and a scenario run
before generation 1 showed what that means: a mutant whose only difference from the
control was one gained paraphrase probe became the survivor. That is selecting on
the generalisation tier, which is the one thing §4.4 forbids.

The reason is that a term in the key is a **gradient** — whatever it rewards,
selection will eventually find, and a held-out set that can reward is a held-out set
being trained on. So the paraphrase tier is permitted to influence an outcome in
exactly one direction: `phrasing_fitted` demotes, and nothing promotes. A set that
can only ever cost a line the win and never earn it one gives selection no reason to
fit it. The asymmetry is the mechanism, not a caveat.

**Why the stage distribution is in the tuple but not in the key.** It is the term
that says *where* a change acted, and a cut that moves `recall` failures into
`shape_arbiter` failures has done something real even at an unchanged score. But
selecting on it would mean preferring a genome because its failures are prettier,
and the log already has a retracted claim that came from reading a distribution as
a result. It is reported, per line, every generation.

**Why `generalisation` is a label, and what `phrasing_fitted` actually checks.**
Every paraphrase probe fails at base by construction — that is how it was
classified — so "lost paraphrase probes" is not a thing that can happen and a
guard phrased that way would never fire. The real risk is the other direction: a
mutant that lifts a frozen ask *without* lifting any rewording of it.

Each probe records the frozen ask it rewords, so the check is per-ask rather than
per-tier. For every frozen ask that moved from fail to pass, `phrasing_fitted()`
looks up the probes whose `rewords` is that ask; if there are any and none of them
passed, the row carries `phrasing_fitted:<ask>`. A mutant that fixes `what did i
tell you about before the kettle?` while both of its rewordings still fail has
fitted a phrasing. Under a weighted sum that trade is a number and someone will
eventually take it; as a label, section 3 makes the line ineligible to win.

Only gains are labelled. An ask that already passed at base has no paraphrase
obligation — the regression tier covers it — and an ask that still fails has
gained nothing to be suspicious of.

## 4. The eval set

Three tiers, and the split between the last two is **measured, not declared**.

### 4.1 Frozen: the 24, by reference

`tools/run_generation.py` reads `tools/scripts_heldout.json` at runtime. It does
not contain a copy. A copy is a second contract that can drift from the first, and
then "zero frozen passes lost" would be measured against whatever the copy said.

Seal `b9d0f2d83fbb7e78`. If that seal differs from the one in
`tools/selection_baseline.json`, the harness **refuses to run** — not warns. The
frozen pass set describes a suite; change the suite and the set means nothing.

Asks are scored in independent mode, one fresh build per ask with only its
preceding tells replayed, for the reason `heldout_eval` gives: nothing an earlier
ask did can move this number. Grading and stage attribution are **imported** from
`tools/heldout_eval.py` (`grade`, `stage_of`), not reimplemented, so a selection
row and a campaign row come off one checker and can be diffed. Ask ids use
`heldout_eval`'s own form, `script::ask`.

### 4.2 Probes: 18 rewordings, in `tools/scripts_selection.json`

Seal `6b6117e9e0a7c331`. Every probe is a rewording of one frozen ask: it shares
its parent script's tells **verbatim** and its parent's `expect` block
**verbatim**, so the only variable is the phrasing. Six groups, one per parent
script — 10 around the five current failures, 8 around behaviours that pass.

The five failures and what their probes vary:

| frozen ask (fails at) | probes | what is varied |
|---|---|---|
| `what did i tell you about before the kettle?` (recall) | `which thing did i mention earlier than the kettle?`, `what came before the kettle in what i said?` | `earlier` is in neither `ORDINAL_CUES` nor `COUNT_FIRST_CUES`; the second drops the record-verb frame and the `which` |
| `what is wet but not on the hook?` (shape_arbiter) | `which of them is wet and is not on the hook?`, `name the wet thing that is not on the hook` | no named alternative, so the disjunction path cannot fire; the second is an imperative, so no interrogative reaches role selection |
| `how many times does the bell turn?` (recall) | `how often does the bell turn?`, `the bell turns how often?` | neither `how many` nor a `COUNT_QUANTS` word; the second moves the interrogative phrase to the end |
| `what does the thing the frost bites hold?` (shape_arbiter) | `what is held by the thing the frost bites?`, `what does the bitten thing hold?` | passive, so the embedded-clause span the arbiter walks is gone; then a participle, so nothing in the question names `frost` or `latch` |
| `does the door hold the frost?` (gating) | `is the frost held by the door?`, `is it true that the door holds the frost?` | passive polar; then `is it true that`, which removes the do-support opener the record path tests `words[0]` against |

**Cue avoidance was done against the organ's own tables, read first.** A probe
that reused its parent's cue words would measure the cue table rather than the
behaviour, so the sets were read out of `organs/neural_language.py` before any
probe was written: `COUNT_QUANTS {times, things, objects, items}`,
`COUNT_FIRST_CUES` / `COUNT_LAST_CUES`, `ORDINAL_CUES {first, last}`,
`RECORD_VERBS {tell, told, mention, mentioned, say, said}`, `GLOSSARY_PAT`
(`which word did i (use|say) for the <cat>`), and the quantity path's `how many` /
`what count of` / `did any` openers. Each probe records the cue it avoided in its
own `why` field, so the avoidance is checkable rather than asserted.

Two probes were written to stay *inside* a mechanism (`what number of eggs is left
in the basket?`, on the claim that `what number of` is an opener the README names
for the quantity path; `which thing turns twice?`, keeping the shape parser's
route). **Both claims were falsified by the base measurement**: both failed at
`stage=recall` and both landed in the paraphrase set. The README names `what count
of X`, not `what number of`, and the shape parser is keyed to a literal `what`.

That is recorded rather than quietly corrected, because it is the clearest
available demonstration of why §4.3 splits by measurement instead of by
declaration. The probe file predicted "should pass, losing it is a regression";
the organ disagreed; the split followed the organ. Had the tiers been declared in
the file, a wrong guess by the author would have become a guard that a mutant
could be charged with breaking. The `why` text in `scripts_selection.json` still
carries the falsified prediction, because editing it would break the seal — the
correction lives here.

### 4.3 The split is a product of the clone run

No probe is labelled "paraphrase" or "regression" in the file. `--freeze-baseline`
reads generation 0 and splits by outcome:

- passed in **every** clone → `regression_pass_set`. It may only be lost.
- failed in **every** clone → `paraphrase_set`. It may only be gained.
- the clones disagreed → `probe_ambiguous`, in **neither** set.

An unstable pass is not a guard and an unstable fail is not a gap. Putting an
ambiguous probe in either tier would let the instrument's own noise be selected on,
which is the one thing a selection harness must not do.

The same rule applies to the frozen tier: `frozen_pass_set` is the **intersection**
across clones, and the asks that passed in some clones but not others are recorded
as `frozen_unstable`. The regression guard then charges a mutant only for asks the
instrument can actually hold.

### 4.4 Keeping the probes from becoming training targets

Three mechanisms, in increasing order of how much they cost to honour.

1. **Blindness.** No selection or mutation code reads `scripts_selection.json`.
   `run_generation.py` reads it to score and for nothing else. The step-6 mutation
   operator sees genome scalars; it never sees ask text, an `expect` block or a
   probe id.
2. **The seal.** The file's sha256 is written into the baseline and into every
   generation row. Editing a probe after seeing a result changes the seal, every
   later row carries `probe-seal-broken`, and the generalisation numbers stop being
   comparable to the baseline's. The edit is still possible; it is no longer
   invisible.
3. **Consumption.** This is the one that actually holds. A paraphrase set that has
   been used to *select* a genome is training material, whatever file it lives in.
   Hiding it does not change that. So: **the set in `scripts_selection.json` is
   one-shot.** The first generation that selects on it burns it, and a fresh set
   must be written — before the code, against the then-current failures, with its
   own cue-avoidance notes — before the next selection round. A generation run
   after that point without a fresh seal is a run selecting on its own training
   data and should be reported as one.

## 5. Reproducibility, and why the first run is three clones

The instrument is **not** deterministic by construction, and the design does not
claim it is. Two mechanisms, both in core code this step may not touch:

- `RateCore._decide_impl` **samples** the action: `rng.random() < epsilon` for a
  uniform choice, otherwise `rng.choice(cand, p=probs)`. The stream is seeded
  (`HybridEngine(seed=0)` → `RateCore(seed=0)`, and `engine_seed` /
  `ratecore_seed` are genes), but the *position* in the stream at any ask depends
  on how many decisions ran before it.
- `_reset_episode_impl` applies `weight_decay` over **wall-clock** elapsed seconds
  (`dt = now - _last_decay_t`, gated at 5 s), and SAN decay is `0.995` per real
  second gated to 10 s steps. A more loaded machine decays more between the same
  two turns. The same genome on two differently loaded machines is not the same
  experiment.

`heldout_eval.compare()` already documents the consequence: "the bar is
reproducible in aggregate and NOT in membership: 5/24 held across campaigns while
two asks left the pass set and two entered it, on an unchanged tree."

So step 5 is not a formality. **Three clones of one genome is the measurement of
the instrument's noise floor**, and three is the minimum that can interpret a
disagreement: with two lines a 1-1 split cannot be attributed to either, with
three a 2-1 split is identifiable as noise. Every line carries a byte-identical
genome including the decision seeds, so *any* difference between lines is the
instrument and not the animal.

The run reports both numbers rather than one: whether the score reproduced, and
whether the **membership** reproduced. A generation whose clones agree on the
score but not on the pass set has a noise floor that must be written into the
baseline before any mutant is judged against it.

Each row also records `seconds` per ask and per line, so a drift can be correlated
with timing instead of speculated about.

## 6. The lineage record

`state/selection/generation_N.jsonl`, one line per brain:

```
generation, line ("g0-1"), genome_id, parent_genome_id, operator,
genome            the genes, whole, in the row
genome_verified   every ask reported its genome applied
shim_clean        every build passed shim_check
provenance        git head + dirty flag, python, numpy, the two file seals,
                  substrate read-back, plastic synapse count, as_found vs birth,
                  and the sealed teaching history
fitness           the tuple of section 3, including both pass sets and every
                  failure with its stage, what was said and why it failed
asks, seconds
guard             live_files_untouched, and the list if not
```

The genome is **in the row**, not in a file the row points at. `fly_v2` printed its
winner and wrote nothing, so an outside check had to replay a whole run to recover
a genome; `verify_saved.py` exists only to close that gap. A generation file here
is self-contained: one line is enough to rebuild the brain and re-derive the
score.

`state/selection/generation_N_asks.jsonl` holds one row per ask as it lands, so a
killed run keeps its work. It is written under `state/sessions/_selection/` during
the run and published to `state/selection/` only **after** the state guard has
passed — `state/sessions/` is inside the guard's own exclusion list, so the
harness's incremental journal cannot be read as the harness damaging the state it
is protecting.

## 7. State safety

Every brain is built by `converse.build()`, which stops the heartbeat, growth,
learning and exposure threads, sets `learning_loop.read_only`, blocks the oracle
by removing its key, turns books off, turns the voice prosthesis off, and
re-points every persistence path into a session directory. The whole `state/` tree
is snapshotted before the generation and checked after; any moved file fails the
run and the failure is printed with the file list.

Session directories are removed per ask. `gc.collect()` runs after each build;
`tools/fly_population.py` measured a second concurrent house at +2426 MB, so lines
are evaluated serially in one process and never two brains at once.

Cost, measured: one independent ask is ~26 s, of which the build is ~15.7 s. The
battery is 42 asks (24 frozen + 18 probes), so one line is ~18 min and a
three-line generation is ~55 min. A whole generation exceeds a foreground shell
timeout — the log measured 24 asks at ~750 s against a 590 s cap — so generations
run as background jobs and journal as they go.

## 8. Step 6, pre-registered here and not implemented

Written before any mutant exists, so the operator cannot be chosen after seeing
what it would win.

**One operator.** A single-gene bounded perturbation: pick one gene from the
post-build whitelist, add `gauss(0, sigma)` with `sigma` small, clip to the gene's
declared bounds, change nothing else. The row's `operator` names the gene and the
delta, and `parent_genome_id` names the source. One gene per mutant, so a moved
ask is attributable to a named scalar rather than to a genome.

**Which gene first, and why it is that one.** `ANSWER_COVERAGE_FLOOR`, base 0.6,
sigma 0.05, bounds [0.45, 0.75]. Two of the five frozen failures are
`stage=recall`, which is the coverage floor refusing (`best_cov <
ANSWER_COVERAGE_FLOOR` in `answer()`), and a third is `stage=gating`. The gene is
on the causal path of three of the five failures **from the base**, which is the
property `fly_population.py`'s second rewrite lacked when a third of its mutants
changed nothing any component could see: "a gene that only matters in a context
the base is not in is not a gene."

**Prediction, stated before the run.** Lowering the floor converts some `recall`
refusals into answers. Some of those answers will be wrong, and the forbid-lists
exist to catch exactly that. So the prediction is **not** "the score rises". It
is: the stage distribution moves mass out of `recall` and into `shape_arbiter` /
`other` / passes, and the frozen count moves by at most one ask in either
direction. A run that moves `recall` failures nowhere has found the gene inert,
and inert is a result — the log books those as landed-and-verified with no
capability point claimed.

**Culling.** Cull the worst line by `select_key` only if the survivor loses zero
frozen passes and zero regression-guard probes. **If every mutant loses a frozen
pass, no line is culled**, and the generation records that the operator is
destructive at that sigma.

**The stall rule, adopted from the selection-lever run.** If the operator produces
nothing on any line: do not lower sigma, do not widen the whitelist, do not add
lines, and do not soften the guard to make a climb possible. Report the stall and
go back to the surface. A harness that can be tuned until it improves is not
measuring anything.

### The seed, declared before generation 1 was run

The pre-registration above fixes the gene, the base, the sigma and the bounds. It
does not fix the draw seed, which is a free parameter and therefore has to be
declared before the sample is inspected rather than after. **The rule is: the seed
is `--mut-seed`, default 1, and generation 1 runs seed 1.** No re-rolling.

Seed 1 was drawn and inspected with `--dry-run` before any evaluation, and it
produced three draws **all on the same side of the base**:

| line | draw | value |
|---|---|---|
| g1-2 | +0.064409 | 0.664409 |
| g1-3 | +0.072472 | 0.672472 |
| g1-4 | +0.003317 | 0.603317 |

With σ=0.05 and three draws, `P(all one side) = 2 × (1/2)³ = 25%`, so this is an
ordinary outcome of a small sample and not a suspicious one. But it has a
consequence that is stated here rather than after the numbers arrive: **generation
1 does not test the directional prediction above.** All three mutants *raise* the
floor, and the prediction is about *lowering* it.

What generation 1 does measure, and why it is still worth its 73 minutes:

- whether the floor is load-bearing **above** 0.6 — the reach pre-flight found a
  guarded frozen pass at 57% coverage that passes *by refusing*
  (`where did i say the scarf is?`), so a raised floor keeps it refusing, but any
  ask that currently answers with coverage in [0.60, 0.67) would be lost, and
  nothing recorded so far says whether such an ask exists;
- the control clone's re-measurement of the parent under today's conditions, which
  is the reference the mutants are ranked against;
- the mutation, lineage, movement and culling machinery end to end, which is this
  step's actual deliverable.

The three options that were considered and refused: re-rolling the seed until the
draws straddle (choosing a sample after seeing the sample); raising `--mutants` so
both sides are likely (the operator's n was fixed at 3 by the instruction); and
stratifying the draws (a different operator than the one pre-registered). The
lowering direction is generation 2's question, with its own seed declared the same
way, before its own run.

### What generation 2 is predicted to do, derived from generation 0's own data

`docs/evidence/coverage_floor_reach.py` reads the coverage percentage out of every
refusal reason in the generation-0 journal. Ten refusals carry one, at **34, 39, 42,
45, 46, 51, 51, 54, 55%** — and one *pass* carries one too, at **57%**:
`where did i say the scarf is?`, whose expect block is `require_refusal: true`, so it
passes **by refusing** and its refusal reason records the coverage that produced it.

That ordering is a structural fact about this battery, and it is awkward for the
pre-registered direction. `answer()` reports coverage rounded to a whole percent, so
"55%" is any `best_cov` in [0.545, 0.555) and "57%" is any in [0.565, 0.575). To
admit the 55% ask the floor must fall to ≤ 0.545; to keep the 57% ask refusing the
floor must stay above 0.565. **0.545 < 0.565, so no floor value separates them**:
any floor low enough to gain `what did i tell you about before the kettle?` is also
low enough to make `where did i say the scarf is?` answer, which fails its
`require_refusal` and its `forbid: ["hook"]`.

**Prediction for generation 2, written before it is run and falsifiable by it:** a
lowering draw below ~0.565 loses at least one frozen pass — the scarf invariant —
and is therefore **ineligible**, so the generation's outcome is `stall` rather than
`no_gain`. A lowering draw that stays in (0.55, 0.60] changes nothing at all and
gives `no_gain` again. There is no draw in the pre-registered bounds [0.45, 0.75]
that gains the target ask without losing the guard.

That is worth running anyway, for two reasons, and neither is to win: it tests
whether the regression guard actually catches a loss in the direction the operator
was designed for (so far it has only ever been exercised on lines that lost
nothing), and a confirmed stall here is evidence that **the coverage floor is not a
usable lever for the recall failures** — which redirects the next cut rather than
consuming it. If generation 2 instead gains the ask and keeps the guard, this
analysis is wrong and the rounding intervals above are the thing to re-check.

The general lesson is the one the harness was built to enforce: a gene's reach has
to be measured against *both* the failures it might fix and the passes it might
break, and the frozen battery already contains a pass sitting above the failure in
the same scalar's ordering. Nothing in the score alone would have shown that.

### Reach, measured before the run rather than after

`ANSWER_COVERAGE_FLOOR` was checked for reach against the generation-0 journal,
which already records the coverage percentage in every refusal reason. The ten
`recall` failures per line refused at **34%, 39%, 42%, 45%, 46%, 51%, 51%, 54%,
55%** (one further `recall` row is a reply-gate refusal with no coverage). So the
gene is not inert: a floor at 0.55 reaches the `before the kettle` ask, and the
σ=0.05 window [0.55, 0.65] contains exactly one frozen failure's coverage and one
guarded pass's. This is a reach measurement of the kind `fly_population.py` reports,
not a tuning input — σ was not changed after seeing it, and the stall rule above
forbids changing it after seeing the scores either.

**Landing is a separate step and is not this one.** A winning genome is a set of
scalars a tool applies at build time. It is **not** persisted into live state, so
nothing about the live animal changes when a generation finishes. Landing a winner
means changing a default in code or config, and it goes through the gate order the
log used when it refused the weighted rule: pytest (including
`test_shape_filler_position`), then the frozen 24 with zero passes lost, then the
eight guard scripts. A genome that wins here and is not landed has not changed
Droso, and the record must say so — "the gain did not transfer" is the failure this
project has already paid for once.

### Generation 1, measured

One control clone plus three mutants, 42 asks each, 168 builds, 78 minutes, one
process. `state/selection/generation_1.jsonl`, per-ask journal beside it, and the
rows as the run first wrote them kept at `generation_1_asrun.jsonl`.

| line | genome | floor | frozen | guarded | paraphrase | stages | key |
|---|---|---|---|---|---|---|---|
| g1-1 | `abffa2b7f101` | 0.6 (control) | 19/24 | 4/4 | 0/14 | recall 10, mouth 4, gating 3, shape_arbiter 2 | [1, 19, 4] |
| g1-2 | `fb6ca8c69a8b` | 0.664409 | 19/24 | 4/4 | 0/14 | identical | [1, 19, 4] |
| g1-3 | `3754cbb05d24` | 0.672472 | 19/24 | 4/4 | 0/14 | identical | [1, 19, 4] |
| g1-4 | `ec3685b7c701` | 0.603317 | 19/24 | 4/4 | 0/14 | identical | [1, 19, 4] |

**All three mutants are inert.** Not "scored the same" — identical at the level of
the individual ask. Comparing every line of both generations against `g0-1` on
`(pass, stage)` per ask: **zero differences across all seven lines** — four carrying
the parent genome `abffa2b7f101` and three carrying a mutant — over 294 ask
evaluations. The stage distribution is byte-identical on all seven.

**Culling: `no_gain`, the parent stands.** All three mutants were *eligible* — none
lost a frozen pass or a guarded probe — and none was better than the control, so
`select_key` ties and the tie goes to the parent. Note the distinction from the
instruction's wording: a **stall** is the outcome where *no* mutant satisfies the
constraint. That did not happen. These mutants satisfied it and gained nothing,
which is a different record and a different next step.

**The three questions, answered from the movement blocks:**

- *Did failure-stage mass move out of `recall`?* **No.** `recall_delta = 0` on all
  three mutants; the whole distribution is unchanged.
- *Did any guarded probe change?* **No.** 4/4 on every line, `guard_gained` and
  `guard_lost` both empty.
- *Did any paraphrase probe change?* **No.** 0/14 on every line, both lists empty.

**Why it was inert, from the reach measurement rather than guessed.** Raising the
floor only affects an ask that currently *answers* with coverage in
[0.60, new_floor). The pre-flight found refusals at 34–57% and no recorded answer
in that band; the asks that pass either go through the dedicated paths (count,
ordinal, disjunction, record, quantity), which never consult the coverage floor at
all, or answer with coverage above 0.672. So all three values sit in a gap. The
gene is real — §10's pre-flight shows exactly where it bites — but not at these
values, and not in this direction.

**The pre-registered directional prediction was not tested**, as declared before the
run: all three draws raised the floor and the prediction is about lowering it. That
is recorded as the generation's main limitation, ahead of its result.

**The seed rule for generation 2, declared before it is run:** the seed is the
generation number, so generation 2 uses `--mut-seed 2`. No re-rolling, and no
inspecting a seed's draws before declaring the rule that picks it. If generation 2
is also one-sided, the conclusion is that three draws at σ=0.05 cannot test a
directional hypothesis — a finding about the design, and not a licence to keep
drawing seeds until one cooperates.

### Two defects this generation found, and how each was caught

1. **`select_key`'s third term was the paraphrase count.** A scenario drive run
   *before* generation 1 reached that code — five synthetic populations pushed
   through `movement`, `cull` and `print_culling` — showed a mutant whose only
   difference from the control was one gained held-out probe becoming the survivor.
   That is selecting on the generalisation tier, which §4.4 forbids, and it was live
   in the code the running generation had already imported. Fixed to the guarded
   count, with the paraphrase tier permitted to influence an outcome only through
   the demoting `phrasing_fitted` veto. `--recompute` re-derived the rows from the
   ask journal under the corrected rule and printed both verdicts:
   `[1, 19, 0]` as-run against `[1, 19, 4]` recomputed, **outcome `no_gain` either
   way**. So generation 1's decision is not an artefact of which rule was in force,
   and the as-run rows are still on disk to prove it.
2. **`lineage_of` ignored its own `parent_id` argument.** It walked the published
   generation files looking up the *child*, and a first-generation mutant is in no
   published file yet, so its lineage came back as `[self]` — a chain that never
   names the parent it was derived from. `docs/evidence/verify_generation1.py`
   caught it on the committed record. Fixed to start the walk from the parent it was
   handed; `--recompute` re-derives lineage, and four tests pin it, including the
   founder and control-clone edge cases where `genome_id == parent_genome_id` and the
   walk must not emit the same id twice.

Both were found by an instrument rather than by reading, and the second only
because the verifier was written to check the record rather than the console.

Also added on the way: `--dry-run`, which prints a generation's genome ids and
mutation values before it commits an hour of builds, and is what surfaced the
one-sided sample; and `--recompute`, which rebuilds a generation's rows from its
ask journal under the current rules while keeping the as-run copy, so a rule change
made mid-run is visible instead of silent.

**The four generation-1 files on disk, and why none was deleted.**
`generation_1_asks.jsonl` is the primary record — 168 per-ask rows, written as they
landed, and the only file the two others are derived from. `generation_1_asrun.jsonl`
is what the run itself published, carrying the pre-correction `select_key`
(`[1, 19, 0]`) and the broken one-element lineage. `generation_1.jsonl` is current:
corrected key (`[1, 19, 4]`) and correct lineage. `generation_1_prev_20261030_023548.jsonl`
is the intermediate from the second recompute — corrected key, still-broken lineage
— kept because it is the only artefact showing the two fixes landed separately
rather than together. Deleting records is how this project lost a memory file once;
13 KB is cheaper than that lesson.

## 9. What would invalidate a result

Recorded so the checks are not invented after the fact.

- `shim_clean` false on any line: something patched the organ. The line is void.
- `genome_verified` false: a gene did not read back. The line is void.
- `guard.live_files_untouched` false: the run wrote to live state. The generation
  is void, not just the line.
- `frozen_seal` differs from the baseline's: the harness refuses to start.
- `probe-seal-broken` label: generalisation numbers are not comparable to the
  baseline's, and no winner may be declared on them.
- `provenance.as_found.epsilon != birth_epsilon`: something ran decisions during
  construction, so the birth-value assumption in §1.4 is false and every
  plasticity gene in the record is suspect.
- Clones disagreeing on frozen membership: not an invalidation, but the
  disagreement becomes `frozen_unstable` in the baseline and those asks leave the
  guard. A capability claim resting on an unstable ask is a claim about the
  instrument.

## 10. Generation 0, measured

Three clones of `abffa2b7f101`, 42 asks each, 126 builds, 53 minutes, one process,
serial. `state/selection/generation_0.jsonl` and `generation_0_asks.jsonl`.

Every number in this section is re-derived from those two files and from
`tools/selection_baseline.json` by `docs/evidence/verify_selection_checkpoint.py`
— 80 checks, exit 1 on any failure, currently all passing. It checks the things a
table cannot: that the three lines are one genome, that the per-ask journal agrees
with the per-line rows, that the three probe tiers account for every probe exactly
once with none in two, that every guarded probe really passed at base and no
paraphrase probe did, and that the seals quoted here are the seals in the baseline.

| line | frozen | probes | stages | genome verified | shim clean | guard |
|---|---|---|---|---|---|---|
| g0-1 | 19/24 | 4/18 | recall 10, mouth 4, gating 3, shape_arbiter 2 | yes | yes | untouched |
| g0-2 | 19/24 | 4/18 | recall 10, mouth 4, gating 3, shape_arbiter 2 | yes | yes | untouched |
| g0-3 | 19/24 | 4/18 | recall 10, mouth 4, gating 3, shape_arbiter 2 | yes | yes | untouched |

**Reproducibility: the score, the stage distribution and the membership all
reproduced.** 19 asks passed in every line and 19 in at least one, so zero asks
changed membership across three independent builds of one genome. That is a
stronger result than the instrument's own documentation predicts —
`heldout_eval.compare()` records "5/24 held across campaigns while two asks left
the pass set and two entered it, on an unchanged tree". Whatever produced that
drift did not reproduce here; the noise floor measured by this harness, at the base
genome, on this machine, is **zero asks**.

`frozen_unstable` is therefore empty and the guard needed no tolerance. Had the
clones disagreed, §4.3's intersection rule would have excluded the disputed asks
and this section would name them.

**The floor cross-validates against the committed record, on a different
interpreter.** The 19 passes and the 5 failures are exactly the ones in
`docs/STATE.md`, ask for ask and stage for stage. But STATE.md's numbers were taken
on Python 3.10 per the README, and `.venv` on this box is **Python 3.12.10 with
numpy 2.5.4** — not the 3.10 the README's install line would create. So this is a
cross-interpreter reproduction of the floor, which is worth more than a
same-interpreter one, and it is also a warning: the row's `provenance.python` and
`provenance.numpy` are the only thing that would have told anyone. `py -3.10` on
this box does have the dependencies (numpy 2.2.6, scipy 1.14.1, pandas 2.3.3), so
a 3.10 cross-check is possible and has not been run.

`provenance.as_found` confirms §1.4's birth-value assumption on all three lines:
`epsilon 0.15 == birth 0.15`, `temperature 0.02 == birth 0.02`, `decisions 0`.
Nothing runs decisions during `converse.build()`.

### The frozen baseline

`tools/selection_baseline.json`, frozen at `2026-10-29T23:39:31` from the three
clones, before any mutant existed:

- `frozen_pass_set` 19, `frozen_fail_set` 5, `frozen_unstable` 0
- `regression_pass_set` 4 probes — may only be lost
- `paraphrase_set` 14 probes — may only be gained
- `probe_ambiguous` 0

### What the probe tier found

**14 of 18 rewordings of asks he already answers fail.** That is a measurement of
the log's architectural finding — organs match phrasings rather than meaning —
rather than an argument for it.

The four that pass, and what each one licenses:

| probe | what it shows |
|---|---|
| `is the coat wet or is it dry?` | the disjunction path is not order-keyed |
| `have i mentioned the moon to you?` | the record path generalises past `did i ever tell you about` |
| `of the lantern and the kettle which one came first?` | the ordinal path takes alternatives before the cue word, as its docstring claims |
| `the bell turns how often?` | see below |

**The most useful single result is the last one.** The frozen ask `how many times
does the bell turn?` fails at `stage=recall`, and its rewording `the bell turns how
often?` **passes**. Same session, same tells, same memory, same expected words. So
the numeral content is in memory and reachable — the frozen failure is the
`how many` + `COUNT_QUANTS` frame in initial position, not an absent fact. Its
sibling `how often does the bell turn?` fails at recall, so it is position and not
vocabulary alone. This is the log's "numeral claim" — both numeral asks arriving
with `shape = None` because `how` is neither `what` nor `where` — with a working
case sitting beside the broken one, and it is now a guarded pass that a mutant
cannot silently lose.

Three failures localise a mechanism rather than a gap:

- `what is bitten by the frost?` fails at recall. This is a **single-hop** passive,
  and the single-hop active passes. So the two-hop passive failures are not about
  the hop — passive voice alone loses retrieval.
- `repeat after me the copper bell turns twice` fails at `mouth`. The echo path is
  keyed to `say exactly`.
- `which thing turns twice?` fails at recall, while `what turns twice?` passes via
  the arbiter head. The shape parser is keyed to a literal `what`.

### Two defects the run found in the harness itself

Both fixed before the baseline was frozen, and recorded because an instrument that
has not been run is not an instrument.

1. **`shim_check` did not check what its name claimed.** The first version compared
   `__name__` and `__qualname__`. A wrapper called `answer` that delegates to the
   real one — which is what `functools.wraps` produces — passed it. `test_the_shim_check_catches_a_wrapper_that_keeps_the_original_name`
   fails against that version and passes against the shipped one, which decides on
   `__code__.co_filename`: the function must have been compiled from
   `organs/neural_language.py`. A replacement defined in a tool, a test or a shim
   cannot satisfy that whatever it calls itself.
2. **A partial run was charged for asks it never ran.** With a baseline present,
   `--only` or `--limit` reported every unrun frozen pass as `frozen_lost` — 17
   phantom regressions on a 2-ask smoke run. That is coverage read as movement, the
   error `heldout_eval.compare()` refuses a raw delta for and the one the log
   retracted a drift claim over. `frozen_lost` is now intersected with the asks the
   line actually ran, the unrun set is reported as `frozen_not_run`, and the row
   carries `partial-run` so it cannot be ranked against a full line. Pinned by two
   tests.

### Not exercised by this run

`--isolate` was smoke-tested separately (one line, two asks, own subprocess, guard
clean, `partial-run` labelled correctly) but generation 0 ran in process, because a
clone touches no module-global gene to any effect. The first mutation run that
moves an `ANSWER_MODULE` gene must use it.

No mutation operator exists. No culling rule has fired. No genome has been landed,
and nothing about the live animal changed: the generation wrote only under
`state/selection/` and `state/sessions/_selection/`, and the state guard reported
the live tree untouched.

## Change log

- Written before the first run. Base genome `abffa2b7f101` snapshotted at
  `8af3ed9`; seals frozen `b9d0f2d83fbb7e78`, probes `6b6117e9e0a7c331`.
- 2026-10-29 — generation 0 run: three clones, 126 builds, 19/24 and 4/18 on every
  line, identical stage distributions, zero asks changing membership, state guard
  clean. Baseline frozen from it (19 guarded passes, 4 guarded probes, 14
  paraphrase probes, 0 ambiguous). Two harness defects found and fixed on the way,
  both pinned by tests; §4.2's two "inside the mechanism" predictions falsified by
  the base measurement and absorbed by the measured split. Measured on Python
  3.12.10 / numpy 2.5.4, not the 3.10 the README names. No mutation operator, no
  culling, nothing landed.
- 2026-10-29 — checkpoint verified and committed. `docs/evidence/verify_selection_checkpoint.py`
  re-derives every number in §10 from the committed records, 80 checks, all
  passing; two of its own checks failed first and the fault was in the checker
  (STATE.md wraps two of the five failing asks across a newline, so a literal
  substring search missed them), which is recorded because a verifier that passes
  on its first run has not been shown to be able to fail. `state/selection/` came
  out of `.gitignore` so the lineage is tracked: unlike `state/fitness/` it is an
  audit record rather than a regenerable report, and force-adding it generation by
  generation would leave gaps nobody notices. Suite **459 passed, 3 skipped**
  (428 + the 31 in `tests/test_selection_harness.py`), which gained two tests since
  the entry above: the frozen-seal refusal, checked against a modified copy so the
  committed suite is never touched, and its converse.
- 2026-10-30 — generation 1 run: the pre-registered mutation step, 1 control clone
  plus 3 mutants of `ANSWER_COVERAGE_FLOOR`, 168 builds, 78 min. Seed 1 declared
  before the run and its three draws all landed above the base (0.664409, 0.672472,
  0.603317), so the directional prediction was not tested — declared in §8 before
  the run rather than explained after it. Result: all three mutants **inert**, zero
  per-ask differences across all seven lines of both generations (294 evaluations),
  culling `no_gain` with the parent `abffa2b7f101` standing. `no_gain`, not `stall`:
  every mutant satisfied the constraint and none gained. Two defects found and
  fixed — `select_key`'s third term was the paraphrase count, i.e. selection was
  training on the held-out tier, caught by a scenario drive before the live run
  reached that code and corrected to the guarded count with the paraphrase tier
  demote-only; and `lineage_of` ignored its `parent_id`, so first-generation mutants
  recorded a lineage of `[self]`, caught by `docs/evidence/verify_generation1.py` on
  the committed record. `--recompute` re-derived the rows from the ask journal under
  the corrected rule and printed both verdicts (`no_gain` either way), keeping the
  as-run rows at `generation_1_asrun.jsonl`. Added `--dry-run` and `--recompute`.
  Seed rule for generation 2 declared in advance: the seed is the generation number.
  Suite **482 passed, 3 skipped**; `verify_generation1.py` 140 checks, all passing.
  Nothing landed, no core code touched, live animal unchanged.
