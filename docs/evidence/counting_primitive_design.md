# A counting primitive with temporal update semantics

**Design only. No core code changed.** No multi-brain work, no broad refactor.

E16a aborted at D2 with one defect that was not a parsing problem: a static relation index
answered `four` to `how many eggs are left in the basket?` where `two` is expected and `four` is
**explicitly forbidden**. The index had no temporal semantics — it did not know that a later tell
*updates* rather than *adds*. Half the recall-gate asks are quantity or frequency questions, so
the architecture review's pre-registered fork resolved toward a counting primitive.

The constraint that shapes everything below: **the organ already passes the `quantity-change`
class 4/4.** A primitive that regresses asks the baseline gets right is worse than no primitive.

---

## 1. How regression is avoided: by placement, not by testing

This is the load-bearing decision and it is structural.

> The counting primitive is consulted **only inside the existing
> `best_cov < ANSWER_COVERAGE_FLOOR` refusal branch** (`organs/neural_language.py:3476`), after
> the coverage gate has already declined.

The `quantity-change` asks pass **at the coverage gate**. They therefore never reach the branch
where the primitive lives. **They cannot regress, by construction** — not because a test asserts
it, but because control never arrives there.

This is the same minimal-blast-radius placement E15's design used, and it is the one property
that survived E15's abort: the mechanism can only ever **add** licences to asks that were
already refusing. It follows that:

- flag-off identity is trivial (the branch is not entered);
- the coverage floor, IDF weights, `stem()` and `reply_threshold` are untouched;
- the guarded scarf ask is protected twice — the coverage gate refuses it first, and §4 gives an
  independent reason to refuse.

Every prior negative is consistent with this placement. E12a failed because it changed the ratio
*inside* the gate, affecting passing asks. E15 failed because its licensing was consulted broadly
enough to reach asks that already passed. Placing a mechanism strictly downstream of a refusal is
the only arrangement seven experiments have not falsified.

## 2. How counts are stored: events, not state

**Store the events. Derive the state.** A stored state cannot distinguish "four, then two broke"
from "two", and that distinction is exactly what the battery asks about.

```
count_events: list of
  { entity:   normalised noun          # "egg"
    numeral:  int                      # 4, 2
    frame:    "absolute" | "event"     # which surface frame produced it
    verb:     normalised verb or None  # "be", "break"
    place:    normalised noun or None  # "basket"
    seq:      int                      # tell order within the session
    who:      "you"                    # provenance: told, never book
    raw:      str }                    # the tell, verbatim
```

Two frames, and only two:

| frame | surface | semantics |
|---|---|---|
| **absolute** | `there are four eggs in the basket` | *sets* the count for `(egg, basket)` |
| **event** | `two eggs broke` | *records* that 2 eggs underwent `break`; effect on state is **not assumed** |

`seq` is the tell order, which is what makes folding possible. `who` is the provenance filter
E11a validated and E15 confirmed is necessary: book rows must never contribute a count.

Nothing is written to the binder. This is an additive index beside it, in the established pattern
of `word_patterns`, `bigram_counts` and the SAN.

## 3. How later tells update rather than add

Folding is **explicit and ordered**, and — critically — **polarity is not guessed**.

```
state(entity, place) = fold over count_events sorted by seq:
    absolute  -> current = numeral                (a later absolute REPLACES)
    event     -> current = current ± numeral      (only if polarity is DETERMINATE)
                 otherwise mark the state INDETERMINATE and stop folding
```

Three rules, each answering a measured failure:

1. **A later absolute replaces an earlier one.** `there are four eggs` followed by `there are two
   eggs` yields 2, not 6. This is the update-not-add semantics E16a lacked.
2. **An event with determinate polarity adjusts.** Polarity is determinate only when the frame
   itself supplies direction — see §5, this is the design's one open risk.
3. **An event with indeterminate polarity makes the state INDETERMINATE, and an indeterminate
   state refuses.** It never defaults to the last absolute, never to zero, never to a guess.
   Silence is the output, per E8's condition: a confident wrong count scores zero *and* teaches
   confabulation, where silence scores zero and asserts nothing.

## 4. How quantity asks query the current count

Two query kinds, because the battery contains both and they are not the same question:

| query | example | answered from |
|---|---|---|
| **event count** | `how many eggs broke?` | the `event` whose verb matches — returns **2** directly, no folding |
| **state count** | `how many eggs are left in the basket?` | `fold(...)` — returns **2** only if polarity was determinate |

The event-count query needs **no polarity at all**: it asks how many underwent the event, and the
tell states it. That is the safer half and the one E17a tests first.

The state-count query needs the fold, and therefore needs polarity. Where polarity is
indeterminate the query **refuses** — which is the current behaviour, so refusing is not a
regression.

Licensing conditions, all required:

- at least one `count_events` row with `who == "you"` for the queried entity (provenance);
- the queried entity is the **head** noun, not a modifier (§6, defect 1 from E16a);
- for a state query, the fold terminated determinate;
- the filler is a numeral word, never a content noun.

## 5. The one open risk: polarity

Determining that `broke` decrements while `are` sets requires knowing something about verbs. A
hand-written verb lexicon is **exactly** what E16a's D4 and E10's Finding 1 forbid — E10
established that lexical knowledge introduced to fix one measurement tends to be wrong about the
binder's actual composition, and D4 aborted on the principle.

Three options, in order of preference:

1. **Avoid polarity entirely.** Answer only event-count queries, which need none. State queries
   refuse. This is strictly less capable and strictly safe, and it is what E17a measures first.
2. **Derive polarity from the frame, not the verb.** `there are N X` is absolute by surface form;
   `N X <verb>` is an event by surface form. Neither needs a verb class. State queries then remain
   indeterminate and refuse — which collapses into option 1.
3. **A closed directional class** (`left`, `broke`, `lost` vs `added`, `found`). This is a
   hand-written list and **trips D4**. It is recorded as the point where the design would have to
   concede, not as a solution.

**The design adopts option 1/2 and states the consequence plainly:** a counting primitive built
this way answers `how many eggs broke?` and **refuses** `how many eggs are left in the basket?`.
Since the organ already passes the state asks, refusing them costs nothing — and per §1 it never
reaches them anyway.

## 6. Head/modifier structure, carried forward from E16a defect 1

E16a licensed `what turns twice?` with filler `copper bell` where `bell` is expected and `copper`
is **forbidden**. A counting primitive has the same exposure: `two copper eggs` must index entity
`egg`, not `copper egg`.

The organ already solves this once, in E11a's `head` field — English noun phrases are head-final,
so the head is the **last** content token before the verb. The counting primitive must reuse that
rule rather than invent one. This is a dependency on E11a's landed work, not a new mechanism, and
E17a tests it explicitly.

## 7. E17a — the read-only probe

**Zero brain builds. No organ change. No gene.** Reads `tools/scripts_heldout.json` and
`tools/scripts_selection.json` only.

Implements the extractor, the fold and both query kinds as **standalone functions in the evidence
script**, then reports:

1. **H1 — event extraction is total.** Every tell containing a numeral yields exactly one
   `count_events` row, or is reported unextractable. No silent drops (E11a's loader bug, E16a's
   D5).
2. **H2 — the head rule.** Entity is the head noun, never a modifier. Tested on every tell with a
   two-token noun phrase.
3. **H3 — event-count queries.** For every `how many X <verb>?` ask, does the event query return
   the `expect.answer`? This is the half that needs no polarity, and the half E17a must pass.
4. **H4 — state queries refuse, never guess.** For every `how many X are left …?` ask, the probe
   must report **refusal**, not a number. A number here means polarity was assumed and option 1
   was violated.
5. **H5 — update-not-add.** Where a script tells two absolutes for the same entity, the fold
   yields the later, not the sum.
6. **H6 — the quantity-change asks the organ already passes are untouched.** Enumerate them from
   the generation-13 journal (`pass == True`) and confirm each is answered by the coverage gate,
   so §1's placement guarantee holds on the real battery rather than by argument.
7. **H7 — the guarded asks are not licensed.** D1 carried forward.

### Abort conditions

| # | condition | consequence |
|---|---|---|
| E1 | any guarded ask licensed | **abort** — the invariant that killed six repairs |
| E2 | any licence with a wrong or forbidden filler | **abort** — confabulation, E8/E15/E16a's mode |
| E3 | any state query returns a number instead of refusing | **abort** — polarity was assumed; option 1 violated |
| E4 | zero event-count asks answered correctly | **abort** — inert, the shape of E9/E13a |
| E5 | extraction needs a verb lexicon or an ask-fitted rule | **abort** — D4 |
| E6 | any quantity-change ask the organ passes would reach the primitive | **abort** — §1's placement guarantee is false and regression becomes possible |
| E7 | a tell with a numeral is unextractable and the affected asks are not reported | **abort** — silent partial coverage |

### Pre-registered expectation

H1, H2, H5, H6, H7 **pass**. H3 passes for the event-count asks — the numeral is stated in the
tell and needs no inference. **H4 passes by refusing**, which is the designed behaviour and the
point: the primitive is deliberately less capable than a full counting mechanism, because the
capability it would need requires a verb lexicon that D4 forbids.

**E4 is the real risk.** If the event-count asks are also already answered by the coverage gate,
then per §1 they never reach the primitive and it licenses **nothing** — inert, like E9's
`RECALL_UNFILTERED_FALLBACK` and E13a's tie-break. E17a must therefore report, for each
event-count ask, whether the coverage gate currently passes or refuses it. **The primitive can
only help on asks that currently fail**, and E16a's D3 found only 2 of 9 recall-gate asks were
even evaluable from the frozen file — so the probe must read the selection battery too, or it
will repeat that coverage gap.

If E4 fires, the honest conclusion is that the counting primitive is **safe and worthless**: it
cannot regress anything and cannot gain anything, which is the same verdict E14a reached for
candidate generation. That would leave the recall-gate class with no untested mechanism at all.

### If E17a passes

E17b is one gene `COUNT_EVENTS`, default off, an additive index written at teach time, consulted
only inside the `best_cov < floor` branch, answering **event-count** queries and refusing
everything else. Two-arm battery, generations 19/20, ~36 min, predictions recomputed from E17a's
actual licence list — not from this document.

**E17b requires a broader battery first**, per the architecture review: a primitive validated on
the asks that motivated it is fitted to them.

## 8. Out of scope

Multi-brain and population work (standing constraint). Broad refactors. A verb or polarity
lexicon. Removing or retuning `ANSWER_COVERAGE_FLOOR`, the IDF weights, `stem()`,
`reply_threshold`, or the echo/bigram/speakability constraints. The relational index from E16a —
its subject-binding result (D1 clear) is recorded as **validated and deferred**, to be revisited
only after head/modifier structure exists, since defect 1 makes it unable to name an answer
correctly. §7b value-weighted eviction — a dependency for any index that must survive beyond one
session, and the current policy is blind FIFO, which E3 observed evicting a `droso` row at count
4561.
