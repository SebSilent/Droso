# The paraphrase gap — diagnosis, and why the line closes

**Read-only, ZERO brain builds. No core code changed.** No multi-brain work, no broad refactor.

`docs/evidence/paraphrase_gap_probe.py` → `paraphrase_gap_result.json`. Reads the generation-13
journal and both script files.

E17a nominated this as "the narrowest open line and the only one where a correct answer is already
demonstrated to exist in the organ": a failing ask with a passing twin on identical taught
evidence. **The diagnosis does not support that nomination. The line closes, and no E18 is
proposed.** Three independent reasons, in §3.

---

## 1. A correction to the probe's own output

The probe printed, for every pair, `pass form bypasses the recall gate: True`, inferred from the
passing twin having `required=[]` and `coverage=None`. **That inference is wrong and is retracted
here.** Checking the eggs asks directly:

```
PASS  cov=None  req=None  how many eggs did i mention first?
PASS  cov=None  req=None  how many eggs broke?
PASS  cov=None  req=None  did any egg break?
PASS  cov=None  req=None  how many eggs are left in the basket?
FAIL  cov=0.538 req=['basket','eggs','in','is','left','number','of']
                          what number of eggs is left in the basket?
```

**Every** passing ask has `cov=None`, `req=None`, `stage=None`, `cause=None` — not just the twins.
The journal records coverage, required terms, nearest rows and stage **only on failure**. So
`coverage=None` on a passing ask is missing data, not a bypassed gate.

This matters more than the pairs themselves: **the passing twin's internal state is not recorded
anywhere.** The comparison E17a proposed — trace candidate generation, coverage terms and answer
path for a failing ask *and* its passing twin, then take the minimal difference — **cannot be
executed read-only**, because one side of every comparison is absent from the instrument.

## 2. What the failing side does show

Four pairs across three propositions. All four failing asks fall into classes already closed:

| failing ask | top retrieved row | cov | class | closed by |
|---|---|---|---|---|
| `how often does the bell turn?` | **`the copper bell turns twice`** — the correct taught row | 0.514 | coverage denominator | E12a, E14a |
| `what did i tell you about before the kettle?` | `did you not tell me about it sooner` — a **book** row | 0.555 | candidate generation | E14a |
| `what came before the kettle in what i said?` | `when the water in the kettle was boiling` — a **book** row | 0.460 | candidate generation | E14a |
| `which thing did i mention earlier than the kettle?` | not recorded (`stage=mouth`) | — | mouth / resonance | E9, E10 |

The first is the sharpest: **the correct row is retrieved and ranked top**, and the ask still
fails at 0.514 against a 0.6 floor, because the denominator counts question syntax (`how`,
`often`, `does`) that no answer row can contain. That is precisely E12a's structural finding and
E14a's ceiling of 0.5488 — not a new mechanism.

The second and third retrieve **book rows** that share a content word (`kettle`, `tell`) while the
taught row is not in the candidate list at all. That is E14a's Class C, where admitting every tell
still capped coverage at 0.5488.

The fourth passed the gate and failed downstream — E9/E10's resonance defect.

**No failing ask in the battery exhibits a mechanism that is not already closed.**

## 3. Why the line closes

**(a) The twins are not paraphrases in the relevant sense.** They are structurally *easier
question types*, and the surface forms show it without needing the journal:

- `which did i tell you first the lantern or the kettle?` and
  `of the lantern and the kettle which one came first?` are **multiple-choice**: they name the
  answer candidates inside the question. Matching `lantern` requires no retrieval of an entity the
  question never mentions.
- `the bell turns how often?` is **declarative with the wh-word in situ** — nearly identical to the
  tell `the copper bell turns twice`, sharing `the bell turns` as a contiguous trigram.
- The failing forms are **canonical wh-interrogatives with auxiliary inversion**:
  `how often does the bell turn?`, `what did i tell you about before the kettle?`. These introduce
  `does`, `did`, `about`, `before` — tokens that appear in no answer row and inflate the
  denominator.

A pass/fail asymmetry between a multiple-choice form and an inverted wh-question is **expected**,
and it does not imply a repairable defect. E17a read the asymmetry as "the evidence is sufficient,
only the surface form differs"; the forms themselves show the *question type* differs, which
changes what retrieval has to do.

**(b) The comparison is not executable read-only.** Per §1, the journal holds no coverage,
required terms, nearest rows or stage for any passing ask. Tracing the passing side needs
instrumented brain builds — and even then it would measure a different question type, so the
"minimal difference" would conflate surface form with question type. There is no read-only
instrument that can isolate a single mechanism here, and E17a's own probe defects (a tautological
H2, misrouted state queries, a silent fold drop) show what happens when a probe is trusted past
what it measures.

**(c) Every failing twin is already accounted for.** §2 maps all four onto closed classes. A repair
aimed at "the paraphrase gap" would in fact be a fourth attempt at the coverage denominator or a
third at candidate generation — both pre-registered as closed, both with measured ceilings below
the floor.

## 4. Disposition — no E18

**No flag-gated repair is proposed.** There is no single mechanism to gate: the four failing asks
need three different repairs, all previously attempted, and the passing twins that made the class
look novel are easier question types rather than paraphrases.

An E18 built on this nomination would have inherited E17a's error — treating a question-type
difference as a surface-form difference — and would have been scored against all 9 recall-gate
asks while addressing at most 2. That is the exact failure mode §5 of `e17a_result.md` identified:
**the aggregate failure count has been the wrong instrument since E13a.**

### What would reopen it

Not a repair — a measurement. The journal records coverage, required terms and nearest rows
**only on failure**, which is why eight experiments have each had to re-derive the passing side
from scratch. Recording the same fields on **passing** asks would make pass/fail pairs directly
comparable for the first time, at the cost of journal size and one instrumentation change in
`tools/heldout_eval.py` — **not** in the organ, and not a core change. Until that exists, any
claim about what distinguishes a passing ask from a failing twin is inference from the failing
side alone.

That is a tooling proposal, deliberately not pre-registered as an experiment: it repairs the
instrument, not the agent, and it cannot change a score.

### Standing conclusion

**Eight accounts of the `mouth`/`recall` boundary remain closed, and the paraphrase gap is not a
ninth.** The guarded scarf invariant has now correctly rejected seven proposed answer-licensing
changes. The honest reading of the whole sequence is the one E15's design pre-registered as its
alternative: the battery's guarded invariants and its failing asks are **jointly unsatisfiable**
by any mechanism that licenses answers from what the agent was told — and the failing asks are not
one class, so no single mechanism was ever going to move the aggregate.
