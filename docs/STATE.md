# Repository state

[![Tests: NO green covering run at HEAD](https://img.shields.io/badge/Tests-no%20green%20covering%20run%20at%20HEAD-e8912d?style=flat-square&labelColor=0d1117)](#last-recorded-numbers)
[![Held-out 24: 19/24 organ only](https://img.shields.io/badge/Held--out%2024-19%2F24%20organ%20only-0a3069?style=flat-square&labelColor=0d1117)](#last-recorded-numbers)
[![Guards: 8/8 · 1.00 warm / cold](https://img.shields.io/badge/Guards-8%2F8%20%C2%B7%201.00%20warm%20%2F%20cold-5b2d8e?style=flat-square&labelColor=0d1117)](#last-recorded-numbers)
[![Core Dataset: BANC v888](https://img.shields.io/badge/Core%20Dataset-BANC%20v888-7d4e00?style=flat-square&labelColor=0d1117)](https://doi.org/10.7910/DVN/7WTH1N)
[![License: MIT](https://img.shields.io/badge/License-MIT-24292f?style=flat-square&labelColor=0d1117)](https://github.com/SebSilent/Droso/blob/main/LICENSE)

A factual inventory of what is in this tree, what each measurement harness does,
and the last numbers that were recorded, with the commit they were measured at.
No recommendations.

<a id="last-recorded-numbers"></a>

Suite last run on the tree committed as **`0abd505` plus the E8 abort**:
**734 passed, 3 skipped**, exit 0 (at `cb59a2d` + the E9/E10 records). The held-out and
guard numbers in the tables below were measured at **`f2e1748`** and have not
been re-run since; the entries added after them (generations 7–10, E7, the
`cause` field) carry their own numbers and journals.

The previously published figure of 621 passed / 11 skipped was recorded by a
concurrent commit and matches no run made here; it is replaced rather than
carried forward. The skip count differs because the seven generation-10 tests
in `tests/test_stage_cause.py` skip until that journal is published, and it now
is.

Suite re-run at **`04e4d4d`**: **743 passed, 3 skipped**, exit 0. The badge above
still reads 734 and is stale by nine tests.

Suite re-run at **`8b1e8d0`**: **1,333 collected, 1,333 executed, 0 missing, 0 failures, 6 skipped, 0
errors**, exit 0, `git_dirty` empty, 811.33 s --
`experiments/MP-E10/results/suite_manifest_post_intermittence_record.json`, sealed in all five ledgers.
The badge read **1,327 passed · 6 skipped** at that moment, which is 1,333 minus the 6 skips: the manifest
records junit counters and has no pass field, so the pass count is arithmetic on its own numbers and is
labelled as such rather than presented as a measured field. The two figures above (734 at `0abd505`+
records, 743 at `04e4d4d`) are left in place as history, each with the tree it was true of -- they are
what "the badge is stale by nine tests" meant, and that sentence was correct when written. This `8b1e8d0`
line stays as history with its tree named; it is superseded below, not deleted.

**Suite run at `cb61fc0` -- HISTORY, the covering run for the tier-300 closure phase, tree
`cb61fc00e008f3bf609383ab350b41644948a423`.** **1,348 collected, 1,348 executed, 0 missing, 4 failures,
0 errors, 6 skipped**, exit code **1**, **802.51 s**, Python 3.12.10, pytest 9.1.1, recorded in
`experiments/MP-E10/results/suite_manifest_post_tier300_closure.json` with `git_head` `cb61fc00e008f3bf609383ab350b41644948a423`.
1,348 is the 1,333 collected at `8b1e8d0` plus the 15 tests in the two promotion files that phase added. The
badge read this run while it was the newest covering run, deliberately amber and not green, because this run
exited 1 and no greener total was claimed for it. It is kept here as history, with its tree named, and the
manifest is neither edited nor overwritten; the badge now reads the `4e12b91` run below.

**Which four tests failed, and the one path they all name:**
`tests/test_g0_prime_instruments.py::test_registration_seal_verifies_against_the_registration`,
`tests/test_g0_prime_instruments.py::test_index_cross_check_is_not_vacuous`,
`tests/test_g0_prime_instruments.py::test_registration_head_contains_its_sealed_files`, and
`tests/test_registration_seal_coverage.py::test_every_registration_seal_verifies`. All four name
`experiments/MP-E10/results/suite_manifest_post_tier300_closure.json` -- the manifest the run was itself
producing. The seal tool's own words: `DRIFT ... missing | 174/175 files match the registration on the git
blob | 174 of 175 are in the git index | HEAD-MISSING ... absent from cb61fc00e: stamped before it was
committed`. That is **sealed-before-produced**: the ordering rule this phase registered sealed a path before
the run that creates it, and those two tests assert every sealed path is in the index and present in the
registration's own anchor, so the rule guaranteed the failures it caused. 1,344 of 1,348 passed; the 6 skips
are the standing registered skips, including the licensed-absence seed-dependence defect. The run's
`git_dirty` also listed the five registrations -- the same ordering mistake in its second form, the re-stamp
not yet committed when the run started. No test was edited, weakened or skipped, and the suite was not run a
second time to chase a greener total.

**The four pass alone at the post-stamp tree.** Once the artifact was committed (`5c0d440`) and all five
ledgers re-stamped at it (`2fc3dad`), `--check` reports for every ledger 175/175 files matching on the git
blob, 175 of 175 in the git index, and 175/175 sealed blobs present byte for byte in `git_head 5c0d4401e`;
`git_dirty_sealed` is `[]` in all five, read back from the committed bytes rather than from the tool's
summary. Re-running those four tests alone at `2fc3dad`: **4 passed in 156.25 s**. That is the governing
procedure -- run the suite once, write the result into the record, re-stamp, then re-run the seal test alone
to prove freshness -- and it is why the covering run's 4 failures stay on the record instead of being
re-measured away. Registered as AMD-MPE10-07 with the corrected ordering.

The sentence "there is no suite run at HEAD" was removed because it became false, not because it was
awkward: `cb61fc0` is now a run on a tree that contains the promoted drivers, the closure tool and the two
new test files. 1,333 remains true of `8b1e8d0`.

**Suite run at `4e12b91` -- HISTORY, the covering run for the row-key work. It was the counters the badge above read until 2026-11-06, and the badge no longer reads them: two later covering runs both exited 1.**
**1,364 collected, 1,364 executed, 0 missing, 0 failures, 0 errors, 6 skipped**, exit code **0**,
**843.47 s** wall (`junit_counters.time` 841.181 s), Python 3.12.10, pytest 9.1.1, recorded in
`experiments/MP-E10/results/suite_manifest_uniquekey.json` with `git_head`
`4e12b913ea2753a4d331ed6a8449f87d17b094cb` and `git_dirty` `[]`. 1,364 is the 1,348 collected at `cb61fc0`
plus the **16 tests this pass added** to `tests/test_mp_e10_row_migration_promotion.py`, which went from 8 to
24 when the row-key defect was fixed: uniqueness per curriculum across 7 artifacts, the pinned collapse counts
(522 and 1,215), shape-is-authored, item-alone-insufficient, and corrected-key-compares-every-graded-ask.
`collected_not_executed` is 0 and `executed_not_collected` is empty, so nothing was collected and never
reached, and nothing ran that was not collected.

**How this run was produced, because the method is the claim.** The suite ran **ONCE**, at the tree committed
as `4e12b91` -- the stamp commit carrying the fixed migration instrument, its 24 tests and the fixed closure
instrument. It was not run a second time to chase a total, and no manifest was copied out of `_tmp/` to
manufacture a green record: `tools/suite_manifest.py` wrote this JSON directly to its tracked path, and the
JUnit XML it parsed stays in `_tmp/` by design (`.gitignore` sweeps it and `organs/tempstore.py` declares the
area non-normative -- the manifest's own `note` and `junit_xml_kept_in_scratch` fields say so). The counters
above are read back from the sealed artifact, not from the tool's stdout.

**The path this run took is the corrected ordering, and that is the point.** The four seal tests that failed at
`cb61fc0` all named the manifest the run was itself producing -- sealed-before-produced. Here the manifest was
produced first, committed, and only then added to `DEFAULT_MANIFEST` and sealed by the stamp that follows. A
manifest is sealed after it is produced, never before (AMD-MPE10-07).

**The four seal tests, which now pass.** `test_registration_seal_verifies_against_the_registration` and
`test_index_cross_check_is_not_vacuous` and `test_registration_head_contains_its_sealed_files` (all three in
`tests/test_g0_prime_instruments.py`) plus
`tests/test_registration_seal_coverage.py::test_every_registration_seal_verifies`.
run alone at the post-stamp tree `5adc3c573e1b62c68112d1155887346c7d0a5049`, after the stamp commit that seals
this manifest: **4 passed in 162.69 s** (wall 163.13 s). That is the governing procedure stated in
`tools/suite_manifest.py`'s own docstring -- run the suite once, write the result into the record, re-stamp,
then re-run the seal tests alone to prove freshness -- and it is why the covering run's counters are not
re-measured away. The stamp at `5adc3c5` records anchor `ac3d42b16b16`, **183 sealed files** in each of the
five ledgers, `git_dirty_sealed` `[]` read back from the committed bytes rather than from the tool's summary,
and the anchor proven an ancestor of HEAD. `docs/STATE.md` is not a sealed path, so recording this result after
the stamp cannot put the seal out of step with the tree.


## No green covering run at HEAD

**The badge above is deliberately amber.** The newest covering suite run is at `e554987` -- **1,485 collected, 1,485 executed, 0 missing, 1 failure, 0 errors, 6 skipped**, exit code **1**, **1009.25 s**, recorded in `experiments/MP-E10/results/suite_manifest_head_e554987.json` with `git_head` `e5549876e28e96f9091164e5ab20df96912c0256` and `git_dirty` `[]`. **It is NOT covering in the sense this file has used the word: it exited 1.** Its single failure is `tests/test_electric_fragment_guard.py::test_the_guard_returns_the_licensed_absence_instead_of_the_fragment`, and it is the licensed-absence flip, characterised at 10 of 200 contexts (5.00 %, Wilson 95 % [2.7382 %, 8.9579 %]) in `experiments/MP-E10/results/licensed_absence_flip_hunt.json` -- see D-MPE10-16.

**The run before it, at `7d14580` -- also NOT covering.** **1,484 collected, 1,484 executed, 0 missing, 1 failure, 0 errors, 6 skipped**, exit code **1**, **1017.25 s**, recorded in `experiments/MP-E10/results/suite_manifest_head_7d14580.json` with `git_head` `7d14580a116ca65ebe1b2a57fa63aaf3453af323` and `git_dirty` `[]`. Its one failure was the stale substring predicate in `test_no_registration_seals_another_registration`, since repaired; the invariant it guards was measured intact (zero true cross-registration entries in all five ledgers).

**What the `e554987` run does establish, because it is on the record and not invented here:** all four seal tests passed inside it -- `test_registration_seal_verifies_against_the_registration` 53.08 s, `test_index_cross_check_is_not_vacuous` 52.96 s, `test_registration_head_contains_its_sealed_files` 0.07 s, `test_every_registration_seal_verifies` 133.65 s -- as did the repaired predicate test and the new `test_the_ledger_predicate_distinguishes_a_suffix_from_a_path_segment`. The repair is certified; the suite as a whole is not green.

**History, with its trees named, unaltered.** The green covering run remains `4e12b91` (`suite_manifest_uniquekey.json`: 1,364 collected, 0 failures, 6 skipped, rc 0, 843.47 s) and the earlier deliberately-amber covering run remains `cb61fc0` (`suite_manifest_post_tier300_closure.json`: 1,348 collected, 4 failures, rc 1, 802.51 s). Both stay above with their own words intact. Neither is the state of HEAD, and the chip no longer implies one.

**Why no greener number was bought.** The suite ran once per tree and was not re-run after the flip; no test was edited to pass on both licensed forms, because that is a ruling and not a repair (D-MPE10-16 puts it to the PI). A badge that reads green when the suite exited 1 would be the misleading artefact, so the badge reads the truth instead of the total.

Held-out and guard numbers in the tables below are still the **`f2e1748`** measurements and have not been
re-run; the badge's other three chips point at them.

## Retrieval-lever closure: E19, E20, E21a

Three read-only probes were run against generation 19 (a control clone of
`abffa2b7f101`, 42 asks, **23 pass — identical to generation 15**, so no
instrumentation changed any score). Together they close every lever that operates
on retrieval of an existing taught row.

| probe | question | verdict |
|---|---|---|
| **E19** `e19_result.md` | is the failure eviction or retrieval? | **eviction falsified** — `taught_resident` True on 40/42 asks, **0/19 failures are eviction** |
| **E20** `e20_result.md` | does the gate cue omit taught terms? | **no** — on 4 of 9 gate asks the gate retrieves the correct row and ranks it **first**, then refuses at coverage 0.340–0.538 |
| **E21a** `cue_dilution_diagnosis.md` | does de-framing the cue recover the row? | **no** — recovers **0 of 4**; best case rank 41→10 against a window of 3 |
| **E22a** `teach_time_reinforcement_diagnosis.md` | does taught-row count predict success? | **no** — the 48%→83% gap is ask-type confounding; the one count=3 gate ask scores **0.454, below the count=1 gate mean of 0.4649**, with its row at rank 1 |
| **E23** `e23_coverage_denominator_prereg.md` | can closed-class syntax be dropped from the denominator? | **refuted pre-implementation** — all 3 variants break the scarf guard (0.5797→0.6676/1.0/1.0 vs a 0.6 floor). The lever *works* (recovers up to 5 of 9 gate failures) and is still undeployable. **No flag, organ change or test added.** |

**Retraction.** E19 and `passing_ask_analysis.md` reported `nearest_has_taught=0`,
i.e. that every gate ask retrieved only book rows. That test was
`startswith("droso:")`, but journal `nearest` entries are bare text carrying **no
who-prefix at all** (30 entries, 0 prefixed), so it could never match. The claim
"taught evidence does not reach retrieval" is **withdrawn**. E19's eviction
finding is unaffected and stands.

**Six-lever conclusion.** E19 (eviction), E20 (cue omission), E21a (cue dilution),
E12a/E14a (score/admission), E22a (reinforcement) and E23 (coverage denominator) are
all closed. E23 is the strongest: excluding closed-class question syntax from the
denominator **works** — recovering 2, 3 or 5 of the 9 gate failures — and **all
three variants break the guarded scarf invariant** (0.5797 → 0.6676 → 1.0 → 1.0
against a 0.6 floor). The obstruction is structural: the scarf cue
`[did, is, say, scarf]` is three-quarters closed-class and its row
`the scarf is wet` contains `scarf` and `is`, so removing syntax collapses the
denominator onto terms the row trivially matches. **The guard depends on the
denominator being wrong in exactly the way the nine failures need it fixed.** A
repair was found, measured, and shown inseparable from breaking a correct refusal.
E23 was refuted by its own read-only pre-test; no flag, organ change or test was
added. The nine gate failures and the one guarded refusal are governed by a single
quantity, and no monotone change to it separates them — so progress requires a
mechanism that is not a coverage threshold. E24 (session-scoped absence inventory)
is pre-registered at `docs/evidence/absence_inventory_design.md`.

**Where the constraint actually sits.** The taught row is resident, findable, and
on 4 of 9 gate asks ranked first by the gate itself — and the ask still fails,
because `must` demands question syntax and passive morphology a declarative tell
can never contain (`what is bitten by the frost?` asks the row
`the frost bites the latch` for `bitten`, `by` and `is`). That is the coverage
denominator E12a/E14a measured and closed at a **0.5488 ceiling**. Where the row
is *not* retrieved, de-framing the cue shows it losing to corpus mass: under the
fully de-framed cue `[bell, turn]` the top three are all book rows about bells,
and the count-1 taught row sits at rank 10.

The constraint chain, corrected: gen 2 / gen 6 said *score*; E12a / E14a said
*score*; `passing_ask_analysis` said *candidate set*; E19 said *cue
construction*; E20 returned it to *score*; **E21a closes cue dilution too**.

**Instrument limitation, recorded.** The E21a probe's `binder.recall(cue, k=200)`
does **not** reproduce the gate's internal retrieval — it disagrees with the
gate's recorded `nearest` in both directions on 2 of 4 asks. Its ranks therefore
cannot certify a repair, and the guarded ask was unattributable
(`taught_row=None`), so guarded-ask safety was never measurable. No repair was
proposed and no organ behaviour, genome or score was changed by any of the three
probes.

## What is in the tree

| path | contents |
|---|---|
| `connectome/` | BANC v888 source tables, core graph construction, rate dynamics, provenance |
| `core/` | action space definition |
| `organs/` | the organs: `neural_language.py` (encoding, semantic association, question answering), `higher_cortex.py` (binder, recall, arbitration), `sequence_organ.py`, `goal.py`, `harness.py`, `local_solver.py`, `reasoning_loop.py`, `learning_loop.py`, `fast_router.py`, `concepts.py`, `knowledge.py`, `api_oracle.py`, `sandbox.py`, `circuit_breaker.py`, `filesystem.py`, and supporting modules |
| `world/` | `connectome_house.py` (HTTP interface, process_chat), `reasoning_agent.py` (assembly), `house/static/` |
| `tools/` | measurement and build tooling (table below) |
| `tests/` | pytest suites |
| `state/` | persistent state: connectome weights, language memory, procedure library, oracle ledger, fitness reports |
| `docs/` | documentation; `docs/archive/` holds historical records written by earlier agents |
| `exocortex/` | verified code fragments available to the assembler |
| `config/` | runtime configuration, no credentials |
| `credentials.py` | per-user credential storage, outside the repository |

## Harnesses

| command | what it does |
|---|---|
| `python -m pytest tests -q` | the test suite |
| `python tools/heldout_eval.py --independent --only <script>` | scores one of six held-out scripts ask by ask, each ask against a freshly built house; `--independent` is the organ-only mode. Journals one line per ask. One or two scripts per call; the full set exceeds a shell timeout. Scripts: `count-frequency`, `order-first-last`, `conjunction-and-absence`, `exact-repeat`, `hop-and-inventory`, `quantity-change` |
| `python tools/script_benchmark.py --only <a>,<b>` | the eight guard scripts, in four pairs: `reference,accumulation`, `discrimination,role_chain`, `switch_back,override`, `session_context,where_kept`. Reports warm and cold scores and their delta |
| `python tools/fly_v2.py --phase generations --seeds ... --n ... --gens ...` | the evolution runner (genome search over `_span_head` weights, `tools/fly_v2.py`). Scores a synthetic component, never an ask; see `docs/selection_design.md` §0 for what that bought |
| `python tools/run_generation.py --generation N --lines K` | the generational selection harness: K brains, each a genome applied to a freshly built house per ask, scored on the frozen 24 plus 18 rewording probes, one lineage row per brain in `state/selection/generation_N.jsonl`. `--snapshot` writes the base genome, `--freeze-baseline` splits the probe pool by the measured clone outcomes. ~26 s per ask, so a 3-line generation is ~55 min and runs in the background |
| `python tools/verify_saved.py --seed <n>` | replays a saved genome and checks it reproduces its recorded composite |
| `python tools/serve.py [--port N]` | OpenAI-compatible chat endpoint (`POST /v1/chat/completions`) |
| `python tools/converse.py` | in-process conversation; `--benchmark` runs a fixed scored script |
| `python tools/mouth_probe.py <script> "<ask>"` | one ask, with its reply and trace |
| `python tools/{quantity,count,record,ordinal,disjunction,glossary,echo_guard,unowned}_probe.py` | paraphrase and control probes, one per answering path |
| `python tools/hop_probe.py` | paraphrase and control probe for the description path |
| `python tools/veto_probe.py` | traces which clause of `_shape_matches` refused an answer |
| `python tools/build_gh_pages.py` | builds the gh-pages payload into `_tmp/gh_pages/` |

## Last recorded numbers (at `f2e1748`)

| harness | result |
|---|---|
| `pytest -q` | 428 passed, 3 skipped |
| held-out 24 asks, organ only, `--independent`, one build per ask | 19/24 |
| eight guard scripts | 8/8, 1.00 warm and 1.00 cold, delta +0.00 |
| live vocabulary | 11,555 words |

Per script: `count-frequency` 4/4, `order-first-last` 3/4,
`conjunction-and-absence` 3/4, `exact-repeat` 3/4, `hop-and-inventory` 2/4,
`quantity-change` 4/4. Failing asks: `how many times does the bell turn?`,
`what did i tell you about before the kettle?`, `what is wet but not on the
hook?`, `what does the thing the frost bites hold?`, `does the door hold the
frost?`.

The 24 was re-derived with `tools/_genome_patch.py` believed moved out of `tools/`.
**It was not**: the file is present and tracked at `tools/_genome_patch.py` (last
touched by `898ae62`), and it replaces `NeuralLanguage._shape_matches` at import
time. No harness imports it, and the selection harness does not trust that —
`tools/run_generation.py` asserts on `__code__.co_filename` that the six methods of
the answer path were compiled from `organs/neural_language.py` before every brain
it scores, because a patched matcher can answer where the organ refused and that
scores the absence of a guard as capability. The same stale claim is in `README.md`
("Known open items"), which also still lists `_oracle_sandbox_hook` as unresolved
when `tests/test_connectome_house.py:690` now asserts the opposite.

## Selection harness baseline (at `8af3ed9`, Python 3.12.10 / numpy 2.5.4)

`tools/run_generation.py`, contract in `docs/selection_design.md`. Generation 0 is
three clones of one genome (`abffa2b7f101`), 42 asks each, 126 builds, 53 min.

| measure | result |
|---|---|
| frozen 24, per line | 19/24 on all three lines |
| probe pool (18 rewordings), per line | 4/18 on all three lines |
| failure stages, per line | recall 10, mouth 4, gating 3, shape_arbiter 2 — identical |
| asks changing membership across clones | **0** (19 passed in every line, 19 in at least one) |
| state guard | live files untouched |
| baseline frozen | 19 guarded passes, 4 guarded probes, 14 paraphrase probes, 0 ambiguous |

Generation 1 then ran the pre-registered mutation step: 1 control clone plus 3
mutants of `ANSWER_COVERAGE_FLOOR` (σ 0.05, bounds [0.45, 0.75], `--mut-seed 1`),
168 builds, 78 min. The seed's three draws all landed **above** the base — 0.664409,
0.672472, 0.603317 — which was declared in the design doc before the run, together
with the consequence that the pre-registered prediction (about *lowering* the floor)
was therefore not tested.

| measure | result |
|---|---|
| frozen 24, all four lines | 19/24 |
| guarded probes, all four lines | 4/4 |
| paraphrase probes, all four lines | 0/14 |
| failure stages, all four lines | recall 10, mouth 4, gating 3, shape_arbiter 2 — identical |
| per-ask differences vs `g0-1`, all seven lines of both generations | **0** of 294 ask evaluations |
| culling | `no_gain` — all three mutants eligible (lost nothing), none better than the control, so the parent `abffa2b7f101` stands |
| state guard | live files untouched |

`no_gain` is not the instruction's `stall`: a stall is when *no* mutant satisfies
the constraint, and all three did. These satisfied it and gained nothing. The
mutants are inert because raising the floor only affects an ask that answers with
coverage in [0.60, new_floor), and the reach pre-flight found refusals at 34–57%
with no recorded answer in that band.

Suite after this step: **482 passed, 3 skipped**. `docs/evidence/verify_generation1.py`
re-derives the stamps, the operator, the guards and the culling decision from the
committed rows: 140 checks, all passing.

Generation 2 ran the same operator with `--mut-seed 2` (the declared rule: seed =
generation number), as a **negative-control guard test**. Its draws were 0.716908,
0.566857 and 0.619743 — one lowering, two raising.

| line | floor | frozen | guarded | verdict | what moved |
|---|---|---|---|---|---|
| g2-1 control | 0.6 | 19/24 | 4/4 | clean | — |
| g2-2 | 0.716908 | 19/24 | **3/4** | LOST | the guarded probe `the bell turns how often?` became a recall refusal |
| g2-3 | 0.566857 | **18/24** | 4/4 | LOST | `where did i say the scarf is?` stopped refusing, so its `require_refusal` invariant broke |
| g2-4 | 0.619743 | 19/24 | 4/4 | clean | nothing |

Outcome `no_gain`, parent `abffa2b7f101` stands: one mutant eligible, none better
than the control. **The regression guard caught a loss in both directions**, which
was the point of the run — until generation 2 the guard had only ever been exercised
on lines that lost nothing.

`docs/evidence/coverage_exact.py` measured the unrounded coverages behind those two
asks before the run (target 0.555, scarf invariant 0.570; `converse._clean()` strips
`coverage` from the reply, so the journal only ever held the whole-percent string).
That corrected a threshold derived from rounded percentages, and it brackets the
lever: the usable band is roughly (0.570, ~0.70), the committed 0.6 already sits
inside it, and both directions are destructive within ±0.12 at σ 0.05. **The
coverage-floor lever is closed** and the stall rule applies — σ, bounds, whitelist
and guards were not changed.

Stability across all eleven lines of three generations
(`docs/evidence/cross_generation_stability.py`): 462 ask evaluations, five lines
carrying the parent genome with **zero** differences between them, and exactly two
differences anywhere in the record — one on g2-2, one on g2-3, each a single ask,
each attributable to the mutated gene. No unexplained variation.

Suite after this step: **484 passed, 3 skipped** (56 in
`tests/test_selection_harness.py`). `verify_generation1.py --generation 2`: 140
checks, all passing.

The 19 passes and 5 failures are the same asks at the same stages as the `f2e1748`
record above, measured on a different interpreter: `.venv` on this box is Python
3.12.10 with numpy 2.5.4, not the 3.10 the README's install line creates. `py -3.10`
does have the dependencies (numpy 2.2.6, scipy 1.14.1, pandas 2.3.3); a 3.10
cross-check has not been run.

Suite after adding `tests/test_selection_harness.py`: **459 passed, 3 skipped**
(428 + 31). Every number in the table above is re-derived from the committed
records by `docs/evidence/verify_selection_checkpoint.py` (80 checks, all passing).

## What the question-answering code does

`organs/neural_language.py`, `respond()`: the utterance is heard (SAN update,
cortex binding, sequence learning); if it is a question it goes to `answer()`,
which selects a role, retrieves propositions through `binder.recall`, and either
recovers the missing role by unbinding or tries a short list of dedicated paths.
Those paths, in the order they are tried:

| path | fires on | behaviour |
|---|---|---|
| echo | the utterance declares an exact repeat | repeats the stated memory |
| glossary | a question about a word used earlier | returns the earlier word |
| ordinal | `which … first/second/last` over session memories | selects by position |
| disjunction | two offered alternatives | settles one against memory |
| record | questions about the telling record | counts or reports absence |
| quantity | `how many X` / `what count of X` / `did any X` | arithmetic over numbers stated in tells |
| description | subject is a definite description | resolves it, then asks the rewritten question |

The description path is not in the tree; it was implemented and reverted (see
`docs/archive/experiment_log.md`). The cue words `first/last` are matched as a
set (`COUNT_FIRST_CUES`, `COUNT_LAST_CUES`).

## Documentation map

| file | contents |
|---|---|
| `docs/STATE.md` | this file |
| `docs/benchmark_findings.md` | benchmark failure analysis, with a 2026-10-27 addendum |
| `docs/cross_session_design.md` | design note: cross-session recall levers |
| `docs/mine_criteria.md` | frozen contract for `tools/mine_primitives.py` |
| `docs/selection_design.md` | frozen contract for `tools/run_generation.py`: the genome schema, the fitness tuple, the three eval tiers and the pre-registered step-6 mutation operator |
| `docs/open_learning_design.md` | design, not yet implemented: moving from a frozen evaluated brain to a persistent learner. Grounded in a fresh census of the live binder, with the six-rung capability ladder, the fourth (open) eval tier, the one unavoidable core change named and flag-gated, and experiment E1 specified with its command and success criteria |
| `docs/evidence/binder_census.py` | census of the live cortex store: rows by `who`, by `count`, by age. Output committed at `docs/evidence/binder_census_20261030.txt` |
| `tools/teach_episode.py` | E1: one teaching episode. Generates novel propositions from the live vocabulary, verifies each is absent from the binder, teaches and consolidates in a sealed session, overlays onto a hardlinked shadow, then measures all four tiers against that shadow in fresh builds. Five gates, exit 1 on any failure. `--dry-run` generates and verifies without teaching |
| `state/lineage/episodes.jsonl` | the episode ledger, one self-contained row per episode. `python tools/run_generation.py --report --episode N` re-prints one |

## Open learning E1 (at `aac701c` + `tools/teach_episode.py`, Python 3.12.10 / numpy 2.5.4)

Episode 1: 20 facts, seed 1, 82 asks, 34 min, one shadow, live state never written.
**Verdict PASS, all five gates.**

| measure | result |
|---|---|
| acquisition, in the words it was taught in, across a process boundary | **20/20** |
| generalisation, held-out rewordings | **2/20** — reverse-role 2/2, question-word swap 0/6, passive 0/12 |
| frozen 24 / guarded probes | 19/24 and 4/4, both unchanged |
| erosion | **none** |
| displacement | 22 evicted, all `book` count 1; 22 added, **20 of them `who="you"`** |
| SAN | nnz 66,107,030 → 66,107,030 (**+0**); total weight −30,211; 8,112 rows changed |
| live seals / guard | unchanged / moved nothing |

The first measured retention of a taught fact across a process boundary in this
project, and the first `who="you"` rows in the live binder lineage. Two results
redirect the programme: the phrasing brittleness measured on weeks-old corpus memory
reproduces exactly on facts taught thirty seconds earlier (so teaching more facts will
not move rung 2 of the ladder), and blind FIFO evicted precisely the low-value corpus
rows, so value-weighted eviction is not needed for small episodes — only once a taught
row ages far enough that 60,000 further binds reach it.

Suite after this step: **509 passed, 3 skipped**.

## Section 7a landed, and E2 measured it (`876dde0` + episode 2)

`WITNESS_W` (`organs/neural_language.py:483`) gained `"you": 1.0`. One entry in one
class constant, landed alone so a regression is attributable to it. Its only reader is
`consolidate()`'s value function, which did `.get(who, 0.6)` — and 0.6 is exactly the
`book` weight, so user testimony had been scoring as corpus at every count.

Three proofs, as the design requires:

| proof | result |
|---|---|
| guarded behaviour unchanged | generation 3, one control line on the changed tree: 19/24 frozen, 4/4 guarded, and **0 of 42 asks differ** from the pre-change reference on `(pass, stage)`. Across 12 lines / 504 evaluations the only two differences anywhere remain generation 2's mutant gene effects |
| consolidation selection, before/after | `docs/evidence/consolidation_census.py`, replica validated against the real function's counters (2000/294/200). **Byte-identical** before and after on live state — which holds zero `you` rows, so there was nothing for the new weight to act on. That is the no-unintended-perturbation proof, not the intended-effect proof |
| suite | 510 passed, 3 skipped |

Episode 2 then measured the intended effect in vivo, and **all six pre-registered
predictions confirmed**:

| measure | E1 (pre-7a, seed 1) | E2 (post-7a, seed 2) |
|---|---|---|
| acquisition | 20/20 | **20/20** |
| generalisation | 2/20 (reverse-role 2/2, question-word 0/6, passive 0/12) | **3/20** (reverse-role **3/3**, question-word **0/10**, passive **0/7**) |
| frozen / guarded / erosion | 19/24, 4/4, none | **19/24, 4/4, none** |
| evicted / added | 22 all `book` count 1 / 20 `you` + 2 `droso` | **23 all `book` count 1 / 20 `you` + 3 `droso`** |
| SAN nnz / total weight | +0 / −30,211 | **+0 / −41,930** |
| consolidation picked, `you` rows | **0** | **6** (of `taught_urgent` 6) |

The last row is the point of §7a: consolidation went from never selecting a taught
fact to selecting **every** one that was eligible for replay. Learning repeats on fresh
material (acquisition 20/20 on a different seed), and rung 2's brittleness reproduces
exactly on facts taught seconds earlier — so it is a property of the answer path, and
teaching more facts will not move it.

One guarded ask's stage moved (`sel-exact-repeat::which thing turns twice?`, recall →
mouth, failing either way); pass sets are identical across all four measurements and
episode 1 against the pre-7a control shows 0 differences, so the cause is the shadow's
different taught material, not §7a. **Stage maps are comparable across generations on
the same state but not across episodes with different material.**

§7b (value-weighted eviction) is not started. Nothing was promoted to live state.
Suite after this step: **510 passed, 3 skipped**.

## The persistent learner: promotion path and E3 (`tools/promote_learner.py`)

`state/live_learner/` holds a versioned learner **beside** the guarded live animal,
which is never written: `--verify` reports it byte-identical to the bootstrap state.
Versions are hardlinked and immutable (a checkpoint is 260.7 MB, 222 MB of it the
binder's `cortex.npz`), the chain is linear, and promotion refuses for five reasons —
verdict not PASS, a gate not exactly True, fewer than 24 frozen asks run, live seals
drifted from what the episode recorded, or staging seals not matching the episode's
`checkpoint_files`. `--rollback` repoints `current/` at the parent and keeps the version
it rolled back from. Ledger at `state/lineage/promotions.jsonl`.

Bootstrap `v0_a7808217f2da` from live state; episode 3 (seed 3, 20 facts) promoted to
`v1_8be802548643`; episode 4 (seed 4) taught **from v1** — the first chained episode.
Both PASS on all five gates.

| measure | ep3 (from v0) | ep4 (from v1, chained) |
|---|---|---|
| acquisition | 20/20 | **20/20** |
| **retention of ep3's facts** | — | **20/20** |
| reverse-role / question-word / passive | 7/7, 0/3, 0/10 | **7/7, 0/6, 0/7** |
| frozen / guarded / erosion | 19/24, 4/4, none | **19/24, 4/4, none** |
| evicted | 22, all `book` count 1 | 21: 20 `book` count 1 **+ 1 `droso` count 4561** |
| SAN nnz | +0 | **+0** |
| `taught_urgent` → picked `you` | — | **9 → 7**, incl. facts from *both* episodes |

Retention 20/20 is the number the promotion path exists to produce: episode 4's binder
read `you: 20` at startup and answered every one of episode 3's acquisition asks after
20 more facts were taught and 21 more corpus rows evicted. Erosion is now **cumulative**
— the frozen floor survives a binder 40 taught rows and 43 evicted corpus rows away from
the guarded animal. Consolidation picked `you` rows from both episodes, the first
evidence §7a protects an *aged* taught fact and not only a fresh one.

One prediction was **falsified and is recorded as such**: a `droso` row rehearsed 4,561
times was evicted, the first measured case of blind FIFO destroying a high-value row. No
capability was lost and the guard held, so §7b stays deferred — but its justification is
now an observed event rather than an argument about a future horizon.

Suite after this step: **531 passed, 3 skipped**.

---

## Generation 7 — the recall gate measured from inside the scored run

`docs/evidence/harness_coverage_diagnosis.md` · classifier
`docs/evidence/harness_coverage_classify.py` · data
`docs/evidence/harness_coverage_diagnosis.json` · journal
`state/selection/generation_7_asks.jsonl`

Until now **every coverage number in this project came from a probe reconstructing the
context**, not from the run that grades the ask. That is why E6's P2 was falsified: a
probe-measured 0.592 did not transfer. Three fields were added to `_clean()`'s keep-list
and to the journal row — `coverage`, `required`, `nearest` — recorded for every ask,
passing and failing. **No threshold moved and no answer-path code changed**; the organ was
byte-identical, `ANSWER_COVERAGE_FLOOR` still 0.6.

Control genome `abffa2b7f101` only (`--lines 1`, no mutation, so no culling and no lineage
decision). 42 asks: **23 passed, 19 failed**. `MEMBERSHIP: 19 in every line, 19 in at least
one` — identical to generations 0, 1, 2, 3, 6.

| class | n | rule |
|---|---|---|
| **ABSENT** | **1** | `required` empty **and** `nearest` empty — cue reached no posting |
| **UNREACHABLE** | **0** | postings found but nothing bindable |
| **GATE** | **9** | `required` set, `coverage` set, `< 0.6` |
| **DOWNSTREAM** | **9** | shape_arbiter 2, gating 3, mouth 4 |

**UNREACHABLE = 0 is a result, not a gap in the instrument.** All nine GATE asks have
exactly 3 neighbours and a non-empty required list; the one ABSENT ask has 0 and empty. The
discriminator ran on real data and nothing landed in the middle.

### The window is not unmeasured — it is **empty**

```
passing asks        n=1   0.570
failed recall asks  n=9   min 0.340   max 0.555
```

The best failing ask (0.555) sits **below** the passing-by-refusal ask (0.570). A floor `F`
admits an ask when `coverage >= F`, so admitting a target needs `F <= 0.555` while keeping
the guard refusing needs `F > 0.570`. Those cannot both hold, and the window is empty in the
**hostile** direction: lowering the floor hits the guard *first*, because its coverage is the
highest number in the battery. A test brute-forces this across the gene's own bounds
`[0.45, 0.75]` at 1e-4. This collapses generation 2's scarf loss (0.566857) and E6's null
(0.587206) into **one ordering fact** instead of two separate null results.

**C1 is answered definitively: no floor exists.** Not "none measured" — none possible, on
this battery, at this genome.

### The probe was wrong, and by how much

| ask | probe | harness | Δ |
|---|---|---|---|
| `what did i tell you about before the kettle?` | 0.555 | **0.555** | 0 |
| `where did i say the scarf is?` | 0.570 | **0.570** | 0 |
| `what is bitten by the frost?` | 0.592 | **0.340** | **−0.252** |

Two of three transferred exactly; the one E6 was built on was off by a quarter. At the real
0.340, floor 0.587206 could never have admitted it — the ask needed the floor lowered by
0.26, far past the guard. The two that agreed are the two whose scripts the probe happened to
reconstruct faithfully, and **there is no way to know in advance which is which**. That class
of error is now closed rather than merely flagged.

### Distinct defects, not 19

The 4 mouth failures rendered **noise** (`bridle adding establish gargery`, `numbered`,
`agin`, `sold`) — a rendering defect in a different organ that no recall change can touch.
The 3 gating failures are the **same** proposition (*the door holds the frost*) in three
framings. One shape_arbiter failure answered *"the coat is on the hook"* to `what is wet but
not on the hook?` — it took the conjunction and **dropped the negation**. Counting distinct
propositions rather than probe rewordings, the 19 failures are roughly 1 absent, 9 gated,
1 negation-dropping, 1 passive-frame, 4 mouth-rendering, 1 gated-proposition-in-3-forms: the
battery's 14 probes reword a smaller fact set, so **failure counts overstate distinct
defects**.

Suite after this step: **607 passed, 3 skipped**.

---

## E7 — `RECALL_UNFILTERED_FALLBACK`, and a correction to the proposed mechanism

The diagnosis document proposed a fallback for "`required_words` returning empty". **That
mechanism does not exist.** `required_words` is not in the codebase; the real gate computes
`must` at `organs/neural_language.py:3231` and only ever reaches it under `if hits and
content:` (line 3228). So an ABSENT ask is not one whose required list came back empty — it
is one where **`binder.recall(content, k=40)` returned postings and three filters removed
every one of them**: drop the question itself, drop memories bearing an interrogative, drop
echo-subsequences of the question. The proposed fallback would have been **inert**, guarded
by a condition that could not fire.

E7 was therefore implemented against the real mechanism. `RECALL_UNFILTERED_FALLBACK`
(default `False`, a **class attribute** beside `ANSWER_COVERAGE_FLOOR` so an A/B arm can set
it without touching the module for everyone) makes the `not hits and raw_n` case re-query the
binder and keep only the exact-question filter, handing the survivors to the coverage gate.
This does **not** bypass a safeguard: the gate still demands every distinctive word at IDF
weight, still refuses below the floor, and the shape arbiter still vetoes afterwards. What
changes is that the refusal becomes a **measured GATE with a coverage number** instead of a
silent ABSENT with none.

The ABSENT return also now carries `recall`, `after_question_filter`,
`after_interrogative_filter`, `after_echo_filter` and `fallback_applied` — recorded
unconditionally, because they are pure recording and they are what separates "no posting
exists" from "postings existed and a filter removed them all, and here is which".

Wired as `--recall-fallback`, recorded in `provenance.code_flags` beside the interpreter and
git head, since two arms of an A/B carry the **same genome** and the flag is the only thing
that distinguishes them.

### E7 result: P2 falsified, and the ABSENT class retracted

Two arms on control genome `abffa2b7f101`, `--tier frozen,probe`, 42 asks each.
Generation 8 flag **off**, generation 9 flag **on**. Both arms identical to each other
and to generation 7: frozen **19/24**, paraphrase probes **0/14**, guarded **4/4**, stages
`{"recall": 10, "mouth": 4, "gating": 3, "shape_arbiter": 2}`, MEMBERSHIP 19 in every
line and 19 in at least one.

| prediction | verdict |
|---|---|
| P1 flag off reproduces gen 7 ask for ask | **CONFIRMED** — all 42 `(pass, stage, coverage)` triples identical |
| P2 flag on moves `which thing turns twice?` out of ABSENT | **FALSIFIED** |
| P3 flag on changes no other ask | **CONFIRMED** — trivially, nothing changed |
| P4 flag on does not raise the score | **CONFIRMED** — 19/24, 0/14 both arms |
| P5 zero erosion | **CONFIRMED** — frozen 19/24, guarded 4/4 both arms |

`fallback fired on any ask: 0` and `rows with a raw recall count: 0`. The fallback is
guarded by `not hits` — by the recall gate having run and found nothing — and **no ask in
this battery reaches that branch**. E7 has no target here and its inertness is total, not
partial. The flag stays default-off and is **not** proposed for promotion: a flag with no
measured effect is not a repair. What is kept is the instrumentation, which cost nothing
and is what turned a confidently wrong classification into a corrected one.

Inspecting every `stage=recall` row's `reason` separates them cleanly:

```
9 x "the closest memory of his covers NN% of the question"    <- real gate refusals
1 x "it did not understand and was not in the mood to babble" <- NOT a recall failure
```

The nine coverages are 34, 39, 42, 45, 46, 51, 51, 54, 55 percent — exactly the nine GATE
values measured in generation 7. The tenth never reached the gate: its raw binder count is
`None`, not `0`, so the instrumented return never executed.

**`stage_of` returns `"recall"` as its DEFAULT** for any unspoken reply whose reason matches
no pattern (`tools/heldout_eval.py`, the fall-through whose own comment says "a DEFAULT, not
a measurement"). *"not in the mood to babble"* matches neither `RECALL_RE`
(`cover|no memor|nothing he rememb|…`) nor `GATING_RE` (`did not feel like speaking|not feel
like|…`), so it fell through. It is a **comprehension** failure wearing a recall label.

Consequences, all recorded in `docs/evidence/harness_coverage_diagnosis.md` §8:

1. The ABSENT class is **empty**, not 1. The true split is GATE 9 / DOWNSTREAM 9 /
   comprehension-mislabelled-as-recall 1.
2. The tally `{"recall": 10, …}` quoted across generations 0–9 has always contained one
   non-recall failure. Real recall-gate failures are **9**.
3. The generation-7 empty-window result is **unaffected and slightly strengthened** — it
   rests on the nine GATE coverages (max 0.555) against the 0.570 passing ask, and the
   retracted ask was never one of them.
4. E5's R1′ determiner repair was aimed at this ask, reparsed it correctly, and it still
   failed — now explicable, because the failure is downstream of parsing. That is a third
   independent confirmation that the shape parser is not the binding constraint.

## Generation 10 — `cause`, a derived field that does not rewrite `stage`

Pre-registered in `docs/evidence/stage_cause_preregistration.md` before the run.
Implementation `cause_of` in `tools/heldout_eval.py`; tests `tests/test_stage_cause.py`.

`stage` is **not** modified, recomputed or backfilled. Generations 0–9 keep the values they
were published with, because ten generations of journals, two sealed baselines and several
committed documents quote those numbers, and rewriting them would make every prior
measurement unverifiable against its own record. `cause` is recorded beside `stage`, derived
from the same turn, `None` on passes.

`cause_of` returns `stage_of`'s answer unchanged for every stage except `recall`, which it
splits into `recall_gate` (a real gate refusal: `RECALL_RE` matches, `COMPREHENSION_RE` does
not), `comprehension` (`COMPREHENSION_RE` matches, checked second and winning because
`RECALL_RE` contains broad tokens like `empty` and `no candidate`), and `unclassified`
(non-empty reason matching nothing — deliberately not given a confident name, since inventing
a fourth label for "matched nothing" would repeat the original error with better vocabulary).
`recall_untraced` is already named by `stage_of` and passes through, so `cause_of` has no
`untraced` value of its own; that branch would be unreachable.

Generation 10: one clone of `abffa2b7f101`, `--tier frozen,probe`, 42 asks, no flags.

| prediction | verdict |
|---|---|
| P1 `stage` identical to gen 9 for all 42 asks | **CONFIRMED** — same id set, zero stage differences, zero pass differences |
| P2 the ten recall failures split 9 `recall_gate` + 1 `comprehension` | **CONFIRMED** — and the comprehension ask is `which thing turns twice?`, `coverage: null` |
| P3 scores unchanged: 19/24, 0/14, 4/4 | **CONFIRMED** — stages `{"recall": 10, "mouth": 4, "gating": 3, "shape_arbiter": 2}`, MEMBERSHIP 19/19 |
| P4 generations 0, 1, 2, 7, 8, 9 contain no `cause` key | **CONFIRMED** — 0 of 126, 168, 168, 42, 42, 42 rows |
| P5 no non-`recall` stage is ever reclassified | **CONFIRMED** — property test over a reason corpus, plus zero reclassifications in the journal |

`unclassified` did not appear, so no reason exists in this battery that matches neither
regex. Full gen-10 `cause` tally: `recall_gate 9, mouth 4, gating 3, shape_arbiter 2,
comprehension 1`, and `None` on the 23 passes.

The corrected census is in `docs/evidence/downstream_repair_proposal.md`, which ranks the
remaining classes by frozen passes recoverable per distinct defect and proposes E8
(`POLAR_ABSENCE_MEANS_NO`) against the three `gating` failures — one proposition in three
framings, and the only class where a single repair moves the frozen score.

## E8 — `POLAR_ABSENCE_MEANS_NO`, aborted at its own pre-registered condition

Pre-registered in `docs/evidence/e8_preregistration.md`. **The flag was never implemented
and no battery was run.** Scores are unchanged by construction: frozen **19/24**,
paraphrase probes **0/14**, guarded **4/4**, zero erosion, no state written.

The proposal was coherent — `hop-and-inventory` really does teach a closed two-relation
inventory (`bites(frost,latch)`, `holds(latch,door)`) and `holds(door,frost)` really is
absent from it, so `no` is the correct answer. It assumed an inventory exists to close a
world over. Four measurements say otherwise:

| check | result |
|---|---|
| (a) an inventory mechanism in the organ | **none** — zero hits for `inventory` or any relation store (`relations`/`triples`/`facts`/`roles`/`propositions`/`edges`). `hop-and-inventory` is a corpus label, not code |
| (b) do the three asks reach retrieval | **no** — all three journal rows carry `coverage: null` and `source: null`; the refusal is the **mood** gate at `organs/neural_language.py:3956-3977` (`understands` True, `wants_to` False), which fires before any answer path |
| (c) what the only memory can licence | **null retrieval** — the binder is 60,000 rows at capacity, 99.19% unrelated `book` prose, blind FIFO eviction; emptiness there carries no information about the taught inventory |
| (d) the organ's own standing policy | **prohibits it** — `_ordinal_answer`'s docstring at `:3052-3054`: "It never says `no`: defect B stays closed until a mechanism can express absence without asserting a false negative." Defect B is this defect |

(b) is the decisive one and it inverts the proposal: there is no suppressed negative to
unlock. Emitting `no` would not release an answer he already reached — it would replace a
mood silence with a fabricated proposition, which is exactly the confabulation the abort
condition was written to prevent, arrived at from the opposite direction.

The condition was quoted verbatim in the proposal: *"If the implementation cannot
distinguish a held inventory from a null retrieval, the experiment is abandoned rather
than shipped."* It cannot, so it is abandoned. The two-arm battery was deliberately not
run: with no code change, both arms would reproduce generation 9/10 ask for ask, and
~36 minutes and ~84 builds to re-measure a known-identical result is not a measurement.

This is the second consecutive proposal to fail its own pre-registration (E7's P2
falsified, E8 aborted), and both were caught by the pre-registration rather than by the
score — which is the intended function of the practice.

**E8' is recorded as future work, not shipped.** A sound negative needs a session-scoped
closed-world relation inventory, and the scoping primitive already exists:
`_ordinal_answer` restricts itself to this session's `who == "you"` rows via `session_t0`
(`:3070-3080`). E8' would answer `no` only when the session inventory is non-empty,
contains at least one relation with the queried verb, and lacks `(A,V,B)` in both
directions — otherwise silence. That non-empty-plus-verb clause *is* the distinction E8
could not make. Two standing constraints keep it out of scope: it must override the mood
gate (a change to the reply-decision path, not an additive answer path like R1/R1'/R2 or
E7), and it needs passive normalisation, where R2's `SHAPE_ALLOW_PASSIVE` was measured
**inert** in E5 and cannot be assumed to work.

Pinned by `tests/test_e8_abort.py` (11 tests), which assert an **absence**: no
`POLAR_ABSENCE_MEANS_NO` attribute, no occurrence of the string in the organ source, the
prohibition still in `_ordinal_answer`'s docstring with no `no` in its body, and the three
polar asks still `spoken: false` with `coverage: null` and `source: null` in generations 9
and 10. Without those tests the next pass could add the flag, see frozen move 19/24 →
20/24, and read that as a repair rather than as a confabulation — a wrong `no` scores the
same as silence on this battery and asserts something false, so only the tests and the
pre-registration tell them apart.

| `docs/archive/experiment_log.md` | historical experiment log written by prior agents |
| `docs/archive/role_chain_proposal.md` | historical proposal, not applied |
| `docs/evidence/e9_result.md` | E9: session-scoped resonance, refuted |
| `docs/evidence/e10_preregistration.md` | E10 pre-registration, written before the gene |
| `docs/evidence/e10_result.md` | E10: content-scoped resonance, refuted |
| `docs/evidence/comprehension_signal_design.md` | what E9/E10 leave as the real blocker |
| `docs/evidence/e11a_support_probe.py` | E11a probe: zero builds, aborts loudly if tells unresolved |
| `docs/evidence/e11a_result.md` | E11a REFUTED — support cannot separate mouth from recall |
| `docs/evidence/answer_formation_diagnosis.md` | the coverage accounting trace, Classes A/B/C, E12 proposal |
| `docs/evidence/e12a_coverage_probe.py` | E12a: zero builds, recomputes coverage over answerable terms |
| `docs/evidence/e12a_result.md` | E12a ABORTED — the guarded scarf ask flips to 0.6676 |
| `docs/evidence/e13a_provenance_rerank.py` | E13a: zero builds, provenance re-ranking of candidates |
| `docs/evidence/e13a_result.md` | E13a NEGATIVE — Class C is generation, not ranking |
| `docs/evidence/candidate_generation_diagnosis.md` | the gap is real but immaterial; ceiling 0.5488 |
| `docs/evidence/e14a_candidate_gap.py` | E14a: zero builds, admits every tell as a candidate |
| `docs/evidence/post_coverage_gate_design.md` | provenanced entailment licensing; E15 probe |
| `docs/evidence/e15_entailment_probe.py` | E15: zero builds, entailment over provenanced rows |
| `docs/evidence/e15_result.md` | E15 ABORTED — C1, C2, C4 all fired |
| `docs/evidence/architecture_decision_review.md` | the seven closed lines; recommends E16a |
| `docs/evidence/e16a_relation_index.py` | E16a: zero builds, offline (s,r,o) extraction |
| `docs/evidence/e16a_result.md` | E16a ABORTED at D2 — guard structural, fillers wrong |
| `docs/evidence/counting_primitive_design.md` | events not state; regression avoided by placement |
| `docs/evidence/e17a_counting_probe.py` | E17a: zero builds, event extraction + fold |
| `docs/evidence/e17a_result.md` | E17a ABORTED — the target class is empty |
| `docs/evidence/paraphrase_gap_diagnosis.md` | failing asks with a passing twin |

### E17a — the counting primitive, ABORTED (`8f31533`)

Zero builds. **E2, E3 and E4 all fire.** The design was motivated by the review's fork — *"if D3
fires, the quantity asks need a counting primitive rather than a relational one"* — and E16a's D3
had fired on a coverage limitation (only 2 of 9 recall-gate asks are in the frozen file). E17a
read both batteries and the journal, and the fork resolves **against** counting.

**The decisive measurement: of 11 quantity asks, 7 already pass at the coverage gate.** The 4
that fail decompose into three mechanisms, **none of which is entity counting**:

1. **Frequency adverbials (2)** — `how many times / how often does the bell turn?` want `twice`.
   Not a count of entities; `twice` is not a cardinal, so the tell extracts as *"no numeral"* and
   is invisible to an `(entity, numeral)` index by construction.
2. **Rehearsal count (1)** — `how often did i say the coat is wet?` asks how many times the *user*
   spoke. That is the binder's existing `count` metadata, which four passing asks already use.
3. **Paraphrase gap (1)** — `what number of eggs is left in the basket?` **fails** while
   `how many eggs are left in the basket?`, the same proposition, **passes**.

The one genuine event-count ask, `how many eggs broke?`, **already passes**, so per the design's
own placement rule the primitive is never reached. **E4: zero gain** — stronger than E14a's "safe
but worthless": not merely no gain, **no target**.

**Four probe defects are reported in the result rather than hidden**, because E2/E3 fired partly
for the wrong reasons. The most important is that **H2 was a tautological test** — it asserted
`entity == normalise(raw_ent[-1])`, exactly what `head()` computes, so it validated the
implementation against itself and reported PASS while the rule was wrong (`there are four eggs in
the basket` → entity `basket`; `then two eggs break` → entity `break`, verb `egg`, swapped).
State-count queries were also misrouted (`left` was in the stop list), so **the polarity-refusal
logic — the design's central safety mechanism — never executed and is untested, not refuted**; and
the place filter silently drops events during folding, a drop H1/E7 could not catch because they
check extraction only. Only 4 tells in the 12-script battery contain a cardinal and one is an
event, so **H5 (update-not-add) is untestable on this battery**.

Fixing the probe would not change the verdict: E4 is measured against the journal, not the
extractor.

### Eight accounts closed, and the instrument was wrong

**Eight accounts of the `mouth`/`recall` boundary are now closed** — resonance ranking (E9/E10),
comprehension signalling (E11a), coverage numerator (E12a), coverage threshold (gen 2/gen 6),
coverage ranking (E13a), candidate generation (E14a), provenanced entailment (E15), counting
(E17a). The pattern holds throughout: every mechanism that makes the agent answer more often also
makes it answer wrongly, and the guarded invariant catches it each time.

E17a adds what the previous seven did not: **the failing asks are not one class.** The 9
recall-gate asks span frequency adverbials, rehearsal counts, paraphrase gaps, irregular
morphology, two-hop composition and unanswerable-by-design queries. Seven experiments each
addressed one facet and were scored against all nine, which is why every one looked like a
near-miss. **The battery's aggregate failure count has been the wrong instrument since E13a.**

The one mechanism that is neither closed nor in need of a new primitive is the **paraphrase gap**
— a failing ask with a *passing twin on identical taught evidence*. It is falsifiable without a
lexicon, a new primitive, or any change to the coverage formula, and it is the only open line
where a correct answer is already demonstrated to exist in the organ.

### E15 — provenanced entailment, ABORTED at C1/C2/C4 (`46d8a56`)

Zero builds. The design claimed the guarded scarf ask would refuse *structurally*, because the
query is locative and the scarf's provenanced evidence is a property. **That reasoning was
wrong**: the script also tells `the coat is on the hook`, a locative row about a **different
subject**, so the ask was licensed — with filler `'the'`. G2 then licensed **five**
currently-passing asks, **four confidently wrong**: `what bites the latch?` → `latch`,
`how many eggs broke?` → `four` from a row saying eggs are *in the basket*.

**Provenance separates *what he was told* from *what resembles the question*. It does not
separate *which told fact answers this question*.** That needs a subject-specific signal — the
axis E11a also lacked. Seven accounts of the `mouth`/`recall` boundary are now closed, and the
pattern is consistent: **every mechanism that makes the agent answer more often also makes it
answer wrongly.** The guarded invariant is not an obstacle to the repair; it is the repair
working, and it has correctly rejected six proposed answer-licensing changes.

### E16a — write-time relation index, ABORTED at D2 (`127337c`)

Zero builds, `scripts_heldout.json` only. **D1 clear — the positive result:** a subject-keyed
index refuses the scarf ask for the right reason (*"subject 'scarf' is indexed but has NO
locative relation — only a property"*). The coat's row **cannot** license it. This is what E15
could not do, and it confirms subject binding is the missing axis.

**D2 fires — three wrong fillers**, from two defects that are missing representational
commitments, not tuning: **multi-word subjects** (`copper bell` where `bell` is expected and
`copper` is forbidden — no head/modifier distinction, the same gap E11a's `head` field was added
for) and **quantity change over time** (answers `four` where `two` is expected and `four` is
forbidden; a static index cannot represent a quantity that changes, and `quantity-change` is a
class the baseline passes **4/4**, so the index would *regress* it).

**Test 4 also failed**: a conservative suffix normaliser maps `bites → bit`, not `bite`.
Write-time morphology is not derivable without a lexicon. D3 fired on a probe-coverage
limitation — only 2 of the 9 recall-gate asks are in the frozen file. D4/D5/D6 clear.

**Right shape of primitive, wrong first primitive.** The relational index is recorded as
**validated and deferred**; the quantity asks need a counting mechanism with update semantics.

### Counting-primitive design (`2ecc2dd`)

`docs/evidence/counting_primitive_design.md`. Three load-bearing decisions. **Regression avoided
by PLACEMENT, not by testing**: the primitive is consulted only inside the existing
`best_cov < floor` refusal branch, so the `quantity-change` asks — which pass at the coverage
gate — never reach it and cannot regress by construction. This is the one arrangement seven
experiments have not falsified: E12a failed by changing the ratio *inside* the gate, E15 by
licensing broadly enough to reach passing asks. **Store events, derive state**: `there are four
eggs` is *absolute* (a later one replaces), `two eggs broke` is an *event*; folding is ordered by
tell sequence, which is the update-not-add semantics E16a lacked. **Polarity is never guessed**:
a verb lexicon would trip D4 and E10's Finding 1, so event-count queries are answered (`how many
eggs broke?` → 2, stated in the tell) and state queries **refuse**. E17a is specified with seven
checks (H1–H7) and seven abort conditions (E1–E7); **E4 is the real risk** — that the
event-count asks are also already answered, making the primitive safe and worthless as E14a was.
| `docs/evidence/` | raw run output cited by the docs |

## E9 — `RESONANCE_SESSION_SCOPE`, refuted and aborted (`ce04020`)

The `mouth` class was diagnosed as **resonance**, not a mouth defect: in all four cases the
wanted word was present in the candidate pool but lost by ~3.8× to static corpus attractors
(`numbered`, `sold`) that the session never mentioned. Top resonance scores ran ~0.009 while
`reply_threshold = 0.55` sits **inside the attractor band** (0.550–0.581).

E9 restricted the resonance candidate pool to words the session actually contains. P2 and P3
passed — scoping did exclude the corpus attractor — but **P4 failed**: the wanted word still
lost, because the session's own function word `the` became a second attractor. All four
`mouth` and three `gating` failures turned into silent refusals. Arm A (gen 11) and arm B
(gen 12) both scored **19/24 frozen, 0/14 probes, 4/4 guarded**.

The organ's existing content/function distinction is `df * 4 <= n_mem`
(`organs/neural_language.py:3380`). E9's abort clause forbade widening *that* experiment and
said why: a function-word filter "is not obviously wrong, which is exactly why it needs its
own pre-registration with its own predictions rather than being folded into a repair that has
already been refuted."

## E10 — `RESONANCE_CONTENT_SCOPE`, refuted and aborted (`cb59a2d`)

E10 was that separate pre-registration. It applied the organ's own recall-gate predicate
(`df > 0 and df * 4 <= n_mem`) as a content-word filter on top of session scope — **not** a
stopword list, and deliberately not `SHAPE_FUNCTION_WORDS`, the hand-written 86-word set
declared a few lines below the new gene.

Arm A (gen 13, both flags off) and arm B (gen 14, `--resonance-scope --resonance-content`)
both scored **19/24 frozen, 0/14 probes, 4/4 guarded, clean, exit 0**. Zero asks gained,
zero lost. Arm B is **indistinguishable from E9's arm B** at every level the battery
measures — same scores, same stages `{recall: 17, shape_arbiter: 2}`, same seven silences.

| prediction | result |
|---|---|
| P1 flag-off identity | **PASS** — 0 field differences vs gen 11 |
| P2 content filter engages | **MIXED 1/4** — `the` removed on all four; `is`/`on` survive on three |
| P3 both attractor classes gone | **MIXED 1/4** — corpus absent 4/4, function words 1/4 |
| P4 wanted word wins | **MIXED 2/4** — `bell` rank 1, `lantern` rank 1, **`scarf` rank 5/6** → abort cond. 1 |
| P5 zero erosion | **PASS** — no pass lost; five `banc_brain.npz` byte-identical to seal `546adb1bb8e433c3` |
| P6 no new babble | **PASS** — none gained, four went silent |
| P7 score rises | **FAIL** — 0/14 → 0/14; winner clears 0.55 on **0 of 4** → abort cond. 4 |

Displacement census **unchanged at 60,000 rows** (book 59,515 / droso 466 / parent 19 / you
0), identical to pre-E9 — a selection battery teaches nothing.

A 4-build pre-flight (`docs/evidence/e10_scope_probe.py`, ~2 min) confirmed
`predicted_silent: 4/4` and `P7: NONE (0/4)` **before** the 84-build battery was committed.

### Finding 1 — the distributional rule is not a function-word rule

The rule removes `the` (df ≈ 59,000 of 60,000) and keeps `scarf` (df 14), but it **keeps
`is` and `on`**, because in this binder they occur in fewer than a quarter of rows. The
binder is **99.19% `book`**, where `the` is near-ubiquitous and `is`/`on` merely common. So
"distinctive in my memory" and "content word in English" come apart — in exactly the
direction that matters: the residue beating `scarf` (`is` 0.2459, `on` 0.2043) *is* the
function words the rule was meant to catch. Document frequency here measures **corpus style,
not lexical class**. Neither a distributional rule nor a hand list is available until the
binder holds something other than one book.

### Finding 2 — once the organ is silent, filtering cannot help

E9 already drove the winner below 0.55; removing *more* candidates from a pool whose argmax
cannot clear the bar leaves the verdict unchanged. **The ranking repair is downstream of the
real blocker.**

### Finding 3 — `reply_threshold` is the binding constraint, confirmed twice

E10 measures the ceiling for honest content words: **`lantern` 0.4129, `bell` 0.1221,
`scarf` 0.1526**. Nothing a session actually taught reaches 0.55. On this path
**comprehension and attractor are the same event** — the only words that can make the
organism report understanding are high-frequency corpus words unrelated to the question.
Lowering the bar is correctly forbidden: it would make `lantern` speak and would equally
make any moderately resonant corpus word speak where it is wrong.

### Disposition

Both genes stay in the organ, default `False`, inert, with results recorded beside them —
joining `RECALL_UNFILTERED_FALLBACK` (E7) and the three E5 shape genes. **Four measured
negatives, all kept**: deleting a refuted gene invites a retry. All forbidden-on-abort
clauses were respected. Pinned by `tests/test_mouth_resonance_scope.py` (79 tests).

The blocker was localised to a single scalar whose value encodes "a corpus attractor is
present" rather than "the question was understood".

## E11a — the comprehension line is closed (zero brain builds)

`docs/evidence/comprehension_signal_design.md` proposed *session-provenanced term support*:
does a row he was **told**, rather than a `book` row, contain this question's terms together?
Provenance is the axis resonance lacks, and it needs no content/function distinction — which
E10 Finding 1 established we do not have.

`docs/evidence/e11a_support_probe.py` → `e11a_support_probe.json`, `e11a_result.md`. Read-only,
one binder read, **no builds, no organ change, no gene written**.

- **A1 ask-dependence PASS** — range 0.1000–0.7500 over 42 asks, 21 distinct values. No ask's
  best row overlaps `numbered`/`sold`, so provenance does defeat frequency-domination.
- **A2 separation FAIL** — `min(mouth)` 0.2222 vs `max(recall)` 0.5000, margin **−0.2778**.
  Mouth *mean* 0.4229 exceeds recall mean 0.3355, so the signal is not noise — but a mean
  difference cannot be thresholded and `understands` needs a threshold.
- **Item 6 FAIL** — thresholds admitting all 4 `mouth` and no recall-gate failure: **0**.

The pre-registered second clause **held exactly**: both classes are questions the session
taught material for, so the difference between them is coverage, not comprehension. The
overlaps are the proof — `how often did i say the coat is wet?` matches `coat/is/the/wet` at
0.4444; `what number of eggs is left in the basket?` matches `basket/eggs` at 0.4444. He was
told all of it and fails at the floor anyway.

**A loader bug invalidated the first run and its failure was not evidence.**
`tools/scripts_heldout.json` names scripts `count-frequency` while the journal records
`sel-count-frequency`; every lookup missed and all 42 asks **silently fell back** to live-only
rows, measuring support against droso's 466 prior rows instead of the taught facts. The
overlaps gave it away (`['is','the']`, `['which']`, `['in']` — no content). Fixed by
normalising the prefix and making the fallback **loud**: the script now aborts if any ask's
script is unresolved or no tells precede an ask. Same class as E10's `_CStub`, inverted —
there a stub silently failed to override so assertions passed for the wrong reason; here a
lookup silently missed so a *refutation* would have been recorded for the wrong reason. The
design doc's premise was also wrong: session rows are **not** on disk in the live binder
(`you` census 0 of 60,000) because each ask is built fresh in scratch, so the tells had to be
synthesised from the script file.

## Answer-formation diagnosis — the boundary is in the accounting

`docs/evidence/answer_formation_diagnosis.md`. Read-only, traced from the generation-13
journal against `organs/neural_language.py:3463-3476`. **No core code changed.**

The gate is more sophisticated than assumed: coverage is **already stem-matched on both
sides** (`stem(w) in hs`, :3471-3473) and terms are **already IDF-weighted** over the 60,000-row
binder (:3464-3467). Neither naive string comparison nor an unweighted denominator is to blame.

In **five of nine** recall-gate asks the exact taught fact *is* the top-scoring row and
coverage still fails: `there are four eggs in the basket` → **0.538**; `the copper bell turns
twice` → **0.514**; `the frost bites the latch` → **0.340**. Retrieval is not failing.

Three classes. **A — irregular morphology survives `stem()`** (3 asks): `bitten`→`bitten` but
`bites`→`bite`, `held`→`held` but `holds`→`hold`, never matching; the one term that would
prove comprehension is the one the comparison cannot see, and being rare it carries a *high*
IDF weight. **B — the answer cannot contain the question's syntax** (all 9): `must` is built
from the question, so it carries `is`, `left`, `number`, `of`, `does`, `by` — damped by IDF
but collectively decisive. Coverage measures how much of the *question's wording* appears in
the memory, not how much of the *answer's content* is supported, and the floor was calibrated
against that inflated denominator. **C — a book row outranks the taught fact** (2 asks):
`done about the same time as the bell` beats `the copper bell turns twice` — E9/E10's
frequency-domination reappearing in the coverage *ranking*.

**Speakability and the echo/bigram constraints are not implicated.** All nine refuse at :3476
before any of them runs; `spoken` is False and `after_echo_filter` /
`after_interrogative_filter` / `after_question_filter` are `None` for every one. They must not
be touched.

This also explains why the floor cannot simply be lowered: with the exact taught fact as top
row the coverages are 0.34–0.555, so admitting them admits the guarded scarf ask at 0.566857 —
precisely what generation 2's g2-3 did, losing the invariant at `shape_arbiter`. **Fix the
numerator and the floor can stay at 0.6.**

**E12 proposed, not implemented**: `COVERAGE_ANSWERABLE_TERMS`, default `False`, restricting
`must` to terms that could appear in an answer using the organ's **own** question-shape parser
word sets at :2112 — already maintained there, deliberately *not* `stemming.STOPWORDS`. One
gene, one site, floor unchanged, IDF unchanged, `stem()` unchanged. It reuses existing organ
machinery rather than adding a hand list, which is the specific way E10 went wrong.

**E12a is a read-only recomputation over the recorded journal — zero builds, no organ
change.** Pre-registered: the guarded scarf ask **will** flip, because 0.566857 sits 0.033
below the floor and the repair removes denominator terms uniformly. If it does, E12 is
refuted at zero cost and `ANSWER_COVERAGE_FLOOR` and the guarded invariant are **jointly**
unsatisfiable with this coverage formula — closing the coverage line as E11a closed the
comprehension line, and leaving Classes A and C as the only untested accounts, both needing
machinery the organ does not have. Abort conditions B1–B5 are pinned in the diagnosis doc; B2
(any guarded ask reaching ≥ 0.6, or any guarded pass lost) is the load-bearing one.

### E12a ran — ABORTED, and E13a ran — NEGATIVE. Both at zero brain builds.

**E12a** (`e12a_coverage_probe.py` → `e12a_result.md`). The pre-registered prediction fired
exactly. `where did i say the scarf is?` — `must` `[did,is,say,scarf]` → `[say,scarf]`, best
row `the scarf is wet` — goes **0.5797 → 0.6676**, over the 0.6 floor. It was already passing
*by refusing*; the repair would make him answer. That is generation 2's g2-3 loss at floor
0.566857, reached by raising the numerator instead of lowering the threshold. **B2 met, E12
refuted, no gene written.**

It does not even buy what it was designed to buy: **2 of 9** recall-gate asks cross (bell
0.5445→0.6996, frost/held 0.5336→0.6399), the eggs ask reaches only 0.5983, and **two asks
get worse** — `what did i tell you about before the kettle?` 0.5470→**0.2839**. The repair is
**not monotone**: question-frame words sometimes appear in the memory row, so deleting them
from `must` deletes *matched* numerator terms as well as unmatched denominator ones.
`the scarf is wet` contains `is`.

**B5 was clean** — no content term (`kettle`, `frost`, `eggs`, `bell`, `coat`, `scarf`,
`basket`) was dropped. The organ's own parser vocabulary behaved as intended, which is what
makes the negative informative: **the failure is structural, not a bad word set.** The floor is
a *ratio*, so removing denominator terms raises every score uniformly, and the guarded ask sits
only 0.020 below it. Fidelity: recomputed vs recorded coverage n=10, max delta 0.0305; the
scarf margin is ~3× that, so the flip is not an approximation artefact.

**Disposition: `ANSWER_COVERAGE_FLOOR` and the guarded invariant are jointly unsatisfiable with
this coverage formula.** The numerator cannot be fixed without breaking the guard, and the
guard is load-bearing — it is the only thing between a coverage change and E8's confabulation
class.

**E13a** (`e13a_provenance_rerank.py` → `e13a_result.md`) tested Class C. Predicted before
running: the gate sorts by coverage descending and takes `scored[0]`, so `best_cov` is already
the **maximum** over hits and re-ranking can only lower it. Measured: **top row changes on
0/10 asks, coverage rose on 0 and fell on 0.**

The `taught_in_cands` column is the finding. **Wherever a taught row is among the candidates it
is already the top row** (eggs 1/3, bell 1/3, frost-held 1/3, frost-bitten 1/3, scarf 1/1).
For the five asks where a book row wins, the taught fact is **not in the candidate list at
all** — `taught_in_cands=0/3`. So **Class C is not a ranking problem, it is a candidate
generation problem**: `the copper bell turns twice` was never a candidate for
`how many times does the bell turn?`, and a tie-break cannot promote a row that is not in the
pool. Class C was mis-classified in the diagnosis doc.

Recall-gate asks crossing 0.6: **0/9**. Guarded scarf: **does not flip** (0.5797 unchanged,
top row already the taught fact). **No E13b** — a provenance tie-break would be a default-off
branch that provably never fires on this battery, the same shape as E9's
`RECALL_UNFILTERED_FALLBACK`.

**The two results compose into a closed argument.** The asks that *lack* their taught fact need
candidate generation; the asks that *have* it already score 0.3475–0.5488 with the correct row
on top, so generation alone would not lift them either — they are capped by Class B, and E12a
established that fixing Class B breaks the guard.

**Five accounts of the `mouth`/`recall` boundary are now tested and closed**: resonance ranking
(E9, E10), comprehension signalling (E11a), coverage numerator (E12a), coverage threshold
(gen 2, gen 6), coverage ranking (E13a). What remains is Class A — irregular morphology,
`bitten` ≠ `bite`, `held` ≠ `hold` — needing a lexical resource the organ does not have, and
candidate generation, which E13a bounds by Class B. Total cost of E12a+E13a: **zero brain
builds**, against E10's 88 and ~38 min.


---

## ELECTRIC C4c/C4d (live demo, reverse-role asks, and what the flag actually buys)

Docs: `electric_c4_live.md` sections 8-10. Code: `ELECTRIC_REVERSE` on
`NeuralLanguageOrgan`, `tools/electric_reverse_ab.py`, `tools/electric_chat.py`.
Suite at this point: **840 passed, 3 skipped**.

**C4c - the live house, over HTTP, across processes.** `serve.py --electric` answers from the
taught inventory across a restart, and a second process reads the same inventory off disk
(`load_state` moved after the corpus build, which had been overwriting it). `tools/converse.py`'s
churn key was **content-keyed by basename**, so any copy of a brain under `state/churn/g*` made
every later run report `LIVE FILES TOUCHED`; it now keys by full path and falls back to the old
stat key if the content read fails. A defect in the safety plumbing, found by a test that did not
exist, not by the live test.

**C4c - reverse-role asks.** `who does the lantern belong to?` reaches the keyed tell, but only
when the ask **strands a preposition**: `who does the mouse chase?` must NOT answer
`the mouse chases the cat` (it wants the chaser), so the who-branch binds only if the frame is
`<verb> the <noun> <prep>`. Verb agreement is by stem, never substring.

**C4d - the A/B arm (14 asks, 6 tells, one variable, separate organs).** Recovered **4/14**,
regressions **0**, confabulations **0 in both arms**, refusals identical **2/2**.

- **It does not fix the C3 reverse-role count.** `what bites the latch?` stays a miss with the
  flag on: that shape has no preposition to strand. What closed is a different, narrower class.
- **The flag is misnamed.** All four recoveries needed the STEM relaxation; only three needed the
  who-branch. `what does the frost bite?` recovered with the who-branch NOT needed - a FORWARD
  agent ask. So the flag is "reverse binding plus stem-tolerant agreement".
- **A live mis-bind, caught by the guard and not by luck.**
  `_electric_bind("what bites the latch?")` returns `('agent','latch')` - `latch` is a subject in
  its own right, and the tell behind that key is `the latch holds the door`, the wrong fact about
  the right noun. Pinned both-halves in `test_a_live_misbind_is_caught_by_the_verb_guard`.
- **A pre-existing leak, not an ELECTRIC bug.** `who does the mouse chase?` is not silence:
  ELECTRIC declines and the house path (`source: arbiter head`) utters the fragment `'to?'`,
  identical in both arms. The A/B grader now prints the raw utterance for any row that is neither
  silence nor the right fact.

Open: the `arbiter head` fragment leak is unowned; the 14 asks are hand-picked shapes, so 4/14 is
not a coverage estimate; nothing here has been tested on a brain that also has a corpus.


**C4e - object-role asks.** `what bites the latch?` names a tell's **object** and wants its
**subject**. C4d proved `--electric-reverse` cannot reach it (nothing to strand) and that the
subject path *mis-binds* it: `_electric_bind` returns `('agent','latch')`, whose tell is
`the latch holds the door` - the wrong fact about the right noun, stopped only by the verb guard.
So this is a third, separate permission: `ELECTRIC_OBJECT_ROLE` / `--electric-object-role`, off by
default, inert without `--electric`.

- **Order is the whole safety argument.** `_electric_answer` is now a dispatch wrapper: the subject
  path runs first and in full, the object path is consulted **only on its miss**. A row that answered
  before answers identically after; the new path can only turn silence into an answer, never one right
  fact into a different one. Pinned by `test_the_subject_path_wins_when_it_answers_at_all`, which
  deliberately pins the *pre-existing* wrong-ish answer to `what holds the latch?` so that any future
  re-ordering is a deliberate act with its own arm.
- **Four guards, each one a silence:** stem-matched verb (never substring), the ask's noun must be the
  tell's *object*, a tell that makes the ask's noun its *subject* is skipped (role clash), and **exactly
  one** surviving candidate - two matching tells is silence, never a pick, never a tie-break.
  Do-support asks (`what does the latch bite?`) are excluded outright, so one question cannot reach two
  paths and get two facts.
- **My first version of this was dead code.** The hook sat after `return tell`, but the subject path
  returns early at three points, so nothing ever reached it. Caught by behaviour on a hand probe, not by
  a test - the usual outcome for a fallback inserted where no control flow goes. While fixing it I found
  `ELECTRIC_REVERSE = False` was declared **twice** in the class body, the first copy unreachable
  because the second overwrote it at import. Merged into one declaration; the class body now carries
  exactly one of each flag.
- **A/B arm (20 asks, 6 tells, reverse ON in both arms, one variable).** Correct **6 -> 10**,
  RECOVERED **4/20** (`what bites the latch?`, `what bites the latch`, `what chases the cat?`,
  `what holds the door?`), regressions **0**, **confabulations caused by this feature 0**, refusals
  identical **2/2**. `what holds the door?` is the sharpest row: with the flag off the house path
  uttered the bare fragment `latch` (scored a confabulation), with it on the organ says the whole right
  tell - the new path *removed* a leak rather than adding one.
- **Two harness errors of my own, both caught before the result was believed.** (1) I reused C4d's ask
  table, where `what bites the latch?` had `want=None` because C4d's question was *whether the reverse
  flag reaches it*. So the arm scored the correct answer as a **CONFABULATION** and aborted on a
  success. The expectation is overridden in this arm only - rewriting a measured arm's table would
  quietly un-report C4d. (2) My appended rows were `(shade, ask, want)` against an `(ask, shade, want)`
  table, so the "same question answered twice, once silent" was the organ being asked the literal string
  `"object-role"`. I had written that up as order-dependence inside `answer()`.
- **That claim is refuted, and pinned as refuted.** `_absence_note` has exactly one call site, in
  `hear()`, and `answer()` never calls `hear()` - questions cannot become facts. Probed: three asks of
  the same question, teach open or closed, inventory steady at 6, answer identical, and a warm organ
  matches a fresh one. `tests/test_electric_ask_idempotence.py` pins the property *and* the row shape
  that manufactured the phantom, because a phantom this plausible will be believed again.

Open: 10 of 20 asks are still silence or a fragment, so 4/20 is not a coverage estimate; irregular past
(`what bit the latch?`) is out of the stem rule and stays silent by design; the ambiguity-silence rule is
proven on synthetic inventories, not on a corpus brain; the `arbiter head` fragment leak is still unowned
and this arm only happened to close one instance of it; nothing here has been tested on a brain that also
has a corpus.


**The arbiter-head fragment leak, owned.** C4d recorded it as unowned: ELECTRIC declines and
the house utters a fragment of the question. It is now reproduced in two asks and fixed behind
a switch.

- **Mechanism, measured.** `answer("who does the mouse chase to?")` is heard and remembered as
  a proposition. Ask `answer("who does the mouse chase?")` and the shape arbiter matches that
  remembered question (verb `chase`, subject `mouse`); `_shape_matches` returns the post-verbal
  token as the *filler*, which for a question is the stranded preposition with its mark still
  attached - `to?` - and the `arbiter head` branch speaks it as an answer. Nothing anywhere
  asked whether the filler came from a statement or from an asking. Asks are learned into memory
  like statements are, independently of `ELECTRIC_TEACH`, which is why the pair is enough.
- **It is not an ELECTRIC defect.** It reproduces with ELECTRIC off entirely (`build(False)`),
  because the branch is in the recall path. So `--electric-fragment-guard` is read **outside**
  the `--electric` block - my first wiring put it inside, which would have made the switch dead
  in exactly the configuration that needs it, and the help text claimed a scope the measurement
  refutes.
- **The fix is a refusal, not a re-route.** `ELECTRIC_FRAGMENT_GUARD` (default off) replaces the
  utterance with the licensed absence the veto path already produces: `spoken=False`, reason
  *"the only thing that matched was the asking itself"*, parser verdict `fragment`. The predicate
  rejects only what could never have been a fact - empty, anything carrying `?`, or a bare
  function word. Content-word fillers (`mouse`, `latch`, `bell`) pass untouched, and an unrelated
  ask returns byte-identical output with the guard on or off.
- **The live house does not reach it.** A real `converse.build` (corpus and state, the path
  serve.py takes) refused at the coverage floor - *"the closest memory of his covers 37%"* - on
  both settings, before the arbiter branch ran. The leak needs the corpus-free condition the
  ELECTRIC demo builds. That asymmetry is the reason this is a guard and not a rewrite of the
  filler logic: I have not measured it on a brain with a corpus, so I am not going to restructure
  one on that evidence.
- **Why the arm's row flickered - and what that cost me.** C4e's run 3 showed `to?` for `who-bare`;
  run 4 showed silence, same code (the guard is off by default and was not in that path). My first
  explanation was table order. **Wrong, and refuted in one command:** two arm runs with
  `PYTHONHASHSEED=0` still differ on that row (`A=other B=other` vs `A=other B=miss`), so it is not
  hash randomization either - it is per-row nondeterminism inside the process (unseeded engine
  randomness is the standing suspect; not isolated). The precondition I pinned (stranded ask heard
  first) is real and necessary - two of my probes missed the leak without it - but it is not
  sufficient, which is why the row flickers. **Consequence for everything measured with this arm:
  single-row verdicts are not stable and must not be cited as if they were. The aggregates are:
  RECOVERED 4/20 and REGRESSIONS 0 held across all six runs.**
  `docs/evidence/electric_object_ab.json` is therefore one sample, not a reproducible record.

Open: the guard is unmeasured on a corpus brain; the `recalled proposition` branch reads out a whole
token list and the guard does not touch it, so a remembered question may still come out in full -
**not measured, deliberately not fixed in the same stroke**; and the deeper question -
should a question be admissible as a memory at all - is untouched and is the one worth answering
next.


**Memory admissibility for asks, implemented.** The `to?` leak was one symptom of a class:
`live()` learns a question into the binder exactly like a statement, and the recall path reads
token lists without asking what kind of turn they came from. The other symptom was never guarded
at all - `recalled proposition` reads out a WHOLE remembered question, which is not a fragment, so
`_is_question_fragment` could not catch it by construction.

- **The change.** `ELECTRIC_ASK_ADMISSIBILITY` (off by default, `--electric-ask-admissibility`).
  Write side: `live()` already computes `is_q` to decide whether to bind a question whole, and now
  passes it to `cortex.hear(..., ask=)`, which tags the meta row. Read side: ask rows are dropped
  from `hits` **before** the provenance vote and the shape arbiter - the one place a recalled memory
  becomes an utterance - so neither `arbiter head` nor `recalled proposition` can be reached by an
  asking. One filter, not one per mouth.
- **The tag is not solely the switch's doing.** `higher_cortex.row_is_ask()` is the single predicate,
  shared by writer and reader: the organ's `is_q` OR any token carrying `?`. The second half is what
  makes the tag survive a delta replay (the replay path re-hears tokens and does not re-derive `ask`)
  and what tags marked questions even with the flag off. Only the read side is gated.
- **A tag a reader cannot see is a tag that does not exist.** `binder.recall()` builds its hit dict
  from a whitelist of meta keys, so the tag would have been stored and silently dropped at retrieval -
  the whole feature would have been inert and every test of the *write* side would still have passed.
  `ask` is now copied into the hit, and `test_the_tag_reaches_the_reader_not_just_the_writer` pins it.
- **Cost, measured per-process.** Object arm's own 20-ask table, one condition per process: tallies
  are **identical** off/on (correct 6, absence 9, arbiter head 2, electric_taught 1,
  electric_absence 2). The only change is *which* licensed absence a row gets: the unmarked
  `what bites the latch` moved from "nothing he remembers has that shape" to "the closest memory of
  his covers 0%" - silence either way, because the question row is no longer the thing being counted.
  Running both conditions in ONE process gives a spurious delta (an answer appears to be lost). That
  is the arm not being hermetic across builds in a process, the same hazard as the flickering
  `who-bare` row - it bit me here first and I nearly recorded a cost that does not exist.
- **Live house: zero delta.** Real `converse.build` (60,000-row binder, corpus and state), seven asks,
  two separate houses: every ask produced the same `spoken` and the same utterance off and on. The tag
  landed precisely - 7 tagged rows, exactly the 7 token-marked ones, **no prose row caught** - and the
  two `recalled proposition` answers survived untouched, including
  `where does the lantern belong to?`, which now reads a corpus statement instead of the asking.
- **Not fixed, and now visible.** The tag covers what the organ recognises as a question plus anything
  carrying a mark. In the hermetic arm organ `is_interrogative("who")` is False, so
  `live("who pets the mouse", speaker="you")` stores an UNTAGGED question row (measured: tagged=[False])
  - admissibility cannot see an asking the organ does not know it heard. And the book/exposure path does
  not pass `ask` at all, so questions read in prose are untagged by design of this stroke. Both are the
  same open question, one level up: is `is_q` the right authority for what counts as an asking, or
  should admissibility be decided by the shape of the row rather than by the caller's intent?


**Ask-admissibility is now SHAPE-authoritative** (`ELECTRIC_ASK_SHAPE`, off by default,
`--electric-ask-shape`, read only under `ELECTRIC_ASK_ADMISSIBILITY`). Yesterday's flag decided
an asking by the caller's intent; intent was the wrong authority because the organ's `is_q` is a
LEARNED judgement (`is_interrogative` needs role votes) and the corpus never delivers a mark.

- **No second lexicon.** `question_shape()` reads `SHAPE_INTERROGATIVES` -- the answer arbiter's
  own closed set -- so a row is tagged exactly when the arbiter could have parsed it as an ask,
  and the binder keeps its promise not to own an interrogative lexicon (`row_is_ask`'s docstring).
  Three rejections, each aimed at a documented prose class: interrogative must be FIRST (a
  mid-sentence `what` is a relative); the word after it must not be a SUBJECT ("what the loop
  does", "what he did next"); no copula after that ("what matters most IS the latch").
- **The write throttle, which is what this project has been calling flicker.** `hear()` DROPS any
  utterance arriving within `MIN_HEAR_INTERVAL_S = 0.05` of the last and only counts it in
  `skipped`. Every inconsistent number in my own probes and tests this week came from that gate: a
  test that fires `live()`/`answer()` back to back is measuring which writes the throttle allowed,
  not what the flag does. Three tests changed behaviour between runs until the interval was
  neutralised; the live house reports **0 skipped** (its writes are spaced), so this is a
  harness-and-rapid-conversation hazard, not a house defect.
- **Shape had to reach `chunk`, or it was inert.** An unmarked ask that windows has no
  interrogative in first position in ANY window, so no shape reader could call any fragment an
  asking -- tag-only authority would have missed exactly the class it targets. Under the flag a
  fitting ask is bound whole.
- **Read-side guessing removed.** The first version re-derived shape from a recalled row's tokens,
  which looked replay-proof and was not safe: in the real house it ate eight-token **windows of
  statements**. Only the writer knows a row's boundary, so the verdict is now **recorded** in the
  session delta (a 6th element; `apply_delta` unpacks `row[:5]` and old deltas are unaffected) and
  `_hit_is_ask` reads tag-or-mark, nothing more.
- **The cap, decided on measurement.** `remember()` binds at most `max_roles` (8) tokens, so binding
  an over-long ask whole stores its head and the rest never exists. Without that limit the live
  house tagged **324 rows** (197 `what`, 65 `who`, 62 `where`) -- genuine book questions the mark
  path never caught -- and among them `who sacrificed everything for him chimed in the`, a relative
  clause cut off mid-phrase: a fact eaten, silently. With the limit: **3 rows tagged, zero delta on
  ten queries**. The wider coverage was declined because its price is silent deletion.
- **Why the corpus is nearly uncatchable by shape at all: 0 marked rows in 60,000.** The exposure
  path lowercases and drops punctuation before `live()` sees the line, so `?` never reaches the
  binder -- the mark fallback has been catching only chat. The right fix is at the token/exposure
  boundary (keep the mark), and it changes every row's tokens, hence every guarded battery number:
  explicitly not this stroke.
- **Collateral, pre-existing and flag-independent:** the window loop's last start is
  `len(toks) - max_roles` stepped by `max(2, mr//2)`, so an 11-token line at mr=8 bounds tokens 0-7
  only -- the last three words never exist anywhere. The house's own diet is "mostly prose at eleven
  words a line" (the binder's comment says so). Worth its own stroke.
- **Tests:** `tests/test_electric_ask_admissibility.py` 9 -> 20: detector over 6 asks and 9 prose
  classes; unmarked ask tagged only under shape; the book path; a real `save_delta` ->
  `apply_delta` round-trip proving the tag survives a replay that rehearses only tokens; a
  window of a statement is not an asking; the cap declines AND deletes nothing; shape is inert
  without admissibility even to a detector pinned always-true; no tell is ever tagged; serve
  wiring; the measured arms still cannot see either switch.


**ELECTRIC recovers three more ask FORMS** (`ELECTRIC_ASK_NORMALIZE`, off by default,
`--electric-ask-normalize` -- a fourth permission inside `--electric`, alongside reverse and
object-role, so a run that shows it costing something can say which switch did it).

- What was silent was the FORM, not the relation. The matchers key on a tell's own verb stem
  and the ask's nouns, so `who is the lantern with?` (a copula where do-support was expected)
  and `what was the door opened by?` (a passive where the object-role path expects the active)
  fell through to the recall path -- which, with admissibility off, answers them out of
  remembered QUESTIONS. Those rows now get their fact instead of an echo.
- **Two rules keep this from becoming a grammar:** function words only (no content word is
  substituted, stemmed into a different word, or invented), and the output is a LOOKUP KEY, not
  an utterance -- the variant goes back through the EXISTING matchers, which still return a
  verbatim taught tell or nothing. So the normalizer cannot make the organ say a sentence it was
  not told; it can only let an ask reach a matcher that was already free to speak that tell.
- **The participant guard is separate from the shared-stem guard because it cannot use it** -- a
  copula ask names no verb, so there is no stem to share. It requires: the tell is an agent frame
  that ITSELF strands a preposition the ask's stranded preposition can mean; a participant on the
  other end of it; and no content word in the ask besides the subject it bound to.
  `ASK_PARTICIPANT_PREP` makes exactly ONE semantic claim (`with` -> `to`/`with`); every other
  entry is identity. That is why `who is the mouse with?` stays silent: `the mouse chases the cat`
  strands nothing, so it has no participant to give -- the row a stem guard could not protect,
  because `mouse` is in both sentences.
- **Found while writing it: `_absence_frame` stop-words the preposition out of its own object.**
  `the lantern belongs to Mira` extracts to an object with no `to` anywhere in it, so the first
  version of this guard refused every possessor fact in the house. Whether a tell strands a
  preposition is a fact about the SENTENCE he was told, so the guard reads the tell's surface.
- **Irregular table: 16 entries, closed, and deliberately no `-%en` rule** (it mangles `green`,
  `men`, `ten`). A table entry buys nothing on its own -- a variant is emitted only when the stem
  it produces is a verb some TAUGHT TELL actually uses, so the house's inventory decides what can
  be recovered, not the table. `what was the latch broken by?` yields no variant at all, because
  nobody was ever told about breaking; the nearest known action is not an answer.
- **Arm `tools/electric_normalizer_ab.py`** (8 tells, 33 asks -- the ENTIRE object-role table
  replayed plus 13 new rows, so a normalizer that quietly breaks `what bites the latch?` is
  caught here): **recovered 6, regressions 0, confabulations caused 0**; refusals 4/4 identical,
  silence 9/9 identical, `other` 9 -> 3. The pre-existing confabulation `what holds the latch?`
  is unchanged and still reported. A second ISOLATED pass (one fresh organ per ask) confirms the
  same 6 and 0 and separates this flag's effect from the sequence effect of asks being learned
  while they are asked.
- **Guarded contract:** `_absence_licence` still calls `_electric_bind(question, inventory)` on
  defaults -- asserted both behaviourally and at the call site, because a future edit that
  threads `normalize` through would otherwise be invisible until a measured refusal went missing.
  `tests/test_electric.py`'s deliberate signature pin caught the new parameter and was satisfied
  by RECORDING the knob (with `default is False`), not by loosening it. That pin is doing its job.
- **Suite:** 902 collected; the only failure anywhere was that pin.

## ELECTRIC knows a book printed a question (`ELECTRIC_ASK_MARKS`, off by default)

**The bottleneck was one hop wide, and the mark was already recovered.** `_load_next_book`
tokenizes with `c if c.isalnum() else " "`, which destroys the `?` before `row_is_ask`'s token
fallback can ever see it -- but the SAME function already records `_book_is_q` per line off the
RAW text, and `expose_tick` uses it for `learn_qa` and `question_initial` and **nothing else**.
So this is not a recovery, it is a channel: positions of the marks, handed to `hear` beside the
tokens.

- **Why a side channel and not the obvious fix:** putting the mark back on the token would make
  `you` and `you?` different tokens to the binder key, the cue and the concept vector -- it
  re-keys every row he has ever heard. Positions cost the row nothing.
- **Three corpus facts set the design.** 2,687 question lines in 83,537. **1,618 of them (60%)
  are longer than `max_roles = 8`**, so a line becomes several rows: a rule tagging only the
  window the mark physically sat in would leave 60% of a question quotable as a fact. Hence
  `marks_cover`: a mark on the LAST token scopes the utterance, an INTERIOR mark scopes only its
  own window. And `_book_is_q`'s `endswith("?")` misses interior marks outright -- `07_prose`
  15 lines vs 11, `war_and_peace` 339 vs 334; the channel sees those, the boolean cannot.
- **`books/` opens on `01_caregiver.txt`, which contains ZERO `?` characters** -- so do 02, 03,
  04 and 06_stories (36,000 lines). That is the whole reason an earlier audit reported "0 marked
  rows in 60,000". A live check on book 0 measures nothing at all; the arm reads Jane Eyre (382
  question lines) AND a mark-free book, so the zero is reported as a fact about the book rather
  than mistaken for a dead flag.
- **A test caught a real bug, not a test bug.** The delta's 6th element was set by ANY mark, so
  an interior mark widened on replay: `he asked who? and left then went away ...` tagged every
  window after a save (`'left then went away outside the gate today'` went False -> True). The
  boolean now means "this utterance is an asking" -- a TRAILING mark -- and the new 7th element
  carries the positions. An old 6-element delta therefore loses interior tagging, which fails
  toward "not tagged", the pre-channel behaviour, never toward over-tagging.
- **The store is not the mouth.** While building this check a probe fed the utterance as one
  giant token; index 6 was out of range, the junk-position guard rejected it, the row went
  untagged -- and the row-level metric still reported QUOTABLE=0 while the house recited the
  question. `tests/test_electric_ask_marks.py::test_the_tag_reaches_the_hit_dict_the_mouth_reads`
  now pins the propagation through `binder.recall` -> `h["ask"]` -> `_hit_is_ask`, because a tag
  that dies before the hit dict makes every write-side count a lie.
- **The live tool's `dropped` metric read a trace key that does not exist.** Every arm returned
  None, which looked like "no leak" and meant "not measured". It is replaced by `leaked` (he
  spoke, and what he spoke is a row a question line made) and `ask_refused` (the reason the gate
  names itself). The first report's "no probe leaked" was this artifact.

**The leak is real, and the pair closes it -- on the real house.** 400 beats of Jane Eyre, 66
question lines, 117 rows:

| arm | tagged | quotable as fact | LEAKS |
|---|---|---|---|
| A1 nothing on | 0/117 | 117 | **1** |
| A2 admissibility alone | **0/117** | 117 | **1** |
| A3 marks alone | 117/117 | 0 | **1** |
| A4 the pair | 117/117 | 0 | **0** |

The probe was `why have i alluded to this that`, one word off a line the book printed as a
question. A1, A2 and A3 all answer `why have i alluded to this man`, source
`recalled proposition` -- the book's own question, recited as a fact. A4 is silent with the
reason `what he remembers there is only the asking itself`. **A2 is the arm that matters:
admissibility on its own tags nothing from a book and leaks exactly as much as nothing on.** The
gate has no idea what it is looking at until the channel tells it. A3 matters equally: a tag is
not a refusal.

Safety, measured in the same run: rows that exist **1173 / 1173 / 1173 / 1173** (and 206 across
all four arms on the mark-free book) -- the channel renames rows, never makes or loses one; zero
statement rows tagged in any arm; zero question/statement row collisions in this sample; A1 and
A3 speak identically on every probe, so marks alone are inaudible; the two taught asks answer
`hook` and `frost` byte-identically in all four arms. `tools/book_question_marks_live.py`,
evidence in `docs/evidence/book_question_marks_live.json`.

- **`live()` does not feed the channel into `chunk`.** Binding a 14-word book question whole
  stores its first eight words and loses the rest; the channel says what a row IS, not how many
  there are. Pinned at the call site.
- **Read outside `--electric`**, like admissibility and shape: the rows it tags come out of the
  recall path, which runs whatever else is on.
- **Tests:** `tests/test_electric_ask_marks.py`, 15 -- positions, `marks_cover` both directions,
  junk positions rejected, row-set equality against the channel-off organ, delta round-trip
  through `save_delta`/`apply_delta`, the four-arm leak on two lines, the propagation pin, and
  the two source-text wiring pins.
- **Suite:** 915 passed, 3 skipped (902 + the 13 here, then 15 with the leak tests).
- **Guarded contract untouched.** No token is altered. No brain was built.
- **Gaps left open, on purpose:** re-echo does not UPGRADE a tag -- a row first stored as a
  statement stays admissible if it is later heard inside a question (`shared=0` in this sample,
  so it did not bite; the conservative direction is a fact staying a fact). The window step drops
  the tail tokens of a >8-word line (pre-existing, not this flag). A mark-free book gains nothing
  from this channel -- 0 marks there, and that is a fact about `books/`, not about the flag.

## ELECTRIC keeps what a book paired (`ELECTRIC_QA_STORE`, off by default)

`learn_qa` already existed and was nearly inert. Audited before touching it
(`tools/book_qa_learn_audit.py`, 300 beats, `docs/evidence/book_qa_learn_audit.json`): it decides
whether the line under a question is that question with its question-word replaced, then **throws
the pair away** and keeps only a role vote -- `pair LINKED in state = 0/119`. Corpus-wide: 2,687
question lines, every one with a next line, **165 pairs pass the gate, and 164 of them are in the
two books written as Q/A** (`05_questions` 140, `grounded_primer` 24). Across the 16 real novels
the gate accepts **one** pair, and it is not an answer:

```
Might a mere warmint ask what property?     great_expectations L1855
Might a mere warmint ask whose property?    L1856
```

Two Dickens rhetorical questions side by side, passing the arithmetic because `what`->`whose` looks
like a filler. Jane Eyre at 300 beats: 49 pairs attempted, **0 accepted**. So the path is inert on
prose, and the 49 asks on the best-case book that were refused `nothing he remembers has that
shape` had their answer line read directly underneath them.

What the flag adds: the accepted pair is KEPT, with provenance, and answered by exact key.

- **Write** (`_qa_keep`): no provenance, no memory. A question cannot answer a question -- the
  guard reads the mark positions of the NEXT line, and those are built for every book whether or
  not `ELECTRIC_ASK_MARKS` is on, so the safety does not depend on a second flag. First pair wins,
  as in `_taught_says`.
- **Read** (`_qa_store_answer`, in `answer()` **after** the taught path and **before** the absence
  refusal): exact `qa_key`, the ask must end in `?`, and what he says is the answer line word for
  word. A keyed lookup, not a retrieval -- it cannot answer a question it was never paired with.
- **Persistence**: `qa_store` rides in the `questions` blob; on load a record with no provenance
  or no answer is dropped, not resurrected.

Organ A/B (`book_qa_learn_audit.json`, store arm): 05_questions stored **119**, answerable
**70/119 -> 119/119**, right-filler **69 -> 119**, gained 49, **lost 0**, reworded 25 (every reword
is `parent` -> `parent feeds droso`); `grounded_primer` stored 24, **19 -> 24**, lost 0;
`jane_eyre` stored **0**, 0 -> 0.

Live house (`tools/book_qa_store_live.py`, `docs/evidence/book_qa_store_live.json`) -- the real
agent from `world.connectome_house`, flags wired as `serve.py` wires them, saved and booted again:

| book | store | rows (pre-probe) | pairs stored | answered | by store | LEAKS | after restart |
|---|---|---|---|---|---|---|---|
| `05_questions` | off | 303 | 0 | 3/8 | 0 | 0 | 4/8, 0 leaks |
| `05_questions` | on | 303 | **119** | **5/8** | **4** | 0 | 6/8, **119 kept** |
| `jane_eyre` | off | 870 | 0 | 2/6 | 0 | 0 | 4/6, 0 leaks |
| `jane_eyre` | on | 870 | **0** | 2/6 | **0** | 0 | 4/6, 0 leaks |

Both books: rows equal **and row-key sets equal**, leaks `0 -> 0`, the taught asks
(`where is the scarf` -> `the scarf is on the hook`) byte-identical in both arms before and after
restart, and **wherever the store did not answer, the two arms said exactly the same words**. The
Dickens pair, fed to the house verbatim as a two-line excerpt, stores nothing and is not answered
by the store.

Four harness defects this check had to be rebuilt around, each of which moved a number:

- `converse.build(..., project_root=None)` boots against the **live** state: the house came up with
  60,000 rows already in it and every probe measured that. Each house now gets its own empty shadow
  root, which also cut a full save from 20.7s to 1.8s and the whole run to ~2 minutes.
- the "restart" was not one. Saves land in the **session** dir (converse re-points every path after
  construction) while a boot loads from `<project_root>/state`; the first version reported
  `stored_after=0` and the second build silently reloaded the live tree. The restart now copies the
  session files into the shadow's state dir and boots again.
- the session dir was not wiped between runs, so a previous run's files were copied in. That is the
  same contamination that invalidated the first before-audit; its JSON is deleted and the clean
  before-state is the store-off arm of the current one.
- rows were counted **after** probing. Answering writes memory -- six probes added seven rows on Jane
  Eyre -- and the arms showed 877/878 while the store held **nothing** in either. Pre-probe: 870/870
  with equal key sets. Three houses booted in sequence with identical flags (off, off, on) come up
  byte-identical, which is what exonerated the flag.
- one metric was deleted rather than tuned: `echoed_untagged_row` lit up on every correct answer,
  because answering from memory IS saying the text of a stored statement row. What replaced it is
  narrower and claimable: where the store did not answer, both arms must agree.

- **Tests:** `tests/test_electric_qa_store.py`, 17 -- the Dickens refusal, an interior-mark refusal
  (`parent? fed droso`, whose trailing boolean is false), the two-normalizers-agree pin (a store whose
  key and lookup disagree stores forever and answers nothing), restart round-trip, corrupt-record
  drop, row-set equality, taught-before-store precedence.
- **Suite:** 934 passed, 3 skipped, 0 failed (287s), including `test_coverage_exclude_frame.py`
  (12) and the E25 tests whose source-inspection assertions had been breaking in the E26 work --
  this change touches neither, so their passing is not attributable to it and was not chased. (This
  line originally called the E26 gen-23 battery run "still outstanding" -- it is not: generation 23
  exists and its published numbers re-derive from the journal. See the closing record below.)
- **Guarded contract untouched.** No token is altered. No brain was built.
- **Gaps left open, on purpose:** this is not comprehension -- the store answers only the exact key
  of a line pair printed as question/answer, and on the 16 real novels it holds nothing at all. It
  changes the voice on asks that were already answered (`parent` -> `parent feeds droso`): the book's
  own line, but a different utterance than the arbiter's. No eviction -- the store grows with
  accepted pairs and is unbounded per book. And the Dickens house still answers
  `might a mere warmint ask what property?` with `the scarf is on the hook` from
  `recalled proposition`: a taught fact reaching an unrelated ask, pre-existing, printed by the tool
  rather than asserted away.

## Closing the outstanding records (E19, E26) -- and what the recheck found

Both items carried as "pending" were **already closed**; the handover was stale, not the tree. They
were re-verified against their own journals rather than re-run, and the recheck found four errors in
a published evidence file.

**E26 / generation 23: nothing owed.** `state/selection/generation_23_asks.jsonl` is complete (42
rows) and `docs/evidence/e26_user_visible.py`, re-executed this turn, re-derives every published
number from the journal: newly answered **1** (`how often does the bell turn?` -> `the copper bell
turns twice`), newly broken **0**, three `recall` asks crossing into `shape_arbiter`, stage mass
`recall 10 -> 6` / `shape_arbiter 2 -> 5`, total **23/42 -> 24/42**, and abort conditions B1, B2
(4/4), B3 (19/24, `frozen_lost_n` 0), B4, B5, B8 all pass. ACCEPTED stands; the coverage line stays
closed. **Generation 24 is consumed** -- it was the ELECTRIC-on battery run where abort **C3 fired**
(`frozen 19/24 -> 17/24`, net 0, `docs/electric_result.md` section 6b), so the next free generation
is **25**
and `docs/capability_first_plan.md`, which had reserved 24 for its own treatment arm, now says so.

**E19: written, and corrected in place.** The file exists and the run is real -- all 42 rows carry
`attribution` with `taught_resident`/`taught_count`/`taught_rank`/`taught_row`/`taught_rank_cue`.
Recomputing them: **`taught_resident=False` occurs on zero asks, failing or passing. 0 of 19 failures
are eviction. H1 stays falsified** -- the load-bearing claim survives intact. Four things did not:

| claim | published | journal |
|---|---|---|
| `taught_resident` True | 40 of 42 | **39 of 42** (18 failing + 21 passing; 3 are `attribution_failed`) |
| attributed asks where the gate ran | 8 | **9** -- `what does the bitten thing hold?` (cov 0.385) was missing from the table |
| `where did i say the scarf is?` | a gate failure | **passes**; the only passing gate ask of 10, and its `nearest[0]` is `the scarf is wet` |
| gate `nearest` on population (a) | all book | **row at gate rank 1 on 3 of the 4** -- E20's retraction, which section 3's body had not absorbed |

The third was the one that mattered for the guarded line: the scarf ask is not a failure to explain,
it is a refusal-shaped pass whose gate retrieval ranks the taught row first. `docs/evidence/e19_result.md`
now carries these as a Recheck section, with the corrections applied in the body; the same 40/42
figure was quoted in `docs/capability_first_plan.md` section 4 and is fixed there too.

## Next capability-first experiment: E27 -- attack the subject key, do not confirm it

**The measured reason, found this turn.** `_absence_frame` (`organs/neural_language.py:125`) keys a
frame on the **first content word** of the tell. Run against the battery's own taught sentences, that
is what the inventory looks like:

```
the coat is wet                 -> subject 'coat'    rel=property   (right)
the frost bites the latch       -> subject 'frost'   rel=agent      (right)
the scarf is on the hook        -> subject 'scarf'   rel=place      (right)
the copper bell turns twice     -> subject 'copper'  rel=agent      (WRONG KEY)
there are four eggs in the basket -> subject 'four'  rel=agent      (WRONG KEY, and not a quantity frame)
the big copper bell turns twice -> subject 'big'     rel=agent      (an adjective)
the coat is very wet            -> subject 'coat'    rel=agent      (property falls through to agent)
```

Consequence, measured through `_electric_answer` with all three read flags in every combination
(`--electric` enables only TEACH+ANSWER; REVERSE/OBJECT_ROLE/NORMALIZE are separately gated and have
never been on for a battery run): asks naming the *semantic* subject get **no answer** regardless of
flags -- `what turns twice?`, `which thing turns twice?`, `how often does the bell turn?`,
`what number of eggs is left in the basket?`, `what is bitten by the frost?` -- each answers in **0
of 8** combinations. Of the nine asks probed, only 2 answer with the read flags off, and both of
those are the divergence below; `what bites the latch?` answers in 4 of 8, only when `object_role` is
on. Reproducible as `docs/evidence/electric_subject_key_probe.py`.
**SUPERSEDED by the E27 result at the end of this file.** The 0-of-8 figure describes
`_electric_answer` in isolation and was read here as "the organism cannot answer", which is
false: `what turns twice?` is answered `bell` through `arbiter head` and **passes** in gen 24.
The paragraph stands only as a statement about the inventory, not about capability.

**Why the published 20/20 did not show this.** `tools/electric_generalise.py` imports E1's generator,
whose training frame is `the {a} {v} the {b}` -- a **one-word subject by construction**. Position 0 is
the head noun in exactly that template, so the run that certifies ELECTRIC cannot see the defect that
only appears when a subject is modified, quantified, or is not the first word. The 20/20 is depth on
one frame shape, not breadth. The generalisation doc's own next line already asks for a multi-relation
widening; this sharpens it into a target.

**E27, as proposed (measurement only -- no organ change, no flag, no genome, no battery score):**
widen the held-out protocol's *training* templates from the single one-word-subject agent frame to
four shapes -- modified subject (`the copper bell turns twice`), quantified subject
(`there are four eggs in the basket`), multi-word property (`the coat is very wet`), and an ordering
pair -- keeping E1's live-vocabulary draw, its held-out ask frames, and its control arm intact.
Report per-shape treatment vs control. Pre-registered expectation, derived from the extractor rather
than hoped for: one-word-subject shapes hold (~20/20 as today); modified and quantified subjects
**collapse to near zero**, because the key is a modifier or a numeral; multi-word properties fall
through to the agent branch. **If a modified-subject shape scores near the one-word baseline, the
extraction reading above is wrong and that is the interesting result** -- it would mean something
downstream repairs the key, which would change what a repair should be.

**Second half of E27, and it is not optional:** the pure-function probe and the organ **disagree**, and
the disagreement must be resolved before any repair is proposed. Driven by a hand-built inventory,
`_electric_answer` returns `the frost bites the latch` for `what is held by the thing the frost bites?`
(a wrong fact: the answer wanted is what the latch holds) and `the scarf is on the hook` for the
**guarded** `where did i say the scarf is?` -- in all eight flag combinations. The gen-24 journal
shows neither: that ask died at `shape_arbiter`, and the scarf ask produced the spoken *admission*
`i don't know, scarf was told but no place was ever told for scarf`. So the probe bypasses something
the organ does not bypass -- most likely the `_absence_licence` ordering, which the pure read side
never sees. E27 must therefore run the identical inventory through the real `hear()`/`answer()` path
and report where it diverges from the pure function, exactly as E21a recorded its instrument
limitation when `binder.recall` disagreed with the gate's own `nearest`. **Until that is done, neither
disagreement above is claimed as a live defect, and the guarded contract is not claimed to be broken.**
Resolved: the scarf disagreement was **an artifact of a tell the probe invented** (`the scarf is on the
hook` -- the battery never teaches a place for the scarf), and the guarded contract is **not** breached.
The other disagreement was confirmed and is live. See the result section.

**What E27 deliberately is not.** Not `v_all` (a third coverage lever, deprioritised in the plan's section 7).
Not a battery-score target: C3 fired, and the grader scores silence as correct on the scarf ask, so an
organ that answers *or* truthfully admits ignorance can lose points without losing capability
(`docs/scoring_contract_issue.md`, still open -- it is a decision for you, not for me to make by
editing a grader). Not a subject-key fix: that was to be E28, and **E27 measured it away** -- the
mis-keying is real in 20/20 modified-subject tells and costs nothing, so a head-noun rule would not
be a repair. What E27 found instead is in the result section.

**Cost bound:** one tool file widened, one run, zero organ edits, flags untouched, guarded contract
untouched, no multi-brain work.

## E27 RESULT -- run, and the prediction in it was wrong

`tools/electric_shape_generalise.py`, both arms, 300 asks each; analysis
`docs/evidence/e27_shapes_analysis.py`; write-up `docs/evidence/e27_shapes_result.md`.
E1's generator for content words, the **battery's own sentence shapes** for templates, E1's
role-word grader, E1's control arm, a separate organ per shape, live state with **no genome**.
0 of 100 tells were already binder rows and every shape's inventory persisted across restart.
(Finding of the build itself: `len(binder.meta)` cannot be a novelty signal -- the binder is a
fixed-capacity ring, capacity 60000, so it never grows. A first version of the harness reported
"20/20 tells already known" because of this; novelty is now tested against the key `remember()`
builds, `organs/higher_cortex.py:412`.)

| shape | treatment | control | gain | inventory answered | confab T / C |
|---|---|---|---|---|---|
| S0 plain agent (E1's frame) | **60/60** | 40/60 | **+20** | 40/60 | 0 / 20 |
| S1 modified subject | 57/60 | 57/60 | 0 | 20/60 | 0 / 0 |
| S2 quantified existence | 19/60 | 19/60 | 0 | **0/60** | 0 / 0 |
| S3 multi-word property | 12/60 | 12/60 | 0 | 0 taught, 20 refusals | 0 / 0 |
| S4 ordering pair | **0/60** | 0/60 | 0 | **0/60** | 0 / 0 |

**The prediction that failed.** Modified subjects were expected to collapse because the tell is
filed under the modifier. They were filed under the modifier in **20 of 20** tells and scored
57/60, identical to control: the routes carrying that shape (`arbiter head`, `recalled
proposition`) never consult the key. The subject-key defect is real and not load-bearing. E28 as
framed -- a learned head-noun rule replacing position 0 -- would repair something that does not
break anything.

**What the 20/20 actually was.** Not a generalisation result. The taught inventory answers only
the sentence shape it writes; on all four widened shapes ELECTRIC's marginal gain is exactly zero,
and on S2 and S4 the inventory is consulted zero times. The certified frame was the mechanism's
entire domain, and the protocol was built so that it could not show otherwise.

**Where it does break, three different causes.** S2: the number never returns (0/20 on
`what number of {a} is in the {b}?` in both arms), the tell is filed under the numeral with
relation `agent`, so no quantity relation exists to read -- and this survives the write-time
collision confound (9/20 groups lost their tell to repeated numeral keys; over the 11 survivors,
0/11 in both arms). S3: `the {a} is very {v}` is stored as relation `agent`, so both property asks
score 0/20 -- the key is correct here (0/20 mis-keyed), only the relation class is wrong. S4:
ordering is outside the mechanism entirely, `source=None` on all 60 asks, no order field was ever
added.

**The guarded property held everywhere: zero confabulations in treatment on all five shapes.**
Control produced 20 on S0. ELECTRIC's real contribution on its own frame is converting 20 confident
wrong answers into right ones -- worth more than the accuracy delta.

**S3 is where the absence detector shows up, and it costs nothing and gains nothing.** 20 refusals
(`src=electric_absence`) where control gives 20 more silences: it knows the fact was told and says
so out loud without producing it. Accuracy identical in both arms. On a battery that scores silence
as correct for absence asks, that is the `docs/scoring_contract_issue.md` trade-off appearing in
measurement rather than in argument.

**The three read flags change no verdict.** `ELECTRIC_REVERSE`, `ELECTRIC_OBJECT_ROLE`,
`ELECTRIC_ASK_NORMALIZE` were run off and on across the nine divergence asks: not one verdict moved.
Gen 24 ran with all three off and lost nothing; no future run needs them on to recover these asks.

**Divergence resolved** (`docs/evidence/e27_realpath_divergence.py`, `e27_divergence.json`). The
first version of that file was itself wrong three times -- it read the journal with `passed` when the
field is `pass` (every row printed FAIL), it invented its own seven-tell inventory, and it restarted
between teach and ask when the battery does not. Corrected: each script's own tells, asked in one
organ life, pure read / real path / journal side by side.
* The scarf claim was an **artifact of the invented tell**. The battery's `conjunction-and-absence`
  teaches `the coat is wet`, `the coat is on the hook`, `the scarf is wet` and expects refusal because
  no place is ever told for the scarf. Real path: the admission, `src=electric_absence`, matching the
  journal verbatim. **The guarded contract is not breached.**
* `what is held by the thing the frost bites?` is **confirmed live in the shipped configuration**:
  `the frost bites the latch` against `answer=[door] forbid=[frost]`, `src=electric_taught`, read
  flags OFF, real path and journal identical. This is the one place the inventory is demonstrably
  wrong rather than merely unused -- it answers a two-hop composition ask with one stored tell.
* The real path reproduces the journal's pass/fail on **6 of 9** asks. The three mismatches are all
  journal-PASS vs reconstruction-FAIL, and gen 24 ran genome `abffa2b7f101` against this harness's
  unmodified live state. Not resolved, not claimed either way.

## ELECTRIC QA provenance -- the vote cast before the refusal, and the answer that could not be reached

`tools/book_qa_store_audit.py` (four arms, corpus scan, restart, vote-leak probe, hard verdict;
`ELECTRIC_QA_PROVENANCE`, off by default, `--electric-qa-provenance`). 200 beats, evidence in
`docs/evidence/book_qa_store_audit.json`, **9/9 verdict claims hold**.

The task was to measure whether the marks channel makes the book `learn_qa` path acquire pairs.
**It does not, and the path is inert on prose for a reason that should stay.** What the audit found
instead were two ordering defects in the path that was already there.

**Corpus, measured before any organ was built** (24 book files, the pairing rule replayed over
every line pair):

| count | value |
|---|---|
| question lines in the corpus | 2,687 |
| pairs passing the arithmetic on the NEXT line | 165 |
| ... with a 6-line window | 203 |
| ... **real novels only**, next line | **1** |
| ... real novels only, window 6 | **2** |

Jane Eyre 0/382, War and Peace 0/334, Moby Dick 0/251. Every corpus pair comes from the project's
own primer files. The single real pair is *false*: `you don t know the gentlemen here` /
`i don t know the gentlemen here`, where the "answer" **precedes** the question.

**Relaxing adjacency was measured and rejected.** Pairing a question with any line he already holds
as a statement yields **175** pairs corpus-wide (6.5% of questions), and **73 of them have the
"answer" preceding the question** -- both in the evidence file, per book, as `stmt_pass` and
`false_order`. A throwaway probe (`_tmp/qa_coincidence.py`, not committed) showed *how* the extra
pairs are wrong rather than merely sparse: `who carries droso` paired with `droso carries wind`
votes that `who` asks for **role 2** instead of role 0 -- the words are all present, the semantic
roles are inverted. Adjacency is load-bearing. The inertness is correct design, not a bug to fix.

**What the channel contributes to acquisition: zero.** `DELTA stored_pairs = 0` in all three books.
The mechanism: `_qa_keep` already reads the mark positions, and those are built for every book
whether or not `ELECTRIC_ASK_MARKS` is on -- the store's safety never depended on the display flag.
Acquisition is gated on `_book_is_q` (trailing), so the 5 quoted asks the channel alone sees
(`"who shut the door?"`) never attempt a pair at all.

**Defect 1, the vote before the refusal.** `learn_qa` wrote `question_roles`, `interrogatives` and
`answer_types` and incremented `qa_pairs_seen` *before* `_qa_keep` decided the pair was not an
answer. In Dickens the pair `might a mere warmint ask what property?` / `... ask whose property?`
returns `learned: True`, the store keeps **0**, `qa_pairs_seen` says **1**, and the organ is taught
that `what` asks role **5** and is answered by `whose`. `is_interrogative`'s own comment records the
historical damage -- `"sees"` and `"learns"` were "picked up by a mis-paired line".

**Defect 2, the unreachable answer.** Asked `who carries droso` with no typed mark, over the 100
pairs he holds with provenance: **0/100 reached the store**. The sources were `recalled proposition`
38, **silence 38**, `arbiter head` 24 -- and the 38 that came from recall did say the exact printed
line, which is worth stating because it is the honest form of the claim: the words are reachable,
the *provenance* is not, and 38 asks got nothing at all.

**The flag changes one idea in two places** -- a pair the organ itself declares is not an answer
teaches nothing, and a pair with provenance is answerable on that provenance:

- `_qa_admissible(provenance)` factored out of `_qa_keep`; `learn_qa` consults it **before** casting
  the vote. Refusal now returns `learned: False, refused_by_provenance: True`.
- `_qa_store_answer` may answer an unmarked ask only on evidence: the tokens must be **exactly** a
  marked book question already in the store, **and** the word that pair teaches as the interrogative
  must satisfy `is_interrogative` -- learned votes, no table, no similarity, no partial key.

Measured with the flag on: **the same pairs are kept** (100, identical set -- provenance costs no
memory), the refused pair teaches nothing (`pairs_seen 0`, `roles {}`), the unmarked ask is answered
**100/100, from the store, saying the exact printed line**, marked asks are unchanged at 100/100
from the store, and pairs survive a restart answerable 100/100.

- **Tests:** `tests/test_electric_qa_provenance.py`, 18. **Suite: 952 passed, 3 skipped, 0 failed**
  (305s) -- including the 17 `test_electric_qa_store.py` tests, whose store return-dict gained the
  `ask_evidence` key and still passes.
- **Guarded contract untouched.** `_absence_licence` still binds with `_electric_bind(question,
  inventory)` and receives no flags, pinned at the call site, with the store's consult ordered
  **after** the taught path and **before** the licence. No token altered, no brain built.
- **Flag default-off, and the guard is pinned.** `ELECTRIC_QA_PROVENANCE = False`; the store's
  consult is gated on `ELECTRIC_QA_STORE` as before, and the new lookup branch inside
  `_qa_store_answer` returns `None` unless the flag is on, so the off path runs the audited code.
  The flags are **class** attributes (`organs/neural_language.py:2919`), not module globals —
  `hasattr(nl, "ELECTRIC_QA_ELICIT")` is False and a module-level write does not reach the organ,
  so every arm here sets them on the instance. Pinned by
  `test_the_flag_defaults_off_and_is_a_class_attribute` rather than assumed.
- **Gaps left open, on purpose.** The two halves interact: the vote gate removes votes, the lookup
  gate needs `INTERROGATIVE_MIN_VOTES = 2`, so a word whose second vote came from a refused pair
  loses its unmarked answer along with its corruption -- real in the stimulus for `what`, pinned by
  `test_the_two_halves_of_the_flag_do_not_fight` rather than papered over; how often it bites at
  corpus scale is unmeasured. Real novels still feed the store nothing, which is correct. The 5
  quoted asks are still not paired. No eviction. And the Dickens house still answers
  `might a mere warmint ask what property?` with `the scarf is on the hook` from
  `recalled proposition` -- pre-existing, printed by the tool, not asserted away.

## ELECTRIC_QA_ELICIT -- a person can teach him a question

`organs/neural_language.py:2919` (`ELECTRIC_QA_ELICIT`, default **False**),
`tools/serve.py --electric-qa-elicit`, `tests/test_electric_qa_elicit.py` (25),
`tools/qa_elicit_live.py` → `docs/evidence/qa_elicit_live.json`.

The store has only ever held lines he was **READ**, which makes it useless in the one place it was
built for: someone telling him something. This flag pairs a user's marked ask with the very next
thing **that user** said and stores it with `source=conversation`. Three routes, each named:

- **WRITE** (`_qa_elicit`, called first in `respond()` so it sees every turn, including the ones
  that answer a pending ask). A trailing `?` makes a pending ask; the next utterance by the same
  speaker is its only candidate answer, and the **same arithmetic the book path uses** decides
  (`_qa_roles` + `_qa_admissible` + `_qa_keep`) -- no new pairing rule, one substituted trigger.
  A second ask spends the first; `_qa_pending` is deliberately **not** persisted, because a
  half-finished exchange is not a memory.
- **READ** (`_qa_from_conversation`). An unmarked ask may hit the store when the record's provenance
  says a **person** typed that exact question marked -- `ask_evidence="person_marked"`. This is a
  separate route, not a widening of `learned`: the book branch is byte-unchanged and gated on
  `ELECTRIC_QA_PROVENANCE` as before. It has to be separate because the vote arithmetic cannot do
  this work -- one person teaching one pair gives `who` **one** role vote and
  `INTERROGATIVE_MIN_VOTES = 2`, so `is_interrogative("who")` is False on a conversation-only house.
  Pinned as a fact, not argued: `test_the_unmarked_route_is_the_record_not_a_learned_question_word`.
- **ROUTE** (`respond`, :5355). To `answer()` when -- and only when -- the store holds a
  **conversation** pair under that key. `respond` routes on `is_interrogative`, which needs two
  votes, so without this the pair is stored, answerable through `answer`, and unreachable in chat.
  Keyed on records rather than on words, so no ask he has no pair for changes path.

**Measured in the real house, two arms × restart, two houses.** Conversation-only: rows **15/15**
identical across arms, 0 pairs off / 2 on, both elicited asks answered marked (`typed`) and unmarked
(`person_marked`, with the text the person typed). After reading `05_questions`: rows **214/214**,
1 pair on. In both houses, **every ask the flag did not answer from a conversation pair said
byte-identical words with the same refusal in both arms** (10/14 and 16/18 of the probes), before
*and* after restart; the guard still refuses (`lantern was told but no place was ever told`);
leaks **0 → 0**; pairs survive a restart, a hanging ask does not.

**What the live house found rather than confirmed.**

- **A marked ask used to be recorded as a tell, and then answered with its own text.**
  `_absence_note` reads a sentence by position, so `what rings the bell?` landed in `_taught_says`
  under subject `rings`, relation `agent`, value = **the question**. `answer()` consults the taught
  path *before* the store, so the route above handed the ask straight back to the person
  (`src=electric_taught said=what rings the bell?`, counted as a leak 0 → 1). Pre-existing and
  identical in both arms -- invisible before this flag because nothing routed an unlearned unmarked
  ask to `answer()` at all. Closed in `_absence_note`, gated on `ELECTRIC_QA_ELICIT` so every path
  measured earlier is measured the same way. An **unmarked** ask is still noted: without the `?`
  nothing in the sentence says it was a question, and inventing one is not this flag's job -- both
  stated in tests.
- **A person cannot overwrite a pair a book printed first.** House B's `who carries droso?` /
  `parent carries droso` stores **nothing**: first-tell-wins refuses it and the book's line stands.
  Correct by design, asserted as such (`first_tell holds ['who carries droso']`).
- **A row-count difference was the harness, not the flag.** `boot()` zeroed `MIN_HEAR_INTERVAL_S`
  *after* hearing the tells, so which tells produced a row depended on wall-clock (13 vs 15).
  Moved the knobs before the tells; rows are now identical across arms.
- **The guard I first chose was the wrong guard.** `where did i say the scarf is?` is the battery's
  case, and the TELLS this house hears do say the scarf is on the hook -- refusing it would itself
  be the bug. The check now guards an untaught relation (the lantern's place) and separately asserts
  both arms say the same thing about the scarf ask.

**Boundaries kept.** `ELECTRIC_QA_ELICIT` implies no grammar learning from a refused pair (the
`_qa_keep` veto still precedes every vote, and elicit-without-store votes nothing at all); it is not
`ELECTRIC_TEACH`, so a person's answer becomes a stored pair whether or not it also becomes a fact;
it does not widen the book route, and it does not touch the grader. The grader call is
`abs_lic = self._absence_licence(text)` (:4494) with **no flags passed**, and the store's consult
`kept = self._qa_store_answer(text)` (:4491) stays ordered before it -- pinned by
`test_the_grader_contract_and_the_answer_ordering_are_untouched`.

- **Tests:** `tests/test_electric_qa_elicit.py`, 25. **Suite: 977 passed, 3 skipped, 0 failed**
  (322s) -- 952 before this work plus these 25, nothing altered on the way.
- **Still open.** A conversation pair is reachable unmarked only through this route; the `learned`
  vote path is untouched, so a house with the flag off keeps its audited behaviour exactly. No
  eviction, no cap on `qa_store`, and the pending ask lives in memory only. Nothing here ran on the
  battery: generation 25 is still the free one.

## ELECTRIC_QA_PARAPHRASE -- a pair taught in one phrasing answers in another

`organs/neural_language.py:2952` (`ELECTRIC_QA_PARAPHRASE`, default **False**),
`tools/serve.py --electric-qa-paraphrase`, `tests/test_electric_qa_paraphrase.py` (26),
`tools/qa_paraphrase_live.py` → `docs/evidence/qa_paraphrase_live.json`.

`ELECTRIC_QA_ELICIT` keys a taught pair by the exact characters that were typed, so the pair is
reachable in the one phrasing the person happened to use. Measured live before writing anything:
taught `who carries droso?` / `parent carries droso`, then asked `who carries the droso` -- an
article short, the store holding the pair, and the house saying nothing.

The lookup now folds the ask first, using the two pieces of machinery the ELECTRIC read path
already runs for this exact problem rather than a third invention: `organs/stemming.py` -- the
project's ONE stemmer, which exists because three lookups each grew their own -- and
`normalize_ask_variants`, the ask normalizer that turns a passive into the active key the
matchers accept. `ASK_PARAPHRASE_DROP` (:388) is `ASK_NORMALIZE_AUX` plus the three articles: the
words that normalizer already strips, and nothing else. `qa_paraphrase_key` (:3055) is
`qa_key` → drop those → `stem()` each survivor. `_qa_paraphrase_hit` (:3233) is consulted only
after the exact key has missed -- and it re-checks the exact key itself, so a caller that forgets
the ordering cannot let a fold take a pair away from the words it was stored under.

Three bounds, each a test rather than an intention:

- **Provenance, not similarity.** Only records whose provenance says a PERSON typed them with a
  `?` (`source=conversation`, `marked`) are candidates. A pair he was READ is never reached by a
  fold, at any setting of `ELECTRIC_QA_PROVENANCE` -- the book route stays the exact-key route the
  audit measured. House B measures this without being staged for it (below).
- **It may only ever refuse.** The fold keeps WORD ORDER, so `who droso carries` does not meet
  `who carries droso`. A bag of stems would have, and would have answered that ask with the
  first pair's fact -- the audit priced exactly this and called it inverted roles. It also
  under-folds on purpose: `stem()`'s policy is that under-folding refuses a question while
  over-folding gets believed, and everything on this path gets believed.
- **Ambiguity answers nothing.** Two pairs that fold onto one key produce no answer. Choosing
  between them is guessing which lesson the person meant.

**Measured in the real house, two arms x restart, two houses** (control = elicit on, paraphrase
off -- the configuration already committed). House A, conversation only: rows **15/15** and store
keys identical across arms, **9/9** claimed paraphrases recovered with the line the person gave
and `person_paraphrase`/`typed_paraphrase` named in the payload, **0** of them answered from the
store by the control, the 7 refused phrasings refused, and every ask the flag did not answer
byte-identical in both arms before *and* after a real restart; guard still refusing
(`lantern was told but no place was ever told`), leaks **0 → 0**, no ask echoed, probing storing no
pair. House B, after reading `05_questions` at 200 beats: rows **213/213**, keys identical,
**5/9** folded probes eligible -- the four ineligible are the `who carries droso` phrasings, whose
standing record is the book's -- and all 5 recovered, 15/23 asks identical across arms.

**What the live house found rather than confirmed.**

- **The provenance bound is real, not a flag.** The same probe -- `who carries the droso` --
  recovers in house A and gets nothing in house B, decided by the record's `source`, with both
  arms of B agreeing byte for byte. That is the widest form of the claim this feature could have
  quietly broken, and it holds.
- **The control arm was not silent, and that changes what this feature is worth.** Of the 9
  paraphrases, the control produced `recalled proposition` on 3 (the right words, no provenance
  behind them), an `arbiter head` **fragment** on 3 (`parent`, `latch`, `parent` -- a noun, not an
  answer) and nothing at all on 3. So this is not "he could not answer before": it is 9 answers
  with the line he was given and a named source, against 3 fragments, 3 unattributed recalls and
  3 silences.
- **The passive worked on the primer's warrant, not the conversation's.**
  `what was the door held by` reached `what holds the door` because `the latch holds the door` was
  already a taught tell, so `normalize_ask_variants` had the verb it requires and produced the
  variant `what hold the door`. Remove the tell and the variant is never emitted -- pinned in
  `test_the_normalizer_adds_no_variant_without_a_taught_verb`.
- **The under-folds are live too.** `who carried droso` folds to `who carri droso` and does not
  meet `who carry droso`; `who own the lantern` does not meet `who owns the lantern` because the
  shared stemmer's `len(w) <= 4` guard protects `owns`, exactly as it protects `does` from becoming
  `doe`. Both are pinned as refusals. Fixing them means growing `IRREGULAR` in `organs/stemming.py`,
  which is shared with binder postings and with **295 stored procedure signatures** folded by the
  function as it stood when they were written -- its own docstring says grow that map from a
  failure that has actually been seen, not from a list of irregular verbs. That is a separate,
  priced change, not something to slip in under a QA flag.

**Boundaries kept.** No new memory: the fold is derived per lookup and nothing about it is
persisted -- `test_the_fold_adds_no_field_to_the_saved_state` asserts the state doc has no new key
and the store is still under `questions.qa_store`. Probing writes no pair and no extra row:
`test_a_paraphrase_stores_nothing_and_writes_no_more_than_answering_always_did` measures the row
delta against the exact ask that already worked, not against zero, because answering has always
written memory. The guarded grader is untouched -- `_absence_licence` still binds with
`_electric_bind(question, inventory)`, receives no flags, and does not read the store or this
flag; the call site `abs_lic = self._absence_licence(text)` (:4607) is still ordered after the
taught path (:4595) and the store's consult (:4604), pinned as text by
`test_the_grader_contract_is_untouched`.

- **Tests:** `tests/test_electric_qa_paraphrase.py`, 26. Written before the implementation and run
  against it: 18 failed / 8 passed on the first pass, and the 8 that passed were the negative
  tests, which is what passing early means. **Suite: 1003 passed, 3 skipped, 0 failed.**
- **Still open.** A paraphrase of a BOOK pair reaches nothing at any flag setting -- that is the
  bound, but it is also the ceiling: `ELECTRIC_QA_PROVENANCE` + a folded book ask is not
  implemented on purpose. Tense pairs the shared stemmer will not bridge stay refused (above). The
  fold is O(store) per missed lookup, fine at 214 rows and unmeasured at corpus scale. Nothing here
  ran on the battery: generation 25 is still the free one.

## ELECTRIC teach mode -- one switch for the stack that makes a pair teachable

`tools/electric_teach_mode.py` (the table, and the only place the list is written down),
`tools/serve.py --electric-teach`, `tools/electric_chat.py --electric-teach`,
`tests/test_electric_teach_mode.py` (20), `tools/qa_teach_mode_live.py` →
`docs/evidence/qa_teach_mode_live.json`.

Seven flags stood between "he remembers the pair a person gave him" and "he can be talked into
remembering one", each added on its own with its own live measurement; an eighth,
`ELECTRIC_ASK_SHAPE_STORE`, joined later and is documented in its own entry below. The cost of that
honesty is
that anyone who just wants to teach him something has to get the DEPENDENCIES right, because two of
them are inert without another and the symptom of an inert flag is that nothing happens and nothing
is said. `--electric-teach` is those eight plus the three that `--electric` already means, defined
once and read by both wiring sites, with the inertness rules in the same table so `serve.py` and
`electric_chat.py` warn in identical words.

The reason a bundle was safe to add at all is a fact about the stack, not a preference: seven of
the eight can only ever REFUSE to speak or refuse to store -- the store holds pairs the audit already
refused, elicitation routes an ask that was already being typed, the fold answers only from a pair
that exists, provenance narrows admission, marks and admissibility drop remembered questions out of
the hits, the fragment guard replaces a spoken `to?` with silence, the store-shape guard declines an
ask-shaped tell. That is why both guards are IN and
the four WIDENINGS are out: `ELECTRIC_ASK_SHAPE`, `ELECTRIC_REVERSE`, `ELECTRIC_OBJECT_ROLE`,
`ELECTRIC_ASK_NORMALIZE` each let more asks reach more matchers, and each was measured alone
precisely so a run could name which one cost something. `ELECTRIC_ASK_NORMALIZE` looks like an
omission and is not: `ELECTRIC_QA_PARAPHRASE` calls `normalize_ask_variants` itself, so a folded
ask does use the normalizer with that flag off -- but as a LOOKUP KEY into the store, where a wrong
key returns nothing, rather than as a route into the keyed inventory, where a wrong variant returns
a wrong fact.

Everything is set on the instance, never on `NeuralLanguage` (`test_the_mode_sets_nothing_on_the_class`
re-reads every class default after the mode has taught a pair). And the mode implies `--electric`,
which is not cosmetic: `serve.py` runs `load_state()` only inside its `--electric` block, so a server
started with the QA flags and not `--electric` wrote every pair to disk and came back remembering
none.

**Measured in a real house, three arms x restart** (`tools/qa_teach_mode_live.py`; T0 = plain
`--electric`, T1 = the mode through the shipped `enable()`, T2 = the eight flags spelled out by
hand, literally, without reading the table it is checking): T1 and T2 are **byte-identical** on rows,
store keys and every probe reply, before and after a real restart -- the bundle IS the list, not a
new configuration nobody measured. Two elicited pairs answer **6** phrasings from the store with the
line the person gave and the evidence named (`person_marked` on the exact key, `person_paraphrase`
on `what ring the bell` and `what is ringing the bell`); T0 answers **0** of them from a store it
never filled. Rows **9/9** across arms; probing 13 asks taught nothing in any arm (pair count
unchanged); the guarded admission still refuses from `electric_absence`, `lantern was told but no
place was ever told`, in the same words in every arm, after a restart; leaks **0**, no ask echoed.
After the restart the pairs are still answerable in every phrasing the fold reaches, and the held
ask is gone -- by design, and now said out loud: two `--say` calls are two lives, so `electric_chat`
warns on stderr when it exits holding a question, because that silence previously read as a broken
feature.

**What the live check found rather than confirmed -- and what closed it.** `_absence_note`
(`organs/neural_language.py`, cited by function because the line numbers move every time a flag is
documented here) files a frame from ANYTHING it is told, and a question's words yield a frame. A question the house cannot classify is therefore HEARD as a statement and enters
`_taught_says` -- the one store that answers *before* the QA store does. The QA store refuses exactly
this pair (`answer_is_question`, the Dickens warmint case); the taught inventory had no counterpart.
Measured across four states, as the check first recorded them -- the same table now runs six rows,
and the four below are the guard-off half of it:

| arm | elicited pairs | `what` votes | filed as a tell | what the house said to `what rings the bell` |
|---|---|---|---|---|
| control | 1 | 0/2 | yes | nothing -- it never classified the ask |
| control | 2 | 0/2 | yes | nothing |
| mode | 1 | 1/2 | yes | **`what rings the bell twice`** (`electric_taught`) |
| mode | 2 | 2/2 | no | `the copper bell rings` (`electric_qa_store`) |

So the filing is universal and pre-existing, but only a house that has since learned the word can be
CAUGHT by it -- and the control arm's safety there is not safety, it is the same inability to answer
anything. The mode's own second pair closes it on its own: the word earns its two role votes, the ask
routes to `answer()` instead of being heard, and there is no frame left to file.

Two candidate repairs were measured before either was built. `ELECTRIC_ASK_SHAPE` does not
close it: with the flag on, both rows are tagged `row_is_ask=True` and the reply still comes from
`electric_taught`, because admissibility and shape are cortex-row concepts while `_taught_says` is a
different store. A guard at the write site does close it, and that is what shipped, as
`ELECTRIC_ASK_SHAPE_STORE` -- its own entry below, because it narrows a write path the graded E24
work owns and that deserves a measurement of its own rather than a paragraph here. The reason it was
NOT built at the time is recorded and still true: `question_shape` mis-fires on relative clauses --
the row tagger already had to learn that, which is why it declines past the binder's `max_roles` cap
-- and declining a WRITE loses a fact silently, which is worse than losing one lookup. That cost is
now measured instead of assumed (see the entry below). `_absence_inv` -- the grader's input -- is
untouched by the mode, by the guard, and by this document.

The pins moved with the fix and were not deleted. `test_pinned_an_unclassified_ask_is_filed_as_tell`
and `test_pinned_the_store_refuses_what_the_inventory_files` now run in the configuration they were
measured in, with the guard forced off, and each has a sibling asserting the closure
(`test_the_mode_as_it_ships_refuses_the_filing_that_used_to_answer_itself`,
`test_the_guard_removes_the_disagreement_it_was_pinned_for`);
`test_pinned_the_learned_word_closes_the_filing` asserts in both arms, because the mode's own
self-repair and the write-site guard are now two mechanisms that have to agree. The live table is six
rows -- control x2, mode x2 with the guard off, mode x2 with it on -- so the closure is attributed to
the switch and not to the bundle around it.

- **Tests:** `tests/test_electric_teach_mode.py`, 20 -- the table (exactly the stack and the base,
  the four widenings off, nothing written to the class), what it buys (a pair the control cannot
  teach, a paraphrase with its evidence named, the second pair earning the word), what it must not
  cost (the guarded admission identical in both arms, the same four utterances writing the same
  number of rows), the inert-flag warnings walked up the whole chain (paraphrase → elicitation →
  store: clearing one parent only moves the warning), and the CLI: `--electric-teach` implying
  `--electric`, `--no-electric --electric-teach` refusing to pretend it is the control arm, and a
  pair taught over HTTP, `/shutdown`, then answered in other words by a second process that shared
  nothing but the state file. **Suite: 1021 passed, 3 skipped in 376.28s, exit 0**
(`_tmp/suite_full2.log`), run after the teach-mode tests and the serve.py guard fix landed; the
last recorded figure was 1003 passed, 3 skipped at the end of the E27 entry. One edit came after
the run started -- the live tool's opening docstring line, which no test reads.
- **Still open.** The write-site guard shipped, but the frame a question yields still lands in
  `_absence_inv`, which is the graded licence's input: the guard declines the SENTENCE as an answer,
  not the inventory entry, and whether a question-shaped frame should ever license a refusal is E24's
  question rather than this flag's, so it is deliberately untested here. A house that has not earned
  a question word also stays exposed for that word in every store that reads rows rather than the
  taught inventory. The `teach` member of `serve.py`'s payload appears only
  under the mode, so the `--electric` wire format is unchanged for every run that did not ask for
  teach mode -- and nothing in the mode has been run on the battery.

## ELECTRIC_ASK_SHAPE_STORE -- shape authority at the `_taught_says` write

`organs/neural_language.py` (the flag, and `_shape_files_as_ask`), `tools/serve.py
--electric-ask-shape-store`, `tools/electric_chat.py --electric-ask-shape-store`,
`tests/test_electric_ask_shape_store.py` (22), `tools/qa_teach_hole_live.py` →
`docs/evidence/qa_teach_hole_live.json`. Eighth member of `--electric-teach`.

The hole itself, and why it was pinned a session before it was repaired, are in the entry above.
What shipped is one line at the write site, placed AFTER the graded one: `_absence_note` extracts
the frame and records it in `_absence_inv` -- that is E24's write and nothing here touches it -- and
only then asks the tell's own SHAPE whether the sentence should be kept as an answer. The detector is
the one the row tagger already uses (`question_shape`, the arbiter's closed set, the binder's own
`max_roles` cap), so the guard invents no vocabulary of its own, and it is wrapped to fail OPEN in
every direction: no tokens, no binder, a throwing tokenizer, a throwing detector -- all four answer
"not an ask" and leave the write exactly where it was before this method existed. A guard that can
delete a fact by crashing is worse than the hole it closes, and that is a test, not a preference.

**What it buys**, measured in a real house (`tools/qa_teach_mode_live.py` section 6, six rows now):
the mode at one elicited pair used to answer `what rings the bell` with `what rings the bell twice`;
with the flag on the same house declines the filing and answers `the copper bell rings` from the
store. The control arm is unchanged, the mode at two pairs is unchanged, and the two arms' flag sets
differ by exactly one name -- which is why the closure is credited to the switch and not to the
bundle around it.

**What it costs**, measured rather than argued (`tools/qa_teach_hole_live.py`, one house per arm,
the same battery told twice):

| line told to the house | shape verdict | filed, guard off | filed, guard on |
|---|---|---|---|
| `the copper bell rings` | False | yes | yes |
| `droso keeps the lantern in the pantry` | False | yes | yes |
| `where the river bends the reed grows tall` | False | yes | yes |
| `who sacrificed everything for him chimed in the ledger` | past the cap | yes | yes |
| `what the loop does at midnight surprises the clerk` | past the cap | yes | yes |
| `the bell that rings at midnight keeps the gate` | past the cap | yes | yes |
| `who rings the bell keeps the gate` | **True** | yes | **no** |

Rows written 8 == 8, `_absence_inv` identical (15 subjects), the licensed refusal identical in
wording and source. The declined line is the residual `question_shape` cannot separate -- a SHORT
free relative is shape-identical to the ask `who rings the bell` -- and what it loses is the PAIR
only: the cortex row and the inventory entry survive, and the frame the other arm filed was
`('agent','rings','bell keeps gate')`, a subject slot holding the verb, which is the same misparse
the hole is made of. The cap is the binder's: `max_roles` is 8 in a real house, and the three lines
past it are left alone because the row tagger leaves them alone. Lower the cap in a unit test and the
guard's cap moves with it -- asserted, so nobody can later harden this by inventing a length.

**And one effect nobody predicted, which is the reason the check exists at all.** The guard is not
pure subtraction; it can change WHICH STORE answers. With the residual filed under `subj='rings'` the
ask `what rings the bell` has two candidate subjects, `_electric_bind` rejects the ambiguity and
returns None, and the QA store answers `the copper bell rings`. With the residual declined the bind
resolves cleanly to `bell`, and the house speaks `the bell that rings at midnight keeps the gate` -- a
tell the person actually said, verbatim, keyed. Deleting a wrong entry made a right one reachable, so
the assertion that survives is the one the contract needs: the reply is a sentence the house was told,
and it is not itself a question. Recorded in the evidence file as `unmasking_note`, printed in the
run's own output.

Two wiring findings, both small and both real:

* `--electric` was never an option of `electric_chat.py`: argparse resolved it as a PREFIX of
  `--electric-teach`, so typing the ELECTRIC switch got you the whole teach stack and left you no say
  in it. Adding a second `--electric-*` option would have turned that same typing into an ambiguity
  error, which is its own regression, so the exact name is now declared: it affirms the default,
  changes nothing, and loses to `--no-electric` in a conflict -- an affirmation of what is already on
  carries no information, and the control arm is the one request that does. Pinned, together with the
  fact that `serve.py` always had the exact name and did not move.
* In `serve.py` the flag must be wired INSIDE the `if args.electric:` block and AFTER
  `ELECTRIC_TEACH = True`, as `bool(args.electric_ask_shape_store) or teach`. Outside that block the
  inert-flag warning would claim a flag was live in an organ with no teach path at all; before that
  line a bare `bool()` would switch the mode's own fix back off. Both orderings are asserted against
  the file's text, because both failures are silent.

- **Tests:** `tests/test_electric_ask_shape_store.py`, 22 -- the hole reproduced with the guard off
  and closed with it on, the closing attributed to the one switch; statements and relative clauses
  still filed; the cap proved to be the binder's; fail-open on all four failure modes; the residual
  declined with its row and inventory entry surviving; rows, pairs, inventory and the licence's reason
  words identical between arms; the CLI in three arms plus the `--electric` prefix.
  `tests/test_electric_teach_mode.py` 18 → 20 (the three pinned hole tests kept in the configuration
  they were measured in, guard forced off, each with a sibling asserting the closure).
  **Suite: 1045 passed, 3 skipped, 0 failed in 417.09s, exit 0.** The arithmetic is the check: the
  figure one entry above (the `--electric-teach` run itself) was **1021 passed, 3 skipped**, and this
  work adds exactly 24 tests: 22 in the new `tests/test_electric_ask_shape_store.py`, and 2 in
  `tests/test_electric_teach_mode.py` (18 → 20, counted against `git show HEAD` rather than
  remembered -- the two closure siblings that stand beside the three `test_pinned_*` tests they
  reverse; `test_electric_fragment_guard.py` is 8 at HEAD and 8 now, so nothing moved out of it).
  1021 + 24 = 1045. A number that does not reconcile with what was added is a number someone counted
  off a different tree. The committed tree was then run again and returned the same figure
  (**1045 passed, 3 skipped, 0 failed in 415.91s**), so the flake below has now failed to appear in
  two consecutive clean full runs and one clean neighbourhood run -- three processes, not one.

  **A green run is a claim about a tree, not about code.** Two full runs of this work failed, and
  neither failure was a behaviour change. The first (5 failures, all `inspect.getsource` call-site
  pins -- `answer`, `_qa_keep`, `qa_paraphrase_key`) happened because I edited
  `organs/neural_language.py` *while the suite was running*: `getsource` maps a code object's line
  numbers onto the file on disk, so the imported module carried offsets into a copy of the file that
  no longer existed and each slice landed on its neighbour -- the `_qa_keep` pin failed on text that
  lives in `_qa_admissible`, sixteen lines above it, and the paraphrase pin returned `qa_key`'s body.
  All five passed in 1.33s on the settled tree with no code change; the pin that guards the graded
  contract is one of the five, which is the reassurance the constraint needed.
  The second was `test_the_guard_returns_the_licensed_absence_instead_of_the_fragment` in
  `test_electric_fragment_guard.py`, which has not reproduced: green in the 87-test electric neighbourhood,
  green 15/15 as a single test across 15 fresh hash seeds, green in the full suite. Its own guard is
  off by default, and its ONE call site is inside `_absence_note` (grep finds two hits in the organ:
  the method and that line), which that test reaches only with the flag False; no test file in
  `tests/` writes a class-level `ELECTRIC_*` default (grepped), and `tools/electric_reverse_ab.py`
  sets only TEACH/ANSWER/REVERSE on the instance. So there is no path from this work to that row.
  **Recorded as unexplained,
  not as not-a-problem**: the file's own header says this row is process-nondeterministic, and the
  evidence is only that it has not been seen twice.
- **Still open.** Whether a question-shaped frame should license a refusal at all -- that is E24's
  input and this flag deliberately leaves it. The residual class above, and the unmasking effect, are
  costs of the shape detector, not of this write site: any guard built from `question_shape` inherits
  both. Nothing here has been run on the battery; generation 25 is still the free one.

## ELECTRIC_LEARN -- one flag for the FULL teach/learn mode, and the restart that proved nothing

**What landed.** `--electric-learn`, in `tools/serve.py` and `tools/electric_chat.py`, is
`LEARN = STACK + EXCLUDED` in `tools/electric_teach_mode.py`: the eight-flag teachable stack, the
three flags `--electric` already means, **and** the four widenings teach mode was built to refuse
(`ELECTRIC_ASK_SHAPE`, `ELECTRIC_REVERSE`, `ELECTRIC_OBJECT_ROLE`, `ELECTRIC_ASK_NORMALIZE`).
Fifteen switches, one list, one table, both doors. `enable_learn()` goes through a new `_set()`
with `enable()`, and `_set()` checks every name against the **class** before setting any of them.
That check is not tidiness: `setattr` on an instance accepts *any* name, so the sentence `enable()`
used to claim -- "a typo'd attribute would raise here rather than silently do nothing" -- was false.
A mode that turns on fifteen switches must not be able to report fifteen and behave like eleven.

**Why a second mode flag and not a wider default.** The two halves have opposite polarity. The
stack can only ever **refuse**: a row dropped from the evidence, a fragment left unspoken, a write
declined. The four widenings can only ever **reach more**: more rows counted as an asking, more asks
matched against the keyed inventory, more phrasings folded onto one key. Combining them is the
configuration where an interaction is most likely and least attributable, and each of the four was
measured alone precisely so a run could say which one cost something. So the combination is
nameable, off by default, and announced in its own banner line rather than folded into `teach=on`.

**The live house, three arms, one script** (`tools/electric_learn_live.py` ->
`docs/evidence/electric_learn_live.json`; 4s per arm, 14 rows in every arm -- the mode wrote no
extra row). `[live / source / after a real restart]`:

| ask | control | teach | **learn** |
|---|---|---|---|
| `what ring the bell` (the stemmer's fold) | — / — / — | the copper bell rings / qa_store / **yes** | the copper bell rings / qa_store / **yes** |
| `what bites the latch` (object-role) | `dog` / arbiter head / `dog` | `dog` / arbiter head / `dog` | **the dog bites the latch** / electric_taught / **yes** |
| `who does the lantern belong to` (reverse) | — / — / `mira` | — / — / `mira` | **the lantern belongs to Mira** / electric_taught / **yes** |
| `where is the moon` (untaught) | — | — | — |
| the stranded-ask fragment | never spoke | never spoke | never spoke |

Two things that table says and the unit tests could not. First, the buy is **a sentence rather than
a word**: without the widenings the house answers an object-role ask with `dog`, lifted out of a
tell it was given by the shape arbiter, and the full mode answers it with the tell, verbatim, from
the keyed inventory. Nothing was invented in any arm -- every reply is a sentence from the taught
set or a word inside one, and that is the invariant four widenings are allowed to share.

Second, and it needed correcting in this file the same day it was written: **the narrow arms answer
`mira` after a restart and nothing before it** -- live, `control` and `teach` say nothing to the
reverse ask; restarted, both lift `mira` out of the tell. The first draft of this note explained
that as the reload handing the arbiter a filler. **That explanation is wrong, and the way it was
found out is the reason it is recorded.** `tools/electric_restart_qrow.py` (evidence:
`docs/evidence/electric_restart_qrow.json`) runs the factors apart: the unrelated remembered
question row, the restart, and the three earlier asks, in every combination -- 24 cells, control
and teach. **`mira` appeared in none of them.** Every cell refused, at 0%, 50% or 53% coverage.
What does reproduce it is the learn-live tool's own sequence, run as a replica in the same file:
`ask_all` in the taught life (six probes, then the `who does the mouse chase to` line, then the
answer to the bare form), save, restart, `ask_all` again -- control and teach refuse live and
answer `mira` restarted, learn answers the verbatim tell in both phases.

So the trigger is an **accumulation of remembered questions**, not a restart and not a row:
enough question-shaped rows in one pool let a *different* question clear the coverage gate, and
once the gate is open the shape arbiter parses the preposition as the verb
(`{"kind": "object_unknown", "subject": ["lantern"], "verb": "to", "tail": []}`, verdict `agree`)
and lifts the object out of the tell. Three consequences worth keeping:

* **Pre-existing, not learn mode.** The replica reproduces it in the CONTROL arm, where no ELECTRIC
  flag is on at all, and this task edited zero lines of `organs/neural_language.py`
  (`git diff --stat HEAD -- organs/` is empty). Learn mode does not cause it and is not bitten by
  it: in all 24 grid cells and both replica phases the full mode answers that ask with the whole
  tell from the keyed inventory, so the one-word path is never reached.
* **Not an admissibility hole either.** In the teach replica `ask_hits_dropped` is 0 -- the flag was
  on and did not intercept this, because the row that opens the gate is not the row that answers:
  the gate is upstream of admissibility and the arbiter is downstream of both. Whether the gate
  should count a remembered question toward covering a question is E27's neighbourhood, not this
  mode's.
* **Not an invention.** `Mira` is who the lantern belongs to. The defect is reachability and
  terseness -- a correct answer that takes 25 configurations to become reachable, and arrives as
  one word instead of the sentence the person said.

Two more things this file says that the earlier draft did not: `is_interrogative("who")` is **False
in every arm, every phase** (`interrogative_who_anywhere: false`; `question_roles` is `[]` in
control and `['what']` in teach/learn), so the filter at `answer()`'s retrieval stage that is
supposed to keep remembered questions out of the pool never fires for `who` in a house like this
one -- role votes are earned only from a `?`-marked line paired with an answer, and every probe
here is unmarked. And the control arm's restart was itself a bug in the harness: `load_state()` was
skipped for control on the reasoning that a flagless house has nothing to load, which is exactly
where a wrong boot hides, so all three arms now load and an arm that loads nothing fails the run.

**The harness bug this found, and why it matters more than the result.** The first two runs reported
that learn mode lost every taught fact across a restart. It did not: `converse.build` comes up with
`persist` off and never calls `load_state()`, so the "restarted" house was booting from an empty
state dir and answering from nothing. The fix is in the tool (`lang.persist = True`, an explicit
`save_state(force=True)`, then `load_state()` on the second boot) **and an invariant**: an arm that
loaded no state now *fails the run* instead of printing empty cells. A restart arm that proves
nothing is worse than no restart arm, because it reads like evidence.

**What is still true and unchanged.** Every attribute is set on the instance, never on
`NeuralLanguage`; `_absence_licence` binds on the class defaults and the graded contract is
untouched (`tests/test_electric_learn_mode.py` compares the class against a snapshot taken at
import, before any organ exists), and `git diff --stat HEAD -- organs/` for this work is **empty**
-- the claim is a file list, not a recollection. `--electric-teach` still refuses the widenings (five
of them as of `ELECTRIC_ASK_DO_SUPPORT`, and the count is read from the table, not written into the
test), and the two modes differ by exactly those -- asserted, not by reading the tables but by
diffing the state of two organs built through them. Nothing here has been run on the battery.

**Numbers at this commit.** `1062 passed, 3 skipped, 0 failed in 458.97s` -- 1045 at the
`ELECTRIC_ASK_SHAPE_STORE` commit plus the 17 tests in `tests/test_electric_learn_mode.py`, the
arithmetic checked rather than assumed, and the suite run on a settled tree with no file edited
while it ran (that is the mistake that produced the five phantom `inspect.getsource` failures two
tasks back). The electric neighbourhood by itself is 267 passed in 5:08, which is the number to
re-run when only a flag table moved. `tools/electric_learn_live.py` costs 4.1-4.5s per arm and
`tools/electric_restart_qrow.py` 62.9s for 24 cells plus 3 replicas; both exit non-zero on a
failure rather than printing an empty cell, and both wrote the evidence files cited above.

## ELECTRIC_ASK_DO_SUPPORT -- the QA gap decomposed by mechanism, and the largest class closed by one word

**The instrument.** `tools/electric_learn_bench.py` (new, ~11 min, 9 houses, evidence
`docs/evidence/electric_learn_bench.json`). `electric_learn_live.py` proved a wiring with four tells
and two pairs; this asks the scale question. A curriculum of **24 tells and 16 question-answer
pairs (40 items)** taught in **three sessions with a restart between every session**, then asked back
in **136 generated probes** -- subject, subject-with-the-inflection-folded, object, object-with-the-
auxiliary-dropped, reverse, reverse-folded, pair-exact, pair-folded -- plus **12 distractors** that
are never taught, six of them role swaps built only out of words the house knows. Three arms
(control / teach / learn) x three depths x three phases.

**The measurement trap, defused before it could produce a finding.** Asking writes a row, and the
previous task established that a pool of remembered question rows changes what a narrow house
answers -- so a benchmark that probes one house six times measures its own probing. The state is
saved **before** the live probe round, so the restarted house loads the taught state with no probe
rows in it; that house is then probed a second time after its own 136 probe rows accumulate, and the
delta between the two columns is printed as the artifact rather than buried. In learn at depth 3 it
moved **exactly one probe** (a refusal became an echo) and the 79 correct did not move.

**Retention across a restart is perfect, and that is the number the mode needed.** Probes gained on
restart 0, probes lost on restart 0, at every depth, in both ELECTRIC arms (teach 14/27/39 correct,
learn 28/52/79 -- identical live and restarted). Every failure in the tables below was a failure
before the house went down. The remembered-question artifact from the last task is real, but it is
not forgetting.

**The floor holds at scale.** No arm said a sentence nobody said, at any depth, in any phase --
which is also what the first draft of the classifier contradicted, until three behaviours were named
apart: the **licensed refusal speaking** (`i don't know, bell was told but no place was ever told
for bell`, source `electric_absence`) is a refusal and not a fabrication; **control answering
`what the dog guard` with the bare word `what`** is the question word falling out of a parse; and an
item not yet taught, answered correctly from a tell the house does have, is the mode working. All
three had been counted as confabulation, which is how a benchmark reported 16 inventions in an arm
with no ELECTRIC flag on at all.

**False acceptance, measured against the largest sample this repo has.** At depth 1, 97 of the 136
probes ask about items that will not be taught for one or two more sessions: refused 89, answered
correctly from a tell already in the house 4, handed a question back 3, **mis-answered 1**. That one
is `what chases the mouse` -> `the mouse chases the dog` -- the opposite direction of a tell, in both
ELECTRIC arms, at every depth, in every phase. Stable enough to be a signature, and a mechanism
rather than a fluke.

**THE DECOMPOSITION.** Every failing probe is classified by which part of the pipeline did not do
its job, and every branch is an observable in the evidence -- the store's own keys, the organ's own
`qa_key`, its `qa_paraphrase_key` -- not a reading of the organ. Learn mode, depth 3, the clean
restarted house, 124 probes about things it was told:

| mechanism | probes | what it means |
|---|---|---|
| **ask_not_recognized** | **20** | 19 `object_fold` + 1 `reverse_fold`, every one refusing with *nothing he remembers has that shape* |
| pair_never_admitted | 10 | 5 pairs x 2 probes. A **write** loss, upstream of every read-path flag |
| fallback_fragment | 8 | a word or a question came out (`arbiter head`, `recalled proposition`) |
| refusal_silence | 4 | coverage near-miss, reverse asks |
| key_shadowed | 3 | the store held the exact key and the inventory spoke a different tell |

The QA-store probes on their own (32): answered 19, pair_never_admitted 10, key_shadowed 2,
fallback_fragment 1. **The largest class was one word wide**: `what does the dog bite` returns its
tell verbatim 17 times in 21, and the same ask with the auxiliary dropped returns nothing 19 times
in 21.

**THE FIX.** `ELECTRIC_ASK_DO_SUPPORT` (class default **False**), `_do_support_variant(toks, says)`.
It inserts the one word English requires -- `what the dog bite` -> `what does the dog bite` -- and
nothing else. The warrant is two keyed facts from **one** tell: some sentence this house was actually
told must carry the ask's noun as its SUBJECT and the ask's verb as its ACTION, both read out of
`_absence_frame`, the extractor the absence licence already uses. `what the moon bite` matches a
moon tell and a bite verb separately and gets no variant, because no tell says the moon bit anything.
A stranded preposition stays where the person put it (`who the lantern belong to` -> `who does the
lantern belong to`), because the reverse path is keyed on it. What comes back is still a verbatim
taught tell: the fold widens **which ask reaches the matcher** and never touches what the matcher may
say -- `test_everything_the_fold_says_is_a_sentence_it_was_told` states that as a sweep.

It is a **fifth widening**, so `--electric-teach` still refuses it and `--electric-learn` is the mode
that has it (seventeen switches now, one table). It is **inert without `ELECTRIC_ASK_NORMALIZE`**,
because the variant is generated inside that block, and `DEPENDS_ON` says so out loud rather than
letting a flag that does nothing be reported as one that does. And because `normalize_ask_variants`
is *also* the store's paraphrase key -- a path in the teach stack -- the fold is a **parameter**, not
an addition to the default list: `normalize_ask_variants(q, says)` returns exactly what it returned
before this flag existed, pinned by a test that compares the passive case with and without.

**POST-FIX, same instrument, same curriculum, same phase (the clean restarted house at depth 3).**
Learn mode went from **79 to 98 correct of 124** taught probes, refused 30 -> **11**, and
`object_fold` from **0/21 to 17/21**; `reverse_fold` 0/2 -> 1/2. The mechanism column moved exactly
where the flag reaches and nowhere else: `ask_not_recognized` **20 -> 4**, while
`pair_never_admitted` 10 -> 9, `fallback_fragment` 8 -> 8, `key_shadowed` 3 -> 3, `refusal_silence`
4 -> 2. Per item, **kept on every probe went 10 -> 28** (part 23 -> 5, lost 7 -> 7) -- the mode
answers the shape it was taught in *and* now most of the shapes it wasn't. The QA-store probes
themselves barely moved (19 -> 20 answered), because this class was never about the store.

**Nothing else moved, which is the half of the result that matters.** The teach arm is identical to
the pre-fix run -- 39 correct, `object_fold` 0/21, all 21 refused -- so the widening is really behind
the flag and the counterfactual survived. Control is identical (0 correct, 83 partial). **Invented:
0 in every arm, every depth, every phase** (the tool's own floor, exit 0). Restart cost is still
exactly nothing: learn live 35/65/98 equals restarted 35/65/98, gained 0 and lost 0 at every depth in
both ELECTRIC arms. Re-probing the house a second time still moves one probe (correct 98 -> 98).

**False acceptance did not grow, and the number is now stated per cell.** Untaught probes answered
with a sentence they were told: **exactly one ask, `what chases the mouse` -> `the mouse chases the
dog`, in teach and in learn, at all three depths, in all three phases -- 18 cells, the same fault,
and zero in control.** It is not caused by this flag (it predates it in the same run) and it is not
a fluke (it is the only one, and it is always that one). Learn's depth-1 sample, where 97 of the 136
probes ask about items taught later: refused 89, entailed-correct 4, echo 3, misattrib 1.

**The 4 that remain are two named things, not a mystery.** `what the nora carry`,
`what the bridge cross`, `what the net catch` fail the warrant because `_verb_stem` under-folds the
`-ies`/`-es` class: it gives `bites -> bite`, `holds -> hold`, `guards -> guard` correctly, but
`carries -> carrie`, `crosses -> crosse`, `catches -> catche`, none of which equals the bare stem the
ask uses (`carry`, `cross`, `catch`) -- and it over-folds `cross -> cros` on the way. The fourth,
`what the dog guard`, is correct behaviour for a broken inventory: no tell in the house pairs dog
with guard, because `the dog bites the latch` already owns the (subject `dog`, relation `agent`) key
and `_taught_says` keeps one tell per key. **Neither is fixed here on purpose.** The stemmer is
shared by the binders, the paraphrase key and the absence frame -- widening it is a change to every
path at once, which is the opposite of a flag-gated one-class fix, and the second is a write-side
collision that needs its own measurement. They are recorded as the next two candidates, in that
order, with the numbers above as the baseline to beat.

**A WIRING BUG FOUND ON THE WAY, and it is the bigger half of this entry.** `tools/serve.py` applies
the mode table and *then* assigns its individual switches from argparse as `= bool(args.x)`. Three of
the four widenings were on the wrong side of that order, so `--electric --electric-learn` set
`ELECTRIC_REVERSE`, `ELECTRIC_OBJECT_ROLE` and `ELECTRIC_ASK_NORMALIZE` back to **False**: the widest
mode ran as teach mode plus one, and the banner printed the user's intent (`reverse={args...}`)
instead of the organ's state, so nothing said so. `--electric-learn` without `--electric-teach` was
worse: the `if teach:` guard skipped the whole `--electric` block, which is where `load_state()`
lives, so the mode that teaches the most came up amnesiac while its own help text claimed it implied
the flag whose code it had not run. Both are fixed -- `or learn` on each widening, `or teach or
learn` on the store guard, `if teach or learn:` -- and the banner reads the organ. This is the failure
this project keeps hitting, named in `tools/electric_teach_mode.py` as the reason the table exists:
**a rule duplicated in a second wiring site drifts, and the drift is silent.**
`test_no_door_switches_a_mode_flag_back_off` is the guard.

**WHAT THIS DID NOT FIX, and why that is the honest order.** `pair_never_admitted` (10 probes, 6 of
16 taught pairs) is `learn_qa`'s admission arithmetic -- a pair is kept only when the answer differs
from the ask by **exactly one word on each side** -- and the store inherits a rule that was written to
learn *which role a question word asks about*, not to remember a lesson. Spot check on pairs a person
would actually say: `where does the bell hang? / the bell hangs on the wall` refused (3 missing, 3
new), `who fed the mouse? / Mira fed the mouse last night` refused. **An answer that tells you
something new is unteachable by construction**, which is why 0 of the 3 pair-only items -- the only
sentences in the house that live nowhere else -- ever reach the store. `key_shadowed` (3) is the
ordering in `answer()`: the keyed inventory is consulted one step before the store, so an exactly
taught pair loses to a shape-matched tell. `shadow()` proves it in three houses and one ask: with
only `the rope holds the shelf` the answer is right; add the unrelated `the shelf holds the lamp` and
the same ask returns *that*, and in a third house where the competitor is the only tell it still
does -- which rules out "the tell beat the pair" and leaves "the pair was never reached", while all
three houses hold the right sentence under the exact key. Neither is touched here: one fix per class,
and both live in the graded organ's read/write paths.

**The contract, stated as a file list.** This task **did** edit `organs/neural_language.py`, unlike
the last two, so the claim has to be narrower and exact: four call sites changed
(`_do_support_variant` is new, `normalize_ask_variants` gained a keyword-only parameter with the
default list byte-identical, `_electric_answer` threads it, `answer()` reads the instance flag) and
one class attribute was added with default `False`. `_absence_licence`, `ABSENCE_INVENTORY`,
`ELECTRIC_TEACH` and `ELECTRIC_ANSWER` are untouched, the new flag is off on the class, and
`tests/test_electric_ask_do_support.py` compares the whole class against a snapshot taken at import
before any organ exists. Nothing was run on the battery.

**Tests added.** `tests/test_electric_ask_do_support.py` (11: the on/off A/B on one organ, the
no-warrant sweep, verbatim-or-nothing, the stranded preposition, the unchanged default variant list,
inertness plus the warning that names it, the table's own bookkeeping, the serve.py wiring guard, and
the benchmark taxonomy pinned so `ask_not_recognized` and `pair_never_admitted` cannot silently swap)
and `tests/test_electric_learn_bench.py` (18, all pure-function and under a second: the curriculum's
size and integrity, no distractor answerable by any tell, the three pair-only items named, probe
vocabulary checked against the curriculum's own words rather than the organ's stemmer -- and every
classifier class, because a benchmark whose classes are wrong measures its own vocabulary).

**Numbers at this commit.** `1091 passed, 3 skipped, 0 failed in 466.76s` -- 1062 at the
`ELECTRIC_LEARN` commit plus the 11 and the 18 above, the arithmetic checked against the files
(`findstr /R "^def test_"` says 11, 18, 17) rather than trusted, and the suite run on a settled tree.
One committed test failed on the first pass and it was a real one:
`tests/test_electric.py::test_direct_function_is_pure` pins `_electric_answer`'s signature by name, and
the new `do_support` knob was the sixth. The pin's own comments are a procedure -- every knob so far
was admitted by adding the name, asserting the default is `False`, and saying in the file why that
knob is safe -- so it was extended that way, not loosened. `tools/electric_learn_bench.py` costs
149-172s per arm (three arms, nine houses, ~11 min for the full grid; `--arms learn --depth 1` is the
40-second version), exits 1 if any house says a sentence nobody said, and its evidence is
`docs/evidence/electric_learn_bench.json`.

**And one thing this commit fixes that had nothing to do with either flag.** Four files had been
rewritten by a helper script that read them in text mode and wrote them back with `newline=""`, which
silently converted them from CRLF to LF -- `tools/electric_chat.py`, `tools/electric_learn_live.py`,
`tools/electric_teach_mode.py`, `tools/qa_teach_mode_live.py`. `git diff --stat` did not show it,
because `core.autocrlf` normalizes before comparing: the diff still read 8/8/44/7 lines. The only tell
was the warning on the status line. They are back to CRLF with the diffstat unchanged, which is the
check that says the content was never touched -- and the lesson is that a script that rewrites a whole
file is not a smaller edit than `edit_file`, it is a bigger one with less visible blast radius.

## ELECTRIC_QA_ANSWER_MEMORY -- the lesson is kept; the arithmetic still decides what grammar it proves

`ELECTRIC_ASK_DO_SUPPORT` closed 20 of the 24 asks in `ask_not_recognized` and left the rest of the
gap named: 9 probes still `pair_never_admitted` -- pairs a person had taught in conversation that
never reached the QA store. The gate was `learn_qa`'s own rule, which the store inherited: a pair is
admitted when the answer differs from the question by **exactly one word on each side**. That is the
right rule for the job it was written for -- `what bites the latch` against `the dog bites the latch`
is one swap, and the swap is what tells the organ that `what` asks about the subject. It is the wrong
rule for the job the store has. Measured on the same instrument: 16 pairs taught in conversation, 10
reached memory, and of the three whose answer sentence exists nowhere else in the house -- the only
three the store is *for* -- **zero**. `where does the bell hang? / the bell hangs on the wall` is
refused at 3 missing / 3 new. An answer that tells you something new is, by construction, the kind
this rule refuses; a one-word swap is the narrow case where the answer adds nothing but the slot it
fills.

So the flag (`ELECTRIC_QA_ANSWER_MEMORY`, default off, the **sixth** widening, so `--electric-teach`
still refuses it and `--electric-learn` turns it on) keeps such a pair and **casts no grammar vote**.
That separation is the whole design, not a detail of it: `question_roles`, `interrogatives`,
`answer_types` and `qa_pairs_seen` do not move on a loose keep, because a pair that does not pin a
role must not teach one -- that is exactly how the corpus's refused warmint pair once taught this
organ that `what` asks about role 5, a fact the store inherited as a bug. The record is written with
its `word` empty and its `role` at -1, which is not a placeholder but an assertion: the grammar does
not know what this question word asks about, so the `learned` route is closed on this record and only
a typed or person-marked ask can open it.

Five bounds, one test each. It must be a conversation pair the person **marked** (a book line that
happens to sit in question order is not this flag's business, and the `?` is the only signal that the
second turn is an answer rather than the next sentence); the shared `_qa_admissible` test still has to
pass; the answer must **add** at least one word, or it is the question repeated back; and the two
turns must share at least one non-stop content word, because adjacency is not aboutness and without
that bound `what is your name?` paired with `the sky is blue` becomes a memory he would answer you
with. The last bound is what still refuses one of the curriculum's own pairs, named below. A loose
keep never overwrites a strict one -- first tell wins across both admissions, the same rule `_qa_keep`
already applies to a pair re-read.

**Numbers, same instrument, three arms, depths 1/2/3.** Learn at depth 3, after a real restart:
correct **98 -> 108** of 124, items kept **28 -> 33** of 40, lost **7 -> 3** and part 5 -> 4,
`pairs_in_store` **10/16 -> 15/16** and `pair_only_in_store` **0/3 -> 2/3** -- the three the store
exists for. Mechanism by mechanism:
`pair_never_admitted` **9 -> 1** and `refusal_silence` **2 -> 0**, which together are the whole
recovery (26 failing probes -> 16), while `fallback_fragment` **8 -> 8**, `ask_not_recognized`
**4 -> 4** and `key_shadowed` **3 -> 3** did not move -- the check that this flag moved the class it
was aimed at and nothing else. The counterfactual holds probe for probe: **the teach arm did not move
at all** (14/27/39 correct at depths 1/2/3, 10 pairs in store at depth 3, `pair_never_admitted` still
10) and neither did control (0 correct at every depth). Restart still costs nothing -- live equals
restarted at every depth in every arm, which is now four runs of that result. **No arm invented a sentence** -- the
tool's own `failures` list is empty, its floor, exit 0 -- and false acceptance did not grow: exactly
one of the twelve untaught distractor asks is answered, `what chases the mouse` -> `the mouse chases
the dog`, and it is answered **identically in the teach arm at every depth and both phases**, which is
what makes it demonstrably not this flag's; control answers none. Grammar state after
five loose keeps in a real house: `qa_pairs_seen` 10, roles `{what, who}` -- identical to the strict
house.

**What it does not fix, and why that is not an omission.** `when does the bell toll? / it tolls at
dusk` is still refused, and it is refused by the bound this flag added: the ask says `toll`, the
answer says `tolls`, and the store's key is exact tokens, so the two turns share no content word.
That is the same stemmer boundary as the do-support residual, arriving on the write side this time --
`tools/electric_learn_bench.py`'s classifier names it, and a test pins the refusal rather than
wishing it away. `what holds the shelf?` still answers `the shelf holds the lamp` (3 probes,
`key_shadowed`, unchanged): the store does hold `the rope holds the shelf` and the keyed inventory
speaks first, which is an ordering question about two memories, not an admission question. And the 8
`fallback_fragment` probes are the shape arbiter returning one word instead of the tell, which
predates every flag in this section.

**Numbers at this commit.** `1108 passed, 3 skipped, 0 failed in 480.18s` -- 1091 at the do-support
commit, and the delta is the 17 tests in the new file, counted out of the file with
`findstr /R "^def test_"` rather than subtracted from a total. The benchmark ran clean: exit 0,
`failures` empty, all three arms and both phases.

`tests/test_electric_qa_answer_memory.py` (17): the class default and both modes, a refused pair kept
while the refusal is still reported, the grammar-does-not-move test (state of the four structures
before and after, not a count of what the call returned), the flag-off counterfactual, one test per
bound, first-tell-wins across the two admissions, `word` empty and `role` -1 as a claim about the
route, the sweep stated as an invariant (every sentence this path can speak is one a person said), a
loose pair surviving a real save/reload, the table listing it as a widening with its parent declared,
inertness without `--electric-qa-store` reported by `unmet()`, and a text pin that `tools/serve.py`
wires it **above** the mode tables -- because an individual assignment placed after `enable_learn`
takes the mode's own widening back off, which is the wiring bug that once made `--electric-learn` run
as teach mode plus one. One pinned surprise belongs to a different flag: under learn mode
`where the bell hangs` -- no mark, no auxiliary -- *does* reach the store, because the ask-shape
normalizer canonicalizes it onto the stored key. That is `ELECTRIC_ASK_SHAPE` and
`ELECTRIC_ASK_NORMALIZE` doing what they were measured to do; this flag only put something worth
answering behind the door.

## ELECTRIC_ARBITER_TELL -- the arbiter verified the memory; now the house says it

`arbiter head` is a branch that works and then chooses to be less useful than it is. The shape
arbiter has already done the hard part: it verified a memory against the queried shape and named the
one content word in it that answers the ask. The organism speaks that word and nothing else. That is
deliberate -- reading a row out loud speaks its modifiers too, which is how `what turns twice?` tripped
its own forbid on `copper` and answered `bell` correctly only because it said one word.

What it costs was measured before this flag existed, on the run committed at `af32c0f`: of the 8
`fallback_fragment` probes left in learn mode at depth 3, SEVEN are this branch, and in seven of
seven the row the arbiter chose IS the tell the person taught, word for word. He is holding the
sentence and handing over a syllable.

The flag says the sentence, under one bound: the row may add **no word the ask did not already name**,
except the answering word itself. Plus the bounds that keep it a memory and not a window: the row was
said to him (`who == "you"`), it is not itself an asking, the named word is in it, and every content
word of it is in the ask or is that word.

Re-measured on this tree by re-running `tools/electric_learn_bench.py` (40 items, 136 probes, 3 arms,
exit 0), not by reading the shipped file back: learn correct live **37/71/108 -> 38/75/115** at depths
1/2/3 (of 39/124/124); `arbiter tell` spoken **36** times and **only** in the learn arm;
`arbiter head` 1034 -> 1014; silence 1535 -> 1519; `fallback_fragment` at learn depth 3 live **8 -> 3**;
teach unmoved at **14/27/39**; control unmoved; guarded-absence rows **24 -> 24**; **no invention in
any arm at any depth**.

The transition matrix, taken row by row against the pre-flag snapshot (27 cells x 136 rows; every ask
text matched its own position in both runs, so this is positional and not inferred):

| learn-arm transition | rows | class movement |
|---|---|---|
| `arbiter head` -> `arbiter tell` | **36** | `partial -> correct` |
| `""` (refused) -> `arbiter head` | **16** | `refused -> partial` |

Nothing else moved, in either the teach or the control arm (**0 rows changed in both**), and **no row
lost `correct`**. The arithmetic closes: `arbiter head` 1034 - 36 + 16 = **1014**, silence 1535 - 16 =
**1519**, and the gain in the headline numbers is fully accounted for by the 36.

**The 36 are the branch doing its job. The 16 are not, and they are the finding.** They are 3 distinct
ungrammatical asks -- `what the nora carry`, `what the dog guard`, `what the bridge cross` -- which used
to be refused with `nothing he remembers has that shape` and now reach the one-word branch and answer
`says`; they appear 16 times because the same 3 asks recur across depths and phases. The mechanism is
the house, not the branch: probes are asked in order against one store, and once the flag has said rows
whole, a row of that shape exists, so an ask that used to find nothing now finds something. The A/B
inside a single tree with only the instance flag differing (off reproduces HEAD exactly) shows the same
thing at depth 1 in one probe; 108 of the 110 replies in that cell are identical either way.

`says` is in none of the 27 told sentences, and in neither the ask nor the row it is drawn from
(`nora carries the lantern`, `the dog guards the gate`, `the bridge crosses the river`). The one-word
branch can name a word the house was never told, and the INVENTED grader cannot see it because it grades
sentences and this is a word. The defect is `arbiter head`'s, not the bound's -- the bound is exactly
what stops those 3 asks being handed a sentence, so with the flag on they still get only the word -- but
this flag is what routes them into it.

**This is a regression, not a curiosity.** `docs/electric_generalisation.md` states this project's own
standard: confabulation is "the category that is worse than silence". A probe that honestly declined now
utters a word nothing in the house supports. The guarded-absence rows did not move and no row lost
`correct`, so the graded contract held -- but `refused -> partial` is not neutral, and an earlier draft
of this section, of `docs/HANDOVER.md`, and of `README.md` asserted "no probe moved to a worse class"
off aggregate arithmetic instead of the matrix. Corrected here, and the correction is the point of
writing the matrix down. **Open: the `says` fallback inside `arbiter head`, and whether routing 3
refuses into it is a price worth paying for +7 correct at depth 3.**

`tests/test_electric_arbiter_tell.py` (18): the seven taught rows spoken, every bound as a rejection of
the predicate, the graded leak (`what turns twice` still answers `bell`) with the flag on, and the
wiring -- excluded from teach mode, present in `ALL_ATTRS`, a `WIDENS` line in `describe_learn()`.
`serve.py --electric-arbiter-tell` and `electric_chat.py --arbiter-tell`, both default off; learn mode
turns it on as the **seventh** widening. Teach mode's guarantee is therefore now six refusals and seven
widenings, and the README's older claim that the widenings "never change what the house is willing to
SAY" is no longer true: what survives is the narrower invariant the flag actually holds -- it never
widens what the house KNOWS, only what it says of a memory already verified against the ask.

One tool change this forced, recorded because it looked like a different bug. Adding the seventh
`WIDENS` line to `describe_learn()` pushed `electric_chat.py`'s startup banner past the 4096-byte
Windows pipe buffer, and the three tests that scan stdout until `ready port=` and then stop touching
the pipe left the child blocked in `print()` before the serve loop was ever reached -- a hang that
presented as a `/shutdown` problem and was a buffer. The readiness line now prints **last**, after the
banner, because the client's own scan is what drains it; nothing needs the port before the banner is
worth reading.
