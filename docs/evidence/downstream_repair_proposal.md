# The downstream failure census, and the smallest next repair

Measured from `state/selection/generation_9_asks.jsonl` (control genome
`abffa2b7f101`, frozen+probe, 42 asks). Cross-checked against generations 7 and 8,
which are identical. Nothing here is a hypothesis about counts; every number below
is a row in a published journal.

Of the 19 failures, 10 carry `stage=recall` and 9 are **downstream** of recall —
the organ retrieved something, or understood and declined, and the failure is in
what happened next. Generation 10's `cause` field splits the 10 into 9 real
coverage-gate refusals and 1 comprehension failure, so the honest census is:

| class | asks | distinct defects | frozen | probes |
|---|---|---|---|---|
| `recall_gate` — coverage below floor | 9 | 1 (the threshold) | 5 | 4 |
| `mouth` — babble instead of content | 4 | 1 | 0 | 4 |
| `gating` — understood, declined to speak | 3 | **1** | **1** | **2** |
| `shape_arbiter` — vetoed or wrong shape | 2 | 2 | 2 | 0 |
| `comprehension` — never parsed the question | 1 | 1 | 0 | 1 |

## The largest downstream class is `mouth`, and it is worth zero frozen asks

All four `mouth` failures have `source: "meaning resonance"` (one `"meaning
resonance + chain"`) and emit **babble** — single unrelated words where content was
wanted:

| ask | wanted | said |
|---|---|---|
| `name the wet thing that is not on the hook` | `scarf` | `agin` |
| `which of them is wet and is not on the hook?` | `scarf` | `numbered` |
| `repeat after me the copper bell turns twice` | `copper bell turns twice` | `sold` |
| `which thing did i mention earlier than the kettle?` | `lantern` | `bridle adding establish gargery` |

This is one defect, not four: when the answer path cannot assemble content it falls
through to a meaning-resonance word sampler instead of failing loudly. The outputs
are not near-misses — `sold` for an echo request, `agin` for a scarf — so the
sampler is not retrieving the right material and mis-rendering it. It is retrieving
nothing and speaking anyway.

It is the largest downstream class and it is **entirely probes**. Fixing all four
moves the paraphrase probe score from 0/14 to at most 4/14 and the frozen score not at all.
That is still worth doing — 0/14 on unseen paraphrases is the generalisation arm of
the fitness tuple and it has never moved — but it is not where a frozen pass is
recoverable.

## The best ratio is `gating`: three asks, one defect, and the only frozen pass available

All three `gating` failures are **the same proposition in three framings**, and all
three want the answer `no`:

| tier | ask | reason |
|---|---|---|
| frozen | `does the door hold the frost?` | `it understood but did not feel like speaking` |
| probe | `is it true that the door holds the frost?` | same |
| probe | `is the frost held by the door?` | same |

The script is `hop-and-inventory`. The tell establishes what the door holds; the
frost is **not** among it. So the correct answer is `no`, the organ correctly found
no supporting proposition, and then the reply gate declined to speak at all.
`stage_of` files this under `gating` because `GATING_RE` matches — and unlike the
`recall` default bucket, that label is **correct**: he understood and chose silence.

This is mechanism **C** from the E5 analysis ("polar can't answer *no*"), and E5
never tested it because E5's three repairs were all aimed at the shape parser and
were all inert. It is the only class where one repair moves the **frozen** score,
and it moves the probe score twice over from the same change.

Ranking by frozen passes recoverable per distinct defect:

1. **`gating`** — 1 defect → **+1 frozen, +2 probes** (19/24 → 20/24, 0/14 → 2/14)
2. `shape_arbiter` — 2 defects → +2 frozen, but one defect each, and they are
   unrelated (`forbidden word said: coat` vs `nothing he remembers has that shape`)
3. `mouth` — 1 defect → +0 frozen, +4 paraphrase probes
4. `recall_gate` — **not repairable by threshold**. Generation 7 measured the window
   as empty: the nine failing coverages top out at 0.555 and the guarded scarf ask
   passes at 0.570, so any floor that admits them admits the guard's. Nine asks,
   zero available moves.
5. `comprehension` — 1 defect, 1 probe, and no parse repair reaches it (E5's R1′
   reparsed this ask correctly and it still failed)

## Proposed experiment E8: `POLAR_ABSENCE_MEANS_NO`

**The smallest flag-gated repair.** One class attribute on `NeuralLanguage`, default
`False`, beside `ANSWER_COVERAGE_FLOOR` and `RECALL_UNFILTERED_FALLBACK`, so an A/B
arm can set it without touching the module for every other instance in the process.

**Mechanism.** When a question is **polar** — the shape parser already produces a
polar verdict, and the three asks above all begin with `does`/`is` — and the answer
path is about to decline with a reply-gate refusal, and recall found **no**
proposition supporting the asserted relation, emit a negative answer instead of
silence. The gate is not weakened for any other case: a non-polar question still
declines, a polar question with a supporting proposition still answers from it, and
a polar question whose retrieval is merely weak still goes through the coverage gate
and still refuses below the floor.

This is deliberately narrow. It converts **absence of evidence into "no"** for
closed yes/no questions only, which is the one place that inference is sound: the
inventory is complete because he was told it, so "not in the inventory" is a fact
about the world rather than a failure of memory.

**What it must not do.** It must not become a general "answer no when unsure". A
polar question about something never mentioned at all would then get a confident
`no`, which is a hallucination with better grammar. The guard is that the negative
is licensed by an **inventory the organ actually holds**, not by a null retrieval.
If the implementation cannot tell those apart, the experiment should be abandoned
rather than shipped — that is a pre-registered abort condition, not a tuning
problem.

### Arms

Two arms on control genome `abffa2b7f101`, `--tier frozen,probe`, 42 asks each,
differing **only** in the flag, recorded in `provenance.code_flags` (as with E7,
since two arms of an A/B carry the same genome and the flag is the only thing
distinguishing them). Arm A flag off, arm B flag on.

### Predictions, to be registered before the run

- **P1** — arm A reproduces generation 9 ask for ask: 19/24 frozen, 0/14 paraphrase
  probes, 4/4 guarded, stages `{"recall": 10, "mouth": 4, "gating": 3, "shape_arbiter": 2}`.
- **P2** — arm B moves **all three** `gating` asks to pass, because they are one
  proposition and one defect. Fewer than three means the framings are not
  equivalent to the parser and the repair is shape-dependent.
- **P3** — arm B scores **20/24 frozen and 2/14 paraphrase probes**. This would be the first
  movement in the frozen score in ten generations.
- **P4** — arm B loses **zero** guarded passes and **zero** frozen passes. The
  selection rule is unchanged: a survivor must lose nothing, otherwise the parent
  stands and the stall is recorded.
- **P5** — arm B changes **no** ask outside the three. In particular the nine
  `recall_gate` coverages must be unchanged, since the flag sits downstream of the
  gate and cannot affect what the gate scored.

### Falsification

- P2 giving 1 or 2 of 3 ⇒ the polar detection is framing-sensitive. Report which
  framing survives and why; do not widen the detector to force 3.
- P4 failing ⇒ the negative answer is being licensed by null retrieval rather than
  by a held inventory. **Abort**, per the condition above. This is the most likely
  failure mode and the most important one to catch, because a confident `no` is
  worse than silence: silence scores zero and asserts nothing, while a wrong `no`
  scores zero and teaches him to confabulate.
- P3 not reached despite P2 ⇒ the asks pass the organ but not the grader, which
  would mean `wanted: ['no']` is not what a negative answer produces. That is a
  harness question and should be checked before any organ change.

### Cost

Two arms × 42 asks ≈ 36 min at the measured 26 s/ask, plus the implementation. No
new mutation, no new genome, no change to the frozen or guarded batteries.

## Not proposed

- **Lowering `ANSWER_COVERAGE_FLOOR`.** The window is empty and generation 2 already
  measured the cost: a lowering draw lost a guarded invariant. Nine asks are
  unreachable this way.
- **Further shape-parser work.** Three independent confirmations that it is not the
  binding constraint: E5's arm B was identical to arm A on all 42 asks, R1′ reparsed
  the comprehension ask correctly and it still failed, and the two `shape_arbiter`
  failures are a forbidden-word rendering and a missing shape, not a parse.
- **A `mouth` repair, yet.** It is the largest downstream class and the right
  second target, but it is worth zero frozen passes and the babble sampler needs its
  own diagnosis first — specifically, whether `meaning resonance` is a deliberate
  fallback or an unguarded one. Proposing a repair before measuring that would
  repeat the E7 error of naming a mechanism from a field's name instead of its code.
- **Multi-brain work or any broad refactor.** Out of scope by instruction.
