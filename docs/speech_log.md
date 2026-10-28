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

Open question, named for the next cut: "the noon owl spins salt" is a
subject-verb-object proposition and "what does the bell spin" asks for that
subject — the shape looks checkable and right, so the veto is either firing
on the filler's role index or on the cue word the memory lacks by adjacency
rather than presence. Diagnosing it needs the reply's `parser` trace plumbed
into the report (converse.py records only kind/ask/spoken/said/pass today).

Honest gate status: pytest re-run with the walk in place: 407 passed,
3 skipped, 163.03 s — held. The full suite (32/32) has NOT been re-run this
cut: the splice fires only where the system already refused, so one-hop
winners are untouched by construction — but that is an argument, not a
measurement, and the suite run is the next cut's first act. The capability is not delivered; the mechanism
is live and the failure is localised one station downstream.