# A comprehension signal for `understands`

**Status: design only. Nothing here is implemented.** This document proposes the smallest
experiment that could replace `max(resonance)` as the organ's test for "he understood the
question", states what it predicts, and ends with a pre-registered E11 that costs **zero
brain builds** and can kill the idea before any gene is written.

It exists because E9 and E10 localised the blocker to a single scalar and then proved that
no amount of pool-filtering moves it.

---

## 1. What the two negatives established

On the resonance answer path, `understands` is `res[best] >= reply_threshold`, with
`reply_threshold = 0.55` and `res` computed **once over the full 11,439-word vocabulary
before any filter runs**.

Three measurements, all from committed journals:

| quantity | value | source |
|---|---|---|
| corpus attractors that clear 0.55 | `numbered` 0.5811, `sold` 0.5722 | `e9_analysis.py` |
| best honest content word | `lantern` **0.4129** | `e10_scope_probe.json` |
| other wanted words | `bell` 0.1221, `scarf` 0.1526 | `e10_scope_probe.json` |

So the 0.55 bar is cleared **only** by high-frequency corpus words unrelated to the
question. Nothing a session actually taught reaches it. On this path comprehension and
attractor are the same event.

E9 removed the corpus attractors by scoping to session words; the session's own `the`
became a second attractor and the organ went silent. E10 removed `the` with the organ's own
distributional rule; `is` and `on` survived (the binder is 99.19% `book`, where document
frequency measures corpus style, not lexical class), and the winner still sat at 0.4129.
**Arm B of E10 is indistinguishable from arm B of E9** — same 19/24, 0/14, 4/4, same stages,
same seven silences.

The general lesson, and the reason this document is not another filtering proposal:

> Once the winner is below the bar, removing candidates cannot help. The ranking is
> downstream of the decision. **The decision itself is the defect.**

`max(resonance)` is a *frequency-and-corpus-similarity* measure wearing the name of a
*comprehension* measure. It is ask-independent (E9 measured the same attractors winning
unrelated asks), which is disqualifying: a comprehension signal must vary with the question.

---

## 2. What a comprehension signal has to do

It answers one question: **does he hold material bearing on this question?** Not "is a
plausible answer word resonating", and not "is the answer good enough" (that is the coverage
floor's job, downstream and separately measured).

Four constraints, each earned from a prior negative:

1. **Ask-dependent.** E9's attractors won unrelated asks. Any signal that returns ~the same
   value for `what does the thing the frost bites hold?` and `repeat after me the copper
   bell turns twice` is another attractor, whatever it is called.
2. **Not frequency-dominated.** This is what kills `max(resonance)` and what killed E10's
   `is`/`on`. A signal proportional to corpus document frequency will rank `numbered` above
   `scarf` by construction.
3. **Must not need a content/function distinction.** E10's Finding 1 is that we do not have
   one: the distributional rule misclassifies `is`/`on`, and a hand list was rejected as
   unprincipled. **Any design that requires separating content from function words inherits
   a known-broken component.** This constraint is the hardest and rules out the obvious
   term-overlap designs.
4. **Must not move `reply_threshold`, must not rescale resonance, must not touch the recall
   gate's `must` rule.** These were forbidden-on-abort in E9 and E10 and stay forbidden.

---

## 3. Three candidate signals, judged against the evidence

### 3a. Term coverage — **rejected as the comprehension signal**

`coverage` already exists and is already reported per ask. It is tempting: it is
ask-dependent and frequency-independent.

But it measures the wrong thing at the wrong time. Coverage scores a **formed answer**
against the question; it is computed after the organ has decided to speak, and it is the
input to `ANSWER_COVERAGE_FLOOR`. Using it as the *comprehension* gate would make the organ's
decision to speak depend on an answer it has not yet committed to — circular, and it
collapses two independently-measured gates into one.

It is also already known to be saturated: the exact unrounded coverages are `kettle` 0.555
and `scarf` 0.570 against a floor of 0.6, and the window between them is **empty**
(`coverage_floor_reach.py`). Generations 1, 2 and 6 proved the floor cannot be lowered to
admit them without losing the guarded scarf invariant (g2-3 at 0.566857 lost it at
`shape_arbiter`). Coverage is a real gate; it is not a comprehension signal.

**Kept as evidence, not as the mechanism.** Its exact values are load-bearing for §7 below.

### 3b. Relation support — **rejected for E11, recorded for later**

The strongest available signal: does the store contain a relation `(A, V, B)` whose `V` is
the queried verb and whose `A`/`B` include the queried terms? This is what
`docs/archive/role_chain_proposal.md` gestures at, and what E8's `_ordinal_answer` docstring
describes as "contains at least one relation with the queried verb, and lacks `(A,V,B)` in
both directions".

Rejected for the first experiment on the same grounds E8 was aborted on: it needs passive
normalisation (R2's `SHAPE_ALLOW_PASSIVE` was measured **inert** in E5 and cannot be assumed
to work) and it needs the role-binding machinery to be reliable, which the answer-path
classification says it is not — learned interrogatives are `how/what/where/who`, `which` was
never learned, and 2 of the 19 failures are at `shape_arbiter`. Building a comprehension
signal on top of a parser that cannot handle `which` would confound the two defects.

### 3c. Session-provenanced term support — **chosen**

> **Does a row he was *told*, rather than a row from the book, contain the terms of this
> question together?**

`support(q) = max over binder rows r with r.who != "book" of |terms(q) ∩ terms(r)| / |terms(q)|`

Why this satisfies all four constraints:

- **Ask-dependent** by construction — the numerator is an intersection with *this* question's
  terms.
- **Not frequency-dominated** — provenance, not frequency, does the selecting. A `book` row
  containing `the` and `scarf` contributes nothing; a `droso` row does. This is the single
  property `max(resonance)` lacks.
- **Needs no content/function distinction.** This is the decisive advantage and the reason
  3c beats a plain term-overlap design. Function words inflate the numerator, but they
  inflate it **only for rows he was told**, and there are few of them: the census is
  `book` 59,515 / `droso` 466 / `parent` 19 / `you` 0 of 60,000. `the` co-occurring with
  `scarf` in a session row is *evidence about the session*, not corpus noise. E10's Finding 1
  is sidestepped rather than solved — which is the honest framing: we do not know which words
  are function words, so we use a signal that does not need to know.
- **Touches nothing forbidden.** It reads the binder, which the organ already reads.

**Known bias, stated up front rather than discovered later.** `the` occurs in nearly every
session row, so it adds roughly a constant to every numerator. That is a **bias, not a
discriminator** — it shifts all asks equally and so cannot create the ask-independence that
disqualified resonance. It does compress the dynamic range, which is why §6 pins the
separation margin rather than the absolute value.

---

## 4. Flag-gated prototype

One gene, default off, inert:

```python
COMPREHENSION_SESSION_SUPPORT = False   # E11: replaces max(resonance) >= reply_threshold
                                        # as the resonance path's test for `understands`.
                                        # Off = the old comparison, line for line.
```

Applied at exactly one site — the resonance path's `understands` test — as an **alternative**,
not an additional conjunct, so that flag-off is provably the old code:

```python
if COMPREHENSION_SESSION_SUPPORT:
    understands = self._session_support(terms) >= COMPREHENSION_SUPPORT_FLOOR
else:
    understands = res[best] >= reply_threshold      # unchanged, verbatim
```

`_session_support` is a **new read-only method**. It must not write the binder, must not
evict, and must not be reachable from the recall gate — the same isolation E10's
`_is_content_word` was tested for, because the guarded floor must stay untouched.

`COMPREHENSION_SUPPORT_FLOOR` is a **module constant, not a genome gene.** Deliberately: the
selection harness mutates genes, and a threshold that selection can drift is a threshold that
will be tuned to the battery. Its value is fixed by §6's offline probe and then frozen.

Both `RESONANCE_SESSION_SCOPE` and `RESONANCE_CONTENT_SCOPE` stay **off** during E11. E9/E10
are refuted; their genes are inert; E11 measures the support signal against the *unmodified*
resonance pool so that a stage change is attributable to one variable.

---

## 5. Tests, written before the gene

Unit level, no brain build:

1. **Flag-off is the old code.** With the gene `False`, `understands` is
   `res[best] >= reply_threshold` for a range of synthetic `res` values straddling 0.55.
2. **Flag-off never calls `_session_support`.** A stub that raises if invoked; assert the
   battery path completes. (E10's `_CStub` bug — a stub that silently failed to override the
   method under test, so every assertion passed for the wrong reason — is the reason this is
   a separate test from #1.)
3. **Ask-dependence.** Two different questions over the same binder return different support.
   This is the property resonance lacks; if it fails, the signal is another attractor.
4. **Provenance does the work.** A term set present only in `book` rows scores **low**; the
   same set present in a `droso` row scores **high**. Same terms, same binder, opposite
   verdict — this is the whole mechanism in one test.
5. **Frequency-independence.** A high-`df` corpus word (`numbered`) does not outrank a
   low-`df` session word (`scarf`) on a question about the scarf.
6. **The `the` bias is a bias.** Support for a question containing `the` and one not
   containing it differ by less than the separation margin in #3, on the same content terms.
7. **Isolation.** `_session_support` is unreachable from the recall gate; the guarded floor
   computation is byte-identical with the gene on and off.
8. **Read-only.** Binder row count and the `who` census are unchanged after a call.
9. **Empty/unreadable binder falls back** to `understands = False`, never to `True` — a
   missing signal must produce silence, not babble.

Outcome level, pinned from the committed journals after the run:

10. **P1 flag-off identity** — arm A vs generation 13, zero field differences across
    `pass`, `stage`, `cause`, `source`, `coverage`.
11. **P5 zero erosion** — no frozen pass lost, no guarded pass lost, guarded 4/4.
12. **P6 no new babble** — no ask gains a `source` that arm A lacked, unless it also gains
    a `pass`. A wrong confident answer scores the same as silence on this battery; only this
    test tells them apart. (This is the E8 lesson, applied prospectively.)

---

## 6. Abort conditions

Checked in this order. **Any one aborts E11; none may be answered by tuning.**

| # | condition | why it is fatal |
|---|---|---|
| A1 | support is ask-independent (range across the 42 asks < 0.10) | it is another attractor; constraint 1 violated |
| A2 | support does not separate the 4 `mouth` asks from the 10 `recall` asks in the **offline probe** | the signal carries no information about the defect it was designed for |
| A3 | flag-off is not line-for-line identical (P1 fails) | the gene is not inert; the whole flag discipline is void |
| A4 | any frozen or guarded pass is lost (P5 fails) | non-negotiable, as in every prior generation |
| A5 | any ask gains a `source` without gaining a `pass` (P6 fails) | confabulation — the E8 failure mode |
| A6 | `mouth` stage mass does not move at all | the signal is not reaching the decision; do not tune it into reaching |

**A2 is checked before any gene is written.** That is §8.

Forbidden, as before: moving `reply_threshold`, rescaling resonance, adding a stopword list,
lowering `ANSWER_COVERAGE_FLOOR`, touching the recall gate's `must` rule, widening to
"recent" words, and any multi-brain or population work.

---

## 7. Expected score changes — the honest prediction

**The headline prediction is that the score does not move, and that this is a success.**

Trace the four `mouth` asks through the pipeline under a working support signal:

1. `understands` becomes `True` — the session did teach `the scarf is on the hook` and
   `the scarf is wet`, so provenanced support is high. **The organ stops being silent.**
2. An answer is formed and reaches the coverage floor.
3. Its coverage is **0.555** (kettle ask) and **0.570** (scarf ask) — both **below**
   `ANSWER_COVERAGE_FLOOR = 0.6`.
4. It fails at the gate. Stage moves `mouth` → `recall`/gate. **No pass.**

And the floor cannot be lowered to admit them: generation 2's g2-3 at 0.566857 lost the
guarded scarf invariant at `shape_arbiter`, and generation 6 at 0.587206 was `no_gain`. The
window between 0.555 and 0.570 is **empty**.

So the predicted result is:

| metric | arm A (gen 15) | arm B (gen 16) | note |
|---|---|---|---|
| frozen | 19/24 | **19/24** | unchanged; P5 |
| probes | 0/14 | **0/14** | unchanged — this is the prediction |
| guarded | 4/4 | **4/4** | unchanged; P5 |
| stages | `{recall:10, mouth:4, gating:3, shape_arbiter:2}` | `{recall:14, gating:3, shape_arbiter:2}` | **`mouth` → 0** |
| speaking asks | 27 | **31** | the four stop being silent |
| passes gained | — | **0** | |

**Why run an experiment predicted to gain nothing?** Because it converts a *conjecture* into
a *measurement*, and the conjecture is load-bearing for everything downstream. Right now the
project has two competing accounts of the `mouth` class:

- resonance is the terminal blocker (E9/E10's framing), or
- the **coverage floor** is the terminal blocker and resonance was only the proximate cause.

E11 discriminates them. If `mouth` mass moves to `recall`/gate and the score holds, the
second account is confirmed and the entire resonance line of work — E9, E10, and any E11
successor — is **closed as a dead end**, with the blocker relocated to a gate whose exact
thresholds are already known to be unmovable. That is a larger reduction in uncertainty than
4 probe passes would be.

If instead the score *does* move, the prediction above is wrong in an informative direction
and the coverage-floor account needs revisiting.

Secondary expectations, stated so they can be checked:

- The **3 `gating` failures** are unaffected. Their recorded reason is *"it understood but
  did not feel like speaking"* — `understands` is already `True` there, so a better
  comprehension signal cannot change them. If it does, something else moved.
- The **9 `recall_gate` failures** (`cause_of()` = `recall_gate`) are unaffected; they fail
  the coverage floor, not comprehension.
- The **1 `comprehension` failure** is the only frozen-tier ask this signal could plausibly
  fix. Predicted: **not fixed**, because its coverage is also below floor. This is a
  1-ask prediction and is falsifiable on its own.
- The **2 `shape_arbiter` failures** are unaffected; that is a parser defect (E5).

---

## 8. E11 — the smallest pre-registered step

**E11a: an offline discriminability probe. Zero brain builds. No organ change. No gene.**

Everything needed already exists on disk: `state/selection/generation_13_asks.jsonl` (42 asks
with `stage`, `cause`, `coverage`, `source`) and `state/live/language_state.json` (the binder,
60,000 rows with `who`). The probe computes `_session_support` as a **standalone function in
the evidence script** — not in the organ — for all 42 asks, and reports:

1. support per ask, grouped by `stage`;
2. the range across all 42 asks → **A1**;
3. the margin between the 4 `mouth` asks and the 10 `recall` asks → **A2**;
4. the `the`-bias measurement (test #6) on real asks;
5. whether `numbered`/`sold` score below `scarf`/`lantern` on their own asks (test #5);
6. the support value that would be needed as `COMPREHENSION_SUPPORT_FLOOR`, and whether any
   single threshold separates `mouth` from `recall` **without** also admitting the 10
   recall-gate failures.

Item 6 is the one that can kill the design outright, and it is checkable in about a minute.
If no threshold separates them, the signal is not merely unhelpful — it is **indistinguishable
from the defect**, and E11b must not be run.

**Cost: one binder read, no builds, under a minute.** Compare E10, which spent 4 pre-flight
builds and 84 battery builds (~38 min) to confirm a prediction its own pre-registration had
already made. E11a is that lesson applied: the pre-flight *is* the experiment.

**E11b, only if E11a passes A1, A2 and item 6:** write the gene and `_session_support`,
write tests #1–#9 first, then run the two-arm battery — generation 15 control (gene off) and
generation 16 (gene on, both resonance genes off), `--tier frozen,probe`, 42 asks each,
**84 builds, ~36 min**. Verify P1/P5/P6 and the stage census against §7's table.

**Pre-registered now, before either step:**

> E11a will show that support **is** ask-dependent (A1 passes) and **does** separate `mouth`
> from `recall` (A2 passes), because provenance is exactly the axis resonance lacks.
>
> E11a will **also** show that no single floor separates `mouth` from the recall-gate failures
> without admitting them, because both classes are questions the session did teach material
> for — the difference between them is coverage, not comprehension.
>
> Therefore E11b, if run, will move `mouth` stage mass to `recall`/gate, will raise the
> speaking count from 27 to 31, and will leave frozen at 19/24, probes at 0/14 and guarded at
> 4/4. **Zero passes gained.**
>
> If that is what happens, the resonance line is closed and the terminal blocker for the
> `mouth` class is confirmed to be `ANSWER_COVERAGE_FLOOR`, whose thresholds are already
> measured and already known to be unmovable without losing the guarded scarf invariant.

If E11a falsifies the first clause, the design is wrong and nothing is built. If it
falsifies the second, the signal is *more* informative than expected and E11b's prediction
must be rewritten before running — not after.

---

## 9. Out of scope

Multi-brain and population work (standing constraint). Broad organ refactors. Passive
normalisation and the `which` interrogative (E5's R1″, recorded not implemented). §7b
value-weighted eviction — noted here only because a support signal that reads the binder
would be improved by an eviction policy that keeps session rows, and the current policy is
**blind FIFO**, which E3 observed evicting a `droso` row with count 4561. That interaction is
a reason to do §7b before relying on support in a long-lived learner, not a reason to widen
E11.
