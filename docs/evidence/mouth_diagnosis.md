# The `mouth` class: resonance over an unscoped 11,439-word pool

Diagnosis of the four `stage: mouth` failures reported identically by generations 9 and
10. Read-only: `docs/evidence/mouth_probe.py` → `docs/evidence/mouth_probe.json`, four
fresh builds in `SCRATCH`, live learner state untouched, **no core answer-path code
changed**.

## Verdict

**Resonance.** Not retrieval, not arbitration, not rendering — though rendering is a
secondary aggravator in 2 of the 4 cases.

The wanted word is *present* in the candidate pool in all four cases, so nothing was
failed to retrieve. It loses the resonance contest by a factor of ~3.8× to a word whose
identity barely depends on the question. `max()` then reports that winner with confidence
because it clears `reply_threshold` by 0.02–0.03.

## The mechanism, from the code

`organs/neural_language.py:3945-3955`:

```python
exclude = ({user_text.strip().lower()} if " " not in user_text.strip() else set())
mates   = [m for m, r in self.word_patterns.items()
           if self._speakable(m) and m not in exclude]
res     = {m: self._resonance(m, act) for m in mates}
best    = max(mates, key=lambda m: res[m])
understands = res[best] >= self.reply_threshold
```

Three properties of this path decide everything below.

1. **`mates` is the entire taught vocabulary, unscoped.** `word_patterns` holds **11,439**
   words — essentially the whole book corpus, accumulated by `_teach_key` over the
   organism's lifetime. Nothing restricts it to the session, to the tells just heard, or
   to anything relevant. The probe measured `vocabulary: 11439` on all four builds.
2. **`_resonance` is a cosine, so it is norm-blind but not prior-blind** (`:613-624`):
   `dot(wv/‖wv‖, av/‖av‖)` over the word cells only. It is a genuine semantic match, not a
   frequency lookup. But `act` is the *whole* semantic state, which after three short tells
   is still dominated by the corpus prior.
3. **The utterance is ONE word.** `_speakable` (`:1841-1851`) requires `len(s) >= 2 and
   s.isalpha() and " " not in s`, so a multi-word answer can never be `best`. It can only
   become two words via the bigram extension (`:3984-3994`, gated on
   `phrase_threshold = 6`) or be replaced wholesale by the `speak_sentence` chain
   (`:3998-4004`, which appends `" + chain"` to `source`).

## The measurements

| ask | wanted | said | source | wanted rank / 11439 | wanted score | winner score |
|---|---|---|---|---|---|---|
| `name the wet thing that is not on the hook` | scarf | `worked rigging` | resonance **+ chain** | **10999** | 0.1508 | 0.5738 (`agin`) |
| `which of them is wet and is not on the hook?` | scarf | `numbered` | resonance | **10993** | 0.1600 | 0.5811 (`numbered`) |
| `repeat after me the copper bell turns twice` | copper bell turns twice | `sold` | resonance | **11187–11228** | 0.1134–0.1221 | 0.5722 (`sold`) |
| `which thing did i mention earlier than the kettle?` | lantern | `compile leagues` | resonance **+ chain** | **1008** | 0.4131 | 0.5730 (`sold`) |

`reply_threshold = 0.55` on all four. `wanted_in_vocabulary` is **true for every wanted
word in every case** — including all four words of the echo phrase.

**Provenance of the `said` column.** The generation 9/10 journals record `stage`, `cause`,
`source`, `coverage` and `pass` for these rows but store **`utterance: null`** — the harness
never persisted what he actually said. Every babble string quoted in this document
(`worked rigging`, `numbered`, `sold`, `compile leagues`, and the resonance rankings behind
them) comes from `docs/evidence/mouth_probe.json`, i.e. from re-running the four asks on
fresh builds, not from the journal. The journal is cited only for what it does hold, which
was verified directly: all four rows are `tier: probe`, `stage: mouth`, `cause: mouth`,
`pass: false`, `coverage: null`, with `source` `meaning resonance` on three and
`meaning resonance + chain` on the fourth. That the probe reproduces the same four asks,
the same `source` strings and the same chain/no-chain split is the check that the two
records agree; the exact words are the probe's alone and would not be expected to repeat
verbatim on a rebuild, since `_decide_impl` samples stochastically.

### The winner does not depend on the question

This is the decisive result. Four asks with different content, different scripts,
different tells:

| ask | top resonance |
|---|---|
| 1 | 0.5738 |
| 2 | 0.5811 |
| 3 | 0.5722 |
| 4 | 0.5730 |

Range **0.009**. And the *identities* repeat: `numbered` is top-5 in **4 of 4**, `sold` in
**3 of 4**, `agin` in 2 of 4, `tears`/`composed`/`unconsciousness` recurring. A resonance
that tracked meaning would move with the question. This one is a **static attractor** —
a small set of high-frequency book words whose `understand(word)` vector has a high baseline
cosine with almost any `act` the corpus-trained organism produces.

So `max()` over 11,439 candidates is not selecting the answer; it is selecting whichever
attractor word happens to sit highest, and `res[best] >= 0.55` then certifies it as
"understood". The threshold is not discriminating anything — it is sitting *inside* the
attractor band.

### The organ has already recorded this failure mode, on a different path

`_provenance_vote`'s docstring (`:2340-2350`) justifies itself by listing what similarity
has already cost, and one entry is this defect measured independently:

> "both similarity bets on this axis are already measured bad (band-hop's overlap: 0/8, then
> 6/8 shape vetoes; **meaning cosine: 8/8 -> 7/8, where a corpus unicorn line out-meaned the
> true tell**)."

"A corpus unicorn line out-meaned the true tell" is precisely what the probe measured here —
corpus content out-resonating the session's own facts — observed on the recall shortlist
rather than the mouth, and bad enough that a provenance-only ranking was written to avoid
it. That is corroboration from inside the organ's own record, not a new claim: **meaning
cosine over an unscoped corpus pool is a known-bad selector in this codebase**, and the
`mouth` class is the same bet placed on the output side where no provenance correction was
ever applied. It also explains why the recall side has a `_provenance_vote` and the
resonance side has nothing.

### No threshold can repair this

The window is empty, structurally identical to the recall-gate finding:

- winner band: **0.550 – 0.581**
- best wanted word: **0.4131** (`lantern`), worst **0.1134** (`turns`)

Raising `reply_threshold` above 0.581 silences all four — converting babble into refusal,
which scores the same 0 and at least asserts nothing false, but wins nothing. Lowering it
admits more attractors. There is no value that admits `scarf` at 0.1508 while excluding
`numbered` at 0.5811. **The defect is the ranking, not the cut.**

### The tells did move resonance — just not enough

`lantern` at rank 1008 / 0.4131 is ~2.7× the score of `scarf` at 0.1508, and `lantern` is
the one wanted word that appears in its script's tells. So session content *is* reaching
`act` and *is* lifting the right word. It lifts it from the bottom of the pool to the top
9%, and the attractor still wins. The signal is present and roughly 4× too weak relative to
a pool 11,439 wide.

### Rendering is a real but secondary defect

`emitted_is_argmax` is **false** in 2 of 4: the chain replaced the resonance winner
entirely, producing `worked rigging` and `compile leagues` — neither word is the argmax
(`agin`, `sold`). So in those cases the final utterance is not even the resonance decision;
`speak_sentence` ran its own process over a 6-word budget. That is a second, independent
way this path emits corpus-shaped text.

It is secondary because the other 2 cases emitted the bare argmax with no chain and were
equally wrong. Fixing rendering alone would change `worked rigging` into `agin`, not into
`scarf`.

The echo case is **not fixable by resonance at all**: `copper bell turns twice` is four
words, `_speakable` forbids spaces, the bigram yields at most two, so no ranking outcome can
produce the wanted string. That ask needs the echo path (`_echo_instruction`, `:3927`), not
a better `max()`. It should be excluded from E9's target set and counted as a rendering
defect separately.

## Why the other three classifications are ruled out

| class | ruled out because |
|---|---|
| **retrieval** | every wanted word is in `word_patterns` (`wanted_in_vocabulary` all true). The pool contained the answer; retrieval is not the failure. The pool being 11,439 wide *is* a scoping failure, but that is a property of the resonance candidate set, not of recall — and note `coverage: null` on these rows in the journal, i.e. the recall gate never ran |
| **arbitration** | `source` is `meaning resonance`, never `recalled proposition`; the shape arbiter is not on this path. Gen 9/10 keep `shape_arbiter` as a separate 2-ask class |
| **rendering** | real in 2 of 4 (chain override) but the 2 bare-argmax cases are equally wrong, so rendering is not the primary cause |
| **resonance** | **the defect**: an unscoped 11,439-word pool where a static corpus attractor band (0.550–0.581) sits above `reply_threshold` (0.55) and ~3.8× above the session-relevant word |

## Smallest flag-gated repair: scope the candidate pool

Not a threshold, not a reweighting, not a new answer path. **Restrict `mates` to words
attributable to this session**, leaving everything else byte-identical.

The scoping primitive already exists and is already trusted in this organ:
`_ordinal_answer` restricts itself to this session's `who == "you"` rows via `session_t0`
(`:3070-3080`). `session_t0` is set once in `__init__` (`:114`) and read at twelve sites, so
it is an established idiom rather than something E9 would invent. E9 reuses that notion for
the resonance candidate set.

**Scope guard — do not reuse `_provenance_vote`.** The ready-made session mask
(`who == "you"` and `when >= session_t0`) lives in `_provenance_vote` (`:2340`), but that is
a **Brain B** method, gated on `DROSO_SECOND_BRAIN` (`:2337-2338`). Multi-brain work is out
of scope for this task and E9 must not touch it, must not enable that env var, and must not
call into it. E9 filters `mates` using `session_t0` directly, the way `_ordinal_answer`
does. The two are conceptually the same bit and that is fine — the point is that E9 stays on
the single-brain side of the line, and a reviewer should treat any `_provenance_vote` or
`DROSO_SECOND_BRAIN` reference in the E9 diff as a scope violation.

```
RESONANCE_SESSION_SCOPE = False        # class attribute beside
                                       # ANSWER_COVERAGE_FLOOR / RECALL_UNFILTERED_FALLBACK
```

When on, `mates` is filtered to words taught or heard since `session_t0`; **if that set is
empty the filter is not applied** and the old full pool stands, so the flag can never turn
a speaking organism into a silent one. Flag off must be line-for-line the current code.

Expected effect, from the measurements above: the pool for these asks drops from 11,439 to
the handful of words in three short tells. `scarf` at 0.1508 and `lantern` at 0.4131 no
longer compete against `numbered` at 0.5811, because `numbered` is not in the scoped pool.
This is the only repair consistent with the data that can actually *win* rather than merely
go quiet — the attractor is not out-scored, it is **not a candidate**.

Target set is **3 asks, not 4**: the two `scarf` asks and the `lantern` ask. The echo ask is
excluded for the rendering reason above and must not be counted as an E9 failure or an E9
win.

All four `mouth` rows are `tier: probe` (verified in the generation-10 journal), so this
class cannot move the frozen score at all. E9's upside is entirely on the **paraphrase
probe** metric — which is the generalisation number that has read 0/14 through every
experiment so far, and is therefore the more valuable of the two to move. P4 predicts frozen
stays 19/24 not because the repair is safe there but because it is *irrelevant* there.

## E9 pre-registration

**Arms.** Same genome `abffa2b7f101`, `--tier frozen,probe`, 42 asks each (24 frozen + 18
probe, where the 18 probe rows are 14 paraphrase probes plus the 4 guarded invariants — the
standing reporting convention, which is why the probe score reads `0/14` with `4/4` guarded
rather than `4/18`).
Arm A control (flag off), arm B `--resonance-scope` (flag on). Two independent builds per
ask, as always.

**Predictions.**

- **P1 — flag-off identity.** Arm A reproduces generation 10 ask for ask: 19/24 frozen,
  0/14 paraphrase probes, 4/4 guarded, stages `{recall: 10, mouth: 4, gating: 3,
  shape_arbiter: 2}`, and the four `mouth` rows still say `worked rigging` / `numbered` /
  `sold` / `compile leagues`. Any difference invalidates the run, not the hypothesis.
- **P2 — the pool actually shrinks.** Instrumented scoped-pool size for the three target
  asks is **< 100** and contains the wanted word. If the scoped pool is empty, or still
  11,439, the mechanism did not engage and E9 is void rather than failed.
- **P3 — the attractor is excluded, not out-scored.** `numbered`, `sold` and `agin` are
  **absent** from the scoped pool on all three target asks. This is the specific claim that
  distinguishes scoping from reweighting; if they remain candidates and merely lose, P3 is
  falsified even if the ask passes.
- **P4 — score movement.** Probes rise from 0/14 to **at least 2/14** (the two `scarf`
  asks). Frozen stays **19/24** and guarded stays **4/4**. `lantern` may or may not pass —
  at 0.4131 it is the strongest candidate but the ask also needs the ordinal path, so it is
  **not** predicted and will be reported either way.
- **P5 — zero erosion.** No guarded ask lost, no frozen ask lost, binder row count
  unchanged at 60,000, and no `who == "you"` row displaced.
- **P6 — no new babble.** Every ask that arm B speaks and arm A did not is listed by name
  with its wanted answer. A repair that trades four wrong words for four *different* wrong
  words is not a repair, and P6 is what catches that.

**Abort condition, stated before running.** If P2 holds but the wanted word still does not
win its scoped pool, **abandon rather than widen**. Do not raise the pool to "recent" words,
do not add a frequency penalty, do not lower `reply_threshold` to compensate. Each of those
reintroduces the attractor by a side door, and the measurement that matters — that the
attractor band sits above threshold and is ask-independent — would still stand unexplained.

**Invalidation.** Any difference between arm A and generation 10; any `mouth` row in arm B
whose `source` is not `meaning resonance` (with or without `+ chain`), which would mean a
different path answered and the experiment measured nothing; any guarded loss.

**Cost.** 2 arms × 42 asks × ~26 s ≈ **36 min**, ~84 builds.

## Tests to write first

`tests/test_mouth_resonance_scope.py`:

1. `RESONANCE_SESSION_SCOPE` exists as a class attribute and is `False` by default.
2. With the flag off, `mates` is computed exactly as before — a pure-function test over a
   stub `word_patterns` asserting the candidate list is unchanged, so the flag-off path is
   provably the old code.
3. With the flag on and a non-empty session set, every candidate is session-attributable and
   the corpus attractors are absent (P3 as a unit test, no brain required).
4. **Empty-session fallback**: with the flag on and no session words, the candidate set
   equals the full pool. The flag must never silence an organism that would otherwise speak.
5. `_speakable` still rejects multi-word strings, pinning the rendering limit that excludes
   the echo ask from E9's target set.
6. The four `mouth` rows in generations 9 and 10 still carry `tier: probe`, `stage: mouth`,
   `cause: mouth`, `pass: false`, `coverage: null` and a `source` beginning
   `meaning resonance` — the journal evidence this diagnosis rests on, pinned so it cannot be
   quietly reclassified. The test asserts on fields the journal actually stores and must
   **not** assert on `utterance`, which is `null` there.
7. A regression test that `reply_threshold` is **not** the repair: asserting the measured
   attractor band (0.550–0.581) lies entirely above the wanted-word scores (≤ 0.4131), so no
   threshold separates them. This is the "empty window" claim, and it is what stops a future
   pass from re-trying the threshold.

## Not done here

No core answer-path code changed. No multi-brain work. No broad refactor. The organ is
untouched by this diagnosis; the only new files are the probe, its JSON, and this document.
