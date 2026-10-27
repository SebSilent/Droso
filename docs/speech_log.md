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
matching the seen set. Corpus-novelty gate (added after the flaw below
was diagnosed): `tools/check_script_novelty.py --scripts
tools/scripts_fresh.json` -- see the flaw section for its findings.
The lever was shaped against the seen set; if the
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
seventh cell, which needs reading carefully. (Revised below by the
corpus-novelty gate: "clean" here means the cold run leaked nothing;
at the fact level five of the seven sets hold corpus near-duplicates,
so only role_chain_fresh and override_fresh are corpus-novel in the
strong sense.)

**accumulation_fresh cold=0.00 is a flaw in the control set, not a
harder test.** The corpus already holds the taught fact: binder row
33878, `who="book"`, count 1, tokens "brown coat so that it is all torn"
(`state/language_state.json.cortex.meta.json`). Cold, with nothing
taught, that row wins recall for "how is the coat" (overlap 2,
overlap_idf 9.86, the trace in `docs/evidence/coldtrace.json`) and leaks "torn"
onto the must_not list. The vocabulary gate checked that the *words* are
owned; nothing checked that the *fact* is corpus-novel: the seen set's
clean cold baseline (its box rows contain none of heavy/red/shelf) was
luck, not design. The corpus-novelty gate is now applied:
`tools/check_script_novelty.py --scripts <set>` scans the binder meta
for propositions sharing two or more content stems with a single
teaching and fails the set before it runs, with the offending rows on
the record. The logged fix shape said "subject-word and expect-word
co-occurrence"; that rule is unusable as written -- the vocabulary gate
guarantees every script word is owned, so single-word co-occurrence is
inevitable and the first cut flagged all seven scripts on stray words
(any "march hare" row hit role_chain_fresh). The working rule is
fact-level: one shared word is a word the corpus owns by design, two
shared content stems on one teaching is the taught fact sitting in the
corpus. On the fresh set the gate flags five of seven: reference_fresh
(4 rows, e.g. "there was a candle burning just outside" vs "the candle
burns at night"), accumulation_fresh (2, including row 33878 and
"tails of my coat were all soaking wet"), discrimination_fresh (2,
"the left side of the forest was dark"), switch_back_fresh (1,
"buonaparte was born with a silver spoon"), session_context_fresh (1,
"distant owl was all the sound"); role_chain_fresh and override_fresh
are clean. A hit is potential, not proven, contamination -- the row
must also win recall to leak, which the cold run measures -- so the
cold 1.00s on the flagged cells are luck to be re-examined, not
evidence of novelty. The set's fix (new content words for the flagged
teachings) remains a separate decision. On the seen set the gate flags
one script: role_chain, "the crows sailing overhead perhaps watched me
while" vs the teaching "the sparrow watches the crow" (crow+watch) --
the other six clean. That cell passed cold in practice, so the hit is
potential, not realized; but the earlier claim that the seen set's
clean cold baseline rests on box rows lacking heavy/red/shelf is now
only part of the story -- the crow-watch teaching has a corpus
neighbour too, and it simply never won recall.

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
reproduced the known `banc_brain.npz` no-op churn (debt entry 6 below):
mtime moved, arrays identical. No live-state contamination; the
guard-window gap remains open as logged below.

### The append-only logs are repo-root organ diagnostics (2026-10-26, the 04:00-04:10 window classified)

During the drift-check window three append-only logs moved:
`exocortex/evaluations.jsonl` (+8 rows, 04:04:00-04:05:37),
`state/knowledge_ledger.jsonl` (+3 rows, 04:04:26),
`exocortex/api_usage.json` (+5 rows, 04:03:55). Classified by reading
the writers, not by assumption:

- The writers resolve to the repo root by design, not to a session's
  `project_root`: `organs/evaluator.py:8` hardcodes
  `EXO = Path("C:/Projects/HybridLLM/exocortex")` and
  `organs/knowledge.py:80-81` takes `ROOT =
  Path(__file__).resolve().parents[1]`. Organ diagnostics are global
  properties of corpus+code, deliberately not per-session state.
- Harness runs cannot write them: `converse.build()`
  (tools/converse.py:143-171) stops the background organs (heartbeat,
  neural_growth, learning_loop, autotraining, exposure_thread), seals
  the learning loop read-only, and nulls the oracle key ("mode becomes
  blocked: refusals, never calls"). Both drift sides use it —
  serve.py:194 included — so the fresh suite (verified first-hand: 0
  evaluations rows in its 01:37-01:50 window) and the drift runs' own
  processes wrote nothing.
- The 04:03:55-04:05:37 entries came from one raw-build process with a
  live oracle: the api_usage burst contains ok:true calls (6+7, 2+4
  tokens), which a sealed process cannot make. Its rows are organ
  self-activity (learning-loop tasks "What is a monad?", procedure
  holes "surface area of a sphere"), not script or teaching content.
  Most likely a lost-window probe; the drift runs are exonerated.
- The agent's behavioural state was guarded throughout: the 04:02:42
  drift report says `live_files_untouched=True` (only the known
  banc_brain.npz no-op churn, content identical — debt entry 6 below).

Net: no contamination; the logs are diagnostics by design. One
residual: the guards snapshot `state/` only, so the two `exocortex/`
logs sit outside every guard window (the ledger, in `state/` root, is
inside) — a future bug that wrote memory content into them would go
unnoticed. Noted, not fixed.

## Debt log, folded in (2026-10-26)

`docs/debt_log.md` is folded here verbatim: dated entries for fixes and
tests that exist but are not fully verified, or observations that need a
future decision. Verification status is stated per item; nothing here is
claimed as proven that is not.

### 2026-10-25

#### 1. Binder postings double-append fix — fixed, regression-tested, mutation-verified

`organs/higher_cortex.py:404-411` (the `_postings` maintenance in
`Binder.remember`): a re-remember of an existing row appended its postings a
second time, so the inverted index double-counted rows and recall returned
duplicates weighted by re-tell count. Fixed by rebuilding the row's postings
in place. Regression tests added at `tests/test_binder_postings.py`
(double-append and idempotent re-remember).

Verification: mutation check run today — reverting the fix kills both
regression tests (2 failed), restoring it passes them (2 passed), and the
restored file is byte-identical to the working copy. The fix is real and
guarded.

#### 2. Observatory port-collision tests — present, suite green, arithmetic not fully reconstructible

Two tests exist at `tests/test_connectome_house.py:1006` (port takeover
detected) and `:1066` (bind refusal on a taken port). Current suite collects
**372 tests** and is green. At the point the Observatory tests were removed
from the working tree, the suite collected 367 (364 passed, 3 skipped —
`docs/evidence/suite_after_deletion.txt`), which is consistent with the tests being
part of the suite, but the exact batch arithmetic (365 → 367 → 372) cannot be
reconstructed without version control. What is verifiable stands: the tests
exist, cover both collision behaviours, and the suite is green with them in.

#### 3. api_oracle HTTPError-without-body fix — fixed, tested, mutation-verified

`organs/api_oracle.py:778-787`: an `HTTPError` with no body made the
`hasattr(e, "read")` guard crash with `KeyError` (the class's `__getattr__`
raises for unset attributes when `fp is None`), masking the real status
instead of reporting `reason="http_<code>"`. Fixed: the body read sits in
its own try/except, so the HTTP code survives an unreadable body.

Closed: `tests/test_api_organs.py:126-159` covers both shapes — a 429 with
an empty headers dict and a 500 with `fp=None` — asserting
`reason == "http_<code>"`, `text == ""` and the error counted. 62 passed on
both interpreters (3.10 and 3.12). Mutation-verified both ways on 3.10, the
interpreter where the trap exists: with the guard reverted both tests fail
with `KeyError: 'file'` from `tempfile.__getattr__`; restored, 62 pass. On
3.12 the trap does not exist (`hasattr(e, "read")` is True and `read()`
returns cleanly with `fp=None`), so the test passes either way there — the
docstring's "measured on this interpreter (3.10)" note is what keeps the
test honest.

#### 4. SAN global decay, now measured per-phase (observation, no action yet)

The cross-session smoke run
(`state/fitness/cross_session_20261025_214202.json`) is the first
instrument to record SAN totals per phase: tell phase moved total weight
298,817.75 → 281,861.625 (rows_changed 8145, nnz constant 66,107,030, new
edges 0); ask phase 281,861.625 → 268,988.062 (rows_changed 1818). Roughly
6% and 5% of total weight decayed per phase with **no rehearsal**
(`rehearsed_n=0` in both). This is the designed decay, not a bug — but
repeated sessions without rehearsal will erode old associations, and the
harness now makes that visible. Watch item: if cross-session battery runs
show monotone total-weight decline with no rehearsal counter-pressure,
rehearsal policy needs a look. Related finding from the same day: the sort
key's only cold-discriminating term (filler-idf) ranks narrative verbs and
is inert in warm; see `docs/evidence/role_chain_proposal.md` §2a and §4.3.

#### 5. Where-filler fix is state-dependent on question shape (resolved 2026-10-26 by the question-shape parser, see its entry)

The sfW fix's where-case (organs/neural_language.py:2012-2015) makes a
where-question's filler its **last token**, on the argument that the
locative lives at the answer's end. That argument holds for the script
shapes measured so far ("where is the box" / "where is the coat":
subject-final questions, locative-final answers). It does not hold for
questions where the subject is not the last token: "where is the box
kept" puts the filler on "kept", "where in the house is the box hidden"
on "hidden": the same tie-on-a-word problem the fix removed, in a
different guise, and a content verb can actively misrank. No current
script or ask form hits this (all where-asks in `tools/scripts.json` and
`tools/scripts_fresh.json` are subject-final), so nothing is broken
today; the risk is a future script that varies the where-question's
shape. If one is added, the filler rule needs a role-aware version
(findings proposal #1, role votes conditioned on proposition length)
rather than a positional shortcut.

#### 7. ensure_baseline's fallback was broken two ways (fixed 2026-10-26 ~01:31; in-flight fresh suite ran on the old code)

`tools/benchmark_cross_session.py` `ensure_baseline()` falls back to
running a script's warm/cold baselines when the newest full-suite
report has no row for it: exactly the fresh-set case, since
`tools/scripts_fresh.json` scripts never appear in a
`script_benchmark_*.json` report. Two bugs, the second masked by the
first:

1. The cold invocation passed `["--cold"]` with no value;
   `tools/converse.py` `--cold` takes the scripts path as its value,
   so argparse aborted every cold baseline with `error: argument
   --cold: expected one argument` (exit 2), `ensure_baseline` returned
   None, and the suite table lost its warm/cold/x-cold columns.
2. Had the cold run succeeded, the code read only the *cold* report
   (the loop's last `tag`) and returned its pass_rate as **both** the
   warm and the cold number; the warm column would have silently
   shown cold performance.

Fix: pass the scripts path to `--cold`, and read each mode's own
report for its own rate. Applied while the 2026-10-26 suites were in
flight; the running fresh-suite processes hold the old code, so their
report's warm/cold columns are empty by construction. The fresh warm
files exist (the fallback's warm leg ran fine); the fresh cold
baselines are being run separately after the suites land, and the
comparison table is assembled from the report files directly. The
seen-set suite is unaffected: its baselines come from the full
`script_benchmark_*.json` report, so the fallback never fires there.

Assembled, same day ~08:00: the fresh-set comparison table, from the
report files directly as promised above — warm/cold from
`conversation_script_*_fresh_{warm,cold}.json` (run 01:16-01:35 and
01:45-01:51), ask from `cross_session_20261026_013730.json` (01:37),
x-cold = ask − cold; assembler `tmp_fresh_table.py`.

    script                  warm  cold   ask  x-cold
    accumulation_fresh       1.0   0.0   1.0   +1.00
    discrimination_fresh     1.0   1.0   1.0   +0.00
    override_fresh           1.0   1.0   1.0   +0.00
    reference_fresh          1.0   1.0   1.0   +0.00
    role_chain_fresh         1.0   1.0   1.0   +0.00
    session_context_fresh    1.0   1.0   1.0   +0.00
    switch_back_fresh        1.0   1.0   1.0   +0.00
    overall                1.000 0.857 1.000   +0.14

Every fresh cross-session ask is at ceiling: the tell-taught state
transfers to a fresh ask session on all seven scripts, including
accumulation_fresh, whose cold baseline is 0.0 — the where-cell of
entry 5, which the question-shape parser later fixed (0/2 -> 1/2, its
entry's table). All components predate the parser (it landed 07:15,
commit 780c514): the table is the pre-parser cross-session state the
01:37 report was measured against, and the parser's post-parser
warm/cold numbers live in its own entry. The 013730 report's
`live_files_untouched` verdicts predate the guard-window change, so
they cover turns only; the wider build+turns window is entry 6a's,
verified separately.

#### 6. Live-file guard is blind to build-time writes; banc_brain.npz mtime churns every run (fixed, see 6a)

Both guard windows start **after** the agent is built:
`tools/converse.py` main() builds at :612 and snapshots at :618;
`tools/benchmark_cross_session.py` run_phase() builds at :76 and
snapshots at :79. Any write during `build()` is outside every guarded
window, so a per-run `live_files_untouched=True` verdict proves the
*turns* wrote nothing, not that the *run* wrote nothing.

Measured during the 2026-10-26 suites: the live
`state/banc_brain.npz` mtime moves in step with every run start
(01:15:23, 01:16:29, 01:18:29, one per run), while every other live
file (language_state.json, cortex npz, san npy, seq npz) kept its
pre-suite mtime. Array-level comparison of two snapshots taken across a
run boundary (`docs/evidence/cmp_banc.py`) shows **identical content**: the
write is a no-op rewrite (np.savez embeds zip member timestamps, so
mtime moves even when arrays do not). The growth organ's first
consolidation tick saves the brain unconditionally
(organs/neural_growth.py:361-363), which is the likely writer; the
60 s timer makes exact attribution inside a busy suite awkward, so the
trigger is probable, not pinned.

Net assessment: no live-state contamination (content verified
identical, all other files verified unmoved), but the guard's clean
verdicts are narrower than they read. Fix shape: take the guard
snapshot before `build()` in both places and treat the known no-op
banc_brain.npz churn explicitly (whitelist with a comment, or report it
as a named known-touch), so the verdict covers the whole run. Not
applied while the suites are in flight; the running processes hold the
old code regardless.

#### 6a. Debt entry 6 applied to the two remaining entry points (2026-10-26, design before implementation)

serve.py (:191, guard before build; :217-218, the churn named and
excluded) and drift_check.py (:181, guard before the first build;
:50-69, array-level content re-verification) already carry the fix
shape. The two main harness entry points do not: `tools/converse.py`
main() and `tools/benchmark_cross_session.py` run_phase() still
snapshot after build. Design, applied next:

1. **The snapshot moves before `build()`** in both entry points, so the
   verdict covers the whole run.
2. **The known churn is treated inside the guard, not at the call
   sites.** `_tree_snapshot` records a *content key* for the root-level
   `banc_brain.npz` — the zip central directory's per-member CRC-32s
   and sizes — instead of (size, mtime_ns). np.savez embeds zip member
   timestamps, so the file's mtime moves on every rewrite even when the
   arrays are identical; the CRCs are a pure function of the stored
   bytes (np.savez writes ZIP_STORED, so stored bytes are the raw array
   bytes), so they move only when content moves. A no-op rewrite then
   never flags; a content change always flags. This is stronger than
   serve.py's named-exclusion, which would tolerate a *content* change
   as a known touch; with the CRC key, serve.py's `known` list goes
   permanently empty and a real content change lands in `unexpected`.
   drift_check's independent array-level re-verification stays as the
   second, deeper check.
3. **The guard takes the state root as a parameter** (default: the live
   tree), so the wider window is unit-testable on a scratch tree; the
   existing tests' `converse.STATE` patching keeps working.
4. **The reports say what the verdict covers**: `guard_window:
   "build+turns"` and `guard_known_churn: ["banc_brain.npz"]` join
   `live_files_untouched` in both entry points' reports. Historical
   reports keep the old, narrower meaning; the field's semantics are
   dated by this entry.

Verification plan, before the change is called applied: (a) the guard
tests extended — a new file caught (already covered), banc_brain.npz
mtime churn with identical content NOT flagged, a content change
flagged; (b) the seen suite re-run warm and cold on the new guard —
14/14 and 14/14 unchanged, every report's `live_files_untouched` true
under the wider window, `guard_known_churn` naming the file; (c) the
numbers logged here and the work committed.

Measured, same day ~07:30-07:40: (a) `tests/test_guard_tree.py` now
collects 5 tests — the three original properties and the two new
content-key ones — all passing; the full suite is 398 passed, 3
skipped. (b) The seen suite re-run on the new guard, one process per
script per mode, 14 runs: 7/7 warm and 7/7 cold print `live state
files untouched (build+turns): yes`; every
`state/fitness/conversation_seen_guard2_*.json` report carries
`guard_window: "build+turns"`, `guard_known_churn: ["banc_brain.npz"]`,
`live_files_untouched: true`, and every pass_rate is 1.0 — matching the
previous suite's 14/14 warm + 14/14 cold. The live
`state/banc_brain.npz` mtime reads 07:37, inside the run window: the
churn fired on every build and the guard stayed clean because the CRC
key matched — the no-op rewrite is now tolerated by content, not by a
whitelist, and a content change would flag. Applied.

## The question-shape parser (2026-10-26, design before implementation)

The binder answers a question from the single best-scoring memory of a
recall ranked by shared words. That ranking cannot see sentence
structure, and the one failing benchmark cell is exactly that blindness:
role_chain cold, "who follows the sparrow", answered
"answered the sparrow as she flew away now" -- a corpus fragment that
shares the question's vocabulary and is not an answer to it. The
coverage floor passed it because every distinctive word of the question
was covered; nothing downstream asked whether the memory has the *shape*
of an answer. This entry is the design, written before any code moves.

### Mechanism

A parser sits between the informative sort and the best-match pick in
`NeuralLanguage.answer()` (organs/neural_language.py, after
`hits.sort(key=informative, reverse=True)`). It classifies the question
into one of three checkable shapes or abstains, then issues one of three
verdicts on the ranked pool. The "verb" is whatever stands after the
interrogative once function words are set aside -- no table of verbs, no
table of subjects, so the parser stays word-agnostic and works on words
it has never been told about.

**Three shapes.**

1. `subject_unknown` -- who/what + VERB + tail ("who follows the
   sparrow"). The filler is the first content word *before* the verb. A
   candidate answers it when the verb's stem is present, the tail's
   stems follow it in order, and at least one content word stands before
   the verb; that word is the filler.
2. `object_unknown` -- who/what + does/do/did + SUBJECT + VERB ("what
   does droso want"). The filler is the first content word *after* the
   verb. A candidate answers it when the subject's stem precedes the
   verb's stem and content follows the verb. Needed so a taught object
   fact ("droso wants food") is not vetoed by a misparse that reads the
   subject as the verb.
3. `locative_unknown` -- where + COPULA + subject ("where is the box").
   The filler is the last content word *after* the copula. A candidate
   answers it when the copula is present, the subject's stem precedes it
   (read right-to-left from the copula), and content follows; that
   content is the filler.

Matching is stem-based (`stem()` from organs/stemming.py: follows ->
follow, holding -> hold, watches -> watch), so inflection does not
defeat it.

**Abstain rules** (the parser returns None and the binder's answer
stands, unchanged):

- no interrogative in the question;
- the interrogative is how/why/when -- no checkable role;
- who/what followed immediately by a copula ("what is the box", "who is
  droso", "who is the one holding the light"): the question asks for the
  copula's complement, whose subject is not a role filler this parser
  can find without the kind of parse that turned retrieval into a
  liability before. The binder's own ranking answers these or refuses;
- no verb-like token after the function words, or the verb is the
  question's last token ("what is for dinner" reads "dinner" as its
  verb; "dinner" is the complement the question is about);
- where-questions with no copula, or no subject after it.

An abstention changes nothing by construction; the parser only ever
speaks about shapes it can check.

**Three verdicts** (`_arbitrate_shape`, over the pool in its existing
informative order, first match wins):

- *agree* -- the binder's own best match has the queried shape. No
  change; the two brains concurred.
- *override* -- the best match does not, but a lower one does: the
  ranking shared the words and missed the structure. The lower hit
  becomes the answer.
- *veto* -- nothing in the pool has the shape. The best match is a
  neighbour that shares vocabulary and not structure, and answering from
  it is the confabulation the coverage floor cannot see. He refuses:
  `{"answered": False, "spoken": False, "reason": "nothing he remembers
  has that shape", "cue": content, "parser": <verdict>}`. The verdict is
  also written to the turn trace as `trace["parser"]` either way, so
  every arbitration is on the record.

**Known limits, accepted:** a passive-voice answer ("the book was wrote
by him" to "who wrote the book") has the right structure in a voice the
parser cannot check and would be vetoed; and a preposition-less locative
("the box is downstairs") is refused with it. Both refusals are true
reports about the parser's own verification, not about the absence of an
answer; extending the matcher to the passive is future work, not silent
tolerance.

**Revision, same session:** the locative matcher first took any content
after the copula, which let a state ("the box is heavy") have the shape
of a place. The accumulation script is that limit made live: it teaches
"the box is heavy", "the box is red" and "the box is on the shelf", then
asks "where is the box" -- under the loose matcher a state memory ranked
first would be agreed with. The matcher now requires a preposition after
the copula, so a state no longer has the shape of a place and the
arbiter overrides to the shelf teaching if the ranking put a state
first. The cold cell it also fixes: "where is the coat" was answered
from "brown coat so that it is all torn", a state proposition, leaking
the taught word "torn"; the corpus holds no coat memory with a
preposition after its copula, so the veto now fires and he refuses.
The cost is the preposition-less locative above.

**Verification, executed.** Unit: 28 cases in `tmp_shape_unit.py`
(parser shapes, matcher fillers, all three verdicts) -- all ok. Corpus
probe (`tmp_coat_probe.py`): zero memories match
`locative_unknown(is, [coat])` with a preposition required, so the cold
"where is the coat" veto fires with no leak risk. Full fresh-set suite
(`tmp_run_suite.bat`, warm then cold, all seven scripts):

    script                  warm       cold (before -> after)
    reference_fresh         2/2        2/2 -> 2/2
    accumulation_fresh      2/2        0/2 -> 1/2   <- where-cell fixed
    discrimination_fresh    2/2        2/2 -> 2/2
    role_chain_fresh        2/2        2/2 -> 2/2
    switch_back_fresh       2/2        2/2 -> 2/2
    override_fresh          2/2        2/2 -> 2/2
    session_context_fresh   2/2        2/2 -> 2/2
    overall                 14/14      10/14 -> 13/14

Warm unchanged at 14/14 (no warm veto, no warm override needed). Cold
13/14: the remaining miss is "how is the coat", which the parser
abstains on by design (a how-question names no role it can check), so
the binder still answers from the corpus row that leaks "torn" -- the
control-set flaw documented above, unchanged by this lever. The fixed
where-cell is the veto working as designed: the corpus row about the
coat's state is not a location, and refusing it is a true report.

Seen set (`tools/scripts.json`, same suite shape, reports
`conversation_shapes_*.json` / `shapecs_*.json`, tables via
`tmp_summarize.py`; warm from `tmp_run_seen.bat`, the four cold cells
the killed job left blank from `tmp_run_seen2.bat`):

    script          warm       cold (before -> after)
    reference       2/2        2/2 -> 2/2
    accumulation    2/2        2/2 -> 2/2
    discrimination  2/2        2/2 -> 2/2
    role_chain      2/2        1/2 -> 2/2   <- the target cell fixed
    switch_back     2/2        2/2 -> 2/2
    override        2/2        2/2 -> 2/2
    session_context 2/2        2/2 -> 2/2
    overall         14/14      13/14 -> 14/14

The target cell, role_chain cold "who follows the sparrow", now passes
with `spoken: false, said: ""` -- the veto, not a lucky answer: the
corpus probe (`tmp_corpus_probe.py`, the exact matcher the veto uses,
over all 60,000 propositions) showed zero shape matches for these
asks, so silence is the arbiter's refusal, and the cold grader
passes it because it carries no taught word. The warm where-cell
("where is the box") answers from the shelf teaching. Both suites are
green: seen warm 14/14, seen cold 14/14, fresh warm 14/14, fresh cold
13/14, with the one fresh cold miss the documented control-set flaw.

### Why two brains beat one here

The binder and the parser fail in opposite directions, on the same pool.
The binder ranks by shared words and cannot refuse a fluent neighbour --
its coverage floor measures *how much* of the question a memory covers,
never *what role* the covered words play, so "answered the sparrow as
she flew away now" scores as well as "the crow follows the sparrow" when
both contain "sparrow". The parser knows the shape of an answer but
knows nothing about which memory is worth reading -- it cannot rank, and
run alone it would either answer from an arbitrary candidate or refuse
everything. Together the division is clean: the binder retrieves and
ranks the candidate pool (its recall, its coverage floor, its echo and
question filters all stay); the parser asks one question the binder
cannot ask -- does the best of these have the shape of an answer? -- and
its three verdicts are exactly the three things that can be true about
that pool. One brain answering alone is the measured failure; two brains
disagreeing is the veto, which is a refusal, which is a true report.

### Success criteria

1. role_chain cold pass rate 0.5 -> 1.0: the failing cell
   ("who follows the sparrow") is vetoed into silence, which the cold
   grader passes (cold grading is `must_not_contain` only; silence
   carries no taught word).
2. Warm suite unchanged at 14/14: every warm ask either abstains (all
   how-asks) or agrees (the traced who/what/where asks all have their
   teaching as the binder's best, which matches the shape). A warm veto
   or override would be a regression -- silence fails warm grading.
3. No other cold cell regresses: the 12 passing cells stay passing
   (silence passes cold), and no cold override may leak a taught word.
4. Live state untouched: read-only state, no writes outside
   `state/fitness/` reports.
5. The full warm+cold suite green, before/after table logged here, then
   commit and push.

### Measured (2026-10-26 09:38, post-parser, both suites green)

Baselines first so the cross harness's `ensure_baseline` picks up
same-era numbers: `script_benchmark_20261026_083729.json` (seen set,
warm then cold, all seven scripts). Then the cross suite:
`cross_session_20261026_093849.json` (tell -> shadow -> ask, seen set).
Every row used the post-parser baseline (measured_at 1793014649.4);
every tell and ask phase reports live untouched.

Before/after, per script (pre-parser reports: baselines
`script_benchmark_20261026_012938.json`, cross
`cross_session_20261026_014346.json`):

| script          | warm   | cold       | cross | x-cold     |
|-----------------|--------|------------|-------|------------|
| reference       | 2->2   | 2->2       | 1.0   | 1.0->1.0   |
| accumulation    | 2->2   | 2->2       | 1.0   | 1.0->1.0   |
| discrimination  | 2->2   | 2->2       | 1.0   | 1.0->1.0   |
| role_chain      | 2->2   | **1->2**   | 1.0   | **0.5->1.0** |
| switch_back     | 2->2   | 2->2       | 1.0   | 1.0->1.0   |
| override        | 2->2   | 2->2       | 1.0   | 1.0->1.0   |
| session_context | 2->2   | 2->2       | 1.0   | 1.0->1.0   |

The parser's whole-suite delta is one cell, twice over: role_chain cold
1->2 in the baselines and role_chain x-cold 0.5->1.0 in the cross suite
-- the same failing question ("who follows the sparrow"), cured in both
harnesses by the subject-unknown veto. No other cell moved. Warm 14/14
and cold 14/14 overall; cross overall 1.000/1.000/1.000.

Environment note for future runs: a background measurement job does not
survive a turn boundary -- the first cross-suite attempt died with the
orchestrator on the last script and its in-memory results were lost (no
report written; the per-phase session dirs remained). Re-ran in one
turn, background job polled to completion. A foreground run cannot beat
the 600s shell cap, so background-plus-polling within one turn is the
only reliable shape for a full suite.

## Sessions hand over deltas, the SAN compresses 50x (2026-10-26, logged
## after the code landed -- the working session that wrote it ended
## before its entry did; this backfill is the record, not a pre-design)

Two storage facts forced the change. First, every session boundary
copied the full state family -- eight files, ~380 MB -- into the shadow,
so a fourteen-phase suite wrote ~5 GB and the 450 GB of accumulated
`state/sessions` was that number multiplied by months of runs. Second,
the SAN matrix was stored dense: 268.4 MB on disk for a matrix whose
useful content is its non-zeros.

### What changed (commit 2d85f26)

1. **The SAN is stored as a compressed npz** (`language_state.san.npz`):
   same keys, same load path, 268.4 MB -> 4.9 MB on disk (98% smaller).
   The dense `.npy` remains readable; the merge tool accepts both
   formats so old lineage copies still load.
2. **A session boundary serialises what the cortex heard, not the
   matrix it moved.** The tell phase saves with `delta=True`: the full
   json (vocabulary, bigrams, persons -- the cheap, must-not-lose
   parts) plus a delta file listing the utterances heard this session.
   The ask phase's shadow boots from the live files and replays the
   delta through `hear()`. Exact by construction, because
   `ConceptSpace.of` is a fixed hash: the same words produce the same
   vectors, so replaying the utterances reproduces the learning without
   shipping it.
3. **The delta has a cap** (3 utterances in the roundtrip test's
   config): past it the save refuses the delta and demands a full save,
   so a long session cannot silently grow an unbounded replay file.
4. **`tools/test_delta_roundtrip.py`** proves both levels: the organ
   alone (delta 658 bytes, 7 items applied, recall crosses the
   boundary, past-cap refusal honest) and the house path (delta 744
   bytes, `cortex.npz` not written by a delta save, stored-vector
   counts identical after boot).

### Runtime state left git (commit 2b5e344)

The brain (`state/language_state*`), the house logs, and the
exocortex's own memory (`exocortex/*`) were tracked files -- every
commit snapshotted a multi-MB brain. They are untracked now, ignored,
and on disk only. History still holds the old blobs (`.git` 444 MB);
rewriting it is destructive and was not done.

### The suite re-run under the new regime (2026-10-26 18:53)

`cross_session_20261026_185308.json`, seen set, post-parser baselines,
one full tell->shadow->ask pass per script. Every shadow received
`overlay_files: 2` (json + delta) instead of the old 8-file full copy;
every tell and ask save reports `save_ok: true`; every session dir was
pruned on report write (58.4 MB reclaimed); live state untouched on all
14 phases.

| script          | warm | cold | cross | tell_ok | ask_ok | pruned |
|-----------------|------|------|-------|---------|--------|--------|
| reference       | 1.0  | 1.0  | 1.0   | yes     | yes    | yes    |
| accumulation    | 1.0  | 1.0  | 1.0   | yes     | yes    | yes    |
| discrimination  | 1.0  | 1.0  | 1.0   | yes     | yes    | yes    |
| role_chain      | 1.0  | 1.0  | 1.0   | yes     | yes    | yes    |
| switch_back     | 1.0  | 1.0  | 1.0   | yes     | yes    | yes    |
| override        | 1.0  | 1.0  | 1.0   | yes     | yes    | yes    |
| session_context | 1.0  | 1.0  | 1.0   | yes     | yes    | yes    |

Identical to the pre-delta numbers on every cell: the delta handover is
behaviour-preserving as designed. The delta-diff fields now in each row
record what one session actually moved (reference tell: 8 bigrams, 3
binder propositions added/3 removed, 8145 SAN rows touched with
`new_edges: 0` -- decay, not growth).

## 2026-10-26 — storage, closed for good

The delta handover (previous entry) fixed the benchmark's own writes.
Everything else that saves still writes full state trees, nothing
deletes them, and every save failure is printed and swallowed -- which
is how a full disk manufactured two fake 0.0 regressions on 2026-10-26
10:07. This entry closes all three holes.

### The writers of bytes (measured 2026-10-26, before this entry)

- `state/language_state*` 383.4 MB -- the live brain. Legitimate; this
  is the organ. Full saves on throttle, delta saves at boundaries.
- `state/lineage/live_2026-10-26` 389.3 MB -- a population.py lineage
  copy of the live brain made the same day. Pure duplication; deleted.
- `state/reader/state/*` 391.1 MB -- the reader's own brain, but its
  SAN predates the compressed-npz change: 237.8 MB dense where the
  live brain stores 4.9 MB. One-off conversion to the compressed
  format; future reader saves are compressed already.
- `state/sessions/*` -- every harness's session copies. converse.py,
  serve.py and drift_check.py still save full trees (the delta change
  only reached benchmark_cross_session.py). Probes and one-offs write
  here too and nothing ever swept them.
- `state/fitness/*` -- reports, kilobytes. Keep.
- `.git` 444 MB -- history blobs from when the brain was tracked.
  Left alone; rewriting history is destructive and was declined.

### Design

1. **One shared module, `tools/state_hygiene.py`.** Three things:
   `require_saved(res, what)` -- raises SystemExit on a failed save,
   the one place that makes a save failure fatal; `save_session_state`
   -- `save_state(delta=True)` plus require_saved, the one save path
   for session copies (save_state already falls back to a full save
   when the delta refuses, so only real I/O failures reach the check);
   `prune_sessions(keep)` -- retention sweep over `state/sessions` and
   `state/lineage`: group by kind (the directory name minus its
   trailing timestamp), keep the newest N per kind, delete older,
   report real bytes freed (hardlink trees count once).
2. **Every writer converted.** converse.py's end-of-run save and its
   interactive `:save` go through the delta path; a failed end-of-run
   save exits nonzero. serve.py's shutdown save and drift_check.py's
   save likewise. benchmark_cross_session.py's run_phase replaces
   print-and-continue with require_saved (the phase process dies
   nonzero, the orchestrator already marks the row errored), and
   run_suite returns 1 if any row errored -- a suite that scored
   against half-saved sessions can no longer exit 0. script_benchmark
   inherits fatality through converse's exit code.
3. **Retention on report-write.** Every report-writing site (converse,
   script_benchmark, the cross suite, serve, drift_check) calls
   prune_sessions after writing: keep the last 3 session dirs per
   kind, the last 2 lineage copies, delete older. Probes and one-offs
   are swept by the same stroke.
4. **Proof.** Footprint before, one full cross-suite run, footprint
   after. The bound to hold: live state + small deltas, no new
   hundred-MB directories.

## 2026-10-26 — storage, proof run and two corrections

### Corrections to the entry above

1. **The reader's SAN is not a format problem.** The writers-of-bytes
   list said its 237.8 MB SAN "predates the compressed-npz change"
   and planned a one-off conversion. Wrong twice over. The file was
   already a compressed npz -- recompressing it reproduced the bytes
   bit-identically at the same size. The size is the information: the
   matrix is ~97% dense with real weights (median |v| 0.14, ~198k
   unique values in a sampled block), while the live SAN's nonzeros
   are 97.7% the denormal 1.4e-44 -- decayed-to-dust weights that
   zlib crushes. The live brain's 4.9 MB is an artifact of decay, not
   a superior format. Nothing to reclaim without altering weights;
   the reader's values were left untouched.
2. **The 404.90 GiB sessions backlog was already gone before this
   work began.** The harness's own pruning during the 18:53 green run
   had emptied `state/sessions`; the disk crisis was over (C: had
   183.55 GB free) before the first line of this entry's code was
   written. What this entry closes is the cause -- writers that save
   full trees, save failures that print and continue, nothing that
   sweeps -- not a lingering effect.

### Proof (2026-10-26 20:06, `cross_session_20261026_200621.json`)

Full pytest suite first: 407 passed, 3 skipped, including the nine
new `tests/test_state_hygiene.py` tests. Then the cross suite, 465 s,
exit 0:

- all seven scripts ask pass_rate 1.0 (2/2 asked, 2/2 passed),
  baselines warm/cold 1.0;
- `tell_save_ok` and `ask_save_ok` true on every row -- the fatal-save
  path never fired because nothing failed, and a failure now would
  kill the phase instead of printing;
- live files untouched on all 14 phases;
- `session_pruned` true on every row -- the retention sweep ran after
  the report and deleted the previous run's directories.

### What a suite run costs now

`state/sessions` after the run holds one tell dir (4.2 MB of deltas),
one ask dir (0.0 MB) and one shadow (756.5 MB apparent, 0.0 MB real:
every file is a hardlink into the live tree -- `fsutil hardlink list`
shows 2 links on the shadow's cortex npz -- and the only new bytes are
the overlay deltas). The footprint scanner counts apparent bytes and
double-counts hardlinks; the real cost of a full suite run is about
5 MB. C: free after: 188.48 GB, up from 183.55 before the run -- the
sweep freed more than the run wrote.

### Committed

Three commits, pushed: the hygiene module with its tests; the five
writer conversions (converse, serve, drift_check,
benchmark_cross_session, script_benchmark); this entry.

## 2026-10-26 (late) — task 3, swing 2: the storage floor goes float16

The state floor is 815.6 MB of float32 npz: the live cortex 350.4 MB,
the reader cortex 153.4 MB, the reader SAN 237.8 MB, the live SAN
4.9 MB, two seq files 17.4 MB. Every one of those matrices is a
perception record, not a learning surface: X and C are bound role-filler
vectors and their cues, the SAN matrices are Hebbian co-activation
accumulated from reading. Their precision is inherited from numpy's
default, not chosen. Float16 carries a 4.88e-4 relative rounding step;
the question is only whether anything downstream can feel that.

### The bit-exact alternative died first

The stronger design -- drop C entirely and recompute it from meta at
load -- was checked before this one and is dead. `cue_of` folds the
IDF weights *as they were at write time* (`_idf` is computed over the
meta that existed when the row was remembered; the corpus was ingested
incrementally, so every row's cue was built under a different global
IDF table). C is normalized, so the norm is lost, and projecting
`of(t) . C_i` recovers each weight only to within a few percent of
cross-talk from the near-orthogonal concept vectors. The weights are
not recoverable; recomputing under the final IDF would change cue
directions. That is a behavioral change, not a storage move. Rejected.

### Pre-flight measurement (tools/_swing3_probe_f16.py, read-only)

Round the real files to float16 and back (store f16, load f32 -- the
exact trip the new format puts every vector through), then measure the
damage where it would land:

- **C, through the real `recall()` ranking**: 300 cues drawn from real
  meta rows. Top-1 flips **0**, top-5 set flips **0**. Raw max
  |dsims| 2.8e-4. The top-2 sims gap the flips would have to beat:
  median 3.9e-1, p1 3.4e-2, min 2.3e-4 -- three orders of margin at the
  median, and the 0.05*overlap and 0.05*log1p(counts) terms only widen
  it.
- **X, through the real `unbind` algebra**: 240 (row, role) unbinds
  scored against the FULL 16,930-word candidate matrix. Answer flips
  **0**. Max |dscore| 3.1e-5; closest top-2 gap 1.6e-1 -- four orders
  of margin.
- **SAN, through both `_spread()` forms** (dense gemv, row-subset
  gemv): reader matrix 65.0M real weights (0.14-4.0), **zero entries
  flush to zero**, relative output delta 4.3e-4 / 5.8e-4 -- float16's
  own precision, no worse. Live matrix: 66.1M stored nonzeros of which
  **65.5M are denormal dust** (~1e-36, thirty-five orders below the
  real 610k weights) and flush to zero under float16 -- which is not
  damage, it is the dust finally being free.

Zero behavioral flips everywhere, error at float16's own relative
precision, decision margins three to four orders above the noise. The
swing ships on measurement, not hope.

### The design

Stored float16, resident float32. The save sites downcast; the load
sites already upcast (`np.asarray(..., dtype=np.float32)` in all three
loaders -- higher_cortex, neural_language, population -- so the loaders
do not change). Arithmetic stays float32: every gemv, unbind and
accumulate runs on upcast arrays exactly as today. Quantization is
confined to the save/load boundary, once per process lifetime, and its
bound is the probe's number. P (the predictor's learning surface) and
the seq files stay float32/int32: P's win is ~1 MB and it is the one
matrix whose small deltas are the point. The merge writer converts too
-- one format everywhere, so a merge cannot reintroduce float32 rows.

Predicted floor: live cortex 350.4 -> ~187 MB, reader cortex 153.4 ->
~83 MB, reader SAN 237.8 -> ~107 MB, live SAN 4.9 -> ~2.5 MB.

## 2026-10-26 (late) — swing 2 landed, cut in half by its own probe
## (backfilled after the code and validation; the session that did the
## work ended before its entry did)

The entry above shipped a design with four f16 halves. Two survived
contact with a behavior probe; two are dead, and the probe that killed
them is the most instructive result of the swing.

### What shipped: cortex X/C float16, nothing else

`tmp_f16_convert_cortex.py` converted exactly two files, after
verifying each byte-identical to a preserved float32 backup
(`state/backup_f16/...`, full relative path layout -- the reader's
backup lives at `state/backup_f16/reader/state/`, not directly under
`reader/`), converting in place via temp+rename, and skipping
already-converted trees on re-run:

- live `state/language_state.json.cortex.npz`: 350.4 -> 222.7 MB
  (36.4% smaller), max |dX| 6.104e-05, max |dC| 5.437e-05;
- reader `state/reader/state/language_state.json.cortex.npz`:
  153.4 -> 98.5 MB (35.8% smaller), max |dX| 6.099e-05,
  max |dC| 3.052e-05.

182.6 MB reclaimed. Every delta is one float16 rounding step. P, the
counts, and the seq files were never touched. The save path
(`higher_cortex.py` writes X/C as f16 with `fmt=["f16-1"]`) and the
load path (upcast to float32) already agreed with the format, so the
files and the code now say the same thing.

### What died: the SAN halves, killed by the mask amplifier

The pre-flight measured the SAN through `_spread()` and saw only
float16's own relative precision (4.3e-4 / 5.8e-4) -- and called that
harmless. It was measuring the wrong surface. The behavioral probe
(`tmp_san_mask_probe.py`) asked what f16 does to `similarity()`, the
SAN-only path the house actually speaks through:

- 'only' and 'of' moved 0.676 -> 0.000 against their f32 selves;
  23 of 100 tested pairs moved more than 1e-3.
- Pinning 'only' to its f32 mask collapsed the delta to exactly
  0.000e+00. The 25% mask is the amplifier and the dust is its input:
  understand() keeps each word's top quartile of SAN rows and
  renormalizes, so a word whose real wiring has fully decayed keeps
  its meaning only through the shape of its renormalized dust.
- The live SAN's nonzeros are 99.1% sub-1e-6 (65.5M of 66.1M are
  denormal ~1e-36). Float16 flushes all of it to zero. That is not
  decay completion; it is erasing the only signal some words have
  left.

So the dust is load-bearing, the "dust-clear" variant dies with it
(it zeroes the same entries), and both SANs stay float32 untouched.
The reader SAN needs no decision: it has zero entries below 1e-6 --
237.8 MB of real, diverse weights zlib cannot crush -- so f16 there
was worthless even before the behavioral verdict. (The earlier
"reader SAN f16 -> 121.6 MB" figure was never squared with the
density census and is not cited; moot, since nothing happens to that
file.)

One operational lesson fell out of the reader SAN: a one-off
recompression of a live individual's state file does not stick while
its writer process runs. The verified 4.9 MB reader SAN was back at
237.8 MB by the next measurement -- the running reader re-saved its
own in-memory matrix. Storage moves are only durable behind a writer
conversion plus a process restart.

### The merge writer, corrected

The entry above said "the merge writer converts too -- one format
everywhere". Superseded for the SAN: `tools/population.py` writes
merged SANs as float32 and upcasts any float16 source on the way in
(there is a brief f16 window in the lineage to absorb). The cortex
needs no conversion in the merge at all -- it is taken whole from one
individual via a byte-for-byte copy, so an f16 cortex source stays
f16 and an f32 source stays f32.

### Validation

`tmp_f16_ab.py` boots two private trees -- one from the float32
backups, one from the converted live files -- through the real load
path, runs a seeded battery (150 recall cues from real meta rows,
100 similarity pairs), and compares keyed by row identity with the
trees verified unwritten and the in-memory state drift-checked:

- SAN: bit-exact. 100 pairs, max |ds| 0.000e+00.
- Recall: 150 cues, 749 top-5 rows matched, max |dsim| 2.000e-04 --
  one f16 rounding step. One top-5 set flip out of 150 cues, and the
  flip is a proven tie-break: the f32 score gap between the two
  swapped rows is 9.690e-05, under the 2.0e-04 perturbation ceiling.
  The cue was ['devoid','every','me','of','proper','then','thought',
  'you']; the outgoing row ('you','are','calm') sits at sim 0.066
  held up by its count (11624) and the incoming
  ('hieroglyphics','then','that','is','the','proper','word','to') at
  0.449 -- both near-noise retrievals at the rank-5 boundary, and the
  f16 ordering is arguably the better one.
- No checksum drift, no file writes on either side.

The harness's gate was made honest rather than relaxed: a set flip is
fatal only if the f32 score spread across the swapped rows exceeds
1e-3 (measured from the f32 side's own ranking fields, score = sim +
0.05*overlap + 0.05*log1p(count)); a spread inside the tolerance is a
numerical tie the perturbation may reorder. The battery recalls k=10
so the rank-6+ rows are visible on the f32 side for that measurement.

Full pytest after the reverts: 407 passed, 3 skipped. The restart
test's original 1e-6 tolerance was restored (not relaxed) and passes
bit-exact -- it measures SAN-only similarity, which the f32 SAN makes
exact again.

### The floor, measured

Live cortex 222.7 MB + live SAN 4.9 MB + seq 14.5 MB; reader cortex
98.5 MB + reader SAN 237.8 MB + seq 14.5 MB. Total ~593 MB against
the 815.6 MB the swing started from. The predicted ~187/~83/~107 MB
figures were optimistic -- zlib does not compress f16 as well as f32
dust -- and the predicted SAN wins do not exist. The measured numbers
above are the floor; the remaining 237.8 MB is information, not
waste.

### The suite, green (2026-10-26 22:31, `script_benchmark_20261026_223112.json`)

The seven-script suite ran to exit 0 in 472.6 s under the final state
(f16 cortex on disk, f32 SAN, f32 resident): every script warm 1.00 /
cold 1.00, delta +0.00 across the board, no FAIL lines, override
winners ['hot', 'hot'] -- deterministic, and reported rather than
graded. Identical to the pre-swing numbers on every cell.

One operational note, because it cost a re-run: the first launch of
this suite was killed mid-run when the session driving it was
interrupted -- the background job registry did not survive, only the
first script's two reports landed, and the job's stdout died with it.
The re-run redirected stdout to
`state/fitness/script_benchmark_out.txt`, which is the only reason
this table exists. Background jobs here are not durable; anything
whose result matters writes to a file.

## 2026-10-26 (late) — the SAN decays through the 1e-6 line (backfilled;
## the watch turn ended before its entry did)

### The watch (tmp_san_watch.py, read-only)

One data point against the live `state/language_state.san.npz`, archive
key `san` (not `weight` -- the first run KeyError'd on the guess):

- nnz 66,107,030 -- stable against the 66.1M baseline; nothing is deleted.
- dust (< 1e-6): 65,533,606; real (>= 1e-6): 573,424 -- down ~6% from the
  ~610k real weights at the swing probe, and dust grew by the same ~37k.
- dust max 9.949e-07 -- sitting just under the threshold line.

Mechanism, from those three numbers: weights decay THROUGH the 1e-6
line, migrating real -> dust at constant nnz.  The decay does not
delete; it demotes.  Real mass: median 2.448e-02, max 4.0, entries
>= 1e-1: 250,266.  The reader SAN is stable and has zero dust (nnz
65,047,556, median 1.403e-01, max 4.0) -- the decay is a live-brain
process.

### Candidate capability item: a consolidation organ

The live SAN's real wiring erodes monotonically between sessions.  The
candidate item is a consolidation organ -- a sleep phase that replays
high-value propositions and re-strengthens their SAN wiring before it
crosses the 1e-6 line.  This is the AGI-relevant shape, not hygiene:
consolidation is what sleep does, and without it long-term wiring
decays to dust that only carries footprint.  Open questions: the rate
(one data point -- constant, accelerating, or bounded is unknown), and
no alarm threshold is set.  The watch script exists and is read-only;
the next data point is one run away.

## 2026-10-26 (late) — writer path settled by measurement; the guard
## watches exocortex; the exit-save fatality is proven by execution

### The writer-path question: sessions never reach the oracle/evaluator

Three independent gates close every path from a session turn to the
exocortex writers:

- `render_voice` returns early unless `self.voice_prosthesis` is on
  (organs/neural_language.py:3003) -- off by default, "because it
  spends the operator's API calls".
- `learn_from_teacher` is invoked only by the house's first-run
  acquisition, never in a session turn.
- the evaluator is not in the turn path at all.

Empirical check: one real turn ("hello droso") left all nine
exocortex files byte-identical (SHA-256 before/after).  The oracle is
wired onto the organ (`set_oracle` at agent init) but never called in
a session turn.

The house, by contrast, rewrites seven exocortex files in bursts
(measured bursts at 21:58:59, 22:00:32 and 23:45 local: api_cache,
learned_procedures, learning_events, reasoning_state, snippet_vault,
speed_routing, stream_progress) and appends to the two logs
(api_usage.json, evaluations.jsonl).  Both log tails carried duplicate
rows (three identical api_usage lines at one timestamp; two
evaluations rows 22 ms apart) -- a property any timestamp-derived
write rate must reflect.  Bursts are bursty, not continuous: a ~40
minute quiet gap preceded the 21:58 burst, so a burst CAN land inside
a session's guard window.

### The guard fix: exocortex watched, reported, never verdict-breaking

`tools/converse.py` now snapshots `exocortex/` as a second watched
root alongside `state/` (EXO constant, `exo_before` at build,
`exo_moved` at the end).  The churn is REPORTED -- a console line and
an `exocortex_churn` field in the fitness report -- but never breaks
`live_files_untouched`: with two concurrent writers (house and
session) the before/after diff cannot attribute a change, and a house
burst inside a suite window would false-flag every row.  A guard that
cries wolf gets ignored, the way the disk-full 0.0s were.

No whitelist for the two logs: the rule was to whitelist them only if
sessions legitimately append -- measured answer is they do not, so
there is nothing to tolerate.  They are watched like every other
exocortex file.

### The exit-save fatality, proven by execution (tmp_save_fatal.py)

The wrapper patches `state_hygiene.save_session_state` to raise
`SystemExit("FATAL: session save failed: forced for evidence")` --
visible to converse because it binds the module object (`from tools
import state_hygiene`), so the attribute lookup at the call site
resolves through the patched module.  Run with stdin at EOF (zero
turns, straight to the end-of-run save):

- exit code 1 (measured with `cmd /v:on`, `PYEXIT=1` -- the first
  attempt through a pipe reported findstr's 0, not python's).
- the FATAL line on stderr, through the real unwrapped call at
  converse.py:748 and require_saved's SystemExit
  (tools/state_hygiene.py:138).
- the new exocortex churn line executed in the same run ("none").

A second run (--save probe, unpatched) verified the report field:
exit 0, `state/fitness/conversation_probe.json` carries
`"exocortex_churn": []` beside `live_files_untouched: true`.

### Every shipped test through the deliverable

Full pytest after the guard fix: 407 passed, 3 skipped, 0 failed,
147 s -- identical to the pre-edit baseline.  Probe artifacts cleaned:
five session dirs and conversation_probe.json deleted; the 22:49
writer-path dir was already swept by the report run's own
prune_sessions().