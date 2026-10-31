# E10 result: REFUTED, aborted at pre-registered conditions 1 and 4

`RESONANCE_CONTENT_SCOPE` + `RESONANCE_SESSION_SCOPE` produced **exactly the same battery
outcome as E9's scope-alone arm**: 19/24 frozen, 0/14 probes, 4/4 guarded, stages
`{recall: 17, shape_arbiter: 2}`, seven asks silent. Adding the content filter changed
nothing measurable at the level of the score, the stages, or a single pass verdict.

Arms: genome `abffa2b7f101`, `--tier frozen,probe`, 42 asks each, one line per arm.
Arm A = generation 13 (both flags off). Arm B = generation 14 (`--resonance-scope
--resonance-content`). Both `clean`, both **exit 0** — no state-guard alarm this run.

| arm | frozen | probes | guarded | verdict | exit |
|---|---|---|---|---|---|
| gen 11 pre-E10 | 19/24 | 0/14 | 4/4 | clean | 1 (known false alarm) |
| **gen 13 arm A** | **19/24** | **0/14** | **4/4** | clean | **0** |
| **gen 14 arm B** | **19/24** | **0/14** | **4/4** | clean | **0** |

Harness summary lines `g13-1` and `g14-1`, both `19/24  0/14  4/4  clean -`.
Zero asks gained, zero lost.

## Predictions

- **P1 flag-off identity — PASS.** Arm A vs generation 11: same 42-ask set, **0 field
  differences** across `pass`, `stage`, `cause`, `source`, `coverage`.
- **P2 the content filter engages — MIXED, 1/4.** `the` is removed on **all four** asks
  (pool 7→6, 7→6, 5→4, 8→7). But `is` and `on` **survive** on three of four. The filter
  engages; it does not do what a function-word filter does.
- **P3 both attractor classes gone — MIXED, 1/4.** Corpus attractors `numbered`/`sold`/
  `agin` are absent on **all four** (scope working exactly as in E9). Function words are
  fully absent on only the echo ask.
- **P4 the wanted word wins — MIXED, 2/4.** `bell` wins the echo pool (rank 1 of 4) and
  `lantern` wins the order pool (rank 1 of 7, at 0.4129). **`scarf` loses both conjunction
  asks at rank 5 of 6**, behind `is` 0.2459 / `on` 0.2043 / `coat` 0.1663 / `hook` 0.1586.
- **P5 zero erosion — PASS.** No frozen pass lost, no guarded pass lost, guarded 4/4,
  frozen 19/24. All five `banc_brain.npz` copies byte-identical to seal `546adb1bb8e433c3`
  (1 distinct sha256 across 5 files). **Displacement census unchanged: 60,000 rows**,
  `book` 59,515 (99.19%) / `droso` 466 / `parent` 19 / `you` 0, 59,665 rows at count 1 —
  identical to the pre-E9 census, as expected since a selection battery teaches nothing.
- **P6 no new babble — PASS.** No ask gained a source (27 speaking in A, 23 in B). Four
  **went silent**: the four mouth asks. Nothing was traded for a different wrong word.
- **P7 the score rises — FAIL.** 0/14 → **0/14**. The winner clears `reply_threshold` on
  **0 of 4** asks; the best winner anywhere is `lantern` at **0.4129** against a 0.55 bar.

## The pre-registered prediction was right

The pre-registration stated before running:

> **P4 will pass and P7 will fail, and the organ will stay silent.** … Filtering the pool
> changes **which** word wins, not the scores — `res` is computed once over the full
> vocabulary before any filter runs.

The 4-build pre-flight (`docs/evidence/e10_scope_probe.py`, ~2 min) confirmed it before the
84-build battery was committed: `predicted_silent: 4/4`, `P7_winner_clears_threshold: NONE
(0/4)`. P4 came in slightly worse than predicted (2/4, not 4/4) because `scarf` loses to
`is` and `on`, which the content filter does not remove.

**Abort conditions 1 and 4 are both met.** Condition 1: the wanted word still loses its
content-scoped pool (2 of 4). Condition 4: the winner is below `reply_threshold` on all
four, so the repair produces silence rather than speech. E10 is abandoned, not widened.

## Finding 1: the distributional rule is not a function-word rule

This is the substantive negative, and it is about the *principled distinction* the task
asked for. I deliberately avoided a stopword list and reused the organ's own recall-gate
rule, `df > 0 and df * 4 <= n_mem` — "distinctive iff it occurs in at most a quarter of
his memories". It removes `the` (df ≈ 59,000 of 60,000) and keeps `scarf` (df 14). But it
**keeps `is` and `on`**, because in this binder they occur in fewer than a quarter of rows.

The reason is the corpus: the binder is **99.19% `book` rows**, and in that corpus `the` is
near-ubiquitous while `is` and `on` are merely common. So "distinctive in my memory" and
"content word in English" come apart, and they come apart in the direction that matters —
the residue that beats `scarf` is precisely the function words the rule was supposed to
catch.

A distributional rule is only as good as the distribution it is measured against. With a
99% single-source corpus, document frequency measures **corpus style**, not lexical class.
This does not argue for going back to a hand-written list; it argues that neither is
available here until the binder holds something other than one book.

## Finding 2: once the organ is silent, filtering cannot help

Arm B is indistinguishable from E9's arm B at every level the battery measures — same
19/24, same 0/14, same 4/4, same `{recall: 17, shape_arbiter: 2}`, same seven silences.
That is not a coincidence. E9 already drove the winner below 0.55; removing *more*
candidates from a pool whose argmax cannot clear the bar leaves the verdict unchanged.

The ranking repair is **downstream of the real blocker**. Both E9 and E10 improve which word
would be chosen, and neither can make the organ choose to speak.

## Finding 3, confirmed twice: `reply_threshold` is the binding constraint

E9 found `understands` on the resonance path is `res[best] >= 0.55` and that in the control
arm the bar was cleared only by corpus attractors (`numbered` 0.5811, `sold` 0.5722). E10
measures the ceiling for honest content words: **`lantern` 0.4129, `bell` 0.1221, `scarf`
0.1526**. Nothing a session actually taught reaches 0.55.

So on this path **comprehension and attractor are the same event**: the only words that can
make the organism report understanding are high-frequency corpus words unrelated to the
question. The threshold was not calibrated to comprehension, it was calibrated to sit just
inside the attractor band (0.550–0.581), which is why the organism babbled confidently
instead of staying quiet.

Both repairs are forbidden from moving it, correctly: lowering it below ~0.41 would make
`lantern` speak — and would equally make `is` (0.2459→ no) or any moderately resonant corpus
word speak on asks where it is wrong. There is no threshold that separates them, which was
E9's `test_no_threshold_separates_attractor_from_wanted_word` and is now measured again from
the other side.

## What stands and what falls

**Stands.** The `mouth` class is a resonance defect. The pool is unscoped at 11,439 words.
The corpus attractor is ask-independent. Session scope removes it as a candidate (P3's
corpus half, 4/4). Content scope removes `the` (4/4). `lantern` and `bell` do win their
filtered pools.

**Falls.** That removing the attractors would let the organism answer. It cannot, because
the winner then sits below the speaking bar. The candidate pool was never the binding
constraint — `reply_threshold` is.

**New.** A distributional content/function rule measured against a 99% single-source corpus
classifies `is` and `on` as content words. Any future repair that needs a lexical-class
distinction cannot get one from binder document frequency until the binder is not one book.

## Disposition

Both genes stay in the organ, default `False`, inert, with these results recorded beside
them — `RESONANCE_SESSION_SCOPE` (E9) and `RESONANCE_CONTENT_SCOPE` (E10), joining
`RECALL_UNFILTERED_FALLBACK` (E7) and the three E5 shape genes. Four measured negatives,
all kept for the same reason: deleting a refuted gene invites someone to retry it.

The forbidden-on-abort list was respected: `reply_threshold` untouched at 0.55, no stopword
list added, no resonance rescaling, no widening to "recent" words, no change to the recall
gate's `must` rule.

**Not attempted, and the honest next question.** The blocker is now localised to a single
scalar whose value encodes "a corpus attractor is present" rather than "the question was
understood". Repairing it is not a threshold tweak — it needs a comprehension signal that
is not `max(resonance)`, which is organ-design work well beyond a flag-gated experiment and
outside this task's no-broad-refactor constraint.

## Reproduce

```
.venv\Scripts\python.exe docs\evidence\e10_scope_probe.py     # pre-flight, 4 builds
.venv\Scripts\python.exe tools\run_generation.py --generation 13 --lines 1 --tier frozen,probe
.venv\Scripts\python.exe tools\run_generation.py --generation 14 --lines 1 --tier frozen,probe --resonance-scope --resonance-content
.venv\Scripts\python.exe docs\evidence\e10_analysis.py
```

Journals: `state/selection/generation_13{,_asks}.jsonl`, `generation_14{,_asks}.jsonl`.
Probe: `docs/evidence/e10_scope_probe.json`. Cost: 4 pre-flight + 84 battery builds, ~38 min.

**Caveat.** `e10_analysis.py`'s `summary()` looks for score keys the generation journal
does not carry and prints `[{}]`; the authoritative figures are the harness's own summary
column quoted above. Its ask-for-ask comparisons (P1, P4 gained/lost, P5, P6) read fields
that do exist and are correct.
