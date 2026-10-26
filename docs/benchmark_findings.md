# Benchmark findings: why the warm scripts fail

Measured 2026-10-25. Benchmark run `state/fitness/benchmark_20261025_171944.json`
(6 scripts, one session, 2 beats between turns); diagnostic replay
`tools/diagnose_recall.py` (session `diag_20261025_172845`) captured the full
`answer()` retrieval traces the benchmark reports drop.

## What passed and what failed

| script | result | detail |
|---|---|---|
| reference | 2/2 | "what rings at noon" -> "the kettle rings at noon"; "what shines at midnight" -> "the lantern shines at midnight" |
| accumulation | 1/2 | "how is the box" -> "the box is heavy" PASS; "where is the box" -> "droso says the box is heavy" FAIL |
| discrimination | 1/2 | "how is the street" -> "the street is loud" PASS; "how is the garden" -> "the garden is calm" FAIL |

Storage is not the problem. All six taught propositions are in the binder with
count 1, the SAN rows moved (rows_changed > 0, total weight net -10%), and the
raw recall on `["box"]` / `["garden"]` returns the taught facts. Every failure
is a retrieval/ranking failure.

## Failure 1: "where is the box" -> "droso says the box is heavy"

Three mechanisms stack:

1. **The role vote cannot express "location".** `role_for('where') = 3`
   (votes: role 2 x133, role 3 x3142) and `role_for('how') = 3` (2:79, 3:2754):
   the same slot for both question words, because the graded corpus answered
   both with short 4-token propositions ("the garden is here" -> role 3 =
   "here"). In the 6-token location proposition `the box is on the shelf`,
   role 3 is "**on**" (idf 3.106); the location word "shelf" sits at role 5,
   unreachable. The location proposition therefore competes with filler "on",
   the weakest possible answer word.
2. **His own rehearsed answer is a proposition.** The earlier reply "the box is
   heavy" was heard back and bound as `droso says the box is heavy`. Its
   role-3 filler is "**box**", the question's own word, idf 7.326, the
   highest of any candidate.
3. **The informative sort ranks filler idf above the not-in-cue guard.** The
   key is `(overlap, expected, filler_idf, not_in_cset)` descending
   (neural_language.py:2004-2008). "droso says the box is heavy" keys
   `[2, 0, 7.326, 0]` and beats "the box is heavy" `[2, 0, 6.761, 1]`: a
   filler that IS the question word outranks a filler that is not, because
   idf is compared first. He answers "where is the box" with a repetition of
   the earlier answer, prefixed "droso says".

The learned answer-type prior (`answer_types['where'] = {'here': 3216,
'home': 59}`) gives every candidate here `expected = 0`, so it does not decide
this one; filler idf does.

## Failure 2: "how is the garden" -> "the garden is calm" (session fact loses)

The expected-answer-type term swamps everything else. The graded corpus
answered "how" with "calm" **2651** times and with "quiet" **59** times:

```
the garden is calm   key = [2, 2651, 6.093, 1]   <- wins
the garden is quiet  key = [2,   59, 6.297, 1]   <- the session fact
```

Weight 0.5 x (2651 - 59) = 1296 from the prior vs 0.25 x (6.297 - 6.093) =
0.05 from filler idf. The session fact never had a chance: any predicate the
training QA corpus did not repeatedly pair with the question word loses to one
it did, regardless of what was just said in the session. (The street probe
passed only because "loud" had no training prior to fight: `answer_types['how']`
has no "loud" entry, so both candidates sat at expected = 0 and idf decided.)

## Failure 3: SAN nnz unchanged (66,107,030 -> 66,107,030)

Not a broken write: a saturated graph. The word-cell pair matrix is 49.5%
occupied (66.1M of 133.5M possible pairs), and every cross-cell pair between
the footprint cells of the scripts' words is already nonzero before the
session, mostly as residual weights from decayed training writes:

```
box x shelf     144/144 wired, max 0.000   (residuals ~1e-8)
box x heavy     144/144 wired, max 0.000
kettle x noon   144/144 wired, max 0.000
street x loud   144/144 wired, max 2.941   (real training weight)
lantern x midnight 144/144 wired, max 3.804
```

The Hebb write only increments existing entries, so an ordinary word pair can
never create a new edge: after 60k propositions plus books, every plausible
pair has co-occurred at least once. The top-k write is sparse in magnitude,
not in graph coverage. "New edges" as a trace metric is dead for common words;
row-weight movement (which did happen) is the live signal.

## Secondary observations

- The questions themselves become propositions: `binder.recall(['box'])` ranks
  "how is the box" (sim 0.784) and "where is the box" (0.743) ABOVE the taught
  facts "the box is red" (0.723) and "the box is heavy" (0.700). The
  interrogative filter keeps him from answering with the question, but
  question-shaped propositions pollute the candidate pool.
- The reference script passes because its propositions are the ONLY ones
  sharing their content words ("kettle", "lantern", "noon", "midnight" are
  rare): overlap 3 vs 2, no competition. The failures are all cases where
  training memory holds competing propositions for the same cue.
- `answer_types['how'] = {'calm': 2651, 'warm': 64, 'bright': 59, 'quiet': 59}`
  shows the graded corpus was highly repetitive ("how is the garden?" ->
  "the garden is calm" thousands of times). The priors are corpus artifacts,
  not knowledge.

## Where a fix would go (not implemented)

1. Role assignment: `role_for`/`answer_types` (neural_language.py:1791-1817).
   "where" needs a location role, which for long propositions is not role
   3; either per-proposition role inference or a role vote conditioned on
   proposition length.
2. Sort key order (neural_language.py:2004-2008): `not_in_cset` should outrank
   `filler_idf`: a filler that is the question's own word is never the
   answer.
3. Answer-type prior weight: the `expected` term (0.5) should decay with
   session recency: a fact heard this session should outrank a 2651-vote
   training prior, or at least the prior should be normalized (2651 vs 59 is
   a corpus repetition artifact, not a knowledge difference).
4. Self-rehearsal propositions ("droso says ...") should be marked at bind
   time and excluded from answering candidates.
5. The benchmark's trace metric: replace "new_edges" with row-weight movement
   (already measured) or count pairs crossing a weight threshold.

## Appendix (same day, evening): the session_context script

Added a seventh script to `tools/scripts.json` to test what the six above do
not: two tells that share a subject and a predicate and differ only in modifier
and time ("the kettle rings at noon" taught first, then "the iron kettle shines
at dawn"). The new pair exists nowhere in his 60,000 stored propositions
(verified against the binder before writing the script), so a cold run cannot
recall it.

- **Warm 2/2** (`state/fitness/conversation_session_context_warm.json`):
  "what shines at dawn" -> "the iron kettle shines at dawn" (the new tell,
  recalled verbatim, winner "iron"); "what rings at noon" -> "the kettle rings
  at noon" (the reference tell). Right tell for the right question, no blend.
- **Cold 2/2** (`conversation_session_context_cold.json`): silence on the new
  pair (closest memory covers 41% of the question, below the speech
  threshold), corpus fragment on the reference pair ("through at noon with a
  stray penny my"). The cold grader auto-derives `must_not` from the taught
  words, so both pass by absence.

The pass counts therefore do not discriminate warm from cold; the reply
content does. Warm answers with the taught proposition; cold is silent or
answers with a corpus fragment that shares only the question's own words. The
`must_not_contain` guards are what make the warm passes meaningful: an answer
from the wrong tell, or a blend of the two, would have failed.

Harness hardening in the same session: the probe guard in `tools/converse.py`
watched nine named files, one of which (`language_state.json.san.npy`) does not
exist: the real SAN file is `language_state.san.npy` (the save code's
`with_suffix` replaces ".json" instead of appending), so a session that wrote
the Hebbian weights would have gone unreported. The guard now snapshots the
whole `state/` tree minus the harness's own outputs (`sessions/`, `fitness/`)
and compares sizes and mtimes before/after; a file that appears or disappears
counts as moved. Pinned by `tests/test_guard_tree.py`; both runs above report
`live state files untouched: yes`.