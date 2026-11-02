# Handover

Objective, state, commands, and boundaries as of this handover. The long-form history is
`docs/CHANGELOG.md` and `docs/STATE.md`; the design record is `README.md`. This file is the operational
layer: what is true right now, how to re-check it, and what not to touch.

## What was in flight

`ELECTRIC_ARBITER_TELL` -- the **seventh** widening of learn mode. When the shape arbiter has verified
a memory against the queried shape and named the word in it that answers the ask, the house says that
memory whole instead of the one word.

It exists because `arbiter head` was the largest remaining source of `fallback_fragment` in learn mode:
measured on the pre-flag run, **7 of the 8** fragment probes at depth 3 were this branch, and in all 7
the row the arbiter chose was the very sentence the person had taught. The one-word branch is
deliberate -- reading a row aloud speaks its modifiers too, which is how `what turns twice?` tripped
its own forbid on `copper` -- so the flag carries a bound rather than a hope: **the row may add no
word the ask did not already name, except the answering word itself.** Plus three more: the row was
said to him (`who == "you"`, so a corpus window is never re-issued as a lesson), the row is not itself
an asking, and the named word is in the row.

Full entry: `docs/STATE.md`, section `ELECTRIC_ARBITER_TELL`. Tests:
`tests/test_electric_arbiter_tell.py` (18).

## Current state -- all of this was re-run on this tree, not read back from a file

| claim | number | how to re-check |
|---|---|---|
| full suite | **1126 passed, 3 skipped, 5 warnings, 490.98s**, exit 0 | `.venv\Scripts\python.exe -m pytest tests -q` |
| new flag's tests | 18 passed in 2.21s | `.venv\Scripts\python.exe -m pytest tests/test_electric_arbiter_tell.py -q` |
| benchmark | 40 items, 136 probes, 3 arms, **no invention in any arm at any depth**, exit 0 | `.venv\Scripts\python.exe tools/electric_learn_bench.py` (~8.5 min) |
| learn correct (live), depths 1/2/3 | **38 / 75 / 115** of 39/124/124 (pre-flag: 37/71/108) | same, or `--arms learn --depth 3` for one cell |
| teach arm | **14 / 27 / 39**, unmoved | same |
| control arm | **0 / 0 / 0**, unmoved | same |
| `arbiter tell` rows | **36**, all in the learn arm; `arbiter head` 1034 to 1014; silence 1535 to 1519 | `docs/evidence/electric_learn_bench.json` |
| guarded absence | **24 rows before, 24 after** -- the graded invariant did not move | same |
| `fallback_fragment`, learn d3 live | **8 to 3** | same |
| rows that lost `correct` | **0** | `_tmp/verify_matrix.py` (scratch, not committed) |
| learn-arm row transitions | 36 `arbiter head`->`arbiter tell` (`partial`->`correct`), **16 `refused`->`arbiter head` (`refused`->`partial`)** | same script, against `_tmp/bench_pre_arbiter_tell_HEAD.json` |
| modes | 18 attributes, **6 refusals + 7 widenings** | `.venv\Scripts\python.exe tools/electric_teach_mode.py --describe` |
| restart test | 23.81s (52.79s at HEAD) | `.venv\Scripts\python.exe -m pytest tests/test_electric_learn_mode.py -q -k restart` |

The 5 warnings are pre-existing: `PytestUnknownMarkWarning: Unknown 'integration'`. The 3 skips are the
pre-existing `legacy_archive` ones. Baseline arithmetic: HEAD was **1108 passed, 3 skipped**; 1108 + 18
= 1126, and per the repo convention counts come from `findstr /R "^def test_"`, not regex guessing.

## Findings a reader should not have to rediscover

**The 36 rows the flag converts are clean; the 16 rows it drags along are not.** Row by row against the
pre-flag snapshot: all 36 `arbiter tell` rows were `arbiter head` rows at the same position, asking the
same thing, and every one moved `partial -> correct` -- the branch converting is exactly the branch. But
**16 further rows moved `refused -> partial`**, and that is not this branch's work. They are 3 distinct
ungrammatical asks -- `what the nora carry`, `what the dog guard`, `what the bridge cross` -- that used
to be refused with `nothing he remembers has that shape` and now reach the one-word branch, because
probes are asked in order against one house that stores what it hears: once the flag has said rows
whole, a row of that shape exists. They recur across depths and phases, which is how 3 asks become 16
rows. No row lost `correct`; the teach and control arms did not move at all (0 rows changed).

**The word those 3 asks now speak is `says`, which is in nobody's mouth.** `says` appears in none of the
27 told sentences, and in neither the ask nor the row it is drawn from (`nora carries the lantern`,
`the dog guards the gate`, `the bridge crosses the river`). The one-word branch can name a word the
house was never told, and the benchmark's INVENTED grader does not see it because it grades sentences
and this is a word. The defect belongs to `arbiter head`, not to the bound -- the bound is exactly what
stops those 3 asks being handed a sentence, so with the flag on they still get only the word. **But by
this project's own standard (`docs/electric_generalisation.md`: confabulation is "the category that is
worse than silence"), a probe that honestly declined now uttering an unsupported word is a regression,
and the flag's +7 at depth 3 must be read against it.** Open, not fixed here.

**A correction, because the first draft of this handover got it wrong.** It said "no probe moved to a
worse class" and "20 of the 36 rows are the branch converting, 16 arrive through state". Both came from
subtracting aggregate source counts (1034 -> 1014) instead of walking the rows. The matrix says 36 of 36
are the branch, and the 16 are a *different* class movement pointing the other way. If you are tempted
to explain a delta by aggregate arithmetic here, walk the rows: the artifact is positional and the asks
line up index by index.

**A startup banner can hang a test suite.** Adding the seventh `WIDENS` line to `describe_learn()` pushed
`tools/electric_chat.py`'s banner past the **4096-byte Windows pipe buffer**. Three tests scan stdout
until `ready port=` and then stop touching the pipe, so the child blocked in `print()` before the serve
loop was ever reached -- it presented as a `/shutdown` problem and was not. The readiness line now
prints **last**, because the client's own scan is what drains it. If you add another mode line, the
banner grows again.

## Commands

```bat
.venv\Scripts\python.exe -m pytest tests -q                     the suite
.venv\Scripts\python.exe -m pytest tests -q -k electric         the electric neighbourhood alone
.venv\Scripts\python.exe tools/electric_learn_bench.py          3-arm benchmark, ~8.5 min, exit 0 = no invention
.venv\Scripts\python.exe tools/electric_learn_bench.py --arms learn --depth 3
.venv\Scripts\python.exe tools/electric_teach_mode.py --describe
.venv\Scripts\python.exe tools/electric_chat.py --learn --port 8899
.venv\Scripts\python.exe tools/serve.py --electric --electric-learn --electric-qa-store --port 8123
```

Line endings, on this machine (`core.autocrlf=true`, **no `.gitattributes`**): working tree is CRLF, git
blobs are LF, and a `git diff --stat` of real line counts is the check that nothing churned.

```bat
git show HEAD:organs/neural_language.py | .venv\Scripts\python.exe -c "import sys;d=sys.stdin.buffer.read();print('blob LF-only:', b'\r' not in d)"
.venv\Scripts\python.exe -c "d=open('organs/neural_language.py','rb').read();print('worktree CRLF-only:', d.count(b'\r\n')==d.count(b'\n'))"
```

## Do not change without re-measuring

- **The guarded absence** (`scarf`/`hook`, `src == electric_absence`): 24 rows in the benchmark, and the
  contract that a thing the house was never told stays unsaid. Any widening that touches speech must
  leave it alone; this one does.
- **Teach mode's guarantee**: `--electric-teach` refuses every widening. `ELECTRIC_ARBITER_TELL` is in
  `EXCLUDED_ATTRS`, so the guarantee survives a flag whose whole purpose is to say more.
- **The graded leak `what turns twice?` -> `bell`.** It is the reason the bound is a bound. Pinned in
  `tests/test_electric_arbiter_tell.py` with the flag ON.
- **`arbiter head` itself.** One probe now reaches it that used to be silent. Fixing the `says`
  pathology belongs to that branch, not to this flag.
- **Determinism.** The benchmark is byte-reproducible: a single-cell re-run reproduced the full run's
  learn/d3 source mix in all three phases. `tools/electric_chat.py --fresh` is NOT deterministic across
  processes on the fragment path, and the repo says so; do not "fix" one by touching the other.

## Not part of this work -- deliberately uncommitted

E27's shape-vs-paraphrase divergence investigation owns these, and they must not ride along with a
flag commit:

- `docs/evidence/e27_divergence.json`, `e27_realpath_divergence.py`, `e27_shapes_analysis.py`,
  `e27_shapes_control.json`, `e27_shapes_result.md`, `e27_shapes_treatment.json` -- **untracked**
- `docs/evidence/electric_subject_key_probe.py` -- **tracked and modified** (+24/-6: the `--treatment`
  switch and the `E27_SHAPE_DEBUG` trace). E27's, not this handover's.
- `tools/electric_shape_generalise.py` -- untracked, +380 lines, no tests, not wired into any mode
- `state/electric_chat/` -- untracked runtime state, rewritten by every live run; never commit it
- `_tmp/` -- this session's scratch (A/B logs, the regression sweep, the pre-flag benchmark snapshot
  `bench_pre_arbiter_tell_HEAD.json`, sha256 `83a774515c5adc67...`). Ignored, safe to delete.

## Commit boundary for this work

`organs/neural_language.py`, `tools/electric_teach_mode.py`, `tools/serve.py`, `tools/electric_chat.py`,
`tools/electric_learn_live.py`, `tools/qa_teach_mode_live.py`, `tests/test_electric_arbiter_tell.py`,
`tests/test_electric_learn_mode.py`, `tests/test_electric_ask_do_support.py`,
`tests/test_electric_qa_answer_memory.py`, `tests/test_electric_teach_mode.py`, `README.md`,
`docs/STATE.md`, `docs/HANDOVER.md`, `docs/evidence/electric_learn_bench.json`.

`docs/evidence/electric_learn_bench.json` is in that list because it was **re-run on this tree**, so it
is this commit's evidence rather than someone else's. Consequence: the pre-flag numbers quoted as
history in `README.md` and `docs/STATE.md` (the 8 fragments, the 108 correct) are no longer in the
shipped artifact -- they are at commit `af32c0f`, and both documents now say so.

## Known-stale or unverified

- `README.md`'s badge figures (vocabulary, propositions, fitness) are from a different corpus and are
  flagged as such in the file. Not re-measured here.
- `docs/STATE.md`'s "electric neighbourhood 267 passed in 5:08" is a historical measurement. The
  subset re-run during this handover was killed by a shell timeout before finishing, so that number
  was **not** re-verified; the full suite (which contains it) is green.
- `tools/electric_learn_live.py` (the live 3-arm tool) was not re-run on this tree; only its evidence
  note text changed.
