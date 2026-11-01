# ELECTRIC C2 hazard arm — I claimed a pollution path. It does not exist.

```
.venv\Scripts\python.exe tools\electric_consolidate.py --arm teachon --facts 20 --seed 1
```

## 1. The claim I made, and what measuring it found

Last round I fixed a real bug (taught facts vanished when `ELECTRIC_TEACH` was switched off
before consolidation) and explained it with a mechanism:

> `consolidate()` replays up to 600 **corpus** sentences through `live(..., learn=True)` —
> the same entry point teach mode uses. With teach mode left on, every replayed library
> sentence becomes a fact *the user told*, and the organism wakes up believing the corpus
> spoke to it.

I wrote that into `save_state`'s comment and into `docs/electric_c2_consolidation.md`
**without testing it.** It is **false.** The hazard arm — teach 20 facts, leave
`ELECTRIC_TEACH` **on** through consolidation, save, restart, measure:

| | `cons` (flag off) | **`teachon` (flag on)** |
|---|---|---|
| correct | 20/20 | **20/20** |
| confabulated | 0 | **0** |
| refusal | 0 | 0 |
| silence | 0 | 0 |
| direct (`electric_taught`) | 18 | **18** |
| `_taught_says` during replay | 20 | **20** |
| `_absence_inv` | 20 → 20 | **20 → 20** |
| **polluted subjects** | 0 | **0** |

Byte-identical to the `cons` arm, including the SAN figures
(`1,457,958 → 1,450,258`) and the frame split (H1 2/2, H2 6/6, H3 12/12). Consolidation ran
fully: `rows_scanned 2000`, `rows_urgent 353`, `rows_replayed 200`, `passes 3` ⇒ 600
`live(learn=True)` calls, 52.3 s.

## 2. Why: the recording hook is not on the path consolidation takes

Three facts, each checked in the file rather than assumed:

- `_taught_says` has **exactly one write site**: `_absence_note` at `neural_language.py:4347`.
- `_absence_note` is called from **exactly one site**: `hear()` at `:4311`, guarded by
  `(ABSENCE_INVENTORY or ELECTRIC_TEACH) and str(speaker) == "you"`.
- `consolidate()` (`:720`) writes through `live()` with `speaker="parent"` / `"book"`
  (`:4087`, `:4213`). `hear()` is called at one site, `:4455`, **outside** `consolidate`.

So consolidation cannot reach the inventory at all — the flag's value during replay is
irrelevant to pollution. My error was reasoning from *"they share `live()`"* to *"they share
the teach hook"*, when the hook sits one level up in `hear()`. `live()` is the shared entry
point for **wiring**; `hear()` is the entry point for **being spoken to**.

## 3. No fix implemented, deliberately

The brief said: *if pollution occurs, implement the smallest flag-gated fix distinguishing
user-taught facts from replayed corpus text.* **Pollution did not occur, so no fix was
written.** The distinction the fix would have encoded **already exists structurally** —
`hear(speaker="you")` vs `live(speaker="parent"/"book")` — and adding a flag to re-state it
would be a second source of truth that could drift from the first.

What I did instead: **correct the false claim where it was recorded**, and pin the real
invariant as behaviour.

- `organs/neural_language.py` — `save_state` comment rewritten: the 0/20 (observed) is kept
  as the justification; the pollution story is marked FALSE with the call sites.
- `tools/electric_consolidate.py` — header corrected; `teachon` arm added; the off-switch in
  `cons` relabelled **defence in depth**, not a measured necessity.
- `docs/electric_c2_consolidation.md` §2 — correction inserted **in place**, leaving the
  original claim visible rather than editing history quietly. §6 updated: the item that said
  "hazard worth its own experiment" now points here.
- `tests/test_electric.py` — two new tests (now 24):
  `test_live_alone_never_mints_a_taught_fact` pushes corpus text through the exact entry
  point `consolidate()` uses with teach mode ON and asserts the inventory stays `{}`;
  `test_consolidation_with_teach_mode_on_does_not_pollute` runs `consolidate(budget=8)` with
  the flag on and asserts subject and relation counts are unchanged. Both assert
  **behaviour**, not source text — unlike the E24 pin that broke last round.

## 4. What this changes about last round's conclusion

**Nothing about the fix.** The one-line gate change stands on the **measured 0/20**: with the
old gate, switching teach mode off before saving wrote an empty inventory and lost every
taught fact. That was observed, and it is still the reason the permission flag must not
double as a memory flag.

What is withdrawn is the *stronger* claim — that leaving teach mode on is dangerous. It
isn't, for this reason: it can't record. Consequences worth naming:

- The `cons` arm's off-switch is now **cosmetic with respect to pollution**. It may still be
  right on other grounds (a learner that is not being taught should not hold write
  permission), but that is a design preference, not a measured protection.
- The "any learner that toggles teach mode per turn silently loses its memory" consequence
  from §2 of the previous doc **still holds and is unaffected** — that claim was about the
  save gate, which is the part I measured.

## 5. Not established

- **The invariant is now checked, but only by reading, not by running.** Recording requires
  `hear(speaker="you")`. The organ's only `hear()` call site is inside `respond()`
  (`:4404`, itself defaulted to `speaker="you"`), which is the conversational reply path and
  is not on any consolidation path. `live()`'s own default `speaker` is `None`
  (`:527`), and `str(None) != "you"`, so the speaker-less `live()` writers at `:912` and
  `:986` cannot record either. That closes the gap I expected to leave open — but I reached
  it by **grep, not by experiment**: no rehearsal, dream or `respond()` path was actually run
  under teach mode here, and a future caller that routes replayed text through `respond()`
  would mint facts with no test failing until these two new tests were extended.
- **Not that the invariant is enforced.** It is a consequence of how the call sites happen
  to be written. Nothing asserts "replay must not enter `hear()`"; the two new tests pin the
  current behaviour, which is the closest thing to a guard available without touching
  consolidation's core.
- **Not many cycles.** One `consolidate(budget=200)` call, not the live tool's
  loop-until-drained (up to 12).
- **Not a real `serve.py` shutdown/startup.** Both arms restart an organ object in one
  process against a scratch copy.
- **Not multi-relation, and not the `copper`/`bell` modifier-keying limitation** from last
  round, which this arm does not touch.

## 6. Suite

`tests/test_electric.py` is now **24 tests**. **Suite: 818 passed, 3 skipped, 5 warnings**
(was 816; +2 new tests; **zero erosion**). ELECTRIC stays **off** for battery runs, no
battery run was made here, and **the guarded grader contract was not touched.**
Evidence: `docs/evidence/electric_c2_teachon.json`.
