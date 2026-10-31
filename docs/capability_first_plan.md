# Capability-first plan: answering simple taught questions reliably

**Status: proposed. Replaces the closure-style diagnostic line (E11a–E26).**
**Trigger:** E25 (`v_synt`) and E26 (`v_frame`) each produced exactly **one** new correct answer —
and it was the *same* answer. E26 additionally cleared four `recall` failures, but three of them
died at the next gate instead of becoming answers. The coverage lever is exhausted.

---

## 1. What the measurements actually say

Across 26 generations and ~25 experiments, the frozen score has not moved from **19/24** and the
paraphrase tier moved **0/14 → 1/14** exactly once. Every intervention that changed anything changed
*which gate an ask dies at*, not *how many asks are answered*.

Stage mass, control → `v_synt` → `v_frame`:

| stage | gen 21 | gen 22 | gen 23 |
|---|---|---|---|
| `recall` | 10 | 8 | **6** |
| `shape_arbiter` | 2 | 3 | **5** |
| `mouth` | 4 | 4 | 4 |
| `gating` | 3 | 3 | 3 |

**Recall is being drained into the shape arbiter.** That is not progress; it is the failure moving
downstream. The system is increasingly able to *find* the taught row and increasingly unable to
*say* it.

## 2. The structural diagnosis

A taught fact must survive **four independent learned gates in series** before it becomes an answer:

1. **coverage** — does the retrieved row overlap the question enough? (`ANSWER_COVERAGE_FLOOR = 0.6`)
2. **shape arbiter** — does the parsed question shape match a licensed answer form?
3. **mouth / resonance** — does a candidate word win the resonance competition above
   `reply_threshold = 0.55`?
4. **gating / mood** — does the organ "feel like speaking"?

Series composition is the problem. If each gate passes a taught fact with probability *p*, the answer
rate is *p⁴*. The measurements are consistent with this: E10 found the resonance winner at **0.4129
against a 0.55 threshold** on an ask whose fact was correctly retrieved. The fact was *known* and the
system still said nothing.

**Every experiment so far has tuned one gate.** E23–E26 tuned coverage. E9/E10 tuned resonance scope.
E12a tuned the `must` set. E16a tuned relation indexing. None touched the fact that a correct
retrieval has to win four separate competitions to become speech.

This is why the guarded set passes 4/4 while paraphrase passes 1/14: the guarded asks are
*structurally identical to the taught sentence*, so they sail through the shape arbiter and the
resonance pool contains the exact taught words. Change the wording and the same fact fails three of
four gates.

## 3. The required change

> **When a taught row is retrieved with high confidence and the question asks for a value the row
> explicitly carries, emit that value directly — bypassing the shape arbiter and the resonance
> competition.**

This is not a shim. It is the difference between *associative recall* and *interrogative lookup*.
The system already has the row; it currently throws the row's content into a general-purpose
resonance pool and hopes the right word wins. A taught fact queried by a taught relation should be
answered from the fact.

Concretely, three learned organ changes:

**(a) A value slot on the taught row.** Rows already carry subject/relation/object structure (E16a
built a relation index). The change is to make the *queried value* addressable: given
`(scarf, place, ...)`, a question whose relation matches `place` returns the stored value without
resonance.

**(b) Relation matching replaces shape arbitration for taught relations.** The shape arbiter stays
for novel syntax. But when the question's relation is one the system was *taught*, the licensed
answer form is the taught one. This is learned, not hardcoded: the relation vocabulary grows from
teaching episodes.

**(c) The mood gate does not apply to a direct lookup.** "It understood but did not feel like
speaking" (3 `gating` failures) is a defensible behaviour for *spontaneous* speech. It is not
defensible for a direct question the system has the answer to. A retrieved-and-matched fact should
set the reply drive, not be filtered by it.

## 4. Minimal prototype

**Flag-gated, default off, one organ, no multi-brain work, no refactor.**

```
DIRECT_ANSWER_LOOKUP = False        # the whole prototype behind one flag
```

Scope, deliberately minimal:

- **Input:** the retrieved binder row(s) already produced by the existing recall path, plus the
  parsed question.
- **New code:** one pure function `_direct_value(row, relation, object_slot)` returning the stored
  value or `None`, and one call site that, when the flag is on and the function returns non-`None`,
  emits that value as the answer and skips the shape arbiter and resonance.
- **Not touched:** retrieval, the coverage gate, the binder, eviction, consolidation, the resonance
  machinery itself (it still runs for every ask the direct path does not claim), the mouth, teaching.
- **Claim discipline:** the direct path only fires when the relation is one the system was taught for
  that subject. Anything else falls through to the existing path unchanged. This is what keeps it
  from being a shim — it cannot answer a question it was not taught.

**Why this is the minimal thing that could work:** it removes *two* of the four series gates for the
class of asks that already retrieve correctly, which E19 established is **40 of 42 asks**
(`taught_resident` True). The facts are there. The series composition is what loses them.

## 5. Predicted outcome, pre-registered

Measured against generation 23 (`v_frame`) as control, treatment in generation 24:

| metric | prediction |
|---|---|
| frozen | 19/24 → **21–23/24** |
| paraphrase probes | 1/14 → **4–7/14** |
| guarded | 4/4 → **4/4** (must not move) |
| `recall` stage mass | 6 → **≤3** |
| `shape_arbiter` mass | 5 → **≤2** (asks claimed by the direct path never reach it) |
| `gating` mass | 3 → **≤1** |

**This is the first prediction in the series that forecasts movement in `frozen`.** E25's corrected
pre-registration explicitly could not, because coverage provably did not bind any frozen ask. The
direct path can, because the frozen failures at `shape_arbiter` and `gating` are exactly the gates it
bypasses.

**Abort conditions:**
- **C1** guarded falls below 4/4 → abort. The scarf must still refuse; a direct lookup on an absent
  value must return `None`, not a guess.
- **C2** any ask the control answered starts refusing → abort.
- **C3** frozen falls below 19/24 → abort.
- **C4** the direct path fires on an ask whose relation was never taught → abort. This is the
  shim-detection condition and it is load-bearing: the project has already recorded one prior
  selection attempt that scored a veto override as capability gain, and one synthetic proxy that
  overfitted a closed modifier class. A lookup that answers untaught questions is the same failure.
- **C5** `frozen` rises but the new passes are all in one script family → treat as overfit, not gain.

## 6. Tests, written first

1. `_direct_value` is pure: no `self`, no binder access, signature asserted.
2. Returns the taught value for a taught `(subject, relation)`.
3. Returns `None` for an untaught relation — **C4**.
4. Returns `None` for a taught subject with an absent value (the scarf case) — **C1**.
5. Flag default off; with the flag off the answer path is byte-identical (assert on source and on a
   recorded control journal).
6. The direct path skips the shape arbiter: assert the arbiter is not entered when the path claims.
7. The direct path does not skip retrieval: assert it consumes the existing recall result and adds no
   new binder query.
8. The mood gate is not applied to a claimed answer — **C3/gating**.
9. Integration: generation 24 vs 23, arms differ in exactly one flag, abort conditions C1–C5 read
   from the published fitness block (not re-derived — E25 §5 records two abort checks that silently
   measured nothing).

## 7. What this plan deliberately does not do

- **No multi-brain work.** Single organ, single flag.
- **No broad refactor.** The resonance machinery, the shape arbiter and the coverage gate all stay
  and keep handling every ask the direct path does not claim.
- **No new gate.** The series gets shorter for one class of ask; it does not get a fifth stage.
- **No `v_all`.** E27 (`v_all`, 5 of 9 offline) is now deprioritised below this. It is another
  coverage lever, and §1 shows coverage is draining into the shape arbiter rather than producing
  answers. Running it would be more closure-style diagnostics.
- **No change to the `cause_all` taxonomy.** Still deferred, for the comparability reason recorded in
  E24.

## 8. Honest statement of risk

The risk is that this is a shim wearing a capability costume. The defence is C4 plus the claim
discipline in §4: the path fires only on a relation the system was *taught*, for a subject it was
*taught*, with a value that is *present*. If it answers anything else, C4 aborts the experiment.

The counter-risk is that it is too narrow — that it fixes the 42-ask battery and nothing else. That
is testable and should be tested: the plan's success criterion is not the battery score but whether
**a newly taught fact, taught in one episode and asked in different words, gets answered.** E1
measured that at **2/20 generalisation**. If the direct path moves E1-style generalisation, it is
real. If it only moves the frozen battery, it is overfit and C5 should catch it.

**Recommendation:** implement §4 behind `DIRECT_ANSWER_LOOKUP`, tests first per §6, run generation 24
against generation 23, and re-run one teaching episode (E1 protocol, 20 facts) to measure
generalisation rather than battery score.
