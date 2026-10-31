# Cue dilution — diagnosis, and why the line closes

**Probe:** `docs/evidence/e21a_cue_dilution_probe.py`, data `e21a_cue_dilution.json`. Builds a
brain in **scratch** and replays each script's tells exactly as the harness does, then calls the
binder's own `recall` with the gate's full cue and with a de-framed cue. No organ behaviour change,
no score, no genome, nothing written to live state.

**Headline: de-framing recovers 0 of 4 asks. Its best case moves the taught row from rank 41 to
rank 10 — still far outside the gate's window of 3. Separately, the probe's ranking contradicts the
gate's own recorded `nearest` in both directions on 2 of 4 asks, so it cannot certify any repair
even in principle. No E21 is proposed. The line closes.**

---

## 1. The same-row pair, measured

E20's evidence for cue dilution was a pair sharing one taught row, `the copper bell turns twice`:

| ask | gate `nearest[0]` | row retrieved by gate? |
|---|---|---|
| `how often does the bell turn?` | `the copper bell turns twice` | **yes, rank 1** |
| `how many times does the bell turn?` | `done about the same time as the bell` | no |

The hypothesis: the extra framing words `many`, `times` retrieve corpus text about *times* and
crowd the row out. Removing them should recover it.

## 2. Result: de-framing does not recover the row

`FRAMING` is a closed list of function words, interrogatives and question verbs only — no content
vocabulary, per E16a's D4 and E10's Finding 1.

| ask | cue (full) | cue (de-framed) | removed | rank full | rank de-framed | window |
|---|---|---|---|---|---|---|
| `how many times does the bell turn?` | bell, does, many, times, turn | **bell, turn** | does, many, times | 41 | **10** | 3 |
| `how often does the bell turn?` | bell, does, often, turn | **bell, turn** | does, often | 33 | **10** | 3 |
| `how often did i say the coat is wet?` | coat, did, is, often, say, wet | **coat, wet** | did, is, often, say | 1 | 1 | 3 |
| `what is bitten by the frost?` | bitten, by, frost, is | **bitten, frost** | by, is | 2 | **1** | 3 |

**`asks where de-framing RECOVERS the taught row: 0`.**

The two bell asks collapse to the *identical* de-framed cue `[bell, turn]` and both land at rank
**10**. That is the cleanest possible test of the dilution hypothesis: same row, same cue, same
result — and the result is rank 10, not rank 1. Removing every framing word buys 31 and 23 ranks
respectively and still misses the window by 7.

What occupies the top instead is instructive:

```
top3 de-framed: ['peal at the bell and in a few',
                 'i bethought myself to ring the bell',
                 'a ring to my bell about the hour']
```

All book text about bells. The taught row `the copper bell turns twice` is a **count-1 row competing
against a 59,515-row `book` population** on the cue `[bell, turn]`, and it loses on frequency, not
on framing. **Cue dilution was a symptom; the cause is the same frequency asymmetry the binder
census measured.** De-framing removes the noise but not the competitor mass.

Note also that de-framing *helps* the one ask that was already fine (`bitten by the frost`, 2→1) and
does nothing for the coat ask (1→1). It has no differential effect on the failing population.

## 3. The probe cannot certify a repair: it disagrees with the gate

This is the more serious finding, and it invalidates the instrument rather than the hypothesis.

| ask | gate's recorded `nearest[0]` | probe's rank of the taught row under the *same* cue |
|---|---|---|
| `how often does the bell turn?` | **`the copper bell turns twice`** (the taught row) | **33** |
| `how often did i say the coat is wet?` | `tails of my coat were all soaking wet` (book) | **1** (`the coat is wet`) |

The disagreements run in **both directions**. On the bell ask the gate found the row first and the
probe ranks it 33rd; on the coat ask the probe finds the row first and the gate ranked a book row
first. That is not a bias or an off-by-one — the probe's `binder.recall(cue, k=200)` and the gate's
internal retrieval are **different code paths** producing different orderings from the same cue and
the same replayed tells.

Consequences, stated plainly:

- E20's rank-1 claims came from the **gate's** `nearest`, which is the quantity that actually
  decides the ask. Those stand.
- This probe's ranks come from a path that does not reproduce the gate. **Any "de-framing recovers
  the row" result from it would have been untrustworthy even if it had been positive.**
- The guarded-ask safety condition — the one that killed E12a — **could not be evaluated at all**:
  `where did i say the scarf is?` has `taught_row=None` (E19's `attribution_failed`, its `expect`
  carries no answer words), so the probe skipped it. A repair whose guarded impact is unmeasurable
  is not proposable.

## 4. Why the line closes

Three independent reasons, any one sufficient:

1. **The repair does not work.** De-framing recovers 0 of 4 asks. Its best case is rank 10 against
   a window of 3. The two bell phrasings reduce to one identical cue and one identical failure.
2. **The mechanism is misattributed.** The top-3 under a fully de-framed cue is three book rows
   about bells. The taught row loses to **corpus frequency at count 1**, which is the binder-census
   asymmetry (59,515 `book` vs 466 `droso`), not question-framing noise. E19 already falsified
   eviction as the cause of these failures; this falsifies dilution too. What remains is that a
   count-1 taught row is simply outranked by a 60k-row corpus on its own content words.
3. **The instrument cannot certify safety.** The probe does not reproduce the gate's retrieval, and
   the guarded ask is unattributable. Even a positive result could not have been promoted.

This is consistent with the wider record: E12a/E14a closed the score lever at a 0.5488 ceiling,
E20 closed the cue lever, E19 closed eviction. **Every lever that operates on retrieval of an
existing count-1 row is now closed.** The row is resident, findable, and sometimes ranked first by
the gate — and the ask still fails on coverage arithmetic, or the row is outranked by corpus mass.

## 5. What is left, not proposed here

The only mechanisms E19/E20/E21a leave standing are ones that do not operate on retrieval of a
single existing row:

- **Reinforcement at teach time.** The coat row is count 3 and still fails on coverage; the bell row
  is count 1 and loses on frequency. Whether count affects *gate* coverage (as opposed to probe
  rank) is unmeasured. This is a teaching-policy question, not a retrieval question.
- **Ordering.** The `before the kettle` pair needs a sequence primitive; E19 and E20 both classified
  it as not-a-retrieval-problem.
- **The coverage denominator itself.** Closed by E12a/E14a as not repairable by admission, and E20
  confirmed the row is often already rank 1 when it fails. Reopening it needs a different lever than
  either admission or cueing.

None is pre-registered. E21a was measurement, and it says the cue-dilution line is closed.

## 6. Limitations

- **The probe's retrieval path ≠ the gate's** (§3). This is the dominant limitation and is why no
  repair is proposed regardless of the rank numbers.
- **Guarded ask unmeasurable** — `taught_row=None`, skipped, so `guarded_safe` is absent from the
  JSON rather than True.
- **`FRAMING` is hand-written.** It is restricted to closed grammatical classes, but it is still a
  list I chose. A different list would give different ranks; it would not change the rank-10
  outcome for the bell pair, since both phrasings collapse to the same two content words.
- **Scratch builds, one per ask.** Each probe brain replays only its own script's tells, so binder
  contents differ from a full 42-ask session. This is a plausible contributor to the §3 divergence
  and is not resolved here.
- **k=200.** Ranks are within the top 200; the gate's window is 3.

## 7. Files

| file | change |
|---|---|
| `docs/evidence/e21a_cue_dilution_probe.py`, `.json`, `cue_dilution_diagnosis.md` | new read-only probe, data, this file. |

No change to `tools/`, `organs/`, `connectome/`, `tests/`, genomes or any score.
