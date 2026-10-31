# Pre-registration: `cause`, a derived refinement of `stage`

Registered before generation 10 was run. Implementation: `cause_of` in
`tools/heldout_eval.py`, wired into the ask journal in `tools/run_generation.py`.
Tests: `tests/test_stage_cause.py`.

## The defect

`stage_of` classifies a failed ask by regex-matching the reply's `reason`. Its
last branch is a fall-through:

```python
return "recall_untraced" if not reason else "recall"
```

with a comment above it saying outright that attributing this to recall "is a
DEFAULT, not a measurement". Any unspoken reply with a non-empty reason that
matches no pattern is therefore labelled `recall`.

That default has been wrong for at least one ask across generations 0–9. E7's
instrumentation proved it: `which thing turns twice?` reports
*"it did not understand and was not in the mood to babble"*, which matches neither
`RECALL_RE` (`cover|no memor|nothing he rememb|…`) nor `GATING_RE`
(`did not feel like speaking|not feel like|…`), so it fell through to `recall`.
Its raw binder count is `None`, not `0` — the recall gate never executed. It is a
comprehension failure, and the tally `{"recall": 10, …}` quoted for ten
generations has contained it the whole time.

The consequence is not cosmetic. A stage tally is how the next repair is chosen,
and a comprehension defect filed under `recall` sends the next cut at memory.
That is exactly what happened: E7 built a recall-side fallback for it, and the
fallback is inert because there was no recall-side defect to fix.

## The change

A new field `cause`, computed from the same turn as `stage`, recorded beside it.

`stage` is **not** modified, **not** recomputed, and **not** backfilled. Rows for
generations 0–9 keep the values they were published with. This was chosen over
relabeling history because ten generations of journals, two sealed baselines and
several committed documents quote those numbers; rewriting them would make every
prior measurement unverifiable against its own record. Versioning the field
instead keeps both readable.

`cause_of` returns `stage_of`'s answer unchanged for every stage except `recall`.
For `recall` it returns one of:

| `cause` | meaning | evidence |
|---|---|---|
| `recall_gate` | the gate ran, found a posting, scored it, refused | `RECALL_RE` matches and `COMPREHENSION_RE` does not |
| `comprehension` | the organ never understood the question | `COMPREHENSION_RE` matches |
| `unclassified` | non-empty reason matching nothing | fall-through |

`recall_untraced` (empty reason) is already named by `stage_of` and passes through
unchanged, so `cause_of` deliberately has no `untraced` value of its own — that
branch would be unreachable, and an unreachable label in a published taxonomy is a
claim the data can never support.

`COMPREHENSION_RE` is `did not understand|does not understand|no content words|
no word of that|not one he knows|could not parse|cannot parse|made no sense|
no question in`. It is checked **after** `RECALL_RE` and wins, because
`RECALL_RE` contains broad tokens (`empty`, `no candidate`) that a comprehension
string could also contain, and "did not understand" is the more specific claim.

`unclassified` is not renamed to something confident. Inventing a fourth label for
"matched nothing" would repeat the original error with better vocabulary.

## Predictions, registered before the run

Generation 10: one clone of control genome `abffa2b7f101`, `--tier frozen,probe`,
42 asks. No flags. Nothing about the organ or the genome changes, so this is a
measurement of the labelling alone.

- **P1** — `stage` for all 42 asks is identical to generation 9, ask for ask. Any
  difference means the derived field perturbed the field it was derived from.
- **P2** — the ten `stage=recall` failures split **9 `recall_gate` + 1
  `comprehension`**, and the comprehension one is `which thing turns twice?` with
  `coverage: null`.
- **P3** — scores unchanged: frozen 19/24, paraphrase probes 0/14, guarded 4/4, stages
  `{"recall": 10, "mouth": 4, "gating": 3, "shape_arbiter": 2}`.
- **P4** — generations 0, 1, 2, 7, 8, 9 contain **no** `cause` key. If one
  appears, something backfilled history and the non-destructive claim is false.
- **P5** — no non-`recall` stage is ever reclassified. Checked as a property over
  a corpus of reasons, not just over this battery, because the guarantee has to
  hold for reasons no current ask produces.

## What would falsify the approach

- P1 or P3 failing ⇒ `cause` is not derived, it is entangled. Revert.
- P2 producing anything other than 9+1 ⇒ either the E7 finding was wrong or
  `COMPREHENSION_RE` is mis-scoped. Re-derive from the reasons, do not tune the
  regex to hit 9+1.
- P4 failing ⇒ history was rewritten. Revert and re-publish.
- `unclassified` appearing in generation 10 ⇒ a reason exists that matches
  neither regex and is not a gate refusal. That is a **new** finding and should be
  reported, not absorbed by widening a regex.

## Scope

Not done here, deliberately: no change to `stage_of`, no relabeling of historical
rows, no change to the frozen or guarded batteries, no change to any organ
constant, no multi-brain work, no refactor. `cause` is recorded on failures and is
`None` on passes, mirroring `stage`.
