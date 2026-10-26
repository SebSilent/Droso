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
`_tmp/suite_after_deletion.txt`), which is consistent with the tests being
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
is inert in warm — see `_tmp/role_chain_proposal.md` §2a and §4.3.