# E25 — pre-registration: `v_synt` re-tested against the relocated guard

**Status: PRE-REGISTERED, NOT YET RUN.**
**Depends on:** E24 phase 1 accepted (`docs/evidence/e24_phase1_result.md`, commit `d32e836`).
**Flag:** `--coverage-exclude synt` (default off), organ attribute `COVERAGE_EXCLUDE_SYNT`.
**Arms:** generation 21 (control, already run) vs generation 22 (treatment).

---

## 0. A correction to the E25 proposal, made before the run

The E25 sketch in `e24_phase1_result.md` §10 predicted **"19/24 → 21/24 frozen"**. That is **wrong**,
and it is corrected here rather than after the run.

E23's pretest measured `v_synt` lifting two asks over the floor:

| ask | `v_base` | `v_synt` | **tier** |
|---|---|---|---|
| `how often does the bell turn?` | 0.545 | **0.700** | **probe** |
| `what is held by the thing the frost bites?` | 0.534 | **0.640** | **probe** |

Both are **probe** tier. The two *frozen* recall failures stay below the floor under `v_synt`:

| ask | `v_base` | `v_synt` | tier |
|---|---|---|---|
| `how many times does the bell turn?` | 0.5417 | 0.5417 | frozen — **unchanged** |
| `what did i tell you about before the kettle?` | 0.4148 | 0.4148 | frozen — **unchanged** |

So `v_synt` cannot move the frozen score at all on this battery. The corrected prediction is below.
Recording the error matters: the frozen number is the one the whole selection harness is built on, and
a pre-registration that predicted movement there would have been unfalsifiable in the direction that
counts.

## 1. Hypothesis

E24 phase 1 took the guarded scarf ask's weight **off** the coverage denominator: it now refuses on
inventory grounds with `coverage: None`, never reaching the gate. E23 was refuted *only* because that
ask's refusal depended on the denominator, so any denominator change was unsafe by construction.

**With the guard relocated, E23's `v_synt` lever is re-testable.** `v_synt` excludes function words
and interrogatives from `must` — the set whose size is the coverage denominator.

## 2. Predicted outcome (corrected)

| metric | control (gen 21) | predicted treatment (gen 22) |
|---|---|---|
| frozen | 19/24 | **19/24 — unchanged** |
| probes | 0/14 | **2/14** |
| guarded | 4/4 | **4/4 — unchanged** |
| total passes | 23/42 | **25/42** |
| scarf `coverage` | `None` | **`None`** |
| scarf `reason` | `scarf was told but no place was ever told for scarf` | **identical** |
| stage distribution | `{recall 10, mouth 4, gating 3, shape_arbiter 2}` | `{recall 8, mouth 4, gating 3, shape_arbiter 2}` |

**Crossing the floor is necessary but not sufficient.** An ask must then survive the reply gate, the
shape arbiter and the mouth. `how often does the bell turn?` and `what is held by the thing the frost
bites?` both currently fail at `recall`, so lifting them past the floor only moves them to the *next*
gate — they may still fail there. **2/14 is a prediction, not a promise**; 0/14 with both asks
advancing past `recall` to a later stage would still be a real, if smaller, result.

## 3. Arms and controls

- **Control = generation 21, already run and published.** `--absence-inventory` on, `v_synt` off.
  No new control arm is needed: gen 21 and gen 22 will differ in exactly one code flag, and gen 20
  already established that the harness reproduces gen 19 byte-for-byte (0 differing keys), so the
  noise floor is measured at zero.
- **Treatment = generation 22.** `--absence-inventory --coverage-exclude synt`.
- Same genome `abffa2b7f101`, same 42-ask battery, same interpreter, one arm per process.
- Both flags recorded in `provenance.code_flags`.

## 4. Abort conditions

| # | condition | consequence |
|---|---|---|
| **B1** | **the scarf ask stops refusing** (`pass` False, or it produces an answer) | **E25 aborts, E23 stays closed.** The relocation did not actually protect the guard. |
| **B2** | **guarded < 4/4** | E25 aborts. |
| **B3** | **frozen < 19/24** | E25 aborts. Zero erosion is absolute. |
| B4 | scarf `coverage` is no longer `None`, or its `reason` changes | E25 aborts — the inventory is no longer pre-empting the gate, so the arms are not comparable. |
| B5 | any ask that the control **answered** starts refusing | E25 aborts. `v_synt` must not subtract answers. |
| B6 | `v_synt` is found to alter `must` for a **subject-absent** ask | E25 aborts — out of scope by design. |
| B7 | the exclusion set contains any content word | E25 aborts. `v_synt` is `FUNCTION | INTERROG`, closed classes only. |

**B1 is the load-bearing condition**, exactly as A5 was for E24. B3 is the one that makes the
corrected prediction safe: since `v_synt` provably cannot move any frozen ask's coverage over the
floor, a frozen drop would mean the mechanism is doing something other than what was measured.

## 5. Scope

**In scope:** one exclusion set applied to `must` in the coverage gate, behind a default-off flag;
the `--coverage-exclude` CLI flag; tests written first; the two-arm comparison.

**Out of scope, and not touched:**
- `v_frame` and `v_all` — **not combined with `v_synt`**, per design §6 and the E5 two-arms lesson.
  If `v_synt` passes, the next variant gets its own generation.
- The absence inventory itself (E24 phase 1, already accepted).
- The coverage **floor** value, the mood gate, the reply gate, the shape arbiter, the mouth.
- The `cause_all` taxonomy's missing `absence_licence` bucket — still deferred, for the same reason
  as in E24: changing it mid-series breaks comparability.
- The state-guard hardlink false positive — pre-existing, separate follow-up.
- No multi-brain work. No broad refactors.

## 6. Sequencing if E25 passes

`v_synt` alone → then `v_frame` (3 of 9) in its own generation → then `v_all` (5 of 9) in its own
generation. Never combined. Each re-runs B1–B7. E23's pretest says `v_all` recovers 5 of 9
`v_base` losses, but that was measured **without** the relocated guard and **without** the probe-tier
correction above, so its frozen-battery value is unknown until measured.

## 7. Files

| file | change |
|---|---|
| `docs/evidence/e25_preregistration.md` | this file |
| `tests/test_coverage_exclude.py` | tests, written first |
| `organs/neural_language.py` | `COVERAGE_EXCLUDE_SYNT` + the exclusion in the coverage gate |
| `tools/run_generation.py` | `--coverage-exclude` code flag |
| `docs/evidence/e25_result.md` | result, after the run |
| `state/selection/generation_22*.jsonl` | treatment arm |
