# E24 — session-scoped absence inventory: design and pre-registration

**Status: PRE-REGISTERED. NOT IMPLEMENTED. No organ behaviour, genome, flag or score is changed by
this document.**

**Companion read-only probe:** `docs/evidence/e24a_absence_inventory_probe.py` (specified in §9). It
builds the inventory offline from `scripts_heldout.json` and tests the guard condition with **zero
brain builds and zero organ changes**. E24 is not implemented until both this design and the E24a
result are accepted.

---

## 1. Why E24, and what it is actually for

E23 established something sharper than a null result. Excluding closed-class question syntax from
the coverage denominator **works** — it recovers 2, 3 or 5 of the 9 gate failures depending on how
much syntax is removed — and **all three variants break the guarded scarf invariant**, because the
scarf ask passes *by refusing* at coverage 0.5797, only 0.0203 below the floor.

The obstruction is not the exclusion set. It is this:

> **The scarf ask refuses for the wrong reason.** The user never said where the scarf is. The organ
> refuses because a ratio of IDF-weighted term overlaps fell below a threshold — not because it knows
> the location was never told.

That is why the guard and the repair are in arithmetic opposition. Both are governed by one
quantity, and no monotone change to it separates them.

**E24's goal is therefore not to gain asks.** It is to **relocate the guard**: give the organ a
positive, non-ratio reason to refuse the scarf ask. If refusal comes from an inventory of what was
actually told, then the coverage denominator stops carrying the guard's weight — and E23's lever,
which is already measured to recover up to 5 of 9 gate failures, becomes deployable.

**Success criterion (pre-registered, and deliberately not a pass count):**

> The scarf ask still refuses, for an inventory reason, while the coverage denominator is free to
> change. Frozen 19/24 and guarded 4/4 must hold. **Gaining asks is E23's job, not E24's.**

Judging E24 by pass count would be the E5 mistake in reverse: a mechanism that changes *why* the
organ refuses can be perfectly correct and move the score by zero.

## 2. The mechanism

A **session-scoped inventory of told facts**, written at teach time and consulted at ask time.

### 2.1 Write side

When a tell is stored, its frame is also recorded in a session-scoped structure:

```
inventory[subject] -> { relation -> object }
```

Three relation classes are in scope for phase 1, because they are the ones the battery's guarded and
gate asks actually turn on:

| relation | example tell | entry |
|---|---|---|
| `property` | `the scarf is wet` | `scarf -> {property: wet}` |
| `place` | `the coat is on the hook` | `coat -> {place: hook}` |
| `agent` | `the frost bites the latch` | `frost -> {agent: bites, object: latch}` |

The inventory is **append-only within a session** and is discarded with the session. It is not
persisted to `state/`, not merged across brains, and not a second memory — it is an index over what
was told *in this conversation*.

### 2.2 Read side

A question is classified by its interrogative into a **queried relation**:

| interrogative | queried relation |
|---|---|
| `where` | `place` |
| `what is X like` / `which … wet/dry` | `property` |
| `what does X verb` / passive `what is verbed by X` | `agent` |

Then:

- **Subject present, relation present** → the inventory *licenses an answer* and supplies the filler.
  The coverage gate is not consulted for the refusal decision.
- **Subject present, relation absent** → **licensed refusal**. This is the scarf case: `scarf` is in
  the inventory with `property: wet` and no `place`. The organ can refuse because it *knows* the
  location was never told, not because a ratio was low.
- **Subject absent** → **no licence either way**. Fall through to the existing coverage gate
  unchanged. The inventory makes no claim about subjects it has never seen.

The third branch is what keeps this conservative: the inventory can only *add* a reason to refuse or
to answer for subjects it actually holds. It cannot make the organ assert anything about an unknown
subject.

## 3. Explicitly addressing the E8 and E15 failure modes

These are the two prior attempts that died, and each died for a reason that must be designed around
rather than hoped away.

### 3.1 E8 — mood-gate override

**What happened.** E8 aborted at its own pre-registered condition. Its three polar asks
(`hop-and-inventory`, `disjunction-neither`, `negation-absent`) were refused by the **mood gate**
before any answer path was reached: `understands` was True and `wants_to` was False, producing
silence. The organ's standing policy at `organs/neural_language.py:3052-3054` explicitly prohibits
saying "no" until a mechanism can express absence without asserting a false negative.

**How E24 avoids it.** E24 phase 1 licenses **refusal only**, never a negative answer.

This is the decisive design choice. A licensed refusal *is* silence — which is exactly what the mood
gate already produces. So phase 1 needs **no mood-gate override at all**: the inventory supplies a
*reason* for a behaviour the organ already exhibits, and the observable output is unchanged. The
mood gate cannot pre-empt a mechanism that does not ask it to speak.

**Phase 2 — negative answers (`no`, `neither`, `nothing`) — is explicitly out of scope** and is not
pre-registered here. It would require overriding the mood gate, which is the condition that aborted
E8, and it would require the organ to assert absence in language. E24 phase 1 is a precondition for
phase 2, not a substitute for it: only once absence is *represented* can the organ be licensed to
*say* it. Until then the policy at 3052-3054 stands and is not touched.

### 3.2 E15 — null retrieval

**What happened.** E15's provenanced entailment licensed the guarded scarf ask **from
`the coat is on the hook`** — a locative row about a *different subject* — and five passing asks were
newly licensed with four confidently wrong. Its retrieval-based approach also inherited E14a's
finding that 5 of 9 gate asks lack their taught row among candidates at all.

**How E24 avoids it.** The inventory is **written at teach time, not retrieved at ask time.**

There is no recall call, no candidate set, no top-k window, and therefore **no null retrieval**. The
structure is built from the tells as they arrive, so it is complete by construction with respect to
the session. E14a's candidate gap, E21a's corpus-mass ranking and E19's eviction are all properties
of *retrieval*; none of them can affect a structure that was never retrieved.

This is also why E24 is not another read-time inference layer over unstructured prose rows — the
architecture review's finding about all seven closed lines. It is a **write-time relation
primitive**, which is what that review recommended.

### 3.3 E15 — subject binding

**What happened.** E15 licensed `where did i say the scarf is?` from a row whose subject was `coat`.
Provenance separated told from book, but nothing separated *which* told fact answers *which*
question.

**How E24 avoids it.** The inventory is **keyed by subject**. A `where` query about `scarf` looks up
`inventory["scarf"]` and finds `{property: wet}` — no `place` key. It cannot reach
`inventory["coat"]`, because the lookup is by subject, not by similarity. The E15 failure is
structurally impossible: there is no code path by which one subject's entry licenses another
subject's question.

Subject normalisation is the residual risk and is addressed in §7 (abort condition A3) and §9 (E24a
measures it directly).

## 4. Guard preservation

The scarf invariant is the guard that killed E12a, E15 and E23. Under E24:

| ask | inventory state | licence | outcome |
|---|---|---|---|
| `where did i say the scarf is?` | `scarf -> {property: wet}` | **place absent** | **licensed refusal** — still refuses, now for a positive reason |
| `is the coat dry or wet?` | `coat -> {place: hook}` … | property absent | falls through to the existing gate (currently passes) |
| `what does the frost bite?` | `frost -> {agent: bites, object: latch}` | **agent present** | licensed answer `latch` (currently passes) |

**The guard is preserved and strengthened.** The scarf ask refuses in both worlds, so guarded 4/4
holds. But the *reason* changes from "coverage 0.5797 < 0.6" to "no place was ever told for the
scarf" — and that is what frees the denominator.

**Pre-registered guard test:** with the inventory active, the scarf ask must refuse, and its refusal
must be attributable to the inventory (a `licensed_refusal` reason), **not** to the coverage floor. If
it still refuses only because coverage is low, E24 has not relocated the guard and has failed its
purpose even if the score is unchanged.

## 5. Scope boundaries

**In scope (phase 1):**
- Session-scoped inventory, written at teach time, discarded with the session.
- Three relation classes: `property`, `place`, `agent`.
- Licensed refusal for subject-present/relation-absent.
- Fall-through to the existing gate for subject-absent.
- Default-off flag, e.g. `--absence-inventory`.

**Out of scope, explicitly:**
- **Negative answers.** No `no`, `neither`, `nothing`. No mood-gate override. Phase 2, not
  pre-registered.
- **Quantity and counting.** `how many eggs are left`, `what number of eggs`. E17a found the genuine
  event-count ask already passes and the rest are frequency adverbials or rehearsal counts. A
  counting primitive is a separate design.
- **Ordering.** `before the kettle`, `which came first`. E19/E20/E22a all classify these as
  not-a-retrieval-problem; they need a sequence primitive.
- **Cross-session persistence.** The inventory is not written to `state/`. Promoting it would
  redefine what 19/24 means, the same objection that required a separate `state/live_learner/`.
- **Any change to the coverage denominator.** E23 stays refuted and unimplemented. E24 must be
  validated *alone*, so that if the score moves, the cause is known. Combining them in one generation
  would make attribution impossible — the E5 two-arms lesson.

## 6. Interaction with E23

E24 and E23 are **sequenced, never combined**:

1. **E24 alone.** Does the inventory relocate the scarf guard without losing frozen or guarded passes?
   Expected score change: **zero**. That is success, not failure.
2. **E23 alone, re-tested.** With the guard relocated, does `v_synt` still break the scarf invariant?
   The pre-test says it lifts coverage to 0.6676 — but if refusal no longer depends on coverage, the
   ask refuses anyway, on inventory grounds. **This is the step that could recover 2 of 9 gate
   failures.**
3. Only then, `v_frame` (3 of 9) and `v_all` (5 of 9), each separately.

If step 1 does not hold the guard, steps 2 and 3 are unreachable and E23 stays closed.

## 7. Abort conditions (pre-registered)

| # | condition | rationale |
|---|---|---|
| **A1** | Frozen passes fall below 19/24, or guarded below 4/4. | The standing hard constraint. |
| **A2** | The scarf ask stops refusing. | The guard E12a, E15 and E23 all died on. |
| **A3** | The inventory licenses an answer for a subject it does not hold, or licenses from a different subject's entry. | The E15 failure mode. Any cross-subject licence aborts immediately. |
| **A4** | The inventory is consulted for a subject-absent question, or changes any ask whose subject is not in the inventory. | The fall-through branch must be inert. If it is not, the mechanism is not conservative. |
| **A5** | The scarf ask still refuses **only** because coverage is below the floor, with no `licensed_refusal` reason recorded. | E24's actual purpose. A score-neutral run that did not relocate the guard is a failure, not a success. |
| **A6** | The inventory is read at ask time via `binder.recall` or any similarity search. | Would reintroduce null retrieval (E15) and corpus-mass ranking (E21a). The inventory must be a direct keyed lookup. |
| **A7** | Any negative answer is produced, or the mood gate is overridden. | Phase 2 scope. The policy at `neural_language.py:3052-3054` is not touched. |
| **A8** | Subject normalisation requires a hand-written list of the battery's subjects. | E16a's D4 and E10's Finding 1 both forbid ask-fitted vocabulary. |
| **A9** | Frame extraction needs a relation class outside `property`/`place`/`agent` to hold the guard. | Scope creep into counting or ordering, which are separate designs. |

**A5 is the one that makes this pre-registration honest.** Every prior line could pass by doing
nothing; E24 cannot, because doing nothing means the guard stays on the denominator and the design
has failed.

## 8. Tests (to be written before any organ change)

1. `test_e24_flag_default_off` — with the flag unset, every ask in the battery scores byte-identically
   to generation 19. Zero behaviour change by default.
2. `test_e24_inventory_is_session_scoped` — the inventory is empty at session start, populated by
   tells, and not written to `state/`.
3. `test_e24_write_side_frames` — `the scarf is wet` → `scarf:{property:wet}`; `the coat is on the
   hook` → `coat:{place:hook}`; `the frost bites the latch` → `frost:{agent:bites,object:latch}`.
4. `test_e24_scarf_licensed_refusal` — the scarf ask refuses **and** carries a `licensed_refusal`
   reason attributable to `place` being absent for `scarf`. (Guards A2 and A5.)
5. `test_e24_no_cross_subject_licence` — a `where` query about `scarf` never reads `coat`'s entry,
   under any phrasing. (Guards A3.)
6. `test_e24_subject_absent_falls_through` — for every ask whose subject is not in the inventory, the
   coverage path and the outcome are unchanged. (Guards A4.)
7. `test_e24_no_negative_answers` — no ask produces `no`, `neither`, `nothing`, or any assertion of
   absence in language; the mood gate is not overridden. (Guards A7.)
8. `test_e24_keyed_lookup_not_retrieval` — the read path performs no `binder.recall` and no
   similarity search. (Guards A6.)
9. `test_e24_frozen_and_guarded` — 19/24 frozen, 4/4 guarded. (Guards A1.)
10. `test_e24_e23_still_off` — the coverage denominator is unchanged; E23's exclusion sets are not
    present in the organ. (Guards §5.)

Tests 4, 5 and 6 are the load-bearing ones. Test 4 in particular cannot be satisfied by an inert
mechanism, which is the point.

## 9. E24a — read-only pre-test

**Can be run with zero brain builds and zero organ changes**, exactly as E23's pre-test was.

`docs/evidence/e24a_absence_inventory_probe.py`:

1. Read `scripts_heldout.json`. For each script, extract frames from its tells using the copula /
   locative / agent patterns only — the three classes E16a's extractor handled correctly.
2. Build the session inventory offline: `subject -> {relation -> object}`.
3. For each of the 42 battery asks, classify the interrogative into a queried relation and look up
   the subject.
4. Report, per ask: subject found? relation found? licence = `answer` / `refusal` / `fall_through`.
5. **The decisive checks:**
   - Does the scarf ask get a **licensed refusal** (subject `scarf` present, `place` absent)?
   - Does any ask get licensed from a **different subject's** entry (the E15 failure)?
   - How many asks fall through, i.e. leave the existing path untouched (the conservatism measure)?
   - Does any currently-passing ask get a licence that would **change** its outcome?

**Pre-registered E24a abort:** if the scarf ask does not receive a licensed refusal offline, or if
any cross-subject licence appears, E24 is refuted before implementation and no organ change is
proposed — the E8/E23 pattern.

**Known bounded risk.** E16a's extractor had two measured defects: the head rule mis-binds multi-word
subjects (`the thing the frost bites` → `thing`), and quantity frames mis-extract
(`there are four eggs in the basket` → entity `basket`; `then two eggs break` → entity `break`).
Neither is in scope for phase 1: the guard turns on `scarf`/`coat` copula and locative frames, which
E16a extracted correctly, and quantity frames are excluded by §5. E24a must nonetheless **report**
how many asks hit those defective patterns, so the fall-through count is not silently inflated by
extraction failure. If extraction fails for a subject, that ask must be counted as `fall_through`,
never as `refusal` — a missing entry is not evidence of absence.

That last rule is the whole difference between E24 and E15: **absence is licensed only by a
positively-built inventory, never by a failure to find something.**

## 10. Files

| file | change |
|---|---|
| `docs/evidence/absence_inventory_design.md` | this pre-registration. |
| `docs/evidence/e24a_absence_inventory_probe.py`, `.json` | the read-only pre-test, to be written next. |

**No change to `organs/`, `connectome/`, `tools/`, `tests/`, genomes or any score.** No flag exists,
because the mechanism it would gate is not yet accepted.
