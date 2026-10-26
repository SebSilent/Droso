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

A turn is one user line through `lang.respond()`, the same door the house's
`/api/chat` uses. It hears the line (SAN `live()` update, cortex binding,
sequence learning), decides whether to speak, and answers from memory when the
words were a question. Between turns the organ gets a fixed number of
autonomous beats (`lang.tick`, `--beats 2` in the benchmark), so drives decay
and recover the way they do in the house and a thought of his own may land in
the log. Nothing is injected: no oracle, no curriculum narration, no task
path. The turn, not the sentence, is the unit scripts are written in
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
698.75): weight movement alone, which the trace rule counts as decay and
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

- **warm**: one persistent session. The script's tells land first, its final
  questions are asked at the end, expects graded on whole-word membership in
  what he said (`any_of` / `must_contain` / `must_not_contain`). A pass means
  the session context survived to the end of the script and was used.
- **cold**: a fresh session, only the final questions, graded on the
  **absence** of the words the warm session taught. If he says one of those
  words cold, training memory already held the fact and the warm pass is not
  evidence that session context was used. A refusal passes: the honest answer
  to a question about a conversation that never happened is not to assert one.

The headline is the warm-cold delta per script kind. Alongside it, the
connectome delta of one warm session: SAN rows/nnz/total weight, vocabulary,
bigrams, persons, propositions, facts, procedures, and the binder digest
(added / evicted / rehearsed). `left_a_trace` is true only if structure or
content moved; weight movement alone is not a trace. Live state files are
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
pass under a warm pass is still session use (he does not assert the taught
words cold: reference, switch_back, override); it just does not move the
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
evictions (6-9, one rehearsal in discrimination). Sessions leave a trace:
content moves (bigrams, binder in/out) and weight rehearses, but no new SAN
wiring, no new vocabulary, no new procedures in a 4-6 turn conversation.

## Findings

### Contradiction-probe nondeterminism

The override script teaches a fact, then contradicts it ("the kettle is
broken" ... "the kettle is fixed"), then asks. Which predicate wins the reply
varies run to run: `memory_won` / `session_fact_won` / `said_something_else` /
`silent` (`tools/converse.py:441-448`). The winner is recorded in the report
and printed by the orchestrator (`override winners (warm): ...`) but never
graded: which of two conflicting facts he answers with is a finding about
recency and decay, not a fault. Do not "stabilise" this; measure it.

### Binder at the 60,000 cap

The binder is at `MAX_PROPOSITIONS = 60000` (`organs/higher_cortex.py:46`) in
the live state, so every session add evicts the oldest row (FIFO `np.roll`,
`higher_cortex.py:388-404`). At capacity an add and an eviction cancel out:
the row count stays flat while the content changes completely. The first
snapshot read a nonexistent attribute and honestly reported 0 propositions;
the count alone also cannot see rehearsal, because the binder dedups by token
tuple: hearing the same sentence again bumps `count` and adds no row. The
binder digest (token tuple -> hear count, `tools/converse.py:300-315`) sees
all three: added, evicted, rehearsed. Consequence: `propositions 60000 ->
60000` in a report does not mean the binder was untouched; read the digest.

## The wrong-slot fix (2026-10-25, evening)

The warm-script failures diagnosed in `docs/benchmark_findings.md` got one
fix applied (the sort key plus the two terms the diagnosis pointed at), and
one separate bug was found on the way and is recorded here unfixed.

### What was applied (the "sfW" fix)

`answer()`'s informative sort (organs/neural_language.py:2032-2036) is now

    (overlap, fresh, expected, filler_idf, not_in_cset)

Three changes against the key that lost the benchmark:

- **where-filler is the last token** (neural_language.py:2012-2015). For a
  where-question the queried role index lands on a function word ("is" in
  a five-token sentence), so every where-answer competed on the idf of
  "is", a tie decided by nothing. The locative lives at the sentence's
  end ("the box is on the shelf"), so a where-question's filler is the
  last token. A narrow version of the findings' proposal #1: fixes the
  where-case without touching role votes.
- **session-fresh term** (neural_language.py:2071-2073, `session_t0` at
  :107). A proposition heard this session outranks a corpus-only one at
  equal overlap. Proposal #3 done as a graded sort term instead of a
  weight decay: `fresh` is 1.0 for a proposition the user spoke this
  session, decaying with age for older user speech, 0.0 for own speech
  and the corpus. The 2651-vote training prior can no longer beat
  something the user said two turns ago when the two overlap the question
  equally, but the term is graded, not tiered: a corpus row with
  strictly more overlap still wins, because `overlap` is the first key.
- **key order**: `(overlap, fresh, expected, filler_idf, …)`
  (neural_language.py:2081-2085). `expected` stays above `filler_idf`,
  and `fresh` sits above both but below `overlap`; that is what actually
  decided failure 2.

The property that makes this safe cold: when no session proposition is in
the pool, `fresh` is a constant and the sort behaves exactly as before
(comment at neural_language.py:2055-2058). Nothing that was not already in
the session changes its answer.

Not applied from the findings' list: #1 proper (role votes conditioned on
proposition length), #4 (mark self-rehearsal propositions at bind time),
#5 (trace metric). "droso says ..." echoes still compete as candidates;
only the sort changed.

### Found on the way, not fixed: the postings double-append

At the 60,000 cap the eviction branch (organs/higher_cortex.py:388-404)
calls `_rebuild_postings()` and then falls through to the shared append
loop (higher_cortex.py:429-432). The rebuild reconstructs every posting list
from `meta`, including the row just appended; the append loop then appends
the newest row's index AGAIN into `_postings` and `_stem_postings`. The most recent
row is therefore double-posted; the next bind's rebuild wipes it and
double-posts the new newest row, so exactly one row is ever wrong and the
corruption walks forward one row per bind.

Probe (`docs/evidence/debug_postings.py`, output `docs/evidence/debug_postings_out.txt`):
row 59999 ("where is the box", the newest) shows `raw postings x2, stem
postings x2` for every word of its key; every older row shows x1. Effect
measured through `recall()`: it walks posting lists without dedup
(higher_cortex.py:485-488), so the newest row's overlap doubles: the
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
the question's own object), a pre-existing gap newly measured, not a
regression. The connectome delta keeps the reference-session shape
(bigrams +14, binder 6 added / 6 evicted, everything else flat); the
nnz trace metric (findings #5) is still unapplied.

## The cross-session lever and the contamination-control set (2026-10-26)

### What was applied (the "floor" fix)

Two guards in `answer()`'s candidate pool (organs/neural_language.py),
shaped against the warm/cold benchmark and the cross-session harness:

- **freshness floor** (`freshness_key`, neural_language.py:51-65;
  `FRESH_FLOOR_S = 300` at :34): the sfW fix's graded term had a flaw
  within one conversation: every teaching is seconds old, and
  `exp(-age/tau)` separated them by thousandths, an ordering with no
  meaning in it, which is how the freshest-by-accident teaching won a
  question it could not answer. The floor ties all user-spoken
  propositions under 300 s at 1.0 so the answer-type term decides among
  them; decay bites only past the floor, i.e. across a session boundary,
  which is the only place the age is real information. The term stays a
  sort key, second after `overlap`: it is not a pool filter, the vote
  count is not in the key, and a corpus row with strictly more overlap
  still wins. What the floor fixes is ordering *among teachings*, not
  teaching-vs-corpus.
- **echo guard** (`_echoes`, neural_language.py:1935-1942): the
  question's own echo ("droso says ...") is excluded from candidates
  outright, not merely outranked: a hit whose token sequence appears
  contiguously in the question's stems is dropped before the sort.

Cold-safety property, same argument as the sfW fix: with no session
proposition in the pool every `fresh` is 0.0 and the sort behaves exactly
as before, so cold behaviour cannot move. The fix can only change
answers when something was actually said this session.

### The cross-session harness

`tools/benchmark_cross_session.py`: for each script, run the same script
three ways: **warm** (state as it is), **cold** (fresh agent, nothing
taught), and **cross** (teach script A's tells in session 1, ask script
B's questions in session 2). The number that matters is cross vs cold:
cross above cold means session memory is doing work that training memory
cannot; cross below cold means the memory is *hurting*: the failure the
baseline found.

Design points: every run is a separate `converse.py` process against the
live read-only state (hardlink, never written); each run records
`live_files_untouched` (mtime+size of the live state files before/after)
so contamination is per-run visible, not assumed; `--scripts` accepts any
scripts file, so the contamination-control set below runs through the
same harness unchanged; `--only`/`--phase`/`--name` allow single-cell
re-runs; the report carries the interpreter string, because of the
pitfall below.

### The interpreter pitfall

The harness and `script_benchmark.py` spawn `converse.py` with
`sys.executable`. Run under the PATH default (Python 3.12) every run dies
with `ModuleNotFoundError: numpy`: the venv-less 3.12 has no numpy, and
the failure surfaces only per-run, minutes in. The suite must run under
the 3.10 interpreter (`C:\Users\Silen\AppData\Local\Programs\Python\
Python310\python.exe`, numpy 2.2.6). `benchmark_cross_session.py` now
fails fast at startup if numpy is missing, instead of after the first
run.

### The baseline anomaly (pre-fix)

`state/fitness/cross_session_20261025_224101.json` (pre-fix, seen set):

    script          warm  cold  cross  cross-cold
    reference       1.00  1.00  1.00   +0.00
    accumulation    1.00  1.00  0.50   -0.50   <- memory hurts
    discrimination  1.00  1.00  0.50   -0.50   <- memory hurts
    role_chain      1.00  0.50  1.00   +0.50
    switch_back     1.00  1.00  1.00   +0.00
    override        1.00  1.00  1.00   +0.00

(session_context has no row here: it was added to `tools/scripts.json`
after this run.) Two scripts scored *below* their own cold baseline:
teaching the session made the answer worse. Diagnosis: the corpus prior
outvoted the session proposition in the candidate pool: exactly the case
the freshness floor targets.

### Results

Seen set, post-fix. The full warm/cold rerun
(`script_benchmark_20261026_012938.json`) matches the pre-fix rerun on
every shared script (warm 1.000, cold 0.929, the one cold miss still
role_chain's pre-existing corpus-fragment leak) and adds session_context
(warm 1.0, cold 1.0). The full cross suite
(`cross_session_20261026_014346.json`):

    script          warm  cold  cross  cross-cold
    reference       1.00  1.00  1.00   +0.00
    accumulation    1.00  1.00  1.00   +0.00   (was -0.50 pre-fix)
    discrimination  1.00  1.00  1.00   +0.00   (was -0.50 pre-fix)
    role_chain      1.00  0.50  1.00   +0.50
    switch_back     1.00  1.00  1.00   +0.00
    override        1.00  1.00  1.00   +0.00
    session_context 1.00  1.00  1.00   +0.00

The two memory-hurts cells are cured and nothing else moved: every
script now scores at or above its own cold baseline, all 14 runs report
`live_files_untouched=True`, and the role_chain cold miss is the
documented pre-existing gap (findings proposal #1), not a regression.

Contamination-control set (`tools/scripts_fresh.json`): same seven
kinds, same turn structure, same ask forms, every content word new
(owl/calls/dusk, candle/burns/night, coat/wet/torn/hook, forest/dark,
meadow/bright, fox/teaches/hare, hare/guards/fox, silver/spoon/smooth,
wooden/bowl/rough/light, tea/bitter/sour/green, brass/sounds/sunrise).
Vocabulary gate: `tools/check_script_words.py --scripts
tools/scripts_fresh.json`: all words owned, turn counts 4,5,4,4,5,5,4,
matching the seen set. The lever was shaped against the seen set; if the
fresh set shows the same cross-vs-cold lift, the lever generalises; if
the fresh set stays flat while the seen set jumps, the lever was
overfit.

### Fresh-set results

Warm/cold from the fallback baselines (`conversation_script_*_fresh_
{warm,cold}.json`), cross from `cross_session_20261026_013730.json`,
all under the 3.10 interpreter:

    script                  warm  cold  cross  cross-cold  live
    reference_fresh         1.00  1.00  1.00   +0.00       ok
    accumulation_fresh      1.00  0.00  1.00   +1.00       ok
    discrimination_fresh    1.00  1.00  1.00   +0.00       ok
    role_chain_fresh        1.00  1.00  1.00   +0.00       ok
    switch_back_fresh       1.00  1.00  1.00   +0.00       ok
    override_fresh          1.00  1.00  1.00   +0.00       ok
    session_context_fresh   1.00  1.00  1.00   +0.00       ok
    overall                 1.00  0.86  1.00

Six of seven: clean cold baseline, cross at ceiling. The lever does no
harm on corpus-novel content, and there is no lift to measure at a
ceiling that cold already reaches. The generalisation claim rests on the
seventh cell, which needs reading carefully.

**accumulation_fresh cold=0.00 is a flaw in the control set, not a
harder test.** The corpus already holds the taught fact: binder row
33878, `who="book"`, count 1, tokens "brown coat so that it is all torn"
(`state/language_state.json.cortex.meta.json`). Cold, with nothing
taught, that row wins recall for "how is the coat" (overlap 2,
overlap_idf 9.86, the trace in `docs/evidence/coldtrace.json`) and leaks "torn"
onto the must_not list. The vocabulary gate checked that the *words* are
owned; nothing checked that the *fact* is corpus-novel: the seen set's
clean cold baseline (its box rows contain none of heavy/red/shelf) was
luck, not design. Fix shape, not applied: a corpus-novelty gate next to
the vocabulary gate, scanning the binder meta for subject-word and
expect-word co-occurrence and failing the set before it runs.

The same cell's cross=1.00 is nonetheless the strongest evidence the
floor has produced: the session teaching ("the coat is torn") had to
outrank a corpus row that is nearly the teaching itself, and did. But
the +1.00 must not be read as memory-vs-no-memory: the cold baseline
here measures a corpus leak, not absent memory. The honest summary: on
corpus-novel content the lever is inert-safe (six cells), and on the one
cell where a corpus near-duplicate competed with the teaching, the
teaching won.

### Harness fallback fix, verified by execution

`ensure_baseline` (tools/benchmark_cross_session.py:212-231) ran its
cold fallback as `("cold", ["--cold"])`, but `--cold` takes the scripts
file as its value (tools/converse.py:592); the fallback could not
produce a cold baseline at all. It now passes `str(scripts_path)` and
reads the report per mode. Verified by the fresh-set run itself: the
cold reports carry the *fresh* scripts' turns (cold_ask "how is the
coat"), which only the fixed argument produces, and the fresh table's
cold column is populated end to end.

Probe note: the 02:04 cold probe (`build()` with no `project_root`)
reproduced the known `banc_brain.npz` no-op churn (debt entry 6): mtime
moved, arrays identical. No live-state contamination; the guard-window
gap remains open as logged.