# E19 — binder attribution: eviction is falsified, and the gate's cue is the defect

**Run:** `tools.run_generation --generation 19 --lines 1 --tier frozen,probe --binder-attribution`,
control clone `abffa2b7f101`, 42 asks, ~25 s/ask. Journal
`state/selection/generation_19_asks.jsonl`. Probe `docs/evidence/e19_analysis.py`,
machine-readable `e19_analysis.json`. Read-only: the flag writes, evicts and reorders nothing and
touches no score, organ behaviour or genome.

**Headline: `taught_resident` is True on 40 of 42 asks — 0 of 19 failures are eviction. H1 is
falsified. But of the 8 attributed asks where the recall gate actually ran, 4 have the correct
taught row at probe rank 1–2 while the gate's own `nearest` list is all book. The row is resident
and a plain content-word query finds it first; the gate's cue does not.**

---

## 1. Tally

| class | failing (19) | passing (23) |
|---|---|---|
| **eviction** (`taught_resident=False`) | **0** | **0** |
| retrieval | 6 | 7 |
| neither (resident + ranked inside window) | 12 | 14 |
| attribution_failed | 1 | 2 |

**H1 (eviction) is falsified outright.** Not one ask, passing or failing, had a non-resident taught
row. The binder-census story — 0.78% `droso`, blind FIFO, a count-4561 row evicted in E3/P4 — is
real as a *census* fact but is **not** what causes these failures. The taught rows survive to ask
time. Any repair aimed at eviction (§7b value-weighted eviction) would be aimed at a measured
problem that is not this problem.

**H2 (retrieval) is not supported as stated either**, because the raw tally does not discriminate:
6 failing and 7 passing asks both classify `retrieval`. The control check did its job — it says the
classification as written is wrong, not that retrieval is exonerated. Section 2 is why.

## 2. A flaw in my own classification, and what survives it

`taught_rank` is measured under a **probe cue** (the ask's content words). `nearest`, and therefore
`window`, is the **gate's** list under the gate's own cue. Comparing "probe rank ≤ gate window"
mixes two different queries, so `neither` and `retrieval` are not trustworthy as written.

Two concrete failures of the rule:

- **`window=0` is meaningless.** When the gate never ran (`coverage_present=False`), `nearest` is
  empty, so every `rank=None` ask falls into `retrieval` via `resident_not_ranked`. **All 7 passing
  `retrieval` asks are this case** — `stage_all=other`, `window=0`. They passed by a path that never
  retrieved, so their rank is irrelevant. Removing them: **passing genuine-retrieval = 0.**
- **`rank ≤ window` across different cues proves nothing.** `how often did i say the coat is wet?`
  scores `neither` (probe rank 1, window 3) yet failed at the gate with the row absent from
  `nearest`.

Discarding the `window=0` cases leaves a real asymmetry: **5 failing asks have a retrieval defect
under a gate that ran; 0 passing asks do** — because 22 of 23 passing asks never run the gate at
all (`passing_ask_analysis.md` §2a). Retrieval is a property of the failing path, not of asks
generally.

## 3. The 8 attributed gate failures, ranked

These are the failing asks with `coverage_present=True` — the gate ran, so `nearest` and coverage
are real measurements.

| ask | cov | probe rank | window | taught row | count |
|---|---|---|---|---|---|
| `how often did i say the coat is wet?` | 0.454 | **1** | 3 | `the coat is wet` | 3 |
| `what is bitten by the frost?` | 0.340 | **1** | 3 | `the frost bites the latch` | 1 |
| `what is held by the thing the frost bites?` | 0.510 | **2** | 3 | `the frost bites the latch` | 1 |
| `what number of eggs is left in the basket?` | 0.538 | **2** | 3 | `there are four eggs in the basket` | 1 |
| `how often does the bell turn?` | 0.514 | 11 | 3 | `the copper bell turns twice` | 1 |
| `how many times does the bell turn?` | 0.417 | 20 | 3 | `the copper bell turns twice` | 1 |
| `what did i tell you about before the kettle?` | 0.555 | None | 3 | `the lantern is lit` | 1 |
| `what came before the kettle in what i said?` | 0.460 | None | 3 | `the lantern is lit` | 1 |

(`where did i say the scarf is?` also ran the gate, cov 0.570, but is `attribution_failed`:
its `expect` carries no answer words.)

Three distinct populations, not one:

**(a) Cue mismatch — 4 asks, probe rank 1–2, gate `nearest` all book.** The correct row is
resident, reinforced (count 3 for the coat), and a plain content-word query ranks it **first**. The
gate did not surface it. This is the sharpest result in the run and it is not a threshold, ranking
or eviction problem — it is **how the gate builds its cue**.

**(b) Genuinely deep — 2 asks, probe rank 11 and 20.** The `bell turn` family. Resident at count 1,
but far down even under a favourable probe query. Last turn I proposed a rank-keyed repair for
exactly this ask on the strength of a separate probe claiming it was "ranked top"; the harness said
otherwise and I withdrew it. E19 now gives the real number: **rank 11 and 20, not top.** The
withdrawal was correct, and the row is not merely mis-cued but weakly indexed.

**(c) Not ranked at all — 2 asks, probe rank None.** The `before the kettle` family. The row
`the lantern is lit` is resident at count 1 but does not appear in the top 200 under the ask's
content words — unsurprising, since the ask's words (`before`, `kettle`) are not in the row
(`lantern`, `lit`). **These two are an ordering question, not a retrieval question**: the answer
requires sequencing two tells, and no single-row retrieval can supply it. Classifying them as
`retrieval` was wrong.

## 4. What this does to last turn's conclusion

`passing_ask_analysis.md` concluded "taught evidence does not reach retrieval," from
`nearest_has_taught=0`. E19 **narrows and partly corrects** that:

- **Correct:** the gate's `nearest` list really is all book, and coverage 0.340–0.555 really is
  what book rows score against taught-fact questions.
- **Corrected:** the evidence is *reachable*. It is resident, and a content-word query ranks it 1st
  on 2 of 8 and 2nd on 2 more. The failure is not that taught rows are gone or buried beyond
  reach — it is that **the gate's cue does not ask for them the way a plain query does.**

So the binding constraint moves again: gen 2 / gen 6 said *score*, E12a / E14a said *score*,
`passing_ask_analysis` said *candidate set*, and E19 says **cue construction** — with a residual
weak-index population (b) and a not-a-retrieval-problem population (c).

## 5. Limitations, recorded not buried

- **`window=0` misclassification** (§2) inflates `retrieval` on the passing side to 7; the true
  figure is 0. The rule needs a `coverage_present` guard before it is reused.
- **Probe cue ≠ gate cue.** `taught_rank` is explicitly labelled and the cue is journaled in
  `taught_rank_cue`. No claim in this doc treats probe rank as the gate's ranking.
- **3 asks `attribution_failed`** with `no_answer_words` — echo and absence asks whose `expect` has
  no answer list. They are excluded, not guessed.
- **`expected_tell` is cosmetically wrong**: it reports the *last* tell matching the content words
  (`the coat is torn`) while residency correctly resolves `the coat is wet`. It is audit metadata
  only; no classification reads it.
- **Residency is token-subset matching**, so a row is "resident" if any tell's content words are a
  subset of its tokens. That is permissive; a stricter match would only reduce residency, and
  residency is already 40/42, so the eviction verdict is not sensitive to it.

## 6. Next

**No repair is pre-registered.** E19 was measurement, and it split one defect into three
populations that need different treatments. The smallest next step is a read-only probe of
**population (a)** — the 4 cue-mismatch asks — recording the cue the gate actually builds, since
that is the one quantity E19 could not observe without instrumenting the organ. If the gate's cue
for `what is bitten by the frost?` omits `frost` or `bitten`, the defect is named and a flag-gated
cue repair becomes proposable. If the cue contains them and the row still loses, the defect is in
scoring, not cueing, and (a) collapses into the score story that E12a/E14a already closed.

Populations (b) and (c) are separate and should not be bundled with (a): (b) is weak indexing of a
count-1 row, (c) is an ordering primitive that no retrieval repair can supply.

## 7. Files

| file | change |
|---|---|
| `tools/run_generation.py` | `--binder-attribution` (default off), `BINDER_ATTRIBUTION`, `_binder_attribution()`, `_E19_STOP`. Read-only; off means no attribution keys, so a control run stays byte-identical to generation 15. |
| `state/selection/generation_19.jsonl`, `generation_19_asks.jsonl` | new, instrumented control battery. |
| `docs/evidence/e19_analysis.py`, `.json`, `.md` | new probe, data and this file. |
