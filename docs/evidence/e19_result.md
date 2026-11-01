# E19 — binder attribution: eviction is falsified, and the gate's cue is the defect

**Run:** `tools.run_generation --generation 19 --lines 1 --tier frozen,probe --binder-attribution`,
control clone `abffa2b7f101`, 42 asks, ~25 s/ask. Journal
`state/selection/generation_19_asks.jsonl`. Probe `docs/evidence/e19_analysis.py`,
machine-readable `e19_analysis.json`. Read-only: the flag writes, evicts and reorders nothing and
touches no score, organ behaviour or genome.

> **RETRACTED IN PART by `e20_result.md` §1.** This file's claim that the gate's `nearest` list is
> "all book" / that taught evidence does not reach retrieval rested on a
> `startswith("droso:")` test, but journal `nearest` entries carry **no who-prefix at all**, so the
> test could never match. Re-tested by exact string equality, **4 of 9 gate asks retrieve the
> correct taught row at rank 1.** The eviction finding in §1 below is unaffected and stands. Read
> §4 of this file together with `e20_result.md`.

**Headline: `taught_resident` is True on 39 of 42 asks (3 asks unattributable) — **0 of 19
failures are eviction**. H1 is falsified. Of the 9 attributed asks where the recall gate actually
ran, 4 have the correct taught row at probe rank 1–2 — and on 4 of those 9 the **gate's own**
retrieval ranks the row **first**, then refuses it at coverage 0.340–0.538. The row is resident and
findable by both cues; the failure is downstream of retrieval.**

> **Numbers corrected on recheck (see §8).** This headline originally read `40 of 42`, `8 attributed
> asks`, and `the gate's own nearest list is all book`. Recomputed from the journal the first two are
> 39 and 9, and the third is the claim E20 retracted — the gate surfaces the taught row at rank 1 on
> 4 of the 9.

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

## 3. The 9 attributed gate failures, ranked

These are the failing asks with `coverage_present=True` — the gate ran, so `nearest` and coverage
are real measurements. `gate rank` is added on recheck: where the taught row appears in the gate's
own `nearest` list, by exact string equality.

| ask | cov | probe rank | **gate rank** | window | taught row | count |
|---|---|---|---|---|---|---|
| `how often did i say the coat is wet?` | 0.454 | **1** | absent | 3 | `the coat is wet` | 3 |
| `what is bitten by the frost?` | 0.340 | **1** | **1** | 3 | `the frost bites the latch` | 1 |
| `what is held by the thing the frost bites?` | 0.510 | **2** | **1** | 3 | `the frost bites the latch` | 1 |
| `what number of eggs is left in the basket?` | 0.538 | **2** | **1** | 3 | `there are four eggs in the basket` | 1 |
| `how often does the bell turn?` | 0.514 | 11 | **1** | 3 | `the copper bell turns twice` | 1 |
| `how many times does the bell turn?` | 0.417 | 20 | absent | 3 | `the copper bell turns twice` | 1 |
| `what did i tell you about before the kettle?` | 0.555 | None | absent | 3 | `the lantern is lit` | 1 |
| `what came before the kettle in what i said?` | 0.460 | None | absent | 3 | `the lantern is lit` | 1 |
| `what does the bitten thing hold?` | 0.385 | None | absent | 3 | `the frost bites the latch` | 1 |

The last row was missing from the original table (it is a probe-tier ask, cov 0.385, cue
`[bitten, hold, thing]` against a row whose words are `frost bites latch` — population (c) below).

The only other ask that ran the gate is `where did i say the scarf is?` (cov 0.570,
`attribution_failed` — its `expect` carries no answer words). **It is not a failure: it passes**, and
it is the sole passing gate ask of the 10. Its `nearest[0]` is `the scarf is wet`, the taught row,
ranked first by the gate. The original text listed it among the gate *failures*, which is wrong.

Three distinct populations, not one:

**(a) Retrieved and still refused — 4 asks, probe rank 1–2.** As first written this population was
called "cue mismatch: gate `nearest` all book", and that is the claim E20 retracted. Measured by
exact string equality the gate surfaces the correct row **at rank 1 on 3 of the 4**
(`what is bitten by the frost?`, `what is held by the thing the frost bites?`,
`what number of eggs is left in the basket?`) and misses on 1 (`how often did i say the coat is
wet?`, the only count-3 row in the set). So the sharp result is not that the gate cannot find the
row — **it finds it, ranks it first, and refuses at coverage 0.340–0.538 anyway.** That is the
denominator, which E20 returned to and E12a/E14a had already closed at a 0.5488 ceiling. The one
genuine cue mismatch is the coat ask, and it is a single observation.

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

## 8. Recheck (later turn, read-only, no re-run)

The run was not repeated. Every number above was re-derived from the published journal
`state/selection/generation_19_asks.jsonl` (42 rows; each row carries `attribution` with
`taught_resident`, `taught_count`, `taught_rank`, `taught_row`, `taught_rank_cue`), so this checks
the write-up against the data it was written from, not the harness against itself.

**Confirmed, and it is the claim that carries the experiment:** `taught_resident=False` occurs on
**zero** asks, failing or passing. 0 of 19 failures are eviction. H1 stays falsified and §1's verdict
is unaffected by any correction below.

**Wrong, and now fixed in place:**

| claim | was | journal says |
|---|---|---|
| `taught_resident` True | 40 of 42 | **39 of 42** (18 failing + 21 passing; the other 3 are `attribution_failed`, `why=no_answer_words`) |
| attributed asks where the gate ran | 8 | **9** — `what does the bitten thing hold?` (cov 0.385, probe rank None, row `the frost bites the latch`) was omitted from §3 |
| scarf ask status | a gate failure | **passes**; it is the only passing gate ask of 10, and its `nearest[0]` is the taught row |
| gate `nearest` on population (a) | all book | **row at gate rank 1 on 3 of the 4** — this is E20's retraction, which §3's body had not yet absorbed |

Arithmetic that does check out: 19 failing / 23 passing; attribution_failed 1 failing + 2 passing = 3;
22 of 23 passing asks never run the gate (§2's control on the `window=0` misclassification); and the
§1 tally rows sum to 19 and 23 as printed.

**Consequence for §6.** §6 proposed probing the gate's cue for population (a) as the next step. That
step was taken and answered by E20 and E21a — the cue does not omit the taught terms, and de-framing
recovers 0 of 4 — so §6 is superseded, not open.
