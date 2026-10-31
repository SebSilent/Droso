# Passing-ask analysis — generation 15, the first instrumented battery

**Run:** `tools.run_generation --generation 15 --lines 1 --tier frozen,probe`, control clone
`abffa2b7f101` (parent, unmutated), 42 asks, ~28 s/ask. Journal
`state/selection/generation_15_asks.jsonl`. Probe `docs/evidence/passing_ask_analysis.py`,
machine-readable `passing_ask_analysis.json`. Read-only, no brain builds.

This is the first battery carrying `stage_all`, `cause_all` and `coverage_present` on **every**
ask. Before it, one side of every passing-vs-failing comparison was absent from the instrument.

**Headline: 23 pass, 19 fail — and of the 10 asks where the recall gate actually ran, every one
retrieved only *book* rows. Zero taught rows reached the candidate set, on passing and failing
asks alike.**

---

## 1. The two groups

| | passing (n=23) | failing (n=19) |
|---|---|---|
| `coverage_present` | **1** (absent 22) | **9** (absent 10) |
| coverage min / max / mean | 0.570 / 0.570 / 0.570 | 0.340 / 0.555 / 0.464 |
| `stage_all` | other **17**, shape_arbiter **5**, recall **1** | recall **10**, mouth **4**, gating **3**, shape_arbiter **2** |
| `cause_all` | other 17, shape_arbiter 5, recall_gate **1** | recall_gate **9**, mouth 4, gating 3, shape_arbiter 2, comprehension 1 |
| asks with a `nearest` list | 1 | 9 |
| `nearest` contains a taught (`droso:`) row | **0** | **0** |
| `nearest` all book | 1 | 9 |

`nearest` and `required` are populated only when the recall gate runs, so those two rows are
measured over the **10** asks with `coverage_present=True` — not over all 42. That is the precise
scope of the headline claim.

## 2. What the instrument settled

**(a) The retracted inference was directionally right, for the wrong reason.**
`paraphrase_gap_probe.py` printed `pass form bypasses the recall gate: True` and I retracted it as
unsupported, because a blank coverage could not be told apart from a gate that ran and returned
None. `coverage_present` now settles it: **22 of 23 passing asks have `coverage_present=False`** —
the recall gate genuinely never ran. They answer by `other` (17) or `shape_arbiter` (5). The
original claim was correct; the *evidence* for it was not, and it took the new field to make it one.

**(b) Exactly one passing ask traversed the recall gate.** Coverage 0.570, `cause_all=recall_gate`,
and its `nearest` list is **all book**. So the single pass that went through the gate did so on a
book row, not a taught one.

**(c) The failing side splits cleanly.** 9 fail *at* the gate (`recall_gate`, all with coverage
0.340–0.555, all nearest-book). 10 fail *after or before* it: mouth 4, gating 3, shape_arbiter 2,
comprehension 1 — and those 10 have `coverage_present=False`, so they never reached the gate.
This matches the earlier `cause_of` work (9 genuine gate refusals, 1 comprehension) and now extends
it to the downstream half.

## 3. My proposed candidate is falsified

Last turn I named the next smallest defect as:

> `how often does the bell turn?` — the correct taught row `the copper bell turns twice` is
> retrieved and ranked top, still refused at coverage 0.514 against a 0.6 floor.

**The instrumented battery does not support it.** The candidate filter — fails at `recall_gate`,
`nearest` non-empty, `nearest[0]` a `droso:` row — matched **zero** asks. Across all 10 asks where
retrieval ran, `nearest_has_taught=0`. No failing ask has a taught row ranked top, because no
failing ask has a taught row in its candidate list at all.

The earlier claim came from `paraphrase_gap_probe.py`, a separate probe with its own session and
retrieval call, not from the harness journal. Either that probe retrieved under different binder
state, or the row was not resident when the harness asked. **The harness journal is the
authoritative instrument, and it says the candidate does not exist.** I am recording the
falsification rather than reconciling the two, because the whole point of the repair was to stop
reasoning from a probe that sees one side.

It also means the *mechanism* I proposed with it — a rank-keyed repair, "trust the top row when it
is taught" — has nothing to act on. There is no taught top row.

## 4. The next smallest capability defect, now supported

> **Taught evidence does not reach retrieval.** For every ask where the recall gate ran (10/42),
> the nearest-3 candidate list contained **only book rows**. The 9 gate failures are not
> threshold failures on the right row; they are failures to retrieve the right row at all.
> Coverage 0.340–0.555 is what a *book* row scores against a taught-fact question.

This reframes the whole recall-gate story. E12a (restrict `must`), E14a (admit all tells,
ceiling 0.5488), generation 2 and generation 6 (move the floor) all acted on the **score**. The
data says the score was never the binding constraint for these asks — **the candidate set was**.
A threshold repair cannot fix an ask whose correct row is not among the candidates, which is
consistent with every one of those experiments coming back inert or `no_gain`.

It also connects to two things already measured and never joined up:

- **Binder census** (`docs/evidence/binder_census.py`): 60,000 rows, **99.19% `book`, 0.78%
  `droso`**, eviction **blind FIFO**.
- **E3 / P4 partially falsified**: blind FIFO evicted a `droso` row with count 4561 — a heavily
  reinforced taught row, discarded anyway.

Taught rows are 0.78% of the binder and are evicted without regard to value. That is a sufficient
mechanism for "nearest is all book" and it needs no new hypothesis.

**Scope honesty:** this is established over the 10 asks where retrieval ran. For the other 32 the
gate never fired, so the journal cannot say whether taught rows were resident — only that
retrieval was not attempted. The claim is about the gate-running subset, and it is total there.

## 5. Smallest flag-gated experiment supported by this

**E19 — retention-vs-retrieval attribution.** Read-only, default-off, no organ or core change,
no multi-brain work, no refactor.

The defect is "taught rows absent from candidates," but that has **two** possible causes and they
need different repairs:

1. **Evicted** — the row is gone from the binder by the time the ask runs (retention).
2. **Resident but not retrieved** — the row is in the binder and the retrieval query does not
   surface it (retrieval/scoping).

Choosing a repair before separating these repeats the E17a mistake of acting on an unmeasured
mechanism. So E19 measures first:

- **Flag:** `--binder-attribution` (default off), `CODE_FLAGS["binder_attribution"]`.
- **What it adds:** for each ask where the recall gate runs, a read-only snapshot recording whether
  the *expected* taught row is still resident in the binder, its reinforcement count, and its rank
  under the retrieval query actually used. Three additive journal keys: `taught_resident`,
  `taught_count`, `taught_rank`. Nothing is written, evicted or reordered.
- **H1:** for the 9 `recall_gate` failures, `taught_resident` is **False** — eviction is the cause.
- **H2:** `taught_resident` is **True** but `taught_rank` is outside the nearest window — retrieval
  is the cause.
- **Abort:** if the expected row cannot be identified for an ask, that ask is recorded
  `taught_resident=None` and excluded; if more than half are `None`, E19 aborts and the
  attribution is reported as not established rather than guessed.
- **Guard:** the survivor loses zero frozen passes and zero guarded probes, or the parent stands.
  Because the flag is read-only the guard should be trivially satisfied; if it is not, the flag is
  not read-only and is wrong.
- **Cost:** one control line, 42 asks, ~18 min. No new genome, no mutation.

**Only after E19** does a repair become proposable, and which one depends on the answer: H1 points
at §7b value-weighted eviction (pending, not started); H2 points at retrieval scoping, which is
where E9/E10 already aborted and would need a different framing. **No repair is pre-registered
now.** Proposing one before the attribution is exactly the error this doc exists to correct.

## 6. Files

| file | change |
|---|---|
| `state/selection/generation_15.jsonl`, `generation_15_asks.jsonl` | new, instrumented control battery. |
| `docs/evidence/passing_ask_analysis.py` | new probe, read-only. |
| `docs/evidence/passing_ask_analysis.json` | new, per-ask records and group summaries. |
| `docs/evidence/passing_ask_analysis.md` | this file. |

`ANSWERABLE` is defined probe-locally (it does not live in `tools/`); it is kept identical to the
set E17a used so the two probes' answerable-term counts agree. The probe imports neither `FROZEN`
nor `PROBES` — `expect` is read from the journal row, which already carries it.
