# MP-E9 precondition: the `organs/` design step B.2 depends on

**Status:** REGISTERED PRECONDITION, written before any `organs/` edit. Authorised by PI instruction
2026-11-03 ("write it as its own registered design document … seal it, and only then implement behind
that flag"). MP-E9 B.2 steps 1–2 are blocked until this document is committed and sealed; steps 3–6 are
blocked until the flags it names exist and their A/B tests pass.

**Why this exists at all.** B.2 step 1 is "restore the arbiter-tell bound at the leak" and step 2 is
"implement morphology normalization on both sides of the QA store behind a flag". Both the leak and the
store live in the answer path of `organs/neural_language.py`. There is no version of MP-E9 that passes
H1/H2/H3 without editing that file, and the standing instruction says `organs/` is not touched without a
registered design step. So the step is registered here rather than the gate quietly failing later, and
rather than the edit happening in the same breath as the result it is meant to produce.

---

## 1. Site 1 — the says leak, and why the existing bound does not stop it

### What is observed

Sixteen rows in the frozen pre-treatment evidence speak the single word `says`, which is in none of the
27 told sentences, in none of the asks, and in neither the row it is drawn from nor any book line the
house heard. `tools/word_provenance.py` grades them `UNTRACEABLE_ASSERTED` — the class C1 aborts on.

They are not scattered. Every one is:

| field | value |
|---|---|
| `src` | `arbiter head` |
| `cls` | `partial` |
| `said` | `says` (one word, nothing else) |
| `ask` | one of exactly three: `what the nora carry`, `what the dog guard`, `what the bridge cross` |
| positions | `learn/d1/live[11]`, `d1/reasked[11]`, `d1/restarted[11]`, `d2/live[11]`, `d2/reasked[11]`, `d2/reasked[32]`, `d2/restarted[11]`, `d2/restarted[32]`, `d3/live[11]`, `d3/live[67]`, `d3/reasked[11]`, `d3/reasked[32]`, `d3/reasked[67]`, `d3/restarted[11]`, `d3/restarted[32]`, `d3/restarted[67]` |

Three asks, sixteen positions, one word. This is `docs/STATE.md:2449`'s caveat arriving in the grader:
*"3 ungrammatical asks that used to refuse with `nothing he remembers has that shape` now reach this
branch and answer `says`"*. The bench's sentence-level `invented` grader cannot see it, because it grades
sentences and this is a word — which is the entire reason G0-prime built the word-level grader.

### The mechanism, at line level

1. `organs/neural_language.py:933-952` — `_note_spoken`. When the house speaks two or more words, it
   records the act: `self.experience("droso", "says", " ".join(ws))`.
2. `organs/neural_language.py:1780` — `experience()` binds that row with `who = "droso"` and the token
   list `["droso", "says", …]`. So `says` enters his memory as a content word of a row about himself.
3. `organs/neural_language.py:5194-5203` — the shape arbiter runs. For these three ungrammatical asks it
   does **not** return `best is None`: it finds the self-echo row and names a filler. So the honest
   refusal at `:5200` (`"nothing he remembers has that shape"`) is never reached.
4. `organs/neural_language.py:5256-5261` — the branch. `ELECTRIC_ARBITER_TELL` asks `_arbiter_tell(best,
   sf, q)` whether the whole row may be spoken. It correctly refuses (the row adds words the ask did not
   name). **And then the `else` speaks `sf` anyway, unconditionally, under `arbiter head`.**

That is the leak: `_arbiter_tell` (`:3947-3986`) bounds the *sentence* path, and the *one-word* path
carries no bound at all. The bound was written around the branch that was considered dangerous, and the
word that escapes comes out of the branch that was considered safe because it predates the flag.

### The fix, and the bound it must be

Apply to the head path the same facts `_arbiter_tell` already asserts about `best`, as one predicate:

- `who == "you"` — the row was said **to** him. A self-echo binds `who == "droso"` and fails here, which
  is the whole correction: he must not re-issue his own prior utterance as a memory of what someone told
  him.
- `_hit_is_ask(best)` false — the row is not itself an asking.
- the filler is a word of the row.
- every content word of the row is either the filler or a word of the ask.

When the predicate fails, the ask takes the **existing** refusal at `:5199-5203` — same string, same
`verdict: veto` — rather than a new one. The three asks return to honest refusal with a reason the record
already contains.

### What this must NOT change

| invariant | value today | requirement |
|---|---|---|
| `arbiter tell` rows | **36**, all `partial → correct`, all in `learn` | survive **row for row**, same positions, same `said`. The bound is added to the head path, not the tell path. |
| guarded-absence rows | **24** | unchanged in count, ask, `cls` and wording. The scarf/kettle refusals must not gain a filler. |
| `UNTRACEABLE_HEARD` rows | 6 (`which` ×3, `why` ×3) | out of scope here. They are a probe-leak, ruled non-aborting by D-G0P-03. A fix that also removes them is a red flag: it means the change reached further than the bound. |
| told sentences | 27 | untouched. |
| class vocabulary | the 9 `CLS` values at `tools/electric_learn_bench.py:633` | no new class, no redefinition. |
| refusal strings | `nothing he remembers has that shape`, `the only thing that matched was the asking itself` | reused verbatim, not reworded. |
| control arm | flags off | byte-identical behaviour. |
| `SHAPE_FUNCTION_WORDS`, `organs/stemming.py` | as is | **not edited.** The bound consumes them. |

## 2. Site 2 — morphology on both sides of the QA store

### The mechanism

The pair taught is `("when does the bell toll?", "it tolls at dusk")`
(`tools/electric_learn_bench.py:167`). The store keys on exact characters:

- write: `organs/neural_language.py:3400` — `key = self.qa_key(q)`
- read: `:3529` and `:5800` — `self.qa_store.get(self.qa_key(raw))`

`qa_key` (`:3209-3219`) lowercases and splits. It does **not** stem. Only `qa_paraphrase_key`
(`:3222-3244`) stems, and it is reachable only through `ELECTRIC_QA_PARAPHRASE` on the paraphrase path.
Measured with the project's own stemmer:

```
stem("toll")=toll  stem("tolls")=toll  stem("tolling")=toll  stem("tolled")=toll
stem("rings")=ring  stem("carries")=carry  stem("crosses")=cross  stem("bites")=bite
stem("says")=says   stem("said")=said          <-- irregular: NOT folded
qa_key("when does the bell toll")        = "when does the bell toll"
qa_paraphrase_key("when does the bell toll") = "when time bell toll"
```

So `toll`/`tolls` is a fold the machinery already performs, on a path the store does not use. The bench
registers 54 rows touching `toll` with **0 correct** — the whole class fails on morphology, not on
memory.

### The fix

A store key function that both sides call, composing the pieces that already exist rather than inventing
a fourth splitter:

```
qa_store_key(x) = qa_paraphrase_key(qa_key(x))   # when the flag is ON
qa_store_key(x) = qa_key(x)                      # when OFF -- exactly today's behaviour
```

Applied at all three sites (`:3400`, `:3529`, `:5800`) plus the restore path (`:6568`), so write and read
cannot disagree. `qa_key` itself is **not** modified: its docstring records that it must stay the same
split `_load_next_book` uses for a book line, or the store answers nothing and looks identical to an
empty one.

### The persistence problem, stated before it is hit

`qa_store` survives restart (`:6368` persist, `:6568` restore). If the key form changes, a store written
before the flag is keyed differently from the one the flag reads, and the symptom is silence — the worst
symptom this repo has, because it is indistinguishable from an empty memory. Two rules follow, and both
are testable:

1. **Keys are recomputed, never trusted.** Restore re-derives `qa_store_key` from the stored `q` tokens
   rather than reusing the stored key, so one house behaves identically before and after a restart.
2. **No half-flag.** The flag is read once per call site and the same predicate governs write, read and
   restore; a store written under one key form is never read under the other.

### What this must NOT change

`stem()` is not edited and no new stemmer is added. The fold must not merge two *different* questions:
word order is kept, per `qa_paraphrase_key`'s own docstring, and `who droso carries` must stay distinct
from `who carries droso`. Under-folding refuses, over-folding gets believed, and this path gets
believed — so the recovery prediction is registered narrowly as the **toll/tolls class only**, and every
other ask that refuses today must still refuse.

## 3. The two flags

| | flag 1 | flag 2 |
|---|---|---|
| attribute | `ELECTRIC_ARBITER_HEAD_BOUND` | `ELECTRIC_QA_MORPH_NORMALIZE` |
| CLI | `--electric-arbiter-head-bound` | `--electric-qa-morph-normalize` |
| default | `False` | `False` |
| read at | `organs/neural_language.py:5256-5261` (the head branch's `else`) | `:3400`, `:3529`, `:5800`, `:6568` |
| registered in | `tools/electric_teach_mode.py` `BASE` tuple, so the bench wires it in the order `serve.py` uses | same |
| parent | none — it sits inside the branch the shape arbiter already gates, like `ELECTRIC_ARBITER_TELL` | `ELECTRIC_QA_STORE`; without it there is no store to key |
| inert-when-parent-off | n/a | must be reported in `DEPENDS_ON`, in the same words at every wiring site |
| off-behaviour | identical to HEAD, byte for byte, verified by A/B in one tree | identical to HEAD, including the toll refusal |

Both are added to `BASE` rather than `STACK` so the `learn` arm gets them and `control` does not: the
arms differ by exactly the flags, which is what makes the comparison mean anything.

## 4. How the time-dependence in G0-prime decision.md §4 interacts with a flag-gated path

This is the part that would have been missed without the noise-floor measurement, so it is recorded as a
design constraint rather than a footnote.

`_note_spoken` is gated on wall-clock: `organs/neural_language.py:946-948` reads `time.time()` and binds
the speech-act row only when **≥ 2.0 s** have passed since the last one. `_refractory` (`:956-971`) is
likewise time-since-dependent. That is the mechanism G0-prime §4 measured: 11 of 3,672 rows move between
three identical clones, all of them in `learn/d1/reasked` and `learn/d1/restarted`, and the one graded
difference is the says frame appearing and vanishing.

Three consequences for this design:

1. **The pre-flag count of 16 is itself a time-dependent number.** Whether a self-echo row exists when an
   ask arrives depends on the 2-second gate. So "16 says rows" is a measurement of one run, not a
   property of the code, and the fix must not be validated by the arithmetic `16 → 0`. It must be
   validated by the **predicate**: no row with `who != "you"` may reach the mouth as an answer, at any
   timing. A bound that happens to zero today's 16 is not the same thing as a bound that is
   time-independent, and only the second one is worth registering.
2. **The flag changes what is spoken, therefore what is echoed, therefore what exists to be echoed.**
   Speaking a whole row instead of a word changes `_note_spoken`'s input, which changes the rows the next
   ask can find. `docs/STATE.md:2452-2455` already records this feedback in the same branch ("seven
   whole answers re-route a later ask this bound refuses"). The bench asks probes in order against one
   house, so this is not hypothetical. Consequence: the post-flag run must be compared to the re-derived
   pre-flag snapshot **positionally**, row by row, and any movement must be attributed to a named cause —
   never averaged.
3. **The flag-gated path must not read the clock.** Neither `_arbiter_head_ok` nor `qa_store_key` may
   consult `time.time()`, `world_clock` or `_spoken_times`. This is checkable by inspection and is
   asserted by a test that fails if the new functions read a time source. It is the one part of this
   design that makes the new behaviour reproducible rather than merely measured — and it is the reason
   R13(b), the injectable clock, stays scheduled rather than being smuggled in here as a convenience.

The noise-floor exclusion from D-G0P-02 (`learn/1/reasked`, `learn/1/restarted`) still applies to the
post-flag run. If those two cells move after the fix, that is **expected** and must be reported as
movement in an excluded cell, not as a clean result and not as a regression.

## 5. Verification, in the order it must happen

1. **A/B with the flag OFF reproduces HEAD byte for byte** on the graded fields, in one tree. Off means
   off, not "off and slightly different".
2. **Flag ON: the three asks refuse** with `nothing he remembers has that shape`, at every depth and
   phase where they currently speak `says`.
3. **Flag ON: the 36 `arbiter tell` rows survive row for row**, and the 24 guarded-absence rows survive.
   Asserted from the run, not from a comment.
4. **The pinned refusal test is replaced by a registered recovery prediction** for the `toll/tolls`
   class, and new tests pin **both** admission (the fold that must answer) and refusal (the folds that
   must not). B.2 step 2 requires all three; a test that only checks the recovery is how an
   over-folding normalizer gets believed.
5. **The word grader runs live on every row of the post-flag run** (`tools/word_provenance.py`), and C1
   is re-evaluated against the registered threshold of 16.
6. **`tools/mp_e9_gate.py` scores H1–H4 and C1–C3** on that run, reading its thresholds from
   `registration.json` — the harness that judges the treatment must be sealed *before* the treatment,
   which is why it exists now.
7. Nothing in `registration.json` changes after results exist (R2). Amendments before results are
   recorded in `registration_amendments` with `results_existed: false`.

## 6. Explicitly out of scope

- **R13(b), the injectable clock.** Correct long-term fix, needs its own design step, must not arrive
  here as a side effect.
- **Tier 120 and tier 300.** `SESSIONS`/`PAIRS` are literal lists; scaling is real work. Tier 40 only.
- **MP-E8 arms B/C.** Need a from-scratch 2–10M harness plus abstention. Not a download, not this file.
- **The `heard_not_told` rows.** Ruled non-aborting by D-G0P-03; fixing them means changing the probe
  set, which changes what the benchmark asks, which is a different decision.
- **`requirements.txt` pinning.** Still open.
