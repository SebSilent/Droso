# Architecture decision review — what the seven closed lines actually say

**Decision document. No core code changed. No multi-brain work. No broad refactor.**

Seven repair lines have been tested and closed, all at the same boundary. This review asks what
they jointly imply and recommends one path forward.

---

## 1. The seven negatives, and the one thing they share

| line | mechanism tried | refuted because |
|---|---|---|
| E9, E10 | resonance ranking (session scope, content scope) | signal is not ask-dependent; no scope makes it so |
| E11a | comprehension signalling (provenanced term support) | ask-dependent and frequency-independent as designed, still cannot separate the classes |
| E12a | coverage numerator (answerable terms only) | lifts the guarded ask 0.5797 → 0.6676; non-monotone; buys 2 of 9 |
| gen 2, gen 6 | coverage threshold | the window between 0.555 and 0.570 is empty |
| E13a | coverage ranking (provenance tie-break) | inert — the taught row is already top wherever present |
| E14a | candidate generation (admit session rows) | safe but worthless — ceiling 0.5488 against a 0.6 floor |
| E15 | provenanced entailment licensing | licenses the guarded ask on another subject's row; 4 of 5 licences confidently wrong |

**Every one of them is a read-time inference over unstructured prose rows.** The binder stores
8-token fragments tagged with `who`, `when`, `count` — no subject, no relation, no object. So
each mechanism had to *reconstruct* structure at query time from word overlap, and each
reconstruction failed in the same two directions:

- **over-matching** — E15 licensed a scarf question from `the coat is on the hook`; E9/E10's
  resonance was won by corpus attractors and then by `the`;
- **under-scoring** — E12a/E14a's coverage denominator counts question syntax no answer row can
  contain, capping a correct single-row match at 0.5488.

Neither is a tuning problem. Both follow from asking a bag of prose fragments to behave like a
structured memory at the moment of answering.

## 2. The guarded invariant is validated, not suspect

Six of the seven were killed by **one** ask: `where did i say the scarf is?`, which passes *by
refusing*. It is reasonable to ask whether a single invariant should veto six repairs.

E15 settles it. The mechanism that broke the invariant did so by licensing an answer from a
locative row about the **coat**, with filler `'the'`, and by licensing four other
confidently-wrong answers (`what bites the latch?` → `latch`; `how many eggs broke?` → `four`
from a row saying eggs are *in the basket*). The invariant caught real confabulation every time.

**The guard is not an obstacle to the repair. It is the repair working.** Any path forward that
treats it as something to route around is misreading seven measurements.

## 3. The three candidate paths

### (a) A broader evaluation battery — **necessary, not sufficient, and not first**

All seven negatives were measured on one 42-ask battery whose 18 probes reword a small fact set
(E14a: failure counts overstate distinct defects — the 3 `gating` failures are one proposition).
A broader battery would tell us whether the 19/24 ceiling is a property of the agent or of the
instrument.

But the ceiling has held across **ten generations and seven mechanisms**, and the guard has been
independently validated. The evidence that the ceiling is real is already strong. Widening the
battery first would spend effort confirming what seven negatives agree on, and would not unblock
anything.

**Kept as a prerequisite for E16b, not as the path.** A new primitive must be validated on more
than the battery that motivated it — otherwise it is fitted to 42 asks, which is E10's error at
battery scale.

### (b) A minimal new organ primitive — **recommended**

Specifically: **write-time structure, not read-time inference.**

At *teach* time the tell is in a known frame (`the {a} {v} the {b}`), so subject, relation and
object are unambiguous — there is nothing to infer. A small additive relation index written then
would make query-time reconstruction unnecessary, and it addresses all three remaining gaps at
once:

- **subject binding** — the axis E15 lacked and E11a lacked before it. A relation index keys on
  the subject, so `where … the scarf` cannot match a row about the coat.
- **composition** — `what does the bitten thing hold?` needs `frost bites latch` + `latch holds
  door`. Two indexed relations joined on a shared entity is a lookup, not a search over 60,000
  prose rows. E14a measured this ask at 0.2220 because no single row can cover a two-hop
  question.
- **Class A morphology** — `bitten`/`bites` can be normalised **once, at write time, against the
  frame the tell actually used**, rather than guessed from a corpus that is 99.19% book prose.
  E10's Finding 1 was that document frequency measures corpus style, not lexical class; a
  write-time normalisation is not exposed to that skew.

It also **unblocks E8**, which was aborted for want of exactly this: E8's condition was that a
negative answer be licensed by "an inventory the organism actually holds", and the abort fired
because no inventory existed. A relation index *is* that inventory.

Why this is not a broad refactor: it is an **additive store beside the binder**, flag-gated,
default off. The binder, the coverage gate, `stem()`, the IDF weights, `reply_threshold` and the
shape parser are all untouched. The organ already holds several parallel indices
(`word_patterns`, `bigram_counts`, the SAN); one more is the established pattern, not a new
architecture.

### (c) A controlled architectural change — **not yet**

Candidates would be §7b value-weighted eviction (E3 observed blind FIFO evicting a `droso` row at
count 4561) or a separate episodic store. Both are real and both are larger. §7b matters for a
**long-lived** learner — a relation index would be evicted by the same blind FIFO — but it does
not address the boundary that seven experiments located, and doing it first would optimise
retention of a representation that does not yet exist.

**Sequenced after (b), and flagged as a dependency:** if E16 shows a relation index works in a
scratch session, §7b becomes the prerequisite for it surviving beyond one session.

## 4. Recommendation

**Path (b): a minimal write-time relation primitive, validated offline first.**

Not because it is likely to succeed — seven predecessors failed — but because it is the only path
that changes the *representation* rather than the *inference over it*, and every one of the seven
failed on inference.

## 5. E16a — the smallest first experiment

**A zero-build, read-only feasibility probe over `tools/scripts_heldout.json` alone.** No organ
code, no binder, no brain, no gene.

The tells and the `expect` blocks are already on disk. E16a implements a frame-based relation
extractor as a **standalone function in the evidence script** and asks one question:

> If every tell were indexed as `(subject, relation, object)` at write time, would a role query
> over that index produce the expected answer for **all 42 asks** — and **refuse** every ask that
> is supposed to refuse?

Reported per ask: extracted relations, the queried role, the licensed filler, the expected
answer, and whether it matches. Plus the two-hop asks, evaluated as a join on a shared entity.

**This is the whole experiment.** It costs seconds. If the index cannot answer the battery
offline, no organ primitive will answer it online, and nothing is built.

### Tests, written before the extractor

1. **Frame extraction is total over the tells** — every tell in every script yields exactly one
   relation, or is explicitly reported as unextractable. Silent drops are the E11a loader bug
   and the E15 subject bug in one.
2. **Subject binding** — a query about the scarf returns no relation whose subject is the coat.
   This is E15's exact failure, pinned as a unit test.
3. **Composition is bounded** — a two-hop join uses exactly two relations sharing exactly one
   entity; three-hop and unshared joins refuse.
4. **Morphology is normalised at write time** — `bitten` and `bites` index to the same relation,
   and the normalisation is derived from the frame, not from a lexicon.
5. **Refusal is the default** — a query with no matching relation returns *no licence*, never a
   low-confidence guess. Silence, not babble.
6. **No hand-written word list** — C5 from E15, carried forward: the role query comes from the
   organ's own shape parser, and the frame from the tell's own surface form.
7. **Additivity** — the probe touches no organ state; asserted by construction and by a test that
   the organ module is unmodified.

### Abort conditions

| # | condition | consequence |
|---|---|---|
| D1 | any guarded ask is licensed | **abort** — the invariant that killed six repairs is non-negotiable |
| D2 | any ask licensed with a wrong filler | **abort** — confabulation, E8/E15's mode |
| D3 | fewer than the 9 recall-gate asks licensed | **abort** — no gain over the status quo; inert like E9/E13a |
| D4 | extraction requires a hand-written lexicon or a rule fitted to a specific ask | **abort** — E10's error |
| D5 | any tell is unextractable and the affected asks are not reported | **abort** — silent partial coverage |
| D6 | the two-hop ask is licensed only by relaxing the join bound | **abort** — unbounded composition is a search over prose again |

**Pre-registered expectation.** D1 will **not** fire: a relation index keyed on subject has no row
whose subject is the scarf and whose relation is locative, because the tells are `the scarf is
wet` (property) and the coat's locative row is keyed on the coat. This is the structural version
of the guard that E15 only claimed to have. D3 is the real risk — the recall-gate asks include
quantity and frequency questions (`how many eggs`, `how often does the bell turn`) whose answers
are numerals and adverbials, not `(s,r,o)` triples, and a relation index may not represent them at
all. **If D3 fires, the honest conclusion is that the battery's failing asks are predominantly
quantity/frequency questions, which need a counting primitive rather than a relational one** — a
different and narrower design, and a cheaper one.

That is a genuinely informative fork, and E16a resolves it in seconds.

### If E16a passes

E16b is the flag-gated organ primitive: one gene `RELATION_INDEX`, default off, an additive index
written at teach time, and a licensing path consulted **only inside the existing
`best_cov < ANSWER_COVERAGE_FLOOR` branch** — the same minimal-blast-radius placement E15's design
used, so it can only add licences and the coverage gate still refuses first. Two-arm battery,
generations 19/20, ~36 min, with predictions recomputed from E16a's actual licence list rather
than from this document.

**E16b requires a broader battery first** (path (a), as a prerequisite): a primitive validated on
the 42 asks that motivated it is fitted to them. The battery must be extended before E16b, not
after.

## 6. Out of scope

Multi-brain and population work (standing constraint). Broad refactors. Removing or retuning
`ANSWER_COVERAGE_FLOOR`, the IDF weights, `stem()`, `reply_threshold`, or the echo/bigram/
speakability constraints. §7b value-weighted eviction — sequenced after E16 and flagged as a
dependency for any index that must survive beyond one session. Any hand-written morphological or
stopword lexicon.
