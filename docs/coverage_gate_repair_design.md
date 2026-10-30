# The coverage gate: what the failing asks actually die of, and the smallest repair

Status: measurement complete, repair pre-registered, **not yet run**.
Evidence: `docs/evidence/coverage_gate_diagnosis.py` →
`docs/evidence/coverage_gate_diagnosis.json` (20 asks, 10 builds).
Depends on: `docs/evidence/coverage_exact.py` (part 1, the scarf/kettle thresholds),
`docs/answer_path_repair_design.md` §3c (E5's null result),
`docs/selection_design.md` §8 (the floor is bracketed and closed).

---

## 1. Why this document exists

E5 found that R1, R1′ and R2 — three correct shape-parser repairs, 22 tests pinning
exactly what they do — are **inert on the battery**. Both arms returned identical
results on all 42 asks, every pass, every failure, every stage. The targeted asks
still failed at `recall`, which is upstream of the shape arbiter, so the parser was
computing a shape nobody consulted.

That left a hypothesis and no measurement: the failures die at the coverage/recall
gate, not in the parser. `selection_design.md` §8 had already *bracketed* the floor
as a lever and closed it, on the grounds that no value separates the kettle target
(0.555) from the scarf guard (0.570). But bracketing a lever is not the same as
knowing how many asks it gates, and §8 measured **two** asks. This document measures
the whole failing set.

## 2. The measurement

`coverage_gate_diagnosis.py` walks each script's turns **in order**, telling each
`say` and asking each planned `ask` at its own position, so the binder holds exactly
the tells that preceded it. It then reads the organ's raw reply dict — not
`converse._clean()`'s keep-list, which strips `coverage`, `required` and `nearest`,
and which is why the generation-0 journal only ever had a whole-percent reason
string.

Two methodological points that cost runs and are recorded so they are not repeated:

- **The first version replayed every tell before every ask.** That silently puts
  later tells into the binder and changes coverage for all of them. The fix is the
  in-order walk. The corrected run agrees with part 1 exactly on the one ask they
  share — kettle = **0.555** — which is the cross-check that says the walk is right.
- **`spoken` is not a harness pass.** The class is named `SPOKE`, not `PASS`, because
  the organ producing an answer says nothing about whether the content matched the
  `expect` block. Four of the five `SPOKE` rows are harness failures. Naming that
  class `PASS` would have made this probe look like it contradicted the recorded
  floor when it does not.

A contrast ask (`what turns twice?`) is not a turn in the script it was asked
against, so it can only be asked after *all* that script's tells. It reads
cov=0.586, below the floor, yet passes in the frozen battery — because there it
belongs to a different script with different tells. That row is labelled
`after-all-tells` in the JSON and **is not evidence about the passing form**. The
guarded tier contributed 0 rows: `regression_pass_set` holds `sel-*` keys that live
in the selection battery, and the plan only looked for them in the heldout one. The
scarf guard's 0.570 therefore comes from part 1, not from this run.

### Result: 19 harness failures, four causes

| class | n | what it means | repairable by a gate change? |
|---|---|---|---|
| **GATE** | **9** | memories exist and were scored, `best_cov < 0.6`, recall refused | **yes — this is the only class a gate repair can touch** |
| **SPOKE** | 5 | the organ answered; the content did not match `expect` | no — an answer-quality problem, downstream of the gate |
| **ABSENT** | 4 | `required` empty: `informative()` dropped every content word, no binder postings | no — there is nothing to recall |
| **VETO** | 1 | the shape arbiter rejected the best candidate | no — and E5 already showed shape repairs are inert here |

The coverage gate is the **single largest cause of failure: 9 of 19**. It is not the
only one, and the honest reading is that a gate repair addresses under half the
failures and cannot touch the other three classes at all.

The `ABSENT` class is worth naming precisely, because it is the class that no amount
of threshold tuning will ever fix: `which thing turns twice?`,
`name the wet thing that is not on the hook`, `is the frost held by the door?`,
`does the door hold the frost?`. For these, `informative()` finds no binder posting
for any content word. The memory is not below threshold — **it is not there in a
form the cue can reach**. That is a binding/indexing question, and it is the real
reason E5's shape repairs were inert on `which thing turns twice?`: the shape was
never the problem, and neither is the floor.

### The nine GATE coverages, against the floor of 0.6

```
0.385  what does the bitten thing hold?            generalisation
0.417  how many times does the bell turn?          frozen
0.454  how often did i say the coat is wet?        generalisation
0.460  what came before the kettle in what i said? generalisation
0.510  what is held by the thing the frost bites?  generalisation
0.514  how often does the bell turn?               generalisation
0.538  what number of eggs is left in the basket?  generalisation
0.555  what did i tell you about before the kettle? frozen
0.592  what is bitten by the frost?                generalisation
```

## 3. What the numbers say about lowering the floor

Part 1 established the constraint that makes this interesting: the guarded ask
`where did i say the scarf is?` **passes by refusing** at cov = 0.570. Any floor
≤ 0.570 admits it, the organ answers instead of refusing, and a guarded pass is
lost. Generation 2 confirmed this empirically — the one lowering draw, 0.566857,
lost the scarf ask at `shape_arbiter`.

But 0.592 sits **above** 0.570. So there is a window that §8 never examined, because
§8 only had two asks in it:

```
floor in (0.570, 0.592]  ->  admits exactly ONE ask: `what is bitten by the frost?`
                             keeps scarf refusing (0.570 < floor)
                             keeps kettle refusing (0.555 < floor)
```

This is a **one-ask window**. It is real, it is measured, and it is narrow enough
that it should be stated plainly as what it is: not a repair that fixes
generalisation, but a single point on a trade-off curve where one ask can be bought
without paying the guard. Eight of the nine GATE failures need a floor below 0.555,
and every floor below 0.570 costs the guarded scarf pass. **The lever cannot fix the
class; it can only buy one member of it.**

That is the central finding of this document, and it is a negative one. The coverage
gate is the largest single cause of failure and is **not usefully repairable by
threshold**, because the failures it causes are spread from 0.385 to 0.592 while the
guard sits at 0.570 in the middle of them.

## 4. Proposed changes, smallest first, all flag-gated

### C1 — measure the window (no code change)

Run the floor at 0.587206 and confirm the prediction in §5. This is a measurement,
not a repair: it tests whether the organ, once past the gate, produces content the
harness accepts. Coverage says the gate opens; **only the run says whether the
answer is right.**

### C2 — `ANSWER_COVERAGE_FLOOR_WINDOW` (default off, no live effect)

A single flag-gated constant recording the measured window `(0.570, 0.592]` and the
one ask it buys, so the number survives in the tree rather than in a document. This
is documentation with a test attached, not a behaviour change, and it is the only
change C1 justifies if C1's answer is wrong.

### C3 — what is *not* proposed, and why

- **Lowering the floor as a gene.** Bracketed and closed by §8, re-confirmed here:
  8 of 9 GATE failures need < 0.555, which costs the guard.
- **A per-ask or per-script floor.** That is fitting the eval set. `fly_v2.py`
  already did this once — a synthetic proxy overfitted a closed modifier class — and
  the whole point of the frozen/guarded split is to make that visible.
- **Weighting coverage by word informativeness** (so that `thing`, which appears in
  no memory, does not drag coverage down the way a rare content word does). This is
  the most promising real repair and it is **deliberately out of scope**: it changes
  what coverage *means*, it cannot be flag-gated into inertness the way a constant
  can, and it needs its own design and its own pre-registration. It is recorded here
  as the next question, not bundled into this one.
- **Fixing `ABSENT`.** Four failures, and the largest single class after GATE. Also
  out of scope, for the same reason: it is a binding/indexing change, not a gate
  change, and E5 is a fresh warning about repairing the stage you can see.

## 5. E6, pre-registered before it is run

**Arms.** Two lines, one generation, `--mutants 1 --mut-seed 7`. Line 1 is the control
clone carrying parent genome `abffa2b7f101`. Line 2 is the single mutant,
`ANSWER_COVERAGE_FLOOR` 0.6 → **0.587206** (draw −0.0128, sigma 0.05, inside bounds
[0.45, 0.75], not clipped). Seed 7 was chosen by enumerating seeds 1–399 through the
real `mutate()` and taking the first whose draw lands in the window; 54 of 399 do.
The seed is recorded so the draw is reproducible and was not cherry-picked after
seeing a result.

**Battery.** `--tier frozen,probe` — 42 asks, the same battery E5 used, so E6 is
directly comparable with both E5 arms.

**Predictions, written before the run.**

- **P1 — the guard holds.** Frozen 19/24, guarded 4/4. Scarf (0.570) and kettle
  (0.555) both stay below 0.587206, so both keep refusing. *Falsified if any frozen
  or guarded ask changes verdict.*
- **P2 — exactly one ask leaves the recall refusal.**
  `what is bitten by the frost?` (0.592 ≥ 0.587206) stops failing at `recall`. Its
  stage must change. *Falsified if it still fails at `recall`.*
- **P3 — no other ask moves.** The other eight GATE coverages are all ≤ 0.555, so
  all stay refused. *Falsified if any other ask changes verdict or stage.*
- **P4 — the harness verdict on that one ask is NOT predicted.** Coverage says the
  gate opens; it does not say the answer is right. This ask is a passive form, and
  E5 showed the passive shape repair (R2) is inert, so the content may well be wrong
  and the ask may still fail — at a *later* stage, which would itself be the
  informative result. **A pass here is a gain of one ask and nothing more; a fail at
  a later stage reclassifies it from GATE to SPOKE and is equally worth having.**

**Selection rule.** Unchanged from `selection_design.md`: a survivor must lose zero
frozen passes and zero guarded probes. P1 is that rule restated as a prediction. If
the mutant loses any frozen or guarded ask, the outcome is `no_gain` and the parent
stands, regardless of P2–P4.

**Stall rule.** Unchanged: do not lower sigma, widen the whitelist, add lines or
soften the rule to get a survivor. If E6 yields `no_gain`, the floor lever is closed
a third time and the honest conclusion is that generalisation is limited by
`ABSENT` and by answer quality, not by the gate — and the next work is C3's
informativeness weighting or the binding question, neither of which is in scope here.

**Cost.** 2 lines × 42 asks ≈ 36 minutes wall clock, dominated by builds.

**Not run with `--isolate`, deliberately.** `--isolate` exists because the genes in
`ANSWER_MODULE_GENES` and `SUBSTRATE_GENES` are read as *module globals* inside the
organ's methods, so setting one is process-wide and moves every brain in the
interpreter. `ANSWER_COVERAGE_FLOOR` is in `ANSWER_INSTANCE_GENES` — it is applied
per instance and restored after each brain — so isolation buys nothing here. More
to the point, E5's two arms and generations 0–5 all ran on the in-process path, and
that path has reproduced the recorded 19/24 floor exactly four separate times.
Changing the execution path in the same breath as changing the gene would make E6
incomparable with the arms it is meant to be read against.

## 5b. E6, run — P2 falsified, and the reason matters more than the result

```
g6-1  abffa2b7f101  parent, unmutated                   19/24  0/14  4/4  key=[1,19,4]
g6-2  ebe00da7aabc  ANSWER_COVERAGE_FLOOR=0.587206       19/24  0/14  4/4  key=[1,19,4]
OUTCOME  no_gain -> survivor g6-1 (abffa2b7f101)
lost=[]  guard_lost=[]  recall+0
noise: none. Every genome's lines agree ask for ask.
```

| prediction | verdict |
|---|---|
| **P1** guard holds, frozen 19/24, guarded 4/4 | **held** |
| **P2** `what is bitten by the frost?` leaves the `recall` refusal | **FALSIFIED** — still fails at `recall` |
| **P3** no other ask moves | **held** |
| **P4** harness verdict on that ask not predicted | moot |

The two arms are identical on all 42 asks. The mutant bought nothing and cost
nothing, and the parent stands.

### Why P2 failed, and what it invalidates

P2 was arithmetic: the probe measured that ask at cov = 0.592, the floor was set to
0.587206, and 0.592 ≥ 0.587206, so the gate should have opened. It did not. Three
explanations are possible and the evidence separates them:

1. **The gene does not reach the organ.** *Ruled out.* Generation 2's mutant at
   floor 0.566857 **lost** the guarded scarf ask — the floor demonstrably changes
   behaviour, and it changed it in exactly the direction part 1 predicted.
2. **Part 1's thresholds are wrong.** *Ruled out, and this is the useful part.* Part
   1 measured scarf at 0.570; generation 2 lowered the floor to 0.566857, just below
   it, and the scarf ask was admitted and the guarded pass was lost. **Part 1's
   number transferred to the harness precisely.** The method — `build()` + `Session`
   + replay `turns[:idx]` + read the raw reply — is sound.
3. **This probe's 0.592 does not describe the harness's context for that ask.**
   *This is what is left, and it is the finding.*

So the same method produced a number that transferred (scarf, 0.570, confirmed by a
generation-2 loss) and a number that did not (0.592, contradicted by a generation-6
null). The difference is not the method. It is that **coverage is not a property of
an ask** — it is a property of an ask *and* the binder state at the moment it is
asked, and this probe's binder state for that ask was not the harness's.

What that invalidates is narrower and sharper than "the probe is wrong":

- The **class** assignment survives. `GATE` was inferred from the organ's own
  `reason` string containing a coverage refusal plus a non-empty `required`, and
  that is a fact about the reply, not about a threshold. Nine of nineteen failures
  really did die on a coverage refusal.
- The **values** do not survive as predictions. §3's window `(0.570, 0.592]` was
  built from one transferred number and one untransferred number, and the window is
  therefore **not established**. It should not be cited.
- Consequently **C1 is answered and C2 is withdrawn**. There is no measured window to
  record in the tree, and writing `ANSWER_COVERAGE_FLOOR_WINDOW` as a constant would
  have enshrined a number that a run just contradicted.

What would settle it: instrument the harness's own ask path and read `coverage`
from inside the scored run, rather than reconstructing the context in a separate
probe. That is a small change to `run_generation.py`'s ask journal — it already
records `reason` and `stage`, and `coverage` is the one field `_clean()` strips.
Until that is done, **no coverage value measured outside the harness should be used
to predict a floor's effect.** Generation 2's scarf result is the only transferred
threshold this project has, and it is a *guard* threshold, not a target.

### The lever is closed a third time

`selection_design.md` §8 bracketed the floor and closed it. Generation 2 confirmed
the bracket from above and below. E6 was the one measured window that seemed to
escape the bracket, and it does not exist. The honest conclusion is the one §8
already reached, now with a mechanism attached: **the coverage floor is not a lever
on generalisation**, and the nine `GATE` failures are not nine asks waiting for a
threshold. The remaining candidates are the two classes this document could not
touch at all — `ABSENT` (4 failures, where the cue reaches no binder posting and no
threshold is relevant) and `SPOKE` (5 failures, where the organ answers and the
content is wrong). Both are downstream work with their own designs, and neither is
a gene.

## 6. Change log

- Measurement run: 20 asks, 10 builds, tally `{GATE:10, SPOKE:5, ABSENT:4, VETO:1}`
  (the 10th GATE row is the invalid `after-all-tells` contrast). Live state verified
  untouched by `guard_check`, with the known `live_learner/*/banc_brain.npz` hardlink
  false alarm firing identically to E5 — which is now the second read-only context it
  has appeared in, and strengthens the case that it is an artifact of the hardlinked
  checkpoint layout rather than of any change under test. It is still not verified by
  sha256 here.
- E6 pre-registered, seed 7, floor 0.587206, predictions P1–P4.
- E6 run: generation 6, `--mutants 1 --mut-seed 7`, control `abffa2b7f101` and mutant
  `ebe00da7aabc` (`ANSWER_COVERAGE_FLOOR` 0.6 → 0.587206). Both 19/24 frozen, 0/14
  generalisation, 4/4 guarded, `key=[1,19,4]`, `lost=[]`, `guard_lost=[]`, `recall+0`.
  Outcome `no_gain`, parent stands. P1 and P3 held, **P2 falsified**. Artifacts
  `state/selection/generation_6.jsonl` and `generation_6_asks.jsonl`.
- §5b written: the window `(0.570, 0.592]` is **withdrawn**, C2 is withdrawn, and the
  reason is recorded — coverage is a property of an ask *and* the binder state when it
  is asked, so a value measured outside the harness does not transfer. Part 1's scarf
  threshold did transfer (generation 2 lost the guard exactly where part 1 predicted),
  which is what makes the contrast informative rather than merely negative.
- The state guard reported 7 live files moved, the same `live_learner/*/banc_brain.npz`
  hardlink set as E5 and the read-only diagnosis probe. It has now fired identically in
  three contexts, one of which wrote nothing at all. That is strong evidence it is an
  artifact of the hardlinked checkpoint layout, but it is still unverified by sha256 and
  it still makes `run_generation.py` exit 1, which is what silently skipped E5's arm B.
- **Two wasted launches, recorded so they are not repeated.** (a) The probe's first
  version imported `config.settings`, which does not exist in this project; the
  pattern is `from tools.converse import Session, build, guard_check, guard_live_files`.
  (b) E6 was first launched as `--lines 2 --mut-seed 7`, which produced **two clones**
  and no mutant, because `--lines` and `--mutants` are separate flags and `--mutants`
  defaults to 0. `--lines N` means N clones of the base with no mutation and is
  mutually exclusive with `--mutants`; `--mutants N` means 1 control clone plus N
  mutants. The run was stopped at the header, before any ask was scored, so nothing
  was published and no partial generation_6 artifact had to be cleaned up. The
  correct invocation is `--mutants 1 --mut-seed 7`, and the header now confirms
  `0.6 -> 0.587206 (draw -0.0128, sigma 0.05)` on genome `ebe00da7aabc` against
  control `abffa2b7f101` — which is the check that should always be read before
  letting a generation run for 36 minutes.
