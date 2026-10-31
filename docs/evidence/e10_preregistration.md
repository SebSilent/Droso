# E10 pre-registration: content-word resonance scope

Written **before** the battery runs. Gene: `RESONANCE_CONTENT_SCOPE`, default `False`.

## Why E10 is legitimate after E9's abort clause

E9's pre-registration forbade widening *that* experiment:

> do not raise the pool to "recent" words, do not add a frequency penalty, do not lower
> `reply_threshold` to compensate.

It also said why, and what the alternative was:

> It is not obviously wrong, which is exactly why it needs its own pre-registration with
> its own predictions rather than being folded into a repair that has already been
> refuted.

E10 is that separate pre-registration. Nothing is folded into E9; E9 stays refuted and its
gene stays inert. E10 is a new hypothesis with new predictions and its own abort condition.

## The defect E10 targets

E9 established two attractor classes, and that each filter alone removes only one:

| filter | removes | leaves on top |
|---|---|---|
| none (gen 10/11) | — | `numbered` 0.5811, `sold` 0.5722 — corpus |
| session scope (E9) | `numbered`, `sold`, `agin` | **`the`** 0.504–0.522 — session function word |
| **both (E10)** | both classes | ? |

The corpus attractors are *rare* in the binder (df 14, 7, 2), so a distinctiveness filter
alone admits them. `the` is in nearly every row, so session scope alone admits it. Neither
half is sufficient. E10 runs both.

## The content/function distinction: distributional, not a stopword list

The requirement was a principled distinction rather than ad hoc stopwords. The organ already
contains one, in the recall gate:

```python
df = len(self.cortex.binder.stem_rows(w))
if not df:
    unknown.add(w); continue          # "a word he has never met is not evidence about anything"
known.add(w)
if df * 4 <= n_mem:
    must.add(w)                       # distinctive enough to be a retrieval key
```

**A word is content iff he has met it and it occurs in at most a quarter of his memories.**
`_is_content_word(df, n_mem)` is that predicate lifted verbatim — `df > 0 and df * 4 <= n_mem`.

This is deliberately **not** `SHAPE_FUNCTION_WORDS`, the hand-written 86-word closed-class set
declared a few lines below the new gene, and not `stemming.STOPWORDS`. Reasons:

- no new constant and no new list — the rule and its `df > 0` guard already exist and are
  already load-bearing elsewhere in the same organ;
- it is derived from the organism's **own** memory, so it adapts to what he has actually been
  told rather than to a fixed model of English;
- it is falsifiable per word: `the` df 59,000 / 60,000 fails, `scarf` df 14 passes.

## Implementation

`_resonance_mates` applies scope first, then content, each with a fallback to the wider pool
when it would empty it, and `_resonance_content` also falls back when the store cannot be
read. So neither flag can cause a silence by exhaustion. `--resonance-content` in
`tools/run_generation.py`; it prints a warning if used without `--resonance-scope`, since
that combination tests a different hypothesis.

## Arms

Genome `abffa2b7f101`, `--tier frozen,probe`, 42 asks, one line per arm.

- **Arm A** — generation 13, no flags. Control.
- **Arm B** — generation 14, `--resonance-scope --resonance-content`. The E10 repair.

Arms differ only in code flags. Same genome, same battery, same guards.

## Predictions

- **P1 — flag-off identity.** Arm A is identical to generation 11/10 ask for ask: 0 field
  differences across `pass`, `stage`, `cause`, `source`, `coverage`.
- **P2 — the content filter engages.** On the four mouth asks the scoped pool shrinks again,
  and `the`, `is`, `on` are **absent** from it.
- **P3 — both attractor classes are gone.** `numbered`, `sold`, `agin` absent (scope) **and**
  `the` absent (content), simultaneously, on all four asks.
- **P4 — the wanted word wins its content-scoped pool.** `scarf` for the two conjunction
  asks, `bell` for the echo, `lantern` for the order ask. E9's measured ranks make this
  plausible: `lantern` was rank 2 of 8 behind only `the`; `bell` rank 2 of 5 behind only `the`.
- **P5 — zero erosion.** No frozen pass lost, no guarded pass lost, guarded stays 4/4,
  frozen stays 19/24 or better. All `banc_brain.npz` copies stay byte-identical to seal
  `546adb1bb8e433c3`.
- **P6 — no new babble.** No ask gains speech with a wrong word. If the winner clears
  `reply_threshold` and the utterance is not the wanted content, that is a failure, not a gain.
- **P7 — the score.** Probes rise from 0/14 to **at least 2/14**, carried by the two asks
  where the wanted word was already rank 2.

## The prediction I expect to be right, stated before running

**P4 will pass and P7 will fail, and the organ will stay silent.**

E9 measured the wanted word's resonance *inside its own scoped pool*: `scarf` 0.1526 and
0.1600, `bell` 0.1221, `lantern` 0.4129. `reply_threshold` is **0.55** and E10 is forbidden
from lowering it. Filtering the pool changes **which** word wins, not the scores — `res` is
computed once over the full vocabulary before any filter runs. So removing `the` promotes
`lantern` to argmax at 0.4129, still below 0.55; `understands` stays `False`; the organ
returns "it did not understand and was not in the mood to babble".

If that is what happens, E10 confirms the ranking repair and refutes the score repair, and
the real finding is structural: **on the resonance path the 0.55 bar can only be cleared by a
high-frequency corpus word.** Comprehension and attractor are the same event. That would make
`reply_threshold` — not the candidate pool — the binding constraint, and it cannot be moved
without reintroducing confident babble.

This is pinned as `test_E10_predicts_silence_because_the_wanted_word_is_below_threshold`,
computed from E9's journal, so it cannot be revised after the fact.

## ABORT condition

**ABORT and record, do not widen, if any of:**

1. the wanted word still loses its content-scoped pool (P4 fails);
2. the winner clears `reply_threshold` and the utterance is wrong — new babble (P6 fails);
3. any frozen or guarded pass is lost (P5 fails);
4. the winner is below `reply_threshold` on all four asks, so the repair produces silence
   rather than speech — the outcome predicted above.

On abort: `RESONANCE_CONTENT_SCOPE` stays default-off and inert, the result is written to
`docs/evidence/e10_result.md`, and the gene is kept for the same reason E9's is kept — a
measured negative is evidence, and deleting it invites a retry.

**Forbidden on abort:** lowering `reply_threshold`; adding a hand-written stopword list;
rescaling resonance scores; widening the pool to "recent" words; any change to the recall
gate's `must` rule. Each would reintroduce the attractor or the babble by a side door.

## Cost

84 builds, ~36 min at the measured 26 s/ask. A 4-build pre-flight probe
(`docs/evidence/e10_scope_probe.py`, ~2 min) measures P2/P3/P4 and the winning score
**before** the battery is committed, so a predicted-silent arm is not paid for twice.

## Reproduce

```
.venv\Scripts\python.exe -m pytest tests/test_mouth_resonance_scope.py -q -p no:randomly
.venv\Scripts\python.exe docs\evidence\e10_scope_probe.py                     # pre-flight
.venv\Scripts\python.exe tools\run_generation.py --generation 13 --lines 1 --tier frozen,probe
.venv\Scripts\python.exe tools\run_generation.py --generation 14 --lines 1 --tier frozen,probe --resonance-scope --resonance-content
.venv\Scripts\python.exe docs\evidence\e10_analysis.py
```
