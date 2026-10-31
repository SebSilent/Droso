# E15 result — ABORTED at C1 and C2. Provenanced entailment licenses the guarded ask and confabulates

**Verdict: `ABORT`. Zero brain builds, no organ change, no gene written.**

`docs/evidence/e15_entailment_probe.py` → `e15_result.json`. The probe stopped after G2 as
specified — the guard is checked first and alone is sufficient to kill the design.

---

## G1 — the guard is licensed. C1 fires.

```
where did i say the scarf is?    role=locative    licensed=True
  filler='the'
  why: locative row 'the coat is on the hook'
```

The design's central claim was that this ask refuses **structurally**, because the query is
locative and the provenanced evidence for the scarf (`the scarf is wet`) is a property. That
reasoning was **wrong**, and the reason it was wrong is the finding:

**The script's tells include a locative row about a different subject.** `the coat is on the
hook` is a provenanced session row, it contains the place preposition `on`, and the subject
check did not exclude it. So a locative row *does* exist in the provenanced evidence — just not
one about the scarf. Entailment licensed the ask on evidence about the **coat**.

The filler is `'the'` — a determiner, not a place. The mechanism licensed an answer and could
not name it.

This is precisely the failure the design said entailment was immune to. E12a broke the guard by
moving a ratio; E15 breaks it by **finding a row that superficially fills the role**. The
semantic guard was not semantic enough: "a provenanced row contains a place preposition" is not
"a provenanced row states where the queried subject is".

## G2 — five currently-passing asks newly licensed, four with wrong fillers. C2 and C4 fire.

| ask | filler | expected | correct |
|---|---|---|---|
| `what turns twice?` | `twice` | — | **wrong** (the answer is the bell, not the frequency) |
| `what bites the latch?` | `latch` | — | **wrong** (the answer is the frost) |
| `how many eggs broke?` | `four` | — | **wrong** (four were in the basket; none broke) |
| `how many eggs are left in the basket?` | `four` | — | **wrong** |
| `how many eggs did i mention first?` | `four` | `four` | correct |

Four of five are **confidently wrong**. `what bites the latch?` returns `latch` — the object of
the question offered back as its answer. `how many eggs broke?` returns `four` from a row that
says eggs are *in the basket*, not that any broke.

This is E8's failure mode exactly: a confident wrong answer scores zero **and teaches
confabulation**, where silence scores zero and asserts nothing. The design's own §4 said
"silence is the output of every refusal path" and "a licence with a wrong filler is worse than a
refusal". G5 was written to catch this; C2 caught it first.

## Why the design failed

The pre-registered expectation was that G1 would not license the scarf ask because its evidence
is a property. The expectation was **falsified by a fact about the scripts that the design did
not check**: each script tells several facts about several subjects, so provenanced evidence for
*any* locative, quantity or role query is usually present somewhere in the session — attached to
the wrong subject.

Provenance separates *what he was told* from *what resembles the question*. It does **not**
separate *which told fact answers this question*. That second separation is the whole problem,
and it is the same axis E11a needed and could not find: a signal that is ask-dependent,
frequency-independent, **and subject-specific**. E11a got the first two and still could not
separate the classes; E15 shows the third is what is missing, and that provenance does not
supply it.

The role query from the organ's own shape parser (`_question_shape`, called unbound — C5 was
satisfied, no hand-written word list) yields `subject_unknown` / `object_unknown` /
`locative_unknown` with a verb and subject. The subject binding is there, but the probe's
locative and quantity branches matched on the presence of a preposition or numeral plus *any*
shared content term, not on the queried subject. Tightening that would be the obvious fix — and
it is the same trap E10 fell into: each tightening is a hand-tuned rule fitted to this battery,
and the design's own C5 exists to forbid exactly that.

## Disposition — no E16

**No flag-gated implementation is proposed.** Three of the five pre-registered abort conditions
fired (C1 guard licensed, C2 other passes licensed, C4 wrong fillers) at zero brain builds.

Seven accounts of the `mouth`/`recall` boundary are now tested and closed:

| line | refuted because |
|---|---|
| resonance ranking (E9, E10) | signal is not ask-dependent |
| comprehension signalling (E11a) | ask-dependent and frequency-independent, still cannot separate |
| coverage numerator (E12a) | lifts the guarded ask over the floor; non-monotone |
| coverage threshold (gen 2, gen 6) | the window 0.555–0.570 is empty |
| coverage ranking (E13a) | inert — the taught row is already top where present |
| candidate generation (E14a) | safe but worthless — ceiling 0.5488 |
| **provenanced entailment (E15)** | **licenses the guarded ask on another subject's row; 4 of 5 licences confidently wrong** |

The pattern across all seven is consistent and worth stating plainly: **every mechanism that
makes the agent answer more often also makes it answer wrongly**, and the guarded scarf
invariant is the instrument that detects this. The invariant is not an obstacle to the repair —
it is the repair working. It has now correctly rejected six proposed answer-licensing changes.

What remains untested is Class A alone (irregular morphology, `bitten` ≠ `bite`), which E12a
and E14a both bound: `what is bitten by the frost?` has its exact taught fact as top row and
scores 0.3475, so perfect morphology leaves it below the floor while Class B stands. Class A
needs a lexical resource the organ does not have, and E10's lesson is that lexical knowledge
introduced to fix one measurement tends to be wrong about the binder's actual composition.

**The honest conclusion is the one §6 of the design pre-registered as the alternative:** the
frozen battery's guarded invariants and its failing asks are **jointly unsatisfiable** by any
mechanism that licenses answers from what the agent was told. The nine recall-gate asks are not
a defect awaiting a repair; they are the coverage gate correctly declining to answer questions
whose answers it cannot verify, and every attempt to widen it has produced confabulation instead.

Cost: **zero brain builds**, against E10's 88 and ~38 min. No core changes, no multi-brain work,
no broad refactors.
