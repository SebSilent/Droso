# E17a result — ABORTED. The counting primitive is aimed at a class that is empty

**Verdict: `ABORT`. E2, E3 and E4 all fire. Zero brain builds, no organ change, no gene.**

`docs/evidence/e17a_counting_probe.py` → `e17a_result.json`, plus
`docs/evidence/e17a_followup.py`. Reads `scripts_heldout.json`, `scripts_selection.json` and the
generation-13 journal only.

The probe has defects of its own and §3 reports them plainly. **The verdict does not rest on
them.** It rests on §2, which is measured from the journal and is independent of the extractor.

---

## 1. Headline

The design was motivated by a fork in `architecture_decision_review.md`: *"if D3 fires, the
quantity asks need a counting primitive rather than a relational one."* E16a's D3 fired on a
coverage limitation — only 2 of 9 recall-gate asks were evaluable from the frozen file. E17a read
both batteries and the journal, and the fork resolves **against** the counting primitive.

**The class it targets is empty, and the one member it has is already answered.**

## 2. The decisive measurement: 11 quantity asks, 7 already pass

From `generation_13_asks.jsonl`, asks matching `^(how many|how often|what number)`:

| ask | gate | cause |
|---|---|---|
| `how many times did i tell you the coat is wet?` | **PASS** | — |
| `how many things did i tell you about the coat?` | **PASS** | — |
| `how many times did i tell you about the scarf?` | **PASS** | — |
| `how many objects did i tell you about?` | **PASS** | — |
| `how many eggs did i mention first?` | **PASS** | — |
| `how many eggs broke?` | **PASS** | — |
| `how many eggs are left in the basket?` | **PASS** | — |
| `how many times does the bell turn?` | fail | recall_gate |
| `how often did i say the coat is wet?` | fail | recall_gate |
| `how often does the bell turn?` | fail | recall_gate |
| `what number of eggs is left in the basket?` | fail | recall_gate |

**7 of 11 already pass.** Of the 9 recall-gate asks, 4 are quantity — but those 4 decompose into
**three different mechanisms, none of which is "count entities and fold updates"**:

1. **Frequency adverbials (2 asks).** `how many times does the bell turn?` and
   `how often does the bell turn?` want `twice`, from `the copper bell turns twice`. That is not a
   count of entities — it is an adverbial attached to a verb. `twice` is not even a cardinal; the
   probe's numeral table does not contain it, so the tell extracts as **"no numeral"** and is
   invisible to this primitive by construction. An `(entity, numeral)` event index cannot
   represent it.
2. **Rehearsal count (1 ask).** `how often did i say the coat is wet?` asks how many times the
   *user* said something. That is the binder's own `count` metadata, which already exists and
   which four passing asks already use. No new primitive is required.
3. **Paraphrase gap (1 ask).** `what number of eggs is left in the basket?` **fails** while
   `how many eggs are left in the basket?` — the same proposition — **passes**. The counting
   information is available to the organ; it cannot retrieve it under the reworded surface form.
   This is the paraphrase-robustness problem the whole battery was built to expose, not a
   counting problem.

And the single genuine **event-count** ask in the battery, `how many eggs broke?`, **already
passes at the coverage gate**. Per §1 of the design the primitive is consulted only inside the
`best_cov < floor` refusal branch — so it would never be reached. **E4 fires: zero real gain.**

This is the same verdict E14a reached for candidate generation: **safe and worthless**. Here it
is stronger — not merely no gain, but no target.

## 3. The probe's own defects, reported plainly

E2 and E3 fired, but partly for the wrong reasons. Four defects, all in the probe:

**(a) H2 was a tautological test and cannot fail.** It asserted
`e["entity"] == normalise(raw_ent[-1])` — which is exactly what `head()` computes. It validated
the implementation against itself. **This is the most important methodological finding here**: a
test that mirrors the code it checks reports PASS while the code is wrong. H2's "PASS" is void.

**(b) The head-final rule picks the wrong entity in both frames.**

```
'there are four eggs in the basket'  -> entity='basket'   (should be 'egg')
'then two eggs break'                -> entity='break', verb='egg'   (swapped)
```

E11a's head-final rule is correct for a noun phrase, but here the tokens after the numeral are
not a noun phrase: in the absolute frame the **place** noun follows the entity, and in the event
frame the **verb** follows it. Taking the last content token therefore selects the place or the
verb. The rule needs a frame-relative notion of head, not a positional one.

**(c) State-count queries are misrouted to event-count.** `left` is in the probe's stop list, so
`qverb` for `how many eggs are left in the basket?` resolves to `basket`, and the query takes the
event-count branch and refuses because no event has verb `basket`. **The state-count branch — and
therefore the polarity-refusal logic that is the design's central safety mechanism — never
executed.** H4's FAIL and E3 are real (a number was returned) but they came from the absolute-only
fold, not from assuming polarity.

**(d) The place filter silently drops events during folding.** `fold(ev, "egg", "basket")`
excludes the event row because its `place` is `None`, so the fold sees only the absolute and
reports `determinate=True`. The followup confirms it:

```
fold with CORRECT entity -> current=4 determinate=True
```

A silent drop inside the fold is the same failure class H1/E7 exists to catch — but H1 only
checks *extraction*, not *folding*. **The check was scoped too narrowly to catch its own risk.**

**Consequence: the design's polarity-refusal logic is untested, not refuted.** Whether "never
guess polarity" works cannot be said from this run. It does not matter for the verdict, because
§2 shows there is nothing for it to operate on.

## 4. Checks and abort conditions as run

| check | result | note |
|---|---|---|
| H1 extraction total | **PASS** | 4/4 numeral-bearing tells extracted, zero drops |
| H2 head rule | **VOID** | tautological test, see §3(a); the rule is in fact wrong, §3(b) |
| H3 event-count | **PASS vacuously** | 0/0 — no event-count ask reaches the branch |
| H4 state refuses | **FAIL** | returned `4` twice, where `two` is expected and `four` forbidden |
| H5 update-not-add | **UNTESTABLE** | no script tells two absolutes for one entity |
| H6 placement holds | **PASS** | the one gate-passing quantity ask cannot reach the branch |
| H7 guard not licensed | **PASS** | all 3 guarded asks refused |

| abort | state |
|---|---|
| **E1** guard licensed | clear |
| **E2** wrong/forbidden filler | **FIRES** — `4` on both eggs-left asks, `four` explicitly forbidden |
| **E3** state query returned a number | **FIRES** — but via §3(c)/(d), not via assumed polarity |
| **E4** zero real gain | **FIRES** — 0 licences on asks the gate refuses; robust to all probe defects |
| **E5** verb lexicon / ask-fitted rule | clear — closed grammatical classes only |
| **E6** passing ask reaches primitive | clear — placement guarantee holds |
| **E7** unextractable numeral tell | clear at extraction; **not checked at folding**, see §3(d) |

Only **4 tells in the entire 12-script battery contain a cardinal numeral**, and only one of them
(`then two eggs break`) is an event. The primitive's evidence base is a single row. H5 — the
update-not-add semantics that was the whole reason to prefer events over state — is **untestable
on this battery**. The design's central mechanism cannot be exercised by the instrument available.

## 5. Disposition — no E17b

**No flag-gated implementation is proposed.** E2, E3 and E4 fire, and E4 is robust to every probe
defect because it is measured against the journal rather than against the extractor.

Fixing the probe would not change the verdict. With a correct head rule, correct routing and no
silent fold drop, the primitive would still face: **no event-count ask that the gate refuses**
(`how many eggs broke?` passes), **no frequency-adverbial representation** (`twice` is not a
cardinal), **no need for rehearsal counting** (binder `count` already exists and four asks already
use it), and **one paraphrase gap** that is a retrieval problem, not a counting one.

### What this closes, and what it leaves open

**Eight accounts of the `mouth`/`recall` boundary are now closed** — resonance ranking,
comprehension signalling, coverage numerator, coverage threshold, coverage ranking, candidate
generation, provenanced entailment, and now counting. The consistent pattern holds: every
mechanism that makes the agent answer more often also makes it answer wrongly, and the guarded
invariant catches it each time.

But E17a adds something the previous seven did not: **the failing asks are not one class.** The 9
recall-gate asks decompose into frequency adverbials, rehearsal counts, paraphrase gaps,
irregular morphology, two-hop composition and unanswerable-by-design queries. Seven experiments
have each addressed one facet and been scored against all nine, which is why every one looked
like a near-miss. **The battery's aggregate failure count has been the wrong instrument since
E13a.**

The one mechanism E17a surfaced that is *not* closed and *is* measurable is **#3, the paraphrase
gap**: `how many eggs are left in the basket?` passes and `what number of eggs is left in the
basket?` fails, on identical taught evidence. That is a retrieval-robustness defect with a known
passing twin, which makes it falsifiable without a new primitive, a new lexicon, or any change to
the coverage formula. It is the narrowest open line and the only one where a correct answer is
already demonstrated to exist in the organ.

Cost: **zero brain builds**, seconds of runtime. No core changes, no multi-brain work, no broad
refactors.
