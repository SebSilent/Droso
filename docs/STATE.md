# STATE — the state of the speech work at handover

Short, factual, current. Everything here was measured, not inferred. The long
reasoning is in `docs/speech_log.md`; this file is the takeover.

**Closing hash:** `f2e1748` (tree clean, pushed).
**Measured at:** `f2e1748`, on a quiet machine, with `tools/_genome_patch.py`
moved out of `tools/` so no shim could be in the path.

## The closing numbers

| harness | result |
|---|---|
| `pytest -q` | **428 passed, 3 skipped** |
| 24 held-out asks, organ only (`--independent`) | **19/24** |
| the eight guard scripts | **8/8 clean** -- 1.00 warm, 1.00 cold, delta +0.00 |
| held-out independent score | **19/24** (same harness; `--independent` *is* the organ-only mode) |

The frozen bar this work started from was **5/24**. The tree it inherited from
the previous line of work scored **6/24**. Both are now well behind the floor.

## Floor

**Floor = 19/24.** It means: the number of the 24 organ-only asks that pass when
every ask is answered by a freshly built house, with no shim, no patch, no
session sharing between asks. **Any change that scores below 19/24 reverts.**
The floor moves only when a *capability point* moves it.

There are two kinds of cut, defined in the log's standard:

- **Capability point** -- must move the 24; booked only then; may raise the floor.
- **Generalisation credit** -- moves no ask because the suite is blind to it;
  gated on unseen paraphrases written before the code; recorded with
  *"zero score delta -- the 24 cannot see cue vocabulary"*; **never raises the
  floor and never substitutes for a capability point.**

## Landed mechanisms, and whether each is general or narrow

| mechanism | where | verdict |
|---|---|---|
| **Echo instruction** (`say exactly …`) | `respond`, echo path | **narrow** -- one instruction shape; guarded by a uniqueness check |
| **Record absence** (`did i ever tell you about the moon?` -> `no`) | `_record_answer` | **general within record scope** -- absence is evidence only for the telling record |
| **Provenance glossary** (`which word did i use for the metal?` -> `copper`) | `_glossary_answer` | **narrow** -- one category; also returns before `hear()`, so the question is not bound that turn |
| **Ordinal selection** (`which did i tell you first …`) | `_ordinal_answer` | **narrow** -- ordinals over the session's memories only |
| **Disjunctive resolution** (`the lantern or the kettle`) | `_disjunction_answer` | **narrow** -- two offered alternatives settled against memory; fixed a `sold` fall-through on this path only |
| **Count over the record** (`how many times did i tell you …`) | `_count_answer` | **general within record scope** -- four quantifier classes (times / things / objects / items) |
| **Quantity arithmetic** (`four eggs`, `two break` -> `two left`) | `_quantity_answer` | **narrow on cue words** -- real subtraction, entity matched by stem; no synonyms |
| **Cue classes** (first/last families) | `_quantity_answer` | **generalisation credit 1** -- *zero score delta; the 24 cannot see cue vocabulary* |

## Reverted / falsified axes, one line each

- **Hop across two memories** -- re-arbitration returned None; `binder.recall`'s contract gave no one-line cause; axis closed as architectural at the time.
- **Description rewrite (defect K)** -- target moved 2/4 -> 3/4, but paraphrase N2 and controls C2/C3 failed; the split keyed on the outer verb's token position, so it was fitted to the phrasing, not to meaning.
- **Band-walk** -- promoted a corpus line over a true tell; meaning-cosine died the same way.
- **Second brain** -- changed *which* memory was offered, never *how strictly* it was judged, so it could not supply a missing shape; falsified as built.
- **Region organ** -- nothing was clipped at the 4.0 cap; the failure was shared hash footprints, and the predicate did not separate under either repair. Closed for good.
- **Mouth head-rule** -- the weighted argmax named the modifier as head and broke `tests/test_shape_filler_position.py`; the fly's modifier class is closed.
- **Additive-fitness population** -- the climb happened entirely on the synthetic four; gen-1 0.783 against a 0.933 ceiling, so the coupling term could not reward capability.

## Harness commands

```bat
:: the 24, organ only -- ONE OR TWO SCRIPTS PER CALL, the full set exceeds the shell timeout
py -3.10 tools\heldout_eval.py --independent --only count-frequency --journal state\fitness\x.jsonl
:: scripts: count-frequency, order-first-last, conjunction-and-absence,
::          exact-repeat, hop-and-inventory, quantity-change

:: eight guard scripts -- four calls, two scripts each, output to a file (no pipe)
py -3.10 tools\script_benchmark.py --only reference,accumulation > state\fitness\g.txt 2>&1
:: pairs: reference,accumulation | discrimination,role_chain |
::        switch_back,override | session_context,where_kept

:: population / evolution
py -3.10 tools\fly_v2.py --phase generations --seeds 13 7 17 23 29 --n 10 --gens 3
py -3.10 tools\verify_saved.py --seed 13        :: proves a saved genome reproduces, no evolution

:: chat probe -- the house door
py -3.10 tools\serve.py --port 8000             :: then POST /api/chat
py -3.10 tools\mouth_probe.py hop-and-inventory "what does the thing the frost bites hold?"
py -3.10 tools\hop_probe.py                     :: target + paraphrases + controls for defect K

:: single-topic probes, one per landed mechanism
py -3.10 tools\quantity_probe.py  |  tools\count_probe.py  |  tools\record_probe.py
py -3.10 tools\ordinal_probe.py   |  tools\disjunction_probe.py  |  tools\glossary_probe.py
py -3.10 tools\echo_guard_probe.py | tools\unowned_probe.py | tools\veto_probe.py
```

## Known defects left open

- **Mood gate** -- an unowned question can still reach the resonance mouth under accumulated drive (defect H was built, passed its five controls, and was reverted because two `test_connectome_house` tests went red).
- **Descriptions** -- `what does the thing the frost bites hold?` is still vetoed; the rewrite experiment is reverted, the harness that failed it is kept.
- **World count** -- `how many times does the bell turn?` still refused (it is a world fact, not a record fact).
- **Two record asks** -- `what did i tell you about before the kettle?` (recall) and `what is wet but not on the hook?` (shape_arbiter).
- **Deliberately refused** -- `does the door hold the frost?` is *supposed* to stay refused; the reversal has no support in memory.
- **Glossary** -- returns before `hear()`, so that turn's question is never bound to memory.
- `tools/veto_probe.py` raises a `TypeError` against its own instance patch; a probe artifact, not the matcher.

## Housekeeping at close

`_tmp/`, `tools/_tmp_report_dump.py` and four root-level git-ignored scratch
scripts (`_vocab_check.py`, `_vocab_check2.py`, `probe_fails.py`,
`probe_speak_fix.py`) were deleted -- leftover diagnostics from earlier
sessions, superseded by the tracked probes in `tools/`. Every probe script in
`tools/` is tracked and documents what it is for. `git status` is clean, nothing
is ignored-but-needed, no background job is alive.

## What is NOT done -- do not repeat it

- **No population run is running.** Nothing is mid-climb, no background job is alive.
- **The evolution harness exists but its fitness saturation is unresolved.** The additive redesign climbs only on the synthetic four; gen-1 sits at 0.783 against a 0.933 ceiling, so fitness cannot pay for a capability the synthetic set does not contain.
- **The 24-ask set is exhausted as a progress signal.** It has been read this many times that further gains are either the same five failures or noise. More normalisation work against it is not progress.
- **Do not re-litigate a reverted axis** without a new mechanism: hop (2 attempts), description rewrite, band-walk, second brain, region organ, mouth head-rule, additive-fitness population.

## The one architectural finding the log earned

**These organs match phrasings, not meanings.** Every mechanism that landed is a
matcher keyed to a surface pattern -- an echo marker, a glossary phrase, an
ordinal, a quantifier noun, a number word, a cue family. Each works exactly on
the shapes it was written for, and the moment the phrasing moves (`holds what?`
instead of `hold?`), the same mechanism walks past it. Nothing here generalises
past its own test, and the honest consequence is that **the suite, not the
organ, is the thing that has to change next**: a new ask set is needed before
another mechanism can be scored as a capability rather than as a phrasing.