# Passing-ask instrumentation — the measurement repair

**Additive. Cannot change a score. No organ change, no core change, no multi-brain work,
no broad refactor.** `tests/test_passing_ask_instrumentation.py` — 10 tests, zero brain builds.
Suite: **96 passed** across the instrumentation, selection-harness and stage-cause tests.

---

## 1. What was wrong

`docs/evidence/paraphrase_gap_diagnosis.md` could not do the job it was asked to do. It was meant
to compare a failing ask against its passing twin on identical taught evidence and take the minimal
difference. **One side of every comparison was absent from the instrument.**

Two distinct causes, which the diagnosis initially conflated:

**(a) `stage` and `cause` were explicitly gated on failure.** In both
`tools/heldout_eval.py::ask_record` and `tools/run_generation.py`'s journal row:

```python
"stage": None if ok else stage_of(t, why),
"cause": None if ok else cause_of(t, why),
```

**(b) `coverage`, `required` and `nearest` were *not* gated** — the generation runner already
recorded them for every ask, with a comment saying so. They came back `None` on passing asks
because **the organ only populates them when the recall gate runs**, and a passing ask answered by
another path never reaches it. `heldout_eval.ask_record` did not carry them at all.

Cause (b) is why the paraphrase probe printed `pass form bypasses the recall gate: True` for all
four pairs and had to retract it: a blank coverage was ambiguous between *"computed and None"* and
*"never computed"*, and the probe guessed the first when the truth was the second.

## 2. The repair

Three additive keys, recorded for **every** ask in both files:

| key | meaning |
|---|---|
| `stage_all` | `stage_of(t, why)` unconditionally. `stage_of` is **total** — on a spoken reply it returns `mouth` / `shape_arbiter` / `other` — so for a passing ask it says *which path answered* rather than which refused. |
| `cause_all` | `cause_of(t, why)` unconditionally, same reasoning. |
| `coverage_present` | `"coverage" in r`. **Separates the two Nones** that caused the retracted inference. |

`heldout_eval.ask_record` also gains `coverage`, `required` and `nearest`, which it never carried.

**`stage` and `cause` are untouched** — still `None if ok else ...`, byte-for-byte the published
behaviour. Generations 0–14, every archived journal and every historical comparison keep the
values they were scored with. The new keys sit beside them so the two can be compared row by row.

## 3. What the tests pin

Three properties, in this order because the first is the safety contract:

1. **Backward compatibility.** A passing ask still records `stage=None`; a failing ask still
   records `stage == stage_of(...)`. `cause` is *not* a key of `ask_record` at all — it is added by
   the generation journal — and the test asserts that stays true rather than inventing a key the
   published schema never had. Two earlier drafts of this test asserted `ok["cause"] is None` and
   failed with `KeyError`; the tests were wrong, not the repair.
2. **The repair works.** `stage_all` / `cause_all` / `coverage_present` are populated on passing
   and failing asks alike, and on a failure `stage_all == stage` and `cause_all == cause`, which is
   what makes old and new rows comparable.
3. **No score can move.** `pass`, `said`, `words`, `spoken` and `why` are computed from the same
   inputs, before any diagnostic field is derived; the same turn yields the same verdict; exactly
   one ask is issued per record.

Plus: archived rows lacking the new keys still compare; `stage_of` is total on a spoken reply so
`stage_all` never raises; and an engine error is still attributed `engine_error` rather than being
relabeled a passing path by the new field.

### A fixture bug worth recording

The first two runs failed 6/10 for a reason that has nothing to do with the repair: the fake turns
were not spoken. `converse._spoken` requires `reply["spoken"]` **and** a non-empty `_said(turn)`,
and `_said` reads `reply["utterance"]` (then `reply["response"]`) — **not** `turn["said"]`. The
fixtures set the wrong key, so every "passing" turn graded as a refusal and the tests silently
measured the failure branch. Had the assertions been looser, this would have passed while testing
nothing — the same class of defect as E17a's tautological H2.

## 4. Not done: the battery rerun

**The control battery was not rerun and no new pass/fail data exists yet.** The instrument is
built and tested; it has not been pointed at a live brain. Populating the new fields needs a real
run — one control line, 42 asks, ~18 minutes of brain builds — which did not fit this session's
budget. Starting it and reporting unverified output would be worse than saying plainly that it is
the immediate next step.

Until that run happens, §5 is inference from the **failing side only**, exactly as before. It is
labelled as such.

## 5. The next smallest capability defect — candidate, unconfirmed

From the failing-side data already in `generation_13_asks.jsonl`, one ask stands out as the
smallest defect in the battery:

> **`how often does the bell turn?`** — the correct taught row **`the copper bell turns twice` is
> retrieved and ranked top**, and the ask still fails at coverage **0.514** against a 0.6 floor.

This is the only failing ask where **retrieval and ranking both succeed** and only the threshold
blocks. Every other recall-gate failure retrieves a *book* row instead
(`did you not tell me about it sooner`, `when the water in the kettle was boiling`) — a candidate
generation defect, closed by E14a — or fails downstream at `mouth`.

Why it is *not* already closed, and why it needs the rerun to confirm:

- E12a closed **restricting `must`** to answerable terms; E14a closed **admitting all tells as
  candidates** (ceiling 0.5488); generation 2 and generation 6 closed **moving the floor**. None of
  those is "the top-ranked row is correct and taught, and is still refused."
- The distinguishing feature is that the correct row is **already first**. A repair keyed on
  *rank* rather than on *score* — trust the top row when it is a taught row — is a different
  mechanism from all three, and it is the only one the data suggests.
- But E17a showed the answer here is a **frequency adverbial** (`twice`), not a counted entity, so
  the answer path may not be able to *produce* `twice` even if the gate admits the row. **That is
  precisely what the new instrumentation would settle**: with `stage_all`, `cause_all` and
  `coverage_present` recorded on the passing asks, a rank-keyed repair can be compared against a
  passing twin row by row instead of by inference.

**No experiment is pre-registered on this.** It is a candidate identified from one side of the
data, and §4 says why that is not enough. The rerun comes first; if the instrumented journal shows
the passing twins succeeding on a *different path* rather than a higher coverage, the candidate
dies there and costs nothing.

## 6. Files

| file | change |
|---|---|
| `tools/heldout_eval.py` | `ask_record` gains `stage_all`, `cause_all`, `coverage_present`, `coverage`, `required`, `nearest`. `stage` unchanged. |
| `tools/run_generation.py` | journal row gains `stage_all`, `cause_all`, `coverage_present`. `stage`/`cause` unchanged. |
| `tests/test_passing_ask_instrumentation.py` | new, 10 tests, zero brain builds. |
