# E9 result: REFUTED, aborted at the pre-registered condition

`RESONANCE_SESSION_SCOPE` did exactly what the diagnosis said it would do to the
candidate pool, and the repair still failed. **P2 PASS, P3 PASS, P4 FAIL.** The
pre-registered abort condition fired, so the repair is abandoned rather than widened.
The flag stays default-off and inert.

Arms: genome `abffa2b7f101`, `--tier frozen,probe`, 42 asks each, one line per arm.
Arm A = generation 11 (flag off). Arm B = generation 12 (`--resonance-scope`).

## Scores

| arm | frozen | probes | guarded | verdict |
|---|---|---|---|---|
| gen 10 baseline | 19/24 | 0/14 | 4/4 | clean |
| **gen 11 arm A, flag off** | **19/24** | **0/14** | **4/4** | clean |
| **gen 12 arm B, flag on** | **19/24** | **0/14** | **4/4** | clean |

Harness summary lines, `g11-1` and `g12-1`, both `19/24  0/14  4/4  clean -`.

**Zero gained, zero lost.** No ask changed its pass verdict in either direction.

## Failure stages moved, and that is the whole result

```
gen 10 / gen 11 arm A : {"recall": 10, "mouth": 4, "gating": 3, "shape_arbiter": 2}
gen 12 arm B          : {"recall": 17,                    "shape_arbiter": 2}
```

The `mouth` class **vanished** — and so did the `gating` class. All seven asks moved to
`recall`, which in this harness is the default bucket for "no specific stage matched"
(`tools/heldout_eval.py:141`), not a measurement. Every one of the seven has
`source: null`: **the organ stopped speaking.**

| ask | arm A | arm B |
|---|---|---|
| `name the wet thing that is not on the hook` | mouth, `meaning resonance` | recall, `null` |
| `which of them is wet and is not on the hook?` | mouth, `meaning resonance` | recall, `null` |
| `repeat after me the copper bell turns twice` | mouth, `meaning resonance` | recall, `null` |
| `which thing did i mention earlier than the kettle?` | mouth, `meaning resonance + chain` | recall, `null` |
| `does the door hold the frost?` | gating | recall, `null` |
| `is it true that the door holds the frost?` | gating | recall, `null` |
| `is the frost held by the door?` | gating | recall, `null` |

Babble became silence. That scores the same 0 and asserts nothing false, so it is not a
regression — but it is not a repair either, and P4 predicted at least 2/14.

## Predictions

- **P1 flag-off identity — PASS.** Arm A vs generation 10: same 42-ask set, **0 field
  differences** across `pass`, `stage`, `cause`, `source` and `coverage`. Flag-off
  inertness is confirmed empirically, not just by construction.
- **P2 the pool actually shrinks — PASS.** Scoped pool **7 / 7 / 5 / 8** words against a
  full pool of **11,439**, and the wanted word is in the scoped pool in all four cases
  (`scarf`, all four echo words, `lantern`). The mechanism engaged.
- **P3 the attractor is excluded, not out-scored — PASS.** `numbered`, `sold` and `agin`
  are **absent** from the scoped pool on all four asks. This was the load-bearing
  prediction and it holds exactly: scoping removes the corpus attractor as a candidate.
- **P4 score movement — FAIL.** Probes 0/14 → **0/14**. `wanted_wins_scoped_pool` is
  **false in all four cases**. Frozen 19/24 and guarded 4/4 held, but the predicted rise
  did not happen.
- **P5 zero erosion — PASS.** No frozen pass lost, no guarded pass lost. All five
  `banc_brain.npz` copies are byte-identical to the episode-3 seal `546adb1bb8e433c3`
  (9,346 bytes each, 1 distinct sha256 across 5 files), so the `STATE GUARD FAILED: 5 live
  file(s) moved` line and the resulting exit code 1 on both arms is the known false
  positive — movement, not damage.
- **P6 no new babble — PASS, vacuously and in the other direction.** No ask gained speech.
  Seven **lost** it. P6 was written to catch a repair trading four wrong words for four
  different wrong words; what happened instead is that the words ran out.

## Why it failed: a second attractor, inside the session

Removing the corpus attractor did not leave the wanted word on top. It left **`the`**.

| ask | scoped pool | argmax | score | wanted | wanted score | wanted rank |
|---|---|---|---|---|---|---|
| `name the wet thing…` | 7 | **the** | 0.5215 | scarf | 0.1526 | 6 / 7 |
| `which of them is wet…` | 7 | **the** | 0.5199 | scarf | 0.1600 | 6 / 7 |
| `repeat after me…` | 5 | **the** | 0.5076 | bell | 0.1221 | 2 / 5 |
| `which thing did i mention earlier…` | 8 | **the** | 0.5041 | lantern | 0.4129 | 2 / 8 |

`the` wins **all four**, at 0.504–0.522. It is a session word — every tell contains it — so
scoping admits it, and it out-resonates the content words the same way `numbered` did.
The diagnosis identified *an* attractor and correctly predicted that scoping would remove
it. It did not predict that the session's own function words would be the next one up.

And `the` at 0.52 is **below** `reply_threshold` 0.55, so `understands` is now False and the
organ returns `"it did not understand and was not in the mood to babble"`. Hence the silence.

### The stronger finding: `understands` was never a comprehension signal

This is worth more than the failed repair. On the resonance path, `understands` is
`res[best] >= 0.55`. In arm A that test was passed by `numbered` at 0.5811 and `sold` at
0.5722 — corpus attractors with nothing to do with the question. In arm B, with the
attractor gone, **`understands` is False on all seven asks that previously cleared it.**

So the organ's self-reported understanding on this path was **entirely an artifact of the
corpus attractor clearing the bar**. It carried no information about the question. The
threshold 0.55 was not calibrated to comprehension; it was calibrated to sit just inside the
attractor band (0.550–0.581), which is precisely why the organism babbled confidently rather
than staying quiet. Arm B is the first measurement in which the resonance path reports
honestly, and it reports that it does not understand.

That also explains the three `gating` asks: `gating` means "understood but did not want to
speak". They were never understanding anything either — the same attractor was clearing the
same bar. Under scoping they join the silence, and the `gating` class disappears.

## Abort, not widen

The pre-registration stated, before running:

> If P2 holds but the wanted word still does not win its scoped pool, **abandon rather than
> widen**. Do not raise the pool to "recent" words, do not add a frequency penalty, do not
> lower `reply_threshold` to compensate.

P2 holds (pools of 7/7/5/8, wanted word present). The wanted word does not win any of them.
**The condition is met and E9 is abandoned.**

The tempting next steps are all forbidden by that clause, and each would reintroduce the
problem by a side door:

- *Lower `reply_threshold` below 0.50* so `the` clears it — that restores confident babble,
  now saying `the` instead of `numbered`.
- *Filter function words from the pool* — `lantern` would then win its pool (rank 2 of 8,
  behind only `the`) and `bell` would win the echo pool (rank 2 of 5). This is the most
  seductive option and it is a frequency/stopword penalty under another name. It is also
  not obviously wrong, which is exactly why it needs its own pre-registration with its own
  predictions rather than being folded into a repair that has already been refuted.
- *Widen the pool to "recent" words* — readmits the corpus.

`RESONANCE_SESSION_SCOPE` remains in the organ, default `False`, inert, with this result
recorded beside it. It is kept for the same reason `RECALL_UNFILTERED_FALLBACK` is kept: a
measured negative is evidence, and deleting it would invite someone to try it again.

## What stands and what falls

**Stands.** The `mouth` class *is* a resonance defect. The pool *is* unscoped at 11,439
words. The corpus attractor *is* ask-independent (range 0.009 across four different asks).
No threshold *can* separate attractor from wanted word. All of that was confirmed by P2/P3,
which passed cleanly.

**Falls.** The claim that scoping the pool would let the wanted word win. It does not, because
the session contains its own attractor. The diagnosis correctly located the defect and
correctly predicted the mechanism of the fix, and then mis-predicted the outcome — the
attractor was a *symptom* of ranking over a pool that contains high-frequency function words,
not the root cause.

**New, and not previously known.** `understands` on the resonance path is not a comprehension
signal. Seven asks across two failure classes were reporting understanding purely because a
corpus word cleared 0.55. Any future work that reads `understands` as evidence of
comprehension is reading noise.

## Reproduce

```
.venv\Scripts\python.exe tools\run_generation.py --generation 11 --lines 1 --tier frozen,probe
.venv\Scripts\python.exe tools\run_generation.py --generation 12 --lines 1 --tier frozen,probe --resonance-scope
.venv\Scripts\python.exe docs\evidence\e9_analysis.py        # P1, P4, P5, P6
.venv\Scripts\python.exe docs\evidence\e9_scope_probe.py     # P2, P3
```

Journals: `state/selection/generation_11{,_asks}.jsonl`, `generation_12{,_asks}.jsonl`.
Probe: `docs/evidence/e9_scope_probe.json`. Cost: 84 builds, ~36 min.

**Caveat on `e9_analysis.py`.** Its `guarded` detection looks for a `guarded` key the ask
journal does not carry, so it reports `paraphrase 4/18, guarded 0/0`. The authoritative
guarded figure is the harness's own summary column, `4/4` on both arms. The script's
ask-for-ask comparisons (P1, P4 gained/lost, P6) read fields that do exist and are correct.
