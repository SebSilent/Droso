# Design step: MP-E12b, the weight-to-connectome compiler

**Status: DESIGN ONLY. Nothing here is implemented, and no MP-E12 stage has run against the synthetic donor
beyond the sealed calibration.** The quoting guard on that calibration forbids quoting a synthetic figure as
evidence about GPT-2, and this document extends the same rule to *actions*: compiling a graph read from random
weights into a live organ would be an organ change whose entire rationale is a placeholder. Stage b is written
down so the ruling can be given in one line when the donor arrives, the way MP-E9's PRE-1 registered a
precondition ahead of the promotion and the H4 counter design step (`docs/h4_updates_counter_design.md`)
registered an instrument ahead of its ruling.

---

## 1. Why this is a design step and not a build

Rule R4 sanctions exactly one parallelism: the MP-E12a probe track, "**disjoint from Droso organs**". Stage a
honours that -- it reads tensors and writes its own artifacts. Stage b is not disjoint: it calls `grow_pool`,
`grow_plastic` and `wire_pool`, and it adds a class to the provenance machinery that protects refusal. So the
parallel-track authorisation **does not cover stage b**, and building it now would be the one kind of licence
this track does not have (recorded as D-MPE12-04 in `experiments/MP-E12/registration.json`). What stage b needs
before it can be written is a gate-order ruling, not code.

## 2. What it would change, at the line sites as they exist on this tree

| what the plan asks for | the real machinery | what stage b would do to it |
|---|---|---|
| "grow_pool for discovered feature clusters" | `connectome/rate_core.py:498 grow_pool(nodes=8, fanin=40) -> dict` | call it once per cluster centroid from extraction 1, so donor-adjacent token sets become pools. Structural growth: pool count changes, which changes every downstream decision surface. |
| "grow_plastic and wire_pool for association edges, gated by confidence" | `rate_core.py:238 grow_plastic(k=50, w0=0.01)`, `rate_core.py:305 wire_pool(pre_nodes, pool, k_per_pre=4, ...)` | create plastic synapses for edges above the confidence threshold and wire them into the pools. This moves the sealed 2,983-synapse build state, which is quoted in published evidence. |
| "every transplanted edge carries a provenance tag -- source model, extraction method, confidence" | `organs/neural_language.py:3431 learn_qa(..., provenance=None)`, `:3556 _qa_admissible` ("no provenance, no memory"), `:3572/:3590 _qa_keep` storing `"prov": dict(provenance)`, `:4196 _provenance_vote` | add a library-read provenance shape alongside the existing ones (book/line/person-marked/typed-by-a-human). **This is the dangerous part**: the same `prov` object is the authority test on the read path (`:3025-3073` "NO WIDENING BEYOND PROVENANCE", `:4974` "The rule is provenance, not knowledge", `:5044` provenance ranked before retrieval). A new provenance class is therefore not a label -- it changes what the agent is willing to say. |
| "the coverage gate gains a source dimension: curriculum-learned and library-read knowledge become distinct classes, which is what protects refusal" | `neural_language.py:107 _coverage_excluded(...)`, the recall gate's own coverage figure at `:5275` and its published form in `tools/converse.py:343-354` (`coverage`, `required`, `nearest`, `join`) | split coverage by source so a library-read row can be counted as covered *without* being treated as something the agent learned from the world. H3's third clause ("the agent can refuse to ground library-sourced claims") depends entirely on this split being real rather than cosmetic. |

## 3. The distinction the design has to hold, or the whole stage becomes unfalsifiable

Stage b contains **two different kinds of change**, and conflating them would let a treatment masquerade as an
instrument or an instrument masquerade as a result:

* **The plumbing** -- the provenance shape, the coverage source dimension, the compiler's reporting. This must
  be **inert**: with nothing to compile, it must change nothing.
* **The treatment** -- the compiled pools and edges themselves. This is *supposed* to change behaviour; that
  is H1. Proving it inert would prove the experiment did nothing.

So the inertness control is a specific run, not a general test: **transplant an empty graph** (zero clusters,
zero edges) through the full compiler path.

## 4. How inertness would be proven (the plumbing)

1. **Empty-graph transplant identity.** Same seed, same curriculum, compiler invoked with an empty association
   graph: `w`, `plastic_w0`, pool count, plastic-synapse count, brain fingerprint and every graded outcome
   bit-identical to the same run with the compiler absent. If the plumbing is inert, an empty transplant is a
   no-op; if it isn't, the plumbing has behaviour in it that no ruling authorised.
2. **Provenance neutrality.** A library-read row must not become answerable through any path that previously
   required human-typed provenance. Tested directly against `_qa_admissible` and `_provenance_vote`: the
   existing refusal suites run with the new class present and **no** edges compiled -- refusal must be
   unchanged, which is C2's condition ("library-sourced knowledge silently promoted to curriculum class --
   abort") expressed as a test rather than a sentence.
3. **Guard batteries unchanged**, per arm: frozen 19/24, guarded 4/4, paraphrase 0/14, `ELECTRIC=off`.
4. **Noise floor re-verified**: the three arm-A clones still within 11 rows of 3,672, movement confined to the
   R13 cell.
5. **The four R6 invariants** read from the tests that own them, not retyped.
6. **Re-seal all five ledgers at one anchor** with `git_dirty_sealed` empty -- `rate_core.py` and
   `neural_language.py` are hashed in every ledger, so a stage-b change touches all of them at once (the
   coupling the coverage test counts).

## 5. What must not move, listed so a reader can check it

The refusal suites and the guarded rows (C1: any guarded row answered post-transplant is an **abort**, not a
finding to be discussed). The distinction between curriculum-learned and library-read classes -- if it can be
collapsed by accident, H3's honesty claim collapses with it. The sealed 2,983-synapse build state as a
*baseline reference* (it may grow as a treatment, but the reference must stay addressable). The existing
provenance classes' meanings. The word-provenance audit's ability to trace every output word (R9). And the
plan's own boundary, "What MP-E12 is not": no donor run for answers, no fine-tuning of the donor, no
transformer wrapped around Droso, **no donor weights resident at deployment** -- the last of those is a
deployment property, so it needs a test that the compiled organ holds no donor tensor, not a paragraph
promising it.

## 6. What stage b would need decided before it can run

- **D-MPE12-06** the confidence threshold that gates an edge into `grow_plastic`/`wire_pool`. It must be fixed
  before the first real graph is compiled, and it cannot be derived from the synthetic donor (whose confidences
  describe geometry, not knowledge) -- so it is a registered number chosen against the *real* graph's shape or
  against a principle, never against its results.
- **D-MPE12-07** whether the source dimension is a new key inside `prov` or a new admissibility class in
  `_qa_admissible`. These are different risks: a key is inert data, a class is an authority. The plan's wording
  ("distinct classes ... which is what protects refusal") asks for the second, which is the one that can break
  refusal.
- **D-MPE12-08** whether stage b may be exercised on a scratch organ before the live one, and what would make a
  scratch result admissible.
- **The gate-order question**: stage b is not covered by R4, so does it wait for G4 (MP-E11) to close as the
  plan's order implies, or does the PI extend the parallel track? This is the decision that actually unblocks
  the work, and it is not a technical one.

## 7. Cost, stated honestly

The plumbing plus its inertness proof is roughly the H4 counter's shape: implementation in one session,
~50 min of machine time for the empty-graph identity run plus clones and batteries, and a re-seal. The
treatment runs (H1 at equal corpus exposure, against the text-distillation control) are a different order of
expense -- two full arms at the tiers the claim names, serial, and the text-distillation control needs the
donor to *generate* once offline, which is its own timed run. None of it can begin before the donor weights
arrive, and the compiler's own correctness cannot be demonstrated on the synthetic graph beyond what a
schema check can do, because there is nothing in a random graph worth compiling.
