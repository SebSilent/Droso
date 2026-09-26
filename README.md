# Droso

An autonomous agent whose decision core is the BANC v888 fly connectome.

## About Droso

Droso is a software agent built around a measured biological wiring diagram. Its
decision substrate is a structural carve of the Brain-And-Nerve-Cord (BANC)
connectome, loaded neuron by neuron from the published source tables. Text input
is encoded as a sparse code over the Kenyon cell population, activity propagates
through measured synapses, and a winner-take-all vote across 12 mushroom body
output (MBON) pools produces the decision. Outcomes are written back by a
three-factor dopamine rule restricted to the 2,983 Kenyon-cell-to-MBON synapses,
the plastic subset of the graph. This is the circuit role the mushroom body
plays in the insect: sparse representation, high-dimensional expansion,
associative learning.

An organ set around the carve provides the agent's remaining capabilities:
planning, code assembly and verification, a sandboxed filesystem, terminal
execution, memory systems, language organs, a fast router, and a query cache.
The carve commits to actions; the organs carry them out. Knowledge the local
systems lack is requested from a teacher model over an API, cached, and
gradually internalized by the learning loop, after which repeats are served
locally.

## Provenance: the carve

The core graph is built from the BANC v888 source tables
(`connectome/data/*.csv.gz`). Construction fails if the tables are absent.

| Component | Count | Notes |
|---|---|---|
| Neurons | 12,867 | nodes of the signed core graph |
| Synapses | 173,294 | total, signed |
| Plastic synapses | 2,983 | KC to MBON; the only edges that learn |
| Static and modulatory synapses | 170,311 | fixed weights: sign x log(1 + synapse count) |
| Kenyon cells | 4,419 | perception layer; text encoder uses a 16-of-3,840 code space |
| MBONs | 85 | pooled round-robin into 12 decision pools |
| Dopaminergic neurons | 83 | carry the teaching signal |
| Projection neurons | 382 | sensory input path |
| Central complex | 961 inputs / 709 outputs | orientation circuitry |
| MBON pools | 12 | one per action in the decision space |

Scope and method: the model is a structural carve run with rate dynamics and a
three-factor plasticity rule. Single-neuron biophysics is out of scope. The
12,867-node core graph is a subset of the full BANC reconstruction
(approximately 188,000 neurons). `build_core_graph(control=True)` produces a
degree-matched random control graph, so claims about the wiring can be tested
against a scrambled brain with matched statistics.

## How a decision runs

1. Text is hashed (blake2b, deterministic) into a sparse code: 16 active cells
   over the 3,840-cell encoder space.
2. The code is injected into the carve's Kenyon cell population.
3. Activity propagates through measured synapses for 10 sub-steps.
4. The 85 MBONs vote by winner-take-all across their 12 pools. The winning pool
   is the action.
5. The outcome fires the dopaminergic population, and the three-factor rule
   (eligibility, dopamine, timing) updates the 2,983 plastic synapses.

```
text -> hash -> KC code -> [BANC carve, 10 steps] -> MBON vote -> action
                                                      |
                                             dopamine -> plastic synapses
```

## The reasoning loop

Task execution runs a 7 phase cycle: understand, explore, choose, plan, execute,
verify, learn. The connectome selects the move at each phase from its 12 action
pools: recall episodic, semantic or procedural memory; execute a terminal
command; read or write a file; ask the user; store a memory; query the external
knowledge library; submit the answer. Backtracking is an explicit event and is
counted in the loop statistics.

## Knowledge and state

All agent knowledge lives in inspectable files under `state/` and
`exocortex/`:

| Store | File | Content |
|---|---|---|
| Lived brain | `state/banc_brain.npz` | plastic synapse weights, drifted from initialization by dopamine events |
| Vocabulary | `state/language_state.json` | words stored as neural patterns over an 8,192-cell Hebbian state (SAN) |
| Procedures | `state/house_agent_learning.json` | task signatures of solved tasks, with success counts |
| Answer cache | `state/house_agent_cache.sqlite3` | teacher answers, replayed locally after enough confirmations |
| Code snippets | `exocortex/snippet_vault.db` | verified code fragments available to the assembler |

Words in the SAN are associations acquired from exposure. The repository ships
with the state accumulated during development; the counts change as the agent
runs.

## Capabilities and known limitations

Capabilities:

- Self-directed reasoning loop over the connectome's action space, with learning
  that persists across sessions.
- Local solving of simple tasks from the snippet vault and procedure store; new
  knowledge requested from a teacher LLM, cached, then served locally once
  confirmed by repeated success.
- A dashboard (FastAPI, port 7773) exposing live neural state, language state,
  learning history, and a file panel with an approval fence: writes inside the
  workspace are free, writes outside it queue for human approval, and deletions
  always require a grant.

Known limitations:

- Knowledge acquisition requires a teacher key. Local generation recombines
  stored fragments, and structural verification alone does not guarantee
  semantic correctness.
- The loop overhead is Python: decisions propagate in milliseconds, phases
  cost more.
- The teacher integration targets OpenAI-compatible endpoints (developed against
  Z.AI); uncached calls cost real money.
- A backlog of older dashboard tests still targets retired endpoints from
  previous iterations. They fail loudly and do not affect the neural core.

## Repository layout

```
connectome/    the carve: BANC v888 source tables, substrate, rate engine,
               provenance metadata
core/          action space definition
organs/        32 organ modules: planner, code assembler, sandbox, terminal,
               filesystem, memory, language, fast router, oracle, learning
               loop, heartbeat, growth, and support modules
world/         the house: dashboard, reasoning agent, meta controller
server/        FastAPI application and websocket streaming
tools/         probe and verification scripts
tests/         pytest suites
state/         lived state (brain, language, procedures, caches)
config/        runtime configuration; contains no secrets by design
credentials.py role-based credential store and CLI
```

## Quick start

```bash
git clone https://github.com/SebSilent/Droso.git
cd Droso
pip install -r requirements.txt
python run_house.py
```

Dashboard: http://localhost:7773.

### Teacher model and credentials

Keys are stored per-user, outside the repository:

```bash
python credentials.py set model    # hidden prompt; stored in the OS app-data directory
python credentials.py status       # fingerprints only, never the key
python credentials.py clear model
```

Resolution order: explicit caller key, user store, environment variable
(`ZAI_API_KEY`). `HYBRIDLLM_OFFLINE=1` forces fully local operation, which keeps
test runs hermetic.

Z.AI is the author's choice of provider, a configuration setting. The oracle
speaks the OpenAI-compatible chat protocol, so any provider that implements it
can be substituted: change the endpoint and key, keep everything else.

## Tests

```bash
python -m pytest tests/test_neural_core.py tests/test_api_organs.py tests/test_safety_layers.py \
  --ignore=tests/test_mental_organs.py --ignore=tests/test_overnight_trainer.py \
  --ignore=tests/test_dashboard.py --ignore=tests/test_connectome_house.py \
  --ignore=tests/test_house_mental_endpoints.py --ignore=tests/test_multilang.py \
  --ignore=tests/test_neural_growth.py --ignore=tests/test_neural_language.py \
  --ignore=tests/test_reasoning.py -q
```

The neural core and safety suites pass. The dashboard test backlog described
above is tracked separately.

## Data credit and citation

The wiring is the BANC v888 release of the Brain-And-Nerve-Cord connectome,
loaded from its published source tables. Cite the connectome for the biology:

- Bates AS, Phelps JS, Kim M, Yang HHJ, et al. Distributed control circuits
  across a brain-and-cord connectome. Nature (2026), open access.
  https://doi.org/10.1038/s41586-026-10735-w
- BANC v888 data deposit: Harvard Dataverse, https://doi.org/10.7910/DVN/7WTH1N
  (CC BY 4.0)

## License

The code in this repository is released under the MIT License.
Copyright (c) 2026 Silent. See [LICENSE](LICENSE).

The BANC v888 connectome data is licensed CC BY 4.0 by its authors.

## Status

Active personal research project. The connectome core was extracted from the
Chimera multi-agent world (the data loader carries that lineage) and previously
ran as HybridLLM before becoming Droso. Measured numbers in this file refer to
the code and data as committed.
