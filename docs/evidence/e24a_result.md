# E24a — read-only absence-inventory pre-test: result

**Probe:** `docs/evidence/e24a_absence_inventory_probe.py`, data `e24a_absence_inventory.json`.
Builds the inventory offline from `tools/scripts_heldout.json` and classifies all 24 scripted asks
against the generation-19 journal. **Zero brain builds, zero organ changes, no score, no genome, no
state touched.**

**Headline: the pre-registered abort is NOT triggered — all three decisive checks pass, and the
scarf guard is relocated. But the per-ask detail refutes the *answer* direction: 2 of the 3 licensed
answers are wrong, and one of them sits on a currently-passing ask. E24 phase 1 must license
REFUSAL ONLY. Answer licensing is out.**

---

## 1. The three pre-registered checks

| check | result |
|---|---|
| scarf ask receives a **licensed refusal** | **PASS** — subject `scarf` present, `place` absent |
| no **cross-subject** licence (the E15 failure) | **PASS** — 0 found |
| no currently-**passing** ask changes outcome | **PASS** — 0 found |

```
licences: fall_through 20, refusal 1, answer 3
```

**The guard is relocated.** `where did i say the scarf is?` binds subject `scarf`, queries relation
`place`, finds `scarf -> {property: wet}` with no `place` key, and receives a **licensed refusal**.
Its journal entry is `pass=True, cause=recall_gate, coverage=0.57` — it currently passes *by
refusing on a low ratio*. Under E24 it refuses because the organ knows the location was never told.
Same observable behaviour, different reason — which is exactly what design §4 required, and what
abort condition A5 tests for.

**Twenty of twenty-four asks fall through**, leaving the existing path untouched. The mechanism is
conservative by construction: it only speaks about subjects it actually holds.

**Zero cross-subject licences.** The E15 failure — licensing the scarf ask from
`the coat is on the hook` — is structurally absent. Note that this script's inventory holds *both*
`coat -> {property: wet, place: hook}` and `scarf -> {property: wet}`; the coat's `place` is right
there and the lookup still cannot reach it, because binding is by subject key, not by similarity.

## 2. What the checks missed: the answer direction is unsafe

Check 3 as written only tested whether a *refusal* licence would change a passing ask. It did not
test whether an *answer* licence would. Reading the three answer licences against their expected
answers:

| ask | inventory entry | licensed filler | correct | journal | verdict |
|---|---|---|---|---|---|
| `what does the frost bite?` | `frost:{agent: bites latch}` | `bites latch` | `latch` | pass | filler contains the verb — sloppy but not wrong |
| `what does the thing the frost bites hold?` | `frost:{agent: bites latch}` | `bites latch` | **`door`** | fail | **WRONG** — needs a hop |
| `what bites the latch?` | `latch:{agent: holds door}` | `holds door` | **`frost`** | **pass** | **WRONG, on a passing ask** |

Two of three are wrong, and the third row is a **regression risk on a currently-passing ask**.

The causes are distinct and neither is fixable by better extraction:

- **Multi-hop.** `what does the thing the frost bites hold?` requires `frost bites latch` then
  `latch holds door`. A single-subject inventory entry cannot compose two hops, and the design
  deliberately excluded ordering and composition from phase 1.
- **Passive voice.** `what bites the latch?` asks *what acts on* the latch. The inventory stores
  `latch` as a **subject** with its own agent relation (`holds door`), so the lookup returns the
  latch's action instead of the thing acting on it. The relation is keyed in the wrong direction for
  passives — the same asymmetry R2 was written for and which E5 measured as inert.

**Conclusion: E24 phase 1 licenses refusal only.** This is not a retreat — it is what the design
already implied. §3.1 restricted phase 1 to refusal to avoid E8's mood-gate override, because a
licensed refusal *is* silence, which the mood gate already produces. Extending that restriction to
the answer direction as well makes phase 1 purely subtractive: **the inventory can only add a reason
to stay silent, never a reason to speak.** A mechanism that can only refuse cannot assert a false
negative, which is precisely the bar the standing policy at `organs/neural_language.py:3052-3054`
sets.

Answer licensing becomes **phase 1b**, gated on solving directionality for passives and composition
for hops. Neither is pre-registered here.

## 3. The predicted extraction defect appeared, and was harmless

Design §9 flagged E16a's two measured extractor defects as a bounded risk. The quantity-frame defect
appeared exactly as predicted, in the `quantity-change` script:

```
tells 2 -> inventory subjects ['four', 'then']
  four: {'agent': 'eggs basket'}      <- from "there are four eggs in the basket"
  then: {'agent': 'two eggs break'}   <- from "then two eggs break"
```

`four` and `then` are not subjects. But **all four asks in that script fell through**, because none
of them contains `four` or `then` as a content word matching an inventory subject. The garbage
entries were never consulted.

This validates the conservatism rule that separates E24 from E15: **extraction failure counts as
`fall_through`, never as `refusal`.** Had a missing or malformed entry been treated as evidence of
absence, these four asks — all currently passing — would have been licensed to refuse. The rule is
load-bearing, and E24a is the measurement that shows why.

The multi-word-subject defect also appeared (`the thing the frost bites` bound to `frost`, not to a
composite subject), and is the direct cause of the multi-hop error in §2.

## 4. Verdict

**The pre-registered abort is not triggered. E24 proceeds to review — with phase 1 narrowed to
refusal licensing only.**

| design claim | E24a result |
|---|---|
| the scarf guard can be relocated off the coverage ratio | **confirmed** — licensed refusal, subject-bound |
| subject keying prevents the E15 cross-subject licence | **confirmed** — 0 occurrences, with the coat's `place` present and unreachable |
| the mechanism is conservative (most asks untouched) | **confirmed** — 20/24 fall through |
| absence is licensed only by a positively-built inventory | **confirmed** — garbage quantity entries never consulted |
| the inventory can license answers | **REFUTED for phase 1** — 2 of 3 wrong, one on a passing ask |

**Expected score change from phase 1: zero.** The scarf ask refuses either way. That is the
pre-registered success criterion, not a failure — E24's job is to free the denominator so E23 can be
re-tested, and E23 is where the 2–5 recovered gate failures would come from.

## 5. Consequences for the pre-registration

`docs/evidence/absence_inventory_design.md` should be read with these amendments, which E24a
established and which do not require re-opening the design:

1. **§2.2 read side, first branch** ("subject present, relation present → licenses an answer") is
   **deferred to phase 1b**. Phase 1 implements only the refusal and fall-through branches.
2. **Abort condition A3** gains a clause: any `answer` licence in phase 1 is an abort, since phase 1
   must not license speech at all.
3. **Test 3** (`test_e24_write_side_frames`) stands, but a new test is required:
   `test_e24_phase1_never_licenses_an_answer` — no ask receives an `answer` licence, and no ask's
   spoken output changes.
4. **Test 5** (`test_e24_no_cross_subject_licence`) is confirmed satisfiable — E24a measured 0.
5. The **sequencing in §6 is unchanged**: E24 alone (expected score change zero), then E23's `v_synt`
   re-tested against the relocated guard, then `v_frame`, then `v_all`, each separately.

## 6. Limitations

- **Offline, not in-organ.** The inventory is built by this probe's own extractor, not by the organ.
  A real implementation must extract frames at teach time inside the organ, and its extraction may
  differ. E24a validates the *design*, not an implementation.
- **24 scripted asks, 6 scripts.** The battery's other 18 rows (14 unseen paraphrases plus the 4
  guarded invariants) are not in `scripts_heldout.json` and were not classified. The paraphrase rows
  are the ones most likely to defeat subject binding, and they are untested here.
- **Subject binding by vocabulary match.** `subject_of` binds by matching inventory subjects against
  the ask's content words, and falls through on ambiguity. That is deliberately weaker than the
  organ's own head-noun rule (which E16a measured as defective) — but it means E24a cannot detect a
  binding failure that a real parser would make.
- **One guarded gate ask.** As in E23, the entire guard analysis rests on the scarf invariant, the
  only passing ask that reaches the recall gate.
- **`answer` licences were evaluated against expected answers by hand**, not by running the organ.
  The two wrong fillers are unambiguous (`door` vs `bites latch`, `frost` vs `holds door`), but a
  real implementation might phrase a correct filler differently.

## 7. Files

| file | change |
|---|---|
| `docs/evidence/e24a_absence_inventory_probe.py`, `.json`, `e24a_result.md` | new read-only probe, data, this file. |

**No change to `organs/`, `connectome/`, `tools/`, `tests/`, genomes or any score.** E24 remains
pre-registered and unimplemented.
