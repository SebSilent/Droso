# E12a result — ABORT. The guarded scarf ask flips, so E12 is refuted at zero cost

**Verdict: `ABORT E12 — guarded scarf ask reaches the floor`.** The pre-registered prediction
fired exactly. No gene was written, no organ was changed, no build was run.

`docs/evidence/e12a_coverage_probe.py` → `e12a_coverage_probe.json`. Read-only: one journal
read, one binder-meta read, 112 parser frame words read from the organ itself.

---

## The scarf ask

```
where did i say the scarf is?          tier=frozen  pass=True
  must_orig       = [did, is, say, scarf]
  must_answerable = [say, scarf]        dropped = [did, is]
  best_row        = 'the scarf is wet'
  coverage  0.5797  ->  0.6676          floor = 0.6
  FLIPS TO PASSING: True
```

It was already passing — **by refusing**. At 0.5797 it sits below the floor, so the gate
refuses and the guarded invariant holds. Restricting `must` to answerable terms lifts it to
**0.6676**, above the floor, so the gate would admit it and he would answer. That is exactly
the loss generation 2's g2-3 produced at floor 0.566857, reached here by raising the numerator
instead of lowering the threshold.

**Abort condition B2 is met. E12 is refuted.**

## The repair does not even buy what it was designed to buy

Recall-gate asks crossing 0.6: **2 of 9**.

| orig → answerable | | ask | dropped |
|---|---|---|---|
| 0.5445 → **0.6996** | CROSSES | `how often does the bell turn?` | `does` |
| 0.5336 → **0.6399** | CROSSES | `what is held by the thing the frost bites?` | `by, is` |
| 0.5488 → 0.5983 | still below | `what number of eggs is left in the basket?` | `in, is, of` |
| 0.4569 → 0.5813 | still below | `how often did i say the coat is wet?` | `did, is` |
| 0.4442 → 0.5417 | still below | `how many times does the bell turn?` | `does` |
| 0.4036 → 0.5054 | still below | `what does the bitten thing hold?` | `does` |
| 0.3475 → 0.4557 | still below | `what is bitten by the frost?` | `by, is` |
| 0.4753 → **0.4242** | *worse* | `what came before the kettle in what i said?` | `in` |
| 0.5470 → **0.2839** | *worse* | `what did i tell you about before the kettle?` | `about, did, you` |

Two asks get **worse**, one of them badly (0.5470 → 0.2839). The repair is **not monotone**:
question-frame words sometimes appear in the memory row, and deleting them from `must` deletes
matched terms from the numerator as well as unmatched ones from the denominator. `the scarf is
wet` contains `is`; the book rows for the kettle asks contain `about`, `did`, `you`.

So the exchange on offer was: spend the guarded scarf invariant, gain 2 of 9 recall-gate
asks, and lose ground on 2 more. That is a regression dressed as a repair.

## B5 clean — the refutation is not the parser sets' fault

Content terms wrongly dropped: **none**. `kettle`, `frost`, `eggs`, `bell`, `coat`, `scarf`,
`basket` all survived. The organ's own parser vocabulary behaved exactly as intended, which is
what makes this negative informative: **the failure is not a bad word set.** It is structural.

Removing denominator terms raises every score, uniformly, because the floor is a *ratio*. Any
repair that raises the numerator of the guarded ask raises it past 0.6, and the guarded ask
sits only 0.020 below the floor. There is no version of "count fewer unanswerable terms" that
spares it.

## Fidelity of the recomputation

`recomputed_orig` vs the journal's recorded `coverage`: n=10, **max abs delta 0.0305**, mean
0.0154. Worst case `how often does the bell turn?` (recorded 0.514, recomputed 0.5445). The
residual is expected and bounded — `nearest[0]` is the diagnostic nearest row and need not be
the row the gate scored, and the recomputation reads document frequencies from the binder meta
rather than calling `stem_rows()`. The scarf margin (0.5797 → 0.6676) is **0.088 above the
floor**, roughly three times the worst fidelity error, so the flip is not an artefact of the
approximation.

---

## Disposition

**`ANSWER_COVERAGE_FLOOR` and the guarded invariant are jointly unsatisfiable with this
coverage formula.** The numerator cannot be fixed without also breaking the guard, and the
guard is load-bearing — it is the only thing standing between a coverage change and the
confabulation class E8 measured.

This closes the coverage line the way E11a closed the comprehension line and E9/E10 closed the
resonance line. Four accounts of the `mouth`/`recall` boundary have now been tested and
refuted, each at a different layer:

| line | experiment | refuted because |
|---|---|---|
| resonance ranking | E9, E10 | the signal is not ask-dependent; no scope makes it so |
| comprehension signalling | E11a | ask-dependent and frequency-independent as designed, and still cannot separate the classes |
| coverage numerator | **E12a** | raises the guarded ask past the floor; non-monotone; buys 2 of 9 |
| coverage threshold | gen 2, gen 6 | window between 0.555 and 0.570 is empty; 0.566857 lost the scarf invariant |

What remains untested are Classes A and C from `answer_formation_diagnosis.md` — **irregular
morphology** (`bitten` ≠ `bite`, `held` ≠ `hold`, a lexical resource the organ does not have)
and **frequency-dominated ranking** (a book row outranking the taught fact). Neither is
reachable by changing what coverage *counts*; both need machinery the organ lacks, and Class A
would mean introducing a new lexical resource, which is precisely how E10 went wrong.

**No E12b is proposed.** The pre-registration said: if the scarf ask flips, stop and record the
refutation without writing the gene. It flipped.

Cost: **zero brain builds**, against E10's 88 and ~38 min. The pre-flight recomputation over
an existing journal was the whole experiment.
