# E25 — `v_synt` re-tested against the relocated guard: result

**Status: ACCEPTED. No abort condition fired. First positive capability result since generation 0.**

**Pre-registration:** `docs/evidence/e25_preregistration.md` (commit `531b3b6`).
**Arms:** generation 21 (control, `--absence-inventory`) vs generation 22 (treatment,
`--absence-inventory --coverage-exclude synt`). Same genome `abffa2b7f101`, same 42-ask battery,
one arm per process. **The arms differ in exactly one code flag** — verified from
`provenance.code_flags`, differing set `['coverage_exclude_synt']`.
**Verification:** `docs/evidence/e25_check.py`.

---

## 1. Headline

| metric | control (gen 21) | treatment (gen 22) | corrected prediction |
|---|---|---|---|
| frozen | 19/24 | **19/24** | 19/24 unchanged — **met** |
| guarded | 4/4 | **4/4** | 4/4 unchanged — **met** |
| paraphrase probes | 0/14 | **1/14** | 2/14 — **partially met** |
| total passes | 23/42 | **24/42** | 25/42 — **partially met** |
| `frozen_lost_n` | 0 | **0** | 0 — **met** |
| stage mass | `recall 10, mouth 4, gating 3, shape_arbiter 2` | **`recall 8, mouth 4, gating 3, shape_arbiter 3`** | `recall 8, shape_arbiter 2` — **recall met** |

**Exactly 2 of 42 asks changed** — and both are the two E23 predicted, by name. Nothing else moved.

## 2. Abort conditions

| # | condition | status |
|---|---|---|
| **B1** | scarf stops refusing | **PASS** — still refuses |
| **B2** | guarded < 4/4 | **PASS** — `probe_guard_passed 4 / probe_guard_asked 4` |
| **B3** | frozen < 19/24 | **PASS** — 19/24, `frozen_lost_n: 0` |
| **B4** | scarf coverage no longer `None`, or reason changed | **PASS** — `coverage: None`, reason byte-identical: `scarf was told but no place was ever told for scarf` |
| **B5** | an ask the control answered starts refusing | **PASS** — 0 |
| B6 | subject-absent ask affected | not fired — the 2 changes are both subject-present |
| B7 | content word in the exclusion set | not fired — asserted by test against 31 battery content words |

**B4 is the important one.** The scarf's coverage is `None` in *both* arms and its reason string is
byte-identical, which proves the absence inventory still pre-empts the gate. `v_synt` changed the
denominator, and the guarded ask never saw it. That is the whole thesis of E25, confirmed.

## 3. The two gains, and why one is a pass and one is not

**`how often does the bell turn?`** — `recall` → **PASS**. Coverage 0.514 in the control; in the
treatment the gate never fired because the ask was answered. This is a real capability gain: the
paraphrase tier went 0/14 → 1/14, and that tier had been at zero through every generation since the
baseline was frozen.

**`what is held by the thing the frost bites?`** — `recall` → **`shape_arbiter`**, still failing.
It **crossed the coverage floor** (0.51 → past 0.6) and then died at the next gate. This is precisely
the caveat the pre-registration carried:

> Crossing the floor is necessary but not sufficient. An ask must then survive the reply gate, the
> shape arbiter and the mouth. **2/14 is a prediction, not a promise**; 0/14 with both asks advancing
> past `recall` to a later stage would still be a real, if smaller, result.

The prediction was 2/14 and the result is 1/14 plus one ask that advanced a stage. The pre-registration
covered this outcome explicitly, so it is a partial confirmation rather than a miss — but it is worth
being plain that **the second gain did not land**, and the reason is downstream of coverage entirely.

## 4. Stage mass moved out of recall

`recall 10 → 8`, `shape_arbiter 2 → 3`. This is the metric the selection harness was originally built
to track — whether failure mass moves *out* of recall — and it moved, in the predicted direction, by
the predicted amount. The two asks that left `recall` are exactly the two that changed; one left the
failure set altogether and one moved to `shape_arbiter`.

**The binding constraint is shifting.** With recall down to 8 and the shape arbiter now the second
largest bucket, further coverage work has diminishing returns: the next asks to fall will fall to
shape parsing, not to the denominator.

## 5. Two verification bugs I hit, both worth recording

**The first B2 check was silently wrong.** It filtered probe rows by `script == "guarded"`, got zero
matches, printed `guarded 0/4`, and then the verdict line reported **PASS anyway** — because `b2` had
been assigned the *frozen* score. An abort condition was being reported as satisfied on a check that
had measured nothing. Caught only because the printed `0/4` contradicted the harness's own `guard 4/4`.

**The second B2 check was also wrong**, in the other direction: it read `regression.guarded_passed`,
a key that does not exist, and reported **ABORT** on a run that had passed. The real keys are
`probe_guard_passed` / `probe_guard_asked`.

Both are now fixed and B2 reads from the published fitness block. The lesson is the same one E24's
`licensed_refusal` artifact taught: **a check that reports PASS without having measured anything is
worse than one that fails.** Two of five abort conditions were, for a moment, not actually being
tested.

**Also:** gen 21's `code_flags` has no `coverage_exclude_synt` key at all, because it ran before the
flag existed. The arms-differ comparison had to take the union of keys and treat missing as off. This
is why the harness now stamps the flag **False explicitly on both branches** — a missing key must
never again be indistinguishable from a deliberate off.

## 6. The state guard false positive fired again

Same five hardlinked `banc_brain.npz` names, same pre-existing defect documented in
`e24_phase1_result.md` §5. It fired on the control arm in E24 and fires here; it is not attributable
to `v_synt`. `git status` still reports no modification to `state/live_learner`. Still unresolved,
still separate follow-up.

## 7. Tests

17 new tests in `tests/test_coverage_exclude.py`, written before the organ change. Full suite
**782 passed, 3 skipped** (skips fell 5→3 because both E25 integration tests now have gen 22 and
pass). Zero erosion.

One E24 test was **amended, not deleted**: `test_e24_e23_still_off` originally banned the literal
strings `v_synt` and `v_frame` anywhere in the organ source. E25 re-opens one of those levers, and
legitimately — E23 was refuted because the guarded refusal *depended* on the denominator, and E24
relocated it. The invariant that actually matters is restated: with every flag off the denominator is
unchanged, E23's original gene names and both unimplemented variants are still absent, the floor is
still 0.6, and `ABSENCE_INVENTORY` is still default-off.

## 8. E26 — proposed next step

Per design §6 the variants are sequenced and **never combined**. `v_synt` is accepted, so the next
single variant gets its own generation.

> **E26: `v_frame` alone, in generation 23.**
>
> **Arms:** control = generation 21 (already run, `--absence-inventory` only). Treatment =
> generation 23, `--absence-inventory --coverage-exclude frame`. **`v_synt` OFF** — the variants are
> measured independently against the same baseline, not stacked, so each result stays attributable to
> one cut. That is the E5 two-arms lesson and design §6.
>
> `v_frame` adds frame words to the exclusion set. E23's pretest measured it recovering **3 of 9**
> `v_base` losses, against `v_synt`'s 1 and `v_all`'s 5.
>
> **Predicted outcome:** frozen 19/24 unchanged, paraphrase probes 0/14 → **1 or 2 of 14**, guarded
> 4/4 unchanged, scarf `coverage` still `None` with an unchanged reason.
>
> **Pre-registered abort:** B1–B7 unchanged. Additionally, **B8: if `v_frame`'s exclusion set contains
> any content word, abort** — `v_frame` is a larger set than `v_synt` and is the variant most likely
> to leak a noun or main verb into it, which is exactly the failure mode B7 exists to catch.
>
> **Sequencing after E26:** `v_all` (5 of 9) in generation 24, again alone. Only once all three are
> measured independently does combining them become a question worth asking — and if they are
> combined, that is a *new* experiment with its own pre-registration, not a continuation of this one.

**A caveat on expected value.** §4 is the reason to be careful here: recall is down to 8 failures and
the shape arbiter is now the second largest bucket. `v_frame` and `v_all` are both coverage levers, so
they are pushing on a constraint that is measurably loosening its grip. E23's "3 of 9" and "5 of 9"
were measured **offline on coverage alone**, without the reply gate, shape arbiter or mouth — and
E25 just demonstrated that crossing the floor does not guarantee a pass. The honest expectation for
E26 is **1 or 2 probe gains, possibly zero**, not 3.

**E26 requires an organ change and is not implemented here.** It awaits acceptance of this result.

## 9. Files

| file | change |
|---|---|
| `organs/neural_language.py` | `COVERAGE_EXCLUDE_SYNT` (default off), `_coverage_excluded`, one `continue` in the `must` loop |
| `tools/run_generation.py` | `--coverage-exclude {synt}`, stamped into `provenance.code_flags` on both branches |
| `tests/test_coverage_exclude.py` | 17 tests, written first |
| `tests/test_absence_inventory.py` | one test amended (E23 → E25 restatement) |
| `docs/evidence/e25_preregistration.md`, `e25_result.md`, `e25_check.py` | pre-registration, this file, verification |
| `state/selection/generation_22*.jsonl` | treatment arm |
