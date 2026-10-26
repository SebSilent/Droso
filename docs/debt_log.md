# Debt log

Dated entries for fixes and tests that exist but are not fully verified, or
observations that need a future decision. Newest last. Verification status is
stated per item; nothing here is claimed as proven that is not.

## 2026-10-25

### 1. Binder postings double-append fix — fixed, regression-tested, mutation-verified

`organs/higher_cortex.py:404-411` (the `_postings` maintenance in
`Binder.remember`): a re-remember of an existing row appended its postings a
second time, so the inverted index double-counted rows and recall returned
duplicates weighted by re-tell count. Fixed by rebuilding the row's postings
in place. Regression tests added at `tests/test_binder_postings.py`
(double-append and idempotent re-remember).

Verification: mutation check run today — reverting the fix kills both
regression tests (2 failed), restoring it passes them (2 passed), and the
restored file is byte-identical to the working copy. The fix is real and
guarded.

### 2. Observatory port-collision tests — present, suite green, arithmetic not fully reconstructible

Two tests exist at `tests/test_connectome_house.py:1006` (port takeover
detected) and `:1066` (bind refusal on a taken port). Current suite collects
**372 tests** and is green. At the point the Observatory tests were removed
from the working tree, the suite collected 367 (364 passed, 3 skipped —
`docs/evidence/suite_after_deletion.txt`), which is consistent with the tests being
part of the suite, but the exact batch arithmetic (365 → 367 → 372) cannot be
reconstructed without version control. What is verifiable stands: the tests
exist, cover both collision behaviours, and the suite is green with them in.

### 3. api_oracle HTTPError-without-body fix — fixed, tested, mutation-verified

`organs/api_oracle.py:778-787`: an `HTTPError` with no body made the
`hasattr(e, "read")` guard crash with `KeyError` (the class's `__getattr__`
raises for unset attributes when `fp is None`), masking the real status
instead of reporting `reason="http_<code>"`. Fixed: the body read sits in
its own try/except, so the HTTP code survives an unreadable body.

Closed: `tests/test_api_organs.py:126-159` covers both shapes — a 429 with
an empty headers dict and a 500 with `fp=None` — asserting
`reason == "http_<code>"`, `text == ""` and the error counted. 62 passed on
both interpreters (3.10 and 3.12). Mutation-verified both ways on 3.10, the
interpreter where the trap exists: with the guard reverted both tests fail
with `KeyError: 'file'` from `tempfile.__getattr__`; restored, 62 pass. On
3.12 the trap does not exist (`hasattr(e, "read")` is True and `read()`
returns cleanly with `fp=None`), so the test passes either way there — the
docstring's "measured on this interpreter (3.10)" note is what keeps the
test honest.

### 4. SAN global decay, now measured per-phase (observation, no action yet)

The cross-session smoke run
(`state/fitness/cross_session_20261025_214202.json`) is the first
instrument to record SAN totals per phase: tell phase moved total weight
298,817.75 → 281,861.625 (rows_changed 8145, nnz constant 66,107,030, new
edges 0); ask phase 281,861.625 → 268,988.062 (rows_changed 1818). Roughly
6% and 5% of total weight decayed per phase with **no rehearsal**
(`rehearsed_n=0` in both). This is the designed decay, not a bug — but
repeated sessions without rehearsal will erode old associations, and the
harness now makes that visible. Watch item: if cross-session battery runs
show monotone total-weight decline with no rehearsal counter-pressure,
rehearsal policy needs a look. Related finding from the same day: the sort
key's only cold-discriminating term (filler-idf) ranks narrative verbs and
is inert in warm; see `docs/evidence/role_chain_proposal.md` §2a and §4.3.

### 5. Where-filler fix is state-dependent on question shape (observation, no action yet)

The sfW fix's where-case (organs/neural_language.py:2012-2015) makes a
where-question's filler its **last token**, on the argument that the
locative lives at the answer's end. That argument holds for the script
shapes measured so far ("where is the box" / "where is the coat":
subject-final questions, locative-final answers). It does not hold for
questions where the subject is not the last token: "where is the box
kept" puts the filler on "kept", "where in the house is the box hidden"
on "hidden": the same tie-on-a-word problem the fix removed, in a
different guise, and a content verb can actively misrank. No current
script or ask form hits this (all where-asks in `tools/scripts.json` and
`tools/scripts_fresh.json` are subject-final), so nothing is broken
today; the risk is a future script that varies the where-question's
shape. If one is added, the filler rule needs a role-aware version
(findings proposal #1, role votes conditioned on proposition length)
rather than a positional shortcut.

### 7. ensure_baseline's fallback was broken two ways (fixed 2026-10-26 ~01:31; in-flight fresh suite ran on the old code)

`tools/benchmark_cross_session.py` `ensure_baseline()` falls back to
running a script's warm/cold baselines when the newest full-suite
report has no row for it: exactly the fresh-set case, since
`tools/scripts_fresh.json` scripts never appear in a
`script_benchmark_*.json` report. Two bugs, the second masked by the
first:

1. The cold invocation passed `["--cold"]` with no value;
   `tools/converse.py` `--cold` takes the scripts path as its value,
   so argparse aborted every cold baseline with `error: argument
   --cold: expected one argument` (exit 2), `ensure_baseline` returned
   None, and the suite table lost its warm/cold/x-cold columns.
2. Had the cold run succeeded, the code read only the *cold* report
   (the loop's last `tag`) and returned its pass_rate as **both** the
   warm and the cold number; the warm column would have silently
   shown cold performance.

Fix: pass the scripts path to `--cold`, and read each mode's own
report for its own rate. Applied while the 2026-10-26 suites were in
flight; the running fresh-suite processes hold the old code, so their
report's warm/cold columns are empty by construction. The fresh warm
files exist (the fallback's warm leg ran fine); the fresh cold
baselines are being run separately after the suites land, and the
comparison table is assembled from the report files directly. The
seen-set suite is unaffected: its baselines come from the full
`script_benchmark_*.json` report, so the fallback never fires there.

### 6. Live-file guard is blind to build-time writes; banc_brain.npz mtime churns every run (measured, no action yet)

Both guard windows start **after** the agent is built:
`tools/converse.py` main() builds at :612 and snapshots at :618;
`tools/benchmark_cross_session.py` run_phase() builds at :76 and
snapshots at :79. Any write during `build()` is outside every guarded
window, so a per-run `live_files_untouched=True` verdict proves the
*turns* wrote nothing, not that the *run* wrote nothing.

Measured during the 2026-10-26 suites: the live
`state/banc_brain.npz` mtime moves in step with every run start
(01:15:23, 01:16:29, 01:18:29, one per run), while every other live
file (language_state.json, cortex npz, san npy, seq npz) kept its
pre-suite mtime. Array-level comparison of two snapshots taken across a
run boundary (`docs/evidence/cmp_banc.py`) shows **identical content**: the
write is a no-op rewrite (np.savez embeds zip member timestamps, so
mtime moves even when arrays do not). The growth organ's first
consolidation tick saves the brain unconditionally
(organs/neural_growth.py:361-363), which is the likely writer; the
60 s timer makes exact attribution inside a busy suite awkward, so the
trigger is probable, not pinned.

Net assessment: no live-state contamination (content verified
identical, all other files verified unmoved), but the guard's clean
verdicts are narrower than they read. Fix shape: take the guard
snapshot before `build()` in both places and treat the known no-op
banc_brain.npz churn explicitly (whitelist with a comment, or report it
as a named known-touch), so the verdict covers the whole run. Not
applied while the suites are in flight; the running processes hold the
old code regardless.