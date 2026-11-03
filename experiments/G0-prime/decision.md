# G0-prime — Decision Record: Freezing the Capability Instrument

**Gate:** G0-prime (DROSO Master Plan v1.1, §B.1). Freeze `electric_learn_bench` as a capability
instrument so MP-E9 can open.
**Recorded at:** HEAD `5d03621` (== `origin/main`), branch `main`.
**Plan baseline:** the plan states its baseline at `0b5f191`. `git log --oneline 0b5f191..HEAD` returns
four commits — `b7f1da4`, `e09c0b9`, `0b5f191`→`5d03621` handover-note commits — and
`git diff --stat 0b5f191 HEAD -- tests/ organs/` is empty. No organ or harness code differs, so the
plan's measured baseline still applies. This discrepancy is recorded at opening rather than silently
absorbed.
**Status:** **CLOSED under R13(a) as ruled by the PI (D-G0P-02) — with one named cell excluded. NOT
closed as "identical row for row", which measurement falsified and still falsifies.** Six of six B.1
steps are met or met-with-a-registered-exception. Step 3 — "three clones … must produce identical
outcomes row for row" remains **falsified as written**; it was resolved by the PI selecting from the three
R13 options **pre-registered before the run**, not by the agent, and the literal verdict is retained in
both artifacts as `NOT REPRODUCIBLE`. See §10. The suite blocker that also gated this record is
**closed, and now measured rather than inferred**: 1,167 collected, 1,167 reached,
0 collected-but-not-executed, **returncode 0, 0 failures, 3 skipped, 528.27 s** (§7). The earlier
exit-1 run stays on the record; the 1,164 → 1,167 move is attributed node-id by node-id and is not
collection instability. Blocker 1 was ruled by the PI as D-G0P-02 and the heard-not-told scope as
D-G0P-03 (§10); one question — `requirements.txt` pinning — is still open and travels with the gate into
MP-E9 rather than being quietly answered by the agent.

---

## 1. What was asked, and what the instrument says now

G0-prime exists because the project had two instruments and had only frozen one. G0 (closed) froze the
generation-0 fitness instrument. The electric bench — the thing that will decide MP-E8's three-arm duel
— was never frozen to the same standard, and the plan's own rule R5 forbids running a duel on an
instrument whose noise floor is assumed rather than measured.

The session's thesis, stated plainly because every finding below follows from it:

> The bench is not a pure function. It is a measurement of a creature that lives in wall-clock time.
> Three clones of one configuration are not three runs of one program; they are three measurements of
> an organism whose memory and refractory state continue between probes.

Everything that passed, passed because of that. Everything that failed, failed because of it.

---

## 2. B.1 checklist, step by step

| # | Requirement | Verdict | Evidence |
|---|---|---|---|
| 1 | Word-level provenance grader, audit trail per row | **MET** | `tools/word_provenance.py`, `experiments/G0-prime/results/word_provenance_audit.json` |
| 2 | Validate: flags the says-gap rows, none of the 24 guarded-absence rows, committed as a regression pin | **MET** | `tests/test_word_provenance.py` |
| 3 | Noise floor: three clones at depths 1/2/3 **identical row for row**; publish clone rows | **NOT MET as literally written** — **MET under D-G0P-02 with one named cell excluded** | clones published; 11 rows move, 20 differences reason-only, 1 graded row. The literal verdict is still recorded as `NOT REPRODUCIBLE` in both artifacts. §4, §10 |
| 4 | Commit harness, registration schema, failure taxonomy, journals, with harness version hashes | **MET** | `experiments/G0-prime/{registration,failure_taxonomy}.json`, `harness_hashes` manifest |
| 5 | Register tier protocol: 40/120/300 items, matrices scaling from the registered 136 | **MET** | `experiments/G0-prime/tier_protocol.json` |
| 6 | Write decision.md; gate does not close until every artifact is committed and sealed | **MET** | this file, committed; both registrations stamped and `--check` clean; suite baseline sealed as `results/suite_manifest.json` |

---

## 3. Step 1–2: the word-level grader, and the bug it exposed

The bench's existing `INVENTED` grader compares **whole sentences** against the told sentences.
`docs/HANDOVER.md` records exactly why that is insufficient: the word `says` is spoken by 16 rows, is
in none of the 27 told sentences, and is not even a word of the rows the arbiter drew from — yet
`failures` stayed **0**, because a single unsupported word is invisible to a sentence-level
comparison. G0-prime's central deliverable is the word-level version of that check.

`tools/word_provenance.py` grades every content word in an answer against three admissible sources —
a taught row, the ask itself, or an admitted source — and logs the trail per row. It **imports**
`REPORT_FRAMES` from `tools/electric_learn_bench.py:317` rather than restating it, so the grader and
`norm()` cannot drift apart; that tuple was moved to module level for this purpose. Refusal forms are
derived from the organ's own template (`organs/neural_language.py:177`/`:4893`) rather than a
whitelisted token list, so the grader survives a template change.

Validated against three pinned row sets, all three exactly:

| pinned set | rows | result |
|---|---|---|
| `says`-gap arbiter-head partial rows | **16** | all flagged `UNTRACEABLE_ASSERTED` |
| report-frame rows | **23** | **0** false aborts |
| guarded-absence rows | **24** | all admitted, **0** flags |

**The grader's first run was wrong, and the correction matters more than the pass.** The initial audit
flagged **39** untraceable rows. Two defects, both in the grader, not the organism:

* `tower` and `who` were false positives because the grader read pair **answers** but not pair
  **questions**, so a word taught only inside a question looked unsupported. Fixed by adding a
  `taught_questions` parameter sourced from `tools.electric_learn_bench.PAIRS`.
* After that fix the count resolved to **16 asserted + 6 heard-not-told = 22** rows.

The 6 `heard-not-told` rows are not a bug — they are a **scope question the plan did not anticipate**,
carried to §7. If R9 covers words that reached the organism only inside another question, then C1 fires
today at 22 rows rather than 16, and MP-E9's H1 threshold must be re-scoped before MP-E9 opens.

---

## 4. Step 3: the noise floor. The gate's real finding

Three clones, one configuration, arms control/teach/learn at depths 1/2/3, **3,672 probe-asks per
clone**, each clone a separate process with its own `--workdir` scratch root and its own `--out` path
so no clone can overwrite the committed baseline or share taught state. Wall clocks: 470.6 s, 451.3 s,
475.9 s.

| clone pair | rows compared | differences |
|---|---|---|
| clone1 vs clone2 | 3,672 | **11** |
| clone1 vs clone3 | 3,672 | **0** |
| clone2 vs clone3 | 3,672 | **11** |

**B.1 step 3 is not met as written.** But it failed in a localized way, which is a diagnosis rather
than a general loss of trust:

* **11 distinct rows of 3,672 are touched at all.** Clones 1 and 3 are identical on every row; clone 2
  differs from both on the same 11.
* **1 row differs in a graded field** — `learn/d1/reasked[120].said` is `droso says when does the bell
  toll` in two clones and `when the bell toll` in the third.
* **10 rows differ only in `reason`** — the organ's own coverage commentary moving by a percentage
  point (`41%`↔`40%`, `19%`↔`20%`), or flipping between two phrasings of the same refusal.
* **`cls` did not move on a single row.** No count of correct/partial/refused changes between clones.
* **Concentration:** arm `{'learn': 22}`, depth `{'d1': 22}`, phase `{'reasked': 16, 'restarted': 6}`,
  field `{'reason': 20, 'said': 2}` (summed over pairs).

That profile is the finding. Every difference is in the **learn arm at depth 1**, and **none is in the
`live` phase** — the first pass, before a question has been asked twice. `restarted` and `reasked` are
where the same probe recurs inside a short window. The **control and teach arms were byte-identical
across all three clones.** The instrument is not broadly unreliable; one cell of it, at one depth, in
the two phases that exercise a time-gated path, moves.

**The mechanism is in the organism, not the harness.** The language organ reads `time.time()`
throughout its answer path — including the **2.0 s refractory at `organs/neural_language.py:946-948`**
gating `experience("droso","says",…)`, the very row the says-gap depends on, and `_refractory()` at
`:956-971`, a time-since-dependent multiplier in word selection. Two clones under different machine
load are two measurements of a creature living in real time. This is the same cause that made the
pre-flag re-derivation diverge (§5), and it is now measured twice, independently.

Three resolutions were pre-registered under R13 **before** this number existed, so choosing one is not
choosing after the fact:

* **(a) Registered tolerance** — graded fields are results, `reason` percentages are noise. MP-E9's
  analysis plan already assumes this. Cheapest. But the one differing graded field is a `said` string,
  and `said` is what the says-gap is graded on, so tolerance must be written as *field-level*, not
  arm-level.
* **(b) Injectable clock** for the organ. Principled and the only one that makes the literal criterion
  true. But `connectome/clock.py` is a lived-time **ledger**, not a time source, so this is new
  machinery inside the organism and it changes what the instrument measures.
* **(c) Restate the criterion** as identity in every graded field except sub-threshold coverage
  percentages. Honest, but it edits the gate after the measurement, which is what R2 exists to prevent.

**Recommendation to the PI: (a), written field-level, with the single `said` difference registered as a
known non-reproducibility and re-measured once MP-E9 touches the refractory path.** (b) is the correct
long-term fix and should be scheduled, not improvised at a gate. This is a recommendation, not a
decision taken here — see §7.

---

## 5. Baseline re-verification (folded into step 3, not a separate detour)

The pre-flag snapshot was **re-derived** rather than restored. `tools/derive_pre_flag_snapshot.py`
rebuilds it from the git worktree at `af32c0f` into a tracked, re-derivable location:
`experiments/MP-E9/baselines/bench_pre_arbiter_tell_HEAD.json` (+ `.manifest.json`). The surviving
`_tmp/bench_pre_arbiter_tell_HEAD.json` was treated as **check-only**, never as source — `_tmp/` is
swept and `organs/tempstore.py:3` states "Nothing that must be consulted may live here."

Re-derivation ran clean (exit 0, 466.6 s, **no invention in any arm**) and reproduced the handover's
pre-flag signature exactly: **arbiter head 1034, arbiter tell 0, silence 1535, says 0, guarded absence
24.**

Cross-checking the re-derived snapshot against the survivor diverged on **12 of 3,672 rows.** That
divergence is not a defect in either artifact; it is §4's mechanism seen from the other side, and it is
why the plan's "byte-reproducible" claim about this bench cannot hold unqualified.

**Baseline against committed evidence:** clone 1 vs `docs/evidence/electric_learn_bench.json` —
**0 differences over 3,672 rows, verdict `reproduces`.** The current bench still reproduces the
committed post-flag run exactly. The instability is confined to the pre-flag re-derivation and the
`reasked`/`restarted` phases, i.e. to time-gated paths, not to the graded result set.

---

## 6. Seal basis, environment, and the two instrument bugs I fixed in myself

**autocrlf=true, no `.gitattributes`.** Tested empirically: `git hash-object` applies the clean filter,
so for a tracked CRLF worktree file it returns the index blob id. For the bench evidence — worktree
1,473,837 bytes CRLF, LF-normalised 1,421,862 bytes — `sha256(normalized)` = `318eb8c2d4fa51259453…`
equals `sha256(HEAD blob)`, and `git hash-object` = `38b74ededd269d7f458457742f747aff39f5096b`.
**LF-normalisation already reproduces the blob bytes exactly.** So `tools/registration_seal.py` seals
**both** the git blob hash and `sha256_of_git_blob`, and asserts their equivalence; if that equivalence
ever breaks, the repository's conversion rules changed and every recorded seal must be re-taken. Option
(b), adding `.gitattributes`, was **not** taken: it changes line-ending behaviour repo-wide, which is a
PI policy decision, not an artifact of this gate. Untracked files show `sha256_of_git_blob: None` —
`git hash-object` predicts the blob but does not write it until staged. Recorded as **PENDING**, not as
a mismatch; a seal tool that cries wolf is one people stop running.

**Environment.** The venv was unpinned — no `requirements.txt` pinning existed — while the interpreter
*is* a seal component. That asymmetry is registered in `registration.json` and is the reason the lock
file exists: `experiments/G0-prime/results/requirements.lock.txt`, **29 packages**, generated by
`tools/freeze_env.py`, package-list sha256
`5b8cbe45445ab5a512e7d2b935a3e75eff9414314539fdf98cd2d5753a2a174f`. **`pypdf` is this session's only
new dependency**, added because the tracked file
`experiments/MP-E9/plan_extract/extract_pdf.py:3` imports it — a tracked file requiring an untracked
package is exactly the drift R10 was written against. `torch`/`transformers` are **absent**, which is
consistent with MP-E8/MP-E12a assets not gating this gate.

**Two bugs in my own instruments, both found by reading the output instead of trusting it.**

* `seals()` crashed with `KeyError: 'environment'` because `sysconfig.get_paths()` has no
  `environment` key in this venv. Fixed to `sys.prefix`. It crashed at the **end of an 8-minute run**,
  and the crash was masked because the bench's legitimate non-zero exit for "invention found" shares
  the code space — the runner now distinguishes a crash from a finding. A related dead end: piping bench
  output through `findstr | more` reports the **last** command's status, so a failing python was
  reported clean.
* `tools/noise_floor_report.py` built its coordinate set from the **capped 8-row preview** instead of
  the full difference list, so it published "8 distinct rows touched" and "7 reason-only rows" when the
  truth is **11 and 10**. An artifact of a display limit, printed as a measurement, and I wrote both
  wrong numbers into this record before catching it. The instrument is fixed, a regression test
  (`test_report_coordinate_count_is_not_a_display_artefact`) recomputes from the clone files, and the
  wrong numbers stay on the record here per R5.

**Seal coverage gap, also self-caught.** The first manifest sealed 19 files and **omitted
`tools/noise_floor_report.py`** — the one file that decides the gate verdict and the one that carried
the bug. The noise-floor evidence files were unsealed too. All added. And `registration.json` listed
**itself**, which guarantees permanent self-inflicted `DRIFT` on `--check` because writing the seal
changes the sealed bytes; the self-entry is now dropped and the reason recorded, rather than left as a
warning line that trains readers to ignore the checker.

**A third bug, and the most uncomfortable one: a check that could not fail.** The seal's strongest claim
is that it matches what git *actually holds*, not what the worktree would hash to. That cross-check
parsed `git ls-files -s` with `l.split()` and keyed its dict on `r[0]` — **the file mode**. Every
`100644` file collapsed into one entry, so it printed "1 of 29 are in the git index" regardless of
reality, the membership test was never true, and the drift loop **compared nothing at all**. It reported
clean because it was structurally incapable of reporting anything else, and it survived every `--check`
run during this gate. It surfaced only when a real mismatch appeared after committing: sha1 agreed, and
the line still said "1 of 29". `test_index_cross_check_is_not_vacuous` now asserts the *counts* the
checker prints, not merely its verdict — the only assertion that catches an unfailable check. The same
run exposed a second reporting defect: a pending `sha256_of_git_blob: None` that resolves once the file
is committed was being called "hash collision or a mis-recorded seal", a false alarm on the transition
from prediction to confirmation. It now prints `RESOLVED` and does not count as drift.

---

## 7. Open blockers, and what the PI must decide

**Blocker 1 — B.1 step 3 (clone identity). RULED by the PI as D-G0P-02.** The criterion was falsified by
measurement; the PI chose R13 (a), a registered tolerance written field-level and narrow, with
`learn/1/reasked` and `learn/1/restarted` excluded from the noise-floor claim. The reasoning, the refusal
to tolerate `said`, and the R2 problem this creates are in §10 — that section, not this one, is the
decision record.

**Blocker 2 — CLOSED on the substance; the residual exit code has a named cause.** The instrument for
this is `tools/suite_manifest.py`: it collects once, runs the suite **once** with `--junit-xml`, and
diffs the two sets by node id, so the question "are 244 tests silently not running?" is answered by
file name rather than by a better-looking total. Run alone, nothing else on the machine, per §9:

| | run 1 — 05:36:39Z | run 2 — 05:59:51Z |
|---|---|---|
| collected | **1,164** (collect exit 0) | **1,167** (collect exit 0) |
| executed (`<testcase>` reached) | **1,164** | **1,167** |
| **collected-but-not-executed** | **0** | **0** |
| pytest returncode | **1** | **0** |
| junit counters | tests 1164, errors 0, failures **1**, skipped 3, 519.320 s | tests 1167, errors 0, failures **0**, skipped 3, 526.447 s |
| wall | 521.18 s | 528.27 s |
| tree | pre-commit (the gate commit did not exist yet) | `bf0bc40` + the re-stamp, worktree clean |

Both runs are in the artifact; run 2 is the one `README.md:853` and `registration.json` now cite. Run 1
stays because it is the measurement that closed the 244-test question and it is the run whose single
failure produced the two seal bugs in §6 — deleting it would delete the evidence for those findings.

**The count moved 1,164 → 1,167, and the reason is arithmetic, not instability.** Three testcases
appeared between the two runs while only one `def test_` was added, which is the signature of collection
reading something other than the tree. It was checked rather than assumed: a throwaway worktree pinned at
the gate commit collected **1,166** ids, and the current tree collects **1,167**, differing by exactly one
node id — `test_index_cross_check_is_not_vacuous`. No id disappeared; no module's count moved except
`tests/test_g0_prime_instruments.py` (16 → 17). So run 1 measured a tree that predated **two**
seal-regression tests which the gate commit itself then carried, and run 2 measures the tree after the
third was added. Collection is deterministic and tree-determined, which is the property MP-E9 needs from
a baseline: the suite does not collect differently depending on artifacts the suite writes.

**The 244-test gap never existed.** `917 passed, 3 skipped in 268.71s` was a **truncated invocation** — a
background wrapper that reported exit 1 while its captured file ended on a pass summary, and two
follow-up attempts that died before pytest returned. It is superseded, and it stays in this record
because R5 forbids quietly deleting a number that was published. Every collected test is reached: the
missing set is empty, so there is no module-level guard, no swallowed collection error, and no
mid-run crash hiding tests. 1,164 = the handover's 1,126 baseline + 38 new tests.

**The one failure, and what it actually was.**
`tests/test_g0_prime_instruments.py::test_registration_seal_verifies_against_the_registration` failed
reporting `15/19 files match`. It was **not** a defect in the organism or the bench: that test reads
`REG = experiments/MP-E9/registration.json` (`tests/test_g0_prime_instruments.py:26`), while every seal
this session stamped went into `experiments/G0-prime/registration.json`. MP-E9's registration still
carried the pre-fix 19-entry manifest **including its own path**, which is the self-referential
permanent `DRIFT` — writing a seal into a file changes the file, so a registration that lists itself can
never verify clean. The test was failing on a stale seal in a file I was not stamping, and it was
pointing at the neighbour gate's registration rather than this gate's. Both are repaired: the test now
checks **both** registrations.

**Following that thread found a second, worse bug.** G0-prime's manifest listed
`experiments/MP-E9/registration.json` and MP-E9's listed `experiments/G0-prime/registration.json` — a
**mutual-sealing cycle**. Each ledger sealed the other's bytes, so stamping A invalidated B's record of A
and re-stamping B invalidated A again: **no finite sequence of stamps makes both fresh**, and `--check`
was clean only by accident of ordering. The rule that dissolves it is the one already applied to the
self-reference — a registration seals instruments and artifacts, never another registration. Two ledgers
that pin each other prove the two agree with each other, not that either matches the world. `seal()` now
drops any `registration.json` target and records the exclusion in `registrations_excluded`, and
`test_no_registration_seals_another_registration` pins it so the cycle cannot be reintroduced silently.
Both registrations are stamped with both exclusions in force, which makes stamping order-independent and
the result idempotent. **Verified, not assumed:** the seal tests were re-run alone —
`37 passed, returncode 0, 7.69s`, later `38 passed, 13.71s` once the vacuous-check regression was added.

**The inference that used to sit here is now a measurement.** At this point the record claimed the full
suite's exit code on the repaired tree was `0` *by inference* from 1,164 reached, 0 missing and one
repaired failure, explicitly labelled as an inference rather than laundered into a measured run. It has
since been run: **1,167 collected, 1,167 reached, 0 collected-but-not-executed, returncode 0, failures 0,
errors 0, 3 skipped, 528.27 s wall**, alone on the machine per §9, in `suite_manifest.json`. Nothing in
the repaired tree changed a bench probe, threshold, class or exit-code rule, so this is the same
instrument the freeze registered — the delta is the three added regression tests and the seal tool. The
inference was correct, and being correct is not the same as being measured, which is why it is replaced
here rather than left as a vindicated prediction.

**The self-reference this exposes, stated rather than hidden.** The suite contains a test that seals
`experiments/G0-prime/decision.md` — the document that cites the suite result. It cannot both quote the
number and be sealed against the instant the number was taken. The procedure is therefore: run the
suite once, write the result here, re-stamp, then re-run **only** the seal test to prove freshness. The
suite is not run twice to chase a total.

The 3 skips are the pre-existing `legacy_archive` ones, named from the XML:
`test_multilang::test_agent_full_loop_in_lua`, `test_reasoning::test_reasoning_loop_solves_and_thinks_multistep`,
`test_reasoning::test_backtrack_switches_approach_and_can_recover`. The 5 warnings are the pre-existing
`PytestUnknownMarkWarning: Unknown pytest.mark.integration` set. Both match the handover.

**Ruled — `heard-not-told` scope.** See §10, decision D-G0P-03. C1 fires at 16.

**Still open — `requirements.txt`.** `requirements.txt` names six packages with no version pins, plus
`pypdf` added this session because a tracked file imports it. The exact measured environment — 29
packages, versions pinned — is in `results/requirements.lock.txt`. `fastapi`, `starlette`, `uvicorn`,
`pydantic` and `anyio` are installed and imported by nothing in the repository. Whether the requirements
file grows version pins, and what to do with those five, is still the PI's call: the requirements file
and the environment the numbers were measured in are not the same set, and a seal cannot be built on
that difference.

**Risk registered (not a to-do an agent discovers at the gate).** Per the plan, MP-E8 arms B and C
require a **from-scratch 2–10M LSTM / tiny-transformer harness plus an abstention mechanism**. No such
code exists in this repo; `torch`/`transformers` are absent; there is no donor model. Arms B and C are
**not** a download. MP-E8 cannot open arms B/C until that harness is built and registered. Likewise
tier 120 and tier 300 curricula **do not exist as code** — the tier protocol is registered with measured
cost projections (tier 120 ≈ 24 min, tier 300 ≈ 60 min for all three arms), but `SESSIONS` and `PAIRS`
are literal lists in the bench, so scaling is real work, not a flag.

---

## 8. Where the artifacts live, and why (the `.gitignore` question)

**`.gitignore` was not edited.** The repo convention is: audit records tracked; regenerable
checkpoints and scratch not. The mechanism is `!` re-include lines **inside** an ignored area, never
un-ignoring the area. Un-ignoring `_tmp/` was rejected on the repo's own terms: `organs/tempstore.py:3`
says "Nothing that must be consulted may live here" and `organs/sandbox.py:119` relies on `_tmp/` being
swept — making the scratch directory normative would break that contract.

So `experiments/MP-E9/` was created as the **tracked normative home** and artifacts were *promoted*
into it, rather than the ignored area being loosened to accommodate them. `git check-ignore` confirms
none of the new paths are blocked, so they add without any `.gitignore` change. Precedent checked
rather than assumed: `docs/evidence/` already holds **47 tracked JSONs** including a 1.42 MB bench
artifact, so a 1.4 MB sealed snapshot in a tracked location is existing practice, not a new policy.

| artifact | path |
|---|---|
| plan text + provenance | `experiments/MP-E9/plan_extract/` (`DROSO_Master_Plan_v1_1.txt`, `PROVENANCE.json`, `extract_pdf.py`) |
| pre-flag baseline (re-derived) | `experiments/MP-E9/baselines/bench_pre_arbiter_tell_HEAD.json` + `.manifest.json` |
| word grader + audit | `tools/word_provenance.py`, `experiments/G0-prime/results/word_provenance_audit.json` |
| regression pins | `tests/test_word_provenance.py`, `tests/test_g0_prime_instruments.py` |
| noise floor | `tools/bench_noise_floor.py`, `tools/noise_floor_report.py`, `experiments/G0-prime/results/noise_floor/` (3 clones + `noise_floor.json` + `per_arm_breakdown.json`) |
| registration + protocol + taxonomy | `experiments/{MP-E9,G0-prime}/registration.json`, `tier_protocol.json`, `failure_taxonomy.json` |
| environment | `requirements.txt`, `experiments/G0-prime/results/requirements.lock.txt` |
| sealing | `tools/registration_seal.py`, `tools/freeze_env.py`, `tools/derive_pre_flag_snapshot.py`, `tools/promote_plan_extract.py` |

The plan source is pinned: `C:/Shared/DROSO_Master_Plan_v1_1.pdf`, sha256
`0e6aa58bef7a114951bf159539529847c55b226d83fc0bed73070ab70a81c0ff`, 32 pages / 11,088 words, with the
extraction command recorded in `PROVENANCE.json` so the text is re-derivable, not transcribed.

One journal note: `docs/HANDOVER.md:4` cites `docs/CHANGELOG.md` as long-form history. **That file does
not exist** — `dir` and `git check-ignore` both return nothing. Recorded, not fixed; the handover is
itself gitignored at `.gitignore:42` and deliberately local-only, which R10 flags as a conflict for any
number a registered result depends on. The pre-flag signature this gate validated against lives in that
local-only file, so the re-derivation in §5 exists precisely so the number does not have to be trusted
on prose.

---

## 9. Reproduction

```bat
.venv\Scripts\python.exe tools\word_provenance.py --audit            :: 16/23/24 pinned sets
.venv\Scripts\python.exe tools\derive_pre_flag_snapshot.py           :: re-derive baseline (af32c0f)
.venv\Scripts\python.exe tools\bench_noise_floor.py --clones 3       :: ~24 min, run ALONE
.venv\Scripts\python.exe tools\noise_floor_report.py                 :: verdict + concentration
.venv\Scripts\python.exe tools\freeze_env.py                         :: requirements.lock.txt
.venv\Scripts\python.exe tools\registration_seal.py experiments/G0-prime/registration.json
.venv\Scripts\python.exe tools\registration_seal.py experiments/G0-prime/registration.json --check
.venv\Scripts\python.exe -m pytest tests/test_word_provenance.py tests/test_g0_prime_instruments.py -q
```

Clones and the suite must **not** run concurrently: CPU contention perturbs the time-dependent organism
and contaminates the noise measurement. That is not caution — it is §4's mechanism, and running them
together would manufacture the very differences this record is trying to bound.

---

## 10. The PI's rulings, recorded as decisions

Everything in §1–§9 above was done by the agent and is written as such. This section is different in
kind: **three decisions were made by the PI on 2026-11-03 and handed down.** They are recorded here with
their reasoning because a decision record that keeps only the outcome loses the part that constrains the
next case — and because the difference between "the agent chose this" and "the PI ruled this" is exactly
what R2 turns on. The agent's role was to implement them, to test them, and to say plainly where a
ruling left the record weaker than one would like.

### D-G0P-02 — the clone criterion: R13 option (a), field-level and narrow

B.1 step 3 read *three clones … identical outcomes row for row*. §4 falsified that: 11 of 3,672 rows
moved, 20 differences confined to `reason`, and exactly one row differing in a graded field.

**Ruling.** Identity is required on `cls`, `said`, `src`, `item`, `shape`, `mech`, `taught`, `own`,
`answered`. Only `reason` is tolerated as noise.

**Why `said` is not tolerated, and why that mattered more than the reproducibility it costs.** The one
graded difference the clones produced *is* the says-gap row — `learn/d1/reasked[120]`,
`'droso says when does the bell toll'` against `'when the bell toll'`, the narration frame appearing and
vanishing. `said` is the field MP-E9 grades: C1, C2 and H2 all read it. A tolerance that forgave `said`
would have bought a clean clone verdict by weakening the instrument on the precise quantity the next gate
spends. The tolerance therefore buys reproducibility on the organ's self-commentary and pays nothing that
is scored.

**Consequence, registered rather than smoothed.** B.1 step 3 is met **on 2 of 3 clones** and on every
phase **except `reasked`/`restarted` of `learn/d1`**. That cell is **excluded from the noise-floor claim
rather than averaged into it** — the rows stay in both artifacts with their values printed
(`r13a.excluded_rows`), and they are counted as identity differences, not as noise. Exclusion is not
forgiveness; the difference is still on the record, it just no longer contaminates the bound.

**Fail-closed on the field the ruling did not name.** `ask` is a graded field that the ruling's
enumeration omitted. Silence from a ruling is not permission: an unenumerated field is held to the
identity standard (`UNENUMERATED_FIELDS` → `REQUIRED_FIELDS`), not quietly folded into the tolerance. It
is immaterial today — zero `ask` differences were observed — but the default is the one that cannot hide
a difference.

**Long-term fix: scheduled, not improvised.** R13 option (b), an injectable clock, is the correct fix and
is recorded as such. §4 supplies the mechanism: the organ reads `time.time()` in its answer path, so a
coverage percentage in a `reason` string can move with machine load. Replacing that clock is a change to
`organs/`, and **`organs/` is not touched without its own registered design step** — the same reason
MP-E9's H1 must not be allowed to pass or fail on load.

**The R2 problem, stated plainly.** This is a criterion changed after the result was seen. Three things
separate it from the thing R2 forbids: (a) was one of three resolutions **written down before the run**;
the ruling *selected* from a pre-registered menu rather than inventing an escape. The tolerance is
**narrower than the literal rule in the graded fields** — it forgives one field and no classes. And the
offending cell is **named and excluded**, not absorbed. What it is not, is innocent of timing: the PI saw
the measurement before ruling, and the record says so.

### D-G0P-03 — heard-not-told: a third class, non-aborting

**Ruling.** R9 does **not** treat these as aborts. `UNTRACEABLE_HEARD` is a third class — reported and
counted, non-aborting, distinct from `UNTRACEABLE_ASSERTED`.

**Reasoning.** The word reached the organism through **the harness's own probe**. `which` and `why`
appear in the house's vocabulary only because the measurement instrument asked a question containing
them. That is a leakage channel in the instrument, not confabulation by the organism. Aborting a run
because the measuring device fed the subject a word punishes the organism for the instrument's design.

**Consequence.** **C1 fires at 16, not 22.** The 6 heard rows **stay visible in every audit** rather than
being silently admitted into the trace set: the ruling changes their *severity*, not their *visibility*.
Had the ruling gone the other way, MP-E9's H1 threshold would have had to be re-scoped before the
experiment opened — which is why the question was asked before opening rather than during.

The grader already implemented this split before the ruling arrived, including the exit-code asymmetry
(fatal on `ASSERTED` only). The ruling therefore *confirms* an instrument behaviour rather than requiring
a code change, and the honest description of this event is that a pending decision was retired, not that
a defect was fixed.

### D-G0P-04 — the suite measurement

The gate's last inferred number was converted to a measurement: **1,167 collected, 1,167 reached, 0
collected-but-not-executed, returncode 0**, run alone. This was not a re-run in search of a better total
— the previous run had already proved 0 missing. The tree had changed and the claim was an inference. See
§7 for the node-id attribution of the 1,164 → 1,167 move.

### What was implemented, and how it is pinned

| Ruling | Implementation | Pinned by |
|---|---|---|
| D-G0P-02 | `tools/bench_noise_floor.py`: `IDENTITY_FIELDS`, `TOLERATED_FIELDS`, `R13A_EXCLUDED_CELLS`, `diff_records`, `r13a_assess`; `tools/noise_floor_report.py`: `r13a` block, one shared field definition | `test_r13a_identity_fields_are_exactly_the_ruled_nine`, `test_r13a_tolerates_a_reason_difference_and_still_reports_it`, `test_r13a_does_not_tolerate_a_said_difference`, `test_said_inside_the_excluded_cell_is_counted_as_a_difference_not_as_noise`, `test_unenumerated_ask_is_held_to_identity_fail_closed`, `test_sealed_clones_meet_r13a_only_with_the_registered_exclusion`, `test_the_excluded_cell_is_the_says_gap_row_itself`, `test_comparator_and_report_agree_because_they_share_one_field_definition` |
| D-G0P-03 | `tools/word_provenance.py` (already split the classes; exit code fatal on `ASSERTED` only) | `test_c1_counts_the_asserted_class_and_fires_at_sixteen`, `test_heard_rows_are_reported_not_erased` |
| Both | `experiments/MP-E9/registration.json`: `pi_decisions_resolved`, `numeric_thresholds` transcribed from the prose thresholds, `registration_amendments` with `results_existed: false` | `test_the_ruling_and_the_code_agree_on_the_field_lists`, `test_no_mp_e9_result_exists_yet_and_the_amendments_say_so`, `test_verdicts_move_when_the_registration_moves` |

The last of those tests is the one that matters most for the next gate: it *edits the registration* and
requires the harness's verdict to move with it. A harness that hardcodes the thresholds would agree with
the registration today by luck and drift silently later.
