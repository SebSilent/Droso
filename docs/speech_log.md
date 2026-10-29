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
both interpreters (3.10 and 3.12) — the 3.12 leg via a uv ephemeral env,
since the venv-less 3.12 has no pytest (`py -3.12 -m pytest` dies with
`No module named pytest`; `uv run --no-project --python 3.12 --with
pytest pytest -q tests/test_api_organs.py` re-confirmed 62 passed in
0.83 s, 2026-10-27). Mutation-verified both ways on 3.10, the
interpreter where the trap exists: with the guard reverted both tests fail
with `KeyError: 'file'` from `tempfile.__getattr__`; restored, 62 pass. On
3.12 the trap does not exist (`hasattr(e, "read")` is True and `read()`
returns cleanly with `fp=None`), so the test passes either way there — the
docstring's "measured on this interpreter (3.10)" note is what keeps the
test honest.

#### 4. SAN global decay, now measured per-phase (observation; mechanism measured and the consolidator landed 2026-10-27 — update below)

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

**Update 2026-10-27 (the live drain).** The mechanism behind this watch is
now measured: decay is lazy — it fires only on `live()` calls landing ≥10 s
after the previous fire (`organs/neural_language.py:437-439`), and the live
state's census is byte-identical across 72 minutes of idle (03:35 → 04:47:
nnz 66,107,030, real 1,446,352, strong 72,680, median 1.670433 — unchanged
from the drain's last post-census). The smoke run's per-phase decline came
from the session's own calls, not elapsed time. The rehearsal-policy
question this entry raised now has an instrument:
`tools/consolidate_live.py` replays the urgent band back above the line,
and the drain's equilibrium finding (this log, 2026-10-27 late) says the
urgent pool stabilizes at the replay budget — the taught band holds, the
dust pool is maintained rather than eliminated. Monotone decline without
rehearsal remains the risk this entry flags; the consolidator is the
counter-pressure.

#### 5. Where-filler fix is state-dependent on question shape (resolved 2026-10-26 by the question-shape parser; verified 2026-10-27 by the where_kept script, see both entries)

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

Update 2026-10-27: the script now exists -- `where_kept` (tools/scripts.json),
the exact shape this entry named ("where is the box kept" / "where is the
coat kept", plus the state tell "the box is heavy" so the preposition veto
is tested under this shape too). Measured warm 2/2, cold 2/2
(state/fitness/script_benchmark_20261027_024233.json): both asks recalled
the right locative-final proposition ("shelf" / "closet"), the state tell
never surfaced, and the cold session leaked neither taught word. The
positional shortcut held; the role-aware version stays the named fix if a
shape ever fails it. Design and numbers: the 2026-10-27 entry at the bottom
of this log.

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

## 2026-10-27 — design: the consolidation organ (sleep phase)

Written before any code change, per the standing rule. The four
machinery questions were settled by measurement first; the design
follows from them.

### The four machinery answers (measured this turn)

**1. Where SAN weights decay.** A global multiplicative pass,
call-driven with a refractory: `elapsed = min(now - _last_decay, 10)`;
fires only when `now - _last_decay >= 10`; applies
`san_w *= 0.995 ** elapsed` (organs/neural_language.py:410-415). So
each fire shrinks the whole matrix by at most 0.951, and fires are
bounded to one per 10 s of live() activity -- not 0.995 per wall
second. A tight replay burst fires decay at most once (the first call,
if the last fire was >10 s ago); replay does not self-destroy the
matrix. The first fire costs -4.9% on everything: accepted, noted.
Constants: SAN_DECAY_PER_S=0.995 (:25), SAN_DECAY_INTERVAL_S=10.0
(:826), SAN_ROW_CAP=1024.0 (:46), HEBB_LR=0.10 (:23), SAN_TOP_K=512
(:45). A second decay site for the cortex sits at :822 (one step over
elapsed time).

**2. The learn path.** live(text, learn=True, speaker=None,
attention=A, announce=False, readout=False) is the replay path:
speaker=None skips the binder write and the person cell (no episodic
record, no salience inflation) and keeps sal=1.0; readout=False skips
the second full-width SAN gather (the reading path's discarded half,
half of the 54% reading time _spread costs). The write itself: sparse
Hebb over the active set -- upper-triangle co-activations, top-512
kept, `san_w[ri,rj] += eff_lr * act_i * act_j` clipped [0,4],
symmetric, then the 1024 row cap on touched rows (:371-409).
eff_lr = 0.10 * (0.5 + 1.2*attention) * min(2,sal) * min(3,surprise).
The interoception band rides in act at 0.6x (:288), so replay also
wires tokens to the current body state -- a known side effect,
bounded by TOP-K, accepted for the first cut and measured.

**3. What value signals propositions carry.** The binder meta carries
who (witness), count (hearings), when (last same-witness hearing).
Measured composition of the live 60,000 rows: 59,515 book / 466
droso / 19 parent. Count spans 1 to 11,925. High-count rows hold
strong wiring despite ~11-day ages (counts 3,143-11,925 -> pairs at
2.5-4.0); decay damage concentrates in low-count old rows (measured:
"you learned a word" pair at 2.35e-13, "you know more now" pairs at
9.72e-03 and 2.95e-22 -- parent rows, heard ~25 times, ~17 days old).
The top-count rows are droso self-echoes, not the teachings: the 19
parent rows rank by count 24-11,925, and the three oldest (counts
24-25) are exactly the decayed ones.

**4. Where a sleep phase hooks.** The house is down; the hook is
end-of-session in tools/converse.py before the final save, plus the
method on the organ itself. Persistence: save_state(force_san=True)
writes the SAN -- a delta save skips it (the delta branch returns
early with skipped=["san","sequence"]), so the hook must force the
full save after replaying or the replay is lost. The existing
end-of-run hygiene save then follows as a no-op delta.

### The design

**Problem.** The live SAN drains real weights: 610k -> 573,424 real
(>=1e-6) over ~3 h of house runtime (-6%); dust grows by the same
amount. Every real weight marches toward the 1e-6 line and crosses
it; below the line the weight is indistinguishable from dust and the
word's wiring is effectively gone. Nothing restores wiring except a
new hearing of the same words.

**Capability claim.** A sleep phase that replays high-value
propositions through the real learning path re-strengthens their SAN
wiring before it decays through the line: the SAN's real-weight
census stops draining (or drains materially slower) across sessions,
without changing recall behavior on the suite.

**Value function (initial, to be calibrated).**
value = witness_w(who) * log1p(count); witness_w: parent=1.0,
droso=0.3, book=0.6. Parent rows are the teachings, book rows the
corpus knowledge base, droso rows self-echoes.

**Urgency filter.** A row is urgent when its weakest measured
token-pair weight < 0.1 (25x below the strong band 2.5-4.0; catches
9.7e-03 rows and dust rows, skips 0.7+ rows). Pair weights are read
from the live matrix via the footprints -- the actual current wiring,
not a decay model.

**Scope cut.** The pair-weight scan runs only over the value-ranked
top M=2,000 rows (all 485 taught + top-1,515 book by count). The
un-scanned bulk is one-time book rows (count=1) -- forgetting them is
the design working, not a gap. Cost: ~2,000 rows x ~45 pair gathers,
seconds.

**Budget.** K=200 rows per sleep, passes=3, attention=0.5
(eff_lr ~ 0.11/pass -> ~0.33/pair restored -- inside the band's lower
reach, 5 orders above the line). The row cap bounds overshoot.

**Hook.** NeuralLanguage.consolidate(...) on the organ (it owns
san_w, live, meta, footprints); called at end-of-session in
tools/converse.py before the final save; report fields land in the
fitness JSON. A standalone CLI comes with the house integration, not
now.

**Report.** rows_scanned, rows_urgent, rows_replayed,
san_real_before/after, sample per-row min-pair before->after,
elapsed_s.

**Acceptance (the A/B, all through the real paths).**
1. Baseline: real-count 573,424 (measured twice, stable).
2. A converse session with the hook: rows_replayed > 0; sample deltas
   show dust pairs restored (e.g. 2.35e-13 -> ~0.3); the suite stays
   green (replay only adds wiring; the risk is row-cap scaling
   shifting strong rows -- the suite's pass rates are the check).
3. The watch across N sessions: real-count >= baseline -- the
   capability claim, measured by tmp_san_watch.py.
4. Full pytest green.

**Not in this cut.** No house timer, no CLI, no witness-weight
calibration beyond the initial values, no SAN float16 (killed earlier
by the mask amplifier), no dust-clear (killed earlier -- the dust is
load-bearing for fully-decayed words).

**Verification (measured 2026-10-27, all through the real paths).**
1. Baseline: real-count 573,424 measured twice -- the A/B probe's
   loaded census and tmp_san_watch.py's npz census agree exactly;
   stable across the whole verification window.
2. Hooked session (hooktest_20261027_004655, 4 turns): rows_replayed
   200, san_real 574,266 -> 720,882 (+146,616), nnz unchanged
   66,107,030, san_sum ratio 1.0996; deltas 20/20 restored, 0 flat --
   parent teachings 2.12e-13 -> 0.33 and 2.66e-22 -> 0.33 (eff_lr 0.11
   x 3 passes), 0.561/0.66 where footprint cells overlap. Persistence:
   the session copy's SAN npz on disk carries real 720,882 -- exactly
   san_real_after; the forced save wrote the consolidated state and it
   survives the process. Live files untouched (guard: build+turns,
   banc content-verified). The A/B probe on the live state agrees:
   573,424 -> 719,534 (+146,110), same shape.
   Suite with the hook active: 7 scripts x warm 2/2 + cold 2/2 =
   28/28 (script_benchmark_20261027_014329.json), delta +0.00
   everywhere, override winners ['hot','hot'], no FAIL lines; warm
   71.7-89.3 s, cold 58.5-69.0 s (~18 min total, ~+50 s/session hook
   overhead). Every suite session's report: rows_replayed 200,
   san_real ~572,450-574,374 -> ~718,104-723,688. The row-cap risk
   (scaling shifting strong rows) did not materialize: pass rates
   identical to the pre-hook baseline 28/28.
3. Watch across N=14 hooked sessions: live real 573,424 -- exactly
   the baseline, unchanged; nnz unchanged 66,107,030. The live state
   is untouched by sessions (the guard's claim, confirmed by census);
   the restore lands in each session's copy. Steady state: in this
   cut the backlog does not drain -- sessions consolidate their own
   copies while the live matrix stays untouched, so every session
   re-finds the same top-200 urgent rows from the unchanged wiring
   (priority-ordered by witness weight x log(count)). No meta marker
   is needed for the drain: urgency is re-measured from the live
   matrix each scan, and a restored row's weakest pair lands ~0.33,
   above the 0.1 urgency line, so it self-selects out -- once the
   live state itself consolidates (the house-integration cut), the
   backlog drains at ~200 rows per run, ~10 runs for the current
   ~1,892-row urgent set, and decay then re-enters rows on the same
   self-selecting cycle.
4. Full pytest: 407 passed, 3 skipped, 0 failed, 146.24 s --
   identical counts to the pre-hook suite.

**Housekeeping (2026-10-27).** state/backup_f16/ (the four f32
originals, ~746.5 MB) is kept: the f16 cortex migration is hours old,
state/ is not in git so these are the only f32 originals, and disk
pressure is gone (196.9 GB free) -- revisit after the migration has
soaked. Loose end closed: the seq store's on-disk weight is float32
(13,079,347 elements) -- the swing-1 f16 conversion was fully
reverted, and sequence_organ's save forces dtype=float32 while its
load is a plain np.load, so store and code agree. Scratch swept
(11 files): the consolidate probe family superseded by the A/B, the
diag/rt/sizes/pytest2/probe/migrate outputs whose numbers are logged,
and the broken tmp_f16_migrate.py (the parents[1] crash is documented
above; the working converter is tmp_f16_convert_cortex.py). Kept:
tmp_san_watch.py, tmp_consolidate_ab.py + its output (cited above),
the f16 convert/rollback/ab trio (the live f16 state's
reproducibility and rollback path), and the earlier-phase probes
(tmp_flip_gap.py, tmp_footprint.py, tmp_san_mask_probe.py,
tools/_swing3_probe_f16.py, tools/_swing3_sizes.py) whose disposition
is not this cut's call.

**Sweep, owner call (2026-10-27).** tmp scratch swept to three keepers:
tmp_consolidate_ab.py + tmp_consolidate_ab_out.txt (the A/B evidence) and
tmp_san_watch.py (the watch instrument). Swept: the f16
convert/rollback/ab trio, tmp_flip_gap.py, tmp_footprint.py,
tmp_san_mask_probe.py, tmp_save_fatal.py, and the parser-era runners
(tmp_run_seen.bat, tmp_run_seen2.bat, tmp_run_suite.bat) -- every one's
numbers are already in this log. The f16 rollback path is now
documentation-only; state/backup_f16/ still holds the f32 originals.
tools/_swing3_probe_f16.py and tools/_swing3_sizes.py stay untracked,
disposition still open. Re-census after the full 28-session suite: live
real-count still 573,424 -- the baseline claim holds at N=28.

## 2026-10-27 — the where-filler residual gets its script (design before code)

**Claim under test.** Debt entry 5's heading says the where-filler residual
was "resolved 2026-10-26 by the question-shape parser"; its body still reads
as written on 2026-10-25: the filler rule is a positional shortcut, no script
hits the shape, and a future one "needs a role-aware version ... rather than
a positional shortcut". Heading and body disagree only if the parser fails
the very shape it claims to cover -- a measurement question. This entry
designs the measurement before touching code.

**What the code does today (read this turn, not measured).** Three pieces
have to hold together for "where is the box kept":
1. `_question_shape` (organs/neural_language.py:2080-2086) takes the locative
   subject as the FIRST content token after the copula, not every one; the
   comment names this exact question -- "kept" is not part of the subject, so
   the shape stays checkable instead of vetoed.
2. The ranking key's where-case (organs/neural_language.py:2357-2358) takes
   the filler from the CANDIDATE's last token, not the question's ("the box
   is kept on the shelf" -> "shelf") -- which is why "kept" never becomes the
   filler in the first place.
3. `_shape_matches`' locative branch (organs/neural_language.py:2158-2180)
   requires a preposition after the copula, vetoing state-answers ("the box
   is heavy") -- the original failure-1 mechanism, now under the new shape.

**The script (`where_kept`, tools/scripts.json).** The debt log's exact
shape: the question's last token is a content verb ("kept"), not the subject.
Two independent pairs, plus the state tell on the box so the preposition veto
is tested under this shape too (accumulation tests it only subject-final):
- tells: "the box is heavy", "the box is kept on the shelf", "the coat is
  kept in the closet"
- "where is the box kept" -> any_of [shelf], must_not_contain [heavy, closet]
- "where is the coat kept" -> any_of [closet], must_not_contain [heavy, shelf]

**Known non-blocker.** learn_qa (organs/neural_language.py, `def learn_qa`)
refuses the pair "where is the box kept" / "the box is kept on the shelf"
(two roles missing: the preposition and the place), so the where answer-type
prior does not learn from these pairs. The shape mechanism does not need the
prior to answer; the prior only feeds the ranking key's `expected` term,
which keeps whatever the subject-final pairs taught it.

**Acceptance.**
- Warm 2/2 and cold 2/2 via `tools/script_benchmark.py --only where_kept`:
  the residual is closed-by-parser with a number, and entry 5's body gets its
  "no current script hits this" clause corrected -- a script now hits it and
  passes.
- Any fail: the failure mode picks the fix; findings proposal #1 (role votes
  conditioned on proposition length) is the named candidate. No code changes
  before the measurement lands.

**Word check first.** "kept" and "closet" appear in no existing script;
tools/check_script_words.py runs before the benchmark and fails loudly if
Droso does not own them. If a word is missing, it is swapped for an owned one
and the substitution is logged here -- the shape property (content verb after
the copula) is what is under test, not the specific word.

**Measured (2026-10-27, state/fitness/script_benchmark_20261027_024233.json).**
Warm 2/2, cold 2/2, live files untouched. Warm: "where is the box kept" ->
"the box is kept on the shelf" (winner "shelf", source: recalled
proposition); "where is the coat kept" -> "the coat is kept in the closet"
(winner "closet"). The state tell never surfaced ("heavy" in no reply); the
report does not show whether the preposition veto fired or overlap ranking
alone sufficed -- either way the state answer lost. Cold: both asks answered
with nothing; neither taught word ("shelf", "closet") leaked. Two side
observations: the coat tell produced no echo (spoken: false) yet still bound
and was recalled -- echo and binding are separate surfaces; and the warm
session bound one nonsense echo as a proposition ("droso says toe intimate
await hammersmith llm communion") -- the known echo nondeterminism,
harmless here. The SAN drained during the session as the decay finding
predicts (total 298,817.75 -> 265,816.031 over 8,148 changed rows, on the
benchmark's copy).

**Resolution.** The residual is closed-by-parser with a number: the
positional shortcut held on the very shape it was warned about. Debt entry 5
gets a dated update; no code changed.


## 2026-10-27 (late) — the consolidator reaches the live state (design
## before code)

**Claim under test.** The consolidation organ's verification (above) closed
all four acceptance items on session copies; the live matrix stayed
untouched, so the urgent backlog never drains and the live census stays
pinned at 573,424 while decay continues underneath. This entry designs the
house-integration cut's first step: the same consolidate() on the live
organ, driven by a CLI, while the house is down (checked this turn: every
python.exe process is Tacit/turn-worker infrastructure, none is serve.py —
no concurrent writer of the live state).

**The resolution (operator call).** The drain is the repeated-runs path,
not one mega-call. The urgency filter makes it self-draining: restored
rows land ~0.33 (A/B deltas: 20/20 restored >0.1, range 0.33–1.32), above
the 0.1 urgency line, so they self-select out of the next scan; ~9 runs of
200 clear the backlog. One mega-call is rejected: 1,888 urgent rows × 3
passes = 5,664 replay calls wire every token to one static body state ~9×
more than the proven 600 (the A/B's 200×3) — an unmeasured distortion the
200-row budget exists to bound.

**The decay compounding, accepted with the math logged.** The decay fires
inside the SAN gather path on any live() call ≥10 s after the previous
fire, capped at 0.995^min(elapsed,10) = ×0.951 per fire (:410-415). The
A/B's own sum ratio independently confirms the per-fire factor: 19.6 s →
2 fires → ×0.904 on the base sum 298,817.7 → 270,247; measured after-sum
328,568.9 − 270,247 = 58,322 over 146,110 restored cells = 0.399 average
restored value — consistent with the delta list (mostly 0.33, some
0.56–1.32). Per run the factor is ×0.951^(fires in run), fires ≈
run_s/10 + 1 (a fresh process's stale timer fires once at the first call
— the mechanism's own cap charging bounded disk-time). Uniform
multiplicative decay preserves all rankings and the 25% mask exactly
(scaling commutes with any threshold structure). The strong band (2.5–4.0)
may land ~1.6–2.5 under the operator's 9-fire estimate, lower if runs fire
more (measured per run by the census); the acceptance floor is 3+ orders
above the 1e-6 line either way, recoverable by future Hebb writes, and the
suite verifies behavior.

**The tool (tools/consolidate_live.py).** Build the house agent at the
live root (build_house_agent(cfg, project_root=ROOT) — the same build
converse.py:149 uses, minus the re-pointing), stop the five
background-life organs (converse.py:158-167's loop), learning_loop
read-only, oracle blocked, prosthesis off, exposure off, persist True.
Assert the invariants that make the write safe (lang.persist is True,
state_path is the live language_state.json). Back up the seven live files (the json doc, the SAN, the sequence and
cortex stores, and their three JSON sidecars — the sub-saves write their
own sidecars, so the moved set is seven, not the four first written
here)
to state/backup_pre_consolidate_<ts>/ (fatal to skip — the first live
write ever gets a rollback path; every run backs up, each is a distinct
rollback point, ~383 MB each, disk has 196.9 GB). Guard snapshot AFTER
the backup (the backup's new files are then in the before-state).
consolidate() (defaults: budget 200, passes 3, attention 0.5,
urgency_line 0.1, scan_top 2000), save_state(force_san=True) (fatal on
failure — delta saves skip the SAN), guard check expecting exactly the
seven language_state files, census + strong-band stats before and after
(the watch's method: abs, !=0, real ≥1e-6; strong band = values ≥1.0:
count, median, max), report to state/fitness/consolidate_live_<ts>.json.
--dry-run: scan + replay in memory, no backup, no save, live files
untouched — the first measurement and the rows_urgent ground truth.

**Baseline moves, deliberately.** Every acceptance in this log anchors on
live real-count 573,424. This cut moves it: after the first run the live
census is the consolidated one (+~146k per the A/B shape). The new
invariant is not "unchanged" — it is "restored rows stay above the line
and the watch tracks decay from the new level". The backups are the
rollback.

**Acceptance.**
1. Dry-run: rows_urgent measured on the live organ (the A/B measured
   1,892 on its copy; the operator's drain math uses 1,888 — the dry-run
   decides the run count, ~9-10); live files untouched (guard: no
   movement).
2. Each run: rows_replayed ≤ 200; live san_real rises; guard names
   exactly the seven language_state files; backup exists and pre-state is
   recoverable; census before/after recorded with strong-band stats.
3. The drain, measured: rows_urgent falls run over run by roughly the
   previous run's rows_replayed (self-draining, now on the live state);
   the final run replays fewer than 200 or zero.
4. Recall behavior unchanged: the full suite on the consolidated live
   state stays 28/28.
5. Full pytest green. The measured compounding math (per-run decay
   factor, strong band before/after) written back into this entry.

**Not in this cut.** No house timer (the house is down; a timer wired
into a down process cannot be measured — it lands with the house
integration), no witness-weight calibration, no dust-clear, no scan_top
change (the drain works within the mechanism's own 2000-row scan).


## 2026-10-27 (late) — the live drain, measured

**The design entry above, run.** `tools/consolidate_live.py` (new CLI,
committed with this entry) drove the same `consolidate()` against the live
matrix while the house stayed down: per-run backup of the seven
language_state files, a file guard around every write, a per-run census, at
most 200 urgent rows replayed per run. Four invocations: a dry-run, two
multi-run drains killed by the environment (a background job dies with its
turn; a foreground command dies at the 420 s shell cap), and one single-run
invocation that fits the cap. Every run's guard was clean, and every kill
left the disk matching the last completed run's census to the digit — the
kills cost nothing.

**Dry-run** (`state/fitness/consolidate_live_20261027_030440.json`):
rows_urgent 1,892 measured on the live organ (the A/B copy also read 1,892;
the operator's drain math said 1,888 — the dry-run decides); guard
`"moved": []` across 600 live() calls.

**Drain 1** (report `...030631.json`, five runs, killed mid-run-6; san_real
starts at the boot census 573,424 and rises every run):

| run | urgent | replayed | san_real after | strong after (median) |
|---|---|---|---|---|
| 1 | 1,892 | 200 | 719,462 | 89,278 (1.963) |
| 2 | 1,504 | 200 | 863,252 | 94,900 (1.689) |
| 3 | 939 | 200 | 979,206 | 99,318 (1.522) |
| 4 | 630 | 200 | 1,093,844 | 93,698 (1.437) |
| 5 | 388 | 200 | 1,209,120 | 89,122 (1.345) |

Run 6's backup exists (`state/backup_pre_consolidate_20261027_030631/run06`);
its record never reached the report. The disk after run 5 matched run 5's
census exactly (read straight from `state/language_state.san.npz`: real
1,209,120, strong 89,122, median 1.345438).

**Drain 2** (report `...031640.json`, seven runs, killed mid-run-8 at the
shell cap; run 8's backup exists, its record and save do not):

| run | urgent | replayed | san_real after | strong after (median) |
|---|---|---|---|---|
| 1 | 206 | 200 | 1,314,744 | 64,992 (1.296) |
| 2 | 70 | 70 | 1,319,534 | 70,142 (1.436) |
| 3 | 86 | 86 | 1,326,368 | 68,570 (1.660) |
| 4 | 118 | 118 | 1,348,216 | 69,712 (1.854) |
| 5 | 100 | 100 | 1,358,252 | 69,370 (2.008) |
| 6 | 164 | 164 | 1,385,986 | 71,734 (1.869) |
| 7 | 227 | 200 (cap) | 1,415,408 | 74,468 (1.757) |

**Run 9** (`--max-runs 1`, report `...033432.json`): urgent 287, replayed 200
(cap), san_real → 1,446,352, strong 72,680 (median 1.670433, max 4.0). Disk
matched its census_after exactly.

**The termination criterion was falsified.** The design entry predicted
rows_urgent falls run over run by roughly the previous run's replayed,
ending below the cap. Measured: the initial descent ran ahead of the replay
budget (1,892 → 188 in five runs of 200 — the design's self-draining
prediction held), but the pool then refilled: drain 2's urgent series is
206 → 70 → 86 → 118 → 100 → 164 → 227 → 287, and run 9 replayed at the cap.
The mechanism is the replay plus lazy decay. An urgent row's min_pair sits
just under the 0.1 urgency line (0.078–0.097 in the recorded deltas); the
replay lifts it to 0.33–0.62; decay then walks it back down — ×0.951 per
fire at most (the code's own cap, `0.995**min(elapsed,10)`,
organs/neural_language.py:437-439), fires landing only while calls are
active — so a restored row re-crosses the line after ~24–36 fires, i.e.
~4–9 drain runs at ~4–6 fires per run. The drain's own restorations re-arm
within several runs; the pool never empties; it equilibrates near the replay
budget rather than draining to zero. The CLI's own output says it: "the
backlog only decays upward". Drain-to-zero is not a termination criterion;
equilibrium at the budget is the steady state, and the house timer's load is
exactly this treadmill.

**Decay is lazy, and the censuses prove it.** Drain 2 run 1's census_before
(strong 89,122, median 1.345438) equals drain 1 run 5's census_after to the
digit across ~6 idle minutes: no live() calls, no fires, no decay. Idle time
does not erode the matrix; only call-time does.

**The strong band, before/after (acceptance item 5's write-back).** Boot:
93,286 (median 2.400, max 4.0). Drain 1 held it near boot (89,278–99,318)
with the median falling (2.400 → 1.345) as restorations landed below the old
core. Drain 2 run 1 then eroded it to 64,992 (1.296) — the band's lower edge
emptying under the replay's own decay fires — and it rebuilt run over run to
74,468 (1.757) by run 7, settling at 72,680 (1.670) after run 9: repeated
rehearsal pushing restored rows past 1.0. The 1e-6 floor held throughout,
orders of magnitude above it.

**Acceptance, closed against the live state.**
1. Dry-run: rows_urgent 1,892 on the live organ; guard `"moved": []` across
   600 live() calls; live files untouched. ✓
2. Each of the 13 runs: rows_replayed ≤ 200; live san_real rose every run;
   the guard names exactly the seven language_state files; a per-run backup
   exists; census before/after with strong-band stats recorded. ✓
3. Falsified as written (above): the urgent count does not fall run over run
   to a sub-cap terminal — it refills from decayed restorations and
   equilibrates at the replay budget; the final run replayed 200, not
   fewer. Replaced by the equilibrium finding.
4. Recall unchanged: the full suite on the consolidated live state — 32/32
   asks across all 8 scripts, warm 1.0 / cold 1.0 (seven chunk reports,
   `script_benchmark_20261027_040618` … `042828`; the item's 28/28 holds as
   the 7-script subset). Each suite session runs on a fresh copy of the
   live state (converse.py re-points persistence into a session dir), so
   the measurement left the live state untouched: all seven files still
   carry the 03:35 mtime and the post-suite census is identical to run 9's
   (real 1,446,352, strong 72,680, median 1.670433). The override winners
   were recorded ('hot', 'hot'), never graded. Re-verified on the
   post-extension state (the series below): the full 8-script suite, report
   `script_benchmark_20261027_062549.json` (exit 0, 1,745.9 s) — 32/32 asks,
   zero `"pass": false` anywhere in the report, all 16 phase entries
   (8 scripts x warm/cold) reading `"passed": 2`. The post-suite census is
   byte-identical to run x15 (real 1,454,608; sum 286,281.0625; strong
   65,666; strong median 1.596504; max 4.000000; nnz 66,107,030) — the
   proof this item needs: had any decay fire run during the suite's 29
   minutes the strong band would have moved (rows in [1.0, 1.051) cross the
   line on one capped fire). It did not move. The census's `real_median`
   reads 3.829e-02; that figure is not an anchor — the extension table never
   recorded it and it drifts with the sub-band population — the six values
   above are the identity.
5. Full pytest green: 407 passed, 3 skipped, 161.19 s. The measured math is
   the strong-band series above plus the per-fire cap. Re-run against the
   post-extension state this cycle: 407 passed, 3 skipped, 161.60 s — the
   counts hold exactly; the gate is the count, not the time.

**On the record.** An earlier session's narration claimed a suite report
`script_benchmark_20261027_033718.json` (28/28 "on the consolidated state"),
a commit `7c1e9b4` carrying a "Measured block" with the removal series
388/565/278/96/96, a drain-1 run-6 terminal record with rows_urgent 0, and
a pytest count of 364. None exists: no such report file, no such commit
(HEAD is 24c2b75), the drain-1 report holds exactly five run records with
nothing after run 5's census, and pytest is 407/3. The true series above is
the first record of these numbers; the fabricated figures never landed on
disk.

The three backup roots (`state/backup_pre_consolidate_*`) are the rollback
and are now gitignored — measured this turn at 105 files (15 run-dirs × 7),
3.88 GB total; the "~383 MB each" drafted earlier was wrong. They stay
until the house integration has validated the consolidated state in live
use, then go (deleting reclaims the 3.88 GB). The killed runs' backups
(run06, run08) stay as evidence of where the kills landed.

**Addendum (same night) — the refill has two sources, and the +18 is the
second.** The equilibrium finding above attributes the refill to decayed
restorations re-crossing the line. The series' shape shows a second
source, and the code settles a wrong hypothesis first: `consolidate()` is
"read-only on the binder" (`organs/neural_language.py:467`) — the replay
writes only the Hebb rule, never the counts — so the scan window's
composition is stable and the refill is not new window entrants. It is
the run's own decay fires. Each fire multiplies the whole matrix by
×0.951 (`:437-439`), and the runs' `elapsed_s` (drain 1: 20.5–32.1 s,
drain 2: 19.6–51.2 s, of scan+replay) means ~2–5 fires per run — so every
run pushes the just-above band under the line: rows that were not urgent
at the run's scan but are urgent at the next. Measured: run 5 ended with
an inferred pool of 188 (388 − 200 replayed); drain 2's boot scan read
206 — the +18 is the just-above band crossing during run 5's ~3 fires
(elapsed_s 31.0 → ×0.86: rows in [0.1, 0.116] fall under between the two
scans); the closure is exact (188 + 18 = 206). The series' shape
separates the sources: drain 2's per-transition refill oscillates +16 to
+64 (once −18) through its first six transitions, then jumps to +260 at
the last — the drain-1 cohort walking back down. The fire ledger: 12
fires across drain 1's five runs, 20 more across drain 2's seven, so run
9's scan reads the matrix at ~32 fires — right where the cohort's ~0.5
landings cross (0.5 × 0.951^32 ≈ 0.10, the line itself); the 0.33
landings crossed at ~24 fires (drain 2's run 6, where the +64s begin)
and the 1.32 tail needs ~52 fires, still above the line. Equilibrium at
the replay budget is the joint steady state of band-eating and the
cohort's slow walk-down; drain-to-zero is unreachable even within a
single run.

**Watch census (debt entry 4's second data point).** The live state has
been idle since run 9's save (03:35); a pure disk read of
`state/language_state.san.npz` at ~04:47 returns the post-suite census to
the digit (nnz 66,107,030; real 1,446,352; real_median 7.510650e-02; sum
334713.1250; strong 72,680; median 1.670433; max 4.0). 72 minutes of
idle, zero decay — the lazy-decay proof now spans 72 minutes where the
census identity gave ~6. Idle time does not erode; calls do.

**Acceptance cycle closed (2026-10-27).** The checks re-executed against
the committed state (`1f5c9e7`): the census check (`tmp_census_check.py`)
returns the watch census's seven numbers to the digit; the full suite
407 passed, 3 skipped in 160.61 s (`py -3.10 -m pytest -q`); the api
file's 3.12 leg 62 passed in 0.83 s (method at debt entry 1). The
deliverable's execution record stands in the drain and suite reports on
disk.

## 2026-10-27 (late) — the strong band's equilibrium: self-correcting or
slow leak (design before code)

The drain entry left one question open: the strong band went
93,286 → 64,992 → 72,680 across the drains — is the erosion/rebuild
oscillation self-correcting (demotion plus rehearsal rebuild) or a slow
leak (rows crossing the line faster than the replay rescues)? This entry
designs the test before running it; the verdict gets its own paragraph
below with the numbers that decided it.

**The series, grepped from the three drain reports** (strong = strong_count,
med = strong_median; sum = total matrix weight; Δ = change from the
previous row's after-census):

| run | urgent | repl | elapsed_s | real_after | sum_after (Δ) | strong_after (Δ) | med |
|---|---|---|---|---|---|---|---|
| boot | — | — | — | 573,424 | 298,817.3 | 93,286 | 2.400 |
| d1 r1 | 1,892 | 200 | 20.8 | 719,462 | 312,616.4 (+13,799) | 89,278 (−4,008) | 1.963 |
| d1 r2 | 1,504 | 200 | 20.5 | 863,252 | 351,540.3 (+38,924) | 94,900 (+5,622) | 1.689 |
| d1 r3 | 939 | 200 | 28.1 | 979,206 | 384,020.8 (+32,481) | 99,318 (+4,418) | 1.522 |
| d1 r4 | 630 | 200 | 32.1 | 1,093,844 | 394,325.6 (+10,305) | 93,698 (−5,620) | 1.437 |
| d1 r5 | 388 | 200 | 31.0 | 1,209,120 | 402,580.7 (+8,255) | 89,122 (−4,576) | 1.345 |
| d2 r1 | 206 | 200 | 51.2 | 1,314,744 | 375,559.0 (−27,022) | 64,992 (−24,130) | 1.296 |
| d2 r2 | 70 | 70 | 19.6 | 1,319,534 | 372,988.3 (−2,571) | 70,142 (+5,150) | 1.436 |
| d2 r3 | 86 | 86 | 21.7 | 1,326,368 | 356,176.6 (−16,812) | 68,570 (−1,572) | 1.660 |
| d2 r4 | 118 | 118 | 29.3 | 1,348,216 | 356,082.5 (−94) | 69,712 (+1,142) | 1.854 |
| d2 r5 | 100 | 100 | 28.4 | 1,358,252 | 346,710.3 (−9,372) | 69,370 (−342) | 2.008 |
| d2 r6 | 164 | 164 | 42.4 | 1,385,986 | 331,617.8 (−15,092) | 71,734 (+2,364) | 1.869 |
| d2 r7 | 227 | 200 | 41.8 | 1,415,408 | 331,641.5 (+24) | 74,468 (+2,734) | 1.757 |
| r9 | 287 | 200 | 44.7 | 1,446,352 | 334,713.1 (+3,072) | 72,680 (−1,788) | 1.670 |

**The mechanism, from the code.** The replay never touches strong rows:
selection is urgency-filtered at the 0.1 line ("strong rows are left
alone", `organs/neural_language.py:446-455`), so the band erodes by decay
alone (×0.951 per fire, `:437-439`) and rebuilds only through the
rehearsal cohort's repeated climbs — a row replayed to 0.33–0.62 decays
back under the line, gets replayed again, and the Hebb write adds to what
remains; rows rehearsed often enough cross 1.0. Two restoring forces
follow: erosion removes the band's weakest rows first (just above 1.0),
which raises the band's median and slows further erosion; and the
rebuild's new entrants arrive just above 1.0, which lowers the median and
lets erosion pick up again. An oscillation with a restoring force, not a
ratchet — if the mechanism is right.

**The evidence in hand.** The trough rebuilt +9,476 (+14.6%) over six
runs; the sum's per-run change converged from −27,022 (d2 r1) through
−15,092 (d2 r6) to +24 (d2 r7) and +3,072 (r9) — additions catching the
decay losses; the band's per-run change narrowed from −24,130 to ±2,800;
the median's path (1.296 → 2.008 → 1.670) is the model's two-phase
rebuild (survivors rehearsed up, then cohort crossings diluting). Net
boot→r9: the band −20,606 (−22.1%) while the sum +35,895.78 (+12.0%) and
real +872,928 (+152%) — weight redistributed from the training-built band
into the rehearsal cohort, not destroyed.

**Decision rule (the second-cycle test).** One erosion-rebuild cycle is
observed; a leak and a new equilibrium agree on that window. Extend the
drain series house-down (the consolidator is committed, guard-clean, and
every run backs up first): chunked `tools/consolidate_live.py --max-runs 3`
calls under the 420 s shell cap, ~9–12 more runs. If the band holds
≥ ~70,000 across the extension with the sum's per-run change inside
±5,000, the oscillation is self-correcting at a new, lower equilibrium —
logged as a measured property, no fix. If the band's trough ratchets
below 64,992 with each cycle lower than the last, it is a leak: the named
fix is a maintenance pass that rehearses just-below-1.0 rows (the band's
own edge) ahead of the dust backlog, and it gets designed here before any
code moves.

**Measured — the extension (2026-10-27, 15 runs across five chunked
invocations, reports `consolidate_live_20261027_052621/053614/054114/
054642/055002.json`; the fifth chunk ran past the planned ~12 because the
12th run's dip was exactly the case the rule exists to catch).** House
down throughout; every run guard-clean (7 files moved, unexpected none);
nnz 66,107,030 at all 35 censuses. The extension series (continuing the
table above; x = extension run):

| run | urgent | repl | elapsed_s | real_after | sum_after (Δ) | strong_after (Δ) | med |
|---|---|---|---|---|---|---|---|
| x1 | 282 | 200 | 54.3 | 1,461,306 | 322,553.1 (−12,160) | 70,270 (−2,410) | 1.628 |
| x2 | 277 | 200 | 58.6 | 1,459,360 | 315,325.0 (−7,228) | 68,924 (−1,346) | 1.584 |
| x3 | 257 | 200 | 60.6 | 1,470,036 | 308,408.8 (−6,916) | 66,486 (−2,438) | 1.566 |
| x4 | 216 | 200 | 53.0 | 1,473,388 | 300,607.3 (−7,802) | 66,008 (−478) | 1.530 |
| x5 | 219 | 200 | 50.7 | 1,478,242 | 295,651.5 (−4,956) | 66,348 (+340) | 1.512 |
| x6 | 243 | 200 | 50.3 | 1,481,544 | 311,458.5 (+15,807) | 70,902 (+4,554) | 1.644 |
| x7 | 198 | 198 | 52.6 | 1,480,436 | 307,583.3 (−3,875) | 72,908 (+2,006) | 1.625 |
| x8 | 177 | 177 | 47.7 | 1,485,010 | 310,453.1 (+2,870) | 76,256 (+3,348) | 1.660 |
| x9 | 205 | 200 | 56.8 | 1,480,604 | 307,417.4 (−3,036) | 74,516 (−1,740) | 1.707 |
| x10 | 241 | 200 | 54.4 | 1,474,548 | 303,296.6 (−4,121) | 75,038 (+522) | 1.646 |
| x11 | 247 | 200 | 59.7 | 1,469,846 | 299,933.6 (−3,363) | 74,830 (−208) | 1.590 |
| x12 | 255 | 200 | 60.9 | 1,466,584 | 283,648.3 (−16,285) | 68,358 (−6,472) | 1.568 |
| x13 | 267 | 200 | 60.4 | 1,461,300 | 287,045.8 (+3,398) | 70,918 (+2,560) | 1.581 |
| x14 | 288 | 200 | 60.2 | 1,457,234 | 286,397.8 (−648) | 67,216 (−3,702) | 1.564 |
| x15 | 304 | 200 | 55.0 | 1,454,608 | 286,281.1 (−117) | 65,666 (−1,550) | 1.597 |

**Verdict: not a leak — a bounded, cadence-set oscillation.** The rule's
leak condition (a trough below 64,992, each cycle lower) never fired:
the troughs read 64,992 → 66,008 → 68,358 → 65,666, every one at or above
the first, and the band wandered [65,666, 76,256] for 15 runs with mean
~70,975 — no trend inside the window. The rebuilds recurred (+4,554,
+2,006, +3,348, +2,560), each from the cohort's crossings, exactly the
designed restoring force. The sum found its level: the last three runs'
changes are +3,398, −648, −117 — flat at ~286k, down from the boot 298.8k
but not falling. The rule's first branch as literally written (band
≥ 70,000 throughout, sum changes inside ±5,000) is violated by the
oscillation's own amplitude — the band dips to ~66k mid-cycle and single
long runs move the sum ±16k — so the verdict is taken on the rule's
intent: bounded and self-correcting, no fix designed, the maintenance
pass stays unbuilt.

**Two measured properties the rule did not anticipate.** (1) The
equilibrium is cadence-dependent: the runs slowed as the real count grew
(drain 1: 20–32 s; extension: 47–61 s — the scan ranks 1.45 M real rows),
more elapsed per run means ~5–6 decay fires instead of ~2–3, and the
lower equilibrium follows. The band's level is not a constant of the
design; it is set by the replay budget against the per-run decay, both of
which the operator's cadence moves. (2) The band's content turns over:
the replay never re-strengthens strong rows, so the training-built cells
decay while rehearsal-built crossings replace them — the max fell
4.000 → 3.804 (exactly one fire on the top cell) at x12 and returned to
4.000 at x13 when a crossing reached the cap. The band's size holds; its
membership is now rehearsal-selected, which is the design working, not
failing.

## 2026-10-27 (late) — design: the band answers — associative recall at
## answer time (design before code)

The extension verdict left a measured asset unused. The strong band — 65,666
cells at or above 1.0 on the live state, membership now rehearsal-selected —
is read by exactly one function, `associations()` (organs/neural_language.py:
1242, "what a token is wired to, read straight out of san_w ... it is the
weight matrix, asked"), and `answer()` has never consulted it. Retrieval
today is one hop: `cortex.binder.recall(content, k=40)` ranks stored
propositions by token overlap (:2220), an idf-weighted coverage key grades
the best candidate against the question's distinctive words (:2303), and
anything under `ANSWER_COVERAGE_FLOOR = 0.6` (:1911) is refused (:2316). The
weight matrix — the one structure holding what experience actually wired
together — is never asked at answer time.

**Why this is the highest-leverage item, in two paragraphs.** (1) The band is
a learned prior no LLM has: a per-association weight that decays with disuse
(0.995/s, capped x0.951 per fire) and is rebuilt only by rehearsal — and this
cycle measured that its membership turned over from training-built to
rehearsal-built (the max fell 4.000 to 3.804 and returned only when a
rehearsed crossing reached the cap). What that prior makes possible is the
answer type the one-hop path structurally cannot give: a question whose
answer memory shares no distinctive word with the question, joined only
through a bridge the band holds. Teach "the kettle rings at noon" and "the
noon bell calls the crow"; ask after the crow's caller by the kettle's hour,
and the direct key sees two half-matches — the cue-side memory covers 2/3 of
the distinctive weight and wins the 0.6 floor with total confidence,
delivering a wrong answer as a right one. The band walk makes the bridge a
retrieval cue instead of a trap. (2) No re-tuning of the existing key can
produce this, because the grading and the candidate pool are both per-memory:
the bridge token sits in neither the question nor the answer memory at
covering weight, so every key setting that keeps confabulation out also
keeps the answer out. The operation is new in kind — retrieval by graph
connectivity through weights that are the residue of what Droso actually
heard — and it is the first time a consolidation finding becomes an answer
rather than a number. It is also the cheapest of the candidate items: the
primitive exists and is measured, the seam is one refusal path in `answer()`,
the gate and the harness are already built, and it falsifies in a single
suite run — unlike a second competing brain (a new organ plus a vote, months)
or a region that grows (a new substrate, slow to falsify), and unlike prompt
assembly, which needs a model to read the prompt and this house has none.

### The mechanism

1. `answer()` runs the direct path unchanged — recall, the three filters
   (question-identity, remembered-question, echo), the coverage key. If it
   clears the floor with a winner, nothing else runs. The 32/32 cannot
   regress by construction: the walk fires only where the system now refuses.
2. On failure (no hits, or best coverage below the floor), the walk expands
   the cue: for each content word, `associations(w, limit=8)`; keep reached
   words that are not question words, cap the reached set at 16.
3. Recall on cue union reached (k=40); grade each candidate with the SAME
   idf-weighted key, but a question word counts as covered if it is in the
   memory's tokens OR is band-adjacent to a memory token (reached from it).
   The floor stays 0.6 — the bar on confabulation is untouched; only the
   matching becomes associative.
4. The winner is a stored proposition, spoken through the existing path
   (sequence organ, recalled-proposition fallback). The trace carries
   `source: "band walk"` and the reached set, so the suite and any later
   audit can tell which path answered. The walk never generates.

### The measurement

New script family, 4 scripts x 2 asks, warm and cold phases as in the
existing suite — 16 asks. Each ask is 2-hop by construction: cue word in M1,
answer word in M2, one shared bridge, M1 and M2 taught as separate tells so
the band wires cue-bridge and bridge-answer; no question shares a distinctive
word with the answer memory at coverage 0.6 or better. FIRST act of the
build, before any code: run the family against the current system unchanged
and record the per-turn baseline — expected at most 2/8 per phase, refusals
or cue-side wrong winners. Then the walk lands; re-run the family; re-run
the full existing suite (32/32 gate, report compared to
`script_benchmark_20261027_062549.json`) and pytest (407/3 gate). House
stays down; the live state is read through the session-copy path the suite
already uses.

### Success criteria

Pass: the walk answers at least 6/8 warm AND at least 6/8 cold on the family
with the direct baseline at most 2/8 each phase, the existing suite holding
32/32 and pytest holding 407/3. A wrong winner on the family that was a
refusal before counts against the pass — converting confabulation is worse
than silence, which is the house rule the floor was bought for.

### Falsification branch

Below threshold: a logged falsification with per-probe traces naming which
failure mode fired — (a) the reached set missed the bridge (the pair never
rehearsed, or the association floor is set above real wiring), (b) recall
found the memory but associative coverage still failed the floor, (c) the
wrong memory won. Each mode is itself a measurement of the band; the entry
stands as the record either way. Green or falsified — both close the item.

### Measured: the direct baseline (2026-10-28, before any code, system unchanged)

The family (`tools/scripts_band2hop.json`, 4 scripts x 2 asks) through the
existing per-session runner (`converse.py --scripts/--cold … --beats 2`;
each session works on a copy of the live state and every run reported
`live state files untouched: yes`; reports
`conversation_band2hop_{1..4}_{warm,cold}.json`).

Warm recall: **0/8.** Every ask refused at the coverage floor — coverages
31–44%: S1 42%/44%, S2 43%/41%, S3 36%/31%, S4 "nothing he remembers has
that shape" / 38%. No wrong winners anywhere: the floor held the gate
exactly as bought. The direct path does not answer 2-hop badly — it cannot
answer 2-hop at all. The gap is total, so the walk's target (≥6/8) is a new
ability, not a lift.

Cold control: 8/8 — but read `run_cold` (converse.py:597) before believing
what that number looks like: the cold phase is the contamination control,
graded on the ABSENCE of the taught words, and a refusal passes by design
("the honest answer to a question about a conversation that never happened
is not to assert one"). It carries no recall information. The threshold is
therefore restated: the recall axis is the warm phase; the cold phase is the
walk's confabulation gate — after the walk lands, cold must still refuse,
proving the associative path fires from session wiring, not corpus wiring.
(The main suite's "cold 1.0" has always meant this control, not recall;
noted here so no future reader mistakes the acceptance line.)

Two measured constraints on the build, from `tmp_band2hop_vocab.py`
(read-only, no organ): (1) word membership — 55 of 58 candidates known
against 10,138 `word_patterns`; bark, drifts, flares are not, and the
family avoids them. (2) **The band offers no fresh slate.** All 1,485
candidate pairs carry max |w| ≥ 0.5 over their 12x12 footprint blocks, most
at 1.9–2.0 — saturation, measured again at pair level. The session's tells
write ~0.1 per edge, two orders under the corpus background, so the walk
must rank by normalized spread (as `_rank_by_spread` already does — cosine)
and never by absolute weight. Whether session-level wiring is separable
from corpus wiring at all is the first real question the build answers; if
it is not, falsification mode (a) fires, and that is itself the measurement.

### The walk built, and where it stopped (2026-10-28)

`_band_walk` landed in organs/neural_language.py (helper before `answer()`,
splice at the coverage-floor refusal only — what clears the floor never sees
the band, so the one-hop path is untouched by construction). The winner
still runs the role ranking and the parser veto downstream; nothing is
generated.

Measured on the family, warm, current state: **still 0/8 — but the refusal
moved.** Script 1's asks, which refused at the coverage floor (42%, 44%),
now refuse at the parser veto: "nothing he remembers has that shape"
(converse.py report `conversation_bandwalk_1_warm.json`). The veto is
downstream of `hits`, so the associative coverage DID clear the floor and
fed a candidate — falsification mode (b) in the design's taxonomy: recall
found the memory, the shape arbiter refused it. The wall is not the band;
it is the arbiter the wrong-slot fix bought (it vetoes shapeless neighbours
when the question has a checkable shape), meeting a winner retrieved by a
route it was never tuned for.

Open question, named for the next cut: ~~the veto is either firing on the
filler's role index or on the cue word the memory lacks~~ — SUPERSEDED
2026-10-28 (Closed below): the premise was wrong on both halves. The
arbiter never saw "the noon owl spins salt", and it vetoed correctly.
Guessing at an arbiter's inputs without reading them is exactly what the
plumbing was for; the plumbing landed the same day and ended the guessing.

Honest gate status: pytest with the walk in place: 407 passed, 3 skipped,
163.03 s — held. Suite gate then RUN AND HELD (2026-10-28, tag
band-walk-gate, report `script_benchmark_20261028_013326.json`, against
committed `749f36e`): **32/32** — zero `"pass": false` anywhere in the
report, all 16 phase records `asked 2 / passed 2 / pass_rate 1.0`, and 8×
`live_files_untouched: true`. Wall 1774.2 s. The `answer()` splice is now
gated, not argued: the walk touches no one-hop outcome.

### Closed: the arbiter was right (2026-10-28, trace evidence)

Plumbing first, permanent: `_clean` (converse.py) now keeps `parser` and
`band_walk` and lifts `parser` out of the oversized `retrieval` dict on the
answered path; `run_script`/`run_cold` records carry both. Report
`conversation_bandwalk_1_diag.json` then showed what the arbiter was handed:

- "what does the bell spin": walk winner **"i do not like to boast of my"**,
  best_cov **1.0**. Reach sets: bell → {deliverance, her, i, in, to},
  spin → {boast, latency, owl, you}, does → {affinity, boast, charg, …}.
  "bell" was covered because the memory contains "i" — a function word in
  bell's reach set — and "spin" via "boast". Full coverage, zero relevance.
- "what does the owl ring": walk winner **"a ring to my bell about the
  hour"**, best_cov 0.746 — corpus text that co-locates ring+bell. Again not
  the told memory.
- The parser vetoed both, and the veto was RIGHT: neither sentence answers
  its question. Yesterday's mode-(b) label above is therefore corrected:
  the trace shows **mode (c), the wrong memory won** — recall never found
  the bridged proposition at all.

The design's bet is half-confirmed, half-falsified: the session edge IS
visible in the band (reach[owl] contains "spin", wired by the tells minutes
earlier), but under saturation the coverage rule is gameable — reach sets
are dominated by function words present in nearly every corpus memory, so
associative coverage scores 1.0 on noise. The signal exists; the scoring
rule is what failed.

Decision, by the pre-registered rule (arbiter right → falsification closed,
walk kept as a second brain's competing vote rather than a rescue path):
the splice now runs the walk at every floor-refusal, records its vote in
`band_walk`, and returns the original coverage-floor refusal — the mouth
never carries a walk winner. Verified live
(`conversation_bandwalk_1_vote.json`): refusals back to 42% / 44% with both
votes on the record. Gates after the demotion: pytest 407 passed, 3 skipped,
164.70 s — held. The suite was not re-run for this change: the refusal
branch is unreachable by a passing ask (all 32 suite asks answer), and the
return shape is the gated pre-walk form plus one trace key — both endpoint
states of this branch are measured 32/32. The item is CLOSED as falsified
rescue.

### The band cannot be the 2-hop substrate, measured both ways (2026-10-28)

The closure above named three fixes for a future walk. Two of the three were
the wrong diagnosis, and a standalone probe on the session copy
(`tmp_band_rank_probe.py`, reading `bandwalk_1_diag_20261028_014007`, san
nonzero 1,445,226 — matching the run report) settled it by recomputing the
organ's own score (`_spread` then `_rank_by_spread`) for every one of the
11,555 known words.

**Ranking route — falsified, with the exception that survives.** Session
edges DO reach the top of the ranking when the pair is rare: `spin→owl`
rank **1**, `owl→salt` rank **2**, `noon→owl` rank **1**, `salt→owl` rank
**1** of 11,555. They do not when the pair is common: `bell→noon` rank
**627** (percentile 94.6), `bell→rings` 651, `ring→rings` 6,851, `ring→noon`
6,727 — absent from bell's top-8 at both exposure cuts, while corpus noise
holds those slots (`deliverance` 1, `wail` 3, `latency` 6, `affinity` 7) and
the unrestricted cut is dominated by `i`, `to`, `the`, `her`, `in`. The
mechanism is one comparison: bell's own score distribution has p99 **0.048**
and max 0.391, and the told pair scores **0.026** — below p99; owl's p99 is
0.059 and its told pair scores **0.128** — above it. A single tell writes
~0.15, so the write is rank-visible only where the corpus background is
already thin. Filtering function words would not have saved the walk: it
would have left `deliverance` and `wail` in bell's reach and still lost
`noon`. **The reach mechanism, not the reach filter, is the wall.**

**Subtraction route — falsified.** If ranking can't see a write, subtracting
the state the session loaded from its own should: `D = session − live`.
It does not separate. 1,412,646 cells changed — essentially every nonzero
cell, because decay is multiplicative and the session fired it many times —
and the session's own consolidation restored 146,662 cells above 0.01.
Told pairs show max-block delta 0.1549–1.9934; control pairs never told
together reach **1.1628** (`owl-kettle`) and sit at **0.4886**
(`salt-lantern`, `noon-tide`) — the identical value told pairs show, because
a restored cell landing anywhere in a 12×12 block outvotes a tell's write.
min(told) 0.0000 < max(control) 1.1628: **OVERLAP**. The session's own
maintenance moves more mass than the session's experiences, so a
difference-based freshness readout is not a write signal at this state.

Verdict: at 1,445,226 real cells over 11,555 words the band answers 2-hop
questions only through rare-word windows. That is a real and narrow property
of it, and it is not the capability the family needs.

### Design: the proposition join (next item, before code)

The family is not a weight problem, it is a join. "the bell rings at noon"
and "the noon owl spins salt" share the token **noon**, exactly; ask 1 pairs
the first sentence's subject with the second sentence's verb. Shared words
are not saturated — they are either in both memories or they are not.

- **Mechanism.** When the direct path refuses (`best_cov < floor`), search
  for a pair of memories (a, b) such that a covers some must-words, b covers
  the rest, and a ∩ b contains at least one distinctive bridge token
  (`df*4 <= n_mem`, the house rule at :2351) that is not a question word.
  Hand **b** to the existing ranking and the existing parser veto as a
  competing candidate. Nothing is generated; the answer is a stored
  proposition; the veto still guards.
- **Scope is the safety property.** Restricted to memories bound by the user
  this session (`who == "you"` and `when >= session_t0`) — the same
  convention the freshness sort already uses (:2470). The corpus holds
  60,000 memories and thousands share a content word with each other, so an
  unfiltered join finds a path between anything. This is recall of today's
  conversation, not inference over everything ever read.
- **Uniqueness.** Exactly one qualifying b, else refuse and report the
  ambiguity. A join that fires on multiple paths is a guess.
- **Baseline.** 0/8 (this family, four scripts; script 1 measured 0/2 three
  times today: `bandwalk_1_warm`, `bandwalk_1_trace`, `bandwalk_1_vote`).
- **Pass/fail threshold.** ≥6/8 on the family **and** the shipped suite still
  32/32 — the join must not displace a one-hop winner.
- **Falsification.** If the unique-bridge criterion yields no candidate, or
  an ambiguous one, on ≥3 of the 4 scripts, then the family is
  under-constrained as a test and the join closes without a code change being
  justified. If candidates are found and unique but the parser vetoes them,
  the wall has moved to role/slot selection — which is a different, already
  partly-mapped item.
- **Known risk, stated before building.** The family expects `owl` for
  "what does the bell spin" — the *subject* of M2 — while "what" normally
  asks for an object. If the join hands over M2 correctly and the
  presentation answers `salt`, the failure is slot selection, not the join.

### Join, first run: not delivered, and the wall is the pool (2026-10-28)

Built as designed — `_prop_join` plus a splice at the refusal point that sets
`hits = [join_hit]` so the join *proposes* and the existing ranking and parser
veto still decide, with the join trace plumbed into reports (`_clean` keeps
`join`; `run_script`/`run_cold` record it).

Result: **0/2 on script 1, the join never fired.** Trace
(`conversation_join_1b.json`): `pool: 2`, `reachable: [bell, does, spin]`,
`pairs_covering: 0`, `joins: 0`. Neither tell contains "does" — "the bell
rings at noon", "the noon owl spins salt" — so the only memory that could
make "does" reachable is **the question's own binding**, which is in the
session pool because it was spoken by the user after `session_t0`. That echo
alone covers all of `reachable`, and the "neither memory alone" guard —
correct in principle, since an echo of a question is not a source of
knowledge — therefore rejects every pair. The join needs the same echo
filter the direct path and the walk already pay. Named, not yet built.

Corrected mid-flight, and worth keeping: the first attempt refused with
`pool: 2, reachable: [bell, does, spin], joins: 0` because the bridge was
filtered by corpus rarity (`df*4 <= n_mem`), which discarded the one true
bridge "noon" — **uniqueness comes from the session scope, not from a
document-frequency test**, and the two must not be confused. The refusal
message also conflated "no pair covered the question" with "no shared
bridge", so those are now separate reasons with a `pairs_covering` count;
without that counter the echo diagnosis above was not reachable from the
report.

Gate: pytest 407 passed, 3 skipped, 161.80 s — held. The splice is
behaviour-neutral while the join does not fire, because `hits` is only
replaced when a unique candidate exists. Family baseline remains **0/8**;
the pass/fail threshold and the falsification condition stand unchanged.

### The ledger join: pool solved, family falsified (2026-10-28)

Third mechanism on this family, and the one that finally worked at its own
job. The pool is no longer a ranking: `live()` keeps a `session_ledger` of
what was said to him, appended at the bind site next to `session_t0`, and
`_prop_join` seeds from it before it widens. Membership is then a property
of the ledger, not of a top-k that cannot see a 40-second-old tell among
60,000 memories.

It fired. `conversation_ledger_1.json` first refused with `pool: 2,
reachable: [bell, spin], pairs_covering: 2, joins: 2, bridges: [[noon],
[noon]]` -- the hop and its bridge both found -- under
`no unique bridge join`. That was my own bug, not the mechanism's: the pair
loop ran `items x items`, so every pair was visited twice, once from each
side, and the uniqueness guard read the duplicate as ambiguity. With
unordered pairs and a stated target rule (the memory holding the question
word that comes LATER, the same word-order convention the sequence organ
already learned, not syntax) the join delivers its candidate on 6 of 8 asks.

Family result: **0/8** (`conversation_fam_band-hop-{1,2,3,4}.json`, house
down, live state read-only, `san rows changed 8115-8120`). The 8 refusals
split into two named modes, and the split is the finding:

* 6 of 8 -- `nothing he remembers has that shape`. The join fired, its
  candidate entered `hits`, and the parser arbiter vetoed it.
* 2 of 8 -- `covers 41%` / `covers 31%` (band-hop-2 and -3, second ask).
  The join did not fire: those asks' distinctive words were not both
  reachable inside the session pool.

**Falsified.** The wall is the first mode. `_arbitrate_shape` asks whether
one memory has the shape of the question's answer, and for a two-memory
join the subject lives in the memory that is *not* the answer by
construction -- so the veto fires on every correct join. That is not a bug
to patch: the arbiter is the thing that stops him confabulating, and the
design constraint on this feature was that the join proposes and the
arbiter decides. A join that only answers when the arbiter is bypassed is
not a capability, it is a way to turn the safety off.

So the honest count for band-hop: rank-based reach falsified (session edges
rank 627 of 11,555 for common words), weight subtraction falsified (a
session's own decay and consolidation move 1.4M cells, more mass than the
tells wrote), recall-seeded join falsified (`seed: 39, pool: 1`, every
rejection `who`), and the ledger join solves the pool but dies on the veto.
**A fly-scale band cannot make a 40-second-old edge outrank a 1.4M-row
corpus, and even when the edge is found by construction the answer cannot
pass an arbiter built for single-memory shape.** No fourth attempt on this
family; the scripts stay as the negative control.

Gate: pytest **407 passed, 3 skipped** (162.41 s) with the ledger and the
unordered-pair join in the tree. Behaviour-neutral on the 32-ask suite
because the join's candidate is vetoed rather than spoken -- the ledger
append is the only change that touches any path, and it writes a list.

### Next axis, design entry only (no code before design)

Retrieval is where the corpus background eats the signal, and three
mechanisms have now been spent on it. Pick an axis whose signal does not
have to beat that background:

* **A region that grows on repeated concepts.** The SAN has no notion of
  "this word has been seen a lot lately"; a growth signal keyed on
  repetition within a window is a property of the input stream, not a
  competition with 60,000 memories, so nothing has to outrank anything.
  Measurable without any ask: count the region after a fixed script and
  compare to the count after the same script with the repeats removed.
* **A second brain whose vote competes on the 8-script benchmark.** Here
  the baseline is already measured and the gate is meaningful (32/32 held
  across this cycle), so a competitor either raises the number or it does
  not -- no interpretation required.

Both are scored against state, not against a refusal message, which is what
band-hop kept making me do.

**Decided: axis (b), the competing second brain.** Why it is the measured
choice, not the aesthetic one: the 8-script suite already carries per-turn
scores (32 asks, each with a pass/fail, a filler and a parser verdict), so a
vote can be scored as state and the gate is real -- 32/32 and pytest 407/3.
Band-hop's score was a refusal message, which is why three mechanisms there
could not tell me whether they were close.

And the arbiter finding hands over the design. The house has one voice for
recall (the binder's ranking: overlap, idf, answer-type, freshness) and one
for shape (`_arbitrate_shape`), and they are **serialized**: the ranking
produces `hits`, then the shape voice takes the first hit that matches and
may veto the lot. That is exactly why a join that passes recall dies on
shape -- 6 of 8 asks, measured. So a second brain added as *another retrieval
path feeding the same arbiter* is not a test of a second brain; it is a
reproduction of that dead end. The only version that is a different claim is
a competing vote **at the same decision point**.

### Design: two brains ranking one candidate list

* **Brain A** is what exists: the binder's ranking of the recalled hits.
* **Brain B** is `understand()` -- a word's footprint plus its strong wiring,
  read from the SAN. It scores a candidate by the *meaning* distance between
  the question's content words and that candidate's filler, which is a
  different quantity from token overlap: it does not ask which memory was
  retrieved, it asks whether the answer-word is semantically near the
  question-words. It never touches `binder.recall`.
* Both brains rank the **same** candidate list. The decision is a rank-sum
  (Borda) over the two orders, and the combined order is what the existing
  arbiter walks. **The arbiter is not modified, relaxed, or bypassed** -- it
  still vetoes anything without the queried shape, which is the constraint
  band-hop died on and the reason a join could not be smuggled through here.
* B sees only A's top 8. `understand()` is called per candidate word and the
  house has measured what that costs (1,264 candidate words turned one reply
  into nineteen seconds); a shortlist keeps the vote affordable, and it is
  recorded in the trace so the truncation is visible rather than assumed.
* **Ablation:** `DROSO_SECOND_BRAIN=0` skips B and returns A's order
  untouched, so the same scripts run with and without the vote and the two
  reports are comparable turn by turn. The switch state is written into each
  report, because a comparison whose condition is not recorded is not a
  comparison.

### Threshold, stated before the run

Accepted only if all four hold:

1. pytest 407 passed, 3 skipped.
2. The 8-script suite holds **32/32** with the vote ON.
3. **Discord > 0**: at least one turn where B's top candidate is not A's.
   The switch must actually be a competition.
4. The band-hop negative control stays **0/8**. If it moves while the arbiter
   code is untouched, re-read the diff before believing the number.

### Falsification, also written before the run

Two-sided, so it cannot be won by construction:

* 32/32 breaks -> the second brain costs answers; revert.
* Discord == 0 -> B is a **mirror** of A, not a second brain. A vote that
  always agrees carries no information; the axis is falsified, not passed.
* Discord > 0 but every disagreement resolves back to A's pick, leaving the
  final choice unchanged on all 32 turns -> the vote is **decorative**; the
  rank-sum never reaches the decision. Falsified.

One limitation stated up front, because it will otherwise look like a win:
the suite is at its ceiling (32/32), so this axis cannot *raise* that number.
What it can produce is no-loss plus a measured disagreement rate, i.e. a
confidence signal the house does not currently have -- agreement between two
independent mechanisms is stronger evidence than one mechanism's verdict.
Any capability *gain* on this axis would need a probe set that is not
saturated, and that is a separate design decision, not a result to be
stretched for here.

### The second brain: falsified as built (2026-10-28)

Brain B is `_semantic_vote`: it takes A's top 8 and re-ranks them by
`understand()` cosine between the question's content words and each
candidate's *novel* words -- the words it does not share with the question,
because scoring the shared ones would only rebuild A's own metric. The two
orders combine by Borda rank-sum, ties broken toward A, and the existing
arbiter walks the result. `DROSO_SECOND_BRAIN` gates it, read per call,
default **off**: an unvalidated mechanism does not get to be the default.

Measured with `tmp_second_brain_probe.py`, the same four scripts replayed
twice in one process per condition, house down, live state read-only:

| condition | asks | passed | discord | reached the decision |
|---|---|---|---|---|
| vote OFF | 8 | **8/8** | -- | -- |
| vote ON  | 8 | **7/8** | 4/8 | 3/8 |

Two of the three acceptance conditions behaved as designed and one did not:

* **Not a mirror.** B disagreed with A's top pick on 4 of 8 asks. Falsification
  branch 2 (discord == 0) is ruled out.
* **Not decoration.** The disagreement changed the top of the list on 3 of 8,
  so the vote reached the decision. Falsification branch 3 is ruled out.
* **It cost a correct answer.** Falsification branch 1 fires: OFF 8/8, ON 7/8.

The lost turn is the whole finding. For `how is the forest`, A held the
session tell `the forest is dark`. B ranked a corpus line above it --
`in the forest roams a unicorn which does`, b_word `roams`, b_score 0.7651 --
the rank-sum promoted it, and he said the unicorn line. That is a
confabulation produced by the vote, not by the arbiter: the arbiter still
governs (on `where is the coat` the combined top was `the coat is torn` and
the shape walk recovered `the coat is on the hook` anyway, which is the
design working exactly as stated).

So meaning-nearness loses to the corpus background the same way retrieval
did, from the opposite direction. Retrieval lost because a 40-second-old
edge cannot outrank 60,000 memories; this lost because the corpus has more
words to be *near* than a two-word tell does, and a semantically rich
neighbour out-meanings a true plain one. A second brain built on similarity
-- token overlap or vector cosine -- is the same bet with a different
distance function, and both halves of that bet are now measured bad. What
would not be a similarity bet is a second brain with a different *authority*,
not a different metric: something that can say "this was said to me five
turns ago and nothing else was". That is the ledger's fact, which band-hop
already proved it can establish -- and the ledger is a session-scope
authority, not a ranking.

**Falsified as built.** The code stays in the tree, default off and inert
(pytest 407 passed, 3 skipped, 166.12 s with it present), as the negative
control for the next attempt on this axis.

**Not measured, stated plainly:** acceptance condition 2 -- the 8-script
suite at 32/32 with the vote ON -- did not run. Both suite invocations died
on argparse (`--only` takes one name and there is no `--save` flag), so the
4-script comparison above is the only evidence, and it comes from a probe,
not from the benchmark reports. The switch state is therefore recorded in
the probe output and here, not in a report JSON: converse.py whitelists the
per-turn keys it copies (`parser`, `band_walk`, `join`) and `vote` is not
among them. Next cut: either re-scope B as an authority rather than a
metric, or delete it -- and the report plumbing gets the switch field either
way.

## Brain B, re-scoped: provenance as an authority, not a metric (2026-10-28)

Both similarity bets on this axis are now measured bad, and they lost the
same way: band-hop's retrieval overlap died because a 40-second-old edge
cannot outrank 60,000 memories, and the meaning-cosine vote died because the
corpus has more words to be *near* than a two-word tell does. A second brain
that computes a different **distance function** over the same content is the
same bet twice. So B is re-scoped onto the thing that is not a distance
function at all.

**What B votes now: provenance.** For each candidate in A's shortlist, one
bit -- `who == "you"` and `when >= session_t0`, the same two fields the
ledger join already used to establish which memories came from this session.
B's order puts every session-bound memory ahead of every corpus memory, with
A's order as the tiebreak inside each group. It reads no weights, no vectors,
no overlap. It answers a different question: not *which memory resembles the
ask*, but *was this said to me here*.

**Why this can disagree with A, which is the whole point.** A's key is
`(overlap, fresh, expected, idf, novel)` -- overlap FIRST, freshness only as
a tiebreak after it. The house logged the consequence at
`neural_language.py` in the comment above that sort: failure (2) was "the
corpus prior beat the teaching outright", and grading freshness fixed it only
partly, because a corpus memory that shares more words still outranks a
session tell that shares fewer. B's order is that priority inverted. Two
different orderings over one list, from two different kinds of fact -- that
is a competition, not a reranking of the same score.

**The specific mirror risk, stated before the run.** If A's overlap-first
order already puts the session tells on top for every ask in the suite, then
B's order equals A's, discord is 0, and B is a mirror wearing a different
costume -- falsified, exactly the branch written down last time. This is the
most likely way this cut fails and it is not a surprise if it happens.

**Same contract as before, unchanged:** both brains rank the SAME candidate
list; the decision is a Borda rank-sum with ties broken toward A; the arbiter
walks the result and is **not** modified, relaxed or bypassed -- it still
vetoes anything without the queried shape. `DROSO_SECOND_BRAIN` still gates
it, read per call, default **off**.

**Plumbing gap closed:** `vote` is added to the keys converse.py copies into
the per-turn records (warm and cold), so the switch state and the discord
counts land in the report JSON rather than only in a probe's stdout. Last
turn's promise, met this turn.

### Threshold, stated before the run

1. pytest 407 passed, 3 skipped.
2. **No regression**: every turn that passes with the vote OFF still passes
   with the vote ON, in the probe (all 7 fresh scripts, warm) and in the
   benchmark suite run with the vote ON.
3. Discord > 0 on the suite asks -- B must disagree with A at least once.
4. Discord must reach the decision at least once (`order_changed` > 0), or B
   is decoration.
5. The band-hop negative control stays 0/8 **unless** a promoted answer is
   the correct two-hop join, in which case re-read the diff and confirm the
   arbiter is untouched before believing the rise.

### Falsification, also stated before the run

* Any previously-passing turn flips to fail -> B costs answers -> revert.
  (This is the branch the meaning-cosine version died on: 8/8 -> 7/8.)
* Discord == 0 -> mirror -> falsified.
* Discord > 0 but `order_changed` == 0 everywhere -> decoration -> falsified.
* Band-hop rises on answers that are not the correct joins -> the vote is
  manufacturing confabulation -> falsified, and the control did its job.

What counts as a real gain here, said plainly so it is not stretched for:
provenance-first can only raise a score where a corpus memory currently sits
above a session tell and the arbiter accepts the tell. On the fresh suite
that is not supposed to happen -- the freshness term already catches it --
so the honest expectation is **no loss plus measured disagreement**, with the
band-hop family as the only non-saturated target where a rise is possible.
If band-hop stays 0/8 and the suite holds, this axis produces a confidence
signal and nothing more, and the log will say that rather than calling it a
capability.

### Provenance B: falsified as a mirror (2026-10-28)

Ran against the thresholds above, house down, live state read-only.

| measurement | vote OFF | vote ON |
|---|---|---|
| probe, 22 asks (7 fresh + 4 band-hop scripts) | **14/22** | **14/22** |
| band-hop negative control (8 asks) | 0/8 | **0/8** |
| full suite, 32 turns | 32/32 (prior cut) | **32/32** |
| pytest | -- | **407 passed, 3 skipped, 166.27 s** |

Suite report with the vote ON: `state/fitness/script_benchmark_20261028_034017.json`,
`pass: true` on 32 turns, `pass: false` on zero, overall 1.00 warm / 1.00 cold.

**Conditions 1, 2 and 5 hold. Condition 3 fails, and it fails in the direction
that matters: `discord = 0` on every turn, at probe scale (22 asks) and again
at suite scale (32 turns).** Condition 4 therefore cannot hold: with no
disagreement there is nothing to reach the decision.

This is not a vote that lacked evidence. **18 of the 22 probe asks fired with
a genuine provenance contrast** -- the shortlist held both session-bound and
corpus memories, `n_bound` strictly between 0 and the shortlist size -- and
in all 18, provenance-first picked the same memory overlap-first had already
picked. Only 7 suite turns reported `no provenance contrast in the shortlist`
and abstained. So the case B was built to catch, a corpus memory sitting
ABOVE a session tell, does not occur in A's shortlists on any probe in this
house.

Which means the freshness term is already doing the job, and doing it well
enough that inverting the priority order changes nothing. The comment above
A's sort records failure (2) as "the corpus prior beat the teaching outright"
-- that failure is real, and it is fixed, but it is fixed by the *second*
term of a lexicographic key, not by the first, and my design entry assumed
that left the first term exposed. It does not: on every ask measured, the
memory with the most shared words is also the session tell. There is no
residual for an authority to correct.

`how is the forest` is the cleanest side-by-side. The meaning-cosine B broke
it (8/8 -> 7/8, promoting `in the forest roams a unicorn which does` over the
true `the forest is dark`); provenance B agrees with A there and the suite
passes it. A second brain that never disagrees is not harmless by definition
-- it is *uninformative*, which is worse for the axis, because it means the
architecture has one voice at this decision point no matter how many ranks
are computed.

**Falsified: mirror.** Both variants of axis (b) are now closed, by opposite
branches of the same pre-written test: the metric cost a correct answer, the
authority never disagreed. Code stays default-off and inert in the tree as
the negative control.

**The plumbing gap from last turn is closed and it earned its keep.** `vote`
is now copied into the per-turn records (warm and cold) and appears on all 32
turns of the report, carrying the switch state per turn. That is how the
discrepancy below became visible at all:

**Unexplained, not papered over:** the report has 32 `vote` fields and
`"on": true` on only **21** of them, though the whole run was launched with
`DROSO_SECOND_BRAIN=1`. 11 turns recorded the switch as OFF from inside a
process that should have had it ON. The likely shape is a per-script or
per-phase child that does not inherit the environment, but that is a
hypothesis, not a measurement. Until it is resolved, the 32/32 above is
"32/32 with the vote on for 21 of 32 turns", which is still a pass on the
no-regression condition and still cannot produce discord on the 11, so it
does not change the mirror verdict -- it does mean the suite number is not
yet the clean vote-ON gate I claimed it was. Next cut: find which turns carry
`on: false` and why, before any further ablation is run through this harness.

### The switch was never lost: that claim was mine, and it was an artifact

Audited the same report properly (`tmp_vote_audit.py`, walking
`rows[].warm.turns` / `rows[].cold.turns` instead of grepping the file):

| per-turn vote state, suite run `..._034017` | count |
|---|---|
| `on: true` | **21** |
| `on: false` | **0** |
| no vote record at all | 31 (20 tell turns + 11 refusal-path asks) |

Among the 21: 11 fired with a real provenance contrast, 7 abstained for "no
provenance contrast in the shortlist", 3 for "one candidate, nothing to rank".

**There is no environment bug.** `subprocess.run` in script_benchmark.py:52
passes no `env=`, so the child inherits it, and converse.py never reads or
scrubs `os.environ`. The 11 turns I said "logged the switch off" were 11
turns where `on` was never written at all, because the refusal paths return
before the ranking: `answer()` has five `{"answered": False, ...}` returns
(lines 2556, 2624, 2674, 2688, 2783) and the vote is stamped only on the
answered path (2776). My count of "32 vote fields" was the same key appearing
twice per answered turn -- once in the per-turn record, once in the `_clean`
lift -- and 32 happened to look like the turn count.

So the defect was in the report's legibility, not in the harness, and the
claim in the commit message was wrong. Fixed at the record sites: a turn
without a ranking now carries `{"reached": false}` instead of silence, plus
`switch_env` read from the child's own environment, so absence and off can
never again be conflated, and a genuine env loss would show as
`switch_env=1` next to `on: false`. Re-running the suite with the vote ON to
confirm that on a fresh report.

**What this does to the gate:** the vote-ON 32/32 is measured for the 21
graded asks that reach a ranking and structurally inapplicable to the 11 that
refuse -- a refusal has no candidate list to re-rank, so no second brain of
any kind can act on it. The mirror verdict is unaffected and in fact
strengthens: 29 votes fired with real contrast across probe and suite
(18 + 11), and not one of them disagreed with A.

### Axis (b) is closed: that decision point has one voice, logged as exhausted

Both variants of a second ranking at the recall/shape decision are now
falsified, by opposite branches of the same pre-written test: the **metric**
cost a correct answer (8/8 -> 7/8, promoting a corpus unicorn line over the
true tell), the **authority** never disagreed at all (0 discord in 29
contrast-bearing votes). The finding is architectural, not about rankings:

> A's key is `(overlap, fresh, expected, idf, novel)`. The freshness term
> already puts session tells above the corpus prior on every ask in this
> house, so the case a second ordering exists to correct -- a corpus memory
> sitting above a session tell -- does not occur. A second ranking cannot be
> informative at a decision point where the first ranking is already right
> for the reason the second would give.

A third variant (a different distance function, a different priority, a
different vote) is the same bet a third time. **This decision point is
logged as exhausted for axis (b). Do not revisit it.** The mechanism stays in
the tree, default-off and inert, as the negative control.

## Regions that grow on recurrence (2026-10-28): the axis where nothing has to outrank anything

The lesson of the closed axis is that ranking problems are saturated here:
there is always one right candidate and A already picks it. So the next axis
is chosen to have no competitor at all. This is a **structural** organ: it
changes his anatomy, and it is scored as **state**, not as an answer. No
arbiter, no refusal message, no corpus competition, no candidate list.

**The claim to test:** a concept that recurs in the session stream should leave
a *place* behind, not just a stronger weight. Repeated teaching of the same
concept grows a distinct region; the same stream with the repeats removed
grows none. The measurement is the delta in his own anatomy between two runs
of one script.

**Substrate, verified in the code rather than assumed:**
- A word is `{"word", "kc": [...], "pool": int, ...}` (neural_language.py:665)
  -- a KC pattern plus the compartment it won. `stats()["pools_used"]`
  (3592-3603) already reports pool -> word count, so compartments are the
  nearest thing this house has to regions, and today they are a byproduct of
  which pool a word happens to win, not something allocated on purpose.
- The growth primitive already exists and is already used: `wire_pool(
  kc_nodes_of_code(code), pool, k_per_pre=4)` at 647, whose comment calls it
  "activity-dependent sprouting -- the word's KCs are firing and this pool is
  the compartment being considered, so give them synapses into it". A region
  organ should ride that, not invent an allocator.
- The recurrence signal already exists: memories carry a `count` (541), and
  `recent_words` is kept. So "recurs past a threshold" is a read of state the
  house already maintains, not a new statistic.
- Mass is countable today: `san_real` is `count_nonzero(san_w >= 1e-6)` (545)
  -- nonzero cells in the Hebbian matrix. Live census at last check: 573,424
  cells, 1,446,352 after the consolidation drain.

**Baseline, and the confound it exists to catch.** Today there are zero
regions by the definition above: nothing allocates a compartment on account of
recurrence. But repeats are not inert in the current anatomy either -- every
replay strengthens `san_w` cells, so a run with repeats will show MORE mass
than a run without, and that difference is ordinary Hebbian growth, not a
region. The baseline instrument must therefore run both variants and report
region count and mass separately: **if the only thing that moves is cell
count, the organ has not been built, it has been described.** The number the
organ must beat is the with-repeats-minus-without-repeats cell delta produced
by the current anatomy alone.

**Threshold, stated before the code:** a concept recurring >= 3 times in one
session allocates or grows exactly one region. The scored pair is one script
run as written, and the same script with the repeated tells removed (same
concepts, each said once, same turn count where possible). Pass requires:
regions > 0 in the repeats run, regions == 0 in the de-repeated run, and the
region mass delta distinguishable from the plain cell delta above.

**Falsification, also stated before the code:**
- Both variants produce the same region count -> recurrence is not reaching
  anatomy -> falsified.
- Regions "grow" but the only measurable change is generic cell count, with
  no dedicated compartment attributable to the concept -> it is a weight bump
  wearing the word "region" -> falsified. (This is the likely failure, and it
  is the reason the baseline is measured first.)
- The 32-turn suite moves at all -> a structural organ is leaking into the
  decision point -> revert. This organ must be **invisible to answers**: its
  only legitimate output is a change in state.
- pytest must stay at 407 passed, 3 skipped.

**Order of work:** baseline instrument first, its numbers logged, then the
organ, then the same instrument re-run against it. The design entry is this
entry; no organ code is written until the baseline is a number and not an
assumption.

### The baseline, measured (2026-10-28): the confound is bigger than the signal and points the wrong way

Instrument `tmp_region_baseline.py`: two variants of ONE script
(`accumulation_fresh`), each replayed into its own house copy, live state
untouched. Recurrence removed by construction -- the recurring subject
replaced by a different known subject in each tell, same tell count, same
asks.

| | with recurrence (`coat` x3) | de-repeated (scarf / lantern / kettle) |
|---|---|---|
| san cells before -> after | 1,454,608 -> 1,449,928 | 1,454,608 -> 1,450,460 |
| **cell delta** | **-4,680** | **-4,148** |
| concepts recurring >=3 | 1 (`coat`) | 0 |
| pools used | 13 -> 13 | 13 -> 13 |
| largest pool, words | 1,187 -> 1,187 | 1,187 -> 1,187 |
| vocabulary | 11,555 -> 11,555 | 11,555 -> 11,555 |
| asks answered | 2/2 | 1/2 (its coat tell no longer exists) |

Three findings, all obtained before any organ code -- which is what the
baseline was for:

1. **A session loses cells.** Both variants *lost* mass. 4,148 cells fell
   below 1e-6 with no recurrence at all, because decay acts on the whole
   matrix every beat and a five-turn session's writes do not restore it. The
   recurrence-attributable part is therefore **-532 cells**: the with-repeats
   run lost *more* than the de-repeated run, the opposite of the direction an
   organ is supposed to add. The confound is ~8x the signal and inverted.
2. **What that changes is the metric, not the threshold.** The pass condition
   "region mass delta distinguishable from the plain cell delta" now has a
   measured meaning: the plain cell delta is **-4,148 per 5-turn session**, so
   a region signal can only be a **local, decay-insensitive count** -- cells
   attributed to a named compartment -- and never a difference of global
   totals. An organ written against the global census would be buried by
   decay before it could be seen. Threshold (>=3 recurrences -> one region),
   the scored pair, and the falsification conditions stand exactly as written.
3. **Pools are not regions -- a sub-claim of the entry, falsified.** The entry
   guessed pools were "the nearest thing this house has to regions". Measured:
   13 pools hold 11,555 words, the largest holding 1,187. A compartment shared
   by ~900 words on average cannot carry a per-concept region. The substrate
   has to be the SAN index space (footprints, 12 cells per word) or a
   dedicated allocation, not the pool.

The de-repeated variant answering 1/2 is the manipulation working as declared:
remove the recurrence and the concept's tell genuinely disappears from recall.

### The vote-ON gate, closed: the stamp works, and the environment was never lost

The re-run's aggregate report had not landed when this was checked (the suite
writes `script_benchmark_*.json` only at the very end), so the gate was closed
on the evidence the run had already produced -- its own per-script reports,
`state/fitness/conversation_script_<name>_<phase>.json`, whose
`benchmark.turns` carry the same records. **16 graded asks from the four
completed scripts** (reference, accumulation, discrimination, role_chain; warm
and cold):

| check | result |
|---|---|
| graded asks carrying `on: true` **or** explicit `{"reached": false}` | **16/16** |
| silent absences (the ambiguity that produced my wrong claim) | **0** |
| `switch_env == "1"` on every graded ask | **16/16** |
| answered asks / refused asks | 11 on:true / 5 reached:false |

Refusals are exactly the `reached: false` turns, all in cold phases; every
answered ask carries a real vote with the switch on. The same query over the
**previous** cut's reports (`*_fresh`, and the older switch_back / override /
session_context / where_kept files) returns `switch_env = None` and bare
absence -- which is precisely the legibility failure this fixed, and it is why
my regex count read as "11 turns logged the switch off".

**Acceptance item (vote-ON gate): MET**, and closed in full the following
turn. The full run died at the turn boundary -- process gone, log stopped at
`=== switch_back ===`, no aggregate report written -- so the remaining four
scripts were run in **two slices**, each comfortably inside the shell's 600 s
cap, with `DROSO_SECOND_BRAIN=1` set for the whole run:

| report | scripts | graded | on_true | reached_false | no_record | on_false | switch_env=1 | failed turns | overall |
|---|---|---|---|---|---|---|---|---|---|
| `script_benchmark_20261028_043639` | switch_back, override | 8 | 6 | 2 | **0** | **0** | 8/8 | 0 | 1.00 / 1.00 |
| `script_benchmark_20261028_044350` | session_context, where_kept | 8 | 4 | 4 | **0** | **0** | 8/8 | 0 | 1.00 / 1.00 |

Add the 16 asks the killed run had already written per-script (four scripts,
verified above) and the suite's **full 32 graded asks** are accounted for:
every one carries a vote with `on: true` or an explicit `{"reached": false}`,
every one reads `switch_env == "1"`, and **not one turn records the switch
off** -- the statement that was missing when I made the wrong claim. Both
audits print `ACCEPTANCE ITEM: MET`. No regression either: warm 1.00, cold
1.00, delta 0.00 in both slices, matching the pre-stamp 32/32 run.

The instrument is `tmp_vote_audit.py <report>`; it walks `rows[].warm.turns`
and `rows[].cold.turns` (graded kinds only), tallies on_true / reached_false /
no_record / on_false, checks the environment as the *child* sees it, and
asserts the item instead of asking me to read a count.

Two process facts worth keeping, both learned the hard way this turn:
the background-job registry does **not** survive across turns -- `bg_output`
on a previous turn's id returns "no background job", and that run was killed
mid-script-5, so a suite must be started and finished, or its per-script
reports read, inside one turn; and the shell caps a command at **600 s**, so
long waits must not be slept in-shell -- poll with `bg_output`, or run the
suite `--only a,b,c` in slices.

### Second baseline measurement (same day): existing cells cannot express a region, at any granularity

`tmp_region_local.py` asks the question the organ actually hinges on -- is a
**local** mass metric measurable? -- by counting, per concept, the nonzero
cells inside its own footprint block (`_fp_idx` gives 12 cells, so a block is
144 pairs) before and after each variant. Asks were held identical across the
two runs, which makes the de-repeated run a clean control: `coat` is **asked
but never told** there.

| concept | times told | block_nz before -> after | delta |
|---|---|---|---|
| coat (repeated run) | 3 | 8 -> 122 | **+114** |
| coat (de-repeat run: asked, never told) | 0 | 8 -> 88 | **+80** |
| scarf | 1 | 0 -> 70 | +70 |
| lantern | 1 | 14 -> 66 | +52 |
| wet (asked in both) | 1 | 4 -> 66 | +62 |
| torn | 1 | 4 -> 34 | +30 |
| hook | 1 | 2 -> 2 | 0 |
| kettle | 1 | 0 -> 0 | 0 |

Two numbers settle it:

1. **Recurrence is not the driver.** Three tells plus two asks give +114;
   the two asks alone give +80. So the three tells are worth about **+34 net**
   -- *less than what a single mention of any other concept buys* (+52 to +70).
   Being mentioned once moves the local block as much as being mentioned three
   times. A region defined as "more nonzero cells in the concept's block"
   would be measuring exposure, not recurrence, and would fire on the
   de-repeated control run too -- which is falsification branch 1 of the entry
   ("recurrence is not reaching anatomy"), reached before the organ exists.
2. **The block saturates.** coat's block ended at **122 of 144 possible
   cells**. A handful of writes fills a 12-cell footprint, so there is no
   headroom left for "recurred >= 3" to register in, and a fourth tell could
   not be distinguished from a third.

So the baseline's answer, stated before any organ code as required: **no count
of existing cells -- global or local -- can express a region.** Global is
decay-dominated (-4,148 cells per 5-turn session against a -532 recurrence
term), local is exposure-dominated and saturating. The threshold (>=3
recurrences -> one region), the scored pair and the falsification conditions
are unchanged; what the numbers force is the substrate. A region must be a
**newly allocated compartment with its own capacity**, written only by its own
concept's consolidation, starting at zero -- not a window onto the
hash-addressed footprint space, which is shared by collision and full of other
concepts' activity. That is the design constraint the organ has to be written
against, and it is why the allocation, not the counting, is the hard part
here.

## Design: the region allocator, written against the measured numbers (2026-10-28)

Design entry first, code after -- house rule. This entry exists because both
baselines above ruled out the substrates that were available, not because a
region sounds like a good idea.

**What is ruled out, and therefore what this is not.** Not a window onto
`_fp_idx` footprint space (saturating at 122/144, and +80 cells for a concept
that was only *asked*), not a difference of global `san_real` (-4,148 per
5-turn session from decay alone), not a pool (13 compartments holding 11,555
words, largest 1,187). Any organ built on those would be an exposure counter
wearing the word "region".

**Substrate: a separate, persisted, addressable matrix.** `region_w`, shape
(256, 512): 256 blocks, one per concept, 512 cells each, 131,072 cells total
against `san_w`'s 1.45M real cells -- deliberately small, because it is meant
to be auditable, not to be a second brain. A block is **allocated**, not
hashed: first free row, recorded in a `region_ledger` mapping concept -> row.
A concept that never reaches the threshold never gets a row, so its region
mass is exactly zero, not "zero minus somebody else's noise".

**Trigger (unchanged threshold):** a concept recurring **>= 3** times in one
session stream allocates one block. Below three, nothing is allocated.

**Write rule:** on each recurrence, the concept's co-activation for that turn
(the words it appeared with) is written into *its own block only*, at strong
weight, capped at the existing 4.0 ceiling. No corpus concept writes into
another concept's block; nothing in `san_w` is redirected.

**Read rule for this cut: none.** Regions are allocated, written, persisted
and measured -- and are not consulted by ranking, recall or answer selection
at all. That is the lesson of the band walk, which was demoted to a recorded
vote for exactly the reason that a structure which is not read cannot break
anything: the no-regression gate should be *trivially* satisfiable, and if it
is not, that is a defect in the organ, not a feature. A read path is a later
cut, gated on this cut's pass pair.

**Durability, computed rather than hoped.** Decay is 0.995^10 = 0.951110 per
fire, so the fires needed to carry a cell down to the 1e-6 floor are:

| written at | fires to reach 1e-6 |
|---|---|
| 0.3 (consolidation band) | 251.6 |
| 1.0 | **275.6** |
| 2.0 | 289.4 |
| 4.0 (cap) | 303.3 |

A block written at 1.0 therefore survives **276 fires** before falling
under that floor; the 4,148 cells that crossed during the baseline session
were already near the floor, not freshly written. A block re-stamped by recurrence therefore keeps its
nonzero count across sessions while the corpus tail drains -- which is the
decay-insensitivity the metric needs, and it comes from attribution (only my
concept writes here), not from writing strong.

**Cost, stated plainly: the save surface grows from seven files to eight.**
`save_state(force_san=True)` currently moves seven (`language_state.json`,
`.san.npz`, `.seq.npz`, `.seq.slots.json`, `.cortex.npz`, `.cortex.meta.json`,
`.cortex.facts.json`). `region_w` plus `region_ledger` add an eighth and a
ninth sidecar. This has been wrong in this log before, so it is a test, not a
note: allocate a region, save with `force_san=True`, restart, and the block
must still be there with its count intact.

**Pass pair, on the same two variants as the baselines:**
- repeated (`coat` x3): regions allocated **>= 1**, block nonzero count > 0;
- de-repeated (each concept once, `coat` never told): regions allocated
  **exactly 0**, including `coat`'s block staying at zero cells.

**Falsification, written before the code:**
1. The de-repeated control allocates **any** block -> the trigger is exposure,
   not recurrence -> the organ is falsified and removed.
2. The 3-tell block's nonzero count does not exceed the largest single-mention
   growth measured above (**+70**, `scarf`) -> the compartment is another
   exposure counter -> falsified.
3. The suite is not 32/32 warm and cold with regions allocated -> the organ is
   not inert -> revert, no renegotiation.
4. After a restart, a saved block's count changes -> the eighth file is not on
   the save surface -> the organ does not survive a restart and is not real
   anatomy.

**What this buys, honestly: nothing yet.** A region that is never read changes
no behaviour. What it does buy is a structure where "this concept has a place
in the brain" is a fact with a number attached, testable in both directions,
which is the precondition for ever routing recall through it. If the pass pair
fails, the axis closes here and the word "region" stops being used in this
house.

### Regions: built, restart-tested, and FALSIFIED on both conditions (2026-10-28)

The organ was written to the entry as frozen -- `region_w` as its own
(256, 512) float32 matrix, an allocator handing out the first free row, trigger
at **3** recurrences, writes only into its own block, **no read path** -- and
hooked at the one place testimony enters the brain (`live()`, beside the
session ledger, gated on `speaker == "you"` so the 21,969-word library cannot
feed it). The threshold was never adjusted, the capacity was never adjusted,
and nothing was tuned to make the pair pass.

**Condition 4 (restart) PASSED, and it is the reusable result.** Two separate
processes, the second reading the files the first wrote:

| | before restart | after restart |
|---|---|---|
| blocks allocated | 2 | 2 |
| rows used | 2 | 2 |
| nonzero cells | 137 | **137** |
| mass | 262.0 | **262.0** |

`load_state()` returns `regions: {loaded: True, allocated: 2, cells: 137,
rows: 2, mass: 262.0}`, block-for-block identical, from a
`language_state.region.npz` of **992 bytes**. The save-surface claim was
measured rather than asserted, and it came out *wrong in the entry*: the
directory holds **nine** `language_state*` files after a forced save, not
eight, because san and region use `with_suffix()` (which drops `.json`, giving
`language_state.san.npz`, `language_state.region.npz`) while sequence and
cortex append to the full name (`language_state.json.seq.npz`,
`.cortex.npz`, `.cortex.meta.json`, `.cortex.facts.json`, `.cortex.npz.err.npy`,
plus the JSON itself). That asymmetry predates regions; the list in the design
entry was counted from memory and was wrong, which is why it is now a test.

**The pass pair FAILED. Both falsification conditions fired.**

| variant | allocated | counts | blocks |
|---|---|---|---|
| repeated | **2** | coat 5, **is 5**, wet/torn/hook/on 1 | coat row0 **68 cells** mass 131.0; **is** row1 69 cells mass 131.0 |
| de-repeated | **1** | **is 5**, coat 2, seven words at 1 | **is** row0 80 cells mass 131.0 |

- **Condition 1, FIRED:** the de-repeated control allocated a block. The
  trigger correctly required three recurrences -- `coat` sat at 2 and got
  nothing -- but what recurred five times was the **copula**. "is" appears in
  every turn of both streams. Recurrence of a function word is not recurrence
  of a concept, and the organ has no way to tell them apart.
- **Condition 2, FIRED:** `coat`'s block reached **68 cells** against the
  frozen bar of **>70** (the largest single-mention growth measured in the
  earlier baseline). Three tells of a genuinely rare concept bought *less*
  local mass than one mention bought in the old substrate.

**The mechanism that let "is" through is a fact about the house, and worth
more than the region idea.** For the concept test I reused the law the house
already has rather than inventing a number: `df * 4 <= n_mem`, the distinctness
rule the provenance vote uses (`organs/neural_language.py:2617`). It **passed
"is"**. Because `df` there is `len(binder.stem_rows(w))` -- **subject-position
frequency, not word frequency**. "is" is almost never a proposition's subject,
so by that law a copula is "distinctive". And `_speakable()` is a *mouth* test
(len >= 2, alphabetic), which passes "the" and "is" as happily as "coat". So
this brain has **no function-word filter in the sense I assumed it did**, and
any future organ that wants "concept" must build that predicate rather than
borrow one that means something else.

**What this falsification does and does not say.** It does not say allocated
compartments cannot work: the allocator, the capacity, the eighth file and the
restart across processes all measured clean. It says that **"a word recurring
>= 3 times in a stream" is not a concept-identifying predicate**, and that a
compartment written only by three tells does not beat the exposure bar the
frozen conditions set. Both are failures of the trigger's *subject* and of the
*growth*, which is exactly what conditions 1 and 2 were written to catch.

**The code is out of the tree** (`git checkout -- organs/neural_language.py`,
verified by an unmodified `git status`), not left inert in the live brain: a
falsified organ that allocates rows for "is" and writes a sidecar on every save
is a cost with no measured benefit, and this house deletes what it falsifies.
The instrument that proved it stays as `tmp_region_organ.py` (write / read /
pair).

**Deviation from the requested order, stated rather than hidden:** the 32-ask
suite (step 5) was **not** run. Its purpose was to prove the organ invisible to
answers; with the organ reverted that question is moot, and 15 minutes of
house-down time would measure nothing that bears on the falsification. pytest
was likewise not re-run, because the tree after the revert is byte-identical to
`c654493`, which passed 407/3 at 161.70s earlier this turn.

Two questions go to the next design entry, before any code -- and neither is
licence to move a number now: (1) what makes a word a concept in this house
without inventing a frequency threshold tuned to a script (the measured
candidate is the asymmetry already logged: a word whose tell-write exceeds its
corpus background, which is what separated `spin`/`owl`/`salt` from
`bell`/`noon`); (2) whether a >70-cell bar is sound at all for a compartment
that starts empty, given that the +70 it is compared against came from a
substrate carrying 144 cells of corpus wiring behind it. If that comparison is
unsound, the entry must say so as a finding about the *condition*, not quietly
re-score against a new one.

### The concept predicate, measured standalone: FALSIFIED, and the wrong thing was named (2026-10-28)

The candidate the previous entry left behind -- **"a tell-write that exceeds its
corpus background"** -- was built as a measured artifact and scored over the four
band-hop ask-streams with **no organ attached**, against a hand list written into
`tmp_concept_probe.py`'s docstring *before* any number was computed: concepts
`spins, owl, salt` (the rare side of the logged asymmetry), not-concepts
`bell, noon` (the common side of the same logged pair) and `is, the` (the function
words that actually allocated blocks in the region organ).

**The first instrument was broken, and is reported as broken rather than
quietly replaced.** It measured each word's strongest edge anywhere in its
footprint rows: maxima came out 2.2--4.0 against a cap of 4.0 -- saturated corpus
edges, not the ~0.048 p99 the log names -- and *every* excess came out negative,
because decay fires on wall-clock during the 35 s build and shrinks the whole
matrix ~5 % while two tells bind. It was measuring the house cooling down, not a
write. The re-score measures on the cells the tell actually writes: the pair
blocks between the word's footprint and each co-told word's footprint, pre and
post pooled over the same blocks in the same order, where decay is a uniform
-4.9 % against writes of +0.1 to +0.6.

| word | hand class | background | write | excess | fires? | `df` baseline |
|---|---|---|---|---|---|---|
| spins | CONCEPT | 0.8491 | 1.1549 | **+0.3058** | yes | df=4 distinct |
| owl | CONCEPT | 1.0897 | 1.5966 | **+0.5069** | yes | df=2 distinct |
| salt | CONCEPT | 3.7331 | 3.5506 | -0.1825 | **no** | df=12 distinct |
| bell | not | 1.0664 | 1.0142 | -0.0521 | no | df=41 distinct |
| noon | not | 1.4393 | 1.8181 | **+0.3788** | **yes** | df=25 distinct |
| the | not | 3.6966 | 3.7140 | **+0.0174** | **yes** | df=22383 furniture |
| is | not | *never occurs in the four streams* | | | | |

**PRECISION 0.500, RECALL 0.667** (TP=2 spins/owl, FP=2 noon/the, FN=1 salt,
TN=1 bell). `is` is reported **UNOBSERVED** and not counted a true negative: a
word that was never presented cannot be scored, and counting it is how a fake
pass gets manufactured. The comparison baseline the entry asked for is worse
news -- the `df * 4 <= n_mem` law the region organ borrowed scores **P=0.600
R=1.000** on the same six observed words, so the new predicate is **beaten by
the law it was meant to replace**, and neither separates.

**Why it fails is structural, not a threshold.**

- **The statistic is bimodal by construction.** For every non-firing word,
  `post = pre x 0.9512` to four digits (bell 1.0664→1.0142, drum 1.0536, salt
  3.7331→3.5506) -- exactly one decay fire and no write above the maximum. So
  the test answers one question: *was the largest touched cell one of the cells
  this tell writes?* That is a coin about which cell happens to be biggest.
- **Headroom under the cap decides, not concept-hood.** `salt`, a hand-listed
  concept, sits at background 3.7331 -- nearly saturated -- so no write can top
  it and it reads as furniture; `the` sits at 3.6966 and *did* top it (3.7140),
  so the definite article reads as a concept. The predicate measures how much
  room a word has left under 4.0.
- **What leads the ranking is novel *pairing*, not concept:** `sings` +0.62,
  `drinks` +0.54, `dew` +0.50, `calls` +0.48 -- the fresh pairings of the other
  three scripts -- and `noon` fires because "the bell rings at noon" pairs it
  newly with `bell`/`rings`.
- **It flips with the sentence.** `the` and `at` both vote 2/4 across the four
  streams. A predicate that names a property of the word cannot depend on which
  word it is standing next to.

So **the wrong thing was named.** The region organ stays dead until the
predicate is right: it is **not wired**, the pass pair was **not** run, and no
capacity or threshold moved. The honest description of what remains unowned is
narrower than the entry that opened this cut: the house still has no predicate
that separates a concept from furniture, and the candidate that was measured is
worse than the one already in use.

### Condition 2's `>70` bar was unsound as written, and is withdrawn -- not re-scored

The pass-pair failure on condition 2 is **not evidence about regions**. The bar
compared an **empty compartment** -- `region_w` at zero, written only by three
tells -- against **+70 cells measured on a substrate carrying 144 cells of
corpus wiring behind it**. Those are not the same quantity: the +70 was growth
*on top of* a block that already had 144 cells of history to amplify into, and
the compartment that scored 68 had nothing but the tells. No empty compartment
that starts at zero and is ever written only by testimony can be compared
against that number, so the 68-vs-70 miss measured the bar, not the organ.

**What a sound condition would be:** a *paired control on the same block* --
identical stream, concept told three times versus told once, both into copies
from the same state, measuring the difference in nonzero cells **within the
allocated compartment**, so the corpus background cancels instead of setting the
scale. The quantity to beat is "does recurrence in a compartment grow it beyond
a single mention in the same compartment", never "does it beat what a
corpus-wired substrate grew".

It is **withdrawn as unsound, not re-scored**: no new bar was substituted this
turn, because a bar written after seeing the number it must clear is the one
thing this house has agreed not to do. The replacement goes into a design entry
before the code.

### Meta: fourth consecutive cut ending in a falsification with a named precondition

Knowledge up, capability flat. Each of the four closed a specific claim on
evidence -- the global-mass signal, the pool signal, `_speakable` as a concept
filter, and now tell-excess as a concept predicate -- and each named, in
advance, the condition that would kill it, and died on it. That is real
progress about what this brain does and does not contain, and it is **zero
progress in what the brain can do**. The streak is not a virtue and not an
excuse. What would break it is a cut that ships a working capability, and the
predicate is the gate on all of them: until a concept can be told apart from
furniture by something that does not depend on which word it is standing next
to, regions, recurrence-tracking, and any organ built on either stay unbuilt.

## The gate was saturated: a heldout hard set, and its baseline (2026-10-28)

Five cuts produced knowledge and zero capability, and the reason is instrumental. The only capability gate in the house (tools/scripts.json, 32 graded asks) reads **32/32 at 1.00/1.00**; a saturated instrument cannot register an improvement of any size, so nothing built after it could show up. The instrument was fixed before more anatomy.

**Harness:** tools/heldout_eval.py + tools/scripts_heldout.json -- six scripts, **24 graded asks**, each in a FRESH house copy (build() re-points persistence, live state read-only, beats=0). **No judge of any kind**: four mechanical checks -- an answer slot (whole word), must_contain plus order (strictly increasing subsequence), a forbid list, and require_refusal, which grades the state invariant (did i ever tell you about the moon) by whether he asserted anything at all. The forbid lists are what make it ungameable: blurting a related word fails.

### BASELINE: 4/24 = 0.167

count **0/8** | order 2/8 | invariant 2/4 | mouth **0/4**. A low number was the point; 1.00 here would mean the tasks were too easy and must be replaced. This measures the reach of the instrument, not how much Droso knows.

### FAILURE MAP (from the reply trace fields)

recall 8 | gating 4 | shape_arbiter 4 | mouth 2 | engine_error 2

- **count 0/8, every one a recall miss with a coverage number attached**: "the closest memory of his covers 45/49/49/58/42 pct of the question". The coverage floor refuses before any counting could happen. The brain has **no counting mechanism at all**, and the gate never gets the chance to be wrong about one.
- **gating 4** -- "it understood but did not feel like speaking". Recall **succeeded**; the reply gate declined. These are not memory failures, and the first classifier nearly counted them as such.
- **shape_arbiter 4** -- "nothing he remembers has that shape" with parser verdict veto, on the ordering ask and on the two-hop ask (what does the thing the frost bites hold): the closed band-hop family showing itself in a fresh script.
- **mouth 2** -- two different asks both answered with the single word **sold**, source = meaning resonance: the ordering ask and the exact-repeat ask. The purest test of the mouth produced one word, and the same word twice.
- **engine_error 2** -- the two conjunction asks raise **KeyError: proposition** in answer(), organs/neural_language.py:2803 (role_of(best["proposition"], ...)). Session.ask keeps the exception in turn["error"] and returns an empty reply, so **a crash looks exactly like a silent recall miss in the trace** -- no reason, no source, no verdict. The first run of this map labelled both recall; the classifier now reads turn["error"]. The crash is NOT fixed this turn.

**Slot extraction is absent.** Asked "what turns twice" he echoed the whole tell (the copper bell turns twice) although the arbiter had already recovered the right filler (recovered_filler = bell, verdict = agree): the correct word was in hand and the mouth said the sentence instead. The forbid list caught it; a lenient scorer would have called that a pass.

**The four passes are all single-hop direct recall** -- latch, frost, wet, and one correct silence. Exactly the shape the saturated 32-ask suite praised: one hop to a co-told word, and nothing else.

### The 4.0-cap explanation was wrong; the region organ closes for good

tmp_cap_probe.py, same pre-registered hand list, same frozen statistic, two repairs:
- **Nothing was pinned.** Across 36 words, 0.000 pct of touched cells sit at 4.0 before the tell, and every write maximum is below it (highest 3.9487).
- **Raising the cap 10x** (SAN_WEIGHT_CAP 4.0 -> 40.0, in memory on a session copy, nothing saved) leaves the verdict **identical**: P=0.500 R=0.667, numbers moving in the fourth decimal (spins 1.1549->1.1544, noon 1.8181->1.8159, the 3.7140->3.7264).
- **Per-row normalisation is worse, and it is a self-inflicted ceiling**: dividing each touched cell by the pre-max of its own row makes the background exactly 1.0000 for any word whose row max lies inside the touched block (bell, salt, spins) -- nothing can exceed 1.0. P=0.333 R=0.333 (asis), P=0.500 R=0.333 (raised).

So the previous entry's claim that headroom under the cap decides is **false, and is corrected here rather than left standing**: nothing was clipped. salt stays quiet because its touched block already holds 3.7331 and the write is smaller than that. The mechanism is **shared footprints** -- the 12 hash cells of a rare word collide with corpus-wired cells, so its block inherits common-word weight whatever the ceiling is.

The predicate did not separate under either repair: **the region organ stays closed for good.** No third variant, no re-tune. SAN_WEIGHT_CAP is now a named constant with its **default unchanged at 4.0** -- a probe handle, not a re-tune; live behaviour is identical until something passes a new value.

**Where the next cut should land, per the map rather than guesswork:** the two conjunction crashes are a plain bug in the answering path; mouth (sold twice, echo instead of slot) is the cheapest visible capability; count 0/8 is the largest block but needs a mechanism the brain does not have. **Nothing was fixed this turn** -- the deliverable is the map.

## Defect fixed: the join chose a memory it had no vector for (`KeyError: 'proposition'`)

Not an experiment -- a crash on the answering path, found by the new instrument.

**Root cause.** `_prop_join` admits the **session ledger** into its pool first
(`organs/neural_language.py:2455`, "Ledger first: the pair the user spoke is in
here by construction"), and ledger rows carry only `tokens/who/when`
(`:342`) -- they are the **whole sentence the user spoke**, deliberately not
windowed, whereas the binder keys its rows on the first `max_roles` tokens. A
join that legitimately found a pair therefore returned a hit with no
proposition vector, and `answer()` unbinds a role from exactly that key:
`role_of(best["proposition"], role, cands)` raised. The two conjunction asks in
the held-out set were the first tasks ever to route a **ledger** row into the
join's winner, which is why 32/32 on the shipped suite never saw it.

**Fix.** `Binder.proposition_for(tokens)` (`organs/higher_cortex.py`, before
`role_of`): the exact stored row when the tokens key onto one, otherwise
`encode(tokens)` -- which is not an approximation invented here, because
`remember` stores `encode(tokens)`, so the re-encode *is* the vector the binder
wrote for those words, up to the idf table having grown since. `_prop_join.admit`
now gives any vectorless entry its proposition **at the moment it enters the
pool**, marks it `vector_derived`, and reports `ledger_vectors` in the join
trace so the count of this fix's work per ask is visible.

**The crash was left uncaught on purpose.** `answer()` still reads
`best["proposition"]` with no `try` and no `.get()`: the key is now guaranteed
where the hit is created, so any future missing key raises loudly instead of
being swallowed. The instrument, not the anatomy, absorbed the lesson:
`Session.ask` stores an exception in `turn["error"]` and returns an empty
reply, so **a crash is indistinguishable from a silent recall miss in the
trace** -- no reason, no source, no verdict. The harness now checks
`turn["error"]` first and labels it `engine_error`.

**Measured, full held-out re-run after the fix** (`heldout_20261028_174052`):
no traceback, no `KeyError`, `engine_error` **0**.

| | pre-fix | post-fix |
|---|---|---|
| score | 4/24 = 0.167 | **4/24 = 0.167** |
| recall | 8 | 8 |
| shape_arbiter | 4 | **5** |
| gating | 4 | 4 |
| mouth | 2 | **3** |
| engine_error | 2 | **0** |

**The total did not move; the composition did, and the two passes in the
conjunction script are now different items.** `what is both wet and on the
hook` **passes for the first time** -- it answered `the coat is on the hook`,
the right memory, where before it crashed. But it now *speaks*, and speaking
changes the state the rest of the script sees, so `is the coat dry or wet`,
which passed pre-fix, now comes back as chain confabulation:
`shire lets crash leant`, `source='meaning resonance + chain'`. Net zero at the
script level (2/4 both times). **4/24 = 0.167 stands as the baseline**, with
this composition.

**Closure of the harness's own unresolved item.** The committed map now says
`engine_error 0` because the committed harness printed it. The pre-fix
`engine_error 2` label remains **traceback-derived, not printed**: the fix
landed before any run could print that label, and the `engine_error` branch has
therefore never been exercised by a real crash. It is untested code that this
log is relying on once-past, and that is stated rather than smoothed over.

## Design: the ask's frame is not the ask's content (recall bucket, 8 of 24)

The frozen bar for this cut is the post-fix baseline **4/24 = 0.167**. Measured
on the held-out set, not on the saturated 32-ask suite.

**Which of the eight.** Seven are the coverage floor refusing, with its number
attached: `how many times did i tell you the coat is wet` **45%**, `how many
things did i tell you about the coat` **49%**, `how many times did i tell you
about the scarf` **49%**, `how many objects did i tell you about` **58%**,
`how many times does the bell turn` **42%**, `how many eggs did i mention
first` **36%**, `how many eggs broke` **41%** -- all against
`ANSWER_COVERAGE_FLOOR = 0.6`. The eighth, `did any egg break`, refuses with
*"it did not understand and was not in the mood to babble"* -- a different
mechanism, **out of scope here**.

**Mechanism.** A question carries **frame words**: words that name the *act of
telling* (`tell, told, say, said, speak, mention, ask, asked, question,
repeat`), the *number of tellings* (`many, much, time, times`), a *position in
the sequence of tellings* (`first, last, next, ever`), the *enumeration nouns*
(`thing, things, object, objects, item, example`) and the *question
auxiliaries* (`do, does, did`). No memory can ever contain them, because they
are not in the world the tells describe -- they are in the asking. Coverage is
a **weighted fraction over `must`**, so an uncoverable word in the denominator
is a permanent tax on every ask that carries it: with `times` and `tell`
weighted, `the coat is wet` cannot clear 0.6 **however exactly it is
remembered**. They are excluded from `must`, matched on stem, from a **closed
frozenset** -- not learned, not tuned per ask, not a threshold moved.

**Threshold.** `ANSWER_COVERAGE_FLOOR` stays **0.6, untouched**. This is not a
loosening of the bar; it is a correction of what the bar is a fraction of. The
word the guard exists to protect -- the content the ask points at (`coat`,
`wet`, `bell`, `turn`, `egg`) -- stays in the denominator.

**The hole this opens, closed in the same edit.** If a question's only
distinctive words were frame words, `must` becomes empty and the coverage block
is skipped entirely -- which today means *answer from whatever came back*. That
is the confabulation the floor was bought to stop, so the new case is refused
explicitly with its own reason: *"the question named only the telling"*. The
pre-existing empty-`must` path (all content words merely common) is **left
exactly as it was** -- this cut does not touch behaviour it did not create.

**Falsification, pre-registered, four conditions:**
1. the held-out score must rise above **4/24**;
2. at least one of the seven coverage-refused asks must pass;
3. **no held-out pass may flip to a fail** -- if one does, a frame word was
   load-bearing for the guard and this is licence to guess: **revert**;
4. the `recall` bucket must shrink. If the seven still refuse at the same
   coverage numbers, the floor was not what blocked them: **revert**.
Plus the standing gate: pytest stays **407 passed / 3 skipped**.

**Honest prediction, made before measuring.** Expected yield is **small**:
`how many times does the bell turn` should pass (strip `times`/`does` and
`the copper bell turns twice` covers `bell`+`turn` fully, and the answer word
`twice` is already inside the tell). `how many eggs did i mention first`
reduces to `{egg}`, which **both** egg tells cover, so it becomes a coin flip on
which memory the ranking picks. `how many eggs broke` is expected **NOT** to be
fixed: its `must` is `{egg, broke}` -- no frame words at all -- and it fails
because `broke` does not stem onto `break`. That is a *stemming* defect, a
different mechanism, and naming it here is the point of not bundling.
`how many objects did i tell you about` becomes empty-`must` and is refused by
the new guard. The rest need a counting or enumeration mechanism the brain does
not have, and this cut does not give it one: they should **move bucket without
passing**, which is a measurement even if the score does not move.


## The frame cut: reverted -- it failed its own conditions (2026-10-28)

Measured on the held-out set against the frozen bar 4/24 = 0.167. Tasks byte-identical, nothing restructured to help the number.

**Result: score did NOT rise -- 4/24 = 0.167 again (condition 1 FAILED).** Buckets moved: recall **8 -> 5**, shape_arbiter **5 -> 8**, gating 4 and mouth 3 unchanged. One GAIN and one FLIP-DOWN, and the flip decided it:

- GAIN: "how many eggs did i mention first" passes. With mention/first out of the denominator `must` = {egg}, and the ranking chose "there are four eggs in the basket", which contains the answer word.
- **FLIP-DOWN: "where did i say the scarf is" passed before as a correct refusal and now FAILS as an assertion** -- he says "the scarf is wet" when asked WHERE the scarf is. Condition 3 says a flipped pass means the frame word was load-bearing for the confabulation guard and this is licence to guess: **revert**. Executed as `git checkout -- organs/neural_language.py` (both edits); the KeyError fix stays committed at c978cbd, unrelated and measured good.

**Why the guard was load-bearing.** "say" is a frame word by my list, and excluding it let the memory that NAMES the scarf clear the floor at 100 pct. The floor was never measuring "does this memory contain the answer" -- it measures "does this memory account for everything the ask points at", and a where-ask with no where-memory is exactly what it was bought to stop. The design entry named this failure mode in advance and the mechanism walked into it.

### What moved, and what did not (the measurement the cut was worth)

- coat-wet-times 45 pct, coat-things 49 pct, objects 58 pct: **left recall and died one stage later at the arbiter**, which has no shape for a count. The floor was real for them; the counting mechanism is still missing. A bucket shift, not a pass.
- scarf-times 49->58, bell-turn 42->**59**, eggs-broke 41->55: **still refused by the floor**. My prediction that bell-turn would pass was WRONG, and the reason is the finding of this cut: the residual tax is the question word itself. "how" leaves `must` only if `is_interrogative("how")` is true, and that is LEARNED from corpus lines carrying a ? -- the held-out asks carry none. So the frame category is not closed-list-complete: the ask's own interrogative pronoun is the largest uncoverable weight remaining, and whether it counts is gated on the punctuation of a book rather than on anything in the question.
- before-the-kettle moved the WRONG way, shape_arbiter -> recall at 57 pct: once frame words left `must` the candidate pool changed under it. It cost no pass. Logged because it is a coupling, not noise.

**Standing bar: 4/24 = 0.167, unchanged, with the pre-cut composition** (recall 8, shape_arbiter 5, gating 4, mouth 3, engine_error 0). The recall bucket's ceiling is not the floor: three of the eight now show they would reach the arbiter and still have nowhere to put a count. Two things this rules out rather than merely fails: lowering ANSWER_COVERAGE_FLOOR would buy the same three gains and the scarf regression together, since the floor is what is holding the guard; and a bigger hand-written frame list is not available, because the word that would have to go on it next is the interrogative itself.

**Cheapest open question from this cut, not taken:** what `is_interrogative` is allowed to know. It is earned from ?-lines in the corpus, so an ask written without one is judged as if it were a statement -- that is a defect in evidence, not a missing organ, and it sits under 3 of the 8 recall failures.

## Instrument fix: the asks now carry punctuation (2026-10-28, ruled)

The missing `?` was an instrument defect, not a task change: `is_interrogative`
is **learned from corpus lines carrying a `?`**, so unpunctuated asks were
presenting Droso with input that never occurs in his training. **23 of the 24
asks got a `?`** -- the imperative `say exactly the copper bell turns twice`
kept none, because it is not a question. The words of the questions, the answer
checks and the forbid lists are unchanged; the file's diff looks large only
because the rewrite reflowed the JSON, not because tasks changed.

**Sequential cold re-run: 4/24 = 0.167 -- the number did not move at all.** Same
four passes, same twenty failures, same stage map (recall 8, shape_arbiter 5,
gating 4, mouth 3). So the interrogative-pronoun hypothesis is **falsified as a
score blocker**: with punctuation present, the floor refused exactly what it
refused before.

## Method fix: the independent mode (path-dependence, ruled on)

Two runs in a row exposed the same thing -- a fix inside one ask moved a later
ask's answer, because the later ask saw a house that had just spoken.

`--independent` scores **every ask against a freshly built house**: the tells
that *precede* that ask are replayed into a new copy, then that one ask and no
other is put to it. Nothing an earlier ask did -- speaking, spending, writing
the ledger, changing what he feels like saying -- can move the number. One build
per ask (~46s), so each result is **journaled** to
`state/fitness/heldout_independent.jsonl` as it lands and the campaign survives
chunking across turns. `ask_record()` is shared by both modes on purpose: the
two numbers must come off the same checker or comparing them is meaningless.

| | sequential | **independent** |
|---|---|---|
| score | 4/24 = 0.167 | **4/24 = 0.167** |
| recall | 8 | **9** |
| shape_arbiter | 5 | 4 |
| gating | 4 | **2** |
| mouth | 3 | **5** |

Same score, same four passing asks -- **but the map differs, and two items moved
bucket.** Two asks that refused after understanding (gating) reach the mouth
when isolated; mouth failures rise 3 -> 5. So path-dependence does not have to
change a score to change what the failure map says. **The independent number is
the bar future cuts are measured against**; the sequential number is reported
alongside it, and where they disagree about *why* something failed, the
independent one is the truth about the ask and the sequential one is the truth
about the conversation.

## The recall cut, second and last attempt: reverted again, axis closed

Frame-word exclusion **plus** the `?` together, as ruled. Sequential:
**4/24 = 0.167 -- the score did not rise (condition 1 FAILED).** `count 0/8 ->
1/8` (the `how many eggs did i mention first` gain) and `invariant 2/4 -> 1/4`
(the `where did i say the scarf is` refusal lost), recall 8 -> 5, shape_arbiter
5 -> 8. **The predicted interaction did not materialise**: the same item gained,
the same item flipped, at the same coverage numbers as the unpunctuated run.

Per the ruling the recall axis is now **closed** -- no third cut on it without a
different mechanism. The mechanism is reverted (`git checkout --
organs/neural_language.py`); the `?` fix and the independent mode stay.

What the two attempts leave as evidence rather than as a failed guess:

- **The floor is not the blocker for the count family.** Taking the uncoverable
  frame words out of the denominator moved three asks out of `recall` and they
  died **one stage later at the arbiter, which has no shape for a quantity**.
  That is where count work lives.
- **The frame words are load-bearing for the absence guard.** Both attempts
  flipped `where did i say the scarf is` from a correct refusal to asserting
  `the scarf is wet`: excluding `say` let the memory that *names* the scarf
  clear the floor. Any future mechanism that touches `must` must carry its own
  absence test rather than inherit the floor's.
- **`how many eggs broke` (`must` = {egg, broke}) is a stemming defect** --
  `broke` does not stem onto `break`. Untouched by both attempts, still open.

Next, per the ruling: the **count bucket** (0/8 sequential, the largest unscored
block) or **gating** (4 failures where recall succeeded and he declined) --
measured against the independent baseline of 4/24 = 0.167.

## Stemmer: one irregular fold, measured alone (2026-10-28, landed)

`how many eggs broke?` was refused while the tell sat in front of it, because the
tell says "then two eggs **break**". `stem()` only ever removes endings; a vowel
change is not an ending, so `broke` and `break` could never meet.

Fixed in `organs/stemming.py` as a **stated closed map**, `IRREGULAR`, with
**one entry** -- not a dictionary of English. Each pair is a claim that two words
are the same word, and `stem` is shared with procedure retrieval, whose 295
stored signatures were folded by the function as it stood when they were
written; a fold that is harmless for question answering can silently un-match a
signature. The list grows from a failure that has been seen, never from a list
of irregular verbs.

**Delta, alone, on the independent bar:**

| | pre-stem | **post-stem** |
|---|---|---|
| score | 4/24 = 0.167 | **5/24 = 0.208** |
| count bucket | 0/8 | **1/8** |
| recall | 9 | 8 |
| mouth | 5 | 5 |
| shape_arbiter | 4 | 4 |
| gating | 2 | 2 |

**Exactly one ask moved** (`how many eggs broke?`, recall -> PASS); all 23 others
landed in the same bucket as before. The stemmer is credited with one point and
nothing more, which is why it was measured before the count work rather than
inside it.

Recorded, **not** touched: `eggs` does not fold to `egg` -- the `len(w) <= 4`
guard returns it before the plural rule. Both sides of every current ask say
"eggs", so nothing breaks today; it is a latent under-fold, not a defect in
evidence.

## The count cut: design recorded, falsification fired before code

The bar was frozen first: **independent count bucket 1/8**, and the target was
the shape the arbiter supposedly refuses -- three of eight count asks having died
one stage downstream of recall.

**The trace's own answer says the premise does not survive the independent run.**

- `_question_shape` classifies **who / what / where** and nothing else. A
  `how many` question returns `None`, and at `organs/neural_language.py:2808`
  that means `best = hits[0]`: **the arbiter is skipped, not stumped.** No count
  ask has ever been refused for want of a quantity shape, because none reaches
  it. An abstention "changes nothing by construction" -- the parser's own words.
- The one count row my map labels `shape_arbiter`
  (`how many eggs are left in the basket?`) is an **artifact of `stage_of`**: it
  was *spoken*, with a role filler, which is case (c) of that classifier -- not a
  veto. What it said was `there are four eggs in the basket`, the top-ranked
  memory replayed whole. The wanted answer is `two`, which is **4 - 2**:
  arithmetic across two propositions. A shape would not supply it, and a shape
  that echoed the nearest numeral would answer a question nobody asked.
- Where the eight actually are: **six at the coverage floor** (45%, 49%, 49%,
  36%, 42%, and one "not in the mood to babble"), **one at gating** (`did i ever
  tell you about the moon?` -- understood, declined), **one now passing**.

So the pre-registered falsification -- *if the asks never reach the arbiter with
a quantity in hand, the defect is upstream after all* -- **fires, on evidence
already in the journal, before a line of organ code was written.** No quantity
shape is built. The "three of eight at the arbiter" figure came from the
frame-cut **sequential** run, which is context only; on the bar the number was
never three.

What this leaves, recorded rather than answered: the count bucket is blocked by
the floor (an axis closed by ruling, and the blocker there is frame words in
`must`), and by arithmetic that no shape in this parser could express. The
sharper question the traces raise is **whether a numeral is a retrievable role
at all** in this architecture -- `how many eggs are left` was answered by
replaying a sentence, and only the mouth's forbid-check noticed the number was
wrong. That is a question about the answer, not about recall, and it is the next
one worth paying for.

## Mouth cut: the render line, designed before code (2026-10-28)

Bar frozen: independent **5/24 = 0.208**, buckets recall 8 / mouth 5 /
shape_arbiter 4 / gating 2 / PASS 5.

**The path.** `answer()` recovers the requested filler twice and throws both
away at the render. `organs/neural_language.py:2819` takes the binder's role
answer into `filler`; `:2800` takes the arbiter's verified answer into
`shape_filler`. Neither reaches the utterance. Line **2834** is
`said, source, words = " ".join(tokens), "recalled proposition", tokens`,
unconditional: the filler is stamped into the event as `recovered_filler`
(`:2844`) and then ignored. That is why `what turns twice?` -- arbiter verdict
`agree`, both fillers `bell` -- said `the copper bell turns twice` and tripped
the forbid on `copper`. Selection was right; the framing overran it.

**The one-line mechanism.** When the arbiter agreed and produced a shape
filler, say the filler; otherwise the render is untouched. The arbiter's
filler, not the role filler, because the arbiter is the organ that verified
the shape against the memory.

**What it deliberately does not touch.** The ruling at `:2828-2833` -- the
recalled proposition IS the answer, the chain is for spontaneous speech and not
for reading out something he remembers -- stays in force. Nothing here re-runs
an answer through `sequence.generate`; that ruling was bought with
`who pets droso` coming back as `parent feeds droso` and it is not being
re-litigated. The abstain path (`shape is None`, `:2809`) is also untouched.

**Guard risk checked before spending 21 minutes on it.** Every expect in
`tools/scripts.json` is `any_of`, with no multi-word `must_contain` anywhere in
the file, and the bare filler is by construction one of the expected words. So
the change can only reduce exposure on the `must_not_contain` rows and cannot
break an `any_of` row.

**Falsification.** If fixing the framing does not move `what turns twice?` to
PASS without flipping any current PASS to fail, the mouth is not the defect and
the numeral claim is the next thing to test.

**A finding that changes what "the mouth bucket" means, recorded before code.**
The five asks my map labels `mouth` are not on this path. `stage_of` labels
`mouth` when the *output* source matches `meaning resonance` or `chain` -- and
for all five (`sold`, `sold`, `amethyst solomon tallied`, `sold`,
`bridle gargery`) the render never had a candidate at all: retrieval fell
through to resonance babble. The label records where the words came *from*, not
which stage refused. The asks actually sitting on line 2834 are the four
labelled `shape_arbiter`. So this cut is aimed at that bucket, and the honest
consequence if it lands is a re-labelling: my `mouth` bucket is a
retrieval-fallthrough bucket wearing the mouth's name, and the mouth's real
defect is one line of framing.

## Stemmer, second entry: `eggs` under the length guard (2026-10-28)

Same defect class as `broke`, now that there is a fold test to extend it: the
ask says `did any egg break?` and the tell says `four eggs`. `stem()` cannot
reach this pair -- not because a vowel changed, but because the `len(w) <= 4`
guard returns `eggs` before the plural rule ever runs.

It goes in the **stated map**, not as a relaxed guard. Lowering the guard to
fold every four-letter `-s` word would fold `does` -> `doe`, `news` -> `new`
and `its` -> `it`: three over-folds that make different things look alike and
get believed, which is the one failure this function's whole policy exists to
avoid. A stated entry costs one word; a general rule costs the policy.

**Caveat recorded, not assumed away.** Unlike `broke`, which appears only on
the ask side, `eggs` appears on *both* sides, so the fold merges two tokens that
were previously distinct. Postings encoded before this change hold `eggs`;
queries after it hold `egg`, so the live house needs a cortex re-encode before
the fold helps it -- the independent campaign rebuilds houses from scratch and
therefore measures the fold honestly. `eggs` appears nowhere in
`exocortex/learned_procedures.json`, so no stored procedure signature is
un-matched.

## Mouth cut: measured, falsified, reverted (2026-10-28)

**The stemmer's second entry, alone on the bar: delta zero.** Independent
campaign, all 24 asks, eggs fold in and nothing else: **5/24 = 0.208**, the same
five passes in the same buckets as the pre-fold bar. Coverage on the eggs asks
ticked (36% -> 37%) and none crossed the floor; `did any egg break?` still
refuses with "not in the mood to babble", which is not a coverage answer. The
fold is landed on correctness -- a plural should meet its singular, it is pinned
by tests, and it cannot un-match a stored signature -- but it is **not** a gain
and is not booked as one. The count bucket is still blocked by the floor.

**The render cut fired its falsification, and the reason is better than the
prediction.** Two variants were measured, each on the asks the design named:

| ask | whole proposition (before) | arbiter's shape filler | binder's role filler |
|---|---|---|---|
| `what turns twice?` | FAIL `the copper bell turns twice` | FAIL **`copper`** | **PASS** `bell` |
| `what does the frost bite?` | PASS | PASS `latch` | FAIL **`bites`** |
| `what bites the latch?` | PASS | PASS `frost` | FAIL **`bites`** |

Variant A -- say the filler the arbiter verified, which is what this design
specified, because the arbiter is the organ that checked the shape -- moved
**nothing**: it said `copper`. Not a misrendering: `_shape_matches` returns
`before[0]` for a subject-unknown shape, the *first* content word before the
verb, so for a multi-word subject ("the copper bell") it names the modifier and
not the head. The framing was faithfully executing a filler that is chosen by
position.

Variant B -- say the filler the binder's `role_of` unbound, the one already
stamped into the event as `recovered_filler` -- moved the target ask to PASS and
**broke two that were passing**, because on those two `role_of` answered with
the verb: `bites`. Net one worse than the baseline.

Neither variant satisfies "move `what turns twice?` to PASS without flipping any
current PASS to fail", so **the mouth is not the defect** and the render is
reverted (`git checkout -- organs/neural_language.py`, verified by re-running
the two flipped asks: both PASS again, and `what turns twice?` back to its
original failure -- the tree is byte-exact the one the 5/24 was measured on).

**What the measurement actually established.** There is no trustworthy "requested
filler" in this architecture to render. The two organs that each claim to hold
one disagree, and each is wrong in the other's success: the arbiter gets `latch`
and `frost` right and `copper` wrong; the role machinery gets `bell` right and
answers `bites` -- a verb -- when asked *what*. A framing change cannot fix a
naming disagreement, and picking whichever filler passes this week's asks is
tuning to the falsification rather than answering it.

**And the bucket labels, as predicted before code.** The five asks labelled
`mouth` are not on the render path at all: every one of them reached
`meaning resonance` with no candidate in hand (`sold`, `amethyst solomon
tallied`, `bridle gargery`). `stage_of` labels the *output* source, so it names
the organ that spoke, not the stage that refused. The mouth bucket is a
retrieval-fallthrough bucket; the asks sitting on line 2834 were always the four
labelled `shape_arbiter`.

**Next, per the condition:** the numeral claim. `how many times does the bell
turn?` (42% coverage) and `how many eggs are left in the basket?` (answered
`there are four eggs in the basket` when the wanted word is `two`) are the two
faces of it -- one never retrieves, one retrieves and replays a sentence. The
test is whether a numeral is a retrievable role at all, not whether the mouth can
be made to say one word.

## Regression guard: the 32-ask suite, run once (2026-10-28)

`state/fitness/script_benchmark_20261028_185939.json`, all 8 scripts, warm and cold, on the tree carrying the crash fix, the instrument fix and the stemmer fold: **warm 1.00, cold 1.00, delta 0.00** -- every script scored 1.0 in both phases. The suite had not run since before `c978cbd` and two `answer()`-touching commits landed in that gap. It cannot show gain; it was run for damage, and there is none.

The stemmer's contract is now under test: `tests/test_stemming_folds.py`, six tests, including that the irregular map is a fixed point of itself (no chains), that the lookup sits before the length guard, and that `spoke` is deliberately absent -- the list grows from a failure that has been seen, not from a table of irregular verbs. The hazard the map documents was checked against the store: every `broke` in `exocortex/learned_procedures.json` sits inside `broken` or `_retry_until_broken`, never a standalone token, so no stored signature can un-match.

## 32-ask guard on the final tree: red under load, green unloaded (2026-10-28)

`state/fitness/script_benchmark_20261028_195822.json`, all 8 scripts on the reverted tree (eggs fold only): **warm 0.812, cold 1.00, delta -0.188** -- `reference` warm 0.0, `accumulation` warm 0.5, the other six at 1.00. It ran concurrently with an 8-ask held-out confirmation and the full pytest.

**Attributed by re-running the two red scripts alone, nothing else on the machine: reference 1.00 warm / 1.00 cold, accumulation 1.00 / 1.00, overall 1.00 / 1.00.** So the red was load, not the fold -- which is also what the content says: neither script contains the word `eggs`, and the fold changes the stem of that one token. Not re-run: the other six, which were already green under load. pytest on this tree: 414 passed, 3 skipped.

Read beside the nondeterminism finding already in this log: a warm score of 0.0 on two asks that pass unloaded is a silent-miss shape, and the guard number is only trustworthy when the machine is quiet. The next guard run happens with nothing else running, and a red guard is not to be booked as a regression until it has been re-run alone.

## Pre-registered: the head-final subject (2026-10-28, written before the edit)

The falsification of the render cut exposed a defect sharper than the one it was
testing, and this one is principled rather than per-ask.

**The defect.** `_shape_matches` returns `before[0]` for a subject-unknown
shape -- the FIRST content word before the verb. English noun phrases are
head-final: in "the copper bell turns twice" the head of the subject span is
`bell` and `copper` is a modifier. So the matcher names the modifier whenever a
subject has more than one word, and it does so from the sentence alone, without
seeing the ask. That is why variant A of the render cut said `copper`: the
framing was faithful and the filler was wrong at the source.

**The mechanism, one line.** head = the LAST content word of the subject span,
`before[-1]`. The stated fallback is automatic: when the span is one word,
`before[-1]` is `before[0]`, so nothing changes for every single-word subject
that the rule already answered correctly.

**Scope, deliberately narrow.** Only the answer side is touched. The question
side has the same defect -- `_question_shape` builds the locative subject with
`[:1]`, so "where is the copper box kept" would also name the modifier -- and it
is **recorded and left alone**, because fixing two position bugs in one cut
means the delta cannot be attributed to either.

**Conditions, all four measured before this is called a gain:**
1. `what turns twice?` moves to PASS, speaking `bell` with no `copper` in it;
2. **no current PASS flips to fail**, on all 24 asks;
3. measured on the full independent set, all 24, freshly built house per ask --
   not a chunk, not the sequential path;
4. pytest stays green (407 + the fold tests now in the tree).
Then, because six green under load plus two green alone is not eight green on a
quiet machine: **all 8 scripts of the 32-ask guard run clean, nothing else on
the machine**, before the point is booked.

**If it fails either way** -- the target still fails, or a PASS flips -- the
render stays reverted, the mouth axis is logged **closed for good**, and only
then does the numeral probe run.

**What a gain means, stated in advance:** it would be the first capability point
the log has recorded in eight cuts, and it would come from a rule about English
noun phrases, not from a threshold moved or a list grown toward an answer key.

**VOID AS PRE-REGISTRATION, and the cut is already landed.** Read before edited:
the committed tree already returns `before[-1]`, and `git log` puts this work at
**`9fdb53f`** -- *arbiter names the head, not the modifier ... the mouth says the
word the arbiter named ... `what turns twice?` moves to PASS speaking exactly
`bell`, independent bar 5/24 -> **6/24 = 0.250**, no current PASS flipped under a
contemporaneous control, all 8 guard scripts clean warm 1.00 cold 1.00 on a quiet
machine, pytest 414* -- followed by `94b1418` (object head `after[-1]`, a verified
no-op, pinned by 5 unit tests) and `de7db33` (campaign auto-diff against its own
control). My summary was three commits stale, so I wrote a pre-registration after
the fact; a pre-registration written after the measurement is not one, and this
paragraph is the record that it was void. **The bar is 6/24 = 0.250, not 5/24,
and the first capability point is booked.** All four conditions above were
already met, including the eight scripts clean on a quiet machine. The pytest
count the instruction quotes (407/3) is also stale: this tree is **428 passed,
3 skipped**.

# The breeding population axis (2026-10-29): cost model, architecture, control

Measurement and design only, as scoped. No thousand generations, nothing
mutated toward the held-out set, and the population never touched main's answer
path -- it runs on copies. `tools/fly_cost_model.py`, `tools/fly_population.py`.

## Step 1 -- the machine sets N. Measured, not guessed.

RSS read by psutil inside a fresh subprocess, so it is the RSS of this work and
not of an editor open for three days.

| what | MB | note |
|---|---|---|
| baseline after imports | 28.4 | |
| **one fully loaded house** | **+2537.2** | corpus, band, embeddings, weights |
| **a second house, same process** | **+2426.3** | **DUPLICATED -- no page sharing** |
| after freeing the second | 0 returned | the allocator kept the pages |
| full copy of `san_w` (8192x8192 f32) | +256.0 | the largest single array found |
| sparse delta, 10 000 cells | **+1.11** | a fly's mutable layer, done right |
| sparse delta, 100 000 cells | +16.82 | |
| rebuild a house from corpus | **18.2 s** | the thing the design forbids per fly |
| one cheap fitness eval, 48 pairs | **< 0.01 s** (10 flies: 0.00 s) | |

Machine at measure time: 11 637 MB total, **4 591 MB free**, 60 % load. The 8 GB
grant is therefore not what this box currently offers, and N is published both
ways. The script's own first derivation was **wrong and is corrected here**: it
divided the usable budget by the per-fly cost without subtracting the one shared
substrate, which is the largest item in the ledger.

```
granted path    8192 - 2048 headroom      = 6144 MB
                6144 - 2537 substrate     = 3607 MB for flies
                sparse delta  1.11 MB/fly -> N = 3249
                full copy   256.0 MB/fly  -> N =   14
                house/fly  2426.3 MB/fly  -> N =    1   impossible
observed free   4591 - 2537 substrate     = 2054 MB
                sparse delta  1.11 MB/fly -> N = 1850
                full copy   256.0 MB/fly  -> N =    8
```

**So N is not 10 and not 400: it is thousands, and RAM is not the binding
constraint.** Two things are. First, the second house duplicates: 2.4 GB more,
so *any* design that gives a fly its own house has N = 1 and is dead on
arrival -- the shared-substrate rule is forced by measurement, not taste.
Second, wall-clock: at < 0.01 s for ten flies the structural fitness costs about
1 ms a fly, so a generation of 1000 flies is ~1 s and a turn could hold
thousands of generations. Time is not the limit either; **the limit is whether
there is any fitness signal worth selecting on**, which is Step 4's problem and
is measured below as not-yet.

Caveat, stated: the array scan walked `language.__dict__` and one level below,
and found only 256 MB of the 2537 MB. The rest sits deeper (cortex, band,
embeddings) and was not individually costed, so per-fly full-copy cost is a
lower bound.

## Step 2 -- architecture that makes N possible

One immutable substrate, loaded once per process, shared read-only. A fly is a
**genome** -- seeded, deterministic, its identity the canonical JSON of itself,
hashed to a 12-char id -- plus a **mutable layer that is a dict of deltas and
knobs**, never a second house. 10 000 perturbed cells cost 1.11 MB, so a fly
costs about a kilobyte per touched cell and a thousand flies cost about a
gigabyte. No fly rebuilds from corpus (18.2 s each, and it would duplicate the
substrate), and no fly writes into the shared substrate: a knob is applied to a
scratch view of only the array it touches and freed before the next fly.
Saving or forking a fly is **one JSON line** -- smaller than the eight-file
surface already proved restart-identical.

**Process model, explicitly: serial in-process against one loaded substrate.**
The measured RAM rules the alternatives out. Threads would share the substrate
but Python's GIL serialises the numpy-free rule work anyway and every fly's
delta becomes shared mutable state -- the one thing the design forbids.
Fork/copy-on-write is the natural fit and is **not available: Windows has no
fork()**, and the measurement shows that loading a second house in one process
duplicates 2.4 GB rather than mapping the same pages, so even a multi-process
pool pays per-process substrate. Serial in-process with saved deltas is the only
model where N is set by the deltas and not by the substrate.

## Step 3 -- the control, and it passes

Genes are positions and closed-class membership, never a threshold:
`head_index` in {first, last, second-to-last}, `extra_function` a subset of
{twice, again, some, old}, `stem_verb` on/off.

```
population A -- 10 clones, identical genome, ZERO mutation
  fitness values = [1.0]                 null spread = 0
  all ten byte-identical in genome id AND fitness  -> identical = True
population B -- 10 mutants from one base, same seed 13, mutation only
  fitness values = [0.0, 0.104167, 1.0]  mutant spread = 2 (3 distinct)
verdict: EVOLUTION MAY START
```

The null is exactly zero, so the harness is deterministic and the mutant spread
is real variance, not noise. **But read Step 4 before believing that buys
anything.**

## Step 4 -- fitness: the control passes on a fitness that is not yet a capability

The fitness the axis wants is the one named in the brief -- does the head-final
shape rule agree with the binder. **It did not run.** The binder answered
**0 of 48** pairs, and the reason is mine, not the binder's:
`role_of(proposition, role: int, candidates)` takes a **numeric** role from
`role_for()` and a proposition of **token ids**, and I passed role names, then
word strings: `ValueError: could not convert string to float: 'the'`. The first
version of this file hid that behind a bare `except` and reported a silent
binder, which is the same mistake as a swallowed error in a test.

So today's key is **structural**: agreement with the head the generator placed
in the sentence. That is self-referential, and worse, it is **saturated** -- the
base genome *is* the head-final rule, so it scores 1.000 by construction and no
mutant can beat it. Selection on this fitness can find regressions and nothing
else. Measured, exactly as the pre-registered second result anticipated:

```
gen 1: best=1.0000 distinct=2 n=10
gen 2: best=1.0000 distinct=3 n=18
gen 3: best=1.0000 distinct=3 n=26
```

Generation 2's best does not beat generation 1's, and it cannot: the ceiling is
where the base already stands. **Logged as the second result, not hidden as a
failure.** And the growing `n` is a defect in my `select()`: it returns
`len(rows)` parents and the caller then adds `n - elite` mutants on top, so the
population balloons 10 -> 18 -> 26 instead of holding size. Both must be fixed
before selection means anything: **the population size bug, and a fitness that
is not already maxed by the incumbent.**

The other three fitness components are designed and **not yet measured**: does a
region survive restart (needs the eight-file save/load, cost unknown); does a
concept separate from its corpus background (needs the embedding API); does a
walk find a 40-second edge (seconds per fly, so it caps N by time, not RAM).
The 24-ask held-out set is never the selection pressure -- 46 s an ask, and
load alone turned a guard red. It stays an outside check scored once afterward,
and its current number is **6/24 = 0.250** from `9fdb53f`, not the 5/24 in my
stale summary; I did not re-score it this turn because the population touched
nothing on the answer path.

## Step 5 -- selection, designed, and where it currently fails

Elitism (best `elite` survive unmutated) plus a k-tournament among the rest;
losers discarded, not archived. Every individual writes genome, fitness, parent
and generation to a lineage file (`state/fitness/fly_lineage_*.jsonl`) so any
survivor is auditable back to base. Implemented, exercised for three
generations, and **wrong in the size term above.**

## Falsification status, written before code and now measured

*If the mutated spread is not larger than the null spread, the axis closes.* The
null spread is 0 and the mutant spread is 2, so **the axis does not close** --
there is heritable variance. *If it is larger but generation 2's best does not
beat generation 1's, log that too.* Logged, immediately above: it does not,
because the incumbent fitness is saturated by the incumbent genome.

**What closes the axis for real, stated now:** not determinism, which holds, but
a fitness with headroom. The next cut is one that the base genome does not
already max -- the multi-word **object** span, where `after[-1]` is pinned by
unit test and has never scored a point, or restart survival, which no current
rule touches at all. Until then this is a working harness with a measured cost
model and no capability to select for.

## The four numbers, reported before any further breeding (2026-10-29)

Read from the files, not from recollection. First, the organ: last turn's
`write_file` truncated `organs/neural_language.py` to 296 chars. Restored with
`git checkout --` and verified -- **4017 lines, 212 507 chars, imports, both head
rules present, tree matches HEAD** -- before anything was measured against it.

**1. The cost model** -- `tools/fly_cost_model.py`, report
`state/fitness/fly_cost_20261029_000648.json`. RSS by psutil inside a fresh
subprocess.

| number | value | source field |
|---|---|---|
| one loaded house | **+2537.2 MB** | `house1_delta_mb` |
| a second house, same process | **+2426.3 MB -- DUPLICATED** | `house2_delta_mb`, `second_house_shares: false` |
| freed again | 0 returned | `after_free_second_mb` |
| per-fly delta, 10 000 cells | **1.11 MB** | `sparse_delta_10000_mb` |
| per-fly full weight copy | 256.0 MB | `full_weight_copy_mb` |
| wall-clock per individual | **< 0.01 s** for 48 pairs (10 flies: 0.00 s) | `fitness_seconds_1fly` |

**Derived N under 8192 MB with 2048 headroom:** 6144 - 2537 substrate = 3607 MB
for flies -> **N = 3249** at 1.11 MB/fly, or **N = 14** at a full weight copy,
or **N = 1** at a house per fly. The script's own first derivation printed 4136
and 17 because it forgot to subtract the substrate; corrected here.
*Wall-clock per individual, restated as one number:* about 1 ms, so time is not
the constraint and 10 000 generations would cost ten seconds.

**2. The null spread -- ZERO, confirmed** -- `state/fitness/fly_control_20261029_000950.json`.
10 clones, zero mutation, seed 13: fitness values `[1.0]`, `null_spread: 0`,
`clones_identical: true`, and one genome id. The harness is deterministic; this
gate passes, so breeding is not blocked on noise.

**3. The mutant spread** -- same file, population B: 10 mutants from base
`08b785873719` (`{"seed":13,"head_index":-1,"extra_function":[],"stem_verb":true}`),
one seed, mutation only. Fitness values `[0.0, 0.104167, 1.0]`,
`mutant_spread: 2`, three distinct. Heritable variance exists, so the axis does
not close on the pre-registered condition.

**4. Generation-1 best vs generation-0 best** -- `state/fitness/fly_gens_20261029_001010.json`:
gen 1 best **1.0000**, gen 0 (the base) best **1.0000**. **No improvement, and
none possible: generation 1's best IS the base genome.** The fitness is
saturated by the incumbent, exactly as logged last night -- selection here can
only find regressions.

**The lineage file does not do what was asked, and this is a defect, not a
formatting nit.** `state/fitness/fly_lineage_20261029_000950.jsonl` exists only
for the control run: **20 rows, all `gen: 1`, and every one carries
`parent: None`**; ids collide, `10 distinct row ids across 20 rows`, because
populations A and B both number themselves `g1-0..g1-9`. And
`phase_generations` **writes no lineage file at all** -- it saved only the best
per generation. So no survivor can currently be traced to its parent. That
needs fixing before selection means anything: `evaluate()` must record the
actual parent genome id at mutation time, `phase_generations` must write the
lineage it currently omits, and ids must be unique across populations.

**The outside check -- in flight, and read it as a reproduction test.** Job
`cdf6b9`, one process, all 24 asks, no chunking, journal
`state/fitness/heldout_fly_g1.jsonl`:

```
py -3.10 -c "import os,json,sys;g={'head_index':-1,'extra_function':[],'stem_verb':True,'seed':13};
os.environ['FLY_GENOME']=json.dumps(g);import tools._genome_patch;
sys.argv=['heldout_eval','--independent','--journal','state/fitness/heldout_fly_g1.jsonl'];
import runpy;runpy.run_module('tools.heldout_eval',run_name='__main__')"
```

`tools/_genome_patch.py` printed **PASS-THROUGH: genome ... is the committed
rule**, so nothing was overridden and this run measures the committed brain.
Baseline to compare against, from
`state/fitness/heldout_ind_20261028_224835.json`: **6/24**, pass set
`{conjunction-and-absence::what is both wet and on the hook?,
conjunction-and-absence::where did i say the scarf is?, exact-repeat::what turns
twice?, hop-and-inventory::what bites the latch?, hop-and-inventory::what does
the frost bite?, quantity-change::how many eggs broke?}`, by kind
count 1/8, order 2/8, invariant 2/4, mouth 1/4.

**What this check can and cannot say, stated before the number lands.** The
brief asks: if the evolved brain scores below baseline on the outside set while
its intrinsic fitness rose, that gap is the finding. Generation 1's best is the
base genome, its intrinsic fitness is 1.0 against a base of 1.0, so **it did not
rise and the brain did not evolve.** The expected result is a reproduction of
6/24 with the same pass set -- and if this run returns anything else, the fault
is mine in the wiring or the campaign, not an evolved brain. There is no gap to
report because there is no movement: the finding is that a saturated intrinsic
fitness has nothing to hand the outside check.

**The outside check never finished, and it is not evidence.** The job registry
lost the handle and the process with it: `state/fitness/heldout_fly_g1.jsonl`
holds **3 rows** and no report was written. Labelled pass-through; nothing for or
against the axis. It will not be re-run, because it was a reproduction test of
6/24 by construction and the axis has moved on.

# EVOLUTION CANNOT START YET (recorded before the three fixes)

The first harness's own numbers, stated plainly and not softened:

- **gen-1 best == gen-0 best, because gen-0 best is already the maximum.**
  Both 1.0000 -- the base genome *was* the rule the fitness measured, so there
  was nothing above it to select for.
- **Mutation was observed only as degradation:** mutants scored 0.0 and
  0.104167 against a 1.0 base. Nothing above the incumbent was ever produced.
- **8 of 10 mutants were invisible to fitness:** ten mutants, two distinct values
  beyond the base, so the genome vector did not reach what fitness read.

That is a harness that cannot evolve, and no amount of breeding would have
changed it. The three fixes, in the order they were made:

**1. Lineage, as a defect.** Every individual is now namespaced (`A-*`, `B-*`,
`g1-*`, `g2-*`), carries row id, genome id, parent genome id and generation, and
both phases write a lineage file -- previously `phase_generations` wrote none and
the control's 20 rows carried `parent: None` with 10 ids shared between two
populations. Generation phase asserts the population size holds (it ballooned
10 -> 18 -> 26 before). Proof by id, from
`fly_lineage_gens_20261029_002414.jsonl`: generation 1's best **`g1-8`
id `2df114c9310a` <- parent `33f3e25c5ca7`**, and `33f3e25c5ca7` is `g1-0`, the
founder with `parent: None` -- the base genome. Seed 17 shows a two-step chain:
`g2-5 id 64b060779a37 (0.625) <- 479403b78559 = g1-3 (0.4375) <- d896c3042232
= g1-0 founder (0.25)`.

**2. Fitness with headroom.** Four components, and the pass condition is the
same span-head check made *harder*, not a fifth soft check: each component is
8 spans -- 2 plain, 3 with a prepositional modifier, 3 with a relative clause.
The incumbent passes the plain ones and fails both harder flavours: *"the bell
of the gate turns twice"* has head `bell` and it says `gate`; *"the bell the gate
holds turns twice"* has head `bell` and it says `holds`. Base genome, measured
(`fly_control_20261029_002414.json`):

| component | base score |
|---|---|
| genitive_subject | 0.250000 |
| pp_subject | 0.250000 |
| genitive_object | 0.250000 |
| pp_object | 0.250000 |
| **composite** | **0.250000** |

No component is 1.0 on the base, so none is dead weight and none was replaced
for being free. **The breeding gate: base composite strictly below 1.0** --
met at 0.250, against the old 1.000.

**3. Mutation reach.** Genes are `head_index` (-1 | 0), `cut_at`
(none | of | all), `rel_head` (bool) -- each decisive at the base. Mutant
values `[0.21875, 0.4375, 0.59375, 0.625]`, spread 3, and **10/10 mutants differ
from base fitness (100%)**, against 2/10 visible before. The intermediate attempt
is recorded because its failure is the lesson: `prep_head` + `prep_scope` gave
**5/10 and was refused by the gate**, because `prep_scope` is inert while
`prep_head` is off -- *a gene that only matters in a context the base is not in
is not a gene*.

# Re-run against the new fitness: three gates pass, the fourth does not

```
null spread        0        (10 clones, one genome id)        PASS
mutant spread      3        ([0.21875, 0.4375, 0.59375, 0.625]) PASS
reach              10/10 = 100%                                PASS
base composite     0.250000 (< 1.0)                            PASS
gen-2 best > gen-1 best                                         FAIL
```

The failure is not a draw. Four seeds, all n=10, two generations:

| seed | gen-1 best | gen-2 best |
|---|---|---|
| 13 | 0.625000 | 0.625000 |
| 7 | 0.625000 | 0.625000 |
| 17 | 0.625000 | 0.625000 |
| 23 | 0.625000 | 0.625000 |
| 29 | 0.593750 | 0.593750 |

**Logged as a result, not hidden.** The mechanism is legible in the trace: the
ceiling needs **two** genes at once (`cut_at: all` and `rel_head: true`), one
mutation from the base reaches 0.625 with either, and the second step must be
proposed by a mutant of a 0.625 individual -- but in a ten-fly pool carrying one
or two such individuals, a three-way tournament breeds from them a minority of
the time, so the population climbs to the 0.625 ledge and sits there. Seed 17
shows exactly that: gen-2's 0.625 arrived by a *different* path
(`g2-5 <- g1-3 (0.4375) <- base`), not by improving the leader.

So: **fitness now has headroom and the population still does not climb it.**
The next lever is selection strength -- tournament size, or breeding only from
the elite -- and it is deliberately NOT applied in this turn, because a run must
report what the design does and not what it can be tuned into. Population size
and generation count stay at 10 and 2.

## Pre-registered: the selection lever (2026-10-29, written before the run)

**Hypothesis, stated before the run.** gen-2 stalls at 0.625 because a
three-way tournament in a ten-fly pool breeds from the 0.625 carriers too rarely
to compose them. The ceiling needs `cut_at: all` AND `rel_head: true` in one
genome; one mutation reaches 0.625 with either, so the second step must be
*proposed*, and proposal happens only when a mutant's parent already carries the
first gene. If the stall is a proposal-rate problem, concentrating reproduction
on the leaders fixes it. If it is not, the lever does nothing and that is the
result.

**Conditions, one at a time so the cause stays attributable.**
(a) elite-only breeding: the top k reproduce, everyone else discarded, k = 2
then k = 4.
(b) only if (a) fails: tournament size 5, then 7, same pool.

**Held fixed:** population 10, three generations for this test only (the stall
is a gen-2 question; gen-3 catches a composition that needs the extra step),
seeds 13, 7, 17, 23, 29 for every condition, fitness and mutation untouched --
the only variable is how parents are chosen.

**Pass:** on the majority of seeds (3 of 5 or more), gen-2 best > gen-1 best OR
gen-3 best > gen-1 best, within one condition. Every improving seed must be
reported with its composition path by lineage id: the winning genome's two
genes, traceable through the chain to the parents that supplied them.

**A stall on every seed and every condition is a result and will be logged as
one:** it means the ceiling is not reachable by selection strength, and the next
question is whether the composite surface is too sparse -- not whether the pool
is too small. In that case: do not widen the pool, do not add generations, and
do not soften the fitness to make a climb possible.

# The selection lever, run: every condition stalls, and the reason is the surface

Fitness, mutation, material, pool (10) and seed stream untouched; the only
variable was how parents are chosen. Every condition began from an identical
population per seed. `tools/selection_lever.py`, reports
`state/fitness/selection_lever_20261029_002923.json` and `..._002944.json`.

| condition | seed 13 | seed 7 | seed 17 | seed 23 | seed 29 | improving |
|---|---|---|---|---|---|---|
| elite k=2 | .625/.625/.625 | .625/.625/.625 | .625/.625/.625 | .625/.625/.625 | .594/.594/.594 | **0/5** |
| elite k=4 | .625/.625/.625 | .625/.625/.625 | .625/.625/.625 | .625/.625/.625 | .594/.594/.594 | **0/5** |
| tournament k=5 | .625/.625/.625 | .625/.625/.625 | .625/.625/.625 | .625/.625/.625 | .594/.594/.594 | **0/5** |
| tournament k=7 | .625/.625/.625 | .625/.625/.625 | .625/.625/.625 | .625/.625/.625 | .594/.594/.594 | **0/5** |

(gen-1 / gen-2 / gen-3 best.) **No composition path exists to report**: no seed
improved under any condition, so there is no arc of two genes to trace.

**Elite-only breeding with k=2 should have composed two genes almost surely if
composition helped at all** -- eight mutants a generation from the leader, a
third of them flipping the missing gene, three generations. It improved nothing,
on any seed. That removed "proposal rate" as the explanation before any
conclusion was drawn from it, so the surface was enumerated instead of guessed:
`tools/surface_probe.py`, all 12 genomes (head_index x cut_at x rel_head), 32
pairs.

```
MAX IN SPACE 0.62500
  0.62500  head=-1 cut=all  rel=False   .625 .625 .625 .625
  0.59375  head=-1 cut=any  rel=True    .625 .500 .750 .500
  0.43750  head=-1 cut=of   rel=False   .625 .250 .625 .250
  0.25000  head=-1 cut=none rel=False   .250 .250 .250 .250   <- the base
  0.21875  head= 0 cut=*    rel=False   ...
```

**The global maximum of the fitness over its entire genome space is 0.625, which
is exactly what generation 1 already holds.** The stall is not that selection is
too weak to climb; there is nothing above the first generation to climb to. The
two improvements are mutually exclusive in this surface: `cut_at: all` reaches
0.625 with `rel_head: false`, and `rel_head: true` reaches 0.59375 -- it buys the
relative-clause pairs and loses more prepositional ones than it gains, so no
genome holds both. The composite is not merely sparse, it is **peaked one
mutation from the base, by construction.**

This is the same defect as before wearing a different number: the first harness
had gen-0 at the maximum (1.0), this one has gen-1 at the maximum (0.625).
Making the material harder raised the difficulty without creating a path -- the
check got harder and the ceiling landed on the incumbent's first neighbour.

**Pre-registered stall rule, applied:** the ceiling is not reachable by
selection strength, so the next question is the fitness surface, not the pool
size. Pool stays 10, generations stay 3 for this test, and the fitness is not
softened to make a climb possible. What must change next is the surface: the
components have to be **additive** -- a genome that fixes relative clauses must
not lose prepositional ones -- which means the two constructions must not compete
for the same decision. That is a redesign of the material and the genes
together, not a tuning of selection.

## Pre-registered: the additive redesign (2026-10-29, before the code)

Two constraints, both so that the next stall means something.

**Cardinality.** Twelve genomes is not a search space, it is an enumeration --
at 12 the population IS the whole space and generations are theatre. The gene
that split relative from prepositional decisions must also widen the value range:
genes become **continuous weights** in [0, 3], not booleans, so the space is
uncountable and no run can exhaust it. A stall on an uncountable space is
"selection failed"; a stall on twelve genomes is "the answer set was twelve".

**Coupling.** The four components are span-matching on synthetic constructions
and are decoupled from the 24-ask set. One component must be read off the real
answer path, so a rising composite is at least plausibly capability: an
**arbiter-coverage** component computed from the organ's own `_question_shape`
and `role_for` on deterministic question forms -- the stage the held-out failure
map names when it says the arbiter refused. It is not scored against any ask's
key and never consults the held-out set, so it cannot be tuned toward it. Its
second job is structural: because the incumbent fails the `how many` forms (the
parser yields no checkable shape), **no fly can reach 1.0 on the composite**,
which is precisely the guard against breeding a brain that maxes its own exam
and still says `copper` when asked for `bell`.

**Stated in advance:** if the additive version still saturates on the first
generation, that is a finding about **coupling**, not about sparsity.

# The additive redesign, run: the climb happens, and it happens entirely on the synthetic four

`tools/fly_v2.py`. Genes are continuous weights in [0, 3] rounded to 6 decimals:
`w_pos`, `w_prep`, `w_first`, `w_len` -- roughly 8e25 genomes, so this is a
search space and not an enumeration, and a stall here cannot mean "the answer
set was twelve". All four features sum into one argmax, so a fly that fixes
prepositional spans does not lose plain ones: additivity is structural, not
hoped for.

**Base, measured with a real house (`--house`, one build, 18 s, shared by every
fly):**

| component | base |
|---|---|
| genitive_subject / pp_subject / genitive_object / pp_object | 0.625000 each |
| **arbiter_coverage (C5, real path)** | **0.666667** |
| **composite** | **0.633333** |

C5 detail, from the organ itself: `what turns twice?`, `what does the frost
bite?`, `who follows the sparrow?`, `where is the box kept?` -> **shape+role**;
`how many times does the bell turn?`, `how many eggs are left in the basket?` ->
**no shape**. That is the incumbent's real parser refusing to give the arbiter
anything checkable on count questions, and it is why the composite's ceiling is
**(4 x 1.0 + 0.667) / 5 = 0.9333, not 1.0** -- structurally out of reach, which
is the guard against breeding a brain that maxes its own exam.

The first run, deliberately recorded: C5 called on a hollow instance answered
"no role" for **every** form, giving 0.0. That caps the composite without
measuring anything -- a cap wearing the costume of a component -- and was fixed
by building one real house for it.

**Generations, 5 seeds, 3 generations, pool 10, unchanged:**

| seed | base | gen-1 | gen-2 | gen-3 | |
|---|---|---|---|---|---|
| 13 | 0.63333 | 0.78333 | 0.78333 | 0.78333 | stalled |
| 7 | 0.63333 | 0.75833 | 0.78333 | **0.83333** | improved |
| 17 | 0.63333 | 0.78333 | 0.83333 | 0.83333 | improved |
| 23 | 0.63333 | 0.78333 | 0.83333 | 0.83333 | improved |
| 29 | 0.63333 | 0.78333 | 0.78333 | 0.78333 | stalled |

**3 of 5 seeds improve** -- the majority the pre-registered criterion asked for,
and the first time in this axis that gen-2 or gen-3 has beaten gen-1. It is not
a first-generation saturation: gen-1 is 0.783, the ceiling is 0.933, and two
seeds reach 0.833 by gen-3.

**But every point of that climb is synthetic.** C5 never moves -- the four
weights cannot touch the parser -- so the improvement from 0.633 to 0.833 is
entirely C1-C4. This is precisely the gap pre-registered above: the composite
rose, and not one fly can be shown to have improved the real answer path. The
axis has produced a brain that is better at its own exam and is provably no
better at `how many times does the bell turn?`.

**Two defects named rather than buried.** (1) *Reach is 2/10 to 5/10 mutants
differing from base* (20-50%), short of "most draws": a mutation that lowers a
weight below the incumbent's leaves every decision unchanged, so half the draws
are silent. (2) *C5 is a cap, not a signal*: inert to these genes by
construction, so it prevents saturation but cannot reward capability. Making C5
gene-responsive is what would let a rising composite mean something about the
real path -- and that requires a gene that reaches the parser, which is a
different organ surface from span weights.

**Logged as the coupling finding the brief anticipated:** the additive redesign
removed sparsity as the blocker and replaced it with coupling. Selection can now
climb; it climbs a surface whose top half is disconnected from the 24 asks.

# Repair 1: reach, diagnosed on boundary distance

`tools/reach_probe.py` sweeps each weight in 0.01 steps from the base until the
composite moves, then replays the ten mutation draws and records which gene was
picked and whether the composite moved. Mutation distribution untouched.

**Before (base `w_pos` 1.0, `w_prep` 0.9, `w_first` 0.9, `w_len` 0.0):**

| gene | value | boundary up | boundary down | draws | crossed |
|---|---|---|---|---|---|
| w_pos | 1.00 | 0.80 | 0.10 | 2 | 2 |
| w_prep | 0.90 | **none (saturated)** | 0.80 | 4 | 4 |
| w_first | 0.90 | 0.11 | 0.80 | 2 | 2 |
| w_len | 0.00 | 0.46 | none | 2 | 2 |

Reach then was **2/10–5/10** across seeds. The diagnosis is exactly the stated
one: `w_prep` was already past its boundary (up = none), so every upward draw was
silent, and `w_pos`, `w_first` sat 0.8 away from their downward boundary. A gene
bites only when the draw crosses a boundary, and the base was far from most.

**After, repositioned to sit just off each boundary in its live direction**
(`w_prep` 0.12, `w_first` 0.99, `w_len` 0.45, `w_pos` 1.0 — composite unchanged
in kind, still below 1.0): boundaries **0.02–0.21** on every gene, both
directions live except `w_len` down, and **reach 10/10 on seeds 13 and 7**.

**After the parser gene was added** (which reshuffles the draw stream), the five
seeds measure **7, 8, 7, 8 and 10 of 10**. The target was 8/10 on every seed;
three of five meet it and two sit at 7/10, because a draw that pushes `w_count`
below zero clamps at its floor and a downward `w_len` still has 0.12 to travel.
Reported rather than fixed by inflating the mutation rate, which is the one lever
the brief forbids.

# Repair 2: five generations, all five seeds, unchanged design

| seed | base | gen-1 | gen-2 | gen-3 | gen-4 | gen-5 | reach |
|---|---|---|---|---|---|---|---|
| 13 | 0.68333 | 0.75833 | 0.75833 | 0.83333 | 0.83333 | 0.83333 | 7/10 |
| 7 | 0.68333 | 0.68333 | 0.75833 | 0.83333 | 0.83333 | 0.83333 | 8/10 |
| 17 | 0.68333 | 0.75833 | 0.82500 | 0.83333 | 0.83333 | 0.83333 | 7/10 |
| 23 | 0.68333 | 0.83333 | 0.83333 | 0.87500 | 0.87500 | **0.90000** | 8/10 |
| 29 | 0.68333 | 0.75833 | 0.75833 | 0.82500 | 0.82500 | **0.90000** | 10/10 |

Four of five improve and two climb past the 0.833 ledge the three-generation run
could not see. Seed 23 was at 0.833 by gen-1 and would have read as a ceiling at
three generations; at five it reaches 0.900 — which is the point of the
extension, and the reason a three-generation stall was not booked as a ceiling.

# The parser gene: `w_count`, and C5 moves

`w_count` in [0, 1]; above 0.5 the fly's parser gives a count question a
checkable shape where the organ returns none. It only ever ADDS a shape, so the
falsification test is a guard in code: `c5_for()` compares the answered set
against the base's and **raises** if enabling the gene turns any answered form
into a refusal. It never fired.

| | C5 | composite |
|---|---|---|
| base (`w_count` 0) | 0.666667 | 0.683333 |
| seeds 23, 29 at gen-5 (`w_count` > 0.5) | **1.000000** | **0.900000** |

So the composite climbs past the 0.933 cap's reach because C5 itself moved: the
arbiter now gets a checkable shape on `how many times does the bell turn?`. Not
falsified — the gene moved C5 without flipping a single answered form.

**What this does NOT show, stated plainly.** C5 measures whether the arbiter
receives a checkable shape, not whether the answer is right. A fly with
`w_count` above 0.5 is *admissible* on count questions; it has not been shown to
count. The 24-ask set remains the outside check, unscored this turn, and no
capability claim is made here beyond the shape stage.

**Gates:** null spread **0** on all five seeds; base composite **0.683333**,
strictly below 1.0; reach per seed in the table above; pytest 428 passed, 3
skipped.

# Two honesty items, recorded before the outside check

**1. Reach is 7/10 on seeds 13 and 17, and the axis is NOT gate-clean.** The
standing gate is 8/10. Three of five seeds meet it, two do not, and the mean of
{7, 8, 7, 8, 10} is not a number I will quote. Every generation table in this
log now carries its seed's reach beside it, and this paragraph is the record
that the gate is **failed on two seeds**, not averaged away.

**2. C5 measures receipt, not correctness.** A fly with `w_count` above 0.5 gets
a *checkable shape* for `how many times does the bell turn?` -- which is the
stage the failure map names (the arbiter was skipped for want of a shape) and
nothing more. It does not show the fly counts. **0.900 may be exam-solving**,
and the outside check is now the only thing that can tell.

# The genome was never persisted, and the number was recovered by replay

`tools/fly_v2.py --phase generations` prints its bests and writes no report, so
when the brief said "use the saved genome" there was no saved genome: the
generation runs left nothing on disk. That is a defect in the harness, recorded
here rather than repaired quietly.

`tools/score_best.py` recovers the fly and proves it is the *same* fly before
saving it:

```
replay A [0.758333, 0.758333, 0.825, 0.825, 0.9]  g5-2  3b55dc76f81a  0.9
replay B [0.758333, 0.758333, 0.825, 0.825, 0.9]  g5-2  3b55dc76f81a  0.9
deterministic across two replays: True     matches the printed best: True
```

Two independent replays from the same seed produce the same trajectory, the
same best row, the same genome id and the same 0.900000, so this is
dereferencing a deterministic value, not a new draw -- and the first attempt is
recorded too, because it **refused to save**: without `--house` the replay scored
fly against C5 = 0 instead of the gene-aware 0.666667/1.000000 and returned
0.700, a different trajectory. The check caught it.

Saved genome, `state/fitness/best_genome.json`, seed 29 gen-5:

```json
{"seed":258235818,"w_first":1.119446,"w_len":0.10172,"w_pos":1.0,
 "w_prep":0.099128,"w_count":0.519588}
```

`w_first` 1.119 is past the boundary that fixes relative spans; `w_prep` 0.099
is *just under* its 0.10 floor, so it still fails prepositional ones; `w_count`
0.52 turns the parser gene on.

# Outside check: what it can and cannot measure

One run, all 24 asks, no chunking, journal `state/fitness/heldout_best.jsonl`,
the saved genome through `tools/_genome_patch.py`:

- the **head rule is applied** -- the arbiter names the head the fly's weights
  choose, which is the same path the hop and exact-repeat asks traverse;
- **`w_count` is NOT applied**, and not for convenience: the organ has no count
  branch (`_question_shape` returns None for `how many`, which is precisely what
  C5 measured), so there is nothing to switch on. Applying it would mean writing
  the count capability into the organ inside the measurement. So the number
  below tests the genes the real path can carry and leaves the parser gene
  untested -- if the fly scores at or below baseline, the parser gene's 0.900
  was exam-solving by construction.

Baseline is the frozen **5/24** in the brief; the tree's own last recorded
campaign reads **6/24** (`heldout_ind_20261028_224835.json`, after `9fdb53f`),
and both are quoted against the result.

**Status at the end of this turn: in flight, and no number reported.** Job
`65a2bb`, journal `state/fitness/heldout_best.jsonl`: **2 of 24** asks journaled
after ~100 s, roughly 50 s an ask, so about twenty minutes total -- longer than
the turn. A number that does not exist yet is not reported as one. The read is
mechanical when it lands: `py -3.10 -c "import json;rows=[json.loads(l) for l in
open('state/fitness/heldout_best.jsonl')];print(sum(1 for r in rows if r.get('pass')),'/',len(rows))"`,
with the per-ask report at `state/fitness/heldout_ind_<stamp>.json`.

**The interpretation is committed now, before the number, so it cannot be
spun afterwards.** Both baselines are quoted: the frozen 5/24 the brief names,
and the 6/24 this tree last recorded.

| result | reading |
|---|---|
| **> 6/24** (and so > 5/24) | The axis's vindication: intrinsic gain accompanied by real capability for the first time. Report plainly, and the head rule is a candidate for the organ. |
| **= 6/24** (= 5/24 against the frozen bar) | The coupling finding, stated plainly: twelve generations of climbing moved the exam and not the brain. The next cut is a component read off a held-out-adjacent deterministic path, not another synthetic weight. |
| **< 6/24** | Said louder: selection is optimising something anti-correlated with capability. The additive design is revisited before any further breeding. |

Because `w_count` is not applied in the organ, a result at or below baseline also
means the parser gene's contribution to 0.900 was **exam-solving by
construction** -- the fly was rewarded for a shape it cannot yet produce.

No further generations this turn. One measurement, one number, when it exists.

# Pre-registered: C6, a retention constraint read off a held-out-adjacent path

The last synthetic weight made the composite climb; the question is whether the
climb is coupled to anything the house actually answers.

**C6 = retention on the deterministic question forms.** For each of the six forms
C5 already reads (the ones the parser either shapes or refuses), the fly's head
rule is applied to the proposition that form presupposes, and C6 counts the
forms where the fly names the SAME word the committed rule names. It is a
constraint, not a capability: the base scores 1.0 by construction, and it can
only be lost. That is deliberate -- a gain in C1-C4 that costs a divergence on a
real question form is exactly the coupling failure this cut exists to expose.

- **Bar:** the frozen **5/24** stands; this tree's 6/24 is quoted alongside.
- **The 24 stay out of selection.** C6 reads deterministic forms, not the
  held-out asks; no ask's expected answer is consulted.
- **Composite becomes** `(4 x C1-C4 mean + C5 + C6) / 6`.

**Stated in advance:** if a rising composite still leaves the outside check
unmoved, the additive design is what needs revisiting next -- not another weight.
That sentence is written now, before C6 exists, so it cannot be reached for
later as an excuse.

## C6, measured

| | value |
|---|---|
| base composite | 0.708333 |
| base retention | 0.833333 |
| **the 0.900 fly, under C6** | **0.888889, retention 0.833333** |

**C6 does not discriminate the climbers: it loses nothing.** The fly carrying
`w_first` 1.119 names the same head as the committed rule on every scorable
form, so its climb cost no divergence -- which is the outcome the constraint was
built to detect, and it did not fire.

Honest about the component's own defect: base retention is 0.833333, not 1.0,
because the locative form (`where is the box kept?`) yields no head under this
rule at all -- `_content` takes the span after the verb and the subject sits
before it -- so that form is excluded for base and fly alike. It is a constant
1/6 offset, not a base failure, and it means C6 is effectively a five-form
constraint. Recorded rather than patched, because patching it now would change
the numbers that were just measured.

**Composite with C6, five seeds, five generations** (reach re-measured per seed
on the new composite):

| seed | reach | base | g1 | g2 | g3 | g4 | g5 |
|---|---|---|---|---|---|---|---|
| 13 | **7/10** | 0.70833 | 0.77083 | 0.83333 | 0.83333 | 0.83333 | 0.83333 |
| 7 | 8/10 | 0.70833 | 0.70833 | 0.77083 | 0.83333 | 0.83333 | 0.83333 |
| 17 | **7/10** | 0.70833 | 0.77083 | 0.82639 | 0.83333 | 0.83333 | 0.83333 |
| 23 | 8/10 | 0.70833 | 0.83333 | 0.83333 | 0.86806 | 0.86806 | 0.88889 |
| 29 | 10/10 | 0.70833 | 0.77083 | 0.77083 | 0.82639 | 0.82639 | 0.88889 |

Null spread **0** on all five seeds; base **0.708333**, strictly below 1.0;
**reach 7/10 on seeds 13 and 17 — the axis is still not gate-clean, and that is
not averaged away.**

**What remains unanswered is the number itself.** C6 confirmed the climbers do
not break deterministic forms, but it cannot show they answer anything better;
only the 24 can, and the outside check has not completed a run yet: the first
died at 3 of 24 rows, the second (job `7b81f3`) is still running. No number is
reported for it.

# Outside check: 7/24, and the ask that moved is the one the gene targets

Both background runs died at turn end (3 and 7 of 24 rows, no report) -- the
workspace kills them when a turn closes -- so the 24 were run as **six complete
per-script segments** in the foreground. Each segment is a disjoint, complete
script of four asks, so the sum is exact; the harness itself labelled every
cross-journal row "coverage, not movement", and no segment was compared on
unequal coverage.

| script | baseline | this fly | delta |
|---|---|---|---|
| count-frequency | 0/4 | 0/4 | 0 |
| order-first-last | 0/4 | 0/4 | 0 |
| conjunction-and-absence | 2/4 | 2/4 | 0 |
| exact-repeat | 1/4 | 1/4 | 0 |
| **hop-and-inventory** | 2/4 | **3/4** | **+1** |
| quantity-change | 1/4 | 1/4 | 0 |
| **TOTAL** | **6/24** | **7/24** | **+1** |

Against the frozen bar in the brief: **5/24 -> 7/24**. Against this tree's own
last campaign: **6/24 -> 7/24**.

**The ask that moved is the ask the gene was selected on.**
`hop-and-inventory::what does the thing the frost bites hold?` went
`shape_arbiter -> PASS`. Its memory span carries a relative clause -- "the thing
the frost bites" -- whose head is `thing` while the last content word is
`bites`; the fly's `w_first` 1.119 names the first content word, which is
exactly the construction `w_first` was rewarded for. **Zero regressions:** all
six baseline passes are retained (`what turns twice?`, `what bites the latch?`,
`what does the frost bite?`, `what is both wet and on the hook?`, `where did i
say the scarf is?`, `how many eggs broke?`), so nothing was traded away.

**Pre-committed reading, applied without reinterpretation:** 7/24 is above 6/24
and above 5/24, so this is the **first branch -- vindication: intrinsic gain
accompanied by real capability for the first time.** The head rule is a
candidate for the organ. Stated with it, because it is true and it bounds the
claim: `w_count` was **not applied** (the organ has no count branch), so the
parser gene contributed nothing to this number; the +1 comes from the head rule
alone, and the fly's advantage is one ask on one construction.

**What 7/24 is not.** It is not a capability point in the house: the shim
overrides a classmethod in a scoring process and no organ file changed. Landing
it means the full protocol -- the 24 again against the organ, the eight guard
scripts clean on a quiet machine, pytest -- and that has not been run.

## Landing attempt: the gain did not transfer, and the organ change was reverted

I implemented the rule the fly's advantage was attributed to, in the organ and
in the smallest principled form: **a determiner appearing after a content word
marks the start of an embedded noun phrase**, so the head is the last content
word before it -- `the thing the frost bites` -> `thing`; `the old bell the gate
holds` -> `bell`; a plain head-final NP has no second determiner and is
untouched. Unit-checked on five spans, pytest **428 passed, 3 skipped**.

Measured on the 24 against the **organ**, no shim, per-script segments:

| script | baseline | organ |
|---|---|---|
| count-frequency | 0/4 | 0/4 |
| order-first-last | 0/4 | 0/4 |
| conjunction-and-absence | 2/4 | 2/4 |
| exact-repeat | 1/4 | 1/4 |
| **hop-and-inventory** | 2/4 | **2/4** |
| quantity-change | 1/4 | 1/4 |
| **total** | **6/24** | **6/24** |

`what does the thing the frost bites hold?` is still `shape_arbiter`. **The +1
did not transfer.** The shim scored the whole weighted argmax -- `w_first`
1.119 against `w_pos` 1.0, with `w_prep` 0.099 and `w_len` 0.102 in the same
sum -- and the determiner cue is not the same rule: it fires only when a second
determiner is present, which is one construction, while the weighted rule moves
the head wherever the weights cross.

**Reverted.** `git checkout -- organs/neural_language.py`: 4017 lines, `before[-1]`
restored, `_span_head` gone, working tree clean, pytest green. An organ change
that scores exactly the baseline is not a landing, and it must not sit in the
live brain while the eight-script guard is unrun. **The axis's 7/24 remains a
shim result.** To land it, the weighted rule itself has to go into the organ --
and then it is the guard that decides, on a quiet machine, not the 24.

## Landing the weighted rule itself: refused by the first gate

The proxy was the wrong idea and the weights went in verbatim:
`w_first` 1.119446, `w_pos` 1.0, `w_len` 0.10172, `w_prep` 0.099128, scored over
the content words of the span as a single argmax, ties to the later word, with
the single-word fallback falling out of the arithmetic. Six unit spans passed,
including `the thing the frost bites` -> `thing`.

**pytest: 1 failed, 427 passed, 3 skipped.**

```
assert 'small' == 'bell'
tests/test_shape_filler_position.py:71
head of 'the small brass bell' is bell, got 'small'
```

The rule names the modifier as the head in a three-word span, because
`w_first` > `w_pos` and the fly's modifier class was **closed**:
`{old, copper, heavy}`. Its training material never contained another modifier,
so it learned "first content word" as though that were a general rule, and the
corpus -- `small`, `brass` -- is outside it. **The fly is overfitted to the
closed class it was scored on**, which is exactly the failure mode a synthetic
component invites.

**Gate order applied:** pytest is first, it is red, so the 24 was not run and
the eight guard scripts were not run. They were not reached; they did not pass.

Reverted again: 4017 lines, `before[-1]`, `_span_head` gone, tree clean,
**428 passed, 3 skipped**. Nothing landed, and the axis's 7/24 remains a shim
result -- now with a measured reason: the rule that produced it contradicts a
documented contract about spans the population never saw.

**What this says about the next cut.** The axis selected a rule that is right on
its own material and wrong one word outside it. Before any further landing, the
fitness has to contain spans whose modifiers are NOT a closed set the rule can
learn to strip -- otherwise every winner will be overfitted by construction, and
the guard or pytest will keep being the thing that finds out.

## THE CONFLICT, AND THE REAL FINDING: 7/24 IS A SHIM RESULT

Pre-registered here, as instructed: a **structural gene** -- a feature firing on
a second finite clause / relative marker inside the span -- conditioning the
head rule, floor frozen at the **6/24 organ baseline**, gate in order (pytest
incl. `test_shape_filler_position`, then the 24 with zero baseline passes lost,
then the eight guards).

**That conditional rule already ran, as the determiner cue** (`7fdd635`): pytest
**428 passed / 3 skipped**, the 24 against the organ **6/24**. It could not
reach 7/24, and I assumed the proxy was simply too weak. The diagnosis says
something worse, so it is recorded before any second attempt:

- The moved ask answers **`door`**, and the span it is read from is **one content
  word**. Every head rule in this log -- last, first, weighted, conditional --
  returns `door` for it. **The head cannot be what moved that ask.**
- Against the organ the same ask is `stage=shape_arbiter`, i.e. `_shape_matches`
  returned **None** -- a **veto** -- for the memory in question.
- `tools/_genome_patch.py` is built to recover exactly that: it calls the
  organ's matcher, and **if the organ returned None** it returns the fly's
  filler instead. `fly_head` does not implement `shape["subject"]` or the
  `shape["tail"]` walk, so it happily answers a memory the organ's matcher
  refused.

**So the +1 is a veto override, not a head correction.** The shim converts "he
refused" into "he answered", and once in 24 that landed on the wanted word. No
head rule can carry that, which is why every landing attempt measured 6/24 --
the proxy was not too weak, it was answering a different question.

**The conflict, stated as the finding: the fly's rule and the organ's contract
disagree, and the contract wins.** The organ requires the queried subject to be
present before the verb and requires the tail to walk; the fly's rule requires
neither. The shipped matcher keeps its guards; nothing lands. This was the one
attempt.

**Recorded, and it stays recorded until it is untrue:**

- **7/24 is a shim result.** It is one ask above the 6/24 organ baseline, and
  that ask was won by overriding a veto, not by naming a head better.
- **The axis still has zero landed capability points.** Nothing bred has changed
  the live brain's score.
- The measurement instrument has a defect of its own: a head-rule genome must
  **not** override a veto, because doing so scores the absence of a guard as
  capability. Until `_genome_patch.py` stops supplying fillers where the organ
  returned None, no number it produces can be read as a capability claim.

# Pre-registered: the instrument fix, and how the veto may be judged

Two defects, separated. Only the first is a patch defect.

## Defect 1, the instrument -- expected result stated before the run

`_genome_patch.py` will be changed so a veto stays a veto: when the organ's
matcher returns None, the patched call returns **None**, and the fly's
disagreement is *counted and printed* (`vetoes_respected`) instead of being
returned. Overriding becomes explicit and off by default.

**Predicted before running: the re-scored 24 is 6/24, identical to the organ
baseline, with the moved ask returning to `shape_arbiter`.** If it is anything
else, the fix is wrong and the difference is a bug in the patch, not a finding.

## Defect 2, the organ -- what the trace must show

The veto on `hop-and-inventory::what does the thing the frost bites hold?` is
**over-strict** if and only if the trace shows all three:

1. a candidate memory whose tokens contain the question's subject span before
   the shape verb -- i.e. the memory really is about *the thing the frost
   bites*;
2. that memory's answer genuinely is the wanted word (`door`);
3. the refusal comes from a **named, single clause** of `_shape_matches` --
   `shape["subject"]` (line ~2183), the `tail` walk (line ~2160), or the
   `vi is None` verb lookup -- and not from the absence of a subject span.

If instead the question's own `_question_shape` supplies no subject tokens, or
the only candidates that yield `door` are memories with no subject before the
verb, then **the veto was right and this ask is unanswerable by this organ**.
In that case there is no organ fix, and the corpus does not contain the
construction.

**What the fixed 24 must reach, either way:** floor **6/24**, with **zero of the
six baseline passes lost**. A matcher change is only worth landing if it moves
the ask for a named clause reason *and* keeps all six; a change that trades a
PASS for a PASS is not a capability point. The shim's 7/24 is not evidence for
any of this -- it was produced by overriding the thing under test.

## Result: 6/24 as predicted, and the veto was RIGHT

**Defect 1, the instrument, fixed.** `_genome_patch.py` now returns the organ's
None when the organ refused, counts the disagreement as `vetoes_respected`, and
prints it; overriding is behind `FLY_ALLOW_VETO_OVERRIDE` and off by default.
Re-scored, per script: 0, 0, 2, 1, **2**, 1 = **6/24**, exactly the organ
baseline and exactly what was predicted before the run. The ask is back to
`shape_arbiter`. **The 7/24 does not survive its own instrument**, and it is
withdrawn as a capability claim.

**Defect 2, the organ, named.** The honest instrument printed the sentence the
old one hid:

```
[genome] veto: 'door' on object_unknown over 'the latch holds the door'
```

- The question's shape is well formed: `object_unknown`, `subject ["thing"]`,
  `verb hold`.
- The only candidate that yields `door` is **`the latch holds the door`**.
- The refusing clause is **`shape["subject"]`** (`neural_language.py:2183`):
  `thing` does not appear before `hold` in that memory. Not the tail walk, not
  the verb lookup, not the head.

**By the pre-registered criterion the veto was RIGHT, and there is no organ
fix.** The ask is a two-memory hop: `the frost bites the latch` establishes what
the thing is, and `the latch holds the door` establishes what it holds. The
organ matches one memory against one question and correctly refuses a fragment
that only answers it if you join it to a second memory. The fly answered `door`
by dropping the subject guard -- that is not a better head rule, it is the
confabulation the arbiter exists to refuse, and it landed on the right word
because the corpus happens to be small.

**What this means for the ledger, unchanged and now explained:**

- **7/24 was never capability.** It was a guard bypass; the fixed instrument
  measures **6/24**.
- **The axis still has zero landed capability points.**
- The matcher is not over-strict on this ask and is **not touched**.
- The real capability candidate is **a hop across two memories** -- something
  the organ has no mechanism for at all. That is new capability work, not a
  matcher tweak, and it does not belong in this turn's gate.

Probe kept as `tools/veto_probe.py`; it raised a `TypeError` on its own instance
patch while reading the trace, which is a probe artifact and explicitly **not**
recorded as an organ defect.

# Pre-registered: the hop across two memories

The veto above was correct, and it names the missing mechanism exactly. The
question asks what *the thing the frost bites* holds. One memory says **the
frost bites the latch**; another says **the latch holds the door**. Neither
answers it alone. The organ matches one memory against one question, so it
refuses -- correctly -- and that refusal is the capability gap.

**Mechanism, uniform and ask-blind.** When, and only when, the arbiter vetoes:

1. Take the question's **subject span** (`what does [the thing the frost bites]
   hold?`). If it holds fewer than three content words, stop -- no hop.
2. Read it as a description with an embedded clause: its **last content word is
   the inner verb**, the content words between the head and that verb are the
   inner clause's subject.
3. Resolve the description with the organ's **own matcher**: find a memory the
   inner shape accepts (`the frost bites the latch`) and take the entity it
   names (`latch`). If no memory accepts it, stop -- no guess.
4. Re-run the **same** arbitration with the outer shape's subject replaced by
   that entity (`["latch"]`), against the same hits.

No ask is named in the code; no constant is fitted; one hop only, never
recursion; the entity always comes from a memory the matcher accepted.

**Floor and gate, in order.** Floor is the organ baseline **6/24**. The change
lands only if: pytest green including `test_shape_filler_position`; the 24
reaches **at least 7/24 with zero of the six baseline passes lost**; and then
the eight guard scripts stay clean on a quiet machine.

**Falsification, stated before the run.** If the ask does not move, the hop is
not the missing mechanism and is reverted. If any baseline pass is lost, the hop
is over-eager and is reverted. If a guard goes red while the 24 improves, **the
guard decides** and the conflict is logged, not the win. A number produced by
the veto-overriding shim plays no part in any of this.

## Result: the hop fired and did not resolve. Reverted, by its own falsifier.

Implemented as registered: `_question_shape` now carries `subject_span`,
`_hop_answer` reads a description's inner clause (`the thing the frost bites`
-> asks back `what does the frost bite`), resolves it with the organ's own
matcher, substitutes the entity and re-arbitrates. pytest **428 passed, 3
skipped** -- the change did not disturb the contract, unlike the weighted rule.

It still did not answer. The probe shows why, in two steps:

1. First attempt: the inner resolution searched the **outer** question's
   shortlist, where `the frost bites the latch` never appears (it is about a
   different subject), so it refused with `verb_not_in_memory`.
2. Second attempt: the resolution was given a fresh `binder.recall` of the inner
   content, which is the right shape of the fix -- but the hop still returned
   None, the trace carries no `hop` key, and the ask is still
   `verdict: veto`.

**Falsification fired: the ask did not move, so the hop is reverted** --
`git checkout -- organs/neural_language.py`, 4017 lines, `_hop_answer` and
`subject_span` gone, pytest **428 passed, 3 skipped**. Nothing landed, and the
24 was not re-run: a change that cannot answer the ask it was built for has no
claim on the score.

**What is actually unknown, and it is narrower than "hops are hard":** the
second attempt shows the substitution path runs, pytest stays green, and the
mechanism fails inside the resolution step -- most likely the binder's `recall`
contract (what a cue is, what a hit carries) rather than the hop logic. That is
the thing to pin down before the next attempt, by reading `binder.recall` and
its callers, not by another guess at the organ.

**Ledger, unchanged:** organ 6/24; axis zero landed capability points; 7/24
withdrawn; the eight guards were not run this turn because the 24 gate was never
reached.

## HOP AXIS CLOSED -- bounded attempt spent, contract did not explain it

The last try was bounded in advance: read `binder.recall` and its callers, and
implement only if the contract names a one-line cause for the inner resolution
returning None.

**Read (`organs/higher_cortex.py:455`, callers at `neural_language.py:2635`).**
The contract is: a cue is a plain list of words, recall stems each one itself
(`rows_for = {t: self.stem_rows(t)}`), it filters to "distinctive" words by his
own document frequency, and it returns memory dicts carrying `tokens`. That is
**exactly** what the failed hop passed it -- `['frost', 'bites']`, a list, and it
read `h["tokens"]` back. The contract admits no other refusal, and therefore
**does not explain the None.**

**So nothing was implemented, and the hop axis is closed.** The cause is a
runtime fact I am not allowed to chase by the bound that governed this attempt
-- an exception inside the hop's own `try`, or a disagreement between the
binder's hit shape and what the hop read -- and guessing at it again is the move
that already cost this log five failures.

**The finding is architectural, as predicted if it failed.** This organ asks one
memory one question, by design: `recall(cue, k)` returns candidates, and
`_shape_matches` judges each memory alone. A two-memory ask needs a mechanism
that does not exist yet, and the next attempt at it must **specify its contract
before it is built** -- what a resolved entity is, where it is stored, and how
it is fed back into a second judgement without weakening the veto. That is not a
retrieval variant; it is a new path.

**The veto stays.** `the latch holds the door` is still refused for a question
about *the thing*, and that refusal is correct. Making it pass would rebuild
`_genome_patch.py`'s defect inside the organ and void every number after it.

**Retrieval side closed.** The log has now recorded rank-reach, subtraction,
join, band-walk and hop. No further retrieval variant is the next item.

# The mouth/gating side, diagnosed

`tools/mouth_probe.py` replays the tells that precede one ask into a fresh
house, asks it, and prints the reply. Three defects, none of which touches the
arbiter:

| ask | said | the mouth's own reason |
|---|---|---|
| `say exactly the copper bell turns twice` | **"sold"** | meaning resonance 0.5725 |
| `did i ever tell you about the moon?` | *(silence)* | "it understood but did not feel like speaking", resonance 0.5819, threshold 0.55 |
| `does the door hold the frost?` | *(silence)* | same, 0.5738, threshold 0.55 |

**Defect A, rendering: an instruction to repeat is answered by resonance.**
Asked to say a sentence back, he says `sold` -- a word produced by meaning
resonance, unrelated to the instruction. Nothing in the path reads the
instruction as an instruction.

**Defect B, gating: a yes/no absence question is answered with silence.** He had
a resonance above his own threshold and chose not to speak. For
`did i ever tell you about the moon?` the true report is **`no`** -- he has no
memory of the moon at all -- and silence is not that report.

## Pre-registered: the echo path (defect A), before any code

**Contract.** An utterance beginning `say exactly …` is an **instruction to
repeat**, not a question. The reply is the remainder of the utterance, verbatim.
It is spoken only if that remainder is something he actually remembers -- every
content word of it present, in order, in one memory -- so the echo cannot
manufacture a sentence he never heard. If he does not remember it, he says he
cannot repeat it. The arbiter is not involved and no veto is relaxed.

**Gate, in order:** pytest green including `test_shape_filler_position`; the 24
organ-only must reach **7/24** -- the echo ask moving PASS -- with **zero of the
six baseline passes lost**; then the eight guard scripts on a quiet machine.

**Falsification.** If the echo ask does not move, the instruction path is not the
defect and it reverts. If any baseline pass is lost, it reverts. If a guard goes
red while the 24 improves, **the guard decides** and the conflict is logged.

**Defect B is deliberately NOT pre-registered here.** `did i ever tell you about
the moon` is an entity-absence question -- `moon` appears in no memory, so `no`
is a checkable true report. `does the door hold the frost` is different: both
words exist, and answering `no` there would be a closed-world assumption the
organ has no right to make from absence of a relation. Only the entity-absence
case gets a mechanism, and only after defect A is gated.

## Defect A verified, gated, and LANDED -- 7/24, organ only

**Guard precondition checked before any code**, as instructed:
`tools/echo_guard_probe.py` found **exactly one memory of 60000** containing the
content words in order --

```
MEMORIES: 60000      RECALL HITS: 40      GUARD CAN FIRE: True
MEMORIES CONTAINING THE SENTENCE IN ORDER: 1
    the copper bell turns twice
```

So case 1 holds: the verbatim path is answerable as posed and the
pre-registration stood unchanged. No amendment was needed.

**Implemented** as registered: `_echo_instruction`, reached **after** the
interrogative branch, firing only on the literal instruction `say exactly`, and
speaking the remainder verbatim only when one memory contains its content words
as an in-order subsequence.

**A cannot manufacture B's false `no`** -- three ways, all checked: it is
unreachable for interrogatives (a question returns from `answer()` before the
echo path is entered); it requires the literal `say exactly` prefix; and what it
speaks is the instruction's remainder, so it has no branch that can utter `no`.
Demonstrated on the asks themselves: after the change,
`did i ever tell you about the moon?` and `does the door hold the frost?` are
**still silent**, unchanged at 0.5819 and 0.5738 against the 0.55 threshold.

**Gate, in order:**

| gate | result |
|---|---|
| pytest incl. `test_shape_filler_position` | **428 passed, 3 skipped** |
| 24 organ-only, no shim | **7/24** (was 6/24) |
| baseline passes lost | **zero** -- all six retained |
| moved ask | `say exactly the copper bell turns twice`: mouth -> **PASS**, source `echo instruction` |
| eight guards, quiet machine | **reference 1.00/1.00, accumulation 1.00/1.00, discrimination 1.00/1.00, role_chain 1.00/1.00, switch_back 1.00/1.00, override 1.00/1.00, session_context 1.00/1.00, where_kept 1.00/1.00** -- every delta +0.00, warm and cold |

**THIS IS THE FIRST LANDED CAPABILITY POINT IN THE LOG.** Organ-only, no shim,
no veto relaxed: the live brain answers one more of the 24 than it did this
morning, and the eight guard scripts did not move.

**Precision about what it is.** The shim's withdrawn 7/24 was a *different* ask
won by overriding a veto; this 7/24 is the echo ask won by following an
instruction. The two must never be added, quoted together, or allowed to look
like one claim. The breeding axis still has **zero landed capability points** --
this one is organ work, landed by hand, and it says nothing about the population.

**What defect A is not.** It is not a question-answering improvement: it renders
an instruction. The remaining mouth failure in that script
(`which word did i use for the metal?`) is a different mechanism, and defect B
-- yes/no absence -- is still open and still unregistered.

# ORGAN FLOOR FROZEN: 7/24

**Frozen 2026-10-29, commit `92821ed`. The organ floor is 7/24.** Every future
cut is measured against it with the 24 organ-only, no shim; **any regression
below 7/24 reverts**, with no exception argued after the fact.

**And it is a narrow 7, exactly one ask above where the tree started:** the echo
path moved `say exactly the copper bell turns twice` and **nothing else moved**.
It works because the prefix is literal and the content is already in memory --
that is an instruction renderer, not general capability, and it must not be
allowed to stand in for the mouth axis, which still has four failures. Anyone
quoting "7/24" as movement on the mouth is quoting the wrong number.

## Pre-registered: the glossary path (defect C), before any code

`exact-repeat::which word did i use for the metal?` -- expected `copper`,
forbidding `bell`, `iron`, `gold`. Today: **0/1**, stage `mouth`.

**What the house actually gives the path.** The tells say only
`the copper bell turns twice`. Nothing states that copper is a metal. So the
answer cannot come from a taught fact; it has to come from **a closed category
lexicon intersected with what he actually heard in this session**. `iron` and
`gold` are forbidden because they exist in his 60000 corpus memories and he did
not say them here -- which makes session provenance, not the lexicon, the thing
being tested.

**Mechanism, uniform and ask-blind.**

1. Fire only on an utterance matching `which word did i [use|say] for the
   <category>` with a `<category>` in a small closed class (metals, first:
   copper, iron, gold, brass, steel, silver, tin, lead, bronze).
2. Candidate set = the words with **`who == "you"` and `when >= session_t0`**,
   which is the same provenance the second brain already trusts.
3. Answer = the **single** candidate that is in the category's set. **Zero or two
   matches means silence** -- an ambiguous glossary question is refused, not
   guessed at.
4. The reply is one word, the word he used.

**Hard stop, as instructed:** this path must not touch `_shape_matches`,
`_arbitrate_shape`, or any veto. If an implementation would need to relax an
arbiter veto to work, **stop and log the conflict instead of building it** --
`which` is not a shape this parser claims, and gaining a point by weakening the
arbiter is the `_genome_patch.py` defect wearing a different hat.

**Gate, in order.** pytest green including `test_shape_filler_position`; the 24
organ-only must reach **8/24** with **zero of the seven frozen passes lost**
(the six original plus the echo ask); then the eight guard scripts on a quiet
machine.

**Falsification.** If the ask does not move, the mechanism is wrong and reverts.
If any frozen pass is lost, it reverts. If a guard goes red while the 24
improves, **the guard decides** and the conflict is logged.

## Defect C landed: 8/24, organ only, zero frozen passes lost

| gate | result |
|---|---|
| pytest incl. `test_shape_filler_position` | **428 passed, 3 skipped** |
| 24 organ-only, no shim | **8/24** (from 7/24) |
| frozen passes lost | **zero** -- all seven retained |
| moved ask | `which word did i use for the metal?`: mouth -> **PASS**, source `glossary`, said `copper` |
| eight guards, quiet machine | **all eight 1.00 warm / 1.00 cold, every delta +0.00** |

**How it works, and what it is not.** `which word did i use for the metal?`
answers `copper` because a candidate must be a word with **`who == "you"` in
this session** -- provenance, the same signal the second brain already trusts --
and exactly **one** such word is in the closed `metal` set. `iron` and `gold` are
forbidden because they live in the 60000 corpus memories and he did not say them
here. Zero or two matches returns silence; the question's own words are excluded
because the question is bound to memory before the answer is computed.

**It relaxes no veto.** `which` is not one of the interrogatives this organ
routes to `answer()`, so `_question_shape` never claims it and `_shape_matches`
is never consulted: the path runs before retrieval ranks anything, and the
arbiter is untouched by construction, not by assertion.

**Two honest limits, recorded at landing time.** First, the lexicon holds
**one** category (`metal`); this is not a general glossary and a second category
would have to be justified separately, not slipped in. Second, a real behaviour
change was found while wiring it: the path returns **before** `hear()` on the
utterance path, so the glossary question is **not bound to memory** that turn
(the probe's session memory count went 2 -> 1). It is recorded rather than
hidden -- if anything later depends on him remembering that he was asked, this
is where to look.

# ORGAN FLOOR RAISED TO 8/24

**Frozen 2026-10-29, commit `92821ed` -> this landing. The floor is 8/24.** Every
future cut is measured against 8/24 organ-only; **any regression below 8/24
reverts.**

**What the two points are, stated so neither can inflate the mouth axis:** an
instruction renderer (`say exactly …`, literal prefix plus memory) and a
provenance glossary (one closed category, session scope). Both are narrow,
both are literal-pattern paths, and **neither is general capability**. The mouth
axis still has three failures and the gating axis still has two.

# Pre-registered: ordinal selection over session memories (defect D)

Two landed points were shortcuts -- a literal prefix, a closed set. This one is
not allowed to be. It must be a **general mechanism that also answers
constructions not in the 24**, and it is judged on that.

**The mouth failures it targets**, both `stage=mouth` today:
`which did i tell you first the lantern or the kettle?` -> `lantern`, and
`which did i tell you last the kettle or the gate?` -> `gate`. The tells are
`the lantern is lit`, `the kettle is singing`, `the gate is open`, in that order.

**Mechanism.** No literal prefix, no lexicon:

1. Trigger on an utterance that contains `which` and one of `first` / `last`.
2. Candidate set = **the content words of the utterance that appear in this
   session's `who == "you"` memories**. That is not a pattern match on phrasing:
   the question does not have to name its alternatives in any fixed position.
3. Answer = the candidate whose **earliest session memory is earliest** (for
   `first`) or **whose memory is latest** (for `last`). Ties, fewer than two
   candidates, or more than two: **silence**.
4. The arbiter is untouched -- `which` is not a shape this parser claims.

**Paraphrase check, written before the code, in the same house.** The mechanism
must answer all three, or the point is logged as **narrow, not capability**:

| # | paraphrase | required answer |
|---|---|---|
| P1 | `which did you tell me first, the lantern or the kettle?` | `lantern` |
| P2 | `of the lantern and the kettle, which did i say first?` | `lantern` |
| P3 | `between the gate and the kettle, which did i tell you last?` | `gate` |

P1 changes the pronoun and adds a comma; P2 puts the alternatives before the
question word and uses `and`; P3 reverses the pair and uses `between`.
A mechanism that only passes the two asks in the 24 has learned the phrasing,
not the thing, and says so.

**Gate, in order.** pytest incl. `test_shape_filler_position`; the 24 organ-only
must reach **9/24** with **zero of the eight frozen passes lost**; then the
eight guard scripts on a quiet machine.

**Non-negotiables.** Defect B (**yes/no absence**) stays closed: this mechanism
must not utter `no`, and no path may assert absence as a negative answer until
one exists that can express "absent from memory" without asserting a false no.

**Falsification.** If either target ask does not move, revert. If any frozen pass
is lost, revert. If a paraphrase fails while the 24 improves, the point is
logged **narrow** and the 24 gain does not count as capability. If a guard goes
red, the guard decides.

## Defect D landed: 10/24, and the paraphrase check passed

| gate | result |
|---|---|
| paraphrase check (written before the code) | **5/5** -- both targets and P1, P2, P3 |
| pytest incl. `test_shape_filler_position` | **428 passed, 3 skipped** |
| 24 organ-only, no shim | **10/24** (from 8/24) |
| frozen passes lost | **zero** -- all eight retained |
| moved asks | both `order-first-last` asks: 0/4 -> **2/4** |
| eight guards, quiet machine | **all eight 1.00 warm / 1.00 cold, every delta +0.00** |

**What generalised, measured not asserted.** `tools/ordinal_probe.py` asked the
two asks and the three rewrites in the same house:

```
target  PASS said='lantern'  which did i tell you first the lantern or the kettle?
target  PASS said='gate'     which did i tell you last the kettle or the gate?
P1      PASS said='lantern'  which did you tell me first, the lantern or the kettle?
P2      PASS said='lantern'  of the lantern and the kettle, which did i say first?
P3      PASS said='gate'     between the gate and the kettle, which did i tell you last?
```

The alternatives are not found by position: they are the question's content
words that appear in this session's `who == "you"` memories, so a rewrite may put
them before the question word (P2), change the pronoun (P1), or reverse the pair
and use `between` (P3). **That is the first landed point that is not a literal
prefix or a closed set.**

**What did NOT generalise, stated here so it cannot be overstated:**

- **Exactly two candidates.** Three or more, or a tie, returns silence.
- **It orders; it cannot count or walk.** `how many objects did i tell you about`
  (counting) and `what did i tell you about before the kettle` (predecessor) are
  both still failures, and neither is this mechanism.
- **When it refuses, the mouth still improvises.** The control
  `which did i tell you first the gate or the gate?` correctly fell through --
  and then the resonance path said **`sold`**. A refusal from this path is not
  silence, it is a fall-through to the mouth's old nonsense. That is recorded as
  an open defect, not papered over.

**Defect B stayed closed, and the harness proves it:** the ordinal path has no
branch that can utter `no`, and `count-frequency` -- which owns
`did i ever tell you about the moon?` -- is **still 0/4**, unchanged. The moon
ask was not converted into a false `no`; it is still refused.

# ORGAN FLOOR RAISED TO 10/24

**Frozen 2026-10-29. The floor is 10/24.** Every future cut is measured against
10/24 organ-only; **any regression below 10/24 reverts.**

Three points landed in this run of work -- an instruction renderer (8+1), a
provenance glossary, and ordinal selection. Only the third is general, and only
across pairs. The mouth axis still has one failure (`is the coat dry or wet?`)
and the gating axis still has two.

**Gates, unchanged and re-measured after the selection change:** null spread **0**
(10 clones, one genome id); base composite **0.250000**, strictly below 1.0;
reach **10/10 mutants differ from base fitness (100%)**; pytest **428 passed, 3
skipped** (the 407 in the brief is stale -- this tree has 428 with the fold and
head-rule tests).

## Pre-registration: the arbiter names the modifier, not the head (2026-10-28)

The render falsification exposed a sharper defect than the one it was testing,
and it is principled rather than per-ask.

**The defect.** `_shape_matches`, for a `subject_unknown` shape, returns
`before[0]` -- the FIRST content word of the subject span
(`organs/neural_language.py:2167`). English noun phrases are head-final:
determiners and modifiers precede the head, so in "the copper bell turns twice"
the head is `bell` and `before[0]` is `copper`. The matcher therefore names the
modifier whenever a subject has more than one content word -- a prediction
derivable from the sentence alone, without seeing the ask, which is what makes it
a defect and not a trade-off.

**The mechanism.** Take the head: the LAST content word of the subject span.
When the span is one word, last is first, so the stated fallback to `before[0]`
is automatic rather than a branch -- the change cannot alter any single-word
subject.

**This is not variant B.** Variant B failed because it asked a different organ
for the word: `role_of` answered `bites`, a verb, when the question was *what*.
This leaves the arbiter as both the gate on which memory and the source of the
word, and corrects which position in the span it reads.

**Prediction, written before measuring.** The change is a no-op wherever the
subject span is one content word, and every `subject_unknown` ask in
`tools/scripts.json` has one ("the kettle rings at noon" -> `kettle`, "the crow
follows the sparrow" -> `crow`). So the expected effect is: **exactly one
held-out ask moves** (`what turns twice?` -> `bell`), **zero house asks change**.
If more than one held-out ask moves, or any house ask changes, the no-op
prediction is wrong -- and that wrongness is the finding, not a bonus.

**Conditions (the operator's, verbatim in effect).**
1. `what turns twice?` moves to PASS speaking `bell`, with no `copper`;
2. no current PASS flips to fail;
3. measured on **all 24** independent, not a chunk, not the sequential path;
4. pytest green (414 passed / 3 skipped as of the fold tests; the standing gate
   was 407/3).
If it holds, it is the first capability point in eight cuts, and **all 8 guard
scripts run clean on a quiet machine before it is booked** -- six green under
load plus two green alone is not eight green on a quiet machine. If it flips a
PASS or the target still fails: revert, the mouth axis is closed for good, and
only then the numeral probe.

**Scope, deliberately not taken.** `after[0]` in the `object_unknown` branch
(`:2181`) carries the same head-final defect symmetrically: an object span of
two content words ("the heavy latch") would name the modifier there too. It is
**not** changed in this cut, because no held-out ask exercises a multi-word
object span, so a second mechanism would land unmeasured. Recorded as the
follow-up, not fixed on the argument that it must be the same bug.

## Result: the head fix lands, and the bar drifted underneath it (2026-10-28)

**The pre-registered fix alone was inert, and that is a finding, not a detour.**
With `before[-1]` in and nothing else changed, `what turns twice?` still failed
speaking `the copper bell turns twice` -- because the render path never read the
arbiter's filler. The head fix corrected what the arbiter *names*; nothing
consumed it. So the ruling as written entails both halves, and the cut as landed
is two edits: the position rule (`_shape_matches:2167`, `before[0]` ->
`before[-1]`) and the mouth saying the word the arbiter named
(`answer():2844`, `source='arbiter head'`, with the whole recalled proposition
kept as the fallback wherever there was no shape to verify). This is not variant
B: the arbiter remains both the gate on which memory and the source of the word.

**Conditions, met.** `what turns twice?` -> **PASS speaking exactly `bell`**, no
`copper` (`said` verified in the journal). All 24 independent, nothing else on
the machine: **6/24 = 0.250**, up one from the 5/24 bar. No current PASS flipped
under a contemporaneous control. pytest **414 passed, 3 skipped**. The no-op
prediction held: exactly one held-out ask moved, and the house suite is
unchanged.

**The guard, run as instructed.** All 8 scripts, four chunks of two, with nothing
else running: **warm 1.00 / cold 1.00 in every chunk**, `override` winners
correct (`hot`, `hot`). Eight green on a quiet machine, not six-plus-two.

**And the instrument moved.** `order-first-last` came back 0/4 (was 2/4) and
`conjunction-and-absence` 2/4 (was 0/4). Neither is this cut's doing: the control
-- the committed tree with both edits removed, same hour, same quiet machine --
reproduces **order 0/4 and conjunction 2/4 exactly**, with the same confabulated
words (`sold`, `bridle gargery`) and the same 55%/58% coverage refusals. The
score held at 5/24 across campaigns while the **pass set** changed membership.
So the independent bar is reproducible in aggregate and not in composition: a
+/-2 shift inside one script is inside the noise of the instrument, and only a
movement verified on both trees, in the same hour, counts. That is how the target
ask's PASS was accepted (FAIL on the committed tree twice, PASS on the cut tree
with `bell`) and how the other four shifts were rejected as drift.

**What the mouth axis now means.** The falsification did not close the axis; it
located the defect one level down, in the arbiter's position rule rather than in
the framing. Variant B stays rejected for the reason it was measured: `role_of`
answers verbs (`bites`) when the question is *what*. What remains on the mouth
label is retrieval fallthrough -- `sold`, `amethyst solomon tallied`, `bridle
gargery` -- which is not a mouth at all.

**Untouched, and next.** `how many eggs are left in the basket?` still says
`there are four eggs in the basket` and `how many times does the bell turn?`
still refuses at 42% coverage. Both have `shape = None` -- `how` is not `what` or
`where` -- so this cut never reached them. The numeral claim stands as the next
probe, unstarted. `after[0]` for multi-word objects stays as recorded, unfixed
and unmeasured.

## Retraction: the bar did not drift; I misread it (2026-10-28)

The entry above says the independent bar is "reproducible in aggregate and not
in composition", and records `order-first-last` 2/4 -> 0/4 with
`conjunction-and-absence` 0/4 -> 2/4 as a membership change on an unchanged
tree. **That is false, and the mechanism that produced it was mine, not the
house's.**

With the pass set emitted as a field and the two campaigns diffed mechanically:
`base_prestore` **4/24**, `eggs` **5/24**, this cut **6/24** -- and each adjacent
pair differs by **exactly one ask**. `order-first-last` was 0/4 and
`conjunction-and-absence` was 2/4 in every campaign, including the base. There
was no shift to explain.

What happened: I compared today's numbers against a recollection of the earlier
per-script scores that had been folded out of my context, and never re-read the
journal to check it. When the two disagreed I invented the drift story -- and the
control I ran to test it (committed tree: order 0/4, conjunction 2/4, identical
to the cut tree) actually **disproved** the story, and I read it as confirmation
because I was reading it as evidence about the bar rather than about my own
notes.

Two consequences, both corrections of things recorded in this log:

1. **The stemmer fold was not delta zero.** `how many eggs broke?` moved
   `recall -> PASS` on the fold. It was a capability point, and I reported that
   it gained nothing.
2. **The standing rule needs a source of truth, not a promise.** "Only movement
   verified on both trees in the same hour counts" was a process rule I was
   already failing to keep. It is now a field: every campaign report carries
   `pass_set` and `attribution`, the journal carries an ask id per row, and
   `--compare A B` prints the two side by side and names every difference. The
   rule is checkable against the record instead of against my memory.

The lesson, stated plainly: a campaign is never compared against recollection.
It is compared against the journal.

## Pre-registration: the object span carries the same positional defect

**The hypothesis is a PAIR of edits, said up front.** Last cut established that a
positional rule changes nothing until the mouth consumes what the arbiter names.
Here the second half is **already in the tree** -- `source='arbiter head'` from
`9fdb53f` speaks the arbiter's filler for every shape, objects included. So this
cut adds only the position rule, and it is **not** expected to be inert the way
the subject's single edit was. Expecting inertness here would be a mistake in the
opposite direction: the consumption half landed already.

**The rule.** For `object_unknown`, the head of the object span is its LAST
content word: `after[0]` -> `after[-1]`. When the span is one word, last is
first, so the stated fallback is automatic and no single-word object can change.

**Falsification, written before the edit.** The prediction that matters is a
**no-op on both suites**, and it is checkable: no ask in `tools/scripts.json` and
none in the held-out 24 exercises an object span of more than one content word.
`what does the frost bite?` resolves against "the frost bites the latch", where
`after` is `['latch']`; `what does the thing the frost bites hold?` vetoes at the
subject test before `after` is ever read. Therefore:

1. the pass set must be **unchanged** -- 6/24 with the same six asks, diffed with
   `--compare` rather than eyeballed;
2. the guard must stay 1.00/1.00 on all 8 scripts, clean;
3. pytest green (414/3 plus the new tests).

If any ask moves, the no-op prediction is wrong and **that movement is the
finding, in whichever direction it points** -- not a bonus and not to be kept by
arguing the direction is favourable.

**The rule itself is verified at the only level that can see it.** A unit test
hands `_shape_matches` a multi-word object span ("the frost holds the heavy
latch") and requires `latch`, with the single-word fallback and the already-landed
subject head pinned beside it. If a test cannot distinguish first from last, then
this path is unmeasurable by the suites and must be recorded as unmeasurable
rather than booked as a fix.

**No point is claimed here.** This buys correctness on a path no current ask
walks. The reason to do it anyway is that the alternative is a latent twin of a
bug that was just proven real, discovered later by an ask that does walk it -- and
the honest record of "landed, no score change, verified by unit only" is what
keeps that from being reported later as a gain it never was.

## Result: the object head lands and moves nothing, as pre-registered (2026-10-28)

**The rule landed.** `_shape_matches` `object_unknown` returns `after[-1]`
(`organs/neural_language.py:2181`), the head of the object span, with the
single-word fallback automatic because last is first.

**Verified at the level that can see it.** `tests/test_shape_filler_position.py`,
5 tests, 3.7s: a multi-word object span ("the frost holds the heavy latch")
yields `latch` and explicitly not `heavy`; a three-word subject span yields the
head; single-word spans are unaffected. The last test asserts the tests are not
vacuous -- it requires the span to hold at least two content words whose first and
last differ before treating the result as evidence about heads. Without that
clause, a one-word span passes any position rule and the file would prove nothing.

**The no-op prediction held, as a field.** All 24 independent: **6/24 = 0.250**.
`--compare` against the previous cut's journal: **`asks whose outcome or stage
differs: 0`**, score delta `+0`. Not an eyeballed "looks the same" -- the
membership is identical, which is what the pre-registration asked for.

**pytest 419 passed, 3 skipped** (414 plus the 5 new). **Guard: all 8 scripts,
four chunks, nothing else running -- warm 1.00 / cold 1.00, `live_files_untouched`
True on every row.**

**No capability point is claimed for this cut.** It landed, it is correct, and
neither suite can tell. That distinction is the record, not a shortfall.

**The instrument change landed with it.** Every campaign report now carries
`pass_set` and `attribution` (ask id -> outcome or stage); every journal row
carries an ask id; `--compare A B` prints the two campaigns side by side and names
every difference. Rows present on one side only are labelled **coverage, not
movement** -- without that, this cut's partial journal against a whole one read as
17 differences where there was 1, which is precisely the error that produced the
retracted drift claim above.

**Where the bar actually stands**, from the journals rather than from my notes:
`base_prestore` 4/24 -> stemmer fold 5/24 -> arbiter head 6/24, each step differing
by exactly one ask. Two capability points in eight cuts, both now checkable
against the record.

**Next, unstarted:** the numeral claim. Both numeral asks have `shape = None`
(`how` is not `what` or `where`), so neither the subject nor the object rule
reaches them.

## Judgment: the object head is booked as landed with no point, and the mouth axis closes

Judged on the terms written before the edit, not on the number afterwards.

**Which branch governs, and why it is not the other one.** The edit *landed* --
the rule is in the tree and does what was claimed at the level the unit test can
see. It was also *inert*, but inertness has two different causes and the
pre-registration named which one this was: **no ask walks a multi-word object
span**, not "the mouth does not consume what the arbiter names". Consumption was
already in the tree from `9fdb53f`, so this cut could not have tested the
pair-hypothesis either way. Treating its silence as confirmation of that
hypothesis would be the same move I just retracted above -- reading a control as
evidence -- so it is refused here explicitly.

**Therefore no revert.** `after[-1]` executes on every `object_unknown` ask
today; it is a live path with a one-word span, not dead code. Reverting it
restores a rule that is wrong in the same shape as the one that cost the last
target ask, on a path no suite can catch it on. The cut is booked as
**landed-and-verified, zero score movement, no capability point** -- which is
what was pre-registered, and the number did not talk me out of it.

**The pair-hypothesis evidence, checked against the record rather than argued.**
The head-fix-alone campaign (`heldout_ind_headfix_only.jsonl`, 8 rows) shows for
`what turns twice?`:

    said = 'the copper bell turns twice'   why = forbidden word said: copper
    stage = shape_arbiter

The mouth **recited the recalled proposition** -- which contains the forbidden
word -- instead of speaking a filler. So consumption really was the missing half.
But two things about that record are uncomfortable and are now fixed rather than
explained:

1. The stage label could not have shown it. `stage_of` returns `shape_arbiter`
   both when the arbiter refuses and when it names a filler the answer ignores
   (`tools/heldout_eval.py:129-145`), so the label alone never proved which half
   was missing -- the proof is in `said`, which I had not read before now.
2. **The journal never stored which filler the arbiter named.** The half of the
   claim that says "nothing consumed *the filler*" was carried only by console
   output that no longer exists. Journal rows now carry `source` and `filler`
   beside `said`, so a moved ask can be explained from the record, not just named.

**The mouth axis closes.** Subject head landed and scored (+1); object head
landed and is unit-pinned with no score movement; the render path was falsified on
two variants and exonerated; consumption is proven necessary and is in place.
There is no third edit to spend on rendering and none is planned. The next and
last mouth-family item is the **numeral claim**: both numeral asks arrive with
`shape = None` because `how` is neither `what` nor `where`, so no positional rule
and no render change can reach them -- it is a shape-coverage question, not a
speech question.

**Instrument, since the point of it is that it runs itself.** A campaign now
archives the journal it replaces and prints the side-by-side at the end
unasked -- verified live, hop-and-inventory re-run on the current tree came back
2/4 with `differs: 0` over the shared asks, matching the committed record. That
run also exposed a bad number in the new tool: it printed `score delta -4` while
comparing 6/24 against 2/4, two different ask sets. An unequal-coverage diff now
refuses the raw delta and reports only the asks both campaigns ran. Five tests
pin the diff itself (`tests/test_pass_set_compare.py`, 0.26s), including the
case that burned me -- equal pass counts over different asks -- and the case that
must not be counted: one-sided rows are coverage, not movement.

**pytest 424 passed, 3 skipped** at the time of writing. No new campaign was run
for this judgment, on the grounds that no organ code had changed since the 24-ask
campaign that produced the table above.

## The third campaign, and two bugs the instrument found in itself

That last sentence was overtaken within the hour, for a reason that has nothing
to do with wanting a better number: **the auto-diff only fires on a whole
campaign, and a whole campaign had never actually gone through it.** Testing an
instrument means running the path, not the score.

Two things came out of running it.

**The foreground shell cannot hold a whole campaign.** 24 asks take ~750s against
a 590s cap; the killed run left an 18-row journal sitting in the live slot, which
is exactly the kind of half-record that gets read as a campaign later. It is
moved aside and named `heldout_ind_partial_killed_2232.jsonl`. The campaign runs
as a background job instead.

**The control was wrong.** The whole run diffed itself against
`heldout_ind_prev_20261028_222257.jsonl` -- a **4-ask chunk** -- because the
fullest-archive preference lived only on the branch where a live journal exists to
be archived. With no live journal (I had moved it aside by hand), the code fell
through to "newest archive", which was the chunk. Newest is not a control.
`prior_campaign()` now picks the **fullest** archived journal, ties going to the
freshest write, and four tests pin exactly that, including the failure it was
built from.

**And the delta was lying.** The same run printed `score delta -4` while comparing
6/24 against 2/4 -- two different ask sets. That is a meaningless subtraction that
wears the costume of a regression, and it is the direct ancestor of the misreading
I retracted earlier today. An unequal-coverage diff now refuses the raw delta and
reports only the asks **both** campaigns ran, labelled as the only comparable
number.

**The number itself**, from the whole campaign on this tree, diffed 24-against-24
against the previous whole campaign:

    A 6/24 = 0.250   B 6/24 = 0.250   score delta +0
    asks whose outcome or stage differs: 0

So the no-op is now reproduced across **two independent whole campaigns**, not
asserted from one. **pytest 428 passed, 3 skipped.** The judgment above stands
unchanged -- landed, verified, no point booked -- and the mouth axis stays closed.
Next and last mouth-family item: the numeral claim, where both asks arrive with
`shape = None`.
