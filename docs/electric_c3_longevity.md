# ELECTRIC C3 — longevity: three teach/consolidate/restart cycles

```
.venv\Scripts\python.exe tools\electric_longevity.py --cycles 3 --per-cycle 5 --budget 200 --seed 1
.venv\Scripts\python.exe tools\electric_longevity.py --cycles 3 --per-cycle 5 --budget 200 --seed 1 --probe-electric off
.venv\Scripts\python.exe tools\electric_c3_diagnose.py
```

**Headline: no memory loss and no interference across three cycles.** But this run
produced a second, unplanned result, and I have to be blunt about both: I read an
"age gradient" in the data that was not an age gradient at all, and the thing actually
broken is a held-out **frame**, not persistence.

## 1. Setup

3 cycles × 5 **new** facts = 15 facts, seed 1. Each cycle: build a fresh organ over the
same state file (the restart), teach 5 new facts with `hear(tell, speaker="you")`, switch
teach mode off, `consolidate(budget=200)`, `save_state(force=True)`, drop the organ,
rebuild, and ask **every fact taught so far** twice — same-words control (T) and
held-out paraphrase (H), graded by E1's role-word rule.

All 15 facts are drawn in **one** call to E1's generator, whose `used` set is per-call:
"one role per word across the batch, so no two facts can be confused with each other by a
shared content word." 45 distinct content words over 15 facts, 0 binder collisions.
**Shared-word interference is designed out**, so anything measured here is damage from
the cycles themselves, not from lexical collision. A word-collision arm is a separate
experiment.

Each consolidation ran fully: `2000 scanned, 274–334 urgent, 200 replayed × 3 passes`,
≈55 s per cycle (600 `live(learn=True)` replays each, 1800 total).

## 2. Retention — the answer is clean

| | probe after cycle 1 | cycle 2 | cycle 3 |
|---|---|---|---|
| inventory facts | 5 | 10 | **15** |
| inventory subjects | 5 | 10 | **15** |
| `_absence_inv` | 5 | 10 | **15** |
| state file | 4387 KB | 4389 KB | **4390 KB** |
| **H correct, ELECTRIC on** | 5/5 | 10/10 | **15/15** |
| confab / refuse / silence / other | 0 | 0 | **0** |

Final probe, ELECTRIC on: **T 15/15 correct, H 15/15 correct**, zero confabulations,
zero refusals, zero silences, zero contaminated replies. The inventory accumulated
exactly — 5→10→15, no extra subject, no lost subject, and **no cohort fact clobbered by
first-tell-wins** (the harness checks this explicitly; zero hits). 3 KB of state growth
across three cycles.

**The interference test that actually matters** is not the aggregate — it is per fact,
across probes. Of 15 facts, **0 changed verdict between any two probes**
(`tools/electric_c3_diagnose.py` §2). Nothing eroded, nothing got shadowed by a later
cohort.

## 3. Where I misled myself, and what the data really said

The ELECTRIC-off arm looked like decay:

| cohort | age | H correct |
|---|---|---|
| 1 | 2 | 2/5 |
| 2 | 1 | 4/5 |
| 3 | 0 | 5/5 |

I wrote that up internally as "the old path loses old facts." **It is not age.** Cohort 1
scored **2/5 at cycle 1, 2 and 3 identically**, and cohort 2 **4/5 at both cycle 2 and 3**
— a gradient that does not change with age is not an age effect. The cause is the frame
mix of each slice, which my consecutive grouping made accidental:

| cohort | H2 drawn | H3 | H1 | H correct |
|---|---|---|---|---|
| 1 | **3** | 2 | 0 | 2/5 |
| 2 | **1** | 4 | 0 | 4/5 |
| 3 | **0** | 3 | 2 | 5/5 |

Perfect rank correlation. Per-fact trace confirms it: every H2 fact confabulated at **its
own first probe**, before any later cohort existed. It was never answerable — it did not
erode.

**The lesson is about the design, not the organism:** slicing one generated batch into
consecutive groups silently correlates cohort with frame, because the generator assigns
frames randomly per fact. Any future longevity experiment must stratify cohorts by frame
or report the frame mix per cohort on the face of the table. I reported the age table
first and the frame mix only after checking, which is exactly backwards.

## 4. The real finding: the old path cannot answer H2, and it answers by echoing

ELECTRIC off, held-out paraphrase, by frame:

| frame | result |
|---|---|
| H1-reverse-role (`what {v} the {b}?`) | **2/2 correct** |
| H2-question-word (`which thing does the {a} {v}?`) | **0/4 — 4 confabulations** |
| H3-passive (`what is {v} by the {a}?`) | **9/9 correct** |

Every confabulating reply is the **question repeated verbatim** — checked, not eyeballed:
`said == ask` after normalisation on **11/11** confabulating replies across all probes.

```
tell : the dainty towns the bottom
ask  : which thing does the dainty towns?
said : which thing does the dainty towns?
```

That is not forgetting. The fact is present in the binder (`source: recalled
proposition` — retrieval fired), and the interrogative *"which thing does…"* is not
mapped to a role, so the question comes back out as the answer. **Confabulation by echo,
not by absence.**

**ELECTRIC masks it.** The same 4 H2 facts, same seed, same state, probed with the flags
on: **4/4 correct**, `source: electric_taught`, replying `the dainty towns the bottom`.
The keyed inventory answers a frame the old path structurally cannot. That is a point in
ELECTRIC's favour that C1/C2 had not isolated, because in those arms the H2 facts were a
small random subset and never split out by frame.

## 5. No fix implemented — the brief's condition was not met

The brief said: *if memory loss or interference appears, diagnose the smallest
persistence/consolidation fix.* **Neither appeared** — 15/15 inventory survival, 0/15
verdict changes, 0 clobbering, 0 contamination, 3 KB growth. So no persistence or
consolidation change was made, and none is warranted.

The H2 echo defect **is** real but is **not** a persistence/consolidation defect: it is
interrogative→role mapping in the retrieval path. Fixing it would mean touching
`answer()`'s question analysis — a broad change to the decision path, explicitly out of
scope here, and it would have to be re-verified against the **guarded grader contract,
which this run did not touch**. It should be its own experiment. I am deliberately not
writing a test that asserts the echo behaviour as expected: that would promote a defect
into a contract.

Added instead, as a cheap pin of what this run *did* establish:
`tests/test_electric.py::test_three_cycles_do_not_erode_the_inventory` — three cohorts of
two facts, each taught over a restarted organ, consolidated (`budget=8`, 0.7 s) and
saved; asserts all six verbatim tells survive in the inventory and none was overwritten.
It asserts **survival, not answer quality**, because answer quality is a frame problem.

## 6. Consistent with E19, in a new regime

README:276-279 records that **E19 falsified eviction** (0 of 19 failures were eviction;
taught rows survive to ask time). C3 re-tests that in a regime E19 did not cover — three
full cycles, 15 facts, 1800 consolidation replays, three restarts — and finds the same:
no fact lost its binder support, and the only failures are frame-shaped. Displacement
across cycles is now falsified twice, not once.

## 7. Not established

- **Not a real restart.** Each cycle rebuilds an organ object in one process over the same
  file. A `serve.py` shutdown/startup is still untested, as in C2.
- **Probing perturbs, and I did not quantify it.** `answer()` calls
  `live(text, learn=True, speaker="you")` internally, so every question **wires** the
  connectome; 60 asks per arm re-wired the facts being tested. No verdict worsened across
  probes, which is evidence against damage, but this is not a clean read-only measurement
  and nothing in the harness separates wiring-by-asking from wiring-by-consolidating.
- **Three cycles is not longevity.** 15 facts, not thousands. One seed. No 10- or 30-cycle
  run, so the shape of the curve beyond age 2 is unknown — and after §3 I do not trust an
  aggregate table without its frame mix.
- **Shared-word interference untested**, by design (§1). Two facts competing for one
  subject word — the first-tell-wins case — is a different experiment.
- **H2 is measured, not diagnosed.** I established the failure mode (verbatim echo,
  retrieval fired) but did not locate the interrogative-mapping code or explain why
  passive and reverse-role survive while question-word does not.
- **Untouched:** the `copper`/`bell` multi-relation modifier-keying limitation from
  earlier generations.

## 8. Suite

`tests/test_electric.py` is now **25 tests**. **Suite: 819 passed, 3 skipped, 5 warnings**
(was 818; +1 new test; **zero erosion**). ELECTRIC stays **off** for battery runs; no
battery run was made here; **the guarded grader contract was not touched.**
Evidence: `docs/evidence/electric_c3_longevity.json` (on-path),
`electric_c3_longevity_oldpath.json` (old path).
