# Repository state

[![Tests: 734 passed · 3 skipped](https://img.shields.io/badge/Tests-734%20passed%20%C2%B7%203%20skipped-1a7f37?style=flat-square&labelColor=0d1117)](#last-recorded-numbers)
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
- **Why the arm's row flickered.** C4e's run 3 showed `to?` for `who-bare`; run 4 showed silence
  for the same row, same code. The row depends on whether the stranded variant was heard first,
  which the table guarantees and my ad-hoc probes did not - two probes of mine missed the leak
  for exactly that reason. Pinned now as an explicit precondition (`_organ()` asks the stranded
  form before the bare one), not as an accident of table order.

Open: the guard is unmeasured on a corpus brain; the `recalled proposition` branch reads out a whole
token list and the guard does not touch it, so a remembered question may still come out in full -
**not measured, deliberately not fixed in the same stroke**; and the deeper question -
should a question be admissible as a memory at all - is untouched and is the one worth answering
next.
