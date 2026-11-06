# PI decision sheet — consolidated, 2026-11-06

**Supersedes by reference:** `docs/mp_e10_pi_decision_brief_consolidated.md`. That brief is **sealed and left
unedited**; it remains the record of the reasoning and the costs as of 2026-11-05. This sheet changes nothing in
it. It exists because the tree has moved since it was written: STEP 5b ran, two new decisions were opened, and a
covering suite run has now been made at HEAD and came back **red**.

Every status string below is **read from the owning file at the line given**, not restated from memory. A line
number is perishable; where a citation is to a ledger, the value was re-resolved against the file at write time.

---

## 0. The thing that changed since the brief: the covering run is red

A full suite run was made at HEAD `7d14580a116ca65ebe1b2a57fa63aaf3453af323`, clean tree, nothing else on the
machine, to `experiments/MP-E10/results/suite_manifest_head_7d14580.json`:

**1,484 collected · 1,484 executed · 0 missing · 1 failure · 0 errors · 6 skipped · rc 1 · 1,017.25 s.**

The failure is `tests/test_g0_prime_instruments.py::test_no_registration_seals_another_registration`:

> `experiments\G0-prime\registration.json seals another registration: ['experiments/MP-E12/results/real_run_preregistration.json']`

**The invariant is not actually violated.** Measured directly: G0-prime's manifest holds 268 files, of which
**zero** end in `/registration.json`; `harness_hashes.registrations_excluded` records all four other ledgers.
The test's predicate is `f.endswith("registration.json")`, and `real_run_preregistration.json` ends with that
string. That is the **substring bug the seal tool itself already fixed** — `tools/registration_seal.py:776` reads
*"MATCH THE FILENAME, NOT THE SUFFIX. `endswith("registration.json")` also matches
`real_run_preregistration.json`, which is an EVIDENCE artifact — the accounting registered before the first donor
read, and the file the ordering proof cites."* The tool compares against the last path segment now. **The test was
never brought into line with the fix it prompted**, and no suite run has covered the tree since B.6 sealed that
artifact — which is exactly the caveat this run was ordered to clear.

**Consequences, stated rather than managed:** the manifest is **not** added to `DEFAULT_MANIFEST`, **not** sealed,
and **not** cited as covering. Nothing was re-run to chase a green total. The red run sits on disk untracked, as
measured. **No item on this sheet is gated on the seal being green, but the covering claim cannot be made at HEAD
until item D below is ruled.**

---

## 1. The gate table, as the ledgers state it

| gate | state as recorded | where it is recorded |
|---|---|---|
| **G2** | **NOT CLOSED.** `D-MPE10-05` was ruled "yes — MP-E10 may run again, under the re-registration…", and the ruling that opened that run also states G2 is not closed. T and N was declined for cost, so G2's evidence stays incomplete. | `experiments/MP-E10/registration.json:3234` (the ruling, which names `D-MPE10-05_G2_is_not_closed`) and `experiments/MP-E10/registration.json:3237` (its `status` field) |
| **G3** | **DOES NOT CLOSE.** H2 measured-and-failing; H3 measured-and-unresolvable at the floor; H1 and H4 uninstrumented; R6 unmeasured. | `experiments/MP-E10/decision_step5b_2026_11_06.md` |
| **G4 / MP-E11** | **NOT STARTED** — no registration, no run, no `experiments/MP-E11` directory. The plan's row and MP-E10's own row describe different histories ("since it was opened" vs "no registration"), recorded as a wording conflict, not settled. No ledger owns MP-E11. | `experiments/MP-E9/plan_extract/DROSO_Master_Plan_v1_2.md:163`; `experiments/MP-E10/registration.json:90` |
| **G5 / MP-E12** | "**G5 (opens now as a PARALLEL track; it does not open G4, G5 or G6 and it does not close G2)**" — quoted from the field, including its own self-referential oddity. | `experiments/MP-E12/registration.json` `gate` |
| **G6** | Not started; owned by no ledger. Recorded beside G4 in `gate_ledger_entries_G4_G6_2026_11_06`… precisely `…_2026_11_05`, with go-criteria quoted from the plan only. | `experiments/MP-E10/registration.json:90` |

**The single item that gates G3 is D-MPE10-14** — which baseline H2 is scored against. H2 is the only hypothesis
with a ruled scalar, a same-tier baseline, a completed run, and a number in the wrong direction. Every other G3
cell is an instrumentation gap, which cannot be closed by a ruling alone but also cannot be closed *without* one.

---

## 2. Rulings the PI owes

For each: measured state · options · machine-time cost beside the measured unit costs · what stays blocked.

### D-MPE10-14 — which baseline does H2 get scored against?  `OPEN, UNRULED 2026-11-06`
*read from `experiments/MP-E10/registration.json:386`*

- **Measured:** replay **2.9764**; unreplayed control **2.9739** on identical bytes; sealed MP-E8 arm-A baseline
  **3.0107** on harness `5cf038c2…`, a byte-set that exists in no commit. Same-bytes delta **+0.0025**;
  cross-bytes delta **−0.0343**; control-vs-baseline **−0.0368**. **Fluency floor 0.0051**, derived at zero bench
  cost from four sealed unreplayed tier-120 runs (`experiments/MP-E10/results/h2_fluency_floor_from_sealed_runs.json`).
- **Option A — keep the clause literal (v1.2:204 names the MP-E8 arm-A artifact).** Cost: **no machine time.**
  H2 **FAILS**, and the failure carries a named byte-set confound. Blocked either way: nothing further.
- **Option B — score against a same-bytes unreplayed control.** Cost: **zero new bench time** for the baseline —
  STEP 5b's control arm already *is* one, sealed. A dedicated re-baseline instead is **one learn-only tier-120 run
  at the measured 488.30 / 488.90 s** (pair 5: 474.12 / 413.42 s; pre-A10: 480.91 / 462.37 s; PI estimate ~475 s;
  tier-40 proof 160.42 s; covering suite 1,017.25 s). Expected verdict becomes **NOT ESTABLISHED**, not PASS,
  because +0.0025 is inside the 0.0051 floor.
- **If left open:** H2 is a FAIL on the literal clause and undecidable on the same-bytes reading. G3 cannot close
  on it either way. **Nothing is lost by leaving it** — both numbers are in the record — but no future run resolves
  it without this ruling.
- **Attached, and deliberately not adopted:** the fluency floor is offered **so it can be registered before use
  rather than after**. Adopting it after seeing +0.0025 would be setting a tolerance to fit a reading.

### D-MPE10-15 — may the two published instruments be edited to reach a bench house?  `OPEN, UNRULED 2026-11-06`
*read from `experiments/MP-E10/registration.json:412`*

- **Measured:** all nine STEP 5b cells classify every failing row `recall_untraced`, because the bench records
  `reason: ""` per row — the five-stage denominator **cannot discriminate on bench rows at all**; mass in `other`
  is 0 rows. R6's four probes (`P-numeral-final`, `R-count-moon`, `R-disj-reversed`, `R-order-ofthe`) are scored by
  `tools/mp_e9_battery.py` over a `run_generation.py` journal the bench does not produce. `heldout_eval.py` has no
  `--state-root`; `run_generation.py` **does** (its line 1907), so R6's route exists and was simply not taken.
- **A — add `--state-root` to `heldout_eval`.** Cost: a tool edit, no bench time for the edit; scoring H1 then
  costs a held-out run per configuration. Touches an instrument sealed evidence quotes — the same ground on which
  D-MPE10-09's route 2 was ruled out for breaking `curriculum_sha256`.
- **B — drive the existing generation pipeline at the bench house.** Cost: **no instrument edit at all**; machine
  time for the generation pass, a separate pipeline from the bench.
- **C — leave both.** Cost: none. H1 stays permanently unscoreable on bench configurations; R6 stays unmeasured at
  tier 120 on registered runs.
- **If left open:** every future tier-120 scored run reproduces the same nine-cells-of-`recall_untraced` table.

### D — should the stale test predicate be corrected? *(new this turn, raised by the red run)*

- **Measured:** the test asserts with a substring where the seal tool asserts with a path segment; the invariant
  holds (0 true cross-registration entries, exclusion recorded).
- **Options:** correct the predicate to the last path segment (a test edit — the same class of act as D-MPE10-15's
  option A, touching an instrument other evidence quotes); or leave the red standing and treat the covering claim
  as unavailable indefinitely.
- **Cost:** the correction is a test edit plus **one covering run at 1,017.25 s** to re-establish the claim.
- **If left open:** no suite run covers HEAD; the badge and STATE.md cannot move by reference; and a rule that
  excludes by substring will eventually exclude the wrong thing — the tool's own comment says so.
- **Not done by the agent:** the predicate was not edited and the suite was not re-run. That is this decision's
  content, not an oversight.

### The already-ruled items the brief carried, restated with their live status strings

These are **ruled**, listed only so the sheet is complete and so their *residual* obligations are visible:

| item | status as read | what it still requires |
|---|---|---|
| `D-MPE10-05_G2_is_not_closed` | `RULED 2026-11-05 by B.R item 3: yes — MP-E10 may run again, under the re-registration o…` — `experiments/MP-E10/registration.json:3234` (the ruling, which names `D-MPE10-05_G2_is_not_closed`) and `experiments/MP-E10/registration.json:3237` (its `status` field)` | G2 stays **not closed**; T and N declined for cost |
| `D-MPE10-09_r6_guarded_battery_at_tier_300` | `RULED 2026-11-05 by B.R item 4: route 2 is ruled out because it breaks curriculum_sha25…` — `experiments/MP-E10/registration.json:3258` | R6 still unmeasured at tier 120 → folded into D-MPE10-15 |
| `D-MPE10-10_which_phase_is_h3s_registered_basis` | `RULED 2026-11-05 by B.R item 5: the phase basis is fixed in the new registration befo…` — `experiments/MP-E10/registration.json:3281` | honoured — STEP 5b used `reasked` |
| `D-MPE10-11_tier300_breaches_the_invention_floor_in_every_run` | `RULED 2026-11-05 by B.R item 2: tier-300 figures are admissible as capacity and instrum…` — `experiments/MP-E10/registration.json:3413` | tier-300 quoted as capacity only |
| `D-MPE10-12_h3_saturation_guard_voids_its_own_tier` | `RULED 2026-11-05 by B.R item 1. Option 1 as specified in v1.2:200: a new dated non-satur…` — `experiments/MP-E10/registration.json:3505` | **moot at tier 120** — the guard did not fire there |
| `D-MPE8-10` | `RULED 2026-11-05 by B.R item 6: per R16, no tolerance widening; any newly gated cell ent…` — `experiments/MP-E8/registration.json:3278` | no widening; newly gated cells enter as measured |
| `D-MPE8-11` | `RULED IN PART 2026-11-05 by B.R item 7, which shares item 6's line: the R16 mechanism is…` — `experiments/MP-E8/registration.json:3299` | partly ruled; remainder unresolved |
| `licensed_absence_intermittence` | `OPEN — NAMED, NOT CLOSED. Does not gate H3 (the flip is in reason, which R13 tolerate…` — `experiments/MP-E10/registration.json:3142` | **the scope question is still open**: whether the licensed absence extends beyond `reason` |
| `requirements_txt` | **no status field at all** — a bare string at `experiments/G0-prime/registration.json:92`: "EXISTS and is UNPINNED: it named six packages…" | pinning is RULED (`experiments/MP-E9/registration.json:2856`, B.R item 9: "yes -- it is hygiene, cheap, and protects every future seal"), and `experiments/MP-E9/registration.json:2855` states that the ruling "authorises the pinning; it does not perform it" -- the file is still unpinned, as `experiments/MP-E9/registration.json:2854` records; it is also the interpreter-of-record question, since "Interpreter is a component of every journal seal" (`experiments/G0-prime/registration.json:93`) |
| `5_promote_the_bound_to_BASE_D-MPE9-05` | **ABSENT — measured, not inferred.** The block at `experiments/MP-E9/registration.json:2858` carries `measured_state`, `pi_ruling_2026_11_05_BR`, `precondition_before_any_promotion` and **no `status` key** | promotion stays flag-gated until the inertness proof exists (`experiments/MP-E9/registration.json:2868`). The absent field is why a stale-status guard cannot correct this item: it never declared a status to be stale |
| `D-MPE12-09` | `question_id` at `experiments/MP-E12/registration.json:98`; **OPEN, UNRULED** — "D-MPE12-09 is named and argued both ways, not answered" (`experiments/MP-E12/registration.json:409`); "This block does not rule on D-MPE12-09 and does not authorise a benchmark run" (`experiments/MP-E12/registration.json:457`) | it is **the single thing G5's next step waits on** (`experiments/MP-E10/registration.json:3927`): permission to spend the donor's one R11 execution on a timing run, or a dated exception granting a second |
| `D-MPE12-10` | `OPEN, UNRULED 2026-11-05 (D-MPE12-10: where the process audit runs)` — `experiments/MP-E12/registration.json:5154` | where the process audit runs |
| `D-MPE12-11` | `OPEN, UNRULED 2026-11-05 (D-MPE12-11: whether the organ's own generate counts)` — `experiments/MP-E12/registration.json:5186` | whether the organ's own generate counts |
| `D-MPE12-12` | `OPEN, UNRULED 2026-11-05 (D-MPE12-12: evidence, configuration, or no list at all)` — `experiments/MP-E12/registration.json:5211` | evidence, configuration, or no list at all |

---

## 3. Authorisations, not rulings

Machine time is the PI's to grant; these are requests, priced at measured costs.

- **Two floor pairs** (`experiments/MP-E10/registration.json:6868`). Pair 3 (no A10 sampler) and pair 5 (with it) are **already run and sealed**;
  pair 5's 6 rows / 0.1603 % governs STEP 5b by executed path. What is *not* bought is a **wider** floor: 0.1603 pp
  is why H3 reads unresolvable, and a fluency floor of 0.0051 is why the same-bytes H2 delta is unresolvable.
  Cost of one further pair: **two tier-120 runs ≈ 977 s** at the measured 488.30 / 488.90 s, plus the registered
  16-minute tier-120 allowance already noted at `experiments/MP-E10/registration.json:6694`. **If left ungranted:** H3 stays bounded by a floor
  narrower than any effect the organism plausibly has.
- **T and N** (`experiments/MP-E8/registration.json:5034`). Status as read: `NOT RUN, and named missing rather than glossed` — `experiments/MP-E8/registration.json:5037`.
  Cost if bought: **"Roughly 2.7 hours of exclusive wall-clock for three noise-floor clones at tier 300"**
  (`experiments/MP-E8/registration.json:5035`); tier 40 exists only as `arms.T`/`arms.N` registered and measured there (`experiments/MP-E8/registration.json:5038`).
  **Declined by the PI for cost and not started.** G2's evidence stays incomplete; nothing on this sheet rescues
  it, and the record says so in the same words.
- **One covering suite run at HEAD, after item D is ruled** — 1,017.25 s, the figure this turn measured.

---

## 4. What this sheet does not do

No ruling is implied or preferred anywhere; the agent chose no option in any item. H2 is not re-scored under
either baseline. The fluency floor is **offered, not adopted**. No instrument, test or answer path was edited. No
donor byte was read. No cap was raised, nothing downloaded. No MP-E11, no MP-E12b/c, no T and N. The 2026-11-05
brief is untouched. The red manifest is unsealed and uncited as covering, and the void first attempt remains void.

**Landing status of this file:** written but **not committed and not sealed**, because the covering claim that
would justify landing it is the thing that just failed. The working tree currently holds two untracked artifacts —
this sheet and `suite_manifest_head_7d14580.json` — so the stamped `git_dirty_sealed: []` in the five ledgers no
longer describes the tree. That is reported, not fixed by stamping over it.
