# E20 — cue-construction probe: the cue is not the defect, and E19's headline was an artifact

**Probe:** `docs/evidence/e20_cue_probe.py`, machine-readable `e20_cue_probe.json`. Read-only over
`state/selection/generation_19_asks.jsonl`. **No new instrumentation was needed and none was
added**: the gate's cue is already journaled as `required` (the organ's `must` list) and its
candidate list as `nearest`, so E20 cross-references those against E19's authoritative
`taught_row`. No retrieval change, no score, no genome, no organ behaviour, no brain build.

**Headline: the cue does not omit the taught terms. On 4 of the 9 gate asks the gate retrieves the
correct taught row and ranks it FIRST — and still refuses, at coverage 0.340–0.538. Cue
construction is exonerated for that population; the binding constraint is the coverage
denominator, which E12a/E14a already measured and closed. The line is recorded as a negative and
closed.**

---

## 1. Retraction: E19's `nearest_has_taught=0` was a bug, not a measurement

E19 and `passing_ask_analysis.md` both reported that every gate ask retrieved only book rows. That
test was `str(n).startswith("droso:")`. The probe confirms journal `nearest` entries are **bare
text with no who-prefix at all**:

```
total_nearest_entries: 30
with_droso_prefix:      0
with_book_prefix:       0
with_any_who_prefix:    0
```

The test could never match. Its "0" was an artifact of the prefix assumption, and the claim built
on it — "taught evidence does not reach retrieval" — is **withdrawn**. Re-tested by exact string
equality against `taught_row`, the truth is:

**4 of 9 gate asks retrieve the correct taught row, at rank 1.**

This is the second time a separate probe's ranking claim has been overturned by the harness journal
(E19 corrected a "ranked top" claim to rank 11/20). The lesson is the same both ways: prefix and
substring heuristics over journal text are not measurements. Exact membership against a
row resolved from the scripted tells is.

## 2. The nine gate asks

| ask | cov | taught row | in `nearest`? | rank | taught content words in cue |
|---|---|---|---|---|---|
| `what is bitten by the frost?` | 0.340 | `the frost bites the latch` | **yes** | **1** | frost |
| `what is held by the thing the frost bites?` | 0.510 | `the frost bites the latch` | **yes** | **1** | bites, frost |
| `how often does the bell turn?` | 0.514 | `the copper bell turns twice` | **yes** | **1** | bell |
| `what number of eggs is left in the basket?` | 0.538 | `there are four eggs in the basket` | **yes** | **1** | basket, eggs, in |
| `how often did i say the coat is wet?` | 0.454 | `the coat is wet` | no | – | coat, is, wet |
| `how many times does the bell turn?` | 0.417 | `the copper bell turns twice` | no | – | bell |
| `what does the bitten thing hold?` | 0.385 | `the frost bites the latch` | no | – | *(none)* |
| `what did i tell you about before the kettle?` | 0.555 | `the lantern is lit` | no | – | *(none)* |
| `what came before the kettle in what i said?` | 0.460 | `the lantern is lit` | no | – | *(none)* |

## 3. Answer to the question E20 was asked

**Does the cue omit required taught terms, or include them while the row still loses?**

**It includes them, and the row still loses.** For the four rank-1 asks the cue carried the taught
content terms, retrieval surfaced the row, and the gate ranked it **first**. The gate then refused
anyway, because coverage — the fraction of `must` terms the row satisfies — is 0.340 to 0.538
against a 0.6 floor. Look at what the cue demands that a declarative tell can never contain:

| ask | cue terms the taught row cannot match |
|---|---|
| `what is bitten by the frost?` | `bitten`, `by`, `is` |
| `what is held by the thing the frost bites?` | `by`, `held`, `is`, `thing` |
| `how often does the bell turn?` | `does`, `often`, `turn` |
| `what number of eggs is left in the basket?` | `is`, `left`, `number`, `of` |

These are question syntax and passive/relative morphology. `what is bitten by the frost?` asks the
row `the frost bites the latch` to contain `bitten`, `by` and `is`. It contains `frost` and a
finite `bites`. That is 1 of 4, and the measured 0.340 reflects partial stemming credit. **The row
is the right row, ranked first, and it is arithmetically incapable of clearing the floor.**

This is precisely the mechanism E12a measured and E14a closed: admitting all tells caps coverage at
0.5488 < 0.6. E20 arrives at the same ceiling from the opposite direction — not "the row isn't in
the candidate set" but "the row is first in the candidate set and the denominator is unwinnable."

**So the cue-repair hypothesis is falsified for population (a).** No cue change can help an ask
whose cue already retrieves the right row at rank 1.

## 4. The five not-retrieved asks are two other problems, not cue omission

- **Cue dilution (2 asks).** `how many times does the bell turn?` and `how often did i say the coat
  is wet?` carry the same taught content words as their rank-1 siblings, but add `many`/`times` and
  `did`/`often`/`say`, which retrieve book rows *about* saying and times
  (`does not often say all this to herself`, `many times again until his face was a`). The taught
  row is crowded out by corpus text that matches the question's own framing words. Note the direct
  comparison: `how often does the bell turn?` retrieves the row at rank 1; `how many times does the
  bell turn?` does not retrieve it at all. **Same row, same stem, different cue — the extra
  question words are what lose it.**
- **Ordering asks (2 asks).** The `before the kettle` pair expects `the lantern is lit`, which
  shares **no word** with the ask by nature: the answer is defined by sequence, not content. E19
  already flagged these as not-a-retrieval-problem and E20 confirms it — no cue can contain the
  answer's words when the question never mentions them.
- **Morphology plus a hop (1 ask).** `what does the bitten thing hold?` has zero content overlap:
  cue `bitten`/`hold` against row `bites`/`latch`. Answering needs passive→active resolution *and* a
  hop to the object. This is the hardest of the nine and is not a cue problem either.

## 5. Limitation in the probe's own verdict rule

The script's binary verdict labelled **all 9** asks `cue_omits_taught_terms`, because it counted
any taught word absent from the cue as an omission — including the determiner `the`, which no cue
will ever carry. That rule is too loose to be the finding, and the tally
(`cue_omits: 9, include_but_lose: 0, include_and_retrieve: 0`) should be disregarded. The
classification in §3–§4 is made by hand from the same recorded fields, separating determiners and
question syntax from genuine content omission, and separating "row retrieved" from "row not
retrieved". The probe's per-ask field dumps are the evidence; its verdict tally is not.

Also recorded: `attribution_failed` on 1 gate ask (`where did i say the scarf is?`, cov 0.570) whose
`expect` carries no answer words, so no `taught_row` was resolved and it is excluded rather than
guessed. That leaves 9 of the 10 gate asks attributed.

## 6. Verdict: negative, line closed

**No cue repair is proposed.** The pre-registered branch was: if the cue omits required taught
terms, propose the smallest flag-gated cue repair; if not, record the negative and close the line.
**It does not.** For the four asks where the row is retrieved at rank 1 the cue is demonstrably
adequate, and for the five where it is not, the cause is cue dilution by question-framing words,
ordering asks whose answers share no words with the question, or a morphology-plus-hop ask — none
of which a cue-construction change addresses without also changing what the gate demands, which is
the score question E12a/E14a already closed.

The chain of binding constraints, corrected: gen 2 / gen 6 said *score*; E12a / E14a said *score*
and measured the 0.5488 ceiling; `passing_ask_analysis` said *candidate set*; E19 said *cue
construction*; **E20 returns it to score**, with the candidate set shown to be adequate on 4 of 9
and the cue shown to be the wrong lever on the rest.

What remains genuinely open, and is *not* a cue or score question:
1. **Cue dilution** — question-framing words (`many`, `times`, `often`, `say`) retrieve corpus text
   that crowds out a taught row the same cue would otherwise find. This is the one E20 finding that
   is new, mechanistically distinct, and evidenced by a same-row pair that differs only in cue.
2. **Ordering** — the `before the kettle` pair needs a sequence primitive, not retrieval.

Neither is proposed for repair here. E20 was measurement, and its measurement says the cue lever is
closed.

## 7. Files

| file | change |
|---|---|
| `docs/evidence/e20_cue_probe.py`, `.json`, `.md` | new read-only probe, data and this file. |
| `docs/evidence/e19_result.md` | §1 retraction recorded here; E19's `nearest_has_taught` claim is withdrawn. |

No change to `tools/`, `organs/`, `connectome/`, `tests/`, genomes or any score.
