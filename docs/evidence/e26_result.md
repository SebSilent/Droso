# E26 — `v_frame` alone: result

**Status: ACCEPTED. No abort condition fired. But it produced no new capability beyond E25, and it
ends the coverage line.**

**Arms:** generation 21 (control, `--absence-inventory`) vs generation 23 (treatment,
`--absence-inventory --coverage-exclude frame`). Same genome `abffa2b7f101`, same 42-ask battery.
`v_frame` is a superset of `v_synt` (function words + question-framing verbs), so the flag turns on
both exclusions — that is **one** variant, not two stacked, and it is compared against gen 21, never
against gen 22.
**Verification:** `docs/evidence/e26_user_visible.py`.

## User-visible changes

**Newly answered: 1** — and it is the *same* ask E25 recovered.

> `how often does the bell turn?` → was silent, now says **`the copper bell turns twice`**

**Newly broken: 0. Answer text changed on a passing ask: 0. Total 23/42 → 24/42, net +1.**

Three further asks crossed the coverage gate and **died at the shape arbiter instead of becoming
answers**:

- `how often did i say the coat is wet?` — `recall` → `shape_arbiter`
- `what did i tell you about before the kettle?` — `recall` → `shape_arbiter`
- `what is held by the thing the frost bites?` — `recall` → `shape_arbiter`

## Stage mass

| stage | gen 21 | gen 22 (`v_synt`) | gen 23 (`v_frame`) |
|---|---|---|---|
| `recall` | 10 | 8 | **6** |
| `shape_arbiter` | 2 | 3 | **5** |
| `mouth` | 4 | 4 | 4 |
| `gating` | 3 | 3 | 3 |

`v_frame` drained **four** asks out of recall and converted **one** into an answer. The other three
moved sideways into the shape arbiter, which is now the largest failure bucket.

## Abort conditions

| # | condition | status |
|---|---|---|
| B1 | scarf still refuses | **PASS** |
| B2 | guarded 4/4 | **PASS** (`probe_guard_passed 4/4`) |
| B3 | frozen ≥ 19/24, `frozen_lost_n` 0 | **PASS** (19/24, 0) |
| B4 | scarf coverage `None`, reason byte-identical | **PASS** |
| B5 | no answer subtracted | **PASS** (0) |
| **B8** | no question verb is a battery content word | **PASS** — asserted against 31 content words; also asserted disjoint from `SHAPE_FUNCTION_WORDS` so the two exclusion sets cannot double-count |

## Verdict: the coverage lever is exhausted

E23's offline pretest predicted `v_frame` would recover **3 of 9** `v_base` losses. It recovered
**four** asks past the coverage floor — and **one** became an answer. The pre-registration for E26
carried this caveat explicitly:

> E23's "3 of 9" and "5 of 9" were measured **offline on coverage alone**, without the reply gate,
> shape arbiter or mouth — and E25 just demonstrated that crossing the floor does not guarantee a
> pass. The honest expectation for E26 is **1 or 2 probe gains, possibly zero**, not 3.

The outcome was at the bottom of that range, and the reason is now measured rather than guessed:
**coverage is no longer what binds.** Two coverage variants, applied independently, produced the same
single answer between them. `v_all` (E27, 5 of 9 offline) is another coverage lever and would be more
of the same.

**The coverage line stops here.** Continued in `docs/capability_first_plan.md`.

## Tests

12 new in `tests/test_coverage_exclude_frame.py`, written before the organ change. Full suite
**794 passed, 3 skipped**, zero erosion. Skips fell 5→3 because both E26 integration tests now have
generation 23 and pass — including `test_e26_abort_conditions`, which reads C-style abort conditions
from the published fitness block rather than re-deriving them.

Two existing tests **amended, not deleted**, both for the same legitimate reason as E25's amendment:
- `test_e25_harness_records_the_flag_in_provenance` / `..._flag_is_default_off` — E26 collapsed the
  harness's two branches into one unconditional assignment driven by `_syn`/`_frm`, which is strictly
  stronger: the key is now written on *every* path and can never be missing.
- `test_e24_e23_still_off` — `COVERAGE_EXCLUDE_FRAME` moves off the banned list for the same reason
  `v_synt` did in E25. **`COVERAGE_EXCLUDE_ALL` stays banned**: `v_all` is not this experiment's
  lever, and implementing it early would stack variants the design forbids.

Three test-side bugs fixed during writing, all in the new file: `ast.literal_eval` cannot parse a
`frozenset(...)` call (it is a `Call`, not a literal) so a `_frozenset_at` helper peels the call off;
`_coverage_excluded` is module-level, not a class attribute, so `NL._coverage_excluded` raised
`AttributeError`; and the hook test's slice arithmetic asserted on the wrong window.

## Files

| file | change |
|---|---|
| `organs/neural_language.py` | `COVERAGE_EXCLUDE_FRAME` (default off), `QUESTION_VERBS`, one extra `or` in the existing `continue` |
| `tools/run_generation.py` | `--coverage-exclude {synt,frame}`, both flags stamped unconditionally |
| `tests/test_coverage_exclude_frame.py` | 12 tests, written first |
| `tests/test_coverage_exclude.py`, `tests/test_absence_inventory.py` | three tests amended |
| `docs/capability_first_plan.md` | the successor plan |
| `docs/evidence/e26_user_visible.py`, `e26_result.md` | verification, this file |
| `state/selection/generation_23*.jsonl` | treatment arm |
