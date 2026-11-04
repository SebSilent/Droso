# Decision brief: D-MPE10-03, D-MPE10-04, D-MPE10-05

One page, for the PI to rule on. Every number below is measured and named; nothing here recommends a choice
on evidence that does not exist, and the evidence that does exist is marked as such.

---

## D-MPE10-03 -- which routing variant is primary

**The options.** (a) confirm variant_ii primary, variant_i the ablation, as registered; (b) swap: variant_i
primary; (c) run them as a compound and register the compound as primary; (d) defer until the house wiring
exists.

**What each costs.** A ruling costs zero machine time. The scored consequence is B.4 step 4 (four mouth-stage
evaluations + the nine-axis suite + the state-only / spread-only / state-plus-spread ablations): the bench at
tier 40 runs ~8 min per arm as measured for MP-E8, and the nine-axis suite is the ~13 min run already
priced. Deferring costs the same later and buys nothing.

**Measured evidence.** `experiments/MP-E10/results/routing_ablation_instrument_level.json` (6 probes, k=8,
all four flags): the variants disagree on the winner on **5 of 6** probes; variant_i's win survives only
against `off` on **3 of 6**; all four flags agree on **1 of 6** (the repeated-token probe, where the state is
unambiguous); and **the `both` condition returned variant_ii's winner on every probe**.

**What that does to the choice.** The two variants are not additive: a mask excludes candidates *before* a
drive can rank them, so variant_ii **subsumes** variant_i whenever both are enabled. Option (c) is therefore
not a third mechanism -- it is variant_ii with dead arithmetic attached, and it should not be registered as
though it were a combination. The real choice is (a) versus (b), and it is a choice about what selection is
*allowed to do*: (ii) can veto pools (12 pools, floored at 3 legal, so 9 of 12 candidates were excluded on the
probe above), (i) can only re-weight among options that all remain legal. That is a design question about
whether the sequence organ should ever be able to make a word illegal, which is the PI's call and not the
measurement's. C5 still governs the reporting: whichever wins, it wins against a disabled alternative, so a
scored win is an ablation result.

**Uncloseable while open.** B.4 step 4 cannot be scored (no primary, so no "the other disabled"), and G3's
`go_if` = H1-H4 hold cannot begin. Step 3 itself is now DONE and sealed regardless of the ruling.

---

## D-MPE10-04 -- the interference margin for H3

**The options.** (a) adopt a margin derived from measurement; (b) adopt MP-E8's precedent of 5 pp; (c) refuse a
margin and let H3 be reported as an interval.

**The derivation for (a), shown rather than asserted.** Three measured inputs:
- clone disagreement (the registered noise floor): **11 rows of 3,672 = 0.2996 pp**
  (`experiments/MP-E8/registration.json` `arms.N.registered_criterion`), re-verified on the current tree as
  differences of [0, 1, 0] rows against clones 1/2/3, the single movement inside the R13 time-dependent cell;
- tier-40 interference: **0 regressions over 3 cycles x 53 items = 159 exposures**;
- a zero-event rate over n=159 has a 95% upper bound of 3/n by the rule of three = **1.887 pp**.

So the tightest margin the existing data can distinguish from "no interference observed" is ~1.9 pp, and
**2.0 pp** is that bound rounded up. It is **6.7x** the measured clone noise, which is the property MP-E8's 5
pp margin was chosen for (its own words: 5 pp "is >16x the noise floor"). Row equivalent: 2.0 pp of the
136-row tier-40 probe matrix = **2.7 rows**; at tiers 120 and 300 the row count must be read off the built
curriculum files, not scaled from 136, and the artifact should carry the row count it divided by.

**The honest limit of that derivation.** The bound is a statement about what tier-40 data can show, not a
prediction about tier 300. A 2 pp margin at tier 300 is a *tighter* test than 5 pp would be, so (a) is the
more demanding option, not the lenient one -- if interference is real and scales with corpus size, 2 pp will
fail it; if the PI prefers a margin that tier-40 zero-events cannot be confused with a pass, (b) is the
conservative choice and costs nothing but rigour. (c) is defensible if the PI wants H3 reported as measured
rather than gated, but it changes H3 from a go-criterion into a description, which is a plan amendment, not a
ruling.

**What each costs.** A ruling costs no machine time. Step 2's runs after it: arm A at tier 120 ~23.5 min and
tier 300 ~53.7 min as measured, plus the replay passes on top (a pass costs what a teaching cycle costs --
measured below at ~1 exposure per pair per pass), so ~1.3 h+ serial per replay configuration.

**Uncloseable while open.** H3 (`replay at tier 300 holds retention at the invariant with interference bounded
by the pre-registered margin`) and B.4 step 2 (episodic replay at tiers 120 and 300 *with the registered
interference protocol*) -- the protocol cannot be registered without the number.

---

## D-MPE10-05 -- the replay write path, with the line sites

**The rule as it actually exists.** `organs/sequence_organ.py:174-216`: for each adjacent pair, the lit cells
of slot i and slot i+1 are crossed and every resulting entry takes `new = old + lr`, `lr = LEARN_LR x (1 +
reward)` with `LEARN_LR = 0.35` (`:76`), clamped at a hard ceiling of **4.0** written literally at **`:206`**.
Counters `transitions` (`:213`) and `sequences_learned` (`:214`) advance on every call. Readout uses
*absolute* gates: `SUCCESSOR_FLOOR = 0.12` (`:77`) and `SUCCESSOR_MARGIN = 0.35` (`:83`).

**The options, and the measured behaviour of the first one.**
- **(A) replay = re-call `learn_sequence`.** Zero new organ code. Measured (`_tmp/measure_replay_rule.py`, a
  from `tools/mp_e10_replay_rule_probe.py`, sealed at
  `experiments/MP-E10/results/replay_rule_saturation_probe.json`; deterministic 53-sequence corpus, the real
  rule, n_slots=8): after 3 cycles all **7,632** entries sit at exactly **1.05**, and `distinct_weight_values`
  is **1** at every pass -- mean equals max equals min, because a constant lr makes replay a **uniform
  translation**, not a selective strengthening. Every entry reaches the **4.0 ceiling after 9 replay passes**
  from that state (11 from a single teaching cycle), at which point `share_at_ceiling` is 1.0, the chain has
  **no ranking left at all**, and `grew` is false forever after. Replay past saturation is a literal no-op that
  still moves the counters: at 30 passes `sequences_learned` rose **+1,590** (it counts calls, not changes)
  while `transitions` rose only **+1,908** against the 6,360 an honest count would give -- the drift is
  self-hiding, because the counter that saturates is the one that would show it.
- **(B) a dedicated replay entry** applying the same delta with a replay gain, advancing no teaching counter.
  Costs a new method on a live organ (an organ change: design step + inertness proof, the same shape as
  `docs/h4_updates_counter_design.md`, ~50 min machine for fingerprint identity + noise floor + batteries).
- **(C) replay through the plastic three-factor path** -- `connectome/rate_core.py:580` and `:620`, writing at
  `:592` and `:629`. This is a *different* engram system (mushroom body, eligibility-trace based), so it does
  not satisfy "the same local rule that wrote the engrams" for sequence material. Listed for completeness.

**The finding that should decide it, whichever way.** Under (A) the mechanism cannot express what replay is
normally for: with a constant lr and no per-item signal, replay raises every visited pair by the same amount,
so it cannot strengthen one engram relative to another. It does two other things, both real: it carries pairs
across the absolute floor/margin gates (`SUCCESSOR_FLOOR = 0.12`, `SUCCESSOR_MARGIN = 0.35`), and past the
ceiling it flattens the ranking that readout depends on -- `distinct_weight_values` stays at **1** all the way
to saturation, so there is no pass at which replay creates a distinction the organ could read. So a
pass-count limit is not an optimisation under (A), it is a precondition -- and
if the PI wants selective consolidation, only (B) can express it.

**Uncloseable while open.** B.4 step 2 has no implementable form (the mechanism is undefined), and H3 depends
on step 2. Nothing else in G3 waits on -05.

---

## What is NOT in this brief, deliberately

No mouth-stage or nine-axis figure is quoted, because none exists on the current tree for the routing flags:
the ablation above is instrument-level over a labelled stand-in geometry, and its quoting guard forbids using
it as a scored result. No synthetic MP-E12 figure appears anywhere. And the house-side routing wiring --
`connectome/engine.py:110 decide(code, text, allowed_pools, extra_drive)`, the `scent` parameter of
`organs/neural_language.py:6225`, existing call site `world/reasoning_agent.py:1334` -- is named-missing in
MP-E10's registration and is a separate organ change, not a sub-choice of -03.
