# Primitive-mining criteria (frozen)

Status: **FROZEN 2026-07-30**, written before `tools/mine_primitives.py` runs.
No revision after results are seen; every later edit needs a dated entry in the
change log at the bottom. This is the contract for proposal item 4, variant (b)
("mine the 30-day library for reusable primitives").

## 0. Blindness

The miner reads only (i) the procedure stores named below, (ii) this document,
(iii) an operator-supplied coverage-tasks JSON (schema in §7). It never reads
the battery, the held-out files, or any diagnosis narrative. The coverage
mapping against the nine refused tasks is a mechanical step over the kind
signatures defined here, applied by the operator to the miner's output.

## 1. Source corpus

Two stores are inventoried and reported separately:

- `state/house_agent_learning.json` — the live library the solver reads at
  runtime. This is where the battery-learned task procedures actually are
  (the proposal named `exocortex/learned_procedures.json` for these; that file
  was measured to hold 274 innate house methods + 3 trial replays and almost
  no task solutions, so the live store is the primary corpus. The correction
  is recorded here, before mining, so the number cannot be chosen after the
  fact).
- `exocortex/learned_procedures.json` — the seeder's output; inventoried for
  completeness and reported separately.

The miner found the live store at `state/house_agent_learning.json`
(9,845 lines, 680 procedures) and the seeder file at
`exocortex/learned_procedures.json` (277 entries: 274 innate + 3
trial_replay). 396 live entries qualified as mining sources under the rules
below; 1 seeder entry did.

An entry is a mining source only if **all** hold:

- `language == "python"`;
- at least one solution with `verified == true`;
- `source` in `{corpus, local, prim, compose, oracle, reasoning_loop,
  trial_replay}`;
- **not** `source == "innate"` — house machinery is not task vocabulary.

Per source entry, fragments are lifted from the most recent verified solution
only.

## 2. What counts as a reusable primitive

A fragment is a strict sub-part of a stored solution, lifted as one of:

- (a) comprehensions (list/set/dict/generator), with or without a filter;
- (b) `for`-loops with an accumulator (append or `+=`);
- (c) `while`-loops with an index or accumulator;
- (d) counting-dict idioms (`d[x] = d.get(x, 0) + 1`) and selection over
  counts;
- (e) single-expression returns using a builtin transformation (`sorted`,
  `set`, `sum`, `join`, `split`, `replace`, `ord`/`chr`, slicing).

The lifted block excludes the function's final `return`; the miner's wrapper
supplies `return <last assigned name>` (or the comprehension itself).

**Parameterizability (the generalization bar).** Every literal in the fragment
is masked to a slot; the original literal is the default fill. A fragment with
no literals is admitted only if its normalized form is not already in the
candidate space (§4). A fragment that reads no enclosing function parameter is
a constant, not vocabulary, and is rejected. A fragment whose only liftable
content is a name the junk list already covers as a builtin is rejected.

**Dedupe.** The normalized form (AST dump with literals masked and names
canonicalized) must not match any body in `PRIMITIVES`, `HINTS`, `HINT_PAIRS`
or `PROGRAM_SHAPES` in `organs/reasoning_loop.py`, nor an already-mined
fragment (first wins; ties by source confidence, then store order).

## 3. Verifier standard

Every candidate fragment is wrapped as a standalone function (free names that
are enclosing parameters become parameters; masked literals become keyword
parameters with the original literal as default) and run in the sandbox:

- on the source solution's own stored examples, when present (correctness is
  inherited from the verified solution; this checks the generalization did not
  break the fragment);
- on a fixed synthetic battery — strings `'droso'`, `'Hello, World!'`, `''`;
  int lists `[1, 2, 3]`, `[]`, `[5, 5, 1]`; str lists `['a', 'b', 'a']`;
  ints `0`, `1`, `7`, `13` — one subprocess per fragment, timeout 10 s.

Admissible iff at least 3 inputs run clean (exit 0, no exception) **and** the
fragment runs clean on the source's own examples when those exist. Inputs of
the wrong type for the fragment may error; they are recorded, not fatal. The
recorded input→output behaviour is part of the admission report, so edge-case
wrongness (the `stem('class')` failure mode) is reviewable before anything is
banked. The verifier proves "runs"; the report makes "behaves" visible.

## 4. Same-lane admission

Mined primitives are banked into the live store as entries with
`source == "mined"`, trigger text = the source task's own wording, code = the
generalized fragment. They then ride the existing lanes with zero code change:

- the `library:` lane (token-overlap recall, same floor, same ranking);
- the compose lane (whole-procedure pool, which already adapts interfaces by
  renaming).

No new lane, no score bonus, no floor change, no gate change, no change to the
per-task enumeration budget (10) or the prog cap (14).

Known limitation, recorded now: the `library:` lane uses stored code verbatim,
so a banked fragment fires there only when its stored function name matches
the tests' target; the compose lane renames and is therefore the primary path.
If admission later adds the existing rename adaptation to the `library:` lane,
that is a small mechanical reuse of compose's machinery and must be logged as
a change; it is not part of this freeze.

Optionally, admission may *also* add mined entries as word-triggered
`HINTS`/`PROGRAM_SHAPES` entries (same scores the lanes already use: 0.3–0.45
prog, 0.35/0.4 hints; slots only of the existing `{c}`/`{e}` kinds with fills
from the existing `_INNER` tables). This is a candidate-space constant change,
subject to the budget in §5, and must be logged.

## 5. Enumeration budget

- Total mined entries admitted: **≤ 12**.
- Per diagnosed kind: **≤ 4**.
- Per source procedure: **≤ 2**.
- Ranking when over budget: source confidence desc, then fragment size asc
  (smaller fragments compose more).

## 6. Kind signatures (structural, for coverage accounting)

- **membership** — a filter test over elements using a character/string class
  predicate (`isalpha/isdigit/isspace/isupper/islower`, or membership in a
  literal string).
- **accumulate** — a loop where a running value is updated **and** appended
  (or emitted) each iteration.
- **distinct-selection** — a counting dict followed by selection over the
  counts (max/min by count, or first with count == 1).
- **interleave** — alternated appends from two sources, or insertion of a
  separator between elements.
- **char-shift** — `ord()` and `chr()` in the same expression (shift
  arithmetic).
- **DP** — a table indexed by loop variables with self-referential assignment
  (`dp[i][j]` from `dp[i-1][j]` / `dp[i][j-1]` / `dp[i-1][j-1]`).

## 7. Coverage accounting (the measured number)

The nine refused tasks (count_vowels, second_largest, slugify, intersperse,
most_common, rot13, levenshtein, pig_latin, running_total) with their
diagnosed kinds. A refused task is **covered** iff ≥ 1 admitted mined entry
has a matching kind signature **and** at least one of its trigger words
appears in the task's wording. The dry-run reports: per kind, admitted entry
names; per refused task, covered yes/no and by which entries; and the count of
covered tasks. This replaces the proposal's 4–6 analogy estimate with a
measurement. The same mapping is reported for the fresh set, clearly
separated, as the "after" probe target. The fresh set's pre-admission
first-contact baseline is `state/fitness/fresh_baseline.json`, beside the
0.6834 composite snapshot (`baseline_cap1024.json`): 11 clean slots, 0
passed, all routed to the reasoning loop, oracle disabled, learn=False.
The count_digits slot was excluded — a probe bug let a library-recallable
task through; the bug and the exclusion are recorded in the file's
provenance wrapper and fixed in `tools/fresh_heldout.py`.

Coverage-tasks JSON schema (operator-supplied):
`[{"name": str, "task": str, "kind": one of the six}]`.

## 8. What the dry-run may touch

Reads: the two stores, `organs/reasoning_loop.py` (constants only, for
dedupe), this document, the coverage-tasks JSON. Writes: its report under
`_tmp/` and nothing else. No store writes, no candidate-space writes, no gate
changes. Without `--dry-run` the tool refuses to run: admission is a later,
logged change.

## Change log

- 2026-07-30 — frozen (pre-change measurement turn). No edits yet.
- 2026-10-25 — mining run executed per §1–§7: 680 live + 277 seeder entries
  inventoried, 397 selected as mining sources, 23 fragments lifted, 8
  admitted (all from the live store), refused-set coverage 6/9. Fresh
  baseline measured (11 clean slots, 0 passed, oracle disabled, learn=False)
  and saved with provenance to `state/fitness/fresh_baseline.json`; runner
  moved to `tools/fresh_heldout.py` with the recall-probe bug fixed
  (Recalled is not a dict; an errored freshness probe now counts as seen).
- 2026-10-25 — admission keying corrected: the eight banked fragments were
  keyed `signature(src_task) + " mined"`, which made each fragment's surface
  a strict superset of its source's. Any query recalling the source then
  scored the fragment identically and the margin gate read a tie — measured
  on the live store (688): the probe query "level nest zephyr quixotic"
  fell from WIN (0.418, no runner) to TIE (0.410 vs 0.410) the moment the
  flatten fragment was banked. Fix: re-keyed in place by
  `tools/rekey_mined.py` as `signature(kind_phrase + own_code_words)` —
  the miner's kind (§6) plus the identifiers and string-literal words of
  the stored fragment itself (params, builtins, `_cN` slots and the
  `mined_*` name excluded). The superset relation is gone; the source keeps
  every query it ever won. Verified: store integrity (688 entries, only the
  8 mined keys and their `signature` fields changed, insertion order and
  all other fields byte-identical, backup
  `state/_learning_backup_before_rekey.json`); the shadow-tie probe returns
  to WIN with pre-mining scores; recall verdicts on the 34 real tasks
  (12 regression + 12 fresh + 10 heldout) are zero-diff before/after at
  both floors. Honest reachability after the re-key: **no** mined entry
  wins a recall on any real task — best ranks are 3rd (vowels fragment,
  0.248 on strip_vowels, behind its own source at 0.361) and 4th (flatten
  fragment, 0.320 on flatten_deep); five of eight share no vocabulary with
  any real task at all. The fragments are reachable through the compose
  lane (§4's primary path), which finds them by code structure, not task
  wording. `tools/admit_primitives.py` now derives keys the same way for
  future admissions. Full suite 365 passed / 3 skipped.
- 2026-10-25 — `--no-learn` was not airtight: the flag gated the battery's
  bank call, but the router's recall branch (`organs/fast_router.py`) calls
  `learning.reinforce` and `learning.alias_request` on its own account, so a
  learn=False regression run banked 12 reinforces (measured: 12 events at
  6.2 s cadence, one per task, all on entries the run had merely recalled),
  and an earlier probe batch had done the same to one entry at ts 1792944780
  (the shadow-tie/settle batch: 8-recall burst, then a verified recall →
  reinforce). Fix: a `read_only` seal on `LearningLoop` — every writer
  (bank, reinforce, alias, save, event) refuses when it is set — and
  `_build(use_library, learn)` threads the flag down. learn=False now means
  zero writes, in memory and on disk. Verified: full suite 365 passed /
  3 skipped in-process, house down; the 30-day regression re-run through
  `docs/evidence/verify_seal.py` gives 12/12 (all router rung, 0 oracle calls) with
  the store sha256 and the events line count (5108) byte-identical
  before/after.