# Droso

Droso is an agent whose decision process runs on a reconstructed section of the
*Drosophila* connectome (BANC v888). Language, memory, planning and program
synthesis are implemented as separate organs on top of that substrate, each
holding its own state and updated by the agent's own activity as it runs.

## Substrate

The graph is constructed from BANC v888 source tables (`connectome/data`).
Construction requires those tables and fails if they are absent.

| Component | Count | Role |
|---|---|---|
| Neurons | 12,867 | nodes of the signed core graph |
| Synapses | 173,294 | signed connections |
| Kenyon cells | 4,419 | sparse encoding of input |
| Mushroom body output neurons | 85, pooled into 12 groups | decision output |
| Dopaminergic neurons | 83 | plasticity signal |
| Projection neurons | 382 | sensory input path |
| Central complex | 961 in, 709 out | orientation circuitry |

The core graph is a subset of the full BANC reconstruction, which contains about
188,000 neurons. Dynamics are simulated at the level of firing rates under a
three-factor plasticity rule (eligibility, dopamine, timing), not single-neuron
biophysics. `build_core_graph(control=True)` builds a degree-matched control
graph for comparison.

Plastic synapse weights are held per running instance and number over 20,000.
The carved graph is loaded once per process and shared.

## Decision cycle

1. Input text is encoded with a deterministic hash (blake2b) into a sparse
   pattern over the Kenyon cell population.
2. Activity propagates through the measured synaptic weights.
3. The 85 mushroom body output neurons vote winner-take-all across 12 pools,
   modulated by the goal currently held.
4. The dopaminergic population fires according to the outcome, and a three-factor
   rule updates the synapses active in that decision.

## Language

Word meaning is represented in a semantic association matrix, updated by Hebbian
learning as sentences are read or produced. A sequence organ generates output
word by word from it and from short-term context. A goal organ holds a target on
the same class of neurons used for sensory input (decay half-life 180 s), and
that target enters both decision making and language production.

Role recovery -- identifying who did what to what in a recalled sentence -- is
more reliable for memories formed from an action the agent took than for
memories formed from reading.

### Question answering

A turn through `lang.respond()` hears the utterance (SAN update, cortex binding,
sequence learning). A question goes to `answer()`, which selects a role,
retrieves propositions through `binder.recall`, and either recovers the missing
role by unbinding or tries the dedicated paths below, in this order:

| path | fires on | behaviour |
|---|---|---|
| echo | a declared exact repeat | repeats the stated memory |
| glossary | a question about a word used earlier | returns the earlier word |
| ordinal | `which … first/second/last` over session memories | selects by position |
| disjunction | two offered alternatives | settles one against memory |
| record | questions about the telling record | counts tells, or reports absence |
| quantity | `how many X`, `what count of X`, `did any X` | arithmetic over numbers stated in tells |
| description | subject is a definite description | not in the tree; implemented and reverted |

The `first`/`last` cue words are matched as sets (`COUNT_FIRST_CUES`,
`COUNT_LAST_CUES`) rather than one word at a time.

## Reasoning and the harness

Task solving is organised into two tiers by `organs/harness.py`, which records
which tier solved each task.

The first tier checks for an exact match: a fact already filed under the task's
key, or a procedure already verified for a task of this kind, replayed with no
search.

The second tier runs when the first finds nothing. Candidates come from
composition of known procedures, from a small set of primitive operations, and
from a program grammar with typed holes. Where a candidate needs a fact that is
not on file, that gap is what gets sent to the external model.

Every attempt runs through the connectome before execution: `engine.decide()`
sets the eligibility trace the three-factor rule requires, and the outcome of
execution feeds back as a reward through `teach()`.

Both tiers report which branch solved a task, so the proportion solved without
external help is measured rather than estimated.

## Evidence and promotion

A candidate procedure is promoted to trusted status only under specific evidence.

| Evidence | Weight |
|---|---|
| A passing test executes a line inside the candidate | 0.35 |
| A task's own assertions accept the candidate | 0.35 |
| The candidate runs without error but nothing inside it is exercised | 0.15 |
| The candidate parses but nothing runs | 0.00 |
| The candidate compiles | 0.00 |

Trusted at cumulative weight 0.70 or above. Repeated identical evidence does not
add weight. The gate applies to every candidate, including answers from the
external model.

## Fact store and external knowledge

Facts are filed under a key of three parts: a concept, a subject, and the type of
value the answer takes, the last read from a task's own assertions.

The external model supplies facts the local system cannot derive, identified from
a specific gap encountered while attempting a solution. Its answer is accepted
only if it passes the evidence gate. Calls are logged with their outcome, and
local, corpus-assisted and externally-assisted solutions are reported as separate
figures.

The external interface speaks the OpenAI-compatible chat protocol.

## Population and merge

Independent instances can run in parallel on separate subsets of tasks and later
be merged (`tools/population_experiment.py`). An earlier version of this test
appeared to show a gain from merging; once measurement was corrected to use the
same persistent state the live process uses, the task subsets were no longer
independent and the gain did not hold. The experiment's status is unresolved.

## State management

Tool processes that measure the agent -- fitness scoring, curriculum runs, the
population experiment -- load the same persistent state the live process uses,
opened read-only. Write access from any process other than the live house is
disabled in the code path. This follows an earlier incident in which a
measurement tool with unrestricted write access overwrote the accumulated memory
file; most of it was recovered through a lineage mechanism.

## Known open items

One test calls a method, `_oracle_sandbox_hook`, that is not defined in the
codebase. Whether any live path lets the external model execute actions directly,
rather than returning text that is separately verified, is unresolved. The
knowledge channel accepts text answers only.

## Repository layout

```
connectome/    BANC v888 source tables, substrate construction, rate dynamics, provenance
core/          action space definition
organs/        language, memory, reasoning, execution organs
world/         connectome_house.py (HTTP interface), reasoning_agent.py, house/static/
tools/         measurement, probes, corpus construction, gh-pages build
tests/         pytest suites
state/         persistent state: connectome weights, language memory, procedures, ledgers
docs/          documentation; docs/archive/ holds historical records
exocortex/     verified code fragments available to the assembler
config/        runtime configuration, containing no credentials
credentials.py per user credential storage, kept outside the repository
```

## Install and run

The recorded measurements were taken with **Python 3.10** (`py -3.10` on
Windows). A bare `python` on this machine is 3.12 without the dependencies.

```bash
git clone https://github.com/SebSilent/Droso.git
cd Droso
py -3.10 -m venv .venv
.venv\Scripts\activate          # source .venv/bin/activate on POSIX
pip install -r requirements.txt
python run_house.py
```

Dashboard: `http://localhost:7773`. Later commands assume the virtual
environment is active.

## Running the suite

```bash
python -m pytest tests -q
```

## Measuring

```bash
HYBRIDLLM_OFFLINE=1 python tools/task_battery.py
HYBRIDLLM_OFFLINE=1 python tools/fitness.py --repeat 6
```

### The held-out script harness

Six scripts of four asks each (24 asks). `--independent` builds a fresh house per
ask, so one ask cannot move another:

```bash
python tools/heldout_eval.py --independent --only count-frequency
```

Run one or two scripts per call; the full set exceeds a shell timeout. Scripts:
`count-frequency`, `order-first-last`, `conjunction-and-absence`,
`exact-repeat`, `hop-and-inventory`, `quantity-change`.

Each run prints `SCORE n/4 = x.xxx` per script and, unless `--journal` is given,
appends one line per ask to `state/fitness/heldout_independent.jsonl`. A failing
ask is printed with its stage (`stage=recall`, `stage=shape_arbiter`,
`stage=gating`, …), which is where in `answer()` it stopped. Scoring is by
expected answer token, so a full sentence containing the expected word passes.

### The guard scripts

Eight scripts, four calls, two scripts per pair, output to a file:

```bash
python tools/script_benchmark.py --only reference,accumulation > state/fitness/g.txt 2>&1
```

Pairs: `reference,accumulation`, `discrimination,role_chain`,
`switch_back,override`, `session_context,where_kept`.

### The selection harness

`tools/run_generation.py` scores brains, not cuts: a genome of the scalars the
organ and the rate core already read is applied to a freshly built house per ask,
and every brain is scored on the frozen 24 plus 18 rewordings of them. Fitness is a
tuple with a hard constraint first — zero frozen passes lost — and no weighted sum.
Contract in `docs/selection_design.md`.

```bash
python tools/run_generation.py --snapshot                 # write the base genome
python tools/run_generation.py --generation 0 --lines 3   # ~55 min, background it
python tools/run_generation.py --freeze-baseline --generation 0
```

One line per brain lands in `state/selection/generation_N.jsonl` carrying its
genome, its parent, both pass sets, every failure with its stage, and the git,
interpreter and live-state seals it was measured under. Generation 0 is three
clones of one genome: all three scored 19/24 and 4/18 with identical failure stages
and no ask changing membership, which is the instrument's noise floor measured
rather than assumed.

The table prints `warm`, `cold` and `delta` per script and overall. Warm is with
the session's own context, cold is after a restart from saved state; a delta of
`+0.00` means the restart changed nothing. `override` also prints its winner.

### Talking to him directly

`tools/converse.py` holds Droso in process with the house down: the real state is
loaded read-only, the session's writes are re-pointed under `state/sessions/`,
and the learning loop is sealed.

```bash
python tools/converse.py                  # interactive session
python tools/converse.py --benchmark      # fixed script, scored
python tools/mouth_probe.py hop-and-inventory "what does the thing the frost bites hold?"
```

### Talking to him over HTTP

`tools/serve.py` exposes the same door as an OpenAI-compatible endpoint. The last
user message's content is the utterance, verbatim; everything else in the request
is ignored. A spoken reply arrives as `choices[0].message.content`; a silent turn
arrives as empty content.

```bash
python tools/serve.py                     # 127.0.0.1:8080
POST /v1/chat/completions  {"messages":[{"role":"user","content":"..."}]}
GET  /v1/models
```

The server is single-threaded: one session, one turn at a time.

## Snapshot figures

Figures below are snapshots with the file they came from; re-measure rather than
assume them current.

| Measure | Value |
|---|---|
| Vocabulary | 11,555 words (live state, at `f2e1748`) |
| Propositions in memory | approximately 60,000 |
| Verified procedures | approximately 680 |
| Coding tasks solved locally, first-contact set | 0 of 10 (`state/fitness/heldout_firstcontact.json`) |
| Composite fitness score | 0.6834 at `SAN_ROW_CAP=1024` (`state/fitness/baseline_cap1024.json`) |
| Test suite | 428 passed, 3 skipped (at `f2e1748`) |

## Data credit and citation

The wiring is the BANC v888 release of the Brain and Nerve Cord connectome.

- Bates AS, Phelps JS, Kim M, Yang HHJ, et al. Distributed control circuits across a
  brain and cord connectome. *Nature* (2026), open access.
  https://doi.org/10.1038/s41586-026-10735-w
- BANC v888 data deposit: Harvard Dataverse,
  https://doi.org/10.7910/DVN/7WTH1N (CC BY 4.0)

## License

Code released under the MIT License. Copyright (c) 2026 Silent. See
[LICENSE](https://github.com/SebSilent/Droso/blob/main/LICENSE).

The BANC v888 connectome data is licensed CC BY 4.0 by its authors.