# Harness coverage diagnosis — the recall gate measured from inside the scored run

Generation 7, control genome `abffa2b7f101`, frozen + probe battery, 42 asks.
Journal: `state/selection/generation_7_asks.jsonl`. Classifier:
`docs/evidence/harness_coverage_classify.py`. Data:
`docs/evidence/harness_coverage_diagnosis.json`.

This is the measurement `coverage_gate_repair_design.md` §5b said had to happen
before any coverage value could be trusted: **read `coverage` from inside the
harness's own scored run, not from a probe reconstructing the context.** E6's P2
was falsified because a probe-measured 0.592 did not transfer. Every number below
comes from the run that grades the ask.

## 1. What was instrumented

Three fields, added to `_clean()`'s keep-list in `tools/converse.py` and to the
journal row in `tools/run_generation.py`:

| field | what it is |
|---|---|
| `coverage` | fraction of the cue's content words the best binder posting covers |
| `required` | the word list that posting demanded |
| `nearest` | the organ's own top-3 postings with scores |

Recorded for **every** ask, passing and failing, because the coverage of the asks
that *work* is the only in-harness evidence of where the gate actually sits. No
threshold changed. No answer-path code changed. `ANSWER_COVERAGE_FLOOR` is still
0.6 and the organ is byte-identical to before this.

The fields are populated only when the recall gate runs. On the answered path the
organ does not set them, and on `shape_arbiter`/`mouth`/`gating` refusals the ask
never reaches the gate — which is itself diagnostic, and is why those stages show
`cov=-` rather than `cov=0`.

## 2. Classification

19 failures, 23 passes.

| class | n | rule |
|---|---|---|
| **ABSENT** | **1** | `stage=recall`, `required` empty **and** `nearest` empty — the cue reached no posting at all |
| **UNREACHABLE** | **0** | `nearest` non-empty but `required` empty, or `coverage == 0` with postings present |
| **GATE** | **9** | `required` non-empty, `coverage` set, `best_cov < 0.6` |
| **DOWNSTREAM** | **9** | `shape_arbiter` 2, `gating` 3, `mouth` 4 |

> **Corrected by §8.** The ABSENT count of 1 is **retracted**: that ask never
> reached the recall gate, and `stage=recall` was the harness's default bucket, not
> a measurement. The true split is **GATE 9 / DOWNSTREAM 9 / comprehension
> (mislabelled recall) 1**, and ABSENT and UNREACHABLE are both **empty**. §3's
> empty-window result is unaffected — it never rested on that ask.

The four-way split asked for collapses to three populated classes. **UNREACHABLE
is empty**: there is no ask in this battery where memories exist and the cue found
neighbours but could not bind. Every recall failure either found nothing (1) or
found postings and scored them too low (9). That is a real result, not a gap in the
instrument — `nearest` has 3 entries on all nine GATE asks and 0 on the one ABSENT
ask, so the distinction is being made and nothing lands in the middle.

## 3. The headline: the window is not unmeasured, it is **empty**

```
coverage of PASSING asks        n=1    0.5700
coverage of failed recall asks  n=9    min 0.3400   max 0.5550
```

The single passing ask that carries a coverage sits at **0.570**. The *best* of
the nine gated failures sits at **0.555**. The guard is above every target.

A floor `F` admits an ask when `coverage >= F`. So:

- to admit the best failing ask: `F <= 0.555`
- to keep the 0.570 ask refusing (it **passes by refusing**): `F > 0.570`

`F <= 0.555` and `F > 0.570` cannot both hold. **No floor admits any failing ask
without first admitting the ask that passes by refusing.** The window
`(0.570, 0.592]` that `coverage_gate_repair_design.md` §3 built — and §5b withdrew
— does not merely fail to transfer. Measured from inside the harness it is empty,
and it is empty in the *hostile* direction: lowering the floor hits the guard
before it hits any target, because the guard's coverage is the highest number in
the whole battery.

This is why generation 2 lost the scarf guard at floor 0.566857, and why E6's
0.587206 bought nothing. Both are now explained by one ordering fact rather than
being two separate null results.

**C1 is answered definitively: no floor exists.** Not "none measured" — none
possible, on this battery, at this genome.

## 4. The probe was wrong, and by how much

| ask | probe (§4 of the prior doc) | harness | delta |
|---|---|---|---|
| `what did i tell you about before the kettle?` | 0.555 | **0.555** | 0 |
| `where did i say the scarf is?` | 0.570 | **0.570** | 0 |
| `what is bitten by the frost?` | 0.592 | **0.340** | **−0.252** |

Two of three transferred exactly. The third — the one E6 was built on — was off by
a quarter. At the harness's real 0.340, a floor of 0.587206 was never going to
admit it; the ask would have needed the floor lowered by 0.26, far past the guard.

So §5b's conclusion holds and is now sharpened. It said coverage is a property of
an ask *and* the binder state when it is asked. The harness shows the probe's
binder state for that ask was badly wrong, not subtly different — the probe
replayed the script's tells in a context that left the cue matching 59% of its
required words where the scored run matches 34%. The two asks that agreed are the
two whose scripts the probe happened to reconstruct faithfully. **There is no way
to know in advance which is which, which is exactly why probe-measured coverage
must not be used to predict a floor's effect.** The instrument is now inside the
harness, so this class of error is closed rather than merely flagged.

## 5. Per-class detail

### ABSENT (1) — `which thing turns twice?` — **RETRACTED, see §8**

> **This classification was wrong and is retracted.** It was inferred from
> `required=[]` and `nearest=[]` plus `stage=recall`, on the assumption that
> `stage=recall` meant the recall gate had run and refused. E7's instrumentation
> shows the gate **never ran**: the row's `reason` is *"it did not understand and
> was not in the mood to babble"*, and its raw binder count is `None`, not `0` —
> the `if not hits` return was never executed. `stage_of` in
> `tools/heldout_eval.py:141` returns `"recall"` as its **default** for any
> unspoken reply whose reason matches no pattern, and its own comment says this is
> "a DEFAULT, not a measurement". This is a **comprehension** failure wearing a
> recall label. See §8.

The original text claimed the cue shared `turns`/`twice` with the tell
*"the copper bell turns twice"* yet `required_words` returned nothing. Both halves
were wrong: `required_words` does not exist, and the cue never reached the code
that would have computed a required list.

### GATE (9) — coverages 0.340 … 0.555

All nine have `required` non-empty and `nearest` = 3. The memories are there and
the organ found neighbours; the overlap is simply below 0.6. Required lists are
dominated by function words the cue carries and the posting does not: `['bitten',
'by', 'frost', 'is']`, `['bell', 'does', 'many', 'times', 'turn']`, `['basket',
'eggs', 'in', 'is', 'left', 'number', 'of']`. The passive and quantifier
rewordings — `what is bitten by the frost?` at 0.340, `what number of eggs is left
in the basket?` at 0.538 — score worst, which is consistent: they are the forms
whose content words diverge most from the told sentence.

Per §3 these are not nine asks waiting for a threshold. They are nine asks whose
coverage is *below the guard's*, so no threshold reaches them.

### DOWNSTREAM (9)

- **mouth (4)** — the organ produced output and the mouth rendered noise:
  `bridle adding establish gargery`, `numbered`, `agin`, `sold`. Three of the four
  are `repeat after me` / `name the …` / `which of them …` forms. This is a
  rendering failure, not a memory failure, and no recall change can touch it.
- **gating (3)** — all three are the *same* proposition (`the door holds the
  frost`) in three framings: `does the door hold the frost?`, `is the frost held by
  the door?`, `is it true that the door holds the frost?`. The response gate holds
  all three. One underlying failure, three probe rewordings.
- **shape_arbiter (2)** — `what is wet but not on the hook?` (said *"the coat is on
  the hook"*, i.e. it answered the conjunction and dropped the negation) and `what
  does the thing the frost bites hold?`.

Counting distinct underlying propositions rather than probe rewordings, the 19
failures are roughly: 1 absent, 9 gated, 1 negation-dropping, 1 passive-frame, 4
mouth-rendering, 1 gated-proposition-in-3-forms. The battery's 14 probes are
rewordings of a smaller set of facts, so failure counts overstate distinct defects.

## 6. Proposed experiment — the smallest flag-gated change that could make an ABSENT memory recallable

**Target: the single ABSENT ask.**

> **Correction, recorded rather than quietly fixed.** This section originally
> proposed a fallback for "`informativeness.required_words` returning empty".
> **That mechanism does not exist.** `required_words` is nowhere in the codebase —
> it was named speculatively from the journal's `required` field without reading the
> gate. The real gate computes `must` at `organs/neural_language.py:3231`, and only
> ever reaches it under `if hits and content:` (line 3228). So an ABSENT ask is not
> one whose required list came back empty; it is one where **`binder.recall(content,
> k=40)` returned postings and three filters removed every one of them** — drop the
> question itself (3195), drop memories bearing an interrogative (3202), drop
> echo-subsequences of the question (3220). The originally proposed fallback would
> have been **inert**, guarded by a condition that could not fire, and would have
> "confirmed" P1 for the wrong reason. This is the same error class as E6's probe:
> reasoning from a field's *name* in a journal instead of the code that writes it.
> The instrument now in place is what caught it.

E7 as implemented targets the real mechanism:

```
RECALL_UNFILTERED_FALLBACK = False      # class attribute, default off, inert

# at the recall gate, after the three filters:
if not hits and raw_n and self.RECALL_UNFILTERED_FALLBACK:
    hits = self.cortex.binder.recall(content, k=40)
    hits = [h for h in hits
            if {str(t).lower() for t in h["tokens"]} != qset]
```

When every posting was filtered out, re-query the binder and keep only the
exact-question filter, handing the survivors to the coverage gate. This does **not**
bypass a safeguard: the gate still demands every distinctive word at IDF weight,
still refuses below the floor, and the shape arbiter still vetoes afterwards. What
changes is that the refusal becomes a **measured GATE with a coverage number**
instead of a silent ABSENT with none.

The ABSENT return also now carries `recall`, `after_question_filter`,
`after_interrogative_filter`, `after_echo_filter` and `fallback_applied`, recorded
unconditionally — they are pure recording, and they are what separates "no posting
exists" from "postings existed and a filter removed them all, and here is which".

Why this is the smallest thing that could work:

- **It cannot change any currently-scored ask.** The fallback is guarded by
  `if not required`, so every ask with a non-empty required list — all 9 GATE, all
  23 passes, the guard — takes exactly the path it takes today. Inertness is
  structural, not empirical, which is the property E5's R1/R1'/R2 had and E6's
  floor mutation did not.
- **It is one flag and one branch**, in the gate's own call site. No threshold
  moves. No parse changes. No core connectome or decision code is touched.
- **It is falsifiable in one generation.** Prediction: with the flag on,
  `which thing turns twice?` moves from `required=[]`/`nearest=[]` to a non-empty
  required list and a `nearest` with entries — i.e. it leaves ABSENT. Whether it
  then *passes* is a separate question and is **not** predicted, because per §3 its
  coverage would have to exceed 0.6 to pass and nothing here raises coverage.

**Pre-registered predictions, to be written before the run:**

Restated for the real mechanism. **P1 is qualified**: the ABSENT return now carries
five new diagnostic keys, so the journal is *not* byte-identical to generation 7 by
construction. Inertness is therefore about **verdicts**, not bytes.

- **P1** With the flag **off** (generation 8), all 42 asks have the **same `pass`,
  `stage` and `coverage`** as generation 7, ask for ask, and the same 23/19 split
  and the same `MEMBERSHIP` 19/19. The new keys may appear; no verdict may move.
- **P2** With the flag **on** (generation 9), `which thing turns twice?` records a
  non-empty `required` and a non-empty `nearest`, i.e. it **leaves the ABSENT
  class**. Its `fallback_applied` is `true`. If `recall` (raw binder hits) was 0,
  the fallback cannot fire and the ask stays ABSENT — which would itself be the
  finding that no posting exists at all, and would close the class rather than
  repair it.
- **P3** With the flag **on**, no other ask changes class, coverage, stage or
  verdict. Specifically the 0.570 passing ask and all nine GATE coverages are
  unchanged, because their `hits` was never empty and the branch is guarded by
  `not hits`.
- **P4** The flag **on** does not by itself raise the frozen or probe score. If it
  does, P3 is wrong and the fallback is firing somewhere it should not.
- **P5** Zero erosion: frozen stays 19/24 and guarded stays 4/4 in both arms.

**What success would mean.** P2 without a score change is still a real result: it
would show that an absent memory can be made *addressable* — the cue reaches a
posting — and that the remaining obstacle is coverage, not reach. That converts one
ABSENT failure into one GATE failure, and GATE failures are the class with a known
(bad) prognosis rather than an unknown one. It would also be the first repair in
this series to move a failure between classes rather than leaving all 42 identical.

**What is deliberately not proposed.** Lowering the floor (§3 forecloses it).
Informativeness-weighted coverage (changes what coverage means for all 42 asks, so
it cannot be flag-gated into inertness, and it is a larger design). Anything for
UNREACHABLE, which is empty on this battery and would be speculation. Anything for
the 4 mouth failures, which are a rendering defect in a different organ and deserve
their own diagnosis rather than being folded into a recall experiment.

**Cost.** One generation, 2 lines × 42 asks ≈ 36 minutes, no new state.

## 7. What was not changed

- `ANSWER_COVERAGE_FLOOR` is still **0.6**. No threshold moved.
- No answer-path code changed. The two edits are a keep-list in `tools/converse.py`
  and three keys in a journal dict in `tools/run_generation.py` — both record what
  the organ already computed.
- No core connectome or decision code touched. No multi-brain work. No refactor.
- Generation 7 ran the **control genome only** (`--lines 1`, no mutation), so there
  is no mutant to cull and no lineage decision. `MEMBERSHIP: 19 asks passed in
  every line, 19 in at least one` — identical to generations 0, 1, 2, 3, 6.
- The state guard again reported the known two populations (the harness's own
  `selection/generation_7*` artifacts plus the hardlinked `live_learner`
  `banc_brain.npz` copies). Pinned by test; still not sha256-verified.

## 8. E7 result — the fallback is inert here, and the ABSENT class was a harness artifact

Two arms, control genome `abffa2b7f101`, frozen+probe, 42 asks each. Generation 8
flag **off**, generation 9 flag **on** (`--recall-fallback`, recorded in
`provenance.code_flags`). Tests: `tests/test_e7_recall_fallback.py`.

| | gen 7 (baseline) | gen 8 (flag off) | gen 9 (flag on) |
|---|---|---|---|
| frozen | 19/24 | **19/24** | **19/24** |
| probes | 0/14 | **0/14** | **0/14** |
| guarded | 4/4 | **4/4** | **4/4** |
| stages | `recall 10, mouth 4, gating 3, shape_arbiter 2` | **identical** | **identical** |
| MEMBERSHIP | 19 / 19 | **19 / 19** | **19 / 19** |

| prediction | verdict |
|---|---|
| **P1** flag off reproduces gen 7's verdicts ask for ask | **CONFIRMED** — all 42 `(pass, stage, coverage)` triples identical |
| **P2** flag on moves `which thing turns twice?` out of ABSENT | **FALSIFIED** |
| **P3** flag on changes no other ask | **CONFIRMED** — trivially; nothing changed at all |
| **P4** flag on does not raise the score | **CONFIRMED** — 19/24, 0/14 both arms |
| **P5** zero erosion | **CONFIRMED** — frozen 19/24, guarded 4/4 both arms |

### Why P2 failed, which is the actual result

`fallback fired on any ask: 0` and `rows with a raw recall count: 0`. The fallback
is guarded by `not hits` — by the recall gate having run and found nothing. **No
ask in this battery reaches that branch.** The nine gated asks all had postings and
scored them; the tenth never reached the gate. E7 has no target here, and its
inertness is total rather than partial.

Inspecting every `stage=recall` row's `reason` separates them cleanly:

```
9 x "the closest memory of his covers NN% of the question"   <- real gate refusals
1 x "it did not understand and was not in the mood to babble" <- NOT a recall failure
```

The nine coverages are 34, 39, 42, 45, 46, 51, 51, 54, 55 percent — exactly the
nine GATE values in §2. The tenth is a **comprehension** failure. `stage_of`
(`tools/heldout_eval.py:141`) returns `"recall"` as its default for any unspoken
reply whose reason matches no pattern, and the comment above that line says
outright it is "a DEFAULT, not a measurement". *"not in the mood to babble"*
matches neither `RECALL_RE` (`cover|no memor|nothing he rememb|…`) nor `GATING_RE`
(`did not feel like speaking|not feel like|…`), so it fell through.

**Consequences.**

1. The ABSENT class in §2 is **empty**, not 1. The four-way split is really
   GATE 9 / DOWNSTREAM 9 / comprehension-mislabelled-as-recall 1.
2. The stage tally `{"recall": 10, …}` quoted across generations 0–9 has always
   contained one non-recall failure. Real recall-gate failures are **9**.
3. §3's empty-window result is **unaffected and slightly strengthened**: it rests
   on the nine GATE coverages (max 0.555) against the 0.570 passing ask, and the
   retracted ask was never one of them.
4. E5's R1′ determiner repair was aimed at this ask. It reparsed correctly and the
   ask still failed — now explicable: the failure is downstream of parsing, in
   comprehension, so no parse repair could have reached it. That is a third
   independent confirmation that the shape parser is not the binding constraint.

### What E7 leaves behind that is worth keeping

The fallback itself is **inert on this battery and stays default-off**. It is not
proposed for promotion: it has no measured effect, and a flag with no effect is
not a repair. What is kept is the **instrumentation** — `recall`,
`after_question_filter`, `after_interrogative_filter`, `after_echo_filter`,
`fallback_applied` on the `not hits` return, recorded unconditionally. They cost
nothing, they are pure recording, and they are what turned a confidently wrong
classification into a corrected one. Without them the ABSENT ask would still be
recorded as a memory problem, and the next cut would again be aimed at recall.

### The next cut this points at, and the one it forecloses

It **forecloses** further recall-side work on this battery: nine gated failures
whose coverages all sit below the guard's, one comprehension failure that is not a
recall problem, and no unreachable memories at all.

It **points at** the stage labelling itself. A default bucket named `recall` has
mis-attributed one failure for ten generations and made a comprehension defect
look like a memory defect. The smallest useful change is not a new repair but a
new label: give `stage_of` a `comprehension` branch for reasons matching
`did not understand`, and let `recall` stop being the fall-through. That is a
harness change with no effect on the organ, it is testable against the existing
journals for generations 0–9, and it would make every future stage tally mean what
it says. It is **not implemented here** — it changes the meaning of a field that
ten generations of rows already carry, so it needs its own pre-registration and a
decision about whether to relabel historical rows or version the field.
