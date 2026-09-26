# PLAN — from a grounded animal to a speaking, coding, reasoning alien

## WHERE THIS ACTUALLY IS (updated from measurement, not intention)

    Phase 0  body        ~80%  acts become propositions with a doer; adversity from
                               real exit codes. Missing: file ops, task lifecycle.
    Phase 1  input       ~90%  45,359-line corpus, 2,549 distinct words, reading at
                               ~36 words/s unattended. Missing: reading in its own
                               process -- it competes with the tick loop and world
                               speed falls from 20x to 7x while he reads.
    Phase 2  population  ~85%  5-way merge verified and installed. Missing: variance.
                               Every headline number in this project is still n=1.
    Phase 3  speech      ~55%  sparse chain, 2,117 words, multi-word speech 25-67%
                               (the variance is the problem). Missing: self-correction,
                               multi-proposition composition, and any variation at all
                               in the sentence endpoint.
    Phase 4  coding      ~75%  Path A activated, graded execution gate, retrieval
                               84%/100%, 159 of 284 procedures trusted. Missing:
                               route distribution over a real task battery.
    Phase 5  reasoning   ~15%  5a built and measured. 5b, 5c, 5d untouched.

Against the three goals: A (English) is the furthest -- he has words and a chain
that can only reproduce orders it has heard, not compose new ones. B (coding) has
sound machinery over a narrow library: his own functions, not novel tasks. C
(reasoning) has its first real component and nothing above it yet.

The number that explains most of the remaining gap: 0.8% of what he remembers is
something he DID. Binding runs 13.5x chance on acts and 1.6x on prose. He is a
reader with a small life.

Working document. Status is updated as items land. Nothing here waits on "later"
unless it genuinely depends on something above it.

The three goals:
  A. Full spoken English.
  B. Coding that covers ~90% of tasks locally, oracle only for the novel ~10%.
  C. Reasoning — multi-step, self-checking, not association dressed up.

The two facts that shape the order:
  * Input structure is the binding constraint. Changing corpus structure alone
    moved comprehension from 24% to 95% with zero architecture change.
  * We are not one animal and we do not have to learn serially. Individuals can
    be run in parallel and their learned structures MERGED — biology cannot pool
    twenty lifetimes into one brain; a filesystem copy can. That is the lever
    that turns months into hours.

---

## PHASE 0 — the body (unblocked, do first)

- [x] Grounding channels exist: `ground(kind, name)` lights a percept on real
      projection neurons for 25 s; words heard while it is lit wire to it.
- [ ] **Every sandbox act becomes a percept.** File read/write/list, terminal
      command, exit code, task start/end. His world is a terminal; code is a
      sense, not a subject.
- [ ] Adversity from real failure (nonzero exit, refused action), not from an
      endpoint poked by hand.

## PHASE 1 — flood the input (unblocked, biggest single lever)

- [ ] **A real corpus.** 477 lines is a pamphlet. Generate tens of thousands of
      grounded sentences with consistent roles, graded: caregiver speech ->
      simple narrative -> technical prose -> code and its commentary.
- [ ] **Reading at machine speed.** The 1 line/second floor was set to stop a
      firehose that cost a 4 MB write per line. Per-line cost is now far lower,
      so measure it and raise the rate to what the box bears.
- [ ] Reading in its own process, like the accelerated life, so exposure does not
      compete with the tick loop.

## PHASE 2 — the population (unblocked, the alien move)

- [ ] **N individuals in parallel**, each on a different corpus shard and
      optionally different organ parameters.
- [ ] **Merge**: SAN weights, sequence chains, binder propositions, vocabulary
      and plastic weights are all combinable. One animal ends up with N
      lifetimes of exposure.
- [ ] Lineage is preserved, never destroyed: a generation is a saved set of
      state files, and the original stays alive as the control.
- [ ] Variance: every headline number gets N runs and a spread, because n=1 is a
      demo, not a result.

## PHASE 3 — speech (needs Phase 1)

- [x] Sequence organ: explicit time slots, position-addressed words, asymmetric
      chains, refuses to invent (5/5 exact recall on trained material).
- [x] Answer a question: interrogative -> role mapping learned from exposure,
      proposition retrieved, role unbound, sentence spoken, silence when nothing
      matches. 24/24 corpus, 7/7 novel phrasings.
- [ ] Chain trained on the real corpus instead of the primer.
- [ ] **Self-correction loop**: speak -> hear own output -> compare with intended
      proposition -> prediction error -> adjust. Fluency is calibration, not
      vocabulary. The predictor already exists; close the loop on his own voice.
- [ ] Composition beyond one proposition (nested/linked roles) so he can say
      "parent feeds droso because droso is hungry".

## PHASE 4 — coding (needs Phase 0; independent of Phase 3)

- [ ] **Activate Path A.** fast_router / local_solver / code_assembler /
      learning_loop / query_cache / token_optimizer are all built and have run
      zero times. Feed them tasks.
- [ ] **Execution-gated verification**: only code that passes in the sandbox
      becomes a procedure. This IS the 90/10 split. Without it the store fills
      with plausible wrong code and speed becomes confident failure.
- [ ] Semantic retrieval for procedures (`recall_procedure` is exact-key lookup —
      the same bug already fixed in language memory; same fix).
- [ ] Measure the route distribution over a real task battery: how much goes
      learned / local / cache / oracle. That number is the claim.

## PHASE 5 — reasoning (ordered; each needs the one above)

- [ ] **5a. A goal that survives across steps.** Working memory is a Python dict.
      Build delay activity — persistent state that holds the goal while he works.
      Nothing multi-step can exist before this.
- [ ] **5b. Search pruned by anticipation.** Multi-step retrieval where each
      candidate is scored by prediction error before it is taken. Requires 5a
      (a place to hold the goal) and the predictor (exists).
- [ ] **5c. Self-verification.** He can run code, so he can falsify himself.
      Inference with ground truth. Requires 5b.
- [ ] **5d. Merge the population's reasoning traces, then evolve the knobs.**
      Requires everything above. Evolution optimises what exists; it does not
      invent what is missing, and a single-metric fitness breeds an individual
      that games the test set.

## Blocked-on map

    Phase 0 ─┬─> Phase 4 (coding)
    Phase 1 ─┴─> Phase 2 (population) ─> Phase 3 (speech at scale)
    Phase 3 + Phase 4 ─> 5a ─> 5b ─> 5c ─> 5d

Phase 3 and Phase 4 are independent of each other and can run in parallel.
5a-5d are strictly serial.

## Explicitly NOT worth doing

- Scaling the sequence organ's slot count. 48 positions is already more than any
  sentence he says; the limit is training data per transition, not length.
- A bigger SAN before the corpus is big. Capacity without input is an empty room.
- Evolving parameters now. There is nothing worth optimising yet.
- Anything that makes the fly more faithfully a fly. The connectome is a premade
  brain, not a museum piece.
