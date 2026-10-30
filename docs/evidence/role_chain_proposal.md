# Role_chain cold failure — proposal (NOT APPLIED)

Status: proposal only. No organ, tool, test, or constant changed for this.
**Updated 2026-10-29:** the `_tmp/` output files named below were deleted when the
speech run closed, so the raw inputs are gone; the document is kept as a record
of what was measured and proposed, not as a plan that can be replayed.
House down throughout — every number below is from local runs with the
oracle off, against the live state tree read-only.

Inputs: `_tmp/cold_sweep_out.txt` (the 14-ask cold sweep, one agent build on
the live state), `_tmp/levers6_out.txt` (six sort-key variants x 14 warm
asks), `_tmp/who_tags_out.txt` (provenance census of the live binder),
`state/fitness/cross_session_20261025_214202.json` (the cross-session smoke
run), `tools/benchmark_cross_session.py` (the harness, validated).

## 1. The honest size

One ask in fourteen fails cold: role_chain's `who follows the sparrow`
speaks `answered the sparrow as she flew away now` — a corpus fragment —
and the cold grader fails any answer naming a taught word (`crow`,
`sparrow`). The other thirteen pass: five by speaking corpus fragments that
happen to avoid the taught words, eight by refusing on an empty pool. The
failure is not a ranking mistake. The cold pool holds five candidates and
**every one contains `sparrow`** (`_tmp/who_tags_out.txt`: 7 rows in the
live binder contain the word, all `who='book'`; the pool is five of them).
The grader fails every candidate in the pool. **No ranking of this pool
passes.** The failure is in the pool: the right proposition — `the crow
follows the sparrow` — was never told in this session, so it does not
exist to be retrieved.

## 2. Why the obvious levers die (measured)

### (a) Sort-key reordering — dead

The five survivors tie on every term of the sort key
`(overlap, fresh, expected[filler], idf[filler], not_in_cset)` except one:
all have overlap=1 (they contain `sparrow`, not `follows`/`watches`),
fresh=0 (cold), expected[filler]=0 (the fillers are narrative *verbs* —
`answered`, `said` — not the answer types `parent`/`droso`),
not_in_cset=1. They differ only on filler-idf: 6.691, 4.117, 3.754,
1.913, … The winner is picked by the rarity of a narrative verb — a noise
signal. Reordering the five terms cannot demote the winner, because there
are no ties to break differently: the only discriminating term is the one
that is measuring noise, and the runner-up (`said the sparrow as she
alighted upon the`) still contains `sparrow` and still fails. The levers
sweep confirms the terms are inert where it matters: all six variants
(current, fresh-first, fresh-first-weighted, and three `not_in_cset`
orders) agree on the winner of **all 14 warm asks**. A new tier inserted
above filler-idf would need a signal the key does not measure — which is
section 3, not a reordering.

### (b) Coverage floor — dead, with a measured counterexample

The failing fragment sits at coverage **0.621**; the passing nonsense
answer — reference cold's `through at noon with a stray penny my`,
which the grader counts as a pass — sits at **0.613**
(`_tmp/cold_sweep_out.txt`). A floor cannot separate them: any floor
≤ 0.613 keeps both (the fragment is still spoken, still fails); any floor
> 0.621 gates both (role_chain passes by refusing, and the passing
nonsense is silenced too). The wrong answer outranks the right-ish one,
so no threshold value produces "gate the fragment, keep the nonsense."
And the threshold that would fix role_chain (> 0.621) is fit to one
measured coverage in a state that churns under our feet: the binder is at
capacity (n_mem=60000) and the smoke run's tell-delta shows **3 rows
added and 3 evicted per tell**, so the idf table drifts with every
session. A floor tuned to 0.622 today sits an unknown distance above
tomorrow's fragment. This is gate-loosening's twin — a constant moved to
make a failing case pass — and its only benchmark-visible effect is on
the case that motivated it.

## 3. The one mechanism with a real signal: provenance

The binder's meta carries a clean source tag. Census of the live state
(`_tmp/who_tags_out.txt`): `{'book': 59515, 'droso': 466, 'parent': 19}`.
Corpus lines are heard as `speaker="book"` (the exposure path,
`organs/neural_language.py:2287`); tells as `speaker="you"` (the hear
path, `:2372`); experiences as the agent's own name. All five cold
fragments are `who='book'`; every warm winner in the benchmark is a told
proposition. The system's own philosophy already states the principle —
"it outranks what the corpus merely says about the same subject. The
corpus is a prior, not a verdict" (`organs/neural_language.py:68-69`) —
but the sort key never measures it.

A **who-exclusion for `who`-questions** — refuse unless a told or
experienced candidate exists — would convert speak-wrong into refuse
(cold role_chain 0.5 → 1.0), leave every warm answer untouched (all 14
winners are told), and is grounded in provenance the agent genuinely
holds, not in the grader's word list.

Honest costs, stated before any measurement:

1. It silences corpus who-knowledge. `who lives at westhouse marbank` —
   the corpus knows; the house would refuse. That is a real capability
   loss this benchmark never measures, because no script asks a
   corpus-answerable who-question.
2. It is still a refusal mechanism: it does not create the missing
   memory, it only stops the house from passing off reading as being
   told.

## 4. Recommendation

**Adopt nothing now.** In order:

1. **Run the full cross-session battery.** The harness is validated end
   to end: the smoke run told `the kettle rings at noon` in one process
   and a fresh process recalled it — `source: "recalled proposition"`,
   ask pass_rate 1.0, live tree untouched in both phases
   (`state/fitness/cross_session_20261025_214202.json`). If the battery
   holds, role_chain's cold condition largely *disappears*: the told
   proposition exists in every session, wins on overlap=2 against the
   fragments' 1, and the failure is retired by capability rather than by
   gating.
2. **Keep the who-exclusion on the shelf** as the fallback for sessions
   that genuinely lack the tell — but only after it is measured per
   section 5, including a new corpus-who probe that quantifies cost (1).
3. **Log the filler-idf finding** as a debt: the sort key's only
   cold-discriminating term ranks narrative verbs, and is inert in warm.
   Not changed here — reordering it is measured-useless (section 2a) and
   no positive proposal for it exists yet.

## 5. Contamination (if the who-exclusion is ever adopted)

The mechanism is motivated by a failure the grader defines, so intent is
contaminated regardless. What keeps the measurement honest:

- The rule is stated in provenance terms (`who ∈ {you, droso, parent}`),
  never in terms of the taught words; the grader's `must_not` set must
  not appear in the implementation.
- Before/after on the full battery with every other constant
  bit-identical; the only permitted delta is the who-tier.
- A **corpus-who probe** (new scripts, written before the change runs)
  asking questions the corpus can answer — its before/after delta is the
  price tag, reported next to the gain.
- The warm sweep must show zero winner changes across all 14 asks; any
  warm change means the tier is doing more than refusing unknown-who
  answers, and the change is rejected.

## 6. Evidence standard

A real result for the cross-session route: all seven scripts pass warm
and cold across fresh session pairs, with `left_a_trace` true and the
live tree untouched in every phase, and the recalled source is
`"recalled proposition"` (not pattern replay or oracle). A real result
for the who-exclusion route: cold role_chain 1.0, warm 14/14 unchanged,
corpus-who probe delta reported and accepted by a human before adoption.
An overfit result looks like: cold role_chain fixed by a constant that
no other measurement can see move.