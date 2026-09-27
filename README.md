# Droso

Droso is an autonomous agent whose core decision process runs on a reconstructed section
of the *Drosophila* connectome (BANC v888). Language, memory, planning, and program
synthesis are implemented as additional organs operating on top of this substrate, each
maintaining its own state and updated by the agent's own activity as it runs.

## Objectives

| Area | Target | Current approach |
|---|---|---|
| Language | Fluent multi word English, on the order of 20,000 word families | A semantic association matrix and a sequence generation organ, trained by exposure |
| Coding | A large majority of tasks solved from a locally verified procedure library | Recall, composition, and a program synthesis loop, checked by execution before anything is trusted |
| Reasoning | Multi step, self correcting behavior toward a held goal | A goal organ combined with a prediction and verification loop |

A further objective, not yet demonstrated, is that separate running instances can be
merged so that knowledge gained independently compounds rather than only accumulates in
parallel. The current status of that test is described under Population and merge below.

## Substrate

The graph is constructed from BANC v888 source tables (`connectome/data`). Construction
requires these tables and fails if they are absent; there is no substitute substrate used
in their place.

| Component | Count | Role |
|---|---|---|
| Neurons | 12,867 | nodes of the signed core graph |
| Synapses | 173,294 | signed connections |
| Kenyon cells | 4,419 | sparse encoding of input |
| Mushroom body output neurons | 85, pooled into 12 groups | decision output |
| Dopaminergic neurons | 83 | carry the plasticity signal |
| Projection neurons | 382 | sensory input path |
| Central complex | 961 in, 709 out | orientation circuitry |

The core graph is a subset of the full BANC reconstruction, which contains approximately
188,000 neurons. Dynamics are simulated at the level of firing rates under a three factor
plasticity rule (eligibility, dopamine, timing), not at the level of single neuron
biophysics. A degree matched control graph can be built with
`build_core_graph(control=True)` for comparison against the measured wiring.

Plastic synapse weights are held per running instance and currently number over 20,000,
changing as the agent operates. The carved graph itself is loaded once per process and
shared.

## Decision cycle

1. Input text is encoded with a deterministic hash (blake2b) into a sparse pattern over
   the Kenyon cell population. The same word produces the same pattern in every running
   instance, which is what allows learned associations to be combined across instances
   during a merge.
2. Activity propagates through the measured synaptic weights.
3. The 85 mushroom body output neurons vote by winner take all across 12 pools, modulated
   by whatever goal is currently held.
4. The dopaminergic population fires according to the outcome, and a three factor rule
   (eligibility times dopamine times timing) updates the synapses that were active in that
   decision.

## Language

Word meaning is represented in a semantic association matrix, updated by Hebbian learning
as sentences are read or produced. A sequence organ generates output word by word from
this and from short term context. A goal organ holds a target on the same class of
neurons used for sensory input, with a decay half life of 180 seconds, and this target
enters both decision making and language production.

Role recovery, correctly identifying who did what to what in a recalled sentence, is
substantially more reliable for memories formed from an action the agent actually took
than for memories formed from reading. This has been measured directly and is the basis
for weighting grounded experience over reading volume elsewhere in the system.

## Reasoning and the harness

Task solving is organized into two tiers by `organs/harness.py`, which also records which
tier solved each task.

The first tier checks for an exact match: a fact already filed under the task's key, or a
procedure already verified for a task of this kind. Either is replayed directly with no
search.

The second tier runs when the first finds nothing. Candidates are generated from
composition of known procedures, from a small set of primitive operations, and from a
program grammar with typed holes. Where a candidate requires a specific fact that is not
on file, that gap, rather than the surrounding task, is what gets sent to the external
model.

Every attempt runs through the connectome before execution: `engine.decide()` sets the
eligibility trace the three factor plasticity rule requires, and the outcome of execution
feeds back as a reward signal through `teach()`.

Because both tiers report which branch solved a task, an existing fact, an existing
procedure, local composition, or an externally supplied fact, the proportion of tasks
solved without external help is a measured quantity rather than an estimate.

## Evidence and promotion

A candidate procedure is promoted to trusted status only under specific evidence.

| Evidence | Weight |
|---|---|
| A passing test executes a line inside the candidate | 0.35 |
| A task's own assertions accept the candidate | 0.35 |
| The candidate runs without error but nothing inside it is exercised | 0.15 |
| The candidate parses but nothing runs | 0.00 |
| The candidate compiles | 0.00 |

A procedure is treated as trusted at a cumulative weight of 0.70 or above. Repeated
identical evidence does not add further weight. This gate applies to every candidate
equally, whatever its source, including answers returned by the external model.

## Fact store and external knowledge

Facts are filed under a key of three parts: a concept, a subject, and the type of value
the answer takes, the last read directly from a task's own assertions. This third
component was added after two tasks sharing a concept and a subject, a rearrangement task
and a counting task, both concerning reversed strings, were found to require answers of
different types, which a two part key could not distinguish.

The external model is used only to supply a fact the local system cannot derive on its
own, identified from a specific gap encountered while attempting a solution rather than
from the task as a whole. Its answer is accepted only if it passes the same evidence gate
described above. Every call is logged with its outcome, and local, corpus assisted, and
externally assisted solutions are recorded and reported as separate figures rather than
combined into one score.

The external interface speaks the OpenAI compatible chat protocol, so the specific model
behind it, hosted or run locally, is a configuration choice rather than a fixed part of
the architecture.

## Population and merge

Independent instances can run in parallel on separate subsets of tasks and later be
merged, testing whether knowledge gained by one instance helps solve tasks assigned to
another. A meaningful version of this test requires the two subsets to be genuinely
unsolvable by the other instance beforehand, checked in both directions, against a
matched compute control. This is implemented in `tools/population_experiment.py`.

An earlier version of this test appeared to show a gain from merging. That result was
later found to depend on each instance starting from an empty memory rather than the
memory the live agent actually accumulates; once measurement was corrected to use the
same persistent state the live process uses, the task subsets were no longer independent
of one another, and the apparent gain did not hold under the same check. The experiment is
being redesigned around task subsets confirmed unsolvable against the agent's actual
accumulated knowledge, rather than against a topic label alone. Its current status is
unresolved rather than positive or negative.

## State management

Tool processes that measure the agent, fitness scoring, curriculum runs, and the
population experiment among them, load the same persistent state the live process uses,
opened for reading only. Write access from any process other than the live house is
disabled at the code level. This follows an earlier incident in which a measurement tool
with unrestricted write access overwrote the accumulated memory file, reducing its
recorded content by more than an order of magnitude before most of it was recovered
through a lineage mechanism. The restriction is enforced in the code path itself rather
than left to convention.

## Known open items

One test in the current suite calls a method, `_oracle_sandbox_hook`, that does not exist
in the codebase. Whether any live path allows the external model to execute actions
directly, as opposed to returning text that is separately verified before use, is under
review. The knowledge channel as currently implemented accepts text answers only.

A portion of the test suite currently fails. Several of these failures are believed to
depend on a live house process being present rather than indicating a regression in the
underlying code, and this is being confirmed test by test rather than assumed.

## Repository layout

```
connectome/    BANC v888 source tables, substrate construction, rate dynamics, provenance
core/          action space definition
organs/
  tokenizer.py, higher_cortex.py, neural_language.py, sequence_organ.py, goal.py
                    language: word encoding, semantic association, sentence production,
                    a goal held on real neurons
  local_solver.py, reasoning_loop.py, harness.py, learning_loop.py, fast_router.py
                    reasoning: recall, composition, candidate generation, the evidence
                    gate, and routing between the two tiers
  concepts.py, knowledge.py, api_oracle.py
                    the fact store, the external model interface, and the channel
                    connecting them through a single verified path
  sandbox.py, circuit_breaker.py, filesystem.py
                    execution, approval gating, and workspace access
  planner.py, task_decomposer.py, causal_reasoner.py, hypothesis_generator.py, and
  further supporting organs
world/
  connectome_house.py   HTTP interface and dashboard
  reasoning_agent.py     agent assembly
  house/static/          frontend
server/          application and websocket layer
tools/
  fitness.py, task_battery.py, curriculum_run.py, knowledge_run.py
                    measurement
  population.py, population_experiment.py
                    parallel instances and merge testing
  make_curriculum.py, make_exercism.py, make_library.py, seed_procedures.py
                    corpus and curriculum construction
  triage_failures.py, oracle_diagnose.py
                    diagnostic tooling
tests/           pytest suites
state/           persistent state: connectome weights, language memory, procedure
                 library, the external model call ledger
exocortex/       verified code fragments available to the assembler
config/          runtime configuration, containing no credentials
credentials.py   per user credential storage, kept outside the repository
```

## Quick start

```bash
git clone https://github.com/SebSilent/Droso.git
cd Droso
pip install -r requirements.txt
python run_house.py
```

Dashboard: `http://localhost:7773`

## External model configuration

Credentials are stored per user outside the repository and are never written to tracked
configuration or committed state. Resolution order: an explicit key passed by the caller,
the user's stored credential, an environment variable. Setting `HYBRIDLLM_OFFLINE=1`
disables the external model entirely; this is also how offline measurements in this
document are taken, and results obtained this way are kept in a separate column from
results that used the external model.

## Measurement

```bash
HYBRIDLLM_OFFLINE=1 python tools/task_battery.py
HYBRIDLLM_OFFLINE=1 python tools/fitness.py --repeat 6
python -m pytest tests -q
```

Figures below are a snapshot taken during active development and should be re-measured
rather than assumed current.

| Measure | Value |
|---|---|
| Vocabulary | approximately 4,500 words |
| Propositions in memory | approximately 60,000 |
| Verified procedures | approximately 680 |
| Coding tasks solved locally, held out set | close to one in five |
| Composite fitness score | most recently measured at 0.68 |
| Test suite | close to 300 passing |

## Data credit and citation

The wiring is the BANC v888 release of the Brain and Nerve Cord connectome, loaded from
its published source tables. Cite the connectome for the biology.

- Bates AS, Phelps JS, Kim M, Yang HHJ, et al. Distributed control circuits across a
  brain and cord connectome. *Nature* (2026), open access.
  https://doi.org/10.1038/s41586-026-10735-w
- BANC v888 data deposit: Harvard Dataverse,
  https://doi.org/10.7910/DVN/7WTH1N (CC BY 4.0)

## License

Code in this repository is released under the MIT License. Copyright (c) 2026 Silent. See
[LICENSE](https://github.com/SebSilent/Droso/blob/main/LICENSE).

The BANC v888 connectome data is licensed CC BY 4.0 by its authors.

## Status

Active research project, developed and revised quickly. Any specific figure in this
document is provisional; the tools listed under Measurement are the source of truth for
current numbers.
