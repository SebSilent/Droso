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

### E2, pre-registered before it is run

**What E2 is.** Teaching episode 2: 20 fresh facts at seed 2, run against live state
with §7a landed (`WITNESS_W["you"] = 1.0`). Same instrument, same shadow discipline,
same five gates.

```bash
py -3.10 tools/teach_episode.py --episode 2 --facts 20 --seed 2 --dry-run
py -3.10 tools/teach_episode.py --episode 2 --facts 20 --seed 2
py -3.10 tools/run_generation.py --report --episode 2
```

**Why a new seed rather than a repeat of seed 1.** Re-running seed 1 would isolate
§7a cleanly but would not test the property an organism actually needs — that learning
*repeats* on material it has not seen. The §7a effect is measured separately and more
sharply by the consolidation census inside the episode, so the episode does not have
to carry it. The consequence is stated up front: **episode 1 and episode 2 differ in
both code and material**, so nothing below predicts that E2's numbers will match E1's,
and a difference between them is not by itself attributable to §7a.

**Predictions.**

- **P1 — acquisition repeats: ≥ 18/20.** Episode 1 was 20/20. Falsifier: a material
  drop means the frame or the generator is seed-sensitive rather than the organ being
  reliable, and the generator becomes the thing to fix, not the organ.
- **P2 — generalisation is again dominated by frame, not by memory.** H2
  (question-word swap) and H3 (passive) predicted **0**, because their causes are
  literal-string dependencies in the answer path — the shape parser keyed to `what`,
  the passive losing retrieval — and §7a touches neither. H1 (reverse role) predicted
  to pass on most or all of its facts. If H2 or H3 *rises*, that is surprising and
  must be checked before it is believed, because nothing in this change should move
  it.
- **P3 — zero erosion.** Frozen 19/24 and guarded 4/4, unchanged. A gate, not a
  prediction.
- **P4 — displacement repeats in kind.** Roughly 20–25 rows evicted, all `book`, all
  count 1; roughly 20 `you` rows added. §7a changes consolidation's *ranking*, not
  the binder's eviction, so displacement should not move at all.
- **P5 — the §7a effect, which has two legitimate outcomes.** The episode records
  `taught_urgent` (how many of the 20 taught rows sit below the 0.1 urgency line) and
  `consolidate_picked_who` (the `who` distribution of consolidation's own returned
  sample, capped at 20 of `budget` and recorded as a sample).
  - **P5a** — if `taught_urgent == 0`, no taught row is eligible for replay, because
    `consolidate()` repairs *decayed* wiring and a fact taught seconds ago is still
    strong. Then `consolidate_picked_who` contains no `you`, and **that is correct
    behaviour rather than a failure of §7a**: the protection §7a buys is real but
    deferred to taught rows that have aged, which is exactly the horizon an organism
    that keeps being taught reaches.
  - **P5b** — if `taught_urgent > 0`, at least one taught row is eligible, and post-7a
    it ranks at `1.0·log1p(count)` against the corpus's `0.6·log1p(count)`, so `you`
    should appear in `consolidate_picked_who`. Episode 1's picked sample was
    **book 188 / droso 11 / parent 1, with no `you` at all** — that is the pre-7a
    comparison, and it is the whole of the evidence E1 can offer on this point.
  - **What would falsify §7a:** `taught_urgent > 0` and still no `you` in the picked
    sample. Either branch of P5 is a result; that combination is not.
- **P6 — SAN nnz unchanged (+0).** Saturation was confirmed on freshly taught material
  in episode 1 and nothing here should change it. Total weight expected to fall again,
  decay outpacing writes.

**What E2 cannot show, stated so it is not claimed later.** Retention across a
*second* restart. Chained episodes — episode 1 was not promoted to live state, so
episode 2 starts from the same live binder, and chaining requires promotion, which is
a deliberate act and a later step. And the far-term eviction horizon §7b addresses,
which needs a taught row old enough that 60,000 further binds reach it.

**Gates.** The same five. `erosion_zero` must be measured on all 24 frozen asks and at
least one guarded probe; the pilot's vacuous PASS is now structurally impossible,
because `verdict_of` fails a gate that was never run and
`test_a_passing_episode_really_did_measure_erosion` enforces that on every ledger row.

**If a gate fails.** Erosion > 0 → stop, and do not run episode 3: teaching would be
costing capability, and §7b becomes a prerequisite rather than an improvement. Live
seals moved → the shadow is leaking; fix before any second run, because every later
number would be measured against a contaminated state. Acquisition 0 → the bind site
or the reply gate, not eviction, is the first blocker, and the ladder's rung 1 is
wrong about what it measures.

### E2, measured

20 facts, seed 2, 82 asks, 2,059 s (34 min), one shadow, live state never written.
`state/lineage/episodes.jsonl` episode 2. **Verdict PASS — all five gates.**

| | E1 (pre-7a, seed 1) | E2 (post-7a, seed 2) | prediction |
|---|---|---|---|
| acquisition | 20/20 | **20/20** | P1 ≥18/20 — **confirmed** |
| generalisation | 2/20 | **3/20** | P2 — **confirmed** |
| — reverse role | 2/2 | **3/3** | most or all — **confirmed** |
| — question-word swap | 0/6 | **0/10** | 0 — **confirmed** |
| — passive | 0/12 | **0/7** | 0 — **confirmed** |
| frozen / guarded | 19/24, 4/4 | **19/24, 4/4** | P3 unchanged — **confirmed** |
| erosion | none | **none** | gate — **held** |
| evicted | 22, all `book` count 1 | **23, all `book` count 1** | P4 — **confirmed** |
| added | 20 `you`, 2 `droso` | **20 `you`, 3 `droso`** | P4 — **confirmed** |
| SAN nnz | +0 | **+0** | P6 — **confirmed** |
| SAN total weight | −30,211 | **−41,930** | falls again — **confirmed** |
| consolidation picked, `you` | **0** | **6** | P5b — **confirmed** |

**P5 resolved, and it is the result §7a was for.** `taught_urgent` was **6 of 20** —
six taught rows sat below the 0.1 urgency line and were therefore eligible for replay
at all. Consolidation's picked sample came back `{book 1, droso 11, parent 2, you 6}`:
**all six eligible taught rows were selected.** Episode 1, pre-7a, picked
`{book 2, droso 16, parent 2}` — **zero `you`** — with 20 taught rows sitting in the
same binder. So the one-entry change moved consolidation's selection in vivo from
never protecting a taught fact to protecting every one that needed it, which is
exactly the mechanism §3.2 said was broken and §7a said it would fix. The sample is
20 of 200 picked and is recorded as a sample, but six of six appearing in it means the
taught rows rank near the top, not merely inside the budget.

**Learning repeats on fresh material.** Acquisition 20/20 on a different seed with
different facts, and displacement the same in kind. Rung 1 is not a one-off.

**Rung 2 is confirmed to be an answer-path property, not a memory property.** H2 0/10
and H3 0/12 on facts taught seconds earlier, reproducing E1's 0/6 and 0/12 on a
different seed. Reverse-role again passed on every fact it was assigned (3/3, and 2/2
in E1), so the fact is stored as a relation queryable from either end — but the
surface form has to contain a literal `what` and has to be active voice. Five asks
across two seeds is still a small sample for H1 and is reported as such.

**One stage moved, and it is bounded and explained.** The guarded battery's stage map
went from `recall 10, mouth 4` to `recall 9, mouth 5`. Per-ask comparison across four
measurements finds exactly one difference: `sel-exact-repeat::which thing turns
twice?`, which **fails either way** and moved from `recall` to `mouth`. Pass sets are
identical across all four (23 each), erosion is zero, and episode 1 against the
pre-7a control shows **0 differences** — so the shift is caused by episode 2's shadow
holding 20 different taught rows, not by §7a (generation 3 already ruled that out on
live state, 0 of 42 asks differing). The lesson is a limit on the diagnostic, and it
is recorded because §3 leans on stage maps: **stage distributions are comparable
across generations on the same state, but not across episodes whose taught material
differs.** An already-failing ask's stage attribution is sensitive to what else is in
the binder.

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

## 10. Promotion: from a shadow episode to a persistent learner

Implemented in `tools/promote_learner.py`, with `--state-root` and
`--keep-checkpoint` added to `tools/teach_episode.py`. Episodes 1 and 2 are **not
promotable**: they measured retention and then deleted the animal with their session
directory. That was correct for E1 and E2, whose question was whether teaching works
at all, and it is why `--keep-checkpoint` is opt-in rather than default.

### 10.1 Why a separate area, and what would break without it

```
state/language_state*, state/banc_brain.npz    the GUARDED live animal -- never written
state/live_learner/manifest.json               the version chain and current pointer
state/live_learner/current/                    what the next episode builds on
state/live_learner/versions/v<N>_<id>/         immutable snapshots
state/live_learner/staging/ep<N>_<id>/         checkpoints awaiting promotion
state/lineage/promotions.jsonl                 one row per bootstrap/promote/rollback
```

The guarded baseline means something only because the state it was measured against
has not moved. `tools/selection_baseline.json` freezes 19 passes and 4 guarded probes
against the live animal, and `run_generation.py` refuses to run if the frozen suite's
seal moves. Promoting a taught episode **on top of** the live state would quietly
redefine what 19/24 refers to, and every generation recorded so far — 0, 1, 2, 3, 504
ask evaluations with a measured noise floor of zero — would become incomparable to the
next. So the learner lives beside the live animal and `live_seals()` globs `state/`,
never `state/live_learner/`. A test pins that by reading the function's own source.

Bootstrap copies the live state into `v0`, so the learner's ancestry *is* the guarded
animal and the first chained episode starts from a known point.

### 10.2 Hardlinks, and the invariant that makes them safe

A checkpoint is 260.6 MB, 222 MB of it the binder's `cortex.npz`. Full copies would
make versioning unusable, so every file in the learner area is a hardlink — the same
mechanism and the same safety argument as `benchmark_cross_session.build_shadow`:
`save_state` writes tmp-then-rename, which **replaces** a link rather than writing
through it, and a checkpoint is only ever read. `link_tree` records `link: true/false`
per file, because a file that cannot be linked (different volume, permissions) is
copied, and silently copying 222 MB while calling it a link would make the disk cost of
versioning invisible. `--verify` re-seals `current/` against the manifest, so the
invariant is checked rather than assumed.

### 10.3 Promotion is never automatic, and refuses for five reasons

`teach_episode.py` always records `promoted_to_live: false` and cannot promote.
Promotion is a separate command with an explicit `--promote --episode N`, and any one
of these refuses it rather than warning:

1. the episode's verdict is not PASS, or any of its five gates is not exactly `True`
   (`None` — a gate that was never run — refuses, which is the pilot's lesson);
2. the episode did not run all 24 frozen asks, so erosion was never really measured;
3. **the live state's seals now differ from the seals the episode recorded before it
   ran** — the episode is not promoted against a state that has since drifted;
4. the staging checkpoint is missing, or any of its file seals differ from the
   episode's recorded `checkpoint_files`, so what would be promoted is not provably
   what was measured;
5. the checkpoint's bytes are already a version, which would fork the chain onto
   identical content and make the version list lie about how much learning happened.

The new version's parent is the current version, so the chain stays linear. `current/`
is rebuilt into `current.tmp` and `os.replace`d, so a half-written swap cannot leave
`current/` pointing at a mixture of two versions.

### 10.4 Rollback

`--rollback` repoints `current/` at the parent version and **keeps** the version it
rolled back from, because a rollback that destroys the thing it is rolling back is not
a safety mechanism. The rebuilt `current/` is re-sealed against the target version's
recorded seals *before* the swap, and a mismatch refuses. Every rollback is recorded in
the manifest and the ledger with its reason. The version cap never prunes anything on
the rollback path — the current version and its ancestors are kept whatever `MAX_VERSIONS`
says — so `--rollback` always has somewhere to go.

### 10.5 The guard, and a false alarm it would have caused

`state/live_learner/` is inside `state/` and is not in `converse.GUARD_EXCLUDE`, so
creating a checkpoint shows up as "live files moved". The first bootstrap run reported
exactly that and exited 1. Reading it as damage would make the tool unable to do its
job; ignoring the guard wholesale would hide a real leak. So `finish_guard` splits the
moved list by prefix — own writes under `state/live_learner/` are counted and reported,
anything elsewhere fails the run — **and** re-seals the live learner files explicitly,
because the invariant that actually matters is that the guarded animal did not move, and
that deserves a direct check rather than an inference from a directory walk. Bootstrap
now reports `17 own writes, 0 elsewhere, live learner files byte-identical (8 sealed)`.

### 10.6 E3, pre-registered before it is run

**E3 is the first chained episode: promote, then teach from the promoted state.** Two
episodes, because a chained measurement needs something to chain onto.

- **Episode 3** teaches 20 facts at seed 3 starting from `state/live_learner/current`
  (which is `v0`, byte-identical to the live animal), with `--keep-checkpoint`. It is
  then promoted to `v1`.
- **Episode 4** teaches 20 facts at seed 4 starting from `v1` — so its binder already
  holds episode 3's 20 taught rows and has already evicted its 23 corpus rows. This is
  the first measurement of an organism that has been taught twice.

Predictions, with falsifiers:

- **P1 — acquisition repeats a third time: ≥18/20** on both episodes. E1 and E2 were
  20/20 on seeds 1 and 2.
- **P2 — episode 4 still answers episode 3's facts.** Not measured by the open tier,
  which only asks about its own batch, so this needs episode 3's acquisition asks put
  to episode 4's shadow. **This is the retention-across-episodes number the whole
  programme is for**, and it is the one E1 and E2 structurally could not produce.
- **P3 — zero erosion on both episodes.** Frozen 19/24 and guarded 4/4. Episode 4 is
  the sharper test: its binder differs from the guarded animal by 40 taught rows and
  ~46 evicted corpus rows, so this is cumulative erosion rather than per-episode.
- **P4 — displacement stays cheap and stays corpus-only.** Roughly 20–25 evicted per
  episode, all `book`, all count 1. If episode 4 evicts a `you` row, the taught rows
  from episode 3 have reached the FIFO tail, and that is the horizon §7b exists for —
  it would be the first evidence that value-weighted eviction is needed now rather than
  later.
- **P5 — consolidation selects the taught rows.** Post-7a, `taught_urgent > 0` should
  put `you` rows in the picked sample, as episode 2's 6 of 6 did. In episode 4 the
  binder holds *two* generations of taught rows, so the sample may contain rows from
  episode 3 as well; that would be the first evidence that consolidation protects an
  **aged** taught fact and not only a fresh one, which is the property §7a was for.
- **P6 — SAN nnz unchanged (+0)** on both episodes.
- **P7 — the chain is linear and verifiable.** `--verify` reports `v1 <- v0` after the
  first promotion and `v2 <- v1 <- v0` after the second, with `current/` matching its
  recorded seals and the live state byte-identical to the bootstrap state throughout.

What E3 cannot show: retention across a *restart of the house* rather than across a
shadow build (the shadow build is a fresh process, so this is close but not identical);
more than two chained episodes; and any effect of §7b, which is not implemented.

If a gate fails on episode 4, `--rollback` returns the learner to `v1` and the episode
is recorded as refused rather than promoted. Nothing is promoted automatically at any
point in E3.

### E3, measured

Episode 3 (seed 3, from `v0`, `--keep-checkpoint`) promoted to **`v1_8be802548643`**;
episode 4 (seed 4) taught from `v1`. 82 and 102 asks, 2,024 s and 2,388 s. Both
**PASS on all five gates**.

| | ep3 (from v0) | ep4 (from **v1**, chained) | prediction |
|---|---|---|---|
| acquisition | 20/20 | **20/20** | P1 ≥18/20 — **confirmed, 4th episode running** |
| **retention of ep3's facts** | — | **20/20** | P2 — **confirmed** |
| reverse-role | **7/7** | **7/7** | most or all — **confirmed** |
| question-word swap | 0/3 | 0/6 | 0 — **confirmed** |
| passive | 0/10 | 0/7 | 0 — **confirmed** |
| frozen / guarded | 19/24, 4/4 | **19/24, 4/4** | P3 — **confirmed** |
| erosion | none | **none** | gate — **held, cumulatively** |
| evicted | 22, all `book` count 1 | 21: **20 `book` count 1 + 1 `droso` count 4561** | P4 — **partly falsified** |
| added | 20 `you`, 2 `droso` | 20 `you`, 1 `droso` | P4 — confirmed |
| SAN nnz / total | +0 / −42,941 | **+0 / −16,948** | P6 — **confirmed** |
| `taught_urgent` / picked `you` | — | **9 / 20 → 7 `you` in the sample** | P5 — **confirmed** |
| chain | `v0` | **`v1 <- v0`, `--verify` OK** | P7 — **confirmed** |

**Retention across episodes is 20/20, and this is the number the whole promotion path
exists to produce.** Episode 4's binder read `you: 20` at startup — episode 3's taught
rows, inherited through promotion — and every one of episode 3's acquisition asks was
answered again after a further 20 facts were taught on top and a further 21 corpus rows
evicted. E1 and E2 structurally could not produce this number: each taught into a
shadow and threw the animal away.

**Zero erosion is now cumulative, not per-episode.** Episode 4's binder differs from the
guarded animal by 40 taught rows and 43 evicted corpus rows, and the frozen 24 and the
4 guarded probes are unchanged. The floor survives two episodes of open learning.

**P5's strongest branch.** `taught_urgent` was 9 of 20 and consolidation's picked sample
was `{droso 13, you 7}` — and the picked `you` rows include facts from **both** episodes
(`the uncertainty breach the wearisome` and `the alfred bowing the dispel` are episode 3's;
`the gigantic jury the committal` and `the breeches amused the platform` are episode 4's).
That is the first evidence that §7a protects an **aged** taught fact and not only a fresh
one, which is the property it was landed for. Pre-7a, episode 1 picked zero `you` rows.

**P4 partly falsified, and the falsification is the useful part.** One evicted row was a
`droso` row with **count 4561** — rehearsed four and a half thousand times and evicted
anyway, because blind FIFO consults nothing. Episodes 1–3 evicted only count-1 `book`
rows, which is why §7b looked deferrable; this is the first measured case of FIFO
destroying a high-value row. It does not change the decision to defer §7b — no capability
was lost, the guard held — but it converts §7b's justification from an argument about a
future horizon into an observed event, and it is recorded as a falsified prediction rather
than folded into P4's confirmation.

**Reverse-role is 12/12 across three seeds** (2/2, 3/3, 7/7). A taught fact is stored as a
relation queryable from either end. Question-word swap is 0/9 and passive 0/17 across the
same three: rung 2's brittleness is a property of the answer path and reproduces on facts
taught minutes ago, so teaching more facts will not move it.

### Two guard false alarms, and the check that replaced them

`state/live_learner/` is inside `state/` and is not in `converse.GUARD_EXCLUDE`, so
`--keep-checkpoint`'s own writes read as damage and episode 3 was marked FAIL on a gate
whose substance had passed. Two hardlinked `.npz` files were also reported moved while
their sha256 was identical, because `converse`'s guard keys `.npz` by zip-member CRC and
size rather than by a hash of the bytes.

Both tools now split the moved list by prefix — own writes under `state/live_learner/`
counted and reported, anything elsewhere failing the run — **and** sha256-seal the live
learner files directly, plus the learner root the episode started from, so a mutated
checkpoint cannot hide behind a directory walk. Episode 3's row was corrected from FAIL
to PASS by `docs/evidence/correct_episode3_gate.py`, which recomputes the gate from data
already in the row plus `promote_learner --verify` run at correction time, keeps the
original verdict inside a `correction` block, and backs the ledger up first. Its
`checkpoint_files` were sealed afterwards by `docs/evidence/seal_episode3_checkpoint.py`,
tied to the run by mtime — every file must predate the episode's end — because the episode
ran before that field existed and re-running 34 minutes to produce the same numbers would
prove nothing. `test_a_passing_episode_really_did_measure_erosion` was too strong here and
was narrowed: it banned any corrected row from claiming PASS, which was written for the
pilot and would have forbidden a justified upgrade. It now requires that an upgrade carry
computed evidence — nothing moved outside the learner area, live sha256 seals unchanged,
`--verify` OK — and still satisfy every ordinary PASS condition.

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
- 2026-10-30 — **§7a landed alone** (`876dde0`): `WITNESS_W` gains `"you": 1.0`. All
  three required proofs attached — generation 3 shows 0 of 42 guarded-battery asks
  differing from the pre-change reference (504 evaluations across 12 lines, noise
  floor still zero); `docs/evidence/consolidation_census.py` shows the before/after
  selection byte-identical on live state (which holds zero `you` rows) with its
  replica validated against the real function's counters; suite green. The test
  written to fail on this fix failed and was updated deliberately, with the census in
  its docstring. §7b not started.
- 2026-10-30 — **E2 run and PASSED, all five gates**, and every one of the six
  pre-registered predictions confirmed. Acquisition 20/20 on fresh material, so
  learning repeats. Generalisation 3/20 — reverse-role 3/3, question-word swap 0/10,
  passive 0/7 — confirming rung 2 is an answer-path property and not a memory one.
  Frozen 19/24 and guarded 4/4 unchanged, erosion none, 23 rows evicted all `book`
  count 1 with 20 `you` added, SAN nnz +0. **P5b confirmed: `taught_urgent` 6 of 20
  and consolidation's picked sample contains all six `you` rows, against zero in
  episode 1 pre-7a** — the one-entry change moved consolidation from never protecting
  a taught fact to protecting every one that needed it. One guarded ask's stage moved
  (`which thing turns twice?`, recall → mouth, failing either way); pass sets
  identical across all four measurements and episode 1 vs the pre-7a control shows 0
  differences, so the cause is the shadow's different taught material and not §7a.
  Recorded as a limit on the stage-map diagnostic: comparable across generations on
  the same state, not across episodes with different material. Suite **510 passed,
  3 skipped**. Nothing promoted to live state; §7b still not started.
- 2026-10-30 — **§10 promotion path implemented and E3 run.** `tools/promote_learner.py`
  (bootstrap / promote / rollback / verify / status) with a separate
  `state/live_learner/` area, hardlinked immutable versions, a linear chain, five
  promotion refusals, and a ledger; `teach_episode.py` gained `--state-root`,
  `--keep-checkpoint` and `--retained-batch`; `run_generation.py` gained a fifth
  `retained` tier so an earlier episode's taught facts can be asked of a later learner.
  Bootstrap `v0_a7808217f2da` from live state; episode 3 (seed 3) promoted to
  `v1_8be802548643`; episode 4 (seed 4) taught from `v1`. Both PASS on all five gates.
  **Retention 20/20** — every fact taught in episode 3 answered again in episode 4 after
  20 more facts and 21 more evictions — and **erosion zero cumulatively**, the frozen 24
  and guarded 4/4 unchanged on a binder 40 taught rows and 43 evicted corpus rows away
  from the guarded animal. Acquisition 20/20 for the fourth episode running;
  reverse-role 12/12 across three seeds; question-word 0/9 and passive 0/17.
  Consolidation picked 7 `you` rows out of `taught_urgent` 9, including facts from
  **both** episodes — the first evidence §7a protects an aged taught fact. **P4 partly
  falsified and recorded as such:** one evicted row was a `droso` row with count 4561,
  the first measured case of blind FIFO destroying a high-value row, which converts §7b's
  justification from a future horizon into an observed event without changing the decision
  to defer it. Two guard false alarms fixed by splitting own-writes from damage and
  sha256-sealing the live learner files and the learner root directly; episode 3's row
  corrected FAIL→PASS on computed evidence with the original kept and the ledger backed
  up; one test narrowed because it banned a justified upgrade. Suite **531 passed,
  3 skipped**. The guarded live state was never written: `--verify` reports it
  byte-identical to the bootstrap state. §7b still not started; no multi-brain work.
