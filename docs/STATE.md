# Repository state

A factual inventory of what is in this tree, what each measurement harness does,
and the last numbers that were recorded, with the commit they were measured at.
No recommendations.

Last measured state: **`f2e1748`** (tree clean at the time).
Docs-only commits after it do not change any number below.

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
| `docs/archive/experiment_log.md` | historical experiment log written by prior agents |
| `docs/archive/role_chain_proposal.md` | historical proposal, not applied |
| `docs/evidence/` | raw run output cited by the docs |