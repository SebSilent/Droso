# Design step: the H4 updates counter (arm A synapse updates per taught fact)

**Status: DESIGN ONLY. Nothing here is implemented.** It edits the write path, which is an organ change, and
this repository's standing rule for organ changes is that they arrive as a registered design step the PI can
accept or reject in one line -- the precedent that kept MP-E9's PRE-1 separate, kept the sim_floor cells from
being absorbed quietly, and is the reason D-MPE10-08 declined to transpose a sealed organ. MP-E8's decision
record names this as "a missing instrument, not a missing run" (§7, and `named_missing.g2.h4_updates_half`);
this document is the instrument's design, written so the next session does not have to re-derive it.

---

## 1. What H4 actually asks for, in the registered words

`experiments/MP-E8/registration.json` registers H4 as **"A_total < B_total at each tier, in both updates and
wall-clock"**, with the statement "arm A cost per learned fact is lower than arm B's optimizer cost at every
tier, measured in updates and wall-clock on identical hardware". The registered quantity is **"synapse update
events per taught fact for arm A"**. Both halves are required; wall-clock is measured for all three arms at
all three tiers; the updates half is absent for arm A. So H4 is PARTIAL and cannot be closed by anything that
does not add this instrument.

## 2. What already exists -- which is more than the close-out note assumed

MP-E8's registration says "the organ exposes no counter for synapse updates per taught fact". That is true of
the *quantity* and false of the *counter*. Measured off the current tree:

| what | where | what it gives | what it is not |
|---|---|---|---|
| `teach_count` | `connectome/rate_core.py:50, 595, 630` | an integer incremented once at **each** of the two write sites, both `self.w += dw` paths (`_reinforce_impl`, `_reinforce_choice_impl`) | a per-fact count: it is cumulative per process and no caller can tell which taught item it belongs to |
| `plasticity_report()["teach_calls"]` | `rate_core.py:440` | the same integer, already exposed | attributed to anything |
| `last_dw_mean` | `rate_core.py:597, 632` | mean **magnitude** of the weight change on the last event | a count of synapses that changed; with `_plastic_active` gating, an event can move nothing and still report a small mean |
| `compartment_stats()` | `rate_core.py:455-490` | per-pool `strengthened` / `weakened` counts as a **state** diff from birth | a rate: it cannot say which fact moved which synapse, which is why "2,983 at build" was correctly rejected as a cost figure |

So the gap is **attribution and a denominator**, not instrumentation from zero. That is the single most
useful thing this document can tell the PI, because it makes the change small.

## 3. Where the counter would sit

Three insertions, none of them inside the arithmetic:

1. **An episode handle at the teaching boundary.** `organs/neural_language.py:1001 live(text, learn=True)` is
   where a taught fact becomes a learning episode. The counter needs an id: `self._update_episode =
   (fact_id, opened_at)` set when `learn=True` opens and cleared when it closes. Nothing in `live()`'s
   behaviour changes; it records an identity that already exists implicitly in the call.
2. **A changed-synapse count at the two write sites.** After `self.w += dw` at `rate_core.py:592` and `:629`,
   add `n = int(np.count_nonzero(dw))` and accumulate `self.update_events += 1`, `self.update_synapses += n`,
   and `self._episode_updates[self._update_episode] += (1, n)`. `dw` is already in scope at both sites and is
   not read again afterwards, so counting it touches no value that feeds the clamp, the cap at `:599` or the
   sign logic at `:600-601`.
3. **Exposure.** A `updates_report()` beside `plasticity_report()`, returning per-episode events, changed
   synapses, the taught-fact denominator and the derived **updates per taught fact**. Written into the run
   artifact so the number is sealed with the run it came from, not computed later from a state diff.

## 4. What it must not change

* The `dw` expression, the `+=` itself, the rpe clip, `_comp_lr`, `_comp_gain`, `_plastic_active`, `_plastic`
  ceilings, the cap/clamp block after the write, and `weight_decay`. The counter reads `dw`; it must not
  recompute, reorder or normalise anything.
* `teach_count`'s existing meaning. It is quoted in published evidence; the new counters sit beside it, they
  do not redefine it.
* The brain's recorded bytes: a run with the counter ON must leave `w`, `plastic_w0` and the brain file
  **bit-identical** to the same run with it OFF.
* The four R6-guarded invariants, the sealed 2,983-synapse build state, and the guard batteries (frozen
  19/24, guarded 4/4, paraphrase 0/14, `ELECTRIC=off`).
* **Wall-clock.** This is the one that makes the change non-trivial. Wall-clock is H4's *other* half, measured
  on the same path the counter is being added to. An instrument that costs measurable time biases the half it
  is paired with, and arm B and arm C cannot carry the same instrument (they are different mechanisms), so
  the comparison would no longer be "identical hardware, identical software". `np.count_nonzero(dw)` on a
  plastic array of a few thousand entries is microseconds, but "microseconds" is a claim, and this program's
  rule is that a claim on the measured quantity gets measured.

## 5. How it would be proven inert

In this order, all before any H4 figure is quoted:

1. **Numeric identity.** Same seed, same curriculum, counter OFF then ON: assert `w`, `plastic_w0`, brain
   fingerprint and every graded outcome identical. This is the C4-style discipline MP-E10 step 1 uses -- the
   claim becomes a test, not a paragraph.
2. **Wall-clock identity at tier 40.** Arm A run twice, OFF and ON, machine alone; the difference must sit
   inside the registered noise-floor tolerance (R13), and the tolerance used must be the one already
   registered, not a new one chosen for this purpose.
3. **Noise floor re-verified.** The three arm-A clones still land within 11 rows of 3,672, with any movement
   confined to the R13 time-dependent cell as before.
4. **Guard batteries unchanged**, per arm, as run for MP-E8's H4 battery clause.
5. **Existing tests unchanged**: MP-E10's 23 module + 17 routing tests, MP-E8's arm tests, the seal coverage
   test.
6. **Re-seal** all ledgers at one anchor with `git_dirty_sealed` empty, because `rate_core.py` and
   `neural_language.py` are hashed in every ledger, not only MP-E8's -- the coupling the coverage test counts.

## 6. What it costs

| step | cost | note |
|---|---|---|
| implementation + tests | one session, no machine time | three insertions and one report function |
| inertness proof (items 1-5 above) | ~50 min machine, serial | 2 x arm A tier 40 (~8 min each) + 3 clones (~24 min) + battery guards |
| re-seal | seconds | `--all`, one anchor |
| the measurement itself, arm A at all three tiers | ~1.5 h machine | tier 40 ~8 min, tier 120 ~23.5 min, tier 300 ~53.7 min, serial |
| **total** | **~2.3-2.4 h exclusive machine time, plus a PI ruling** | the ruling is required because it edits the write path, not because the work is uncertain |

## 7. What it does NOT buy

It closes H4's updates half for **arm A only**. It does not touch H2's missing scalar, does not instrument
H3, does not change H1's outcome at any tier, and does not make G2 pass -- G2's verdict is recorded and this
adds a number to a clause that is already measured on its other half. If the PI's position is that a partial
H4 is acceptable as published, this instrument is optional and the record already says which half is absent.

## 8. One alternative the PI may prefer

Count updates **outside** the organ, by diffing `w` before and after each teaching call at the harness level.
Zero organ change, no inertness argument about the write path, and wall-clock stays untouched. Its cost is
real: it measures the *net* change after decay and clamping rather than the events that produced it, so
"update events per taught fact" would mean something slightly different from the registered phrase, and a
full-array diff per teach call adds O(synapses) work to the harness side of the same timed comparison. It is
a legitimate choice, and if taken, the registered wording should be amended first rather than measured
against afterwards.
