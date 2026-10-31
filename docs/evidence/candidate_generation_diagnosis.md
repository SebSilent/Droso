# Candidate-generation diagnosis — the gap is real but immaterial

Read-only. **Zero brain builds.** No core code changed. No multi-brain work.

`docs/evidence/e14a_candidate_gap.py` → `e14a_candidate_gap.json`.

**Verdict: the candidate pool is not the binding constraint. Even admitting every taught row
as a candidate, no recall-gate ask reaches the floor — 0 of 9. No E14b.**

---

## 1. The gap E13a exposed

E13a found that for **5 of 9** recall-gate asks the taught fact is absent from the recorded
candidates (`taught_in_cands=0/3`), while for the other 4 it is already the top row. Confirmed
here: **5 asks with no taught row among candidates, 5 with one.**

| ask | taught in cands | recorded cov |
|---|---|---|
| `what did i tell you about before the kettle?` | **0** | 0.555 |
| `what came before the kettle in what i said?` | **0** | 0.460 |
| `how often did i say the coat is wet?` | **0** | 0.454 |
| `how many times does the bell turn?` | **0** | 0.417 |
| `what does the bitten thing hold?` | **0** | 0.385 |
| `what number of eggs is left in the basket?` | 1 | 0.538 |
| `how often does the bell turn?` | 1 | 0.514 |
| `what is held by the thing the frost bites?` | 1 | 0.510 |
| `what is bitten by the frost?` | 1 | 0.340 |

## 2. Which mechanism excludes them

**Displacement: ruled out.** All 42 asks share one binder. Four asks retrieve their taught row
from it, so the rows are present and retrievable. Displacement cannot explain why 5 asks lack
them and 4 have them.

**Row encoding: ruled out** by the same argument — identical encoding for both groups.

**Echo / question / interrogative filters: not the exclusion.** The taught rows are not
subsequences of their questions and carry no interrogative, so none of the three filters at
`organs/neural_language.py:3434-3453` would remove them. And `after_echo_filter`,
`after_interrogative_filter`, `after_question_filter` are `None` for every one of these rows —
they populate only on the `if not hits` path, which never fires.

**Cue terms and unscoped recall: this is the mechanism.** `binder.recall(cue, k=40)` draws 40
rows from **60,000**, of which **59,515 are book** and the session contributes a handful.
There is no session scoping and no provenance preference in `recall` — `_provenance_vote`
exists but is Brain B, out of scope. So one taught sentence must beat 40 book rows on raw
similarity, and the cue is dominated by question-syntax terms that are **far more common in the
book corpus than in the taught sentence**. The evidence is in the recorded `nearest` rows: for
`what did i tell you about before the kettle?` the top candidate is
`did you not tell me about it sooner` — a book row matching `tell`/`you`/`about`, exactly the
cue's high-frequency terms. The taught row `the kettle is singing` shares only `kettle`.

**Session scope: absent by construction.** This is E9/E10's frequency-domination reappearing
one layer earlier — not in `_resonance`, which E9/E10 already closed, but in `binder.recall`.

## 3. The upper bound: perfect candidate generation still fails

The repair would admit session rows into `hits`. The gate takes the **maximum** coverage over
hits, so admitting more candidates can only raise `best_cov`. Computing that maximum over
**every tell in the ask's own script** — strictly more candidates than any provenance repair
would supply — gives the ceiling:

| ask | best tell | its coverage | crosses 0.6 |
|---|---|---|---|
| `what number of eggs is left in the basket?` | `there are four eggs in the basket` | **0.5488** | no |
| `how often does the bell turn?` | `the copper bell turns twice` | **0.5445** | no |
| `how often did i say the coat is wet?` | `the coat is wet` | **0.5414** | no |
| `what is held by the thing the frost bites?` | `the frost bites the latch` | **0.5336** | no |
| `how many times does the bell turn?` | `the copper bell turns twice` | **0.4419** | no |
| `what came before the kettle in what i said?` | `the kettle is singing` | **0.3865** | no |
| `what is bitten by the frost?` | `the frost bites the latch` | **0.3475** | no |
| `what did i tell you about before the kettle?` | `the kettle is singing` | **0.3113** | no |
| `what does the bitten thing hold?` | `the latch holds the door` | **0.2220** | no |

**Maximum across all nine: 0.5488. Floor: 0.6. Crossing: 0/9.**

Two rows are worth noting. `what did i tell you about before the kettle?` recorded **0.555**
from a *book* row while its best taught row scores only **0.3113** — the book row is genuinely
the better coverage match, so admitting taught rows would not even change that ask's verdict.
And `what does the bitten thing hold?` peaks at **0.2220**: its answer requires composing two
taught facts (`the frost bites the latch`, `the latch holds the door`), and no single row can
cover a two-hop question. That is a composition gap, not a retrieval gap.

## 4. The guard is safe under this repair — and that is why the negative is clean

```
where did i say the scarf is?    pass=True   must=[did, is, say, scarf]
  recorded coverage   0.570
  best tell coverage  0.5797   'the scarf is wet'
  CROSSES 0.6 IF ALL TELLS ADMITTED: False
    0.5797  'the scarf is wet'
    0.1273  'the coat is wet'
    0.1273  'the coat is on the hook'
```

Unlike E12a, admitting candidates does **not** flip the guarded ask. So E14 would not have
broken the invariant — it simply would not have helped. The repair is safe and inert, which is
the cleanest possible negative: no trade-off to weigh.

## 5. Disposition — no E14b

A flag-gated session-provenance admission in candidate generation would be **safe but
worthless**: it changes no verdict on any of the 42 asks. Writing the gene would add a
default-off branch that provably never alters an outcome — the shape of E9's
`RECALL_UNFILTERED_FALLBACK` and E13a's proposed tie-break.

**The binding constraint is the coverage formula's denominator, not the candidate pool.** Every
ask is capped below 0.6 by Class B — `must` is built from the question, so it carries terms no
truthful answer row could contain (`is`, `left`, `number`, `of`, `does`, `by`, `did`, `say`).
E12a established that fixing the denominator lifts the guarded scarf ask from 0.5797 to 0.6676,
over the floor. So:

- **Candidate generation** (this doc): safe to fix, gains nothing — ceiling 0.5488.
- **Coverage numerator** (E12a): gains 2 of 9, breaks the guard. Refuted.
- **Coverage ranking** (E13a): inert — the taught row is already top where present.
- **Coverage threshold** (gen 2, gen 6): the window between 0.555 and 0.570 is empty.

**Six accounts of the `mouth`/`recall` boundary are now closed.** The remaining untested class
is A — irregular morphology, `bitten` ≠ `bite`, `held` ≠ `hold` — which needs a lexical
resource the organ does not have, and which E12a's data bounds: `what is bitten by the frost?`
has its exact taught fact as top row and scores 0.3475, so even perfect morphology would leave
it below the floor while Class B stands.

The honest reading is that **`ANSWER_COVERAGE_FLOOR = 0.6` is not satisfiable by these asks at
all** under a coverage metric that counts question syntax in the denominator. The floor was
calibrated against a quantity whose maximum, for a short taught fact answering a well-formed
question, is arithmetically below 0.6. That is a property of the metric, not of the agent's
memory — and E12a showed the metric cannot be corrected without spending the guarded invariant
that prevents confabulation.

Cost: **zero brain builds.**
