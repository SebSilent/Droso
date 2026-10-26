# Cross-session memory: mechanism map and lever design

Written 2026-10-25, after the first complete mechanism read. Companion to
`benchmark_findings.md` (which covers the warm, same-session failures). This
document covers the boundary: what survives from one session into the next,
what the cross-session benchmark actually measures, and what the three
candidate levers would and would not change.

## What the benchmark measures

`tools/benchmark_cross_session.py` runs each script three ways and prints
`warm / cross / cold`:

- **warm** — the whole script (tells then asks) in one session, from
  `converse.py --scripts`. The baseline: memory used in the session it was
  learned.
- **cross** — two processes. A *tell* phase runs the script's tell turns in its
  own shadow and saves `language_state*` into its session dir. An *ask* phase
  then runs the script's ask turns in a second shadow built from the live
  state **plus the tell's saves overlaid** (`build_shadow`,
  benchmark_cross_session.py:120-175: hardlinks to every live state file, then
  the tell's saves copied on top). The ask is graded on the taught answers.
- **cold** — one fresh session, ask turns only, no tells
  (`converse.py --cold`, `run_cold`, converse.py:557-579). Graded on the
  **absence** of every word the warm script's expects would have taught
  (`told_words`, converse.py:541-554). A refusal passes. Cold high is correct:
  he must not assert facts about a conversation that never happened.

So the memory signal is **cross − cold**: cross should approach warm (the
teaching survives the boundary), cold should stay high (nothing leaks in
without teaching). The store guard (`_tree_snapshot` / `guard_check`,
converse.py:188-211: (size, mtime_ns) of every live state file, `sessions` and
`fitness` excluded) is checked in both phases; the benchmark's writes land
only in session dirs and `state/fitness/`.

## The mechanism map (verified, with line numbers)

The answer path for a question:

1. **Retrieval pool.** `binder.recall(cue)` scores every binder row by
   `sims + 0.05·overlap + 0.05·log1p(count)` and returns the top-k
   (higher_cortex.py:511). The count term is the one signal that separates
   what he *knows* from what he has *merely seen* — computed, stored, and used
   here.
2. **Answer ranking.** `answer()` re-ranks the pool with `informative()`
   (neural_language.py:2032-2036):
   `(overlap, fresh, expected[filler], idf[filler], not_in_cset)` descending.
   `fresh` is **binary** (neural_language.py:2023-2024): `1` if the row's
   `when >= self.session_t0` (line 73), else `0`. The comment above it states
   the design intent: at equal overlap, something the user said two turns ago
   outranks a corpus prior, and *when no session proposition is in the pool
   the term is a constant and the sort behaves exactly as before*.
3. **Unbind.** `role_of` (higher_cortex.py:523) unbinds the queried role from
   the winning proposition; for `where`-questions the filler is the last
   token, not the role index (neural_language.py:2012-2015).
4. **The recovered proposition IS the answer** (neural_language.py:2057-2065,
   source `"recalled proposition"`). The chain is not allowed to overrule a
   memory that was found — that overrule is how "who pets droso" once came
   back as "parent feeds droso".

State that moves across the boundary:

- **Binder** — 60000-row FIFO at capacity (higher_cortex.py:46). Every tell
  evicts the oldest rows to make room (the pilot's reference tell: added 3,
  removed 3 — two taught propositions plus one corpus echo). Eviction is
  `np.roll` + posting-list rebuild (higher_cortex.py:389-411).
- **SAN** — decays `0.995^dt` per second of wall clock, gated to 10 s steps
  (neural_language.py:374-377), row cap 1024 (line 371), TOP_K 512 (line 369).
  In the pilot's 55 s tell: 8145 rows changed, **zero new edges**, total
  weight 298 818 → 281 862 (−5.7 %): decay outpaced every write. nnz stayed
  66 107 030 — the taught pairs were already wired by the corpus.
- **Rehearsal** — happens only in sleep replay (neural_growth.py:346). A 55 s
  tell session never sleeps, so `rehearsed_n` is 0 in every tell delta. The
  benchmark therefore cannot see rehearsal at all.
- **Everything else** — vocabulary, bigram counts, persons, the proposition
  store, facts, procedures: unchanged by a tell (the pilot's delta shows
  `changed: false` on all of them). Teaching writes exactly two things: binder
  rows and SAN weight.

## What is actually measured so far

The pilot history is thinner than it looked:

| run | outcome |
|---|---|
| 21:39:32 | reference tell phase crashed (exit 1) |
| 21:42:02 | reference completed: warm 1.0, **cross 1.0**, cold 1.0 |
| 21:55:06 | relaunched under a numpy-less interpreter; seven error rows, exit 2 |

So **only reference has ever been measured cross-session**, and it passed:
the taught rows won on overlap + expected + idf outright, because nothing in
the corpus competes with "the kettle rings at noon". The scripts where the
corpus *does* compete (accumulation, discrimination — the warm findings'
failures) are exactly the ones the binary `fresh` term was built to fix, and
they are exactly the ones that have never been measured across the boundary.
The run started 22:11 fills them.

## The levers

### Lever a — graded freshness across the boundary

**Mechanism.** Replace the binary `fresh` (neural_language.py:2023-2024) with
a graded term restricted to testimony:

```python
who = str(h.get("who") or "")
age = self.session_t0 - float(h.get("when", 0.0) or 0.0)
fresh = (1.0 if age <= 0 else math.exp(-age / FRESH_TAU_S)) if who == "you" else 0.0
```

with `FRESH_TAU_S = 3600` s as the first cut. A proposition the *user* said
this session scores 1.0 exactly as today; one said an hour ago scores 0.37;
one said yesterday scores ~0; everything else — the corpus, his own speech,
parent narration — scores 0, exactly as the binary term scored it. The term
stays a constant when no recently-taught row is in the pool, so cold
behaviour is untouched — the existing comment's promise
(neural_language.py:2016-2022) is preserved verbatim.

**The who-restriction is required, not a refinement.** Graded freshness
alone is falsified by the first real cross measurement (accumulation,
22:14:54): "how is the box" passed, "where is the box" answered with the
ask's own first reply. The where-fix (filler = last token,
neural_language.py:2012-2015) landed after the findings doc was written, so
the echo row's filler is now "heavy", not "box" — the `not_in_cset` reorder
would not demote it. Three candidates tie on overlap, not_in_cset and
expected, and fresh decides:

| candidate for "where is the box" | filler | fresh (graded, no who) |
|---|---|---|
| ask's own reply to ask 1, bound seconds earlier ("droso says the box is heavy") | heavy | **1.0** |
| taught "the box is on the shelf" | shelf | ≈0.98 |
| 17:19 echo living in the live binder (the shadow hardlinks live state) | heavy | ≈0.0067 |

The ask's own echo is *always* fresher than the teaching in a cross ask, by
construction — the reply is bound seconds before the next ask, the teaching
minutes before the session ended. Grading alone makes the failure
*deterministic*, not occasional. The distinguishing signal is the binder's
`who` field (higher_cortex.py:376, returned by recall at :514): own speech
binds `who="droso"` (neural_language.py:878), user speech `who="you"`
(converse.py:247). Freshness is testimony recency: what he was *told*, not
what he *said*. Verified empirically (gate): the live binder's 60 000 meta
rows are book 59 515 / droso 466 / parent 19 / **you 0**; the cross shadow
session's binder is book 59 510 / droso 468 / parent 19 / **you 3** — the
three taught propositions, and nothing else, carries `who="you"`. The
restriction promotes exactly the taught rows and nothing else.

**Why it is the right lever.** In the cross ask, the taught rows are *in the
pool* (the ask traces show them retrieved) but lose the sort: their `fresh`
is 0, identical to every corpus row, so the tie is decided by
`expected[filler]` and `idf[filler]` — corpus statistics. Grading the term
restores the ordering the comment describes: something the user said *before
this session started* still outranks a corpus prior, decaying with age —
and outranks his own echo of an earlier answer, which graded-but-unrestricted
freshness would promote above the teaching.

**Predictions.**

- cross rises toward warm on the corpus-competing scripts; reference stays
  1.0 (it already wins outright).
- cold unchanged on every script: no `who="you"` rows exist in a cold
  session, the term is constant, the sort is byte-identical.
- warm unchanged or more robust: every row in a warm session's pool has
  `when >= session_t0` except corpus rows (0 exactly as today); where a warm
  ask previously decided between a taught row and his own echo by the idf
  accident (shelf outranks heavy), it now decides by fresh — taught 1.0
  beats echo 0 regardless of corpus statistics.
- The ask's `trace["ranked"]` shows the change directly: the taught rows'
  keys carry a fractional second term instead of 0, and the echo rows'
  keys carry 0.

**Risks.** A taught row from *last week* now scores ~0 — same as the corpus —
so very old teaching loses its edge. That is the intended trade (the corpus
*is* the record of old teaching, via the graded corpus). Parent narration
(19 rows) is not promoted; that is intended — being read to is not being
told. The tau is a guess; the benchmark's tell→ask gap is ~3 minutes, so tau
cannot be discriminated by the harness as it stands (any tau in 600–36 000 s
gives the same ordering). A `--delay N` option on the ask phase (sleep before
the session starts) would make tau measurable; proposed below.

### Lever b — durable rehearsed SAN rows

**Mechanism.** Rehearsed rows (replay count ≥ threshold) get a slower decay
exponent or a durable snapshot re-applied after decay, with a cap on the
durable set.

**Decision: dropped from this benchmark's scope.** Rehearsal only fires in
sleep replay (neural_growth.py:346); a benchmark session never sleeps, so
`rehearsed_n` is 0 in every tell delta and the lever is invisible to all
three columns. Making it visible would mean a sleep-replay hook between the
benchmark's phases — minutes of replay per suite run — for a lever that
addresses *weeks-scale* SAN decay, not the session boundary this benchmark
exists to measure. The boundary failure mechanism (echo rows outranking
teaching in the answer sort) is fully addressed by lever a; nothing in the
cross measurements implicates SAN decay. If weeks-scale retention ever
becomes the measured goal, the night-simulating run is the experiment to
build — a separate harness, not an extension of this one. Until then lever b
is parked, not scheduled.

**Risks.** SAN bloat: nnz is already 66 M; a durable subset needs its own cap
and a report line, or the decay that keeps the matrix inspectable stops
meaning anything.

### Lever c — teach-to-binder on session end

**Finding: this is already the behaviour.** The tell binds the taught
propositions (pilot tell delta: `added_n: 3`, sample includes both taught
sentences) and saves them; the ask loads them. The cross failure — where it
occurs — is a *ranking* failure, not a presence failure. The residual gap
lever c could address is that taught rows carry `count: 1` and no rehearsal,
so the pool score's count term (higher_cortex.py:511) gives them nothing.
But the pool is not the bottleneck: the taught rows are already retrieved.
Adding a count term to the answer sort would be a fourth change to a key
that already has five terms. **Drop lever c as a separate change**; the
count term already does its work where it belongs (the pool).

## Measurement plan

1. **Baseline (running now).** The 22:11 suite run fills the six unmeasured
   scripts. Every row must show `ok` (both guards) or the run is void.
2. **Lever a.** One-line change plus the constant; rerun the suite; compare
   per-script cross against this baseline. Acceptance: cross − cold opens on
   the corpus-competing scripts, warm and cold unchanged within noise, both
   guards `ok`, and the ask traces show the graded term in the ranked keys.
3. **Tau sweep (needs a harness addition).** `--delay N` on the ask phase,
   then N ∈ {60 s, 10 min, 1 h} to place the knee. Without this the tau is
   unfalsifiable by the harness.
4. **Lever b, separately.** A night-simulating run; not part of the
   cross-session acceptance.

## Open questions

- The 21:39 tell crash (exit 1) was never diagnosed — the 21:42 rerun
  succeeded, so it may have been transient (the api_oracle HTTPError fix
  landed between them). If it recurs, diagnose before touching anything.
- `session_context` has no warm/cold baseline yet; `ensure_baseline` will run
  it during the current suite (two extra converse runs). Its cold grade is
  the strictest: each ask must contain the new tell's words *and not* the
  other tell's — a blend fails both asks.
- The binder is at capacity: every teaching session evicts ~as many corpus
  rows as it adds. At 60000 rows and a few tells per day this is not a
  near-term risk, but the eviction is blind (FIFO, no rehearsal weighting) —
  a taught fact from last month is evicted before a corpus row read
  yesterday. Noted for lever b's follow-up, not for this boundary.