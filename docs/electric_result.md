# ELECTRIC — first open-ended live-learning prototype

**Status: the demo works.** Teach facts in natural language → restart the organism →
answer the same facts in different words → and say it does not know a fact that was
never told.

```
.venv\Scripts\python.exe tools\electric_demo.py            # treatment
.venv\Scripts\python.exe tools\electric_demo.py --control  # every flag off
```

## 1. Result

Five facts taught in life 1, asked in different words in life 2, after a full restart:

| asked (life 2) | taught (life 1) | treatment | control |
|---|---|---|---|
| `where is the scarf?` | the scarf is on the hook | **`the scarf is on the hook`** (direct) | silent |
| `where is the coat?` | the coat is in the hallway | **`the coat is in the hallway`** (direct) | silent |
| `what is the bell like?` | the bell is copper | **`the bell is copper`** (direct) | silent |
| `what bites the latch?` | the frost bites the latch | silent | silent |
| `where did you put the lantern?` | the lantern is on the shelf | **`the lantern is on the shelf`** (direct) | **echoes the question** |
| `what is the scarf like?` | *never told* | **`i don't know, scarf was told but no property was ever told for scarf`** | **`the scarf is on the hook`** |

**Treatment: 4/5 paraphrases answered, 1/1 ignorance admitted.**
**Control: 2/5 answered, 0/1 ignorance admitted.**

The control's failures are not just "fewer answers". Two are worth naming:

- It **echoes the question as the answer** on `where did you put the lantern?` — the
  ask out-matches the fact it belongs to, which is the failure mode the existing
  question-filter was written to catch.
- On the never-told fact it **confabulates**: asked what the scarf is *like*, it
  answers where the scarf *is*. It states something it was told, in response to a
  question it was not answered by. This is the single worst behaviour in the whole
  project — the organism asserts a non-sequitur with full confidence.

ELECTRIC turns that specific answer into `i don't know`. **That is the capability
gain, and it is a correctness gain before it is a fluency gain.**

## 2. What was built

Four pieces, all behind two flags, both default off:

**Teach mode (`ELECTRIC_TEACH`).** `_absence_note` already extracted
`(relation, subject, object)` from every tell the user made. It was throwing the
sentence away and keeping only the frame. ELECTRIC keeps the sentence too, in
`_taught_says[subject][relation]`. **First tell wins** — a re-tell does not
overwrite, because a fact that changes when a later sentence arrives is a recency
artifact, not a memory.

**Consolidation / persistence.** `_absence_inv` was session-scoped by E24 design,
which is right for a diagnostic and fatal for a learner. Both inventories now go
into the version-2 state document — but **only when the run opted in**:

```python
"taught_says":       self._taught_says  if ELECTRIC_TEACH     else {},
"absence_inventory": self._absence_inv  if ABSENCE_INVENTORY  else {},
```

With every flag off, the state document is unchanged, so the battery baseline keeps
its meaning. On load the shape is **validated, not trusted**: anything that is not
`dict → dict → str` is dropped and the organism simply does not remember, which is
the honest failure, rather than a corrupt file becoming a source of answers.

**Semantic retrieval over taught facts.** `_electric_bind(question, inventory)` —
which relation is being asked about, and which subject does this ask bind to. This
is E24's licence detection **lifted out verbatim and shared**, not reimplemented:
the answer path and the refusal path must agree on the binding, or one ask can be
refused for a relation and answered for another. Keyed lookup only. No recall, no
similarity search (E24 abort A6 stands): `where are the scarves?` returns `None`
even though `scarf` is in the inventory.

**Direct answer emission (`ELECTRIC_ANSWER`).** One hook, placed **before** the
absence licence and therefore before the shape arbiter, the binder recall and the
resonance competition:

```python
if self.ELECTRIC_ANSWER:
    told = _electric_answer(text, self._taught_says)
    if told:
        return {"spoken": True, "answered": True, "utterance": told,
                "source": "electric_taught", "direct": True}
```

This is the series-gate cut the capability plan called for. A taught fact used to
have to win four independent competitions in series — coverage floor 0.6, shape
arbiter, resonance above 0.55, mood — so a known fact could still come out silent
(E10 measured a resonance winner at 0.4129 against a 0.55 floor on an ask whose
fact was correctly retrieved). The direct path removes two of the four for the
class of asks that already retrieve correctly.

## 3. Why the answer is the verbatim tell, not a regenerated sentence

`_absence_frame` drops the locative preposition: `the scarf is on the hook` and
`the scarf is in the box` both store `obj = "hook"` / `"box"` with no preposition
attached. Rebuilding `the {subj} is on the {obj}` would **invent a preposition the
organism was never told**. Carrying the tell itself is both honest and smaller.

This is a real limitation, not a cosmetic one: the answer to `where is the scarf?`
is the sentence that was taught, so ELECTRIC currently demonstrates *recall of a
taught form*, not *recomposition of a stored value into a new form*. Recomposition
requires the frame extractor to keep the preposition, which would change E24's
stored values. Deferred deliberately.

## 4. What is NOT claimed

- **Not generalisation yet.** The 4/5 is against five facts chosen to fit the three
  relation classes the extractor knows. E1 measured true generalisation at **2/20**;
  that has not been re-run and is the next honest test.
- **`what bites the latch?` fails.** The agent relation is stored but `_electric_bind`
  does not detect it in that surface form — its regexes cover `what does`, `what is X
  by`, `what Xs`, and this ask matches none. This is E24's detector, not ELECTRIC's
  lookup. Recorded, not fixed, because widening a relation regex is exactly the kind
  of change that has silently broken the guarded battery before.
- **The mood gate is untouched.** The plan's item (c) — that a direct lookup should
  not be filtered by "I don't feel like speaking" — is not implemented. The direct
  path returns before the mood gate is consulted, so it is bypassed rather than
  reformed. That is a difference worth stating: the gate still governs everything
  the direct path does not claim.
- **No new memory architecture.** No multi-brain work. The binder, cortex, SAN and
  chain are untouched; the taught inventory is a plain dict beside them.

## 5. Regression net

The battery is kept as a safety net and is **not being optimised for**. Generation
24 runs the gen-23 arm plus `--electric`, one flag different, so the guarded set and
the frozen tier are checked rather than chased.

**Abort conditions carried forward:** C1 guarded must stay 4/4 — and specifically,
the scarf must still refuse, because ELECTRIC answers only from a keyed
`(subject, relation)` hit and no place was ever told for the scarf. C4 is the shim
detector and is already covered by test: an untaught relation for a taught subject
must return `None`, never an adjacent value. C5: if frozen rises but every new pass
is in one script family, that is overfit, not gain.

## 6. Tests

18 new in `tests/test_electric.py`. Full suite **812 passed, 3 skipped** (was 794;
+18, zero erosion).

Two E24 tests amended, not deleted, both because ELECTRIC changes an invariant on
purpose:

- `test_e24_inventory_is_session_scoped` asserted `save_state` must never mention
  `_absence_inv`. "Never on disk" was right for a diagnostic instrument and is wrong
  for a learner that must remember across restarts. Restated as: **persisted only
  behind the flag; with every flag off, nothing goes to disk** — asserted on the
  actual `else {}` branches.
- `test_e24_flag_is_a_module_gene` asserted `save_state` must not mention
  `ABSENCE_INVENTORY` at all. That check was blunt because the inventory was never
  written, so any mention proved the flag had leaked. ELECTRIC legitimately reads
  the flag to decide *whether* to write. Narrowed to the invariant that still
  matters: **the flag itself is never serialised and never restored.**

One test-side bug caught while writing: `test_control_path_is_unchanged` initially
set `_absence_inv` without setting `ABSENCE_INVENTORY`, so the licence never fired
and the ask fell through to the echo path — the test asserted `spoken is False`
against a genuine `spoken is True`. Fixed by constructing E24's phase 1 exactly:
licence on, ELECTRIC off. The failure was informative — it is the same echo
confabulation the control demo shows.

## 6b. Battery regression run (generation 24) — C3 FIRED, and it is informative

`--absence-inventory --coverage-exclude frame --electric` against the gen-23 arm, one
flag different. **frozen 19/24 → 17/24, probes 1/14 → 2/14, guarded 4/4.** Net answered
23/42 → 23/42, **net 0**. Verdict: LOST regression. Two gained, two lost:

**Gained:** `how often does the bell turn?` and `what is bitten by the frost?` — both
previously silent, both now answered.

**Lost — bug 1, a real defect, now fixed.** `what bites the latch?` went from the
correct `frost` to **`the latch holds the door`**. The inventory keys on *subjects*, and
this ask names the *object*: `latch` is itself a subject with its own agent fact, so the
bare keyed bind answered a question nobody had asked, confidently. This is precisely the
failure C4 was written to catch, and it was caught by the battery, not by the demo —
the demo's five facts never put an object in the ask. Fixed by an **agent guard**: an
agent question is a question about an *action*, so the ask must share a content word with
the taught tell besides the bound subject, or the claim is dropped and the ask falls
through to the pre-ELECTRIC path. The guard is exact-word, not stemming —
`what does the frost bite?` does **not** match taught `bites` and is deliberately left
unclaimed, because E24 abort A6 bans similarity search and the safe failure is silence,
not a stemmer deciding which fact was meant. Covered by
`test_agent_ask_naming_the_object_is_not_claimed`.

**Lost — not a defect, a scoring contract.** `where did i say the scarf is?` was
**silent in the control and graded PASS**. ELECTRIC said
`i don't know, scarf was told but no place was ever told for scarf` and was graded
**FAIL**. The battery's contract is that correct behaviour for this ask is *saying
nothing*; the organism now says something true and is scored as wrong.

This is exactly why the brief says keep the battery as a safety net and do not optimise
for it. **The capability is better than the score and the score is not wrong** — the
grader encodes silence-as-success, which was the right contract for E24 phase 1 and is
the wrong contract for a learner that must admit ignorance. Changing the grader to accept
a spoken admission is a real decision with a real cost (it redefines what "pass" has
meant for 24 generations), so it is **not taken here**. It is recorded as an open
question for you.

**C3 fired and stands: do not turn ELECTRIC on for battery runs.** The flags default off,
so nothing above is the shipped behaviour — generation 24 was an explicit opt-in.

## 7. Files

| file | change |
|---|---|
| `organs/neural_language.py` | `ELECTRIC_TEACH`, `ELECTRIC_ANSWER` (default off), `_taught_says`, `_electric_bind`, `_electric_answer`, one answer hook, two persisted state keys, spoken ignorance |
| `tools/run_generation.py` | `--electric`, both flags stamped on every path |
| `tools/electric_demo.py` | the demo: teach → restart → paraphrase → ignorance |
| `tests/test_electric.py` | 18 tests |
| `tests/test_absence_inventory.py` | two tests amended |
| `docs/evidence/electric_broken.py` | the newly-broken diff that found bug 1 |
| `state/selection/generation_24*.jsonl` | battery regression run (C3 fired) |
