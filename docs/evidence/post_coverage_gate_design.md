# Post-coverage answer licensing — provenanced entailment instead of a single-row ratio

**Design only. No core code changed.** No multi-brain work, no broad refactor.

This document exists because six accounts of the `mouth`/`recall` boundary have been tested and
closed, and they converge on one conclusion: the binding constraint is the **coverage metric
itself**, not the agent's memory, its candidate pool, its ranking, or its threshold.

---

## 1. Why the coverage ratio cannot be repaired

`ANSWER_COVERAGE_FLOOR = 0.6` gates on a single number: the IDF-weighted fraction of the
question's `must` terms that appear in **one** binder row (`organs/neural_language.py:3464-3476`).

Four measured facts close it:

| attempt | result |
|---|---|
| lower the threshold | window between best failing coverage (0.555) and the guarded scarf ask (0.570) is **empty**; g2-3 at 0.566857 lost the invariant |
| count only answerable terms (E12a) | scarf **0.5797 → 0.6676**, over the floor. Buys 2 of 9, makes 2 worse, **non-monotone** |
| prefer taught rows in ranking (E13a) | **inert** — top row changes on 0/10; the taught row is already top wherever present |
| admit all taught rows as candidates (E14a) | **safe but worthless** — ceiling **0.5488** across all 9, so 0/9 cross |

The structural reason, from E14a: `must` is built from the **question**, so it carries terms no
truthful answer row could contain (`is`, `left`, `number`, `of`, `does`, `by`, `did`, `say`).
For a short taught fact answering a well-formed question, the maximum attainable ratio is
**arithmetically below 0.6**. The floor was calibrated against a quantity with a low ceiling.

And the ratio is **single-row**: `what does the bitten thing hold?` peaks at **0.2220** because
its answer requires composing `the frost bites the latch` with `the latch holds the door`. No
single row can cover a two-hop question, so no threshold and no candidate set can license it.

**Conclusion: the metric has to change, not be tuned.** But it must change in a way that keeps
the guarded invariant — which is the only thing standing between a coverage change and the
confabulation class E8 measured.

## 2. The design principle: license by entailment, not by lexical overlap

> An answer is licensed **only when a provenanced evidence set entails it** — when rows he was
> *told*, not rows from the book, supply the relation the question asks about and fill its slot.

Three properties, each answering a specific measured failure:

1. **Provenanced.** Evidence must come from rows with `who != "book"`. The binder is 59,515
   `book` of 60,000; E14a showed book rows out-match taught rows on question-syntax terms
   (`did you not tell me about it sooner` beat `the kettle is singing` at 0.555 vs 0.3113).
   Provenance is the axis that separates *what he was told* from *what resembles the question*.
   This is E11a's one validated finding: provenance **is** ask-dependent and **is**
   frequency-independent. E11a failed because it used provenance as a *comprehension* signal;
   here it is used as an *evidence* filter, which is what it is good at.
2. **Relational, not bag-of-words.** The question's shape parser already yields a role query
   (`subject_unknown` / `object_unknown` / `locative_unknown`). Licensing asks whether a
   provenanced row **fills the queried role**, not whether it shares enough words. This is what
   makes the ceiling problem disappear: the denominator stops containing question syntax
   because there is no denominator.
3. **Compositional where a single row cannot entail.** Two provenanced rows sharing a term may
   jointly entail a two-hop answer. Bounded to **depth 2** and to provenanced rows only, so the
   search space is the handful of session rows, not 60,000.

## 3. How the guarded scarf invariant is preserved — structurally, not by luck

This is the load-bearing part, and it is why the design is not E12a with extra steps.

`where did i say the scarf is?` currently **passes by refusing**: coverage 0.570 < 0.6, so the
gate declines and the frozen invariant holds. E12a broke it by raising the ratio to 0.6676 —
the ask started answering, and answering is what the invariant forbids.

Under entailment licensing the ask **still refuses, for a different and stronger reason**: the
question queries a **locative** role (`where … is`), and the provenanced evidence for the scarf
is `the scarf is wet` — a **property**, not a location. No provenanced row fills the queried
locative role, so there is nothing to entail and the mechanism declines.

The distinction matters:

- **E12a's guard risk was arithmetic.** A ratio moved past a constant. Any future change to the
  ratio, the weights, or the floor could move it back over, and nothing in the mechanism knows
  the guard exists.
- **Entailment's guard is semantic.** The ask refuses because the evidence does not answer the
  question that was asked. That is stable under reweighting, under floor changes, and under
  admitting more candidates — none of which can manufacture a locative row that was never told.

**This is falsifiable before any code is written**, and §6 makes it the first thing E15 checks.
If the entailment rule *does* license the scarf ask, the design is refuted at zero cost and no
gene is written.

## 4. How it refuses and silences unsupported asks

Refusal is the **default**, and licensing is the exception. Four independent gates, all of which
must pass:

| gate | refuses when | which measured failure it answers |
|---|---|---|
| **provenance** | no `who != "book"` row bears on the query | E14a: book rows dominating the cue |
| **role** | no provenanced row fills the queried role | the scarf ask (locative vs property) |
| **slot** | the role is filled but the filler is not a content term | E9/E10: function-word attractors |
| **composition bound** | a two-hop answer needs > 2 provenanced rows, or the chain has no shared term | E14a: `bitten thing hold` at 0.2220 |

Crucially, **silence is the output of every refusal path.** The mechanism never emits a
low-confidence guess, never falls back to `max(resonance)`, and never widens to book rows when
provenanced rows run out. E8's abort condition applies verbatim: a confident wrong answer is
worse than silence, because silence scores zero and asserts nothing while a wrong answer scores
zero and teaches confabulation.

The existing coverage gate is **not removed**. The new mechanism is an **alternative licensing
path consulted only when the coverage gate has already refused**, so:

- every ask that passes today still passes by the same route (flag-off identity is trivial);
- the coverage floor, its IDF weights and `stem()` are untouched;
- the guarded invariant is doubly protected — the coverage gate still refuses the scarf ask
  first, and the entailment path independently declines it.

That ordering is the smallest-blast-radius property available: the mechanism can only ever
**add** licences, and §3 plus §6 constrain which.

## 5. Flag-gated prototype

```python
LICENSE_BY_PROVENANCED_ENTAILMENT = False   # default off; inert
ENTAILMENT_MAX_HOPS = 2                     # module constant, NOT a genome gene
```

One gene, one call site: inside the `best_cov < ANSWER_COVERAGE_FLOOR` branch at
`:3476`, **before** the existing `_prop_join` / `_band_walk` fallbacks, so it is consulted only
on an already-refused ask and its refusals fall through to the current behaviour unchanged.

`ENTAILMENT_MAX_HOPS` is a module constant for the same reason E12's floor was to be: the
selection harness mutates genes, and a bound that selection can drift is a bound that will be
tuned to the battery.

New read-only helper `_provenanced_evidence(role_query)` returning the session rows that bear on
the query, plus `_entails(evidence, role_query)` returning `(licensed, filler, hops, why)`.
Neither writes the binder, evicts, nor is reachable from the recall gate — the isolation E10's
`_is_content_word` was tested for, because the guarded floor must stay untouched.

**Not reused:** `_provenance_vote`, which is Brain B behind `DROSO_SECOND_BRAIN` and out of
scope. The provenance test here is the `who != "book"` / `when >= session_t0` idiom already used
by `_ordinal_answer` at `:3070-3080`, which is single-brain.

## 6. E15 — the read-only probe, and it is the experiment

**Zero brain builds. No organ change. No gene.** Everything needed is on disk: the
generation-13 journal (`required`, `nearest`, `coverage`, `stage`, `cause`, `pass`) and
`tools/scripts_heldout.json` (the exact tells, hence the exact provenanced evidence set).

E15 implements `_entails` as a **standalone function in the evidence script** and evaluates it
over all 42 asks. It reports, in this order:

1. **G1 — the guard.** Does entailment license `where did i say the scarf is?` If **yes →
   ABORT**, record the refutation, write no gene. This is checked first and alone is sufficient
   to kill the design.
2. **G2 — every other currently-passing ask.** Does entailment license any of the 23 passes,
   especially any that pass *by refusing*? Any yes is a guard break in all but name.
3. **G3 — the 9 recall-gate asks.** How many are licensed, and with what filler? Predicted from
   the trace: the eggs ask (`there are four eggs in the basket` → `four`), the bell asks
   (`the copper bell turns twice` → `twice`), the frost asks (`the frost bites the latch` →
   `latch`). These are the asks E14a proved the ratio can never license.
4. **G4 — composition.** Is `what does the bitten thing hold?` licensed at 2 hops
   (`frost bites latch` + `latch holds door` → `door`)? **This depends on Class A** — it needs
   `bitten` to match `bites`, which `stem()` does not do. Predicted: **not licensed**, and the
   probe must report the morphology mismatch as the reason rather than silently scoring it a
   failure of composition.
5. **G5 — false licences.** For every licensed ask, is the filler the *expected* answer from the
   script's `expect` block? A licence with a wrong filler is worse than a refusal, and this is
   the check that catches it before a battery does.

**Abort conditions, stated before running:**

| # | condition | consequence |
|---|---|---|
| C1 | G1 licenses the scarf ask | **abort**, no gene — the design breaks the invariant it was built to preserve |
| C2 | G2 licenses any currently-passing ask | **abort** — same failure, different ask |
| C3 | G3 licenses **zero** asks | **abort** — the mechanism is inert, the shape of E9/E13a |
| C4 | G5 finds any licence whose filler is wrong | **abort** — confabulation, the E8 failure mode |
| C5 | licensing depends on a hand-written word list | **abort** — E10's error; the role query must come from the organ's own shape parser |

**Pre-registered expectation.** G1 **will not** license the scarf ask, because its provenanced
evidence is a property (`the scarf is wet`) and the query is locative — and if that reasoning is
wrong the design dies here at zero cost. G3 **will** license the eggs, bell and frost asks,
which is a gain the coverage ratio provably cannot produce (E14a's ceiling is 0.5488). G4
**will not** license the two-hop ask, because Class A morphology is unresolved. So the expected
E15 outcome is **3–5 of 9 recall-gate asks licensable, guard intact, zero false licences**.

If that holds, E15b is the flag-gated two-arm battery (generations 19/20, 84 builds, ~36 min)
with the predictions recomputed from E15's actual licence list — not from this document's
estimate. If G1 or G2 fires, the post-coverage line closes with the coverage line, and the
honest conclusion is that the frozen battery's guarded invariants and its failing asks are
**jointly** unsatisfiable by any mechanism that licenses answers from what the agent was told.

## 7. Expected score changes

Stated as a range because E15 has not run, and to be recomputed from its output before E15b:

| metric | now | if E15 confirms | note |
|---|---|---|---|
| frozen | 19/24 | **19–21/24** | 2 frozen recall-gate asks are licensable (`eggs`, `bell`) |
| paraphrase probes | 0/14 | **0–3/14** | first movement in this metric in any experiment |
| guarded | 4/4 | **4/4** | preserved structurally, §3; abort if not |
| `mouth` class | 4 | **4** | untouched — E9/E10 closed that line |
| `gating` class | 3 | **3** | untouched — E8 aborted, mood gate not addressed |

The frozen gain is the reason this is worth a battery: **no prior experiment has moved the
frozen score**, and E12a's only route to it spent the guard.

## 8. Out of scope

Multi-brain and population work (standing constraint). Broad refactors. Removing or retuning
`ANSWER_COVERAGE_FLOOR`, the IDF weights, `stem()`, `reply_threshold`, or the echo/bigram/
speakability constraints (not implicated — all nine recall-gate asks refuse at `:3476` before
any of them runs). An irregular-morphology lexicon (Class A) — a new lexical resource, and E10's
lesson is that lexical knowledge introduced to fix one measurement tends to be wrong about the
binder's actual composition; G4 is designed to report Class A as the reason for a miss rather
than paper over it. §7b value-weighted eviction — noted only because a mechanism that reads
provenanced rows would benefit from an eviction policy that keeps them, and the current policy is
**blind FIFO**, which E3 observed evicting a `droso` row with count 4561. That is a reason to do
§7b before relying on entailment in a long-lived learner, not a reason to widen E15.
