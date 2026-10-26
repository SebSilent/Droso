---
layout: default
title: Speech-phase log
---

# Speech-phase log

Design decisions and findings from giving Droso a conversational harness
(`tools/converse.py`) and a script benchmark (`tools/script_benchmark.py`,
`tools/scripts.json`). Recorded, not fixed. All numbers from runs against the
live read-only state (11,555 words, 60,000 propositions, 66,107,030 SAN nnz).

## Design decisions

### Turn boundary

A turn is one user line through `lang.respond()` -- the same door the house's
`/api/chat` uses -- which hears it (SAN `live()` update, cortex binding,
sequence learning), decides whether to speak, and answers from memory when the
words were a question. Between turns the organ gets a fixed number of
autonomous beats (`lang.tick`, `--beats 2` in the benchmark), so drives decay
and recover the way they do in the house and a thought of his own may land in
the log. Nothing is injected: no oracle, no curriculum narration, no task
path. The turn -- not the sentence -- is the unit scripts are written in
(`tools/scripts.json`: 6 scripts, 4-6 turns each, later turns depend on
earlier ones).

### Decay

SAN decay is time-based, not per-turn: `SAN_DECAY_PER_S = 0.995` per second of
elapsed time, applied in one step over the whole elapsed interval when at
least `SAN_DECAY_INTERVAL_S = 10.0` seconds have passed since the last decay
(`organs/neural_language.py:23-24, 366-370, 781`). `SAN_DECAY = 0.999` is the
per-tick constant. Consequence for the harness: a conversation's turns are
seconds apart, so within-session decay is small; the measurable weight
movement in a session is rehearsal on existing wiring, not forgetting. In the
smoke runs, 8,145 SAN rows changed with `new_edges == 0` (max row delta
698.75) -- weight movement alone, which the trace rule counts as decay and
rehearsal, not new wiring.

### Reply gating

Whether he speaks at all is gated on weighted coverage
(`ANSWER_COVERAGE_FLOOR = 0.6`, `organs/neural_language.py:1766`). The
question's distinctive words are IDF-weighted (`log(1 + n_mem/df)`); the best
memory must account for at least 60% of that weight or he stays silent with
the reason ("the closest memory of his covers 56% of the question"). Guards
upstream of the gate: interrogative tokens never count as retrieved knowledge;
a memory that is a piece of the question itself is discarded (echoing the
asker's words reads as fluency and is worse than a refusal); words he has
never met are excluded from the must-set rather than treated as maximally
distinctive; if nothing in the question is known, he refuses. Silence is a
true report; a confident wrong answer is a lie he does not know he is telling.

### Benchmark design

Each script runs twice through the same harness, each run as its own process
so the connectome delta is one session's and nothing leaks between runs:

- **warm** -- one persistent session: the script's tells land first, its final
  questions are asked at the end, expects graded on whole-word membership in
  what he said (`any_of` / `must_contain` / `must_not_contain`). A pass means
  the session context survived to the end of the script and was used.
- **cold** -- a fresh session, only the final questions, graded on the
  **absence** of the words the warm session taught. If he says one of those
  words cold, training memory already held the fact and the warm pass is not
  evidence that session context was used. A refusal passes: the honest answer
  to a question about a conversation that never happened is not to assert one.

The headline is the warm-cold delta per script kind. Alongside it, the
connectome delta of one warm session: SAN rows/nnz/total weight, vocabulary,
bigrams, persons, propositions, facts, procedures, and the binder digest
(added / evicted / rehearsed). `left_a_trace` is true only if structure or
content moved -- weight movement alone is not a trace. Live state files are
size-and-mtime checked at exit; any change is a violation.

## Benchmark results (2026-10-25, house down, live state read-only)

Warm vs cold, per script kind (`state/fitness/script_benchmark_full_*.json`;
12 process runs, every run `live_files_untouched: true`):

```
script          kind          warm  cold  delta
reference       reference     1.00  1.00  +0.00
accumulation    accumulation  0.50  1.00  -0.50
discrimination  discrimination 0.50 1.00  -0.50
role_chain      role-chain    1.00  0.50  +0.50
switch_back     switch-back   1.00  1.00  +0.00
override        override      1.00  1.00  +0.00
overall                       0.83  0.92  -0.08
```

Reading: delta = warm - cold is "session added over training memory". A cold
pass under a warm pass is still session use -- he does not assert the taught
words cold (reference, switch_back, override) -- it just does not move the
delta. The three warm failures are wrong-slot answers, not silence:
accumulation "where is the box" -> "droso says the box is heavy" (taught fact,
wrong slot); discrimination "how is the garden" -> "the garden is calm" (wrong
predicate of the two taught); role_chain cold "who follows the sparrow" ->
"answered the sparrow as she flew away now" ("sparrow" is a must_not word and
training memory already surfaces it). Override winners this run: [hot, hot]
(memory won both asks).

Connectome delta, one warm session (reference, 4 turns): SAN rows changed
8,145 of 66,107,030 nnz, new edges 0 (nnz 66,107,030 -> 66,107,030), total
weight 298,817.75 -> 269,420.84 (-9.8%, max row delta 698.75); bigrams
268,985 -> 268,999 (+14); vocabulary 11,555 -> 11,555; persons 4 -> 4;
propositions 60,000 -> 60,000 (flat, at cap); facts 1 -> 1; procedures
688 -> 688 (0 gained); binder digest 6 added / 6 evicted / 0 rehearsed
(added: "the kettle rings at noon", "the lantern shines at midnight", "what
rings at noon", ...). left_a_trace: true.

Across all six warm sessions: new edges 0 everywhere; rows changed 8,145-
8,153; total weight -9.8% to -11.5%; bigrams +12 to +20; binder adds = 
evictions (6-9, one rehearsal in discrimination). Sessions leave a trace --
content moves (bigrams, binder in/out) and weight rehearses -- but no new SAN
wiring, no new vocabulary, no new procedures in a 4-6 turn conversation.

## Findings

### Contradiction-probe nondeterminism

The override script teaches a fact, then contradicts it ("the kettle is
broken" ... "the kettle is fixed"), then asks. Which predicate wins the reply
varies run to run: `memory_won` / `session_fact_won` / `said_something_else` /
`silent` (`tools/converse.py:441-448`). The winner is recorded in the report
and printed by the orchestrator (`override winners (warm): ...`) but never
graded -- which of two conflicting facts he answers with is a finding about
recency and decay, not a fault. Do not "stabilise" this; measure it.

### Binder at the 60,000 cap

The binder is at `MAX_PROPOSITIONS = 60000` (`organs/higher_cortex.py:46`) in
the live state, so every session add evicts the oldest row (FIFO `np.roll`,
`higher_cortex.py:388-404`). At capacity an add and an eviction cancel out:
the row count stays flat while the content changes completely. The first
snapshot read a nonexistent attribute and honestly reported 0 propositions;
the count alone also cannot see rehearsal, because the binder dedups by token
tuple -- hearing the same sentence again bumps `count` and adds no row. The
binder digest (token tuple -> hear count, `tools/converse.py:300-315`) sees
all three: added, evicted, rehearsed. Consequence: `propositions 60000 ->
60000` in a report does not mean the binder was untouched; read the digest.

## The wrong-slot fix (2026-10-25, evening)

The warm-script failures diagnosed in `docs/benchmark_findings.md` got one
fix applied -- the sort key plus the two terms the diagnosis pointed at --
and one separate bug was found on the way and is recorded here unfixed.

### What was applied (the "sfW" fix)

`answer()`'s informative sort (organs/neural_language.py:2032-2036) is now

    (overlap, fresh, expected, filler_idf, not_in_cset)

Three changes against the key that lost the benchmark:

- **where-filler is the last token** (neural_language.py:2012-2015). For a
  where-question the queried role index lands on a function word ("is" in
  a five-token sentence), so every where-answer competed on the idf of
  "is" -- a tie decided by nothing. The locative lives at the sentence's
  end ("the box is on the shelf"), so a where-question's filler is the
  last token. A narrow version of the findings' proposal #1: fixes the
  where-case without touching role votes.
- **session-fresh term** (neural_language.py:2023-2024, `session_t0` at
  :73). A proposition heard this session outranks a corpus-only one at
  equal overlap. Proposal #3 done as a sort term instead of a weight
  decay: the 2651-vote training prior can no longer beat something the
  user said two turns ago, because the prior is now compared only within
  the fresh tier (or within the not-fresh tier).
- **key order**: `expected` stays above `filler_idf`, but the fresh tier
  sits above both -- that is what actually decided failure 2.

The property that makes this safe cold: when no session proposition is in
the pool, `fresh` is a constant and the sort behaves exactly as before
(comment at neural_language.py:2020-2022). Nothing that was not already in
the session changes its answer.

Not applied from the findings' list: #1 proper (role votes conditioned on
proposition length), #4 (mark self-rehearsal propositions at bind time),
#5 (trace metric). "droso says ..." echoes still compete as candidates;
only the sort changed.

### Found on the way, not fixed: the postings double-append

At the 60,000 cap the eviction branch (organs/higher_cortex.py:388-404)
calls `_rebuild_postings()` -- which rebuilds every posting list from
`meta`, including the row just appended -- and then falls through to the
shared append loop (higher_cortex.py:429-432), which appends the newest
row's index AGAIN into `_postings` and `_stem_postings`. The most recent
row is therefore double-posted; the next bind's rebuild wipes it and
double-posts the new newest row, so exactly one row is ever wrong and the
corruption walks forward one row per bind.

Probe (`_tmp/debug_postings.py`, output `_tmp/debug_postings_out.txt`):
row 59999 ("where is the box", the newest) shows `raw postings x2, stem
postings x2` for every word of its key; every older row shows x1. Effect
measured through `recall()`: it walks posting lists without dedup
(higher_cortex.py:485-488), so the newest row's overlap doubles -- the
probe's recall shows `ov=4` for the newest row where the true overlap is
2 (`the` filtered as non-distinctive; is+box = 2, each counted twice).

Why the benchmark failures were not this: the newest row at question time
is the question's own echo, which the self-answer filter excludes from
candidates; the rows that actually competed were older and single-posted.
Still live in the tree. Fix shape is one guard: skip the fall-through
append when the rebuild path ran, or make the rebuild the only poster.

### Verification

Suite green on both sides of the edit batch: 365 passed / 3 skipped
(suite_before.txt, 19:01), then 364 passed / 3 skipped
(suite_after_deletion.txt, 19:23). The 19:01:34 batch touched
tests/test_connectome_house.py and four tool scripts
(verify_architecture.py, make_prose.py, seed_procedures.py,
triage_failures.py) in the same second and removed exactly one test;
which test could not be pinned from the pytest cache (it holds weeks of
accumulated rename history). Recorded as an open thread, not resolved.

Behavioural verification is the full six-script benchmark rerun against
the live state (`state/fitness/script_benchmark_20261025_193151.json`,
compared with the pre-fix `script_benchmark_full_20261025_172119.json`):

    script          pre-fix          post-fix
    reference       2/2, 2/2         2/2, 2/2
    accumulation    warm 1/2, cold 2/2   warm 2/2, cold 2/2   <- fixed
    discrimination  warm 1/2, cold 2/2   warm 2/2, cold 2/2   <- fixed
    role_chain      warm 2/2, cold 1/2   warm 2/2, cold 1/2   (unchanged)
    switch_back     2/2, 2/2         2/2, 2/2
    override        2/2, 2/2         2/2, 2/2
    overall         warm .833 cold .917   warm 1.0 cold .917

The two diagnosed failures now pass warm and cold, and nothing else moved:
role_chain/cold was already 1/2 before the fix ("who follows the sparrow"
-> the corpus fragment "answered the sparrow as she flew away now", whose
role-3 filler "as" passes the filler guard while the full reply contains
the question's own object) -- a pre-existing gap newly measured, not a
regression. The connectome delta keeps the reference-session shape
(bigrams +14, binder 6 added / 6 evicted, everything else flat); the
nnz trace metric (findings #5) is still unapplied.