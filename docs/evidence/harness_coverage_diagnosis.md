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

### ABSENT (1) — `which thing turns twice?`

`required=[]`, `nearest=[]`. The tell was *"the copper bell turns twice"*; the cue
shares `turns` and `twice` with it, yet `informativeness.required_words` returned
nothing, so the gate never scored and there was nothing to refuse. This is the ask
E5's R1' determiner repair was built for, and R1' correctly reparsed it — then it
died here, one stage later, for a reason no parse fix can reach. **This is the only
failure in the battery that is not a threshold, a veto, or a rendering problem.**
It is a cue-to-posting addressing failure.

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

**Target: the single ABSENT ask. Mechanism: `required_words` returning empty.**

The gate refuses to score when it has no required words. That is correct behaviour
for a cue with no content — but `which thing turns twice?` *has* content (`turns`,
`twice`); the filter dropped it. So the smallest possible intervention is a
fallback that only fires when the filter returns nothing:

```
RECALL_EMPTY_REQUIRED_FALLBACK = False      # default off, inert

# in the recall gate, where required_words() is called:
required = informativeness.required_words(utterance)
if not required and RECALL_EMPTY_REQUIRED_FALLBACK:
    required = [w for w in tokens(utterance)
                if w.isalpha() and len(w) >= 2
                and w not in INTERROGATIVES and w not in STOPWORDS]
```

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

- **P1** With the flag **off**, all 42 asks are byte-identical to generation 7.
  This is the inertness check and it must hold exactly, ask for ask.
- **P2** With the flag **on**, `which thing turns twice?` records a non-empty
  `required` and a non-empty `nearest`. It leaves the ABSENT class.
- **P3** With the flag **on**, no other ask changes class, coverage, stage, or
  verdict. Specifically the 0.570 passing ask and all nine GATE coverages are
  unchanged, because their `required` was never empty.
- **P4** The flag **on** does not by itself raise the frozen or probe score. If it
  does, P3 is wrong and the fallback is firing somewhere it should not.

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
