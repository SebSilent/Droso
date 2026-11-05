# DROSO Master Plan v1.2 — The Live Brain Protocol

**Execution Roadmap MP-E8 to MP-E13, amended to repository reality at `ee7416c` and to the addressed-library doctrine**

| Field | Value |
|---|---|
| Version | **v1.2** — 2026-11-05 |
| Supersedes | v1.1 (2026-11-02), tracked at `experiments/MP-E9/plan_extract/DROSO_Master_Plan_v1_1.txt` |
| Source of truth | Repository `main` at HEAD `ee7416c`; 194 sealed files at anchor `6a66d7cb2579`; `git_dirty_sealed = []`; covering suite 1,364/1,364 executed, 0 failures, 6 skipped, rc 0 (`suite_manifest_licensed_absence_hunt.json`) |
| Owner | Principal Investigator (the funder; every PI ruling in this plan is theirs) |
| Workforce | Human lead + AI engineering agents + orchestrator |
| Discipline | Pre-registered, gate-driven, sealed, word-level honest, floor-doctrined |
| Program goal | Real intelligence — or, as the funder states it: *an agent that works cheaply with frozen weights, without wasting RAM or VRAM, on a laptop* |
| Donor directive | **Qwen3.8-27B** — funder-designated 2026-11-05; confirmed open-weights (released 2026-08-13/14, Apache 2.0, `Qwen/Qwen3.8-27B`). Addressed, never executed (rule R11) |

---

## 0. The v1.2 Amendment Record

### 0.1 Why v1.2 exists

Version 1.1 was written before the program's instrument met the program's predictions. Between 2026-11-02 and 2026-11-05 the repository built the registration-seal machinery (five ledgers, 194 sealed files, one shared anchor), ran the three-arm duel's first full tiers, and returned four findings that a plan written on 2026-11-02 cannot absorb:

- **(a) The duel's registered forgetting prediction was falsified.** Arm B (frozen store + retrieval) dropped 1.6827 pp at tier 120 against a registered 5.0 pp minimum — a FAIL — and at tier 300 the sign reversed: arm B *improved* by 1.24–2.68 pp (`armB_tier120_seeds_verdict.json:4-15`, `armB_tier300_seeds_verdict.json`). 
- **(b) MP-E10's H3 is void at its own registered tier.** The pre-registered saturation guard fired: at tier 300 the store pushed 72 entries to the 4.0 ceiling at depth 2 (pass 1 of 2) and 156 stood at ceiling before / 252 were pushed during at depth 3 — so the 0.0000 pp interference reading is *a result that was not obtainable*, not a null result (`replay_tier300_summary.json:208-209`, ruling D-MPE10-12 open).
- **(c) The instrument itself moves without treatment.** Two fresh-vs-fresh pairs at tier 120, same process, identical code: 17/3,744 (0.4541%) and 4/3,744 (0.1068%) rows moved, confined to depth-3 refusal classes, `correct` identical everywhere (`fresh_vs_fresh_tier120.json`). Every single-run behavioural claim on this instrument is now bounded by a measured floor.
- **(d) The licensed-absence defect has an n.** 10 flips in 200 contexts = 5.00%, Wilson 95% [2.7382%, 8.9579%], intermittent, not seed-determined, the same single alternative in 10/10 flips, safety property intact in 200/200 contexts, and a green covering suite that does not close it (`licensed_absence_flip_hunt.json:2235-2294`; `registration.json:2120` — "OPEN — NAMED, NOT CLOSED").

Independently, the funder issued two directives that name this version's destination:

1. **The scale donor is Qwen3.8-27B** — designated by name, confirmed real and open (Apache 2.0, dense 27B, 262k native context, released August 2026). This plan treats the designation as fact and pins engineering details at registration.
2. **Frozen weights must work in an unconventional way**: not by running them — by *accessing them at any point*, the way one calls an API; the connectome should understand the weights *as if they were its own knowledge*. This directive is codified as standing rule **R11** and rewrites MP-E12 (Chapter 6.5) around an **addressed library**: a read-only, memory-mapped weight space that stays queryable at deployment, never executed, never fully resident.

### 0.2 The amendments

| ID | Amendment | Triggered by |
|---|---|---|
| **A** | **Gate ledger reconciliation.** Every gate G0-prime through G6 is restated at its *measured* verdict as of `ee7416c` (Chapter 5), replacing v1.1's prospective go-criteria as the program's status of record. Verdicts come from the owning ledgers, with file:line sources. | The funder's decision report (2026-11-05); all figures verified against artifacts. |
| **B** | **Theory-of-victory re-aim.** "Baselines catastrophically forget at 120–300 items" is retired as a claim — measured not to happen on this organ at these tiers (finding a). Surpass is redefined on the axes a frozen stack structurally cannot follow: adaptation during deployment, retention across restarts, refusal calibration, cost per retained item, and capacity per watt (§2.2). The falsification is recorded under R5 as an asset, not buried. | G2-H1 FAIL + sign reversal at tier 300. |
| **C** | **The floor doctrine becomes law (R17).** No single-run behavioural claim without a fresh-vs-fresh pair on identical instrument bytes at the claim's tier. The tier-300 fresh-vs-fresh pair (~44 min, 2 × 22.0 min learn-only) is a *mandatory purchase* before any tier-300 attribution, including the 111-row replay-vs-control difference, the 251/302 migration counts and the 91/92/100 invention-breach tallies. | Finding (c); the tier-300 identical-code floor is still unmeasured. |
| **D** | **Capacity promoted to first-class.** The tier-300 saturation (72 and 252 ceiling hits) is a *finding*, not a failure: the store's capacity wall is now a registered, tracked curve (ceiling-hits vs. tier), and the program adopts an explicit target — 300 → 3,000 taught items at flat laptop cost. MP-E10's H3 is re-registered: primary at tier 120 (guard silent, prediction already held on 416 rows); tier 300 reported as a capacity finding, never as an interference measurement. D-MPE10-12 is ruled exactly this way and no other (§6.3). | Finding (b); the saturation guard fired as pre-registered. |
| **E** | **MP-E12 rewritten: the addressed library.** The donor is never run. Its weights are a read-only address space, mmap-resident on disk, queryable at any coordinate at deployment time, journaled per access, compiled into the connectome by confidence-gated local rules. Scale donor: **Qwen3.8-27B**. New hypotheses, new C-conditions, and a new H4 (the laptop clause: residency ceiling, VRAM = 0, latency budget) (§6.5, Appendix A). Codified as rule **R11**. | The funder's directive; the report's confirmation that MP-E12 is blocked only on weights that are a download away. |
| **F** | **A tenth evaluation axis.** A10 *resource cost*: peak RSS per phase, VRAM = 0 asserted per run, and cost per retained item across restarts. The v1.1 report priced every quantity in minutes and never measured the axis the program goal is stated in. Adding axes is sanctioned by v1.1 §8.2; removal or redefinition of the nine is still forbidden. | The program goal; the report's own cost table. |
| **G** | **The licensed-absence defect is scheduled, with an order.** The hunt is done (5.00%, CI, safety intact); what remains is a targeted fix *after* the ruling batch and T & N, because an answer-path edit supersedes the 1,364-test covering run and every artifact quoting a `reason` string. Budget: one re-baseline, 852.01 s measured. Green is not closure. | Finding (d); R2 discipline on answer-path edits. |
| **H** | **Execution order priced and re-sequenced.** Rulings first (11 PI items, zero machine time, fixed order §7.2), then the two cheap purchases that unblock attribution (GPT-2 weights, tier-300 floor pair), then T & N (~3.85 h), then the re-registered replay config, and the answer-path fix last. MP-E12a opens in parallel immediately (G0-prime is closed; R4's sanctioned parallelism is available). | The report's pricing; dependency chain `:935-936`. |

### 0.3 What v1.2 does not change

The thesis (frozen versus live, not big versus small) stands — sharpened, not weakened, by finding (a). The native-versus-transplant rule R1 stands without exception. The MP- namespace, the gate structure, the two-instrument doctrine, the registration protocol and the nine classical axes all stand. The repository's rule registry (R12–R16, defined in `experiments/G0-prime/registration.json` `risk_register_additions`) is absorbed by reference, not restated or renumbered — which is why this amendment's two new rules take R11 (unused) and R17 (next free). No closed negative is re-opened: the six retrieval levers, the repo-E8 abort, the gen-24 LOST verdict, the P2 falsification and the G2-H1 verdict remain recorded facts any future proposal must cite. And the standing prohibitions on deciding after seeing the result (§6.2) are elevated from the report's warning list to program law.

---

## 1. Executive Summary

Droso is a connectome-scale agent that learns during deployment without gradient descent: taught facts in natural language survive real process restarts, are answered in words the teacher never used, are consolidated by replay under local rules, and unknowns are refused with reasons instead of confabulated. The program's discipline — pre-registration, sealed ledgers, word-level honesty grading, registered abort conditions — has survived contact with its own predictions three times this month, which is exactly what it is for. The goal is unchanged and is now stated in the funder's own terms: real intelligence, or at least an agent that works *cheaply*, with frozen weights, without wasting RAM or VRAM, on a laptop.

Where the program stands, measured: the capability instrument is sealed and its conditional closure recorded (G0-prime, closed under R13(a) with the noise-floor caveat *NOT REPRODUCIBLE* recorded beside it — an honest instrument, not a perfect one). The duel has run: the live arm holds its taught set across restarts at every tier measured so far, and — the headline surprise — the frozen-plus-retrieval rival did **not** catastrophically forget at tier 120 (drop 1.68 pp vs. a registered 5.0 pp minimum) and *improved* at tier 300. The program's response to that falsification is this plan's central re-aim: the claim was never going to be that rivals decay; it is that a live substrate *becomes different during deployment* while a frozen stack cannot, and now the fight is taken to the axes where that difference is structural — adaptation, retention across restarts, refusal calibration, cost per retained item, and capacity per watt.

The consolidation instrument met its own guard: at tier 300 the store saturated (72 and 252 entries at the 4.0 ceiling), and the pre-registered saturation guard correctly declared the interference measurement *void rather than null*. v1.2 converts that wall into the program's next climbing objective — the saturation curve becomes a registered, tracked metric, with an explicit target of 3,000 taught items at flat laptop cost — and re-registers the interference question at tier 120, where the instrument is clean and the prediction already held (0.0000 pp on 416 rows, guard silent).

The flagship is rewritten around the funder's directive. MP-E12 no longer reads a donor's weights once, compiles, and discards. Under R11, a frozen model's weights are an **addressed library**: a read-only, memory-mapped address space that the connectome queries at any coordinate, at any time, during deployment — the way an organ calls an API — and understands *as if it were its own knowledge*: fluency-wise indistinguishable from taught material, honesty-wise distinct (library-sourced words are traceable to an address, quotable or refusable, never silently curriculum). The library is never executed — no forward pass, no autoregressive loop, no inference latency, no VRAM — and never fully resident: it lives on disk, only touched pages are cached, peak RSS is a registered metric with a ceiling, and VRAM = 0 is asserted on every run. The calibration donor remains GPT-2 124M (a download away, unblocking MP-E12a immediately); the scale donor is **Qwen3.8-27B** (funder-designated; Apache 2.0; dense; 262k context) at MP-E12c, where the laptop clause — H4 — is graded on the big library itself.

Execution order, priced from measured unit costs: **rule the 11 pending PI items** (zero machine time; D-MPE10-12 alone unblocks G3) → **download GPT-2 124M** (~500 MB; unblocks the flagship's first stage) → **buy the tier-300 fresh-vs-fresh pair** (~44 min; without it no tier-300 number is attributable) → **run T & N at tiers 120/300** (~3.85 h) → **re-register and run the non-saturating replay config** (~2 h) → **fix the licensed-absence defect last** (one re-baseline, 852.01 s) — with MP-E12a running in parallel from the moment the GPT-2 weights land. Everything in this plan is executable by the agents without further interpretation: every experiment carries its status, its remaining work, its price, its hypotheses, its C-conditions, and a pasteable checklist (Chapter 12).

---

## 2. The Live Brain Thesis

### 2.1 Why frozen weights lose in the end (v1.2 statement)

The dominant paradigm froze learning into a batch process. A language model is trained for weeks, its weights are frozen, and deployment consists of prompting a static artifact; anything it must know afterwards is injected as context. Retrieval-augmented generation is the honest name for this arrangement: the model does not learn, it is told. It cannot consolidate an experience into structure, cannot distinguish what it knows from what it was just handed, and — as measured repeatedly at every scale, including this program's own tier-300 invention-breach tallies — it will fabricate when asked about anything outside its store.

v1.1 predicted that such a stack would also *decay* — that arm B would show a catastrophic-forgetting drop above 5 pp at tiers 120 and 300. The measurement said otherwise: 1.6827 pp at tier 120 (FAIL against the registered minimum), and improvement of 1.24–2.68 pp at tier 300. The program records that falsification and re-grounds the thesis on what the measurement did show. A frozen stack loses in the end not because it forgets, but because of four things no snapshot can do:

1. **It cannot become different.** Its accuracy-versus-exposures curve is flat by construction. Every fact Droso acquires at deployment is a fact the frozen stack will still not know after a year of the same deployment.
2. **Its knowledge is rented or frozen.** Prompt-bolted knowledge costs context window on every query and evaporates with the session; weights-baked knowledge costs a training run on a cluster and a full re-freeze.
3. **Its honesty boundary is not its own.** Arm C satisfies the registered refusal criterion while producing zero correct answers at every tier — abstention calibrated on a store that cannot learn is abstention about a store that cannot improve.
4. **Its cost structure is the wrong shape.** Every query pays inference latency and (typically) VRAM. The addressed-library doctrine (R11) inverts this: the weights are read like memory, not executed like a function — and reading is not running.

The measured Droso stack holds the other side of the comparison: generalisation to held-out frames at 20/20 with zero confabulations, survival of 600 consolidation replays at 20/20, three teach-consolidate-restart cycles with zero loss and zero interference, and live-learning curves (79 → 98 → 108 → 115 of 124 at depth 3) that no frozen arm can produce at any price. The fight is not big versus small; it is frozen versus live — and live wins wherever the axes keep moving after deployment.

### 2.2 What surpass means, precisely (re-aimed by Amendment B)

A claim of surpassing is meaningless until phrased as axes and thresholds. The program evaluates ten (the nine of v1.1 plus A10, Amendment F). Surpass is defined as: **beat both reference baselines on the four live axes — adaptation speed, backward transfer, refusal calibration, and cost per retained item — while holding the classical five competitive, and demonstrate capacity scaling on laptop hardware that neither baseline can match at its cost structure.**

The two reference baselines are unchanged: a sequentially fine-tuned small language model (arm B) and a frozen language model with retrieval bolted on (arm C); the teach arm serves as the internal repeat-and-lookup control. One claim is explicitly retired, in the open, under R5: *"the baselines will catastrophically forget at 120–300 items"* — measured false on this organ at these tiers, with the sign reversing at tier 300 on an instrument whose single-run floor now bounds interpretation (R17). What replaces it is sharper: the baselines' *level* may hold, but their *curves* cannot move; Droso's can, and Chapter 6.2 prices the measurements that prove it. Surpass still does not mean beating transformer fluency at the duel stage; the fluency gap closes on the MP-E10/MP-E11 path and this plan says so in advance. And the gen-24 verdict (ELECTRIC on: 17/24 against the battery's 19/24; abort fired; LOST recorded) remains the program's definition of a fair fight.

### 2.3 The native-versus-transplant rule

Unchanged from v1.0 and v1.1, and now load-bearing for the flagship: any mechanism buildable from pools, plastic synapses, spreading activation, and local learning rules is native and may be built freely; any mechanism requiring global gradients or a training run inside the deployment loop is a transplant and is forbidden. The addressed library is native end to end: an mmap is an address space, not a computation; an address read is a lookup, not a gradient; compilation is confidence-gated local wiring. Backpropagating error into the connectome remains a transplant, and so is any differentiable pipeline wrapped around it. Rule R11 (§4) is the flagship's special case of R1, stated separately because it is the program's most important design commitment.

---

## 3. Program Baseline v1.2 and Working Vocabulary

### 3.1 Where the codebase stands (measured, 2026-11-05, HEAD `ee7416c`)

The following facts are measured on the repository and constitute the baseline from which every experiment starts. Sources are artifact paths in the repository; where the funder's decision report carried file:line citations, they are reproduced so any agent can re-derive the number.

| Component / capability | Measured state at `ee7416c` | Program response |
|---|---|---|
| Substrate | BANC v888 carve: 12,867 neurons, 173,294 signed synapses, 4,419 Kenyon cells, 85 mushroom-body output neurons in 12 groups, 83 dopaminergic neurons, 382 projection neurons, central complex 961-in/709-out | MP-E11 scaling tiers; `build_core_graph(control=True)` real-versus-random control |
| Plastic substrate | 20,000+ plastic synapse weights per instance; at small scale real wiring performs like random wiring | MP-E11 tiers 20k→50k→100k→200k |
| Live learning (ELECTRIC) | Teach/answer/learn modes behind default-off flags; generalisation 20/20 on held-out frames, zero confabulations; 600-replay survival 20/20; three teach-consolidate-restart cycles, zero loss, zero interference; learn-arm depth-3 curve 79→98→108→115 of 124 | MP-E8 arm A; curriculum tiers 120/300 measured this window |
| Suite | 1,364 collected / 1,364 executed / 0 failures / 6 skipped / rc 0 at `1ff00c3` (852.01 s); one skip is the licensed-absence reproduction test, reason `INTERMITTENT, NOT SEED-DETERMINED` | Green ≠ closure (finding d); fix scheduled last (Amendment G) |
| Sealing | Five ledgers, 194 sealed files, one shared anchor `6a66d7cb2579`, `git_dirty_sealed = []`; registration-seal coverage test in suite | Re-stamp tax accepted; ruling batch to clear the queue (§7.2) |
| Duel (MP-E8) | Arm A artifacts at tiers 40/120/300; arm B tier-120 drop 1.6827 pp vs registered 5.0 pp minimum (FAIL; per-seed 3.8462/2.1634/1.6827; spread 2.1635 pp), tier-300 drops −1.24 to −2.68 pp (sign reversed); arm C satisfies H2 clause 2 with zero correct answers at every tier; T and N exist at tier 40 only | Amendment B re-aim; remaining work priced in §6.2 |
| Replay (MP-E10) | Tier-120 H3: 0.0000 pp on 416 rows, guard silent, prediction held; tier-300 H3: void at depths 2/3 by pre-registered saturation guard (72 and 252 ceiling hits at 4.0); replay-OFF control moved 58 of the same rows → sealed-baseline drift ~1.8% registered as `sealed_baseline_reproducibility` | D-MPE10-12 ruling spec (§6.3); capacity curve (Amendment D) |
| Instrument floor | Fresh-vs-fresh tier 120: 17/3,744 (0.4541%) and 4/3,744 (0.1068%) rows moved with no treatment, same process, identical code; movement confined to depth-3 refusal/partial/invented classes; `correct` identical at every depth and phase | Rule R17; tier-300 pair mandatory (Amendment C) |
| Licensed absence | 10/200 flips = 5.00%, Wilson 95% [2.7382%, 8.9579%]; 5 of 8 seeds flip, 3 never; same single alternative 10/10; safety property intact 200/200; OPEN — NAMED, NOT CLOSED | Amendment G: targeted fix after rulings + T & N; one re-baseline 852.01 s |
| Frozen battery | 19/24 organ-only, stable across 26 generations; guards 8/8; regression guard only | No capability claim argued from it |
| Donors | GPT-2 124M public weights **not on this machine** (`MP-E12/registration.json:2060`); Qwen3.8-27B designated by the funder, open-weights confirmed | Download GPT-2 now (§7.2 step 2); Qwen3.8-27B at E12c registration |
| Measured unit costs | Tier 40 full three-arm 481.3 s (8.0 min); tier 120 full 1,396.5 s (23.3 min); tier 120 learn-only 475.5 s; tier 300 full 3,214.6 s (53.6 min); tier 300 learn-only 1,317.1 s control / 1,124.6 s replay; covering suite 852.01 s; hunt repetition mean 12.60 s | All remaining work priced from these (§7) |

### 3.2 Working vocabulary — additions since v1.1

| Term | Definition in this program |
|---|---|
| **Addressed library** | A frozen model's weights treated as a read-only, memory-mapped address space: any tensor coordinate (layer, matrix, row, column, value) is accessible at any time during deployment, instantly, without executing the model (R11). |
| **Access journal** | The per-access record of the library: which address was read, by which probe, when, and what was returned. The organ remembers what it looked at — the substrate of "his knowledge" that is still word-level traceable under R9. |
| **Compile read vs. live address read** | Compile reads happen offline (extraction, budgeted, sealed) and feed the compiler. Live address reads happen at deployment, through native probes, under the latency budget. Both are reads; neither is execution. |
| **Fresh-vs-fresh pair** | Two full runs of the same arm, same tier, same instrument bytes, no treatment difference, in one process. Measures the identical-code floor at that tier. Required by R17 before any single-run behavioural claim at that tier. |
| **Saturation guard** | The pre-registered MP-E10 condition that voids an interference reading when entries are pushed to the 4.0 weight ceiling: an unchanged tally from a saturated store is a result that was not obtainable, not a null result. |
| **Saturation curve** | The registered capacity metric: ceiling-hit counts vs. curriculum tier. First-class from v1.2 (Amendment D); the program's scaling target is 3,000 taught items at flat laptop cost. |
| **Registration seal / five ledgers** | The repository's sealing machinery: experiment registrations stamped at a shared git anchor, per-blob sha256, `git_dirty_sealed` empty, coverage-tested in the suite. R10's mechanism, built. |
| **PI ruling queue** | The numbered list of open decisions awaiting the Principal Investigator (11 items, 14 ledger keys, indexed at `MP-E10:2538`). Zero machine time; batched (§7.2, B.R). |
| **Licensed-absence defect** | The intermittent answer-path flip: 5.00% [2.74, 8.96] of contexts, not seed-determined, one recurring alternative, safety property intact. The program's only live honesty defect; fix scheduled last (Amendment G). |
| **Resource ledger** | The A10 instrument: peak RSS per phase, VRAM = 0 assertion, cost per retained item across restarts. Registered on every bench run from v1.2 onward. |

---

## 4. Program Doctrine: Standing Rules R1–R11 and R17

Eleven doctrine rules govern every design decision and every experiment. R1–R10 carry over from v1.1 in substance. **R11 is added by this amendment** (the funder's addressed-library directive; the number is unused by the repository). **R17 is added by this amendment** (the floor doctrine; the repository's risk register has already assigned R12–R16 in `experiments/G0-prime/registration.json`, and this plan absorbs those by reference rather than colliding with them). Rules are retroactive in spirit: they describe standards the repository already enforced once at a cost, and this plan makes them standing law so the cost is paid once.

- **R1 — Native versus transplant.** Any mechanism buildable from pools, plastic synapses, spreading activation, and local rules is native and may be built; anything requiring global gradients or a training run inside the deployment loop is forbidden. The addressed library is native: an mmap is an address space, not a computation. Checked at every design decision.
- **R2 — Pre-registration before execution.** No experiment runs before its registration file exists: hypotheses with directional predictions, arms and seeds, metric definitions, thresholds, C-conditions, stopping rules, analysis plan, and harness version hashes. Nothing in the file changes after results exist. Deciding after seeing the result is the defining R2 event; the standing prohibitions in §6.2 are its current form.
- **R3 — Suites are frozen after first use.** The frozen 24, the probe journals, the guarded invariants, the guarded-absence rows, the four mouth stages, and the registered probe matrices are never edited after results have been seen against them. New questions go to new suites; historical rows are never backfilled.
- **R4 — One experiment in flight.** A gate must close before the next experiment opens. The single sanctioned parallelism remains the MP-E12a probe track, which touches only the donor library and no Droso organ; G0-prime is closed, so it is open now.
- **R5 — Every result ships artifacts.** Results JSON with a versioned schema, figures, and a decision record — including null results, voids, losses, and retracted claims. A loss recorded honestly is a program asset. The G2-H1 falsification and the tier-300 H3 void are v1.2's additions to that ledger, recorded beside the claims they correct.
- **R6 — Invariants: retention and refusal.** Any change that improves fluency but degrades retention or refusal accuracy is rejected regardless of the size of the gain. The system must never learn to lie in order to speak better.
- **R7 — Baselines cannot be ducked.** Any beats-frozen-weights claim includes both the sequentially fine-tuned model (arm B) and the frozen model with retrieval (arm C) in the same registration, on the same suites, under the same restart protocol; the teach arm is reported beside them as the internal repeat-baseline.
- **R8 — A repair that works but breaks a guard is a diagnosis, not a fix.** When a gain and a guard collide, the collision is measured, named, and shipped as knowledge; the flag stays off until a mechanism separates them. (Repo-E23; generation 24.)
- **R9 — Honesty is graded at word level.** Every content word in every answer must be traceable to a taught row, the ask, or an admitted source. Under the addressed library (R11), an accessed address is an admitted source *only through the access journal*: a library-sourced word is quotable or refusable by address, never silently curriculum.
- **R10 — Registered instruments live in the repository.** Harnesses, journals, registration files and schemas that measurements depend on are committed or re-derivable from committed scripts. Built out this window as the registration seal: five ledgers, 194 sealed files, coverage-tested.
- **R11 — The library is addressed, never executed.** *(New in v1.2.)* A frozen donor's weights are used in exactly two ways: as a read-only address space (compile reads offline; live address reads at deployment), and never as a computed function. No forward pass, no autoregressive loop, no sampling, no inference of any kind may sit in the deployment loop or in any mechanism whose output reaches an answer. Every access is journaled. The only sanctioned execution of a donor in the entire program is the text-distillation control arm — offline, once per registration — because it is the rival hypothesis being tested, not the mechanism. Any pipeline that must run the model to answer is a different program.
- **R17 — No behavioural claim without a floor.** *(New in v1.2.)* Before any single-run behavioural claim is made at a tier — treatment effect, migration count, breach tally, retention delta — a fresh-vs-fresh pair on identical instrument bytes must exist at that tier, and the claim must survive the measured floor. A tier whose floor is unmeasured produces capacity findings and instrument findings, not treatment effects. The floor itself is registered per tier and re-measured whenever the instrument's bytes change.

**Repository rules absorbed by reference** (defined in `experiments/G0-prime/registration.json`, `risk_register_additions`): R12 (arms B/C are a build with an owner and a budget, not an asset download), R13 (a noise-floor tolerance must be registered before the run that uses it; its cell list is never edited after artifacts exist), R14 (tier curricula are built as a generator and registered before running), R15 (interpreter is a seal component; cross-version comparisons are re-measured, not smoothed), R16 (the set of wall-clock-gated cells is an observed property of an environment; new cells are added by dated amendment naming the revealing artifact, never by editing the original list).

---

## 5. The Gate Ledger (status of record at `ee7416c`)

v1.1 stated prospective go-criteria; the instrument has since spoken. This table is the program's status of record. Verdicts come from the owning ledgers, cited by file:line as verified by the funder's decision report of 2026-11-05. A gate does not reopen history — it prices what remains.

| Gate | Registered question (one clause) | Measured verdict | What remains | Source |
|---|---|---|---|---|
| **G0-prime** | grader shipped and validated, bench noise floor measured on three clones, harness sealed | **CLOSED, conditional** — under R13(a) per D-G0P-02; `learn/1/reasked` and `learn/1/restarted` excluded from the noise-floor claim; `closing_blockers: []`; explicitly *not* closed as "identical row for row" | None. The caveat travels with every number the bench produces. | `G0-prime/registration.json:118` |
| **G1 / MP-E9** | zero untraceable words, three routing rows back to refused, morphology class answered, invariants hold | **PARTIAL / FAIL on P2** — H1, H2 pass (16 rows moved, protections intact); P2 falsified (`ELECTRIC_QA_MORPH_NORMALIZE` moved 0 of 3,672 rows); H3 fails; H4 holds; residual named, not fixed, not attempted a third time | The named residual travels with the duel, measured (`residual_for_the_duel`); three rulings (§7.2 items 8–10) | `MP-E9/registration.json:2631`, `:2613` |
| **G2 / MP-E8** | sealed artifacts for arms A/B/C at 40/120/300 plus teach-arm control and noise floor; forgetting/interference/exposure/cost valid | **FAIL (H1) / PARTIAL** — arm B clause fails at both required tiers; tier-300 sign reversed; H2 clause 1 fails 3/5, clause 2 passes but is satisfiable by blanket refusal; H3 has no instrument; T and N exist at tier 40 only | T & N at 120/300 (~3.85 h); tier-300 fresh-vs-fresh (~44 min); H2 specificity floor by dated amendment; then G2 closes on the re-aimed claim (Amendment B) | `MP-E8/registration.json:4388`, `:4427`, `:4027` |
| **G3 / MP-E10** | mouth stages improve-or-hold, working memory live at seconds scale, replay at tier 300 within the registered interference margin, invariants hold | **UNMEASURABLE as registered** — H3 void at depths 2/3 under the pre-registered saturation guard; 0.0000 pp not quotable as a pass; R6 invariant cell has no tier-300 instrument; no MP-E10 figure scored on the current tree | One ruling (D-MPE10-12) → re-register H3 primary at tier 120; tier 300 becomes the capacity curve (Amendment D); ~2 h of re-registered runs | `MP-E10/results/replay_tier300_summary.json:208-209`; `registration.json:4255`, D-MPE10-12 `:2359` |
| **G4 / MP-E11** | wiring-matters curve at ≥3 tiers with seed CIs, branch decision recorded | **NOT STARTED** — no registration, no run; `experiments/` contains only G0-prime, MP-E8, MP-E9, MP-E10, MP-E12 | Registration after G2/G3 close; unchanged spec | plan `:912-918`; directory listing |
| **G5 / MP-E12** | H1–H3 hold or a pre-registered partial with the text-distillation control done; guarded rows and source dimension verified post-transplant | **BLOCKED on an external input** — "The weights are not on this machine"; four open decisions (D-MPE12-01…04) | Download GPT-2 124M (~500 MB, §7.2 step 2) → E12a opens; rule the four decisions in the batch; E12c registration pins Qwen3.8-27B | `MP-E12/registration.json:2060`, `:1990`, `:1936-1939` |
| **G6 / MP-E13** | all four live axes beaten against both baselines over a 24-hour window, artifacts public | **NOT STARTED** — no registration exists; "MP-E13 requires everything" | Requires G2–G5; now also carries the A10 resource ledger | plan `:926-931`, `:942` |

Dependency chain (plan `:935-936`): G0-prime → G1 → G2 → G3 → G4 → G5 → G6, with MP-E12a in parallel from G0-prime. As measured: G2 and G3 are the two gates with remaining machine work; G5's first stage is unblocked by a download; everything downstream is queued behind rulings that cost zero machine time.

---

## 6. The Experiment Program (MP-E8 to MP-E13)

Six experiments. Each section states: current status (measured), remaining work (priced from measured unit costs), and the amended specification an agent executes. The C-condition pattern remains normative; checklists are in Chapter 12.

### 6.1 MP-E9 — Recognition, Morphology, and the Direct Answer Path

**Status.** H1 and H2 pass: under the live word-level grader, zero untraceable words; 16 rows moved with all protections intact. **P2 is falsified**: `ELECTRIC_QA_MORPH_NORMALIZE` moved 0 of 3,672 rows — the morphology lever, as registered, does nothing. H3 therefore fails; H4 holds. The residual (`residual_for_the_duel`) is named in the ledger, not fixed, and per v1.1's own fallback it will not be attempted a third time: **the duel runs with the residual measured and named.**

**Remaining work.** Three rulings, zero machine time: `3_tier_120_and_300` (whether MP-E9's tier legs run at all, given P2), `4_requirements_txt_pinning` (reproducibility hygiene), and D-MPE9-05 (whether `ELECTRIC_ARBITER_HEAD_BOUND` promotes to BASE — its own precondition is the inertness proof; promoting without it is a listed R2 event and stays forbidden). P-1/P-2, if ruled to run, need an inertness proof plus one re-baseline before any figure is quoted.

**Standing lesson (now R8/R17 case law).** The morphology falsification joins the denominator falsification: two levers that the pre-registration killed before they could contaminate a headline. No flag, organ change, or test was added for either. This is the doctrine working.

### 6.2 MP-E8 — The Three-Arm Duel on the Live Bench

**Status.** Arms A, B, C have sealed artifacts at tiers 40/120/300. The registered forgetting prediction (H1) failed at both required tiers with the sign reversed at tier 300. H2 clause 1 fails 3/5; clause 2 passes but is *satisfiable by blanket refusal* — a hole, not a win. H3 (fluency) has no instrument yet. T and N exist at tier 40 only.

**Remaining work, priced.**
1. **Tier-300 fresh-vs-fresh pair** — 2 × 22.0 min learn-only ≈ **44 min**. Mandatory under R17 before any tier-300 attribution. Until it exists, the 111-row replay-vs-control difference, the 251/302 migration counts, and the 91/92/100 invention-breach tallies are unattributable.
2. **T & N at tiers 120 and 300** — 3 × 23.3 min + 3 × 53.6 min ≈ **3.85 h** (the D-MPE10-04 condition-3 clone set is the same run as the tier-300 N and is counted once).
3. **H2 clause-2 specificity floor** — a dated amendment (R16 mechanism) requiring that a passing refusal rate answer *specific* guarded rows with reasons, so blanket refusal cannot satisfy the clause. Registered before the next scored run.
4. **H3 instrument** — the four mouth stages, wired to the duel's tiers, so fluency stops being the axis with no number.
5. **Rulings D-MPE8-10/-11** (R13 tolerance-adjacent; zero machine time). The R13 tolerance list is never widened after artifacts exist (that is the standing R2 prohibition, ruled as R16's dated-amendment mechanism instead).

**Standing prohibitions (elevated to program law).** None of the following may be taken, in any experiment, now that the data exists: widening R13's tolerance list after seeing which cells disagree; re-specifying a gain or ceiling and then scoring the affected quantity without a pre-run ruling; editing the answer path to make an intermittence test pass and reusing sealed evidence that quotes `reason` strings; promoting a flag to BASE without its own inertness proof; running a new arm against a sealed baseline as though the baseline were the same instrument (measured false: `fresh_vs_fresh_tier120.json:619`, `same_harness_as_the_fresh_runs: false`).

### 6.3 MP-E10 — The Mouth, the Second Timescale, and the Capacity Wall

**Status.** Tier-120 replay measured clean: H3 = 0.0000 pp on 416 rows at every depth, guard silent, prediction held — but not quotable as a tier-300 result. Tier-300 H3 is **void at depths 2 and 3** by the pre-registered saturation guard: 72 entries pushed to the 4.0 ceiling at depth 2 (pass 1 of 2), 156 at ceiling before / 252 pushed during at depth 3. Depth 1 ran clean (13,878 pairs, 2 of 2 passes). The store saturated at tier-300 teaching volume — the prediction that it would not was computed from a tier-40 state. Ruling D-MPE10-12 exists to decide this and is the single item gating G3.

**The ruling, specified.** D-MPE10-12 is ruled exactly as follows (Amendment D): the non-saturating replay gain is registered as a *new, dated configuration before any run* (R2, R16 mechanism); the 2.0 pp margin and the 0.0000 pp reading are preserved under R5 as history; **H3's primary tier is 120**, where the instrument is clean and the guard does not fire; **tier 300 is reported as a capacity finding** — the saturation curve — and never as an interference measurement. Companion rulings in the same batch: D-MPE10-11 (tier-300 admissibility), D-MPE10-05_G2 (whether MP-E10 may run again — ruled yes, under the re-registration), D-MPE10-09 (R6 at tier 300 — route 2 breaks `curriculum_sha256` and is therefore not a route), D-MPE10-10 (H3 phase basis).

**The capacity curve (new, first-class).** From v1.2, every MP-E10 run emits the registered saturation metric: ceiling-hit count by depth and pass, vs. curriculum tier. The program's scaling target is explicit: **3,000 taught items at flat laptop cost**, climbed by re-registering store geometry (gain, ceiling, eviction policy) as dated configurations — each falsifiable, each costing the comparability it spends, exactly as R16 requires. The wall is the objective now.

**Remaining hypotheses (re-registered).** H1: mouth stages improve on at least two, none regressed. H2: fluency improves over the MP-E8 arm-A baseline at the same tier. H3 (re-registered): replay at **tier 120** holds retention at the invariant with interference bounded by the pre-registered margin, *on an instrument whose tier-120 floor is measured* (done: 0.11–0.45%). H4: invariants hold. C-conditions carry over (C1 untraceable word — abort; C2 guarded rows answered — abort; C3 retention/restart regression — abort; C4 working memory leaking across a restart — abort; C5 one routing variant winning only with the other disabled — ablation result, not a win), plus **C6: any tier-300 saturation event during a scored interference run — the run is a capacity datum, not a score.**

### 6.4 MP-E11 — Connectome Scaling: Does the Wiring Matter?

**Status.** NOT STARTED; no registration. Spec unchanged from v1.1 (tiers 20k/50k/100k/200k plastic synapses, pools 12→24, real-versus-random with shared wire-draw code, multiple seeds, CIs). One v1.2 addition: **the capacity curve's storage geometry decisions feed MP-E11's tier planning**, and MP-E11's tiers in turn set the transplant budgets for MP-E12b/c — the dependency v1.1 already registered, now carrying the saturation data too. The twin hypotheses stand: H1 functional (real wiring beats random by a pre-registered margin at one or more tiers) or H2 null (parity — an equally publishable conservation law).

### 6.5 MP-E12 — Frozen Weights as an Addressed Library (Flagship; rewritten by v1.2)

**Objective.** Establish the knowledge-transfer channel no published system has, and run it the way the program has committed to: the donor's weights are **never executed**. They are a read-only, memory-mapped **address space** that the connectome queries at any coordinate, at any time — during compilation *and during deployment* — and understands **as if it were its own knowledge**. Reading is not running; addressing is not inference.

**The doctrine (R11), operationalised.** Three access classes, and only three:

1. **Compile reads (offline, MP-E12a/b).** Budgeted static extractions against the mapped library: embedding geometry (nearest-neighbour structure of the token-embedding matrix → candidate feature pools), association edges (top-k successors read from unembedding and head structure in single matrix operations), circuit motifs (attention heads as directed association maps; MLP neurons as key-value feature detectors). Every item's operation count is logged and sealed under a hard per-item read budget.
2. **Live address reads (deployment, new in v1.2).** The library stays mapped — on disk, read-only — after compilation. At deployment the organ may resolve any address through native probes (spreading activation over compiled pool structure → address resolution → journaled read). Every access is written to the **access journal**: address, tensor, indices, values, requesting probe, timestamp. This is what "the weights are his knowledge" means operationally: the organ does not distinguish a taught row from a library row in *fluency*, and distinguishes them exactly in *honesty* — a library-sourced word is traceable to an address, quotable or refusable, never silently curriculum (R9 as amended by R11).
3. **The control (the rival hypothesis).** The text-distillation arm is the only sanctioned *execution* of the donor in the entire program: the frozen donor is run once, offline, to emit text, and Droso trains on that text through its normal curriculum. Weight-reading must beat or match text-distillation at lower latency and energy; if it does not, the weights carried nothing beyond their own outputs — and that null result is itself the first controlled measurement of its kind.

**Stage MP-E12a — the address space and the calibration donor (opens now).** Donor: **GPT-2 124M** public weights (deliberately the same family as the program's reference opponent; confirmed specs pinned in the registration: n_embd 768, n_layer 12, n_head 12, d_head 64, n_positions 1024, vocab 50257, MLP inner 3072, wte tied). Work: implement the mmap'd read-only address space (safetensors, zero-copy, per-tensor index resolution), the three compile-read extractions under per-item budgets, the access journal, and the latency benchmark (budgeted static read vs. autoregressive inference, identical hardware and query set; the ≥10× threshold is pre-registered and carried over from v1.1). Deliverable: the typed association graph (nodes, edges, confidences) plus the instrument itself — the thing every later stage reuses. **Blocked only by a ~500 MB download (§7.2, step 2).**

**Stage MP-E12b — the weight-to-connectome compiler (+ the live address class).** Compile the association graph through the existing primitives: `grow_pool` for discovered feature clusters; `grow_plastic` and `wire_pool` for association edges, confidence-gated. Every transplanted edge carries a provenance tag — source model, extraction method, confidence, address range — sealed per edge in the ledger discipline the repository already runs. The coverage gate gains its source dimension: `curriculum-learned`, `library-read (compiled)`, and `library-read (addressed)` are distinct classes with distinct refusal policies. Then enable the live address class end to end: probe → resolution → journaled read → answer path, graded word-level throughout.

**Stage MP-E12c — the scale donor: Qwen3.8-27B, and the laptop clause.** Donor: **Qwen3.8-27B**, designated by the funder (2026-11-05), confirmed open-weights: released 2026-08-13/14 on Hugging Face (`Qwen/Qwen3.8-27B`), **Apache 2.0**, dense 27B with hybrid attention, vision encoder included, 262k native context (extensible to 1M), safetensors format; community-confirmed envelopes ≈ 56 GB BF16 / ≈ 28 GB FP8 / ≈ 14–16 GB at 4-bit. Exact tensor inventory and shapes are pinned at registration from the released `config.json` — the plan does not guess them. The addressed-library doctrine is what makes this donor laptop-legal: the library lives on NVMe and is *never fully resident*; only touched pages enter RAM; the mechanism has no VRAM footprint by construction. Registration pins (before download): the residency ceiling (registered maximum peak RSS while mapped; the working target is ≤ 8 GB at any moment, page cache excluded), the disk budget (~54 GB BF16; a quantized copy is legal only as a **separate library with its own registration** — different bytes are different provenance, and the H1 claim must be demonstrated at least once on unquantized bytes), the access-class latency budgets (page-resident reads: microseconds; cold NVMe reads: single-digit milliseconds), and the license record (Apache 2.0, verified at registration).

**Hypotheses (four now).**
- **H1 (transfer).** Droso bootstrapped from the library beats Droso trained on text alone at equal corpus exposure, on paraphrase probes and on acquisition of new material — demonstrated on GPT-2 124M and replicated on Qwen3.8-27B.
- **H2 (latency).** Per-association read cost is at least ten times lower than autoregressive inference for equivalent association queries, on identical hardware — measured for both donors, with the access-class budgets held.
- **H3 (honesty preserved).** Retention stays at the invariant; the refusal suites are unchanged post-transplant; the agent can refuse to ground library-sourced claims; the source dimension works; every answer passes word-level grading with the access journal as the admitted source.
- **H4 (the laptop clause — new).** With the Qwen3.8-27B library mapped: peak RSS stays under the registered ceiling, VRAM = 0 holds on every run (asserted, not assumed), the donor is never executed (R11 audited: no donor runtime import reaches the deployment path), and access latency meets its registered class budgets. This hypothesis is the program goal, stated as a falsifiable measurement.

**C-conditions.** C1: any guarded row answered post-transplant — abort. C2: library-sourced knowledge silently promoted to curriculum class — abort. C3: read budget exceeded on any logged item — abort the extraction. **C4 (new): any donor forward pass detected in the deployment loop — abort, and the mechanism is rebuilt under R11.** **C5 (new): residency ceiling breached or VRAM > 0 on any run — abort the run and re-register the storage configuration.**

**Gate G5.** Full go when H1–H4 hold on both donors with the text-distillation control completed and the source dimension verified. Pre-registered partial: compiler and address space ship as tooling with the transfer result reported exactly as measured. Null: the negative-results paper — the flag is still planted, because a controlled null on weight-reading into a non-backprop substrate does not exist yet.

**What MP-E12 is not.** It never runs the donor for answers, never fine-tunes the donor, never wraps a transformer around Droso, and never leaves the library executable. The only machine in the program that may execute a donor is the control arm's offline batch, once per registration. The connectome remains the only thing that thinks; the library is the shelf it reads from — at any point, instantly, as if the shelf were written in its own hand.

**Known risks (carried and extended).** Representational superposition (donor features share dimensions → noisy edges; mitigated by probe-battery breadth, confidence gating, and the text-distillation control). Semantic drift on compilation (detected by re-testing paraphrase probes post-compile). Abstention corruption (hard condition: refusal suite re-run at G5). New under the addressed doctrine: **address thrash** (a working set that pages continuously — detected by the access journal's hit-rate distribution, mitigated by compile-first coverage), and **provenance blur across library copies** (mitigated by the separate-registration rule for quantized copies).

### 6.6 MP-E13 — The Living System Demo

**Status.** NOT STARTED; requires G2–G5 ("MP-E13 requires everything", plan `:942`). Spec unchanged in substance: a 24-hour live window, ELECTRIC as the teaching interface, both baselines on the same stream, word-level grading live for every arm, accuracy-versus-exposures as the headline figure. Two v1.2 additions: (i) the **A10 resource ledger runs for every arm through the whole window** — peak RSS, VRAM assertion, cost per retained item — so the demo's headline includes the program-goal axis; (ii) the **live address class is part of the demo's arm-A surface**: the window includes queries the organ answers partly by live address reads, with the access journal published beside the stream logs. C-conditions carry over (C1 untraceable word — pause; C2 guarded row answered — pause; C3 restart loses taught material — pause); new **C4: residency ceiling or VRAM breach during the window — pause the window.**

---

## 7. Milestone Gates and Execution Order

The program runs on gates, not dates. A gate opens when its experiment opens and closes when its go-criteria are met and its decision record is written. One experiment in flight (R4), with MP-E12a as the single sanctioned parallelism — open now, since G0-prime is closed.

### 7.1 Gate criteria, v1.2

| Gate | Closes when (all required) | On fail |
|---|---|---|
| **G0** | RECORDED CLOSED (battery-era harness freeze). No agent re-opens or re-does it. | — |
| **G0-prime** | CLOSED, conditional (R13(a), D-G0P-02). The exclusion of `learn/1/reasked` and `learn/1/restarted` and the NOT-REPRODUCIBLE floor caveat travel with every bench number. | — |
| **G1** | The three MP-E9 rulings are made; the named residual's measured value is written into the duel's decision record as a known, bounded asterisk. | Already recorded honestly; nothing to fail. |
| **G2** | T & N exist at tiers 120/300; the tier-300 fresh-vs-fresh pair exists and the floor is registered (R17); H2's specificity floor is registered and re-scored; the H3 mouth-stage instrument produces numbers at all three tiers; all artifacts sealed. Claims close under the re-aimed structure (Amendment B), with the H1 falsification recorded beside them. | Re-run the flawed arm only; no specification edits mid-run. |
| **G3** | D-MPE10-12 ruled and implemented (new dated, non-saturating replay configuration); H3 scored at tier 120 primary on the measured floor; the capacity curve emitted at tier 300; invariants hold. | Legacy organ stays; routing ablation decides the next attempt. |
| **G4** | Wiring-matters curve at ≥3 tiers with seed CIs; branch decision (functional or null) recorded. | The 50k tier stands alone; 200k deferred with cause. |
| **G5** | H1–H4 hold on both donors; text-distillation control completed; guarded rows and the source dimension verified post-transplant; access journal published. | Compiler and address space ship as tooling; negative-results paper. |
| **G6** | All four live axes **and A10** beaten against both baselines over the 24-hour window; artifacts public, including the access journal and the resource ledger. | One re-registered extension; then claims are re-scoped. |

### 7.2 The execution order, priced from measured unit costs

| Step | Action | Cost | What it buys | Gate |
|---|---|---|---|---|
| 0 | **The ruling batch** — 11 PI items in dependency order (texts in B.R) | 0 machine time; one sitting | Unblocks G3 (D-MPE10-12), G2's amendment path, MP-E9's disposition, and MP-E12's four open decisions | All |
| 1 | **A10 resource-ledger instrumentation** — peak-RSS sampler, VRAM assertion, cost-per-retained-item, wired into the bench with tests | Small code, no bench time | The program-goal axis becomes measurable before the next scored run | all subsequent |
| 2 | **Download GPT-2 124M** (~500 MB) | ~10 min | MP-E12a opens immediately (R4 parallelism); the flagship stops being blocked on "weights not on this machine" | G5 |
| 3 | **Tier-300 fresh-vs-fresh pair** (2 × 22.0 min learn-only) | ~44 min | The tier-300 identical-code floor; R17 satisfied at tier 300; attribution un-bounded for the 111-row, 251/302 and 91/92/100 figures | G2 |
| 4 | **T & N at tiers 120/300** (3 × 23.3 min + 3 × 53.6 min; tier-300 clone set counted once with D-MPE10-04 condition 3) | ~3.85 h | The duel's missing controls at scale; G2's artifact set completes | G2 |
| 5 | **Re-registered replay configuration, tier 120 primary** | ~1.3 h per configuration at tier 300; tier-120 primary cheaper | H3 scored on a clean instrument at its primary tier; the 2.0 pp margin's successor pre-registered | G3 |
| 6 | **Mouth-stage instrument wired to the duel tiers** | Small machine time | H3 (fluency) stops being the axis with no number | G2 |
| 7 | **Licensed-absence targeted fix + one re-baseline** | 852.01 s measured | The program's only live honesty defect closed, with the covering run superseded exactly once | G1/audit |
| P | **MP-E12a parallel track** from step 2 onward; E12c registration (pins Qwen3.8-27B, runs the disk-feasibility check, decides the download) after E12a's machinery validates | GPT-2: ~500 MB; Qwen3.8-27B: ~54 GB disk (BF16), decided at registration | The addressed library: address space, compile reads, access journal, latency benchmark — then the scale donor | G5 |

Sequencing logic: rulings first because they are free and gate everything; the two cheap purchases (download, floor pair) next because each unblocks an entire attribution class or experiment; T & N before re-registration because the clone set is shared; the answer-path fix last because it supersedes the covering run and must happen exactly once. MP-E12a touches no Droso organ and may proceed from the moment the GPT-2 weights land.

---

## 8. Evaluation Harness and Pre-Registration Discipline

### 8.1 The two-instrument doctrine, now with a floor

The program measures on two instruments and argues from neither alone. The **frozen battery** (24 asks, 18-row probe journal, 4 guarded invariants; 19/24 stable across 26 generations) is the regression guard. The **electric bench** (taught curriculum, real restarts, phrasing matrices, three arms, depths 1/2/3, tiers 40/120/300) is the capability instrument. Every capability claim cites the bench; every regression claim cites the battery; ELECTRIC runs with the battery only as a guard, off by default, because the gen-24 verdict LOST is part of the record.

v1.2 adds the third layer, which is not a third instrument but a property of each: **the floor**. At every tier where a behavioural claim is made, a fresh-vs-fresh pair on identical instrument bytes must exist (R17), and the claim must survive the measured floor. At tier 120 the floor is measured: 0.11–0.45% of graded asks move with no treatment, confined to depth-3 refusal classes. At tier 300 it is not — which is why step 3 of the execution order exists, and why no tier-300 figure is quotable as a treatment effect today. The word-level grader audits both instruments; the access journal audits the library; the resource ledger audits the laptop.

### 8.2 The ten axes

Registration files may add axes but never remove or redefine these. Baselines marked *measured* are repository values; *computed at G2/G3* are fixed by the duel and the mouth.

| Axis | Definition | Instrument | Current baseline (2026-11-05) |
|---|---|---|---|
| A1 Acquisition | accuracy on newly taught material after first exposure | bench probe matrices per tier | Measured: 115/124 live correct at depth 3, tier 40; tier scaling in artifacts |
| A2 Retention | accuracy on earlier material after later training, across restarts | forgetting curves, restart deltas, replay audits | Measured: 20/20; zero gained/lost across restarts; 20/20 after 600 replays; zero interference, three cycles at 40 items |
| A3 Paraphrase | recognition of rephrased probes of taught material | battery 14-probe journal (guard); bench phrasing matrices | Measured: battery 0–1 of 14 (flag off); bench 20/20 held-out frames; reverse-role 4/20 |
| A4 Refusal | correct abstention with valid reasons | guarded invariants; guarded-absence rows | Measured: 4/4 battery; 24 bench rows; **live defect: licensed absence 5.00% [2.74, 8.96], fix scheduled (Amendment G)** |
| A5 Fluency | generation quality under staged failure evaluation | four mouth stages | Baseline set at G2 (instrument wired, §7.2 step 6); expected to trail arms B/C by a recorded margin |
| A6 Adaptation speed | accuracy as a function of exposures during deployment | accuracy-versus-exposures curves | Measured curve at tier 40: 37/71/108 → 38/75/115; **structurally flat for frozen arms** |
| A7 Backward transfer | interference of new material on old | per-session deltas; replay audits | Measured: 0.0000 pp at tier 120 on 416 rows, guard silent; tier 300 = capacity finding (Amendment D) |
| A8 Refusal calibration | quality of the abstention boundary, for all arms | calibration curves; arm C retrieval-empty case | H2 clause 1 fails 3/5; clause 2 re-scored under the specificity floor (§6.2) |
| A9 Cost per learned fact | synapse updates, wall-clock, energy per acquired fact | instrumented harness, identical hardware | Measured unit costs (§3.1); arm-B optimizer cost comparison computed at G2 |
| **A10 Resource cost** *(new)* | peak RSS per phase, VRAM = 0 asserted per run, cost per retained item across restarts | **the resource ledger** | **Not yet measured on any registered run — first registered on the next bench run (Amendment F; the v1.2 gap-closer for the program goal)** |

### 8.3 Registration protocol and artifact standard

Unchanged from v1.1, with three additions. Before the first run of any experiment, a registration file is committed and hashed: hypotheses with directional predictions and thresholds; arms with seeds; metric definitions referencing §8.2; C-conditions with measured triggers; stopping rules; analysis plan; harness version hashes. Nothing in the file changes after results exist; discoveries are carried by dated amendment (R16). The artifact standard per experiment (`experiments/MP-Ex/`): `registration.json`, `results/`, `figures/`, `decision.md` — all committed or re-derivable (R10), sealed per row. Additions: (i) every artifact that quotes a behavioural figure at a tier carries the **floor registration** for that tier; (ii) MP-E12 artifacts additionally carry the **access journal** and the read-budget logs; (iii) every bench run from v1.2 onward carries the **resource ledger** (A10).

---

## 9. Risk Register

Live risks first. Likelihood and impact are planning judgments, revisited at every gate.

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Ruling-queue bottleneck**: 11 PI items wait on one human who is also the funder | High (live) | Medium | Batch in one sitting with B.R's recommended texts; the dependency order is fixed; zero machine time is lost to waiting on anything else meanwhile |
| **Amendment cost**: every re-registration converts sealed evidence into history | High (structural) | Medium | R16's dated-amendment mechanism; amend only what the finding forces (D-MPE10-12's gain; H2's specificity floor); never widen R13's list; preserve superseded text under R5 |
| **Saturation wall**: the store's capacity ceiling caps interference claims and the 3,000-item target | High (measured) | High | The saturation curve as a first-class metric; store-geometry re-registrations (gain, ceiling, eviction) as dated configurations; MP-E11 tiers inform capacity budgets |
| **Address thrash** (MP-E12): a working set that pages continuously destroys the latency budget | Medium | High | Compile-first coverage so most answers never touch the library; the access journal's hit-rate distribution detects it; residency ceiling enforced at C5 |
| **Quantized-copy provenance blur**: a 4-bit Qwen copy silently substitutes for the BF16 library | Medium | High | A quantized copy is a separate library with its own registration; H1 must hold at least once on unquantized bytes; provenance tags carry the library identity |
| **Donor-execution leak** (R11 violation): a convenience call to a donor runtime reaches the answer path | Low | Critical | C4 audits the deployment path for donor runtime imports; the control arm's execution is offline, batch, and the only sanctioned one |
| **Licensed-absence defect**: 5.00% intermittent flip, live in a green suite | Medium (measured) | High | Characterised (n=200, Wilson CI, seeds ruled out, safety intact); targeted fix scheduled last with one re-baseline; green ≠ closure is doctrine |
| Flag jungle | Medium | Medium | Fold flags into registered modes (`ELECTRIC_LEARN` precedent); every new flag ships with C-conditions and tests |
| Word-level grader blind spots | Medium | High | R9 abort conditions everywhere; novel classes become regression pins, never silent patches |
| The duel shows Droso behind on more axes than expected | Medium | Medium | Both outcomes define paper 1; the re-aimed claims (curves, cost, capacity) are the ones the duel can actually lose; R5 records losses as assets |
| The new mouth composes fluent falsehoods | Medium | High | Coverage gate stays the sole authority on answering; R9 audits generation; refusal suite re-runs at G3 |
| Scaling shows wiring never matters (null at all tiers) | Medium | Medium | Pre-registered as publishable; frees the substrate-budget narrative for MP-E12 |
| Donor superposition blurs weight extraction | High | Medium | Probe-battery breadth; confidence gating; text-distillation control bounds the claim |
| Transplanted knowledge corrupts abstention | Medium | High | Source dimension in the coverage gate; refusal suite re-run at G5 is a hard condition; library knowledge quotable or refusable, never silently curriculum |
| Compute or disk overrun (200k tier; Qwen3.8-27B ~54 GB) | Medium | Low | Staged tiers; deferral with cause registered; disk-feasibility check before the scale download |
| Scope drift; experiments multiply | Medium | Medium | R4: one experiment in flight; MP-E12a is the only sanctioned parallelism |

---

## 10. Publication and Strategy Framing

**Paper 1 (after G2 and G3 close).** *A connectome agent that learns during deployment: what a living system holds, what it refuses, and what it still cannot do.* The spine is now stronger for the honesty: the duel measured that neither the live arm nor the frozen-plus-retrieval arm catastrophically forgets at 120–300 items — and the paper says so in its abstract, because the claim that survives is sharper: **levels can hold while curves diverge**. Arm A climbs its exposure curve, holds retention across real restarts at the invariant, refuses with calibratable reasons, and pays a measured cost per retained fact on laptop hardware; arms B and C hold levels with curves that cannot move, at cost structures the resource ledger prices. The repairs (recognition, the direct path) supply method; the losses on fluency are reported in the same breath as the wins.

**Paper 2 (after G4).** *Does the wiring matter?* Unchanged: plasticity scaling and the functional role of connectome topology, real-versus-random with shared wire-draw code, functional or null.

**Paper 3 (after G5 and G6).** *Reading frozen weights without running them: the addressed library.* The flag-plant, now with the doctrine the funder directed: the first system that treats a trained network's weights as a permanently addressable, read-only knowledge library — compiled into a living substrate by local rules, queried at any coordinate during deployment through journaled reads, executed by no one — demonstrated on GPT-2 124M and replicated at 27B scale on Qwen3.8-27B, with the laptop clause (H4: residency ceiling, VRAM = 0, latency budgets) as the headline result and the text-distillation control setting the standard any follow-up must meet.

The program brand is the discipline: pre-registered, gate-driven, word-level honest, nulls and voids published. The one-line thesis for talks and read-me files: **it learns during deployment without gradients, forgets nothing across restarts, refuses what it was never taught — and reads other networks' weights without running them, at any point, as its own library.** Every clause is backed by a registered instrument or a scheduled experiment, and the honest negatives — six closed retrieval levers, one aborted experiment, one measured LOST verdict, the P2 falsification, the G2-H1 falsification with its sign reversal, the tier-300 H3 void — are part of the brand, not exceptions to it.

---

## 11. Appendix A: MP-E12 Technical Primer — Addressing Weights Without Running Them

### A.1 What a frozen model knows statically

A transformer checkpoint contains at least three readable structures, and all of them are *addresses* before they are anything else. The token-embedding matrix is a geometric map: tokens used in similar contexts sit near each other, so nearest-neighbour searches over the raw matrix expose lexical and semantic neighbourhoods without a single forward pass. The unembedding directions and the attention heads encode association: for a probed token, the strongest successors can be read from these structures with one small matrix operation each. The MLP layers act as key-value memories: presented with a probe vector, the top-responding neurons are the features the model associates with the probe, and their output directions are the values those features write.

Under R11 these reads are organised as an **address space**. An address is `(tensor_id, indices)` — a layer, a matrix, a row, a column. Resolution is arithmetic on a memory-mapped file, not computation: the library has no forward pass to run, and the organ that reads it performs the same class of operation it already performs on its own plastic stores. None of these reads involves generation. Each is a bounded set of matrix-vector products or similarity searches against frozen matrices — a dictionary lookup in a very large, very strange dictionary that stays on the shelf between lookups.

### A.2 The donors

**Calibration donor — GPT-2 124M.** Public weights; the same family as the program's reference opponent; small enough to validate every mechanism cheaply. Pinned in registration: n_embd 768, n_layer 12, n_head 12, d_head 64, n_positions 1024, vocab 50257, MLP inner 3072, wte tied. Blocked only by the ~500 MB download (§7.2 step 2).

**Scale donor — Qwen3.8-27B** (funder-designated 2026-11-05). Confirmed public facts, recorded here so no agent has to guess: released 2026-08-13/14 on Hugging Face as `Qwen/Qwen3.8-27B`; **Apache 2.0**; dense 27B with hybrid attention; a vision encoder included (the release is multimodal); 262k native context, extensible to 1M; safetensors distribution; community-confirmed envelopes ≈ 56 GB BF16, ≈ 28 GB FP8, ≈ 14–16 GB at 4-bit. Pinned **at registration, from the released `config.json`** — the plan does not guess them: the full tensor inventory and shapes, the layer/tensor naming scheme the address space will expose, and the vision tower's disposition (addressable like any other tensor; probed only if a registered extraction uses it). The download decision runs the disk-feasibility check first; a quantized copy is a separate library with its own registration, and the H1 claim must hold at least once on unquantized bytes.

### A.3 Access classes, budgets, and the benchmark

Three access classes, and only three (R11): **compile reads** (offline, budgeted, sealed — the extractions of §6.5), **live address reads** (deployment, journaled, latency-budgeted), and **the control's one offline execution** (the rival hypothesis, once per registration). Budgets are per class and registered: a maximum operation count per probed association for compile reads; a maximum resolution-plus-read time per access class for live reads (page-resident: microseconds; cold NVMe: single-digit milliseconds). The benchmark compares, on identical hardware and an identical association query set: static reading (the budgeted extraction) against autoregressive inference (the donor generating the association token by token). Reported quantities: wall-clock, operation count, energy estimate. The pre-registered threshold for H2 is that reading is at least **ten times cheaper per association** than inference — now measured for both donors.

### A.4 Residency: the laptop law

The library lives on disk, mapped read-only, and is **never fully resident**. Only touched pages enter RAM; the resident set is whatever the working set is, and the working set is measured: the access journal's hit-rate distribution is the early-warning instrument for address thrash (§9). The registered ceilings: maximum peak RSS while the library is mapped (working target ≤ 8 GB at any moment, page cache excluded, pinned at registration), VRAM = 0 on every run (asserted by the harness, not assumed), and the disk budget checked before the scale download. This is the clause that makes a 27B donor laptop-legal — not compression, but the refusal to run or hold what can be addressed.

### A.5 Compilation into the connectome

The association graph compiles through the existing primitives. Cluster centroids from the embedding geometry become `grow_pool` calls; association edges become `grow_plastic` and `wire_pool` calls with weights scaled by extraction confidence. Two planning inputs come from MP-E11: how many edges fit at each plasticity tier, and whether real wiring carries spread better than random wiring at the relevant tier. Provenance is compiled in, not appended later: every library-sourced edge is tagged with source model, extraction method, confidence and address range — sealed per edge. The coverage gate treats the tag as a distinct source class with its own refusal policy; under the live address class, the access journal is the admitted source that word-level grading (R9) accepts.

### A.6 Failure modes and honesty guarantees

Five are pre-registered. **Superposition**: donor features share dimensions, so extracted edges may be noisy — detected by probe-battery agreement checks, mitigated by confidence gating. **Semantic drift**: compiled edges may shift meaning as they settle into the SAN — detected by re-testing the paraphrase probes after compilation. **Abstention corruption**: the agent may behave as if it knows things it cannot ground — detected by the refusal suite re-run, a hard condition at G5, graded at word level. **Address thrash**: the working set pages continuously and the latency budget dies — detected by the access journal's hit-rate distribution, mitigated by compile-first coverage and the residency ceiling. **Provenance blur**: a quantized or derivative copy silently substitutes for the registered library — prevented by the separate-registration rule and library identity in every provenance tag. The standing mitigation behind all five is the same: the source dimension. Library-sourced knowledge can be quoted or refused, but it is never silently promoted to curriculum knowledge.

---

## 12. Appendix B: Agent Execution Checklists

Each checklist is directly pasteable to a coding agent. A checklist is complete only when every step has a checked artifact behind it.

### B.0 Closing a Gate (applies to every gate)

1. Verify all artifacts exist: `registration.json` (hash recorded before the first run), `results/`, `figures/`, `decision.md` — all committed or re-derivable from committed scripts (R10), sealed per row.
2. Verify results JSON against the versioned schema; verify seals (git commit, interpreter, live-state) on every journal row; reject hand-edited numbers and unsealed rows.
3. Verify the **floor registration** for every tier a behavioural figure is quoted at (R17); a figure without a floor is an instrument finding, not a result.
4. Verify the **resource ledger** (A10) ran: peak RSS recorded, VRAM = 0 asserted, cost per retained item computed. Missing A10 data fails the gate from v1.2 onward.
5. Evaluate every registered C-condition row by row and record each verdict in the decision record.
6. Check invariants explicitly: R6 (retention and refusal unchanged or improved; guarded 4/4; guarded-absence rows intact) and R9 (word-level traceability audit passed; for MP-E12 artifacts, the access journal reconciles with every library-sourced word).
7. Log any retracted claim beside the claim it corrects.
8. Close the gate in the program log; only then open the next experiment.

### B.R The 2026-11 Ruling Batch (PI, one sitting, zero machine time)

Rule in this order; each item names the ruling this plan recommends, all of them dated amendments under R16 — never edits to sealed lists.

1. **D-MPE10-12** (H3 void at its own tier). Rule option 1 as specified in §6.3: new dated non-saturating replay configuration; H3 primary at tier 120; tier 300 = capacity finding; 2.0 pp margin and 0.0000 pp reading preserved under R5.
2. **D-MPE10-11** (tier-300 admissibility). Rule tier-300 figures admissible *as capacity and instrument findings only* until the fresh-vs-fresh pair exists (R17).
3. **D-MPE10-05_G2_is_not_closed** (whether MP-E10 may run again). Rule yes, under the re-registration of item 1.
4. **D-MPE10-09** (R6 at tier 300). Rule route 2 out (it breaks `curriculum_sha256`); the R6 invariant cell is measured at tier 120 and the tier-300 R6 question joins the capacity curve.
5. **D-MPE10-10** (H3 phase basis). Rule the phase basis fixed in the new registration before the first re-run.
6. **D-MPE8-10** / 7. **D-MPE8-11**. Rule per R16: no tolerance widening; any newly gated cell enters the dated observed-wall-clock block naming its artifact; replicates, if bought, are priced 53.6 min each.
8. **MP-E9 `3_tier_120_and_300`**. Rule the tier legs merged into the duel's remaining machine work only where the duel needs them (T & N); no separate MP-E9 tier campaign while P2 stands falsified.
9. **MP-E9 `4_requirements_txt_pinning`**. Rule yes; it is hygiene, cheap, and protects every future seal (R15 interplay).
10. **D-MPE9-05** (arbiter head bound to BASE). Rule: promote only after the inertness proof exists; until then it stays flag-gated (the R2 prohibition is standing law).
11. **D-MPE12-01…04**. Rule: E12a proceeds on GPT-2 124M now; the address space and access journal are registered as instruments (R10) before the first extraction; E12c registration pins Qwen3.8-27B with the residency ceiling, latency budgets, disk-feasibility check and license record of §6.5.

### B.1 G0-prime — RECORD ONLY

Nothing to build. Agents must not re-run, re-measure, or "improve" the closure: it is conditional (R13(a), D-G0P-02), the exclusions are part of the record, and `noise_floor_verdict = NOT REPRODUCIBLE` stands beside the ruled verdict as the honest wording. The only permitted action is citing it correctly.

### B.2 MP-E9 — Residual Disposition

1. Carry the three ruling outcomes of B.R items 8–10 into `decision.md`.
2. Record the named residual (`residual_for_the_duel`) verbatim into MP-E8's decision record as a bounded asterisk on every affected figure.
3. If P-1/P-2 are ruled to run: register the inertness proof and one re-baseline first; no figure is quoted before both exist.

### B.3 MP-E8 — Completing the Duel

1. Buy the tier-300 fresh-vs-fresh pair (2 × learn-only, ~44 min); register the resulting floor; re-emit the tier-300 attribution table with the floor bound applied to the 111-row, 251/302 and 91/92/100 figures.
2. Run T & N at tiers 120/300 (~3.85 h); clones must match within the registered floor before treatment rows count.
3. Register the H2 clause-2 specificity floor as a dated amendment; re-score H2 on the existing sealed artifacts under the new clause; record both scores (before/after) in `decision.md`.
4. Wire the four mouth stages to the duel's tiers; produce H3 numbers at all three tiers.
5. Emit the re-aimed claims table (levels vs. curves; cost per retained fact; capacity) beside the original H1–H4 verdicts, under R5.
6. Write `decision.md`; G2 closes per §7.1.

### B.4 MP-E10 — The Re-Registration

1. Implement D-MPE10-12 as ruled: new dated, non-saturating replay configuration (gain chosen and registered before any run); register the H3 primary tier as 120.
2. Run the re-registered replay at tier 120; score H3 against the measured tier-120 floor; verify invariants.
3. Emit the capacity curve at tier 300: ceiling-hit counts by depth and pass, vs. tier; classify the run as a capacity datum (C6).
4. Register store-geometry variants (gain, ceiling, eviction policy) as dated configurations on the path to 3,000 items; each carries its own C-conditions.
5. Write `decision.md`; G3 closes per §7.1.

### B.5 MP-E11 — Connectome Scaling (unchanged, for the record)

1. Tiered budgets 20k/50k/100k/200k with checkpointing; pools 12→24; archived 3k/10k points carried on the same curve.
2. Shared wire-draw code between real and random arms; only the topology source differs.
3. Register seeds, tiers and the functional-margin threshold in advance; run with multiple seeds and CIs.
4. Emit the wiring-matters curve; record the functional-or-null branch; write `decision.md`.

### B.6 MP-E12 — The Addressed Library

1. **Open the track** (G0-prime is closed; R4 parallelism): confirm the GPT-2 124M weights are on the machine (§7.2 step 2); if not, download and record the hash.
2. **Build the address space**: read-only mmap over safetensors; per-tensor index resolution; zero donor runtime on the deployment path; unit tests for address arithmetic and out-of-range refusal.
3. **Build the access journal**: every read logged (address, tensor, indices, values, requesting probe, timestamp); journal schema versioned and committed (R10).
4. **Compile reads**: the three extractions (embedding geometry, association edges, circuit motifs) under per-item read budgets; operation counts logged and sealed; emit the typed association graph to a versioned schema.
5. **Latency benchmark**: budgeted static reads vs. autoregressive inference, identical hardware and query set; the ≥10× threshold pre-registered; report wall-clock, operations, energy for both donors when available.
6. **Compiler (E12b)**: `grow_pool` from clusters; `grow_plastic`/`wire_pool` from edges, confidence-gated; provenance tags (source model, method, confidence, address range) sealed per edge; coverage-gate source dimension with the three classes.
7. **Live address class**: probe → resolution → journaled read → answer path; word-level grading with the journal as admitted source; refusal policy for library-sourced claims registered before enabling.
8. **Control**: one offline text-distillation run per registration — the only sanctioned donor execution.
9. **E12c registration**: pin Qwen3.8-27B (tensor inventory from `config.json`; residency ceiling; latency budgets; disk feasibility; license record; separate registration for any quantized copy); download after the feasibility check passes.
10. **Verify H1–H4** on both donors; verify C1–C5 row by row; emit before-and-after paraphrase and acquisition figures, the resource ledger, and the access journal; write `decision.md`.

### B.7 MP-E13 — The Living System Demo

1. Build the 24-hour stream harness: live teaching through ELECTRIC, interference probes, unanswerables, paraphrase probes in unseen words — plus queries answered partly by live address reads.
2. Wire both baselines to the same stream; word-level grading live for every arm.
3. Run the resource ledger for every arm through the whole window; snapshot plastic synapses at fixed intervals; keep replay tapes and the access journal.
4. Freeze protocol, thresholds and C-conditions (including C4: residency or VRAM breach pauses the window) before the window opens.
5. Emit accuracy-versus-exposures and the A10 headline (cost per retained item) as the figures; verify all four live axes plus A10 against both baselines; publish artifacts; write `decision.md`.


