# Answer-formation diagnosis — why supported asks still fail the coverage floor

**Read-only. No core code changed.** Traced from `state/selection/generation_13_asks.jsonl`
(`required`, `coverage`, `nearest`, `reason`) against the gate at
`organs/neural_language.py:3463-3476`. Zero brain builds.

E11a established that the 9 `recall_gate` asks **do** have session-provenanced support —
he was told the coat is wet, the eggs, the frost biting, the bell. This document traces what
happens between having the material and refusing to use it.

---

## 1. The gate is more sophisticated than the diagnosis assumed

Two mechanisms are already present and already correct:

```python
n_mem = max(1, int(self.cortex.binder.X.shape[0]))
wq = {w: float(np.log(1.0 + n_mem / max(1.0, len(self.cortex.binder.stem_rows(w)))))
      for w in must}                                    # :3464  IDF weight per term
tot = sum(wq.values())
for h in hits:
    hs = {stem(t) for t in h["tokens"]}                 # :3471  stemmed memory row
    scored.append((sum(wq[w] for w in must
                       if stem(w) in hs) / tot, h))     # :3472  stemmed both sides
best_cov = scored[0][0]
if best_cov < self.ANSWER_COVERAGE_FLOOR:               # :3476  floor 0.6
```

So: **coverage is stem-matched on both sides**, and **terms are IDF-weighted over the whole
60,000-row binder**. High-frequency question syntax (`does`, `is`, `by`, `of`) gets a *low*
weight; rare content terms (`kettle`, `frost`, `eggs`) get a *high* one. The denominator is
therefore already tilted toward content.

That rules out the two obvious accounts. The defect is not naive string comparison, and it is
not an unweighted denominator inflated by question framing. Both were already fixed.

---

## 2. The trace

`required` is the `must` set; `nearest[0]` is the best-scoring retrieved row.

| ask | cov | `must` | best row | what the dominant term did |
|---|---|---|---|---|
| `what did i tell you about before the kettle?` | 0.555 | about, before, did, **kettle**, tell, you | `did you not tell me about it sooner` | row echoes 4 *low*-weight question words; **`kettle` absent** |
| `what came before the kettle in what i said?` | 0.460 | before, came, in, **kettle**, said | `when the water in the kettle was boiling` | `kettle` present, but only 2 of 5 |
| `how often did i say the coat is wet?` | 0.454 | **coat**, did, is, often, say, **wet** | `tails of my coat were all soaking wet` | both content terms present, 4 syntax terms absent |
| `what number of eggs is left in the basket?` | 0.538 | **basket**, **eggs**, in, is, left, number, of | `there are four eggs in the basket` | **the exact taught fact**, still 0.538 |
| `how often does the bell turn?` | 0.514 | **bell**, does, often, turn | `the copper bell turns twice` | **the exact taught fact**, still 0.514 |
| `what is held by the thing the frost bites?` | 0.510 | bites, by, **frost**, **held**, is, thing | `the frost bites the latch` | taught fact retrieved; `held` ≠ `holds` |
| `what does the bitten thing hold?` | 0.385 | **bitten**, does, hold, thing | `the next thing i laid hold of was` | book row; `bitten` matches nothing |
| `what is bitten by the frost?` | 0.340 | **bitten**, by, **frost**, is | `the frost bites the latch` | taught fact retrieved; **`bitten` ≠ `bite`** |
| `how many times does the bell turn?` | 0.417 | **bell**, does, many, times, turn | `done about the same time as the bell` | book row outranks the taught fact |

The last column is the finding. **In five of nine cases the taught fact is retrieved and is
the top-scoring row — and coverage still lands between 0.34 and 0.54.** Retrieval is not
failing. Candidate generation is not failing. The *accounting* is.

---

## 3. Classification

### Class A — irregular morphology survives `stem()` (3 asks) · **coverage accounting**

`stem()` normalises regular inflection (`turns` → `turn`) but not irregular forms:

- `bitten` → `bitten`, while `bites` → `bite`. **Never match.**
- `held` → `held`, while `holds` → `hold`. **Never match.**

`what is bitten by the frost?` retrieves `the frost bites the latch` — the fact he was taught
— and then loses the term that identifies it. `must` is `[bitten, by, frost, is]`; `bitten`
is rare, so its IDF weight is **high**, and it is unmatchable by construction. The single
term that would prove comprehension is the one term the comparison cannot see.

This is not a stemming bug. It is a **lexical-resource gap**: the organ has no irregular-form
map, and `stem()` was never meant to supply one.

### Class B — the answer cannot contain the question's syntax (all 9) · **coverage accounting**

`must` is built from the question. Every ask carries terms that **no truthful answer row could
ever contain**: `does`, `did`, `is`, `by`, `of`, `often`, `many`, `number`, `left`, `times`,
`say`, `tell`, `you`, `about`, `before`, `came`, `said`, `in`.

IDF weighting *damps* these but does not remove them. They are individually low-weight and
**collectively decisive**: `what number of eggs is left in the basket?` has `must` of 7 terms
against the exact taught fact `there are four eggs in the basket`, and still scores 0.538 —
because `is`, `left`, `number`, `of` are in the denominator and cannot be in the answer.

The structural point: **coverage measures how much of the question's wording appears in the
memory, not how much of the answer's content is supported.** For a well-formed question about
a short fact, the ceiling is arithmetically below 1.0, and for these asks it is below 0.6.
The floor was calibrated against a quantity that has a low maximum.

### Class C — a book row outranks the taught fact (2 asks) · **candidate generation**

`how many times does the bell turn?` ranks `done about the same time as the bell` above
`the copper bell turns twice`. `what does the bitten thing hold?` ranks
`the next thing i laid hold of was` — pure book — as its best row.

Here the weighted-coverage ranking prefers a corpus row that echoes several low-weight
question words over a session row carrying the one high-weight content term. This is the
**same frequency-domination defect E9/E10 found in resonance, reappearing in the coverage
ranking** — and it is the only class here that is a retrieval/ordering problem rather than an
accounting problem.

### Not a class: speakability and bigram/echo constraints

No ask in this set reaches the mouth. `spoken` is False for all 9 and the recorded `reason`
is uniformly *"the closest memory of his covers N% of the question"* — the refusal is issued
at :3476, **before** any echo filter, bigram constraint or speakability check runs. The
`after_echo_filter` / `after_interrogative_filter` / `after_question_filter` fields are
`None` for every one. Those constraints are **not implicated** in this failure class and
should not be touched.

---

## 4. Why this explains E11a's negative

E11a found support high on both sides of the `mouth`/`recall` boundary and concluded the
boundary is not about having the material. This trace says what it *is* about: the material
is retrieved, and then a comparison that includes unanswerable question syntax and
unmatchable irregular forms scores it below a floor calibrated against that inflated
denominator.

It also explains why the floor cannot simply be lowered. The measured coverages are
0.34–0.555 with the **exact taught fact as the top row**. Lowering the floor to admit them
admits everything above it, including the guarded scarf ask at 0.566857 — which is precisely
what generation 2's g2-3 did, losing the invariant at `shape_arbiter`. The floor is not
miscalibrated in isolation; it is calibrated against a numerator that undercounts.

**Fix the numerator and the floor can stay at 0.6.** That is the whole of E12.

---

## 5. E12 — the smallest flag-gated repair

> **`COVERAGE_ANSWERABLE_TERMS`** — default `False`. When on, `must` is restricted to terms
> that could appear in an answer, using **the organ's own question-shape parser word sets**
> at `organs/neural_language.py:2112`, which are already maintained there and are
> deliberately *not* `stemming.STOPWORDS`.

One gene, one site, the construction of `must` before :3464. The floor stays **0.6**. The
IDF weighting stays. `stem()` stays. Nothing downstream is touched.

Why this is the smallest repair that could work, and why it is not a repeat of E10:

- **It targets Class B, which is present in all 9 asks** — the only class that is universal.
  Class A (3 asks) needs a lexical resource the organ does not have; Class C (2 asks) needs a
  ranking change. Class B needs a set the organ **already owns**.
- **It reuses existing organ machinery rather than adding a hand list.** E10 was refuted
  because it introduced a distributional rule that misclassified `is`/`on`. Here the
  interrogative/auxiliary vocabulary is the parser's own — the same set that decides whether
  a question has a shape at all. If a word is question-frame for the parser, it is
  question-frame for coverage. One vocabulary, one owner, no new lexical resource.
- **It raises coverage without moving the threshold.** Removing unanswerable terms from the
  *denominator* raises every score, including the guarded ones — which is exactly why the
  guarded invariant is the primary abort condition rather than an afterthought.

### Predicted effect, computed from the trace

`what number of eggs is left in the basket?`: `must` drops `is`, `left`, `number`, `of` →
`[basket, eggs, in]`, all present in `there are four eggs in the basket` → coverage rises from
**0.538 toward 1.0**. `how often does the bell turn?`: drops `does`, `often` →
`[bell, turn]`, both present in `the copper bell turns twice` (via `stem`) → from **0.514
toward 1.0**. Both cross 0.6 **with the floor unchanged**.

### Abort conditions — checked in this order, none answerable by tuning

| # | condition | why fatal |
|---|---|---|
| B1 | flag-off is not line-for-line identical to generation 13 | the gene is not inert |
| B2 | **any guarded ask's coverage rises to ≥ 0.6, or any guarded pass is lost** | the invariant is the whole point of the guard; a repair that buys 9 asks by spending the scarf invariant is a regression, not a gain |
| B3 | any frozen pass lost | non-negotiable, every generation |
| B4 | any ask gains a `source` without gaining a `pass` | confabulation — the E8 failure mode; a wrong confident answer scores the same as silence on this battery |
| B5 | the parser word sets, applied to `must`, remove a **content** term (`kettle`, `frost`, `eggs`, `bell`, `coat`) | the set is doing E10's job badly; abort rather than curate it |

**B2 is the one that matters and it is checkable before the battery.** The guarded scarf ask
sits at 0.566857, only 0.033 below the floor. Removing unanswerable terms from its
denominator will very likely push it over. If it does, **E12 is refuted at zero cost** and the
floor/guard pair is confirmed to be jointly unmovable — which would close the coverage line
the way E11a closed the comprehension line.

So the smallest E12 is **not** the two-arm battery. It is:

> **E12a — a read-only recomputation.** For all 42 asks in the generation-13 journal, recompute
> coverage from the recorded `required` and `nearest[0]` with the parser word sets removed
> from `must`, using the same IDF formula and the same `stem()`. Report every ask whose
> verdict flips. **Zero builds, no organ change.**
>
> If any guarded ask flips to passing → **stop**, record the refutation, do not write the gene.
> If none do and the 9 recall-gate asks flip → E12b, the flag-gated two-arm battery
> (generations 17/18, 84 builds, ~36 min), with B1–B5 pinned from the journals first.

**Pre-registered now, before E12a runs:** the guarded scarf ask **will** flip, because its
0.566857 is 0.033 below a floor and the repair removes denominator terms from every ask
uniformly. If it does, E12 is refuted and the correct conclusion is that
`ANSWER_COVERAGE_FLOOR` and the guarded invariant are **jointly** unsatisfiable with this
coverage formula — the numerator cannot be fixed without also fixing the guard, and the guard
is load-bearing. That would close the coverage line too, leaving Classes A and C — irregular
morphology and frequency-dominated ranking — as the only untested accounts, both of which
need machinery the organ does not have.

If the scarf ask does **not** flip, the prediction is wrong in the informative direction and
E12b's expected gain must be recomputed from E12a's actual flip list before any build.

---

## 6. Out of scope

Multi-brain and population work (standing constraint). Broad refactors. Adding an
irregular-morphology lexicon (Class A) — a new lexical resource, and E10's lesson is that
new lexical knowledge introduced to fix one measurement tends to be wrong about the binder's
actual composition. Changing the coverage ranking (Class C). Touching `reply_threshold`,
`ANSWER_COVERAGE_FLOOR`, the echo/bigram/speakability constraints (not implicated, §3), or
the recall gate's `must` construction beyond the flag-gated restriction above.
