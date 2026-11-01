[![License: MIT](https://img.shields.io/badge/License-MIT-1a7f37?style=flat-square&labelColor=0d1117)](https://github.com/SebSilent/Droso/blob/main/LICENSE)
[![Core Dataset: BANC v888](https://img.shields.io/badge/Core%20Dataset-BANC%20v888-0a3069?style=flat-square&labelColor=0d1117)](https://doi.org/10.7910/DVN/7WTH1N)
[![Topology: 12,867 Nodes / 173,294 Synapses](https://img.shields.io/badge/Topology-12%2C867%20Nodes%20%2F%20173%2C294%20Synapses-5b2d8e?style=flat-square&labelColor=0d1117)](#substrate)
[![Footprint: Python 3.10 + requirements.txt](https://img.shields.io/badge/Footprint-Python%203.10%20%2B%20requirements.txt-7d4e00?style=flat-square&labelColor=0d1117)](#install-and-run)
[![Tests: 734 passed · 3 skipped](https://img.shields.io/badge/Tests-734%20passed%20%C2%B7%203%20skipped-1a7f37?style=flat-square&labelColor=0d1117)](#running-the-suite)
[![Held-out 24: 19/24 organ only](https://img.shields.io/badge/Held--out%2024-19%2F24%20organ%20only-0a3069?style=flat-square&labelColor=0d1117)](#the-held-out-script-harness)
[![Guards: 8/8 · 1.00 warm / cold](https://img.shields.io/badge/Guards-8%2F8%20%C2%B7%201.00%20warm%20%2F%20cold-5b2d8e?style=flat-square&labelColor=0d1117)](#the-guard-scripts)

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

```text
Droso/
├── connectome/     BANC v888 source tables, substrate construction, rate dynamics, provenance
├── core/           action space definition
├── organs/         language, memory, reasoning, execution organs
├── world/          connectome_house.py (HTTP interface), reasoning_agent.py, house/static/
├── tools/          measurement, probes, corpus construction, gh-pages build
├── tests/          pytest suites
├── state/          persistent state: connectome weights, language memory, procedures, ledgers
├── docs/           documentation; docs/archive/ holds historical records
├── exocortex/      verified code fragments available to the assembler
├── config/         runtime configuration, containing no credentials
└── credentials.py  per user credential storage, kept outside the repository
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

Ten generations have now been run against one control genome, `abffa2b7f101`, and
**none has beaten it**. Generations 1 and 2 mutated `ANSWER_COVERAGE_FLOOR`; all
six draws were inert or harmful — one lowering draw lost a guarded invariant, which
was the predicted outcome and the reason the guard exists. Generations 4 and 5
tested three shape-parser repairs as two arms differing only in code flags: all
three were inert, arm B identical to arm A on all 42 asks. Generation 7 measured
where the failures actually die. Generations 8 and 9 were the two arms of a
recall-side fallback, and its prediction was **falsified** — the fallback never
fires, because no ask in the battery reaches the branch it guards.

The score has not moved off 19/24 frozen, 0/14 paraphrase probes, 4/4 guarded
invariants in any of them. (The journal holds 18 probe rows: 14 unseen paraphrases
plus the 4 guarded invariants, which is why the table reads `0/14` and not `0/18`.)
That is the honest headline: the instrument is reproducible and the organ is not
improving under scalar selection.

#### Every retrieval lever is now closed (E19, E20, E21a)

Three read-only probes ran against generation 19, a control clone scoring **23
pass — identical to generation 15**, so the instrumentation changed no score,
organ behaviour or genome.

**E19 falsified eviction.** `taught_resident` is True on 40 of 42 asks and **0 of
19 failures are eviction**. The binder census (0.78% `droso`, blind FIFO) is real
as a census fact but is not what causes these failures; the taught rows survive to
ask time.

**E20 falsified cue omission — and retracted an E19 claim.** On 4 of the 9 gate
asks the gate retrieves the correct taught row and ranks it **first**, then refuses
anyway at coverage 0.340–0.538, because `must` demands question syntax and passive
morphology a declarative tell can never contain: `what is bitten by the frost?`
asks the row `the frost bites the latch` for `bitten`, `by` and `is`. E19's
`nearest_has_taught=0` was an artifact of a `startswith("droso:")` test against
journal entries that carry **no who-prefix at all**, so "taught evidence does not
reach retrieval" is **withdrawn**.

**E21a falsified cue dilution.** De-framing the cue to closed-class words only
recovers **0 of 4** asks; its best case moves the row from rank 41 to rank 10
against a window of 3. Both bell phrasings collapse to the identical cue
`[bell, turn]` and both land at rank 10, where the top three are all book rows
about bells. The count-1 taught row loses to **corpus mass**, not to framing
noise. The probe also does not reproduce the gate's internal retrieval — it
disagrees with the gate's recorded `nearest` in both directions on 2 of 4 asks —
so it could not have certified a repair, and the guarded ask was unattributable.

The constraint chain, corrected: gen 2 / gen 6 said *score*; E12a / E14a said
*score* and measured a 0.5488 ceiling; `passing_ask_analysis` said *candidate
set*; E19 said *cue construction*; E20 returned it to *score*; E21a closes cue
dilution. Records in `docs/evidence/`.

**E22a closed reinforcement.** Taught-row `count` looks predictive — count=3 passes
5/6 (83%) against count=1 at 16/33 (48%) — but the gap is entirely ask-type
confounding: five of the six count=3 asks are meta-cognitive rehearsal questions
(`how many times did i tell you…`, `did i ever tell you…`) that carry
`cause=other` and never enter the recall gate. Restricted to gate asks, where
reinforcement could act, the **single** count=3 ask scores **0.454 — below the
count=1 gate mean of 0.4649** — with its row at rank 1. The best-reinforced row in
the battery, retrieved first, has worse gate coverage than the average count-1 row.

**E23 closed the coverage denominator, and it is the strongest result of the six.**
Excluding closed-class question syntax from the denominator *works*: it recovers 2,
3 or 5 of the 9 gate failures depending on how much syntax is removed. And **all
three variants break the guarded scarf invariant** — 0.5797 → 0.6676 → 1.0 → 1.0
against a 0.6 floor. The obstruction is structural: the scarf cue
`[did, is, say, scarf]` is three-quarters closed-class and its row
`the scarf is wet` contains `scarf` and `is`, so removing syntax collapses the
denominator onto terms the row trivially matches. **The guard depends on the
denominator being wrong in exactly the way the nine failures need it fixed** — the
scarf ask is *supposed* to refuse, and refuses only because `did`/`is`/`say` drag it
0.0203 below the floor. Refuted by its own read-only pre-test; **no flag, organ
change or test was added.** Exclusion is also not monotone:
`what did i tell you about before the kettle?` *falls* 0.547 → 0.415 → 0.238 → 0.0.

#### Six levers closed, and what that implies

| lever | probe | verdict |
|---|---|---|
| eviction | E19 | falsified — 0/19 failures |
| cue omission | E20 | falsified — gate ranks the row **first** on 4/9, still refuses |
| cue dilution | E21a | falsified — de-framing recovers 0 of 4 |
| score / admission | E12a, E14a | closed — ceiling 0.5488 < 0.6 |
| reinforcement | E22a | falsified — count=3 gate ask below the count=1 mean |
| denominator | E23 | **refuted pre-implementation — works, and is undeployable** |

E23 is the sharpest because it is the only lever that **works**. That is a stronger
statement than "no repair was found": a repair was found, measured, and shown to be
**inseparable from breaking a correct refusal**. The nine gate failures and the one
guarded refusal are governed by a single quantity, and no monotone change to it
separates them.

Progress therefore needs a mechanism that is **not a coverage threshold** — a way to
represent *absence*, so the scarf ask refuses for a reason other than a low ratio.
If the guard's refusal came from an inventory of what was actually told rather than
from the denominator, E23's lever would become deployable. That is E24,
pre-registered in `docs/evidence/absence_inventory_design.md`.

#### `stage` is a default bucket, and one failure was misfiled for ten generations

`stage_of` classifies a failure by regex-matching the reply's `reason`, and its
last branch is a fall-through whose own comment says attributing it to recall "is a
DEFAULT, not a measurement". Any unspoken reply with a non-empty reason matching no
pattern is labelled `recall`.

Generation 9's instrumentation showed the tally `{"recall": 10, …}` was mixed. Nine
of the ten are real coverage-gate refusals, reporting coverages of 34–55%. The
tenth, `which thing turns twice?`, reports *"it did not understand and was not in
the mood to babble"* and has a raw binder count of `None`, not `0` — the recall gate
never ran. It is a **comprehension** failure that wore a memory label, and it is why
a recall-side repair was built for a defect that was not on the recall side.

Generation 10 adds a derived field `cause` beside `stage`, splitting `recall` into
`recall_gate` (9), `comprehension` (1) and `unclassified` (0). `stage` is **not**
rewritten and historical rows are **not** backfilled, so every prior measurement
still verifies against its own record. Pre-registered in
`docs/evidence/stage_cause_preregistration.md`; the corrected classification in
`docs/evidence/harness_coverage_diagnosis.md` §8.

The corrected census then ranked the nine downstream failures and proposed **E8**
(`POLAR_ABSENCE_MEANS_NO`) against the three `gating` ones — the only class where a
single repair moves the frozen score. **E8 was aborted at its own pre-registered
condition and never implemented** (`docs/evidence/e8_preregistration.md`). The licence it
required — an inventory the organism actually holds — does not exist: the organ has no
relation store, and all three asks are refused by the **mood** gate at
`organs/neural_language.py:3956-3977` before any answer forms, which the journal shows as
`coverage: null` and `source: null`. So there is no suppressed negative to unlock; saying
`no` would fabricate one. The organ already forbids this at `:3052-3054` — *"It never says
`no`: defect B stays closed until a mechanism can express absence without asserting a
false negative."* Scores are unchanged by construction and no battery was run, because
with no code change both arms would reproduce generation 9/10 ask for ask. E8' is recorded
as future work with the design that *would* satisfy the condition: a session-scoped
closed-world inventory over `who == "you"` rows, answering `no` only when that inventory
is non-empty and contains the queried verb. `tests/test_e8_abort.py` pins the absence, so
a future pass cannot add the flag and mistake a confabulated `no` for the +1 frozen it
would appear to score.

The table prints `warm`, `cold` and `delta` per script and overall. Warm is with
the session's own context, cold is after a restart from saved state; a delta of
`+0.00` means the restart changed nothing. `override` also prints its winner.

### Four measured negatives, kept inert in the organ

Four flag-gated repairs have been run and refuted. Each gene stays in the organ, default
`False`, with its result recorded beside it — deleting a refuted gene invites a retry.

| gene | experiment | what it tried | why it failed |
|---|---|---|---|
| three shape genes | E5 | widen the interrogative parser | **completely inert**; the shape parser is not the binding constraint |
| `RECALL_UNFILTERED_FALLBACK` | E7 | answer from unfiltered recall | never fires — no ask reaches the `if not hits` branch |
| `RESONANCE_SESSION_SCOPE` | E9 | restrict resonance to session words | wanted word still lost to the session's own `the` |
| `RESONANCE_CONTENT_SCOPE` | E10 | also drop function words | winner then sits below `reply_threshold` |

E9 and E10 attacked the `mouth` failure class, diagnosed as **resonance**: the wanted word
was in the candidate pool in all four cases but lost by ~3.8× to static corpus attractors
(`numbered`, `sold`) the session never mentioned. Scoping removed those attractors — and the
organism went silent instead of answering, because `reply_threshold = 0.55` sits **inside the
attractor band** (0.550–0.581).

E10 measured the ceiling for honest content words: `lantern` 0.4129, `bell` 0.1221, `scarf`
0.1526. Nothing a session actually taught reaches 0.55. On this path **comprehension and
attractor are the same event** — the only words that make the organism report understanding
are high-frequency corpus words unrelated to the question. Arm B scored 19/24 frozen, 0/14
probes, 4/4 guarded, **indistinguishable from E9's arm B**: once the organ is silent,
filtering the pool further cannot help.

E10 also refuted its own method. It used the organ's distributional rule (`df * 4 <= n_mem`)
rather than a stopword list, and that rule **keeps `is` and `on`** — the binder is 99.19%
`book` rows, where `the` is ubiquitous and `is`/`on` merely common. Document frequency here
measures corpus style, not lexical class.

Full write-ups: `docs/evidence/e9_result.md`, `docs/evidence/e10_result.md`.

**E11 closed the comprehension line too, at zero brain builds.**
`docs/evidence/comprehension_signal_design.md` proposed replacing that scalar with
*session-provenanced term support* — does a row he was **told**, rather than a book row,
contain this question's terms together? Provenance is the axis resonance lacks, and it needs
no content/function distinction, which E10 proved we do not have. `docs/evidence/e11a_result.md`
records the refutation: the signal **is** ask-dependent (range 0.10–0.75 over 42 asks) and
**is** frequency-independent (no ask's best row overlaps `numbered`/`sold`), exactly as
designed — and it still cannot separate the classes. `min(mouth)` 0.2222 against
`max(recall)` 0.5000; **zero** thresholds admit all four `mouth` asks and no recall-gate
failure. The reason is the substantive result: the recall-gate asks are *equally*
well-supported, because he **was** told the coat is wet, the eggs, the frost biting. Having
the material was never what separated them. No gene was written.

`docs/evidence/answer_formation_diagnosis.md` then traced the nine recall-gate asks and found
the boundary is in the **accounting**, not the retrieval: in five of nine the exact taught
fact *is* the top-scoring row (`there are four eggs in the basket`, `the copper bell turns
twice`) and coverage still lands at 0.538 and 0.514. The gate already stems both sides and
already IDF-weights the terms, so neither naive matching nor an unweighted denominator is to
blame. What remains is that `must` is built from the *question*, so it carries terms no
truthful answer could contain (`is`, `left`, `number`, `of`) plus irregular forms `stem()`
cannot bridge (`bitten` ≠ `bite`, `held` ≠ `hold`). Coverage measures how much of the
question's wording appears in the memory, not how much of the answer's content is supported —
and the floor was calibrated against that inflated denominator. Speakability and the
echo/bigram constraints are **not** implicated: all nine refuse at the floor before any of
them runs.

**E12a and E13a both closed, at zero brain builds.** E12a (`docs/evidence/e12a_result.md`)
recomputed coverage over answerable terms and the pre-registered prediction fired: the guarded
scarf ask goes **0.5797 → 0.6676**, over the floor — it was passing *by refusing*, so the
repair would make him answer. It buys only **2 of 9** recall-gate asks and makes **two worse**
(`what did i tell you about before the kettle?` 0.5470 → **0.2839**), because the repair is
**not monotone**: question-frame words sometimes appear in the memory row, so deleting them
removes *matched* numerator terms too. B5 was clean — no content term dropped — so the failure
is structural, not a bad word set: the floor is a *ratio*, and the guarded ask sits 0.020 below
it. **`ANSWER_COVERAGE_FLOOR` and the guarded invariant are jointly unsatisfiable with this
coverage formula.** E13a (`docs/evidence/e13a_result.md`) tested Class C and moved nothing:
**top row changes on 0/10 asks**, because wherever a taught row is among the candidates it is
*already* top, and for the five asks where a book row wins the taught fact is **not in the
candidate list at all**. So **Class C is candidate generation, not ranking** — a tie-break
cannot promote a row that is not in the pool. No E13b: the gene would be a default-off branch
that provably never fires, the shape of E9's `RECALL_UNFILTERED_FALLBACK`. Together they close
the argument: asks lacking their taught fact need generation, asks having it already score
0.3475–0.5488 with the correct row on top, and the numerator fix that would lift them breaks
the guard.

**E14a closed the candidate-generation line, and it is safe but worthless.**
`docs/evidence/e14a_result.md`: **5 of 9** recall-gate asks lack their taught fact among the
candidates, because `binder.recall` draws 40 rows from 60,000 using question-syntax-dominated
cues. But admitting every session tell caps the best coverage at **0.5488** against a 0.6 floor —
a correct single-row match cannot reach it, because the denominator counts question syntax no
answer row can contain. **No E14b.**

**E15 closed provenanced entailment, at zero builds, and it broke the guard.**
`docs/evidence/e15_result.md`: the design claimed `where did i say the scarf is?` would refuse
*structurally*, because the query is locative and the scarf's evidence is a property. **That
reasoning was wrong** — the script also tells `the coat is on the hook`, a locative row about a
**different subject**, so the ask was licensed, with filler `'the'`. Five currently-passing asks
were newly licensed, **four confidently wrong**: `what bites the latch?` → `latch`,
`how many eggs broke?` → `four` from a row saying eggs are *in the basket*. **Provenance
separates *what he was told* from *what resembles the question*; it does not separate *which told
fact answers this question*.** That needs a subject-specific signal — the axis E11a also lacked.

**E16a tested a write-time relation index and split the result.** `docs/evidence/e16a_result.md`:
**D1 clear — the positive finding.** A subject-keyed index refuses the scarf ask for the right
reason (*"subject 'scarf' is indexed but has NO locative relation — only a property"*); the
coat's row **cannot** license it. This is what E15 could not do, and it confirms **subject
binding is the missing axis**. But **D2 fired** on three wrong fillers, from two defects that are
missing representational commitments rather than tuning: **multi-word subjects** (`copper bell`
where `bell` is expected and `copper` forbidden — no head/modifier distinction) and **quantity
change over time** (answers `four` where `two` is expected and `four` forbidden; a static index
cannot represent a quantity that changes, and `quantity-change` is a class the baseline passes
**4/4**, so it would *regress*). A suffix normaliser also maps `bites → bit`, so write-time
morphology is not derivable without a lexicon. **Right shape of primitive, wrong first
primitive** — the relational index is validated and deferred.

**E17a closed the counting primitive, and its target class is empty.**
`docs/evidence/e17a_result.md`: of **11** quantity asks, **7 already pass** at the coverage gate.
The 4 that fail decompose into three mechanisms, **none of which is entity counting** —
**frequency adverbials** (`how often does the bell turn?` wants `twice`, which is not a cardinal,
so the tell extracts as *"no numeral"* and is invisible to an `(entity, numeral)` index by
construction), **rehearsal counts** (`how often did i say the coat is wet?` is the binder's own
`count` metadata, which four passing asks already use), and a **paraphrase gap**
(`what number of eggs is left in the basket?` fails while `how many eggs are left in the basket?`
— the same proposition — passes). The one genuine event-count ask, `how many eggs broke?`,
**already passes**, so per the design's own placement rule the primitive is never reached:
**E4 fires, zero gain**. Stronger than E14a's "safe but worthless" — not merely no gain, **no
target**. The result also reports four defects in its own probe rather than hiding them, chiefly
that **H2 was a tautological test** which validated the implementation against itself and reported
PASS while the head rule was wrong; consequently the design's polarity-refusal logic **never
executed and is untested, not refuted**.

**Eight accounts of the `mouth`/`recall` boundary are now closed**, and the pattern is
consistent: **every mechanism that makes the agent answer more often also makes it answer
wrongly.** E17a adds what the previous seven did not: **the failing asks are not one class.** The
9 recall-gate asks span frequency adverbials, rehearsal counts, paraphrase gaps, irregular
morphology, two-hop composition and unanswerable-by-design queries — seven experiments each
addressed one facet and were scored against all nine, which is why every one looked like a
near-miss. **The battery's aggregate failure count has been the wrong instrument since E13a.** The guarded scarf invariant is not an obstacle to the repair — **it is the repair
working**, and it has correctly rejected six proposed answer-licensing changes. The honest
conclusion is the one E15's design pre-registered as the alternative: the battery's guarded
invariants and its failing asks are **jointly unsatisfiable** by any mechanism that licenses
answers from what the agent was told. `docs/evidence/architecture_decision_review.md` records the
review; `docs/evidence/counting_primitive_design.md` specifies the narrower next step — store
**events** and derive state by ordered folding, avoid regression **by placement** (consulted only
inside the existing `best_cov < floor` refusal branch, so asks that pass at the coverage gate
never reach it), and **never guess polarity**, so event-count queries are answered and state
queries refuse.

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

`serve.py --electric` (off by default) additionally lets a chat turn **teach**: a
statement heard from `you` enters the keyed taught inventory, a question may be answered
from it, and a relation that was never told is answered with an admission instead of a
guess. Restarting over the same `--session-dir` reloads what was taught — verified on the
real house (`docs/electric_c4_live.md` §8): told three facts, restarted,
`loaded=True taught facts=3`, forward paraphrases came back verbatim and an untaught
relation came back as an admission. `--electric-reverse` (§9) additionally lets a
reverse-role ask like `who does the lantern belong to?` reach the inventory — but only when
the ask **strands a preposition**, because that is what proves the noun in the middle is
the tell's own subject; `who does the mouse chase?` still misses rather than answering the
wrong fact. Off by default, and verified off on the house.

```bash
python tools/electric_chat.py --state state/electric_chat/neural_lang.json
#   "+the scarf is on the hook"   teaches   (the organ has no learned interrogatives,
#   "?where is the scarf?"        asks       so the act is declared: see the doc)
```

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
| Test suite | 734 passed, 3 skipped (at `cb59a2d` + the E9/E10 records) |
| Held-out 24 asks, organ only | 19/24 (at `f2e1748`) |
| Guard scripts | 8/8, 1.00 warm and 1.00 cold, delta +0.00 (at `f2e1748`) |

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