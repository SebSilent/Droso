# Open learning: from a frozen evaluated brain to a persistent organism

Written before any code. This is the design and the contract for the next step;
every later change to it needs a dated entry in the change log at the bottom.

Scope of this step: the design, the capability ladder, the tier structure, and one
specified first experiment. **No core connectome or decision code is modified
here.** Where a core change turns out to be unavoidable, §7 names it, puts it behind
a flag, and states the proof required before it lands.

Companion documents: `docs/selection_design.md` (the frozen/guarded harness this
builds on and must not weaken), `docs/cross_session_design.md` (the session-boundary
mechanism map), `docs/benchmark_findings.md` (SAN saturation), and
`docs/archive/experiment_log.md` (the historical record, whose conclusions are its
authors').

## 1. The target, stated so it can fail

A Droso brain that, across teaching episodes separated by process restarts,
**retains what it was taught and answers it in words it was not taught in**, while
**losing none of what it could already do**.

Four properties, each separately measurable and each separately falsifiable:

| property | what it means | how it is measured |
|---|---|---|
| **retention** | a fact taught in episode N is still answerable in episode N+k, across a restart | teach, restart, re-ask |
| **acquisition** | a fact taught once becomes answerable at all | ask immediately after teaching |
| **generalisation** | the retained fact survives a rewording it was not taught in | the paraphrase probes |
| **non-erosion** | none of the above costs a capability that was already there | the frozen 24 and the guarded probes, re-measured after every episode |

"Continuously improving" is not a target, it is an outcome, and it is only
meaningful once non-erosion is instrumented — otherwise improvement and churn are
the same number. The order above is deliberate: **non-erosion is the constraint,
the other three are the objective.** That is the same shape as the selection
harness's `select_key`, and for the same reason: a scalar objective that can pay for
a loss will eventually do so.

## 2. What the substrate actually is today

Measured, not assumed. `docs/evidence/binder_census.py`, run 2026-10-30 against the
live cortex store, output at `docs/evidence/binder_census_20261030.txt`:

```
60,000 rows  (capacity MAX_PROPOSITIONS = 60000, higher_cortex.py:46 -- FULL)
  book    59,515   99.19%
  droso      466    0.78%
  parent      19    0.03%
  you          0    0.00%     <- nothing the user ever taught him is present
  rows with count == 1:  59,665   99.44%   (never rehearsed)
  max count: 11,925
  row ages: p0 14.38d  p50 20.91d  p100 21.34d   (all bound in one ~7-day window)
  token length: 55,316 of 60,000 rows are exactly 8 tokens
```

Three facts here shape the entire design.

**2.1 Teaching does not currently accumulate at all.** `who == "you"` is zero. Every
proposition this project has ever taught him in a session ran against a sealed
shadow — `tools/converse.py` repoints every persistence path into
`state/sessions/`, and `tools/run_generation.py` and `heldout_eval.py` both build
through it. That sealing is correct and must stay: it is why the guarded baseline
means anything. But it also means **the live organism has never kept a taught
fact**, and the newest row in its memory is 14 days old. The "fixed evaluated
brain" in the goal statement is not a metaphor; it is the measured state.

**2.2 Eviction is blind FIFO.** `higher_cortex.py:399-413`: when the binder is at
capacity, `meta.pop(0)` drops the **oldest** row and `np.roll` shifts everything,
then `_seen` is rebuilt with every index decremented. Nothing consults `who`,
`count`, or value. So a fact taught today is evicted before a corpus line read once
three weeks ago, exactly as `docs/cross_session_design.md` warned. Accumulation on
this substrate is not addition, it is **displacement** — and which thing is
displaced is currently decided by arrival order alone.

**2.3 The association matrix cannot grow.** `docs/benchmark_findings.md` measures
the SAN at 66,107,030 nonzeros, 49.5% of all possible word-cell pairs, and frozen
across 13 consolidation runs and 2,138 replayed rows: **zero new edges**. The Hebb
write only increments existing entries, so after 60k propositions plus books every
plausible pair has already co-occurred. Weight movement is the only live signal, and
"new associations formed" is not an available metric for common words.

The consequence for this design: **the room to grow is not in the weights and not in
new capacity. It is in which of the 59,665 count-1 corpus rows is allowed to keep
its seat.** That is a small, precise lever, and it is the one §7 names.

## 3. What must change, item by item

Each item is marked with what already exists, because building a second mechanism
beside a working one is how this project has previously ended up with two that
disagree.

### 3.1 Persistent plastic synapses and learned weights — **EXISTS**

`connectome/engine.py:220 save_brain()` / `:248 load_brain()` write
`state/banc_brain.npz` (weights, plastic pre/post indices, and a provenance stamp
that refuses to load a control brain into an experimental one). `NeuralGrowth` calls
`load_brain()` at start (`organs/neural_growth.py:52`), `save_brain()` on stop
(`:195`) and on every consolidation tick (`:363`). `load_brain` adopts a recorded
geometry that **grew or pruned** past the birth carve, matching synapses by identity
`(pre, post)` rather than position, so a lifetime of structural change survives
rebirth.

Language state: `neural_language.py:4259 save_state()` / `:4391 load_state()` write
`language_state.json` plus `.san.npz`, `.seq.npz`, `.cortex.npz`, all
tmp-then-rename, plus a **delta path** (`.cortex.delta.json`) that stores heard
utterances for exact replay and refuses past `HEARD_DELTA_CAP = 2000`
(`higher_cortex.py:757, :1011`).

**What is missing is not persistence but proof of it.** `tools/script_benchmark.py`
already measures warm against cold-after-restart and reports a delta; the recorded
figure is 1.00/1.00 with every delta +0.00 on eight scripts. That is a
restart-fidelity check on eight scripts and nothing else. The open-learning tier
needs the same check on material that was *taught*, not material that was already in
the corpus — which is a new measurement, not new machinery.

### 3.2 Persistent teaching history and memory state — **PARTIAL**

The binder's rows carry `who`, `when`, `count` and `tokens`, and `who` is set at the
bind site: user speech binds `who="you"` (`neural_language.py:3285`, and
`freshness_key` gates on `who != "you"` at `:70`), own speech `who="droso"`, corpus
`who="book"`, narration `who="parent"`. `WITNESS_W` (`neural_language.py:483`) is
intended to weight those categories and `consolidate()`'s value function uses it as
`WITNESS_W.get(who, 0.6) * log1p(count)` (`:501-504`).

**But the ranking signal is broken for exactly the category open learning depends
on, and this was found while writing this document rather than inherited from it.**
`WITNESS_W` is `{"parent": 1.0, "user": 1.0, "teacher": 1.0, "oracle": 0.8,
"book": 0.6, "droso": 0.3}` — **there is no `"you"` key**, and nothing in the tree
binds `who="user"`. So user testimony falls through `.get(who, 0.6)` to the default,
which is precisely the `book` weight. Measured:

```
you  count=1 -> 0.415888      book count=1 -> 0.415888     identical
you  count=3 -> 0.831777      book count=3 -> 0.831777     identical
parent count=1 -> 0.693147    droso count=1 -> 0.207944
```

`you` and `book` are indistinguishable at **every** count, because the `who` term
contributes nothing for testimony. The consequences are concrete and they are worse
than a missing key:

- With 59,665 of 60,000 rows at count 1, all tied at 0.415888, `consolidate()`'s
  `scan_top = 2000` window takes the 19 `parent` rows and then 1,981 of the tied
  rows — chosen by Python's **stable sort**, i.e. by binder order, i.e. **oldest
  first**. Consolidation today replays the oldest corpus lines.
- A taught fact therefore receives **no protection at all** from the one mechanism in
  the tree whose stated purpose is to hold high-value propositions above dust. It
  ties with a book line read once three weeks ago, and loses its seat to blind FIFO
  on top of that.

This does not change the plan, it sharpens it: §7's eviction change cannot simply
reuse `WITNESS_W` as "the existing signal", because the existing signal scores
testimony as corpus. The missing key is a one-entry addition to a class constant, but
it is core code and it changes what `consolidate()` selects on live state, so it is
named in §7 with its proof requirements and **not made here**.

**What is missing is an episode record.** There is no notion of "teaching episode N
happened at time T, was given these inputs, and produced these state deltas". The
directory for it exists and is empty: `state/lineage/` is managed by
`tools/state_hygiene.py:38,44` (`DEFAULT_KEEP = {"sessions": 3, "lineage": 2}`) and
**contains nothing** — no code in the tree writes to it. `tools/population.py:165`
treats a lineage as "the files themselves, flat", which is a restore mechanism and
not a history.

So: an append-only episode ledger at `state/lineage/episodes.jsonl`, one row per
episode, carrying the episode id, its parent, the timestamp, the generator seed and
seal, what was taught, the state seals before and after, the eviction census, and
the evaluation result. That is the learner's analogue of
`state/selection/generation_N.jsonl`, and it should carry the same discipline: the
row is self-contained, the genome/state seals are in it, and a reader can tell which
animal it describes.

### 3.3 Consolidation so new learning does not erase old capability — **PARTIAL, and the gap is precise**

`neural_language.py:486 consolidate()` is a sleep-phase replay: it value-ranks
propositions, filters to those whose weakest adjacent-pair weight is below
`urgency_line = 0.1`, and replays them through `live()`'s Hebb rule to hold their
wiring above dust. It is read-only on the binder and the caller must
`save_state(force_san=True)` because delta saves skip the SAN.
`tools/consolidate_live.py` runs it against **live** state with a per-run backup
(`state/backup_pre_consolidate_<ts>/<run_tag>`, seven on disk), a file guard with an
`EXPECTED_MOVE` whitelist of seven files, a strong-band census before and after, a
report to `state/fitness/`, and exit codes 0 drained / 1 fatal / 2 max-runs.

**The gap: consolidation stabilises weights, not rows.** It strengthens the SAN
entries of rows that are still *in* the binder. It does nothing about the binder
evicting those rows in the first place. Given §2.2 and §2.3 — eviction is blind and
the SAN cannot grow — the erasure mechanism for a taught fact is **row eviction**,
and no existing mechanism protects against it. This is the single most important
sentence in this document, and it is why §7's first core change is about eviction
and not about plasticity.

### 3.4 Versioned learner checkpoints — **PARTIAL**

What exists: per-run rollback backups (`state/backup_pre_consolidate_*`), the
`state/backup_f16` directory, `tools/population.py`'s flat individual directories,
and `engine.load_brain`'s provenance-and-geometry check that refuses a mismatched
brain rather than loading it silently.

What is missing: a **versioned checkpoint with an identity and a verified restore**.
The selection harness already has the shape — `genome_id` as a sha256 of the genes,
`parent_genome_id`, a `lineage` chain walked from published records, and seals on
every input file so a changed contract refuses the run. A learner checkpoint needs
the same four things: an id derived from the state it names, a parent, a lineage, and
a seal — plus one thing a genome does not need, because a genome is small and a
learner state is 250 MB: **a restore that is verified by re-measurement rather than
by file comparison.** `tools/verify_saved.py` is the precedent: it replays a saved
genome and asserts it reproduces its recorded composite, rather than trusting that
the file was written.

Proposed: `state/lineage/ckpt_<n>_<id>/` holding the seven state files, plus one row
in `state/lineage/episodes.jsonl` naming it, its parent, its seals, and the score it
was measured at. `state_hygiene.py` already caps `lineage` at 2, which is too few for
a lineage and needs raising — a change to a tool constant, not to core code.

### 3.5 Evaluation that measures growth without contaminating the guarded baseline — **THE HARD ONE**

The frozen battery is sealed and the harness refuses to run if the seal moves
(`tools/run_generation.py`, `frozen_seal b9d0f2d83fbb7e78`). That must not change.
Three rules follow, and the third is the one that is easy to get wrong.

1. **The open tier is a fourth tier, never a replacement.** `frozen` (24),
   `regression guard` (4 probes), `paraphrase` (14 probes) stay exactly as they are.
   The open tier is added beside them and every episode re-measures all four, so
   erosion is visible in the same record as growth.
2. **The open tier's material must be generated, not fixed.** A fixed file is
   exhausted by the first episode: teach it once and episode 2 measures recall of
   episode 1's teaching rather than the ability to learn. So the tier is a
   *generator* with a declared seed, and each episode's material is sealed into the
   episode row.
3. **The generator must not produce material the guarded tiers can see, and must not
   be fitted to them.** This is where `tools/fly_v2.py` failed: it generated
   synthetic spans whose modifier class was closed at `{old, copper, heavy}`, and the
   winner it bred named `small` as the head of `the small brass bell`. A generator
   that draws from a closed vocabulary produces a learner that looks like it is
   growing and is only memorising the generator. Constraints on the generator, all
   checkable: it draws content words from the **live vocabulary** (11,555 words) and
   not from a private list; every proposition it emits is **verified absent from the
   binder** before it is taught, the discipline `docs/benchmark_findings.md` records
   for the `session_context` script; and its output is sealed per episode so a
   regenerated batch can be compared to the one actually taught.

And the consumption rule from `docs/selection_design.md` §4.4 applies verbatim: an
open-tier batch that has been *taught* is training material by definition, so it can
never also be the generalisation probe for that episode. Each episode therefore needs
**two** generated batches — one taught, one held out and only asked — and the held-out
batch is what measures whether learning transferred or merely fitted.

## 4. The capability ladder

Six rungs. Each has a mechanical check and a **current measured value**, because a
ladder with no numbers on it is a wishlist. Two rungs are honestly marked as
unmeasured or zero rather than being given an optimistic estimate.

| rung | capability | mechanical check | measured now |
|---|---|---|---|
| **1** | memory and recall over taught facts | the frozen 24, independent mode, one build per ask | **19/24**, stable across 5 measurements of the parent genome in 3 generations |
| **2** | paraphrase robustness | the 18 rewordings in `tools/scripts_selection.json` | **4/18** — 14 of 18 rewordings of asks he already answers fail |
| **3** | multi-step QA | the hop asks: `what does the thing the frost bites hold?` and its two rewordings | **0/3** — one at `shape_arbiter`, two at `recall` |
| **4** | simple compositional reasoning | arithmetic over stated quantities: `quantity-change` 4 asks, `count-frequency` 4 asks | **8/8** — this rung already passes, and it is the only one that does |
| **5** | planning / tool-use readiness | `Harness.solve()` branch attribution on the first-contact coding set | **0 of 10 solved locally** — all 10 *passed*, all 10 by oracle (`solved_locally: 0`, `solved_by_oracle: 10`, `oracle_calls: 1` each, in `state/fitness/heldout_firstcontact.json`) |
| **6** | self-correction after feedback | *none exists* | **unmeasured** — no mechanism and no instrument |

Three things about this ladder are worth stating plainly.

**Rung 4 passing while rung 3 fails is not a contradiction.** Composition over
*stated numbers* works (four eggs, two break, two left) because the quantity path
does arithmetic over numbers extracted from this session's tells. Composition over
*relations* fails, because answering the hop requires joining two memories and
`_prop_join` proposes a join that the shape arbiter then refuses — the log records
the veto as correct and the axis as closed after a bounded attempt. So rung 3 is not
"rung 4 but harder"; it needs a mechanism the organ does not have.

**Rung 2 is the rung open learning can actually move, and it is the weakest.** 14 of
18 rewordings fail, and the probe tier localised three of the causes to a literal
string: the shape parser is keyed to `what` (`which thing turns twice?` fails where
`what turns twice?` passes), the echo path to `say exactly` (`repeat after me …`
fails at `mouth`), and the quantity path's openers to `how many` / `what count of` /
`did any` (`what number of eggs…` fails). Those are phrasing dependencies, and
phrasing dependencies are exactly what teaching more varied phrasings should erode.
That is the hypothesis the open-learning tier exists to test, and rung 2 is where it
will show up first or not at all.

**Rung 5's zero is not a failure to solve, it is a failure to solve alone.** All ten
first-contact tasks passed; every one was solved by the oracle with one call each.
That is precisely the distinction `organs/harness.py` exists to make — its branch
attribution (`system1_fact | system1_recall | system2_local | system2_oracle_hole |
unsolved`) is the only thing that separates "he can do this" from "he can get this
done" — and it is the rung where open learning has the most room and the least
instrument, because the 0.70 evidence gate in `README.md` applies to oracle answers
exactly as it does to his own.

**Rung 6 has no instrument and must not be claimed.** Self-correction after feedback
means: he is told an answer was wrong, and a later ask shows the correction took.
Nothing in the tree does this for language. `organs/error_expertise.py`,
`solver.repair_against` and the learning loop's demote-on-failure all exist for
*code*, and the evidence gate in `README.md` weights a passing test that executes a
line inside a candidate at 0.35. Whether any of that transfers to a spoken answer is
an open question, and the ladder records it as unmeasured rather than estimating it.

The ladder is a **report**, not a fitness function. Nothing selects on it. Selection
stays where `docs/selection_design.md` put it: the frozen 24 and the guarded probes,
with the paraphrase tier demote-only. A ladder that is optimised becomes a target,
and rung 2's whole value is that it is currently an honest 4/18.

## 5. The tier structure

```
tier        file                        sealed   taught?   role in selection
frozen      tools/scripts_heldout.json  yes      never     the floor; a loss is a hard fail
guard       scripts_selection.json (4)  yes      never     may only be lost
paraphrase  scripts_selection.json (14) yes      never     may only be gained; demote-only
open        GENERATED per episode       per-ep   yes       growth; never selects, only reports
```

The first three are unchanged and stay unchanged. The open tier is generated per
episode, in two batches:

- **teach batch** — propositions fed to `lang.live()` / `lang.respond()` as tells.
  Consumed by definition. Sealed into the episode row.
- **held-out batch** — asks about the teach batch's content, in **rewordings the
  teach batch never used**, asked after a restart. This is the rung-2 instrument for
  open learning, and it is generated by the same generator with a different seed so
  it cannot leak into the teaching.

Every episode re-measures all four tiers. The episode row therefore carries the
frozen score, the guarded score, the paraphrase score and the open score side by
side, and **erosion of any of the first three fails the episode** regardless of what
the open tier did. That is the non-erosion constraint from §1 made mechanical, and it
is the same rule the selection harness already enforces — reused, not reinvented.

Grading and stage attribution are imported from `tools/heldout_eval.py` (`grade`,
`stage_of`) exactly as `run_generation.py` does, so an open-tier ask and a frozen ask
come off one checker and their numbers are comparable. Ask ids use the same
`script::ask` form.

## 6. The smallest safe first implementation

Four pieces, and three of them are existing machinery used in a new arrangement.

1. **One persistent learner state — the live one.** Not a copy, not a second brain.
   `state/language_state*` and `state/banc_brain.npz` are the learner. A teaching
   episode runs against a **shadow** built the way
   `tools/benchmark_cross_session.py:159 build_shadow` already builds one
   (`os.link` to every live state file at `:179,187`, then the episode's saves
   copied on top — note `docs/cross_session_design.md` cites this as `:120-175`,
   which is stale), so
   the live state is only ever replaced by a *promoted* checkpoint, deliberately,
   with a backup. This is the difference between an organism that learns and one that
   has been overwritten.
2. **One teaching/consolidation loop — `tools/teach_episode.py`**, modelled on
   `tools/consolidate_live.py`'s proven shape: backup, guard with an `EXPECTED_MOVE`
   whitelist, census before and after, report, exit codes, house-down requirement.
   It generates the two batches, teaches the first, consolidates via the existing
   `lang.consolidate()`, saves, and appends one row to `state/lineage/episodes.jsonl`.
3. **One evaluation script — an `--tier open` on `tools/run_generation.py`**, not a
   new harness. One checker, one journal format, one comparison tool. The open tier
   reads a generated batch file instead of `scripts_selection.json`, and its seal goes
   in the episode row.
4. **Tests proving the existing suite still passes.** 484 passed, 3 skipped is the
   current bar and it is a gate, not a report. New tests pin: the episode ledger's
   schema, the generator's absence-verification (a proposition already in the binder
   is refused, not taught), the erosion guard (an episode that loses a frozen pass
   fails whatever its open score is), and the restore (a promoted checkpoint
   re-measures to the score recorded for it).

Explicitly **not** in the first implementation: multi-brain work, population or
merge, structural growth or pruning, any change to the SAN, any new plasticity rule,
and any change to the frozen or guarded tiers.

## 7. The core-code boundary

Step 6 of the instruction is that core connectome and decision code is not modified
until the design and tests exist, and that an unavoidable change goes behind a flag
with the suite proven green. One change is unavoidable, and it is named here rather
than discovered later.

Two changes, in this order, because the second is meaningless without the first.

**7a. `WITNESS_W` gains a `"you"` key (`neural_language.py:483`).** One entry in a
class constant. Without it, testimony scores as corpus (§3.2) and every value-based
decision downstream of it — consolidation's scan window, and 7b's eviction — ranks a
taught fact level with a book line read once. This is a prerequisite, not an
optimisation, and it is the smallest core change in the programme.

Its proof requirements are stricter than its size, because it moves live behaviour:
`consolidate()`'s `scan_top = 2000` window currently selects 1,981 tied rows in
arrival order, and after the change it will select the taught and rehearsed rows
instead. So the proof is (i) the frozen 24 unchanged with `asks whose outcome or
stage differs: 0` via `heldout_eval --compare` — consolidation is not in the answer
path, so this is expected to hold and must be shown to; (ii) a before/after census of
which rows `consolidate()` picks, so the change in selection is measured and not
assumed; (iii) the full suite green.

**7b. Value-weighted eviction in `higher_cortex.py:399-413`.** Blind FIFO is the
erasure mechanism (§2.2, §3.3), so no amount of teaching can accumulate while it
stands. The change is small *given 7a*: evict the least-valuable row rather than the
oldest, valued by the same `who`/`count` function consolidation uses. The census says
why this is safe to try at all — **59,665 of 60,000 rows have count 1 and 59,515 are
`book`** — so on the live state today a value-weighted eviction chooses among tens of
thousands of interchangeable corpus rows and would not touch a taught row.

Discipline around them, all of it required:

- **7b is flag-gated and off by default.** `Binder(capacity=…, eviction="fifo")` with
  `"value"` opt-in, so live behaviour is byte-identical until something passes the
  new value. `SAN_WEIGHT_CAP` is the precedent: named, default unchanged, "naming it
  is not re-tuning it" (`neural_language.py:48-53`).
- **7a cannot honestly be flag-gated and is not pretended to be.** It is one entry in
  a class constant read by a method with no plumbing for a switch; threading a flag
  down to it would be a larger change than the fix. So it is gated by proof instead —
  the three requirements above — and it lands alone, in its own commit, with the
  before/after consolidation census attached, so a regression is attributable to it
  and not to whatever shipped beside it.
- **The frozen battery must not move with the flag off.** Proven by running the 24
  both ways and requiring `asks whose outcome or stage differs: 0`, using
  `heldout_eval --compare`.
- **The full suite green**: 484 passed, 3 skipped, plus the new tests.
- **It must not be scored through a shim.** `tools/_genome_patch.py` is present and
  tracked and patches `NeuralLanguage._shape_matches` at import time; the selection
  harness asserts on `__code__.co_filename` that the answer path is the organ's own
  code before every brain it scores, and that check must stay clean. An eviction
  change is inside the binder, not the answer path, so the check does not cover it —
  which is a reason to add the binder's eviction method to the watched list, not a
  reason to skip the check.
- **One performance note, recorded before it bites:** the current eviction rebuilds
  `_seen` with every index decremented on every eviction (`:411-413`), which is O(n)
  per bind at n = 60,000. A value-weighted eviction that scans for a minimum is also
  O(n). If both happen per bind, teaching a batch of 100 propositions costs 100
  scans of 60,000 rows. That is survivable and must be measured rather than assumed,
  because the alternative — a heap — is a larger change to a core data structure and
  is not in the first implementation.

Nothing else in `connectome/`, `organs/`, `core/` or `world/` needs to change for
§6, and nothing else should.

## 8. Experiment E1 — the retention cost of one teaching episode

**E1 does not teach anything new into the live state and does not change any core
code.** It measures the quantity that decides whether open learning is possible on
this substrate at all: what one teaching episode costs.

The reason to measure cost before capability is §2.2. If teaching 20 facts evicts 20
corpus rows and leaves the 20 facts answerable, the substrate supports accumulation
and the ladder is worth climbing. If teaching 20 facts evicts 20 rows and the facts
are *also* gone by the next restart, then no teaching loop will help and the eviction
change in §7 is the prerequisite, not an optimisation. Either answer is useful and
they imply different next steps, so E1 is designed to distinguish them.

### The command

```bash
# house down, live state read-only, everything written under state/sessions/
py -3.10 tools/teach_episode.py --episode 1 --facts 20 --seed 1 --dry-run
py -3.10 tools/teach_episode.py --episode 1 --facts 20 --seed 1
py -3.10 tools/run_generation.py --report --episode 1
```

`--dry-run` generates and seals both batches, verifies every teach proposition is
absent from the binder, and writes nothing — the same pattern as
`run_generation.py --dry-run`, which is what surfaced generation 1's one-sided sample
before an hour of builds was committed to it.

`tools/teach_episode.py` does not exist yet. It is the deliverable of the next step,
and §6 lists its four required pieces. The command above is its specified interface,
recorded now so the interface is fixed before the implementation rather than after.

### What it measures

One shadow, built from live state. Teach 20 generated propositions as tells. Then,
each against a **fresh build** so nothing an earlier ask did can move a later one:

| measurement | instrument |
|---|---|
| acquisition | the 20 taught facts asked in the words they were taught in |
| generalisation | the same 20 asked in held-out rewordings |
| erosion | the frozen 24 and the 4 guarded probes, re-measured in the same shadow |
| displacement | binder rows before and after, with the evicted rows' `who` and `count` distribution |
| weight movement | SAN rows changed, total weight, nnz — reported, with nnz expected not to move (§2.3) |
| restore | the shadow discarded, live state re-measured, seals compared |

### Success criteria

E1's criteria are about the **instrument**, not about Droso getting better. A
capability claim from a first episode would be exactly the over-reading this project
keeps having to retract.

**Pass, all required:**

1. Every one of the 20 teach propositions was verified absent from the binder before
   teaching, and the verification is in the episode row. A proposition that was
   already present is refused, not taught, and the batch is topped up.
2. **Erosion is zero**: all 19 frozen passes and all 4 guarded probes still pass in
   the post-teaching shadow. This is the constraint from §1 and it is a hard gate.
3. The displacement census is reported with its `who`/`count` distribution, so what
   was evicted is named rather than counted.
4. The live state is untouched: the guard reports `live_files_untouched`, and the
   live seals after the run equal the seals before it.
5. The episode row is self-contained — one row in `state/lineage/episodes.jsonl`
   carrying the generator seed and both batch seals, the parent checkpoint id, the
   before/after state seals, all four tier scores, and the census.
6. The full suite is still 484 passed, 3 skipped.

**Reported, not gated** — these are the numbers E1 exists to obtain, and any value is
a result:

- acquisition: how many of the 20 are answerable in the words they were taught in.
  Zero is a finding, and it would mean the bind site or the reply gate, not
  eviction, is the first blocker.
- generalisation: how many of the 20 survive a rewording. Expected to be low, because
  rung 2 is 4/18 on material he has known for weeks; a *higher* rate on freshly
  taught material than on the standing paraphrase tier would itself be interesting
  and would need checking before it was believed.
- whether nnz moved. Expected **not** to (§2.3). If it does, the saturation finding is
  wrong or the taught words are rare enough to have un-wired pairs, and either way
  `docs/benchmark_findings.md` needs an addendum.

**Fail, and what each failure means:**

- erosion > 0 → teaching already costs capability, and §7's changes are a
  prerequisite rather than an improvement. Do not proceed to E2.
- the guard reports live files moved → the shadow is leaking. Stop and fix before any
  second run, because every later number would be measured against a contaminated
  state. This is the incident class the README records: a measurement tool with
  unrestricted write access overwrote the accumulated memory file.
- a teach proposition was already in the binder and was taught anyway → the generator
  is not verifying absence, and the episode's acquisition number is measuring recall
  of the corpus rather than learning.

### What E2 is, and why it is not E1

E2 is §7, in its two parts and in order. **E2a** lands the `WITNESS_W["you"]` key
alone, with the frozen 24 compared before and after and the consolidation census
attached. **E2b** lands flag-gated value-weighted eviction, run as: E1 with the flag
off, E1 with the flag on, and the two compared on retention, generalisation and
erosion — with `heldout_eval --compare` requiring `asks whose outcome or stage
differs: 0` on the frozen 24 with the flag off, so the flag's own inertness is proven
rather than claimed. Neither is started until E1 passes, and together they are the
only planned core changes in this programme.

### E1, measured

20 facts, seed 1, 82 asks, 2,022 s (34 min), one shadow, live state never written.
`state/lineage/episodes.jsonl` episode 1, checkpoint `7c8d00202101`,
`promoted_to_live: false`. **Verdict PASS — all five gates.**

| | result |
|---|---|
| acquisition (T frame, the words it was taught in) | **20/20** |
| generalisation (held-out rewordings) | **2/20** — H1-reverse-role **2/2**, H2-question-word **0/6**, H3-passive **0/12** |
| frozen 24 | 19/24, unchanged |
| guarded probes | 4/4, unchanged |
| **erosion** | **none** |
| displacement | 60,000 → 60,000 rows; **22 evicted, all `book`, all count 1**; 22 added: **20 `you`**, 2 `droso` |
| SAN | nnz 66,107,030 → 66,107,030 (**+0**); total weight 286,281.156 → 256,070.031; 8,112 rows changed |
| guarded-battery stages | recall 10, mouth 4, gating 3, shape_arbiter 2 — identical to generations 0/1/2 control |
| open-tier stages | shape_arbiter 12, gating 6 |
| live seals | unchanged; guard moved nothing |
| generator | pool 10,234 live-vocabulary content words, 21 draws, 0 binder collisions, seal `85bcfc181260831c` |

**Retention works, and this is the first time it has been measured here.** Every
acquisition ask was put to a **fresh build against the shadow**, so the fact had to
survive `save_state` → `build_shadow` → a new process → `load_state`. 20 of 20 did.
`who="you"` rows entered a binder — 20 of them — where the census two days earlier
found zero. The organism is no longer only a fixed evaluated brain, in the narrow and
checkable sense that a taught fact now persists across a process boundary.

**The fact is stored as a relation, not as a question-answer pair.** H1 asks for the
*other* role (`the {a} {v} the {b}` taught, then `what {v} the {b}?` expecting `{a}`)
and it passed **2/2**. That is the single most encouraging number in the run and it
must not be over-read: the seed assigned H1 to only two of the twenty facts, so this
is two asks and not a rate. A generation that balances the frames across facts would
make it one.

**Phrasing brittleness transfers to freshly taught material, and that is the result
that redirects the programme.** H2 (`which thing does the {a} {v}?`) 0/6 and H3
(`what is {v} by the {a}?`) 0/12 reproduce exactly what the standing paraphrase tier
found on material he has known for weeks: the shape parser is keyed to a literal
`what`, and the passive voice loses retrieval. So rung 2's 4/18 is **not** an artefact
of old corpus memory or of a saturated SAN — it is a property of the answer path, and
it appears on facts taught thirty seconds ago. **Teaching more facts will not move
rung 2.** The 18 open-tier failures split shape_arbiter 12 / gating 6 with no recall
failures at all, which localises it: the memory was found, and the mouth or the
arbiter refused it.

**Displacement is exactly what §2.2 predicted, and cheaper than feared.** 22 rows
evicted, every one `book` with count 1 — the low-value corpus rows — and zero
erosion. Blind FIFO evicts the *oldest* rows, and the oldest rows are all count-1
book rows, so at this scale FIFO and value-weighted eviction **choose the same
victims**. That is a real qualification on §7b: it is not needed for small episodes on
a binder whose tail is uniformly low-value. It becomes necessary when a taught row has
aged far enough that 60,000 further binds reach it, which is the horizon an organism
that keeps being taught will actually reach. E1 measured the near term, not that one.

**SAN saturation confirmed on freshly taught material.** nnz moved by exactly zero,
so `docs/benchmark_findings.md`'s addendum holds for new teaching and not only for
replayed corpus rows. Total weight *fell* by 30,211 with 8,112 rows changed: decay
outpaced every write, which is the same direction the 2026-10-25 and 2026-10-27
measurements found.

**The guarded battery's stage map did not move at all.** Teaching 20 new facts left
the standing failure profile byte-identical, so the new material neither helped nor
interfered with what was already there. That is what non-erosion looks like when it
holds, and it is the reason the constraint is worth gating on.

### Two honesty items from the run

**The pilot row was corrected in place, visibly.** Episode 99 was the instrument
pilot (3 facts, `--tier open`) and it recorded `verdict: PASS` with frozen 0/0 — the
erosion gate had passed on nothing it measured. The gate was fixed afterwards
(unmeasured is `None`, and `None` fails), but the row was already in an append-only
ledger. `docs/evidence/correct_pilot_row.py` rewrote that one row to `FAIL`, kept the
original verdict and gate value inside a `correction` block, marked it
`kind: instrument-pilot`, and copied the ledger to `episodes_precorrection.jsonl`
first. A false PASS in a ledger is worse than an edited one, and the edit is recorded
rather than silent. `test_a_passing_episode_really_did_measure_erosion` now enforces
the invariant: any row claiming PASS must have run all 24 frozen asks and at least one
guarded probe, and any corrected row must not claim PASS.

**The interpreter is not the one the command line says.** §8's commands are written
`py -3.10`, following the README, but `.venv` on this box is Python 3.12.10 with
numpy 2.5.4 and that is what ran E1 — the same interpreter as generations 0-2, so the
frozen and guarded numbers are comparable to the committed baseline. `py -3.10` does
have the dependencies. The episode row carries `provenance.python` and
`provenance.numpy`, which is the only reason this is checkable rather than assumed.

## 9. What would invalidate the programme

Recorded so the checks are not invented after the fact.

- **The frozen or guarded tiers move.** Any change to `scripts_heldout.json` or to the
  four guarded probes invalidates every episode recorded against the old seal. The
  harness already refuses to run on a changed frozen seal; the episode runner must do
  the same.
- **The generator draws from a closed vocabulary.** If its content words are a private
  list rather than the live 11,555, every result is the `fly_v2` overfitting failure
  wearing a different number. Checkable: the generator's word source is the loaded
  vocabulary, and an episode row records how many distinct content words it used.
- **Teach and held-out batches overlap.** If a held-out ask uses a phrasing that was
  taught, the generalisation number is recall. Checkable by set intersection on the
  two batches' token sequences, asserted in a test.
- **Episodes are compared across different live states.** An episode row carries the
  before/after state seals; two episodes whose parent seals differ are not comparable
  and must not be plotted as a trend.
- **`state/lineage/` is capped at 2.** `state_hygiene.py:44` would delete a lineage.
  Raising that constant is a tool change and must happen before the second episode,
  not after the first two checkpoints are gone.
- **The house is up during an episode.** `consolidate_live.py` states it plainly: a
  concurrent writer would fight the guard, not lose to it.

## Change log

- 2026-10-30 — written, before any code. Grounded in a fresh census of the live
  binder (`docs/evidence/binder_census.py`, output committed beside it) rather than in
  the 2026-10-25 figures in `docs/cross_session_design.md`, which the census
  reproduces exactly for the `who` distribution and extends with the count and age
  distributions. No core code modified, no episode run, no checkpoint written,
  `state/lineage/` still empty. Suite at 484 passed, 3 skipped.
- 2026-10-30 — **defect found while writing §3.2, recorded before anything was built
  on top of it.** `WITNESS_W` (`neural_language.py:483`) has no `"you"` key and
  nothing binds `who="user"`, so `consolidate()`'s only use of it (`:503`,
  `.get(who, 0.6)`) scores user testimony at exactly the `book` weight — verified
  equal at every count. With 59,665 of 60,000 rows tied at 0.415888 and
  `scan_top = 2000`, the window fills by stable sort on binder order, so consolidation
  currently replays the **oldest corpus rows** and gives a taught fact no protection
  at all. §7 was rewritten as two ordered changes (7a the missing key, 7b the
  flag-gated eviction) because value-weighted eviction built on the existing signal
  would have ranked testimony as corpus. Not fixed here: it is core code, and step 6
  of the instruction defers core changes until the design and tests exist.
- 2026-10-30 — **E1 run and PASSED, all five gates.** `tools/teach_episode.py`
  implemented to §8's specified interface; `tools/run_generation.py` gained the
  `open` tier, `--open-batch`, `--state-root` and `--report --episode`, so the open
  tier runs through the same runner, grader and journal as the other three rather
  than beside them. 20 facts, 82 asks, 34 min: acquisition **20/20** across a process
  boundary, generalisation **2/20** (H1 reverse-role 2/2, H2 question-word 0/6, H3
  passive 0/12), frozen 19/24 and guarded 4/4 unchanged, **erosion none**, 22 rows
  evicted all `book` count 1 with 20 `you` rows added, SAN nnz **+0** confirming
  saturation on freshly taught material, live seals unchanged. Two findings redirect
  the programme: phrasing brittleness transfers to material taught thirty seconds ago,
  so **teaching more facts will not move rung 2**; and blind FIFO evicted exactly the
  low-value corpus rows, so §7b is not needed for small episodes on a uniformly
  low-value tail — it becomes necessary only once a taught row ages far enough that
  60,000 further binds reach it. The episode-99 pilot row was corrected in place from
  a vacuous PASS to FAIL with the original kept in a `correction` block and the ledger
  backed up first. Suite **509 passed, 3 skipped**. No core code modified, nothing
  promoted to live state, `state/lineage/` now holds the ledger.
