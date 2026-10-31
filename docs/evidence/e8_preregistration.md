# E8 pre-registration — `POLAR_ABSENCE_MEANS_NO`

**Status: ABORTED at the pre-registered abort condition. The flag was never
implemented and no battery was run.**

Written before any implementation, per the project's standing rule that a
prediction is only worth recording if it was made before the measurement.

---

## 1. The proposal being tested

From `docs/evidence/downstream_repair_proposal.md`. Generation 9's nine
downstream failures include three at `stage=gating`:

| ask | script |
|---|---|
| `does the door hold the frost?` | `hop-and-inventory` |
| `is it true that the door holds the frost?` | `sel-hop-and-inventory` |
| `is the frost held by the door?` | `sel-hop-and-inventory` |

All three are one proposition in three framings and all three want `no`. They
are the only downstream class where a single repair moves the **frozen** score:
projected 19/24 → 20/24 and 0/14 → 2/14 paraphrase probes.

Proposed mechanism: one class attribute `POLAR_ABSENCE_MEANS_NO`, default
`False`, beside `ANSWER_COVERAGE_FLOOR` and `RECALL_UNFILTERED_FALLBACK`,
licensing a negative answer to a closed yes/no question when recall finds no
supporting proposition.

**Pre-registered abort condition, quoted verbatim from the proposal:**

> the negative is licensed by an INVENTORY HE ACTUALLY HOLDS, not by a null
> retrieval, because absence-of-evidence-is-no is sound only where the
> inventory is complete. … If the implementation cannot distinguish a held
> inventory from a null retrieval, the experiment is abandoned rather than
> shipped, since a confident wrong `no` is worse than silence — silence scores
> zero and asserts nothing, while a wrong `no` scores zero and teaches him to
> confabulate.

## 2. What the script actually establishes

`tools/scripts_heldout.json`, script `hop-and-inventory`, kind `order`:

```
say  "the frost bites the latch"
say  "the latch holds the door"
ask  "does the door hold the frost?"   expect answer ["no"], forbid ["yes"]
```

So a legitimate negative is *conceivable*: the taught inventory is two
relations, `bites(frost, latch)` and `holds(latch, door)`, and the question
asks about `holds(door, frost)`, which is not among them. Under a closed world
over a complete two-fact inventory, `no` is correct. The proposal was not
incoherent. It assumed an inventory exists to be closed over.

## 3. The abort check — four measurements

**(a) There is no inventory mechanism in the organ.** Grepping
`organs/neural_language.py` for `inventory`, and for any structured relation
store (`self.relations`, `triples`, `facts`, `roles`, `propositions`, `edges`,
`subj`, `obj`), returns **zero** hits. The script's name `hop-and-inventory` is
a label in the test corpus, not a code mechanism. There is nothing to close a
world over.

**(b) The three asks never reach retrieval.** From the generation-9 journal,
all three rows carry:

```
reason   'it understood but did not feel like speaking'
spoken   False
coverage None
source   None
```

`coverage: None` means the recall gate never executed; `source: None` means no
answer was formed. The refusal is at `organs/neural_language.py:3956-3977`:
`understands = res[best] >= reply_threshold` is **True** and
`wants_to = social_drive >= reply_drive_min` is **False**. This is a **mood**
gate, and it fires *before* any answer path runs.

Consequence: there is no computed negative being suppressed. Emitting `no`
here would not unlock an answer he already reached — it would replace a mood
silence with a fabricated proposition. That is the confabulation the abort
condition exists to prevent, arrived at from the opposite direction than
expected.

**(c) The only memory available is null retrieval.** The binder holds 60,000
rows at capacity, censused at `book` 59,515 (99.19%), `droso` 466, `parent` 19,
with blind FIFO eviction (`organs/higher_cortex.py:399-413`). A query for
door+frost+hold returning nothing from a bag that is 99% unrelated book prose
carries no information about the taught inventory. That is precisely "a null
retrieval", which the condition forbids as a licence.

**(d) The organ already prohibits this, by pre-registration.**
`_ordinal_answer` at `organs/neural_language.py:3042-3055` handles the sibling
case and states the policy in its own docstring:

> Refuses — silence — on fewer than two candidates, more than two, or a tie. It
> never says `no`: **defect B stays closed until a mechanism can express absence
> without asserting a false negative.**

Defect B is "polar questions can't be answered `no`" — the same defect E8
targeted. The organ's author already ruled that `no` is forbidden until such a
mechanism exists. Measurement (a) shows it does not. Shipping E8 would silently
reverse a standing pre-registered decision without new evidence, which is the
same class of error as E7's: naming a mechanism from a field's name instead of
reading its code.

## 4. Verdict

**ABORT.** The implementation cannot distinguish a held inventory from a null
retrieval, because there is no held inventory — only a prose binder whose
emptiness is uninformative — and because the asks are refused on mood grounds
before any retrieval occurs. The condition is triggered, so per its own terms
the experiment is abandoned rather than shipped.

No flag was added. No arm B exists. **The two-arm battery was not run**, and
deliberately so: with no code change, arm A and arm B would both be generation
9/10 reproduced ask for ask, and spending ~36 minutes and ~84 builds to
re-measure a known-identical result is not a measurement. Frozen, probe and
guarded scores are therefore **unchanged by construction** — 19/24, 0/14, 4/4 —
and zero erosion is trivially satisfied because no state was written.

This is the second consecutive proposal to fail its own pre-registration
(E7's P2 was falsified; E8 aborts). Both were caught by the pre-registration
rather than by the score, which is the intended function of the practice.

## 5. What would satisfy the condition — E8', not shipped

Recorded so the abort is a redirection and not a dead end. A sound negative
needs a **session-scoped closed-world relation inventory**, and the organ
already contains the scoping primitive: `_ordinal_answer` restricts itself to
this session's `who == "you"` binder rows via `session_t0`
(`organs/neural_language.py:3070-3080`). E8' would:

1. Build the inventory from **this session's** `who == "you"` rows only — the
   tells, not the corpus. For `hop-and-inventory` these are exactly the two
   framed sentences above.
2. Parse each into `(subject, verb, object)` using the frame the organ was
   taught with, `"the {a} {v} the {b}"`. This is feasible here and is **not**
   contradicted by the earlier finding that role harvesting fails: that failure
   was harvesting from the whole binder's 8-token prose fragments, which
   produce ungrammatical pools. Freshly-taught tells are in the taught frame.
3. Answer `no` to `does A V B?` / `is B V by A?` / `is it true that A V B?`
   **only when all three hold**: the session inventory is non-empty; it contains
   at least one relation whose verb is `V`; and `(A, V, B)` is absent from it in
   both directions. Otherwise refuse — silence.

Clause 3 is the whole point. A non-empty inventory containing the queried verb
is a *held* inventory; an empty one, or one with no `V` relation, is null
retrieval and must produce silence, never `no`. That is the distinction E8
could not make.

Two obstacles keep E8' out of scope for this pass, both standing constraints
rather than difficulties:

- It requires overriding the **mood gate**, since the asks are refused at
  `:3956-3977` before any answer path. That is a change to the reply-decision
  path, not an additive answer path like R1/R1'/R2 or E7.
- It requires passive normalisation (`is the frost held by the door?` →
  `holds(door, frost)`). R2's `SHAPE_ALLOW_PASSIVE` exists but was measured
  **inert** in E5, so it cannot be assumed to work here.

E8' is therefore future work with a pre-registered design, not a proposal to
ship. If it is built, it must be built as its own experiment with its own
abort condition, and the first thing it must prove is that clause 3 refuses
rather than confabulates when the session inventory is empty.

## 6. Tests

`tests/test_e8_abort.py` pins the abort so it cannot silently regress:

- the organ has **no** `POLAR_ABSENCE_MEANS_NO` attribute;
- `_ordinal_answer`'s pre-registered prohibition is still in its docstring, so
  reversing it requires an explicit edit rather than drifting;
- in the generation-9 and generation-10 journals, all three polar asks are
  `spoken: False` with `coverage: None` and `source: None` — the measured basis
  of clause (b);
- `cause_of` classifies that reason as `gating` — not `comprehension` and not
  `recall_gate` — so the mood refusal stays distinguishable from the two defects
  it was previously conflated with. It is `gating` rather than a new name
  because `cause_of` only reclassifies out of `recall` and passes every other
  stage through unchanged (P5 of the `cause` pre-registration).
