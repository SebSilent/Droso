# Teach-time reinforcement — diagnosis, and why the line closes

**Probe:** `docs/evidence/e22a_reinforcement_probe.py`, data `e22a_reinforcement.json`. Read-only
over `state/selection/generation_19_asks.jsonl` and the live binder dump
`state/language_state.json.cortex.meta.json`. **No brain build, no retrieval change, no score, no
genome, no organ behaviour.**

**Headline: the raw correlation looks strong — count=3 passes 83%, count=1 passes 48% — and it is
entirely confounded by ask type. Five of the six count=3 asks are meta-cognitive rehearsal
questions ("how many times did I tell you…") that never reach the recall gate at all. The ONE
count=3 ask that does reach the gate FAILS at coverage 0.454 with its row ranked 1 — *below* the
count=1 gate mean of 0.4649. Count does not predict success in the population where reinforcement
could act. No E22 is proposed. The line closes.**

---

## 1. The raw numbers, and why they mislead

```
count=1: 16/33 pass  (rate 0.4848)
count=3:  5/6  pass  (rate 0.8333)
```

`taught_count` takes only **two values** across the whole 42-ask battery — 1 on 33 asks, 3 on 6. So
this is a 2-level comparison with n=6 in the high arm, not a correlation.

The six count=3 asks, in full:

| ask | pass | cause | coverage |
|---|---|---|---|
| `how many times did i tell you the coat is wet?` | **True** | other | – |
| `how many things did i tell you about the coat?` | **True** | other | – |
| `how many times did i tell you about the scarf?` | **True** | other | – |
| `did i ever tell you about the moon?` | **True** | other | – |
| `have i mentioned the moon to you?` | **True** | other | – |
| `how often did i say the coat is wet?` | **False** | **recall_gate** | **0.454** |

Five of six are **meta-cognitive**: they ask *about the telling*, not about the content. They carry
`cause=other` and `coverage=None` — they never enter the recall gate. They pass because the organ
can answer a rehearsal question without retrieving a content row at all.

Count=3 is not a cause of passing. **Count=3 co-occurs with a question type that bypasses the
mechanism.** The scripts that repeat a fact three times are the same scripts that ask how many
times it was repeated. The confound is structural, not incidental.

## 2. The decisive comparison: restrict to the gate

Reinforcement could only act through retrieval of a content row, so the only informative population
is asks that actually reach the recall gate.

```
count=1: gate asks 8, coverage mean 0.4649, range [0.340, 0.555]
count=3: gate asks 1, coverage 0.454
```

**The single count=3 gate ask scores 0.454 — below the count=1 mean of 0.4649.** Its taught row
`the coat is wet` is at probe rank **1**, and the ask still fails against a 0.6 floor.

This is the whole finding in one line: **the best-reinforced row in the battery, retrieved at rank
1, has worse gate coverage than the average count-1 row.** Reinforcement did not help coverage, and
coverage is what decides the ask.

## 3. Why reinforcement cannot help even if it improves rank

Count does appear to help *rank*: count=3 rows rank 1 in all 3 cases where a rank was resolved,
against a count=1 mean of 4.88 (best 1, worst 25). But rank is not the binding constraint, and E20
already proved it:

> On 4 of 9 gate asks the gate retrieves the correct taught row and ranks it **first**, then refuses
> anyway at coverage 0.340–0.538.

`what is bitten by the frost?` has its row at gate rank 1 and coverage **0.340** — the lowest in the
battery. Rank 1 and failure coexist. So a mechanism whose only demonstrated effect is improving
rank, on a battery where rank-1 rows already fail, **has no path to changing an outcome.**

The coverage denominator is set by `must` — the question's own syntax and morphology — not by how
often the row was taught. `how often did i say the coat is wet?` demands `did`, `often`, `say` from
a row that says `the coat is wet`. Teaching that row thirty times does not put `often` in it.

## 4. The battery cannot test reinforcement at all

Even setting the confound aside, this is a design gap worth recording:

- **Two count values.** 1 and 3, with n=6 in the high arm. No dose–response is measurable.
- **Count is aligned with ask type.** Every count=3 ask sits in a script that also asks a rehearsal
  question, so count and question class cannot be separated in this data.
- **The live binder has far more range than the battery exercises:** 60,000 rows, **76 distinct
  count values**, but 59,665 rows (99.4%) at count=1. Reinforcement effects at count 5, 10 or 20 are
  unmeasured and unmeasurable from these journals.

A real test would need scripts that vary repetition count **independently** of question type — the
same content question asked about a fact told once, three times and ten times. That is a battery
change, not a probe, and it is not proposed here.

## 5. Verdict: negative, line closed

**Count does not predict success in the causal population.** The apparent 48%→83% gap is ask-type
confounding. Restricted to gate asks, the one count=3 row scores *below* the count=1 mean while
ranked first. And the mechanism reinforcement would act on — rank — is already demonstrably not
binding.

No E22 is proposed. Per the pre-registered branch, the negative is recorded and the line closes.

This completes the closure of every lever that operates on an existing taught row:

| lever | probe | verdict |
|---|---|---|
| eviction | E19 | falsified — 0/19 failures, `taught_resident` on 40/42 |
| cue omission | E20 | falsified — gate ranks the row **first** on 4 of 9 and still refuses |
| cue dilution | E21a | falsified — de-framing recovers 0 of 4; best case rank 41→10 vs window 3 |
| score / admission | E12a, E14a | closed — ceiling 0.5488 < 0.6 floor |
| **reinforcement** | **E22a** | **falsified — count=3 gate ask scores below the count=1 mean** |

The row is resident, findable, sometimes ranked first, and sometimes taught three times — and the
ask still fails, because the gate demands question syntax the declarative row cannot contain. **The
binding constraint is the coverage denominator, and it is a property of the question, not of the
memory.**

## 6. What is left, not proposed here

Only mechanisms that do not operate on retrieval or reinforcement of an existing row:

- **The coverage denominator itself.** Every probe now points here. E12a/E14a closed *admission*
  (letting more rows in) at 0.5488; nobody has tested changing what `must` demands — e.g. excluding
  closed-class question syntax from the denominator. That is an organ behaviour change and would
  need its own pre-registration, guard analysis and abort conditions. It is the one lever the
  evidence still supports.
- **Ordering.** The `before the kettle` pair (count=1, rank=None, coverage 0.460/0.555) needs a
  sequence primitive; E19, E20 and E22a all classify it as not-a-retrieval-problem.

Neither is pre-registered. E22a was measurement, and it says the reinforcement lever is closed.

## 7. Limitations

- **n=6 in the count=3 arm, one gate ask.** The decisive comparison in §2 rests on a single
  observation. It is sufficient to falsify "count predicts success" — one counterexample at rank 1
  does that — but it cannot characterise the shape of any real count effect.
- **Confounded by construction.** Count and question type are aligned in `scripts_heldout.json`, so
  no statistical adjustment can recover an unconfounded estimate from this battery.
- **`taught_count` is E19's attribution**, resolved by matching scripted tells against binder rows.
  It is the count at ask time in that session, not a live-binder count.
- **Probe rank vs gate rank.** §3 uses E19's independent probe rank; E21a showed probe rank and the
  gate's own `nearest` ordering can disagree. The rank argument is therefore indicative — but the
  coverage argument in §2 does not depend on rank at all, and coverage is the gate's own recorded
  quantity.

## 8. Files

| file | change |
|---|---|
| `docs/evidence/e22a_reinforcement_probe.py`, `.json`, `teach_time_reinforcement_diagnosis.md` | new read-only probe, data, this file. |

No change to `tools/`, `organs/`, `connectome/`, `tests/`, genomes or any score.
