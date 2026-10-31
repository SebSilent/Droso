# E13a result — NEGATIVE. Provenance re-ranking gains nothing, and Class C is not a ranking problem

**Verdict: `NEGATIVE — no E13b`.** Zero brain builds, no organ change, no gene written.
Guard intact: the scarf ask does not flip.

`docs/evidence/e13a_provenance_rerank.py` → `e13a_provenance_rerank.json`. Read-only over the
generation-13 journal plus binder document frequencies.

---

## The structural prediction held, and then some

Stated before running: the gate sorts candidates by coverage **descending** and takes
`scored[0]`, so `best_cov` is already the **maximum** over hits. Re-ranking by provenance can
therefore only lower it, never raise it.

Measured: **asks whose top row changes: 0/10. Coverage rose on 0, fell on 0.** Not "taught
facts promoted but coverage fell" — nothing moved at all.

## Why nothing moved: Class C was mis-classified

The `taught_in_cands` column is the finding.

| ask | taught in candidates | top row | cov |
|---|---|---|---|
| `what number of eggs is left in the basket?` | **1/3** | taught | 0.5488 |
| `how often does the bell turn?` | **1/3** | taught | 0.5445 |
| `what is held by the thing the frost bites?` | **1/3** | taught | 0.5336 |
| `what is bitten by the frost?` | **1/3** | taught | 0.3475 |
| `where did i say the scarf is?` (guarded) | **1/1** | taught | 0.5797 |
| `what did i tell you about before the kettle?` | **0/3** | book | 0.5470 |
| `what came before the kettle in what i said?` | **0/3** | book | 0.4753 |
| `how often did i say the coat is wet?` | **0/3** | book | 0.4569 |
| `how many times does the bell turn?` | **0/3** | book | 0.4442 |
| `what does the bitten thing hold?` | **0/3** | book | 0.4036 |

**Wherever a taught row is among the candidates, it is already the top row.** Provenance
re-ranking has nothing to promote. And for the five asks where a book row wins, the taught
fact is **not in the candidate list at all** — `taught_in_cands=0/3`.

So Class C is not a *ranking* problem. It is a **candidate generation** problem: the taught
fact never reaches `hits`. The diagnosis doc recorded `done about the same time as the bell`
outranking `the copper bell turns twice` for `how many times does the bell turn?`; what E13a
shows is that `the copper bell turns twice` was never a candidate. A tie-break cannot promote
a row that is not in the pool.

## Recall-gate asks crossing 0.6: **0 of 9**

Unchanged from the recorded coverages, exactly as predicted. And the four asks that *do* have
their taught fact as top row still sit at 0.3475–0.5488 — below the floor with the correct row
in hand. That is Classes A and B, which E12a already refuted: fixing the numerator lifts the
guarded scarf ask over the floor.

## Guarded scarf ask (B2): does **not** flip

```
where did i say the scarf is?   pass=True
  top_by_cov   0.5797  taught=True  'the scarf is wet'
  top_by_prov  0.5797  taught=True  'the scarf is wet'
  delta +0.0000   FLIPS TO PASSING: False
```

Its top row is already the taught fact, so provenance re-ranking is a no-op on it. The guard
is safe under this repair — but the repair buys nothing, so there is nothing to protect.

---

## Disposition

**No E13b.** A flag-gated provenance tie-break in the coverage ranking would be inert: it
changes no top row on any of the 42 asks, moves no coverage, and crosses no floor. Writing
the gene would add a default-off branch that provably never fires on this battery — the same
shape as E9's `RECALL_UNFILTERED_FALLBACK`, which never fired because no ask reached the
`if not hits` branch.

**The untested repair is candidate generation, not ranking** — getting the taught row into
`hits` for the five asks where it is absent. But E13a bounds what that could buy: the four
asks that already have the taught fact on top still fail at 0.3475–0.5488, so generation alone
would not lift them over 0.6 either. They are capped by Class B (unanswerable question syntax
in the denominator), and E12a established that fixing Class B breaks the guarded invariant.

The two results compose into a closed argument:

- **E12a** — fixing the *numerator* (count only answerable terms) lifts the guarded scarf ask
  from 0.5797 to 0.6676, over the floor. Refuted.
- **E13a** — fixing the *ranking* (prefer taught rows) moves nothing, because the taught row is
  already top wherever it is present. Inert.
- **Together** — the asks that lack their taught fact need candidate generation; the asks that
  have it need a numerator fix; and the numerator fix is blocked by the guard.

Five accounts of the `mouth`/`recall` boundary are now tested and closed: resonance ranking
(E9, E10), comprehension signalling (E11a), coverage numerator (E12a), coverage threshold
(gen 2, gen 6), and coverage ranking (E13a). What is left is Class A — irregular morphology,
`bitten` ≠ `bite`, `held` ≠ `hold` — which needs a lexical resource the organ does not have,
and candidate generation, which E13a shows is bounded by Class B.

Cost: **zero brain builds**, against E10's 88 and ~38 min.
