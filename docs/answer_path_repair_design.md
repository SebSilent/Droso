# Answer-path repair: question-form robustness (rung 2)

Written before any code. Contract for the E5/E6 series; changes need a dated entry in
the change log at the bottom.

Rung 2 of the capability ladder (`docs/open_learning_design.md` §4) is the weakest
measured rung and the only one that four episodes of open learning did not move:
**4/18** on the standing paraphrase tier, and across three teaching episodes
**question-word swap 0/9** and **passive 0/17**, while reverse-role was **12/12**. The
episodes proved the memory is there — a taught fact is queryable from either end — and
that the surface form is what fails. So this is an answer-path problem, not a learning
problem, and teaching more will not fix it.

Scope: classify the failures by mechanism, propose the smallest flag-gated changes,
test them, and run one pre-registered experiment. **No multi-brain work, no broad
refactors.** One cut at a time, because a result from two changes at once is not
attributable to either.

## 1. The classification, measured not inferred

`docs/evidence/answer_path_probe.py` builds one sealed house and puts every failing
form through the real `is_interrogative` and `_question_shape`, beside the forms that
pass. Line numbers are from the current file (4,627 lines); the ones quoted in older
documents are stale by 100–900 lines.

Learned sets, live: `interrogatives`, `question_roles` and `answer_types` are all
**`['how', 'what', 'where', 'who']`** — four entries, and **`which` is not among
them**. `statement_words` 4,000.

The shape parser's own gate is a **closed literal tuple** at
`organs/neural_language.py:2108`:

```python
inter = next((w for w in q if w in ("who", "what", "where")), None)
```

Three words. `which`, `how`, `when`, `why` produce `inter is None` and the function
returns `None` at 2109-2110 — it abstains. Note that `how` *is* a learned
interrogative and still gets no shape, because this tuple and the learned set are two
different things and only the learned one was ever taught.

Measured shape per form:

| form | `_question_shape` | outcome |
|---|---|---|
| `what turns twice?` | `subject_unknown` | **passes** |
| `what does the frost bite?` | `object_unknown` | **passes** |
| `which thing turns twice?` | **None** | fails, recall |
| `which of them is wet and is not on the hook?` | **None** | fails, mouth |
| `which thing did i mention earlier than the kettle?` | **None** | fails, mouth |
| `what is bitten by the frost?` | **None** | fails, recall |
| `what is held by the thing the frost bites?` | **None** | fails, recall |
| `is the frost held by the door?` | **None** | fails, gating |
| `how many times does the bell turn?` | **None** | fails, recall |
| `how often does the bell turn?` | **None** | fails, recall |
| `does the door hold the frost?` | **None** | fails, gating |
| `name the wet thing that is not on the hook` | **None** | fails, mouth |
| `repeat after me the copper bell turns twice` | **None** | fails, mouth |
| `what number of eggs is left in the basket?` | `subject_unknown` | fails, recall |
| `what did i tell you about before the kettle?` | `object_unknown` | fails, recall |
| `the bell turns how often?` | **None** | **passes** |

And the passive, directly: `what is bitten by the frost` → `None`, `what is held by the
door` → `None`, `what does the frost bite` → `{"kind": "object_unknown", "subject":
["frost"], "verb": "bite", "tail": []}`. **There is no passive handling anywhere in the
file**; `_question_shape`'s own docstring at 2099-2105 says passive answers are vetoed
and left as future work, and `by` sits in `SHAPE_FUNCTION_WORDS` (1956) so it is
stripped as a function word rather than recognised as an agent marker.

### The five mechanisms

**A — question word outside the literal tuple.** `which` and `how` never produce a
shape, so the arbiter has nothing to arbitrate and the question falls through to
resonance, which refuses. Five standing paraphrase failures and the whole 0/9
question-word frame. *Cause: one tuple at 2108.*

**B — passive voice has no parse.** `what is <verb> by <agent>` reaches the
who/what-plus-copula branch and returns `None` at 2133-2134, the same branch that
correctly abstains on `what is the box`. *Cause: a missing branch, not a wrong one.*

**C — polar questions cannot be answered "no".** `does the door hold the frost?` and
`is the frost held by the door?` get no shape, and only `_record_answer` is allowed to
utter "no" (its own docstring says an affirmative carries information a silence does
not, and a refusal is not a negative answer). *Cause: no polar path exists.*

**D — imperatives are not questions.** `name the wet thing…` and `repeat after me …`
produce no shape; the echo path requires a literal (`say exactly`). *Cause: a closed
literal in the echo detector.*

**E — the shape parses and the coverage floor refuses anyway.** `what did i tell you
about before the kettle?` gets `object_unknown` and still fails at recall on coverage
**0.555**; `what number of eggs is left in the basket?` gets `subject_unknown` and
fails the same way. **This class is not a shape problem and no shape repair will touch
it** — and `docs/selection_design.md` §8 measured that the floor is not a usable lever:
the band that would admit 0.555 also admits the 0.570 pass-by-refusal that guards
`where did i say the scarf is?`, so no floor value separates them.

Two forms break the correlation and are the reason this is measured rather than read off
the source: `the bell turns how often?` gets **no shape and passes** (a dedicated path
claims it), and the two class-E forms get a shape and fail. A shape is necessary for the
arbiter to help and not sufficient for an answer.

## 2. What must not be broken, and the two hazards found before writing code

**The dedicated paths are dispatched in `respond()` before `answer()` is reached.** That
is the structural fact that makes a shape repair safe: the arbiter only ever sees
questions the ordinal, glossary, disjunction, record, quantity and count paths already
declined. Three *passing* frozen asks contain `which` — `which did i tell you first…`,
`which did i tell you last…` (ordinal) and `which word did i use for the metal?`
(glossary) — and a widened shape parser cannot reach them, because a dedicated path
answered first and `answer()` never ran.

Two hazards are recorded because both were found by reading rather than by breaking
something:

1. **Widening 2108 is not a pure addition.** A question that currently abstains gets no
   shape and so is never vetoed; give it a shape and it becomes eligible for the
   arbiter's veto. For the forms in class A that is harmless — they already fail — but
   it means the change can convert a `recall` failure into a `shape_arbiter` failure,
   which is a *stage* change with no score change. Any comparison must therefore be
   per-ask on `(pass, stage)` and not on the score alone.
2. **Widening the learned `interrogatives` set is a different and larger change.**
   `answer()` blacklists memories containing any interrogative (3133-3135), so teaching
   the organ that `which` is a question word would also start suppressing every stored
   proposition containing `which`. **This repair does not touch the learned set.** Class
   A is fixed in the shape parser only, which is a closed literal in one place and has no
   effect on retrieval blacklists.

## 3. The proposed changes, smallest first, each behind its own flag

Three repairs, ordered by size and by how much of the measured failure they address. Each
is a module-level constant defaulting to the current behaviour, so the live animal is
byte-identical until something passes the new value — the `SAN_WEIGHT_CAP` precedent
(`neural_language.py:48-53`: named, default unchanged, "naming it is not re-tuning it").

**R1 — class A, the question-word tuple.** One constant and one expression:

```python
SHAPE_EXTRA_INTERROGATIVES = ()          # R1, default off
SHAPE_INTERROGATIVES = ("who", "what", "where") + SHAPE_EXTRA_INTERROGATIVES
```

with 2108 reading `SHAPE_INTERROGATIVES`. Setting the constant to `("which",)` makes
`which thing turns twice?` parse as `subject_unknown` exactly as `what turns twice?`
does. It adds no branch, changes no guard, and cannot affect a question a dedicated path
already claimed. `how` is deliberately **not** included: `how many …` and `how often …`
are quantity and count questions whose dedicated paths key on their own cue sets, and
giving them a shape would put them in front of the arbiter without giving them a filler
to arbitrate.

**R2 — class B, a passive branch.** A new branch in `_question_shape`, before the
copula-abstain at 2133, matching `<wh> is <verb> by <agent>` and returning
`object_unknown` with `subject=[agent]` and `verb=<verb>` — reusing the existing shape
kind and the existing `_shape_matches` guards rather than inventing a fourth kind, so the
arbiter, the provenance vote and the mouth all work unchanged. Gated on the copula being
present and `by` being followed by content, so `what is the box` still abstains exactly as
it does today. This is the larger change and it is **not** in E5.

**R3 — classes C and D: not proposed.** A polar path that can utter "no" is a new
capability with a new failure mode (confabulated negation), and the echo literal is one
string in one detector. Both are recorded as future work rather than bundled, because
bundling them would make E5's result unattributable.

## 3b. R1′ and R2 — the addendum written after P2 was falsified

R1 gave `which` a shape and the shape came out wrong, because `subject_unknown` takes the
first non-function word after the interrogative as the verb and `which thing` is a
two-word question phrase. The repair must not be a list of nouns to skip — that is the
`fly_v2` closed-class failure. So the rule has to be syntactic.

### R1′ — determiner interrogatives take a noun-phrase head

The distinction is real and it is not about `thing`. **`what`, `who` and `where` are
pronouns**: they stand in for the missing constituent, so the next content word *is* the
verb. **`which` is a determiner**: it modifies a noun, so a head noun follows it and the
verb comes after that. That is why `what turns twice` parses and `which thing turns twice`
does not, and it predicts the failure for every `which <noun> …` form rather than for one
word.

```python
SHAPE_DETERMINER_INTERROGATIVES = ()      # R1', default off; ("which",) when on
```

Rule, applied only when the interrogative is in that set: **if three or more content words
follow the interrogative, the first is the NP head and is skipped**; otherwise nothing is
skipped. The threshold is what keeps both forms correct and it is a structural condition,
not a vocabulary:

| form | content words after `which` | skip? | verb | tail |
|---|---|---|---|---|
| `which thing turns twice` | thing, turns, twice (3) | yes | **turns** | twice |
| `which turns twice` | turns, twice (2) | no | **turns** | twice |

The known cost, stated rather than hidden: `which thing turns` — a head noun, a verb and
no tail — has two content words, so it is not skipped and still parses `thing` as the verb.
That form is ungrammatical as a question in the batteries and in ordinary use (a
`subject_unknown` question needs something after the verb to be about), so R1′ does not
chase it. If it ever appears, the fix is to let the arbiter try both parses and keep the
one a memory satisfies, which is a larger change and is recorded here as R1″ rather than
bundled in.

### R2 — a passive branch, reusing `object_unknown`

`what is <verb> by <agent>` currently reaches the who/what-plus-copula abstain at
2133-2134, the same branch that correctly refuses `what is the box`. R2 adds a branch
**before** that abstain, gated on two structural conditions: a copula immediately after the
interrogative, and a `by` later in the question with at least one content word after it.
Both hold for `what is bitten by the frost` and neither holds for `what is the box`, so the
abstain that prevents confabulation is preserved exactly.

The branch returns the **existing** `object_unknown` kind with `subject` = the content words
after `by` and `verb` = the first content word after the copula. No fourth shape kind, so
`_shape_matches`, `_arbitrate_shape`, `_provenance_vote` and the mouth all work unchanged —
which is the difference between a repair and a refactor. `by` stays in
`SHAPE_FUNCTION_WORDS`; the branch reads it positionally before the function-word filter
strips it.

Gated behind its own flag, separately from R1′, so a result is attributable to one cut.

### What is still not proposed

R3 (polar questions that can answer "no", and imperatives) stays out. A polar path is a new
capability with a new failure mode — confabulated negation — and bundling it would make E5
unattributable. Class E is untouched by any of this and remains closed by
`docs/selection_design.md` §8.

## 3c. E5 REVISED — run, and the result is that all three repairs are inert

E5 as originally specified was not run, because P2 was falsified by a test (§4). It was
re-run against R1+R1′+R2 as two arms differing **only** in code flags — both carry genome
`abffa2b7f101`, so `provenance.code_flags` is the only thing distinguishing them, which is
why that field exists.

- **arm A** `generation 4`, flags off — the control
- **arm B** `generation 5`, `--shape-extra which --shape-determiner which --shape-passive`

| | frozen | generalisation | guarded | failure stages |
|---|---|---|---|---|
| arm A (control) | 19/24 | 0/14 | 4/4 | `{recall:10, mouth:4, gating:3, shape_arbiter:2}` |
| arm B (repaired) | 19/24 | 0/14 | 4/4 | `{recall:10, mouth:4, gating:3, shape_arbiter:2}` |

**Identical on all 42 asks — every pass, every failure, every stage.** Zero erosion, and
zero gain. Arm A also reproduces the generation-0/3 floor exactly, so the instrument is
stable and the null result is not drift.

### The finding: the shape parser is not the binding constraint

Hazard 1 predicted R1 would convert `recall` failures into `shape_arbiter` failures. **It
did not, and that is the result.** The three asks the repairs were aimed at:

```
probe 36  which thing turns twice?                   recall -> recall   (R1' target)
probe 37  what is held by the thing the frost bites? recall -> recall   (R2 target)
probe 41  what is bitten by the frost?               recall -> recall   (R2 target)
```

All three still fail at **`recall`**, which is *upstream* of the arbiter. A question that
dies at recall never reaches `_arbitrate_shape`, so no change to `_question_shape` can
affect it — the parser is computing a shape nobody consults.

The decisive pair is inside the frozen tier, and it was in front of me in generation 0
without being understood:

```
frozen 16  what turns twice?         PASS
probe  36  which thing turns twice?  fail at recall
```

With R1′ on, `_question_shape` returns the **same** shape for both — `subject_unknown`,
`verb="turns"`, `tail=["twice"]` — pinned by
`test_r1p_skips_the_np_head_after_a_determiner_interrogative`. Same shape, same memories,
one passes and one fails at recall. **So the difference between them is not the shape.**

The remaining difference is the question's own words. `what` is stripped as an
interrogative; `which` and `thing` are not, and `thing` appears in no stored proposition.
That points at the coverage/recall gate rather than the parser — the same mechanism as
class E, which §3 already noted is untouched by any shape repair. **This is a hypothesis
from the stage evidence, not a measurement**: the generation-0 journal rows carry no
coverage field (`_tmp/reach_preflight.py`), so confirming it needs the unrounded coverages
that `docs/evidence/coverage_exact.py` knows how to get. It is recorded as the next
question, not as a conclusion.

### What this changes

Class A collapses into class E. The five-mechanism classification was right about the
*parses* and wrong about the *cause*: `which`/passive forms genuinely get no shape, but
that was never why they fail. R1, R1′ and R2 are correct parser improvements — 22 tests pin
exactly what they do — and they are **inert on this battery**, because the questions die
before the arbiter. They stay in the tree, flag-gated and default-off, costing nothing.

The pre-registered discipline paid for itself twice: P2 was falsified by a 0.1 s test
before 84 builds, and the revised E5 falsified the whole class-A theory with a null result
that is unambiguous *because* both arms carry the same genome and the control reproduces
the recorded floor. A scalar fitness would have reported `0.0` for both arms and hidden
this entirely.

## 4. E5, pre-registered before it is run

**E5 measures R1 and nothing else.** R2 stays off. Two arms, one line each, both against
the **live** state (not a learner checkpoint — the guarded baseline describes the live
animal, and comparing against it is the point):

```bash
py -3.10 tools/run_generation.py --generation 4 --lines 1                      # flag off
py -3.10 tools/run_generation.py --generation 5 --lines 1 --shape-extra which    # flag on
py -3.10 docs/evidence/compare_arms.py 4 5
```

Battery: the frozen 24 plus all 18 probes, 42 asks per arm, independent mode, one fresh
build per ask. Grading and stage attribution imported from `heldout_eval`, so both arms
come off one checker.

**Predictions, with falsifiers.**

- **P1 — the guarded floor does not move.** Frozen **19/24** and guarded probes **4/4**
  in both arms, and `asks whose outcome or stage differ` on the frozen 24 = **0**. This
  is a gate, not a prediction. The mechanism is §2's: the three passing `which` asks are
  claimed by dedicated paths before `answer()` runs. *Falsifier: any frozen pass lost →
  R1 is rejected and the flag stays off, and the loss is reported rather than tuned away.*
- **P2 — `which thing turns twice?` moves from fail to pass.** ~~It is the cleanest
  case~~ — **FALSIFIED BY A TEST BEFORE E5 WAS RUN, and E5 was therefore not run.**
  `tests/test_answer_path_r1.py::test_r1_alone_gives_which_thing_the_WRONG_shape_so_p2_is_falsified`
  puts both forms through the real `_question_shape` and they do **not** parse alike:

  ```
  what turns twice        -> subject_unknown  verb="turns"  tail=["twice"]         correct
  which thing turns twice -> subject_unknown  verb="thing"  tail=["turns","twice"] WRONG
  ```

  The `subject_unknown` branch (2142-2149) takes the **first non-function word after the
  interrogative** as the verb. `what` is followed directly by the verb; `which thing` is a
  two-word question phrase and `thing` is a content word, so it is taken as the verb. The
  arbiter then looks for a memory with `thing` as its verb, finds none, and vetoes. So R1
  converts a `recall` failure into a `shape_arbiter` failure — **a stage change with no
  score change**, which is precisely hazard 1 and precisely what P6 predicted. P6 was
  right and P2 was wrong, and the two were written in the same document an hour apart.

  **R1 is necessary and not sufficient.** What it does buy is pinned by
  `test_a_single_word_which_question_does_parse_correctly`: `which turns twice` parses
  exactly like `what turns twice`. The frame that actually fails in the battery is
  `which thing …`, not that one.

  **Why E5 was not run.** Its central prediction was falsified by a test that costs 0.1 s,
  and running 84 builds to confirm a stage change with no score change would have produced
  a number that looks like a result and is not one. The obvious repair — skip `thing`/`one`
  after `which` — is a **closed word class**, which is the `fly_v2` failure mode exactly: a
  modifier class closed at `{old, copper, heavy}` whose bred winner named `small` the head
  of `the small brass bell` and failed `test_shape_filler_position`. R1' needs a principled
  rule for question-phrase length and must be designed before it is coded, not smuggled in
  to make P2 come true.
- **P3 — the other class-A forms improve or stay equal, and none regresses.**
  `which of them is wet and is not on the hook?` and `which thing did i mention earlier
  than the kettle?` currently fail at `mouth`; giving them a shape may move them to a
  pass or to a `shape_arbiter` veto. Either is acceptable; a *new* failure on an ask that
  passed in the flag-off arm is not, and is caught by P1's per-ask comparison.
- **P4 — the paraphrase tier's score rises by at least 1 and the rise is named.** The
  prediction is deliberately weak: 4/18 → ≥5/18. A large rise would be suspicious, since
  R1 touches one question word and only three of the fourteen failures are class A.
- **P5 — classes B, C, D and E do not move at all.** Passive 0, polar 0, imperative 0,
  and the two class-E asks still failing at recall on coverage. *This is the prediction
  that makes E5 informative rather than merely hopeful: a repair that moves forms it was
  not aimed at is a repair nobody understands.*
- **P6 — stage mass moves from `recall`/`mouth` toward `shape_arbiter` on the class-A
  asks**, per hazard 1. A stage change with no score change is an expected outcome and is
  reported as such, not hidden.

**What E5 cannot show.** Whether R1 helps an organism that has been taught (it runs on the
live animal, not on a learner checkpoint). Whether R2 works. Anything about classes C and
D. And it does not select on the paraphrase tier: per `docs/selection_design.md` §3 the
tier is report-and-veto only, so a rise in it is evidence and not a fitness gain.

**If P1 fails**, the flag stays off, R1 is recorded as rejected with the lost ask named,
and the next step is R2 rather than a retry of R1 with a narrower word list — narrowing
until it passes would be tuning the instrument to the answer.

## 5. What would invalidate a result

- Any comparison made on scores rather than per-ask `(pass, stage)`. Hazard 1 says a
  stage can move with no score change, and a score-only comparison would report "no
  difference" over a real mechanism change.
- Both arms run in one process. `SHAPE_EXTRA_INTERROGATIVES` is a module global, so the
  arms must be separate processes or the second inherits the first's flag.
- The learned `interrogatives` set changed. If `which` appears in it, the experiment is
  measuring hazard 2 and not R1, and the retrieval blacklists moved too.
- The frozen suite's seal differs from `b9d0f2d83fbb7e78`, or the probe seal from
  `6b6117e9e0a7c331`. `run_generation.py` already refuses on the first and labels every
  row on the second.
- A result attributed to R1 and R2 together.

## Change log

- 2026-10-30 — **R1 implemented flag-gated, and its central prediction falsified by a
  test before E5 was run.** `SHAPE_EXTRA_INTERROGATIVES` (default `()`) plus a
  `SHAPE_INTERROGATIVES` **property** — a property rather than a class attribute because
  `BASE + EXTRA` at class scope is frozen when the class body runs, so setting the flag at
  runtime would silently do nothing and an A/B would measure the control arm twice while
  reporting that it had not. `run_generation.py` gained `--shape-extra` and records code
  flags in `provenance.code_flags`, because both arms of an A/B carry the same genome and
  the flag is the only thing distinguishing them. 10 tests in
  `tests/test_answer_path_r1.py`; suite **541 passed, 3 skipped**. **E5 was not run**: P2
  is falsified in §4 with the measured parse, R1 is necessary and not sufficient, and the
  obvious repair is a closed word class. Two test-harness defects were found and fixed on
  the way, both of which would have produced confident empty results: the stub snapshotted
  the constants at import so the flag fixture never reached it, and `N.SHAPE_INTERROGATIVES`
  read on the class returns the property object rather than its value.
- Written before any code. Classification measured by
  `docs/evidence/answer_path_probe.py` against the live animal: learned interrogatives
  are `['how','what','where','who']` with no `which`; the shape parser's gate is the
  closed tuple `("who","what","where")` at `neural_language.py:2108`; there is no passive
  handling anywhere in the file. Five mechanisms classified, two hazards recorded, three
  repairs proposed of which only R1 is in E5. Suite at 531 passed, 3 skipped. No core code
  modified yet.
