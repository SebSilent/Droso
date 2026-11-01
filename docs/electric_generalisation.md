# ELECTRIC generalisation — E1's 20 novel facts, asked in a held-out frame, after restart

```
.venv\Scripts\python.exe tools\electric_generalise.py --facts 20 --seed 1
.venv\Scripts\python.exe tools\electric_generalise.py --facts 20 --seed 1 --control
```

## 1. Headline, and the honest decomposition

| arm | correct | confabulated | refusal | silence |
|---|---|---|---|---|
| **treatment** (ELECTRIC on) | **20/20** | **0** | 0 | 0 |
| **control** (all flags off) | 14/20 | **6** | 0 | 0 |

**Do not read the 20/20 as ELECTRIC's achievement.** Fourteen of those twenty were
already answered correctly by machinery that predates this work. The capability delta is
exactly the six the control got wrong:

| held-out frame | control | treatment | ELECTRIC's marginal gain |
|---|---|---|---|
| H1 `what {v} the {b}?` (reverse role) | 2/2 | 2/2 | none — the old path already had it |
| H2 `which thing does the {a} {v}?` | **0/6, all 6 confabulated** | **6/6** | **+6, and 6 confabulations eliminated** |
| H3 `what is {v} by the {a}?` | 12/12 | 12/12 | none needed |

18 of 20 answers carried `source=electric_taught`; the 2 H1 answers came from the
pre-existing path, which is the correct division of labour and is reported rather than
claimed.

**Confabulation, the category that is worse than silence, went 6 → 0.** In the control
every H2 failure was the organism echoing its own question back as an answer
(`which thing does the dainty towns?` → `which thing does the dainty towns?`), which
contains the forbidden role word and not the required one. This is the same defect the
5-fact demo showed on `where did you put the lantern?`; it is now measured at 20 facts
and it is now gone.

## 2. Why this is a generalisation test and not a nicer demo

The harness **imports E1's generator rather than copying it**, so if E1 changes this test
changes with it. That generator (`teach_episode.py:81-191`) draws content words from the
**live 10,234-word vocabulary**, filters them with **the organ's own closed-class sets**
rather than a private list, verifies each proposition's absence against the **binder's own
repeat key**, and assigns one role per word per batch so no two facts can be confused by
a shared content word. Writing my own fact list would reintroduce the exact bug
`teach_episode.py` documents: `fly_v2` bred a winner that happened to match a private
vocabulary the generator controlled.

Propositions are **semantically arbitrary on purpose** — `the continuation shouldn the
rendered`, `the euston jurors the indulgence`. A fact that could be guessed from corpus
priors would make a correct answer ambiguous evidence; one that cannot be guessed makes
it evidence about the teaching.

**Asks are E1's held-out frames, never the training frame** `what does the {a} {v}?`. An
ask that repeats the tell's own word order tests recall of a sentence, not grasp of a
fact. Grading is by **role word, not string equality**: the required role's word must
appear, and the forbidden role's word must not.

**Restart is real**: teach into a copy of the trained organism → `save_state(force=True)`
→ discard the object → build a new organ → `load_state()` → ask. `taught_after_load=20`.

### Relationship to E1's published 2/20 — not a contradiction

E1 measured the **cost** of teaching through the sealed-session **shadow** rig, after
consolidation, against a 60,000-row FIFO binder that evicts by `meta.pop(0)` consulting
nothing. Its 2/20 is a statement about displacement on that path. This harness measures
the **answer path** of a live organ. The control here scores 14/20 on the held-out
frames, which is not E1's number because it is not E1's question. **No claim is made that
E1 was wrong.** The open question this leaves is §6.

## 3. The bottleneck was one regex, and it was phrase-driven

The first run scored **0/3 with 3/3 confabulated** and `source=electric_taught` firing
**zero** times. Diagnosis, before any fix:

| frame | why the bind returned `None` |
|---|---|
| H2 `which thing does the {a} {v}?` | detector required the literal strings `what does` / `what is X by` / `what Vs`. `which thing does` contains none. **rel = None → fall through.** |
| H3 `what is {v} by the {a}?` | matched, and the guard passed because E1 uses `{v}` verbatim — my predicted morphology failure (`towned` vs `towns`) does **not** occur on this corpus |
| H1 `what {v} the {b}?` | asks for the **subject**; a subject-keyed index structurally cannot serve it. Correctly declined; the old path answers it. |

The failure was **not** retrieval, persistence, the agent guard, the mood gate, or
coverage. It was that "which relation is being asked about" was implemented as a list of
surface phrases instead of a structure.

## 4. The one capability-first fix, and the asymmetry that makes it safe

`_electric_bind(question, inventory, broad_agent=False)` gained a **structural** agent
branch: a wh-word plus do-support is an agent question, whatever the wh-word is.

```python
elif broad_agent and "like" not in words and re.search(
        r"\b(what|which)\b[^?.]*\b(do|does|did)\b", ask):
    rel = "agent"
```

**`broad_agent` is passed by the ELECTRIC answer path only. E24's absence licence keeps
the narrow detector** (`neural_language.py:170`, verified by
`test_licence_keeps_the_narrow_detector`). The asymmetry is deliberate and it is the only
safe direction to be asymmetric in:

- Widening the **licence** would let the organ claim *knowing-it-doesn't* about asks E24
  never licensed it to discuss — changing a behaviour measured across 24 generations.
- Widening the **answer** path means ELECTRIC may speak a fact it was *genuinely told*,
  keyed, where the licence would merely have stayed silent.

Scope is `what|which`. `who did the dainty town?` is **not** claimed, and a test asserts
that: no frame in E1's corpus required it, and widening a relation regex on a guess is
precisely how the guarded battery has silently broken before.

## 5. Suite status

**814 passed, 3 skipped, 5 warnings** (was 812; +2 new tests; zero erosion).
`tests/test_electric.py` is now 20 tests. No E24 test was amended in this round.

## 6. Still open, in priority order

1. **E1's cost question is untouched.** This harness does not consolidate and does not
   measure binder displacement. Whether 20 taught facts survive a real consolidation
   cycle — the thing E1 was built to ask — is **unmeasured**.
2. **One relation class, one frame family.** All 20 facts are `the {a} {v} the {b}`
   agent sentences. Locative and property facts were exercised only by the 5-fact demo.
   A multi-relation generalisation run is the next widening.
3. **H1 is answered by luck of the old path, not by memory.** 2/2 is far too thin to
   conclude the reverse-role question is solved; a subject-keyed index cannot answer
   `what {v} the {b}?` and does not.
4. **Answers are verbatim tells.** `what is mills by the gather?` → `the gather mills the
   gaily`. Correct, and it contains the required role, but it is recall of a taught form,
   not recomposition.
5. **Cosmetic bug found while writing this:** the harness prints `(PERSISTED)` when
   `taught == taught_after_load`, which is trivially true at `0 == 0` in the control arm.
   The control's line reads `taught_after_load=0 (PERSISTED)`. The number is right, the
   label is not; it must not be quoted as evidence of persistence in the control.

## 7. Battery posture

**ELECTRIC stays off for battery runs.** Generation 24 (C3 fired: frozen 19/24 → 17/24)
is why; the agent guard and the broad branch were both added after that run, so gen 24's
numbers describe neither. No battery run was made in this round. The scoring-contract
problem that run exposed is recorded in `docs/scoring_contract_issue.md` and **the grader
was not changed.**
