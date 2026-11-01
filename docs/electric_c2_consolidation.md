# ELECTRIC C2 — do taught facts survive consolidation? Yes, and the way they nearly didn't is the finding

```
.venv\Scripts\python.exe tools\electric_consolidate.py --arm nocons --facts 20 --seed 1
.venv\Scripts\python.exe tools\electric_consolidate.py --arm cons   --facts 20 --seed 1
```

Same seed, same generator call, so **both arms and the earlier 20/20 generalisation run
teach the identical 20 facts and ask the identical held-out frames.** The only variable is
whether `consolidate()` ran.

## 1. Result

| arm | correct | confabulated | refusal | silence | direct (`electric_taught`) |
|---|---|---|---|---|---|
| `nocons` (save → restart) | 20/20 | 0 | 0 | 0 | 18 |
| **`cons`** (consolidate → save → restart) | **20/20** | **0** | **0** | **0** | **18** |
| `cons`, **before the fix** | **0/20** | — | — | — | 0 |

Frame split identical across both arms: H1 2/2, H2 6/6, H3 12/12.

**Consolidation does not destroy or hide the taught inventory.** The taught facts do not
live in the 60,000-row FIFO binder at all — they are a keyed `dict` in the version-2 state
document — so the eviction pressure E1 was built to measure never touches them. That is
the structural reason for the result, not an accident of this seed.

The consolidation run itself was real: `rows_scanned 2000`, **`rows_urgent 353`**,
`rows_replayed 200`, `passes 3` ⇒ 600 `live(learn=True)` calls, 52.3 s.

## 2. The actual finding: the safe choice was the one that erased the learner

The first `cons` run scored **0/20 with all 20 subjects lost** — and the pollution check
was clean, so nothing had overwritten them. Cause, one line in `save_state`:

```python
"taught_says": (self._taught_says if self.ELECTRIC_TEACH else {}),
```

**`ELECTRIC_TEACH` is a write permission, and I had used it as a memory flag.**

Teaching must be switched off before consolidation, and this is not a hypothetical:
`consolidate()` replays up to 600 **corpus** sentences through `live(..., learn=True)` —
the same entry point teach mode uses. With teach mode left on, every replayed library
sentence becomes a fact *the user told*, and the organism wakes up believing the corpus
spoke to it. So the harness turns teach mode off. That is the correct, defensive choice —
and under the old gate it **wrote an empty inventory and lost every taught fact.**

The consequence reaches past this experiment: under the old gate, **any learner that stops
being in teach mode forgets everything it was taught at its next save.** A design that
toggles teach mode per turn — the obvious way to avoid minting facts from corpus text —
silently loses the whole memory, and loses it only on the paths that were being careful.

### The fix, and why it is battery-neutral

```python
"taught_says": (self._taught_says
                if (self.ELECTRIC_TEACH or self._taught_says) else {}),
```

Gate on **"is there anything to keep"**, not on "am I still allowed to learn".
`_taught_says` can only be non-empty if `ELECTRIC_TEACH` was on at some point in the
session, so **every run with ELECTRIC off still writes `{}` and the state bytes are
unchanged** — asserted, not assumed, by `test_electric_off_still_writes_an_empty_inventory`.
One line, inside the existing ELECTRIC block, no new flag: the flags that gate the
behaviour (`ELECTRIC_TEACH`, `ELECTRIC_ANSWER`, `ABSENCE_INVENTORY`) are unchanged and all
default off.

`absence_inventory` keeps its old gate. E24's inventory was **session-scoped by design**
and is a diagnostic, not a memory; widening its gate would change a measured behaviour for
no capability gain. The asymmetry is deliberate.

## 3. Two things I got wrong and corrected against evidence

1. **I guessed the state API.** The first draft imported `E1`, `FRAMES`, `FORBID`,
   `seed_scratch` from the generalisation harness — none of which exist (it binds the
   generator as `te`, and its helpers are `seed_state`/`build`/`grade`). Caught before
   running by reading the file rather than trusting my own memory of writing it. The
   rewrite also bought real comparability: reusing `te.generate(a, 20, 1)` regenerates the
   *identical* facts as the 20/20 run.
2. **I guessed the inventory key.** A new test asserted `_taught_says["bell"]` for *"the
   copper bell turns twice"*. The measured key is **`copper`**: `_absence_frame` takes the
   first content word after the article, so **a multi-word noun phrase keys on its
   modifier**. I corrected the test to the measurement and left the surprise on record —
   it means an ask naming `bell` does *not* bind, and that ask in fact came back
   `source='recalled proposition'` from the old path, not from ELECTRIC. This is a real
   limitation of the keyed index, not exercised by the 20 facts because they are all single
   words.

## 4. Observation I did not decompose

`san_real` (nonzero SAN entries) went **1,457,958 → 1,450,258** across consolidation —
*down* 7,700, which is the opposite of what "Hebbian replay only adds" suggests. The
mechanism is identified: `live()` rescales touched rows/columns (`:653-654`) and applies a
time-based decay tick (`:658-659`, `SAN_DECAY_PER_S = 0.995`). So the number is a **net of
adds, rescales and decay**, and **I did not separate the three.** Reported as an
observation, not a conclusion; it does not bear on retention, since retention did not
depend on the SAN at all.

## 5. Suite status: one E24 test broke, and it broke for a reason worth keeping

`tests/test_absence_inventory.py::test_e24_inventory_is_session_scoped` **FAILED** on the
first full run. Its assertion was:

```python
assert "if self.ELECTRIC_TEACH else {}" in save
```

That is a **source-text pin** — it greps the implementation for an exact string, so a
legitimate change to that expression reads as a regression even when the behaviour it was
protecting is intact. It is also the second time this round an E24 test pinned my prose
rather than the contract.

I **retargeted it to the test's stated intent rather than deleting or weakening it**: the
write must remain conditional and must still emit an empty dict when nothing was ever
taught.

```python
assert "if (self.ELECTRIC_TEACH" in save and "else {}" in save
assert "or self._taught_says" in save
```

The intent is now additionally asserted **behaviourally**, which is the stronger form and
is what actually protects the battery:
`test_electric_off_still_writes_an_empty_inventory` loads a real organ with every flag
off, speaks a sentence to it, saves, parses the JSON and asserts `taught_says == {}`.

**This is not the guarded grader contract** and no grader was changed. The `absence_inventory`
gate in the same document is left exactly as E24 wrote it.

Final counts are in §8.

## 6. What this does NOT establish

- **Not survival across a *real* restart of the live house.** Both arms restart a new organ
  object in one process against a scratch copy. A genuine `serve.py` shutdown/startup is
  untested.
- **Not many cycles.** One `consolidate(budget=200)` call, not the live tool's loop-until-
  drained (up to 12 runs). Whether repeated consolidation, or consolidation with teach mode
  left ON, erodes anything is unmeasured — and the second is now known to *inject* corpus
  sentences as taught facts, which is a hazard worth its own experiment.
- **Not that the binder kept the facts.** It probably did not; the keyed JSON inventory is
  what answered. E1's displacement cost stands exactly where it was.
- **Not multi-relation.** All 20 facts are `the {a} {v} the {b}` agent sentences.

## 7. The one-line change, in full

```diff
- "taught_says": (self._taught_says if self.ELECTRIC_TEACH else {}),
+ "taught_says": (self._taught_says
+                 if (self.ELECTRIC_TEACH or self._taught_says) else {}),
```

No new flag. `ELECTRIC_TEACH`, `ELECTRIC_ANSWER` and `ABSENCE_INVENTORY` keep their
meaning and their off-by-default status; this only stops a *permission* flag from also
acting as a *memory* flag.

## 8. Files and suite

`tools/electric_consolidate.py` (new), `organs/neural_language.py` (save gate + comment),
`tests/test_electric.py` (+2 tests, now 22), `tests/test_absence_inventory.py` (source pin
retargeted to intent), `docs/evidence/electric_c2_{cons,nocons}.json`.

**Suite: 816 passed, 3 skipped, 5 warnings** (was 814; +2 new tests; zero erosion).
`test_electric.py` is now 22 tests.

**Battery posture unchanged: ELECTRIC stays off for battery runs, and the guarded grader
contract was not touched.**
