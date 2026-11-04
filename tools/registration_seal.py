"""Stamp and verify the harness hashes a registration promises (R2, and plan B.0 step 1).

A registration that names its harness by a hash somebody typed from memory is a claim. This computes
them and re-checks them, so "committed and sealed" (B.1 step 6) is a falsifiable statement rather than
an aspiration.

WHAT THE SEAL HASHES, and the proof behind it (G0-prime fix #2)
---------------------------------------------------------------
This machine runs `core.autocrlf=true` with no `.gitattributes` -- docs/HANDOVER.md lists both as
standing conditions. So a file's worktree bytes and the git blob it came from are different byte
strings, and a seal over raw worktree bytes does NOT verify after commit+checkout. docs/HANDOVER.md's
published hash for the pre-flag snapshot is exactly that: the CRLF worktree hash.

Measured here, on the tracked 1.4 MB evidence file:

    worktree bytes            1,473,837  (CRLF)
    CRLF folded to LF         1,421,862  == the HEAD blob, byte for byte
    git hash-object           38b74ede... == the index blob  (autocrlf clean IS applied)
    git hash-object --no-filters 2f850ad4... (the CRLF bytes -- NOT checkout-stable)
    sha256(HEAD blob)         318eb8c2d4fa5125... == sha256(LF-normalised worktree)

Two hashes are therefore recorded, and they are the same content seen two ways:

  * `git_blob_sha1` -- `git hash-object`, which applies the same conversion `git add` would. Stable
    across checkouts on any platform, and directly comparable to `git ls-files -s` once committed.
  * `sha256_lf` -- sha256 over CRLF-folded-to-LF bytes. Proven above to equal sha256 of the blob, so
    it is equally checkout-stable, and it is the algorithm this program already uses elsewhere.

`--check` verifies BOTH, and additionally asserts the equivalence (sha256 of the git blob == the
recorded sha256_lf) so the seal cannot drift away from what git actually stores.

Option (b), adding a `.gitattributes` to pin line endings, was NOT taken: it changes line-ending
behaviour for the whole repository, which is a policy decision for the PI, not an artifact of this
gate. The raw worktree hash is still recorded where it differs, so a reader holding an old hash can
tell whether they have the same artifact.

Run:  .venv/Scripts/python.exe tools/registration_seal.py experiments/MP-E9/registration.json
      .venv/Scripts/python.exe tools/registration_seal.py <registration.json> --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parents[1]

DEFAULT_MANIFEST = [
    "tools/electric_learn_bench.py",
    "tools/word_provenance.py",
    "tools/bench_noise_floor.py",
    "tools/derive_pre_flag_snapshot.py",
    "tools/promote_plan_extract.py",
    "tools/registration_seal.py",
    "tools/freeze_env.py",
    # The instrument that DECIDES the noise-floor verdict. It was missing from the first seal, and it
    # is the file that carried the coordinate-count bug -- the one artifact most in need of pinning
    # was the one not pinned.
    "tools/noise_floor_report.py",
    # Produces the sealed suite baseline (B.1 step 4). Its OUTPUT, results/suite_manifest.json, is added
    # to this list only once the file exists: check() reads a never-written artifact as MISSING -> DRIFT,
    # which would fail the seal test for the wrong reason. The ordering is recorded, not discovered.
    "tools/suite_manifest.py",
    # The sealed suite baseline itself. Added only now that the file exists -- see the note above.
    "experiments/G0-prime/results/suite_manifest.json",
    # MP-E9's harness, its tests, and the wiring-validation artifact. Listed here because all three are
    # committed in the same commit as this line: a manifest entry for an uncommitted file makes the
    # index cross-check fail on `in_index != total`, which is the correct outcome but the wrong reason.
    "tools/mp_e9_gate.py",
    "tests/test_mp_e9_gate.py",
    "experiments/MP-E9/results/gate_validation.json",
    # PRE-1: the organs/ design step, the test that enforces it, and the battery instrument that
    # gives H4 a measured state. All three are committed in the same commit as this line. The
    # document is sealed because it is a GATE, not a note: unsealed, it can be edited or deleted
    # with no signal, and the constraint it states stops being falsifiable.
    "experiments/MP-E9/organs_precondition.md",
    "tests/test_mp_e9_precondition.py",
    "tools/mp_e9_battery.py",
    # H4's measured battery state, and the gate verdict that consumed it. Added only now that both
    # files exist -- check() reads a never-written artifact as MISSING -> DRIFT. The battery journal
    # itself is NOT here: generations 9001-9006 are synthetic scratch and were deleted after
    # extraction, so the artifact carries the per-chunk journal hashes instead.
    "experiments/MP-E9/results/battery_pre_flag.json",
    "experiments/MP-E9/results/gate_validation_with_battery.json",
    # The 42 rows behind battery_pre_flag.json. The scratch generation journals were deleted --
    # state/selection/ is the tracked lineage and generations 9001-9006 never happened -- so this
    # is what makes H4's battery numbers recomputable from rows instead of trusted.
    "experiments/MP-E9/results/battery_pre_flag_rows.jsonl",
    # The MP-E9 A/B. Three 1.4 MB artifacts, and they are committed for the same reason the noise
    # floor clones are: the decision in decision.md is "H1/H2 hold, H3 fails", every number behind
    # that is computed from these files, and a gate claim whose inputs only exist on one machine is
    # not a sealed result. Each carries its own provenance.electric_flags, so an artifact states
    # which arm it is instead of being identified by the filename somebody gave it.
    "experiments/MP-E9/results/ab_flag_off.json",
    "experiments/MP-E9/results/treatment_arbiter_head_bound.json",
    "experiments/MP-E9/results/treatment_qa_morph_normalize.json",
    # The instrument that proves the OTHER half of the A/B -- that the flag-OFF arm moved nothing --
    # and the reports it wrote. A treatment effect is only controlled if the no-treatment arm is
    # measured on the same keyed comparison, so this file is as load-bearing as the gate.
    "tools/ab_reproduction.py",
    "experiments/MP-E9/results/ab_flag_off_reproduction.json",
    "experiments/MP-E9/results/treatment_arbiter_head_bound_effect.json",
    "experiments/MP-E9/results/treatment_qa_morph_normalize_effect.json",
    # The gate verdict computed over each arm, committed so a reader gets the same numbers without
    # re-running the gate against a tree that has since moved.
    "experiments/MP-E9/results/gate_ab_flag_off.json",
    "experiments/MP-E9/results/gate_treatment_arbiter_head_bound.json",
    "experiments/MP-E9/results/gate_treatment_qa_morph_normalize.json",
    # F1: the plan's one registered fallback for the morphology defect, and the mechanism tests for
    # it. Committed because the second-failure claim in decision.md rests on this artifact: "0 of
    # 3,672 rows moved" is the evidence that the defect is not a store-key problem, and a negative
    # nobody can re-check is an assertion.
    "experiments/MP-E9/results/treatment_per_entry_aliases.json",
    "experiments/MP-E9/results/treatment_per_entry_aliases_effect.json",
    "experiments/MP-E9/results/gate_treatment_per_entry_aliases.json",
    "tests/test_electric_qa_morph_aliases.py",
    # MP-E8 opens on the Table 6 G1 fallback. Its registration is the pre-run contract; the
    # curriculum manifest is what makes "identical curricula" checkable across arms rather than
    # intended; the reverification is the evidence that arm A's configuration on the current tree
    # is still the one N was measured on.
    "experiments/MP-E8/registration.json",
    "experiments/MP-E8/curriculum_tier40.json",
    "experiments/MP-E8/results/noise_floor_reverification.json",
    "tools/mp_e8_curriculum.py",
    "tests/test_word_provenance.py",
    "tests/test_g0_prime_instruments.py",
    "experiments/G0-prime/tier_protocol.json",
    "experiments/G0-prime/failure_taxonomy.json",
    "experiments/G0-prime/registration.json",
    "experiments/G0-prime/decision.md",
    "experiments/G0-prime/results/requirements.lock.txt",
    "experiments/MP-E9/baselines/bench_pre_arbiter_tell_HEAD.json",
    "experiments/MP-E9/baselines/bench_pre_arbiter_tell_HEAD.manifest.json",
    "experiments/MP-E9/registration.json",
    # MP-E9's result. Sealed for the same reason G0-prime's is: it states a negative -- H3 fails, a
    # registered premise is falsified, two arms moved zero rows -- and a published negative that can
    # be edited after the fact without a signal is worth less than no negative at all.
    "experiments/MP-E9/decision.md",
    "experiments/MP-E9/plan_extract/PROVENANCE.json",
    "experiments/MP-E9/plan_extract/extract_pdf.py",
    # The noise-floor evidence. The clones are 1.4 MB each and regenerable, but the gate claim in
    # decision.md ("11 rows of 3,672 move; 1 graded") is computed from them, and an unverifiable
    # number in a gate record is worse than a large file.
    "experiments/G0-prime/results/noise_floor/noise_floor.json",
    "experiments/G0-prime/results/noise_floor/per_arm_breakdown.json",
    "experiments/G0-prime/results/noise_floor/clone_1.json",
    "experiments/G0-prime/results/noise_floor/clone_2.json",
    "experiments/G0-prime/results/noise_floor/clone_3.json",
    "experiments/G0-prime/results/word_provenance_audit.json",
    "docs/evidence/electric_learn_bench.json",
    "requirements.txt",
    "organs/neural_language.py",
    # D-MPE8-03's authored tiers and the instruments that made them. Sealed because the ruling's whole
    # point is that tiers 120/300 are REGISTERED DATA with a reproducible construction: an unsealed
    # tier file is a spreadsheet, and --check-tier only proves something if the file it re-derives
    # against is itself pinned.
    "experiments/MP-E8/curriculum_tier120.json",
    "experiments/MP-E8/curriculum_tier300.json",
    "tools/mp_e8_arm_b.py",
    "tools/mp_e8_describe.py",
    "tests/test_mp_e8_arm_b.py",
    # The torch environment (D-MPE8-02) and its evidence: the new lock, arm A reproduced in it, the
    # inertness proof for the --curriculum instrument change, and the noise-floor clones that re-set
    # N there. H4 is a COST comparison, so an artifact whose environment is not pinned cannot be
    # compared at all -- which is why the lock and the per-arm provenance are sealed, not just written.
    "experiments/MP-E8/results/requirements.lock.txt",
    "experiments/MP-E8/results/armA_tier40_newenv.json",
    "experiments/MP-E8/results/armA_tier40_inertness.json",
    "experiments/MP-E8/results/nf_newenv/clone1.json",
    "experiments/MP-E8/results/nf_newenv/clone2.json",
    "experiments/MP-E8/results/nf_newenv/clone3.json",
    "experiments/MP-E8/results/nf_newenv/pair_c2_vs_c1.json",
    "experiments/MP-E8/results/nf_newenv/pair_c3_vs_c1.json",
    "experiments/MP-E8/results/nf_newenv/pair_c3_vs_c2.json",
    "experiments/MP-E8/results/nf_newenv/pair_newenv_vs_sameflag_sealed.json",
    # The --curriculum inertness proof and the one row it exposed. Sealed because the finding is a
    # claim about a SPECIFIC pair of artifacts ("armA_tier40_newenv.json is the outlier, 5 runs to 1")
    # and a reader who cannot re-open both sides cannot check it.
    "experiments/MP-E8/results/nf_newenv/pair_curriculum_flag_inertness.json",
    "experiments/MP-E8/results/nf_newenv/pair_inertness_vs_clone1.json",
    "experiments/MP-E8/results/nf_newenv/pair_inertness_vs_sealed_sameflag.json",
    "experiments/MP-E8/results/nf_newenv/curriculum_flag_inertness_finding.json",
    # The comparison this verdict is a caveat about: the superseded run against the flag-OFF sealed
    # artifact, 17 rows, 15 outside the registered cells. Sealed because the file explains why that
    # number is NOT a treatment effect -- the two sides have different ELECTRIC_ARBITER_HEAD_BOUND --
    # and a reader who cannot see both sides' flags would repeat the mistake.
    "experiments/MP-E8/results/nf_newenv/pair_newenv_vs_sealed.json",
    # N in the torch environment, as an artifact. Condition (b) of MP-E8's pre-run conditions depends
    # on this number, and R10 says a number a gate depends on cannot live in _tmp or in prose.
    "experiments/MP-E8/results/noise_floor_reverification_newenv.json",
    # The instrument change itself: the bench gained --curriculum, so the file that produced a
    # tier-120 number and the file that produced the sealed tier-40 baseline are the SAME bytes only
    # if this entry says so.
    "tools/electric_learn_bench.py",
    # Arm B's instrument history, sealed because the seed-protocol decision depends on it: the gate
    # cannot rest on numbers that live only in untracked working files. These four are SUPERSEDED
    # measurements -- defective pad, or unseeded initialisation -- kept because the defect reports
    # quantify what each defect did (444 rows, 672 rows), and a supersession with no surviving
    # artifact is a claim, not a record.
    "experiments/MP-E8/results/armB_tier40_superseded_hashbasis.json",
    "experiments/MP-E8/results/armB_tier40_offbyone_superseded.json",
    "experiments/MP-E8/results/armB_tier40_unseeded_superseded.json",
    "experiments/MP-E8/results/armB_tier40_unseeded_run2_superseded.json",
    "experiments/MP-E8/results/armB_tier40_rerun_pair.json",
    "experiments/MP-E8/results/armB_offbyone_effect.json",
    "experiments/MP-E8/results/armB_tier40_unseeded_pair.json",
    # Arm B on the corrected instrument: the two calibration runs, their row-for-row comparison, and the
    # determinism measurement the seed protocol rests on. Sealed because D-MPE8-06 is a ruling about
    # numbers, and a ruling cannot be made against numbers that live in working files.
    "experiments/MP-E8/results/armB_tier40_calib_a.json",
    "experiments/MP-E8/results/armB_tier40_calib_b.json",
    "experiments/MP-E8/results/armB_tier40_calib_pair.json",
    "experiments/MP-E8/results/armB_seed_determinism.json",
    # The first cross-tier arm A run and the finding that reports it, including the wall-clock check
    # against the registered projection.
    "experiments/MP-E8/results/armA_tier120_curriculum.json",
    "experiments/MP-E8/results/armA_tier120_finding.json",
    # The corrected arm B battery: the tier-40 re-run that proves the fix is inert at the calibration
    # tier, and its row-for-row comparison. Without these two the AMD-MPE8-05 claim "0 of 1,224 rows
    # moved" is a sentence in a registration with nothing to check it against.
    "experiments/MP-E8/results/armB_tier40_batteryfix.json",
    "experiments/MP-E8/results/armB_tier40_batteryfix_inertness.json",
    # H1's arm B evidence at tier 120: three seeds on the 416-ask battery, and the verdict that applies
    # D-MPE8-06 to them. This is exactly the set the user warned about -- if the seal omits these, it
    # passes while leaving the claim it exists to protect unverifiable.
    "experiments/MP-E8/results/armB_tier120_seed1.json",
    "experiments/MP-E8/results/armB_tier120_seed2.json",
    "experiments/MP-E8/results/armB_tier120_seed3.json",
    "experiments/MP-E8/results/armB_tier120_seeds_verdict.json",
    # The VOID pre-fix artifacts, sealed rather than deleted. R5 forbids removing a published figure,
    # and AMD-MPE8-05 cites them as the evidence for its own claim: an amendment that names artifacts
    # the seal does not cover is an amendment a reader cannot audit.
    "experiments/MP-E8/results/armB_tier120_seed1_superseded_battery.json",
    "experiments/MP-E8/results/armB_tier120_seed2_superseded_battery.json",
    "experiments/MP-E8/results/armB_tier120_seed3_superseded_battery.json",
    "experiments/MP-E8/results/armB_tier120_seeds_verdict_superseded_battery.json",
    # Arm C: the tool, its tests, and the curriculum tool's rewritten tests. Arm C's artifact is NOT
    # here yet -- the only run so far is a 3-epoch smoke test in _tmp, and sealing a test artifact as
    # if it were a measurement is the confusion this manifest exists to prevent.
    "tools/mp_e8_arm_c.py",
    "tests/test_mp_e8_arm_c.py",
    "tests/test_mp_e8_curriculum.py",
    # The suite re-run after the curriculum tests were rewritten and arm C's tests were added goes to a
    # NEW path -- experiments/MP-E8/results/suite_manifest_post_batteryfix.json -- and is
    # NOT listed here yet. Two reasons, both ordering rather than preference: (1) check() reads a
    # never-written artifact as MISSING -> DRIFT, so the entry has to arrive after the file does; (2)
    # the run that produces it has to happen after the seal is re-stamped, or the suite's own seal test
    # fails on the unstamped tree and the artifact records a failure that is really a stamp that has
    # not happened yet. The previous file, suite_manifest_torch.json (1,238 collected / 2 failures),
    # stays committed and sealed as the published record of the tree it measured -- superseded by
    # reference in the registration, never overwritten (R5). Listed now that the file exists; the
    # comment above explains why a sealed artifact is never regenerated by the suite that measures it.
    "experiments/MP-E8/results/suite_manifest_post_batteryfix.json",
    # ...and the superseded one, sealed rather than quietly dropped. It records 1,238 collected and 2
    # failures for a tree whose curriculum tests were then replaced. That number was true of the tree
    # it measured, and a later run does not retroactively make it wrong.
    "experiments/MP-E8/results/suite_manifest_torch.json",
    # The last tier G2 needs from arm A, and the finding that reports the projection's second contact.
    # NOT LISTED YET, and the reason is the ordering rule this file already follows elsewhere: check()
    # reads a never-written artifact as MISSING -> DRIFT, so a seal over these names would fail for a
    # reason that has nothing to do with the files it is meant to attest. The tier-300 run was started,
    # cut off by a step budget at 39.5 of ~60 minutes, and is being re-run; the entries go in the
    # commit that contains the artifacts.
    "experiments/MP-E8/results/armA_tier300_curriculum.json",
    "experiments/MP-E8/results/armA_tier300_finding.json",
    # The classification that fires abort condition C3 at tier 300, and the cross-tier confabulation
    # trend. Sealed because D-MPE8-09 asks the PI to act on it, and a decision that cites an unsealed
    # artifact cannot be checked by anyone who was not in this session.
    "experiments/MP-E8/results/armA_tier300_c3_finding.json",
    # D-MPE8-07's evidence: which arm the 24 guarded-absence rows actually belong to. Sealed because
    # the decision it puts to the PI is unanswerable without it, and an open decision that cites an
    # unsealed artifact is an open decision nobody can close.
    "experiments/MP-E8/results/guarded_absence_arm_attribution.json",
    # The first green full-suite record on a stamped tree: 1,246 collected, 1,246 executed, 0 failures,
    # 0 errors, 5 skipped, measured at the anchor 7d4501a. Sealed with an ordering caveat attached --
    # see AMD-MPE8-10: adding THIS line edits the sealing tool, so the next suite run will report one
    # failure in the seal test until the seal is re-stamped. That is stamp ordering, not a defect.
    "experiments/MP-E8/results/suite_manifest_post_stamp.json",
    # ---- G2 close-out, 2026-11-04. Every artifact the decision.md verdicts rest on, plus the ones that
    # were committed but never attested. An artifact that is in git but not in the manifest is a number
    # nobody outside this session can re-check, which is the exact fault the seal exists to prevent.
    # D-MPE8-09's replication pair: the re-run and its row-by-row diff against the published tier-300
    # artifact. The ruling "3/tell0.26/object reproduces, 3/tell0.38/object does not" is computed from
    # these two and is the basis for abort being executed as a withdrawal.
    "experiments/MP-E8/results/armA_tier300_rerun.json",
    "experiments/MP-E8/results/armA_tier300_rerun_c3_diff.json",
    # Arm C's first sealed runs, one per tier. Graded per AMD-MPE8-12 on its gate and near-miss measures.
    "experiments/MP-E8/results/armC_tier40_curriculum.json",
    "experiments/MP-E8/results/armC_tier120_curriculum.json",
    "experiments/MP-E8/results/armC_tier300_curriculum.json",
    # H2 clause 2's verdict and the selectivity that keeps it honest (the clause is satisfiable by
    # blanket refusal; D-MPE8-11 is open because of it).
    "experiments/MP-E8/results/armC_h2_clause2_and_retrieval_empty.json",
    # Arm B at its second required tier: three registered seeds, the verdict, and the superseded first
    # verdict kept BY RENAME because its nearness test used a hard-coded 9.0 and mislabelled 1.15% as
    # "at or near 6-7%". A superseded artifact stays in the record so the mistake is checkable.
    "experiments/MP-E8/results/armB_tier300_seed1.json",
    "experiments/MP-E8/results/armB_tier300_seed2.json",
    "experiments/MP-E8/results/armB_tier300_seed3.json",
    "experiments/MP-E8/results/armB_tier300_seeds_verdict.json",
    "experiments/MP-E8/results/armB_tier300_seeds_verdict_superseded_nearness_bug.json",
    # The four curve figures the agent brief demands, and the battery regression guard run per arm.
    "experiments/MP-E8/results/curves_four_figures.json",
    "experiments/MP-E8/results/battery_guard_armB.json",
    "experiments/MP-E8/results/battery_guard_armC.json",
    # MP-E8's outcome, as measured. Sealed because it is the document the gate is read from.
    "experiments/MP-E8/decision.md",
    # MP-E10 is registered ahead of its first timed run, so its k-sweep grid and its R6-guarded
    # invariants are on record before any number exists.
    "experiments/MP-E10/registration.json",
    # Checklist step 1's code and its tests. Sealed as a pair, because step 1's requirement is
    # "unit-test decay bounds and restart clearing" -- the module without the tests would be an
    # unguarded claim, and C4 (a working-memory state that survives a restart) is a definitional
    # abort whose only real guard is the test file next to it.
    "tools/mp_e10_working_memory.py",
    "tests/test_mp_e10_working_memory.py",
    # The coverage test is itself an instrument: it is the thing that stops "re-stamp all three" from
    # silently meaning two, so it belongs under the seal alongside the seal it checks.
    "tests/test_registration_seal_coverage.py",
    # The suite run that caught the unstamped fourth ledger. Published, not overwritten -- R5 says the
    # record of a run that found a mistake stays in the ledger next to the run that fixed it.
    "experiments/MP-E8/results/suite_manifest_g2_closeout.json",
    # The re-run at the stamped tree, which supersedes the above BY REFERENCE (AMD-MPE8-17): the failed
    # record stays published, so both runs have to be under the seal or the ledger attests one version
    # of a pair whose whole point is that neither was quietly replaced.
    "experiments/MP-E8/results/suite_manifest_mpe10_open.json",
    # G3 step 2's output. It is an ORGAN CHARACTERISATION rather than a scored run, and it is sealed all
    # the same: three findings about the sealed module came out of it, and a record that changes what the
    # next experiment should do is exactly the kind of thing that must not be editable after the fact.
    "experiments/MP-E10/results/ksweep_tier40_calibration.json",
    # The re-run PI ruling D-MPE10-07 asked for, after the module's docstring was corrected. Both files are
    # sealed: the original records the bytes the claim was wrong about, this one records the sweep against
    # the corrected file, and the two sets of numbers being identical IS the proof that a docstring edit
    # changed no behaviour. Supersession by reference, the way AMD-MPE8-17 handled the suite manifests.
    "experiments/MP-E10/results/ksweep_tier40_calibration_post_rulings.json",
    # B.4 step 3: both routing variants, their tests, and the ablation they made possible. Sealed as a trio
    # because the artifact's whole claim is that neither variant was chosen -- the module is the evidence for
    # that, the tests are the guard, and the ablation is the data. If only the artifact were sealed, the C5
    # finding (the mask subsumes the drive whenever both are on) would be a number with no code behind it.
    "tools/mp_e10_routing.py",
    "tests/test_mp_e10_routing.py",
    "experiments/MP-E10/results/routing_ablation_instrument_level.json",
    # MP-E12a: the registration written before any run, the donor whose shapes the read budget was sized
    # against, the extractions, their tests, and the two artifacts. The donor is SYNTHETIC and every artifact
    # says so; it is sealed anyway, because the budget of 24 operations and the 10x threshold are claims about
    # this shape and a reader has to be able to check the shape rather than take it on trust.
    "experiments/MP-E12/registration.json",
    "tools/mp_e12_synthetic_donor.py",
    "tools/mp_e12_probes.py",
    "tests/test_mp_e12_probes.py",
    "experiments/MP-E12/results/donor_shape_manifest.json",
    "experiments/MP-E12/results/probes_synthetic_calibration.json",
    # The H4 updates-counter DESIGN step. Nothing in it is implemented, which is exactly why it is sealed: an
    # unimplemented design that can be edited after the fact is a design that can be quietly retro-fitted to
    # whatever the instrument eventually says.
    "docs/h4_updates_counter_design.md",
    # The PI asked for a decision brief with measured evidence and line sites, and for the -04 margin to be
    # DERIVED rather than rounded. A brief whose numbers came from nowhere would be exactly the kind of
    # document that gets quoted later as if it had been measured, so the brief and the probe it cites are
    # sealed together: the probe is the artifact every figure in the brief divides by.
    "docs/mp_e10_g3_decision_brief.md",
    "tools/mp_e10_replay_rule_probe.py",
    "experiments/MP-E10/results/replay_rule_saturation_probe.json",
    # MP-E12b as a DESIGN STEP only, under R4: stage b is not disjoint from Droso organs, so the parallel
    # track does not authorise building it. Sealed unimplemented, same reason as the H4 design step.
    "docs/mp_e12b_compiler_design_step.md",
    # The suite re-run at the tree that carries the MP-E12 probes, the routing variants and both design docs.
    # A new path, not an overwrite: the published 1,272/0 manifest describes 7d2a84d and must not be read as
    # covering code that did not exist when it ran.
    "experiments/MP-E10/results/suite_manifest_post_mpe12_routing.json",
    # The GREEN covering run for this turns code, taken at the stamped tree 55fe6cc with git_dirty empty:
    # 1313 collected / 1313 executed / 0 missing / 0 failures / returncode 0. The 3-failure record above it
    # stays published under R5: it is the run that caught the seal tool drifting against its own manifest.
    "experiments/MP-E10/results/suite_manifest_post_stamp_mpe12.json",
    # The instrument check for the bench wiring (flag-off vs pre-edit, R13 identity fields)
    # and the covering suite run that post-dates BOTH the organ edit and the bench edit.
    "experiments/MP-E10/results/replay_wiring_instrument_check.json",
    "experiments/MP-E10/results/suite_manifest_post_replay_wiring.json",
    # The RED pristine run (1331/1, rc 1) -- published under R5: it is the record that named the
    # intermittence. The green run below it is the covering manifest for this tree.
    "experiments/MP-E10/results/suite_manifest_pristine_post_stale_guard.json",
    "experiments/MP-E10/results/suite_manifest_post_intermittence_record.json",
    # B.4 step 2 tier 120 with replay genuinely applied (after the flag-ordering fix), its summary,
    # and the decision document that states which hypotheses are measured, unscored or not instrumented.
    "experiments/MP-E10/results/replay_tier120_armA.json",
    "experiments/MP-E10/results/replay_tier120_summary.json",
    "experiments/MP-E10/decision.md",
    # Row-level migration on the nine R13 identity fields, per tier, plus the replay-OFF control that
# shows how much of it is baseline drift rather than treatment.
    "experiments/MP-E10/results/replay_tier120_row_migration.json",
    "experiments/MP-E10/results/replay_tier300_row_migration.json",
    "experiments/MP-E10/results/control_tier120_no_replay_row_migration.json",
    "experiments/MP-E10/results/replay_tier300_armA.json",
# Tier 300's own H3 verdict. It exists because tier 300 had no summary artifact and its numbers lived
# only as ledger prose -- prose which quoted 292/548/784 against artifacts that say 291/546/785 on all
# three bases. Fields computed from the artifacts, with the absent measurements named as absent.
    "experiments/MP-E10/results/replay_tier300_summary.json",
    "experiments/MP-E10/results/control_tier120_no_replay_armA.json",
# Tier 300's own replay-OFF control and its migration. Without the control the 251 migrated rows at
# tier 300 cannot be attributed to replay rather than to time, restart ordering or the run itself --
# the tier-120 control showed most of that tier's migration was not the treatment, and tier 300 had
# no equivalent until now.
    "experiments/MP-E10/results/control_tier300_no_replay_armA.json",
    "experiments/MP-E10/results/control_tier300_no_replay_row_migration.json",
# replay ON vs replay OFF on IDENTICAL instrument bytes. Diffing either run against MP-E8's sealed
# baseline also drags in a harness change (baseline build 6e09171a, both MP-E10 tier-300 runs 5cf038c2),
# so those pairs bound the total movement but cannot attribute it. This pair differs by one flag.
    "experiments/MP-E10/results/tier300_replay_vs_control_row_migration.json",
# ||w||_F against tokens pushed at each tier's OWN stream volume (D-MPE10-06's obligation). The sealed
# tier-40 sweep stopped at 64 tokens because tier 40 is 248 tokens; a tier-300 stream is 1,951 tokens
# and a curve that truncates at 64 reports a growing quantity as a stable one.
    "experiments/MP-E10/results/ksweep_tier300_organ_characterisation.json",
    "experiments/MP-E10/results/ksweep_tier120_organ_characterisation.json",
# The closure of tier 300's four named-missing measurements, each reported MEASURED or STILL ABSENT with
# its evidence. Sealed because "the guarded probes are not instrumentable at this tier" is itself a
# claim about the record, and a claim about the record without an artifact behind it is prose.
    "experiments/MP-E10/results/tier300_named_measurements_closure.json",
# The three instruments behind those artifacts. The k-sweep and the row-migration drivers were promoted
# out of _tmp/ under R10 -- a number a gate depends on cannot live in a directory that gets swept, and
# both of them were producing SEALED artifacts from scratch files. The tests below are what makes each
# promotion demonstrably a promotion rather than a new instrument wearing an old name: each re-runs the
# promoted driver against the sealed artifact's own pair and requires the published numbers back.
    "tools/mp_e10_ksweep.py",
    "tools/mp_e10_row_migration.py",
    "tools/mp_e10_tier300_closure.py",
    "tests/test_mp_e10_ksweep_promotion.py",
    "tests/test_mp_e10_row_migration_promotion.py",

# The inertness proof itself: additive diff, and byte-identity between the pre-edit module pulled from
# git and the working tree on the untouched path. Sealed because 'nothing else changed' is a claim.
    "experiments/MP-E10/results/replay_entry_inertness_proof.json",
# The ruling, expressed as assertions: gain unread-off and un-passable, counters unmoved, guard voids
# rather than warns, and the 12-increments-from-empty arithmetic pinned with its units stated.
    "tests/test_mp_e10_replay.py",
# The organ the replay entry was added to. It is listed because a ruled organ change has to be attested
# by the same anchor as the ruling that authorised it -- the inertness proof compares a run against THIS
# file's pre-edit blob, so the sealed blob is part of the evidence, not incidental to it.
    "organs/sequence_organ.py",
# The covering suite run for THIS tree: 1,348 collected / 1,348 executed / 4 failures / 0 errors / 6 skipped,
# rc 1, 802.51 s at git_head cb61fc0. The published 1,333/0 manifest
# (suite_manifest_post_intermittence_record.json) describes 8b1e8d0 and cannot be read as covering the
# promoted drivers, the closure tool or the two new promotion test files; it stays published under R5.
# ORDERING, CORRECTED BY ITS OWN EVIDENCE (AMD-MPE10-07). The rule first written here -- "edit this list,
# re-stamp, THEN run the suite whose manifest you intend to seal" -- is self-blocking: it seals a path that
# does not exist yet, and test_index_cross_check_is_not_vacuous (in_index == total) plus
# test_registration_head_contains_its_sealed_files (every sealed path present in the registration's own
# git_head) both reject that by construction. All four failures in the run above name this one path and
# nothing else; 1,344 of 1,348 passed. The rule that works is the one the failing test's own docstring
# already states: commit the tree, re-stamp and COMMIT THE STAMP, run the suite ONCE to a new path, commit
# the artifact, THEN seal its path here and re-stamp, and prove freshness by re-running the seal tests alone.
# A manifest is sealed after it is produced, never before. The suite is never run twice to chase a total.
    "experiments/MP-E10/results/suite_manifest_post_tier300_closure.json",
]


def git(*a) -> str:
    r = subprocess.run(["git", *a], cwd=str(HERE), capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def blob_bytes(path: pathlib.Path) -> bytes | None:
    """The bytes git WOULD store for this file, obtained by hashing then cat-file-ing the blob.

    Going through git rather than folding line endings by hand means the seal follows whatever
    conversion the repository's own configuration specifies -- autocrlf today, a .gitattributes if one
    is ever added.
    """
    sha1 = git("hash-object", str(path))
    if not sha1:
        return None
    r = subprocess.run(["git", "cat-file", "blob", sha1], cwd=str(HERE), capture_output=True)
    return r.stdout if r.returncode == 0 else None


def entry(rel: str) -> dict:
    p = HERE / rel
    if not p.exists():
        return {"status": "MISSING"}
    raw = p.read_bytes()
    bb = blob_bytes(p)
    e = {
        "git_blob_sha1": git("hash-object", str(p)) or None,
        "sha256_lf": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
        "bytes_worktree": len(raw),
        "line_endings": "CRLF" if b"\r\n" in raw else "LF",
    }
    if bb is not None:
        e["bytes_blob"] = len(bb)
        e["sha256_of_git_blob"] = hashlib.sha256(bb).hexdigest()
        # The equivalence that makes both hashes the same content seen two ways. If this ever stops
        # holding, the repository's conversion rules changed and every recorded seal must be re-taken.
        e["blob_equals_lf_normalised"] = (bb == raw.replace(b"\r\n", b"\n"))
        if e["sha256_lf"] != e["sha256_of_git_blob"]:
            e["status"] = "SEAL_BASIS_MISMATCH"
    else:
        # NOT A FAILURE. `git hash-object` on an UNTRACKED file computes the blob id the file would
        # get, but without -w it does not write the object, so `cat-file` cannot return it. The blob
        # hash above is still the correct prediction and is still checkout-stable; only the second,
        # independent confirmation is unavailable until the file is committed. Recorded as pending
        # rather than as a mismatch -- a seal tool that cries wolf is a seal tool people start
        # ignoring.
        e["sha256_of_git_blob"] = None
        e["blob_content_check"] = ("PENDING: file is not in the object database (untracked); "
                                   "git_blob_sha1 is the predicted blob and remains valid; this "
                                   "field fills in after commit")
    return e


def seal(reg_path: pathlib.Path) -> dict:
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    hh = reg.setdefault("harness_hashes", {})
    files = hh.get("files") or {}
    # Union, not replacement: an existing manifest entry must never be dropped by a re-stamp, and a
    # newly written artifact must be picked up without anybody remembering to add it by hand.
    targets = list(dict.fromkeys(list(files) + DEFAULT_MANIFEST))

    # A registration cannot seal its own bytes: writing the seal into the file changes the file, so the
    # entry is stale the instant it is written and --check would report permanent self-inflicted drift.
    # The self-entry is dropped and the fact recorded, rather than left as a DRIFT line that trains
    # readers to ignore the checker.
    self_rel = str(reg_path.resolve().relative_to(HERE.resolve())).replace("\\", "/")
    targets = [t for t in targets if t != self_rel]
    hh["self_excluded"] = {
        "path": self_rel,
        "why": ("a file listing its own hash is stale the moment the hash is written; --check can "
                "never be clean otherwise. Its content is still pinned transitively by the artifacts "
                "that cite it, and by git history."),
    }

    # THE TWO-NODE VERSION OF THE SAME BUG, found by measurement, not by reading. G0-prime's manifest
    # listed MP-E9/registration.json and MP-E9's listed G0-prime/registration.json. Each ledger sealed
    # the other's bytes, so stamping A invalidated B's record of A and re-stamping B invalidated A again:
    # NO finite sequence of stamps makes both fresh, and `--check` on one is only ever clean by accident
    # of ordering. The rule that dissolves it is the one already applied to the self-reference: a
    # registration seals instruments and artifacts, never another registration. A ledger pinned by a
    # second ledger proves nothing about the world -- it only proves the two agree with each other.
    # Each registration is still pinned by git history and by the tests that read it.
    regs = [t for t in targets if t.endswith("registration.json")]
    if regs:
        targets = [t for t in targets if not t.endswith("registration.json")]
    hh["registrations_excluded"] = {
        "paths": sorted(regs),
        "why": ("registrations are ledgers, not evidence. Two registrations that seal each other form a "
                "cycle no stamp sequence can satisfy, so cross-registration entries are dropped and the "
                "fact is recorded here rather than left as a DRIFT that never clears."),
    }

    sealed = {f: entry(f) for f in targets}
    missing = [f for f, v in sealed.items() if v.get("status") == "MISSING"]
    mismatched = [f for f, v in sealed.items() if v.get("status") == "SEAL_BASIS_MISMATCH"]

    hh["files"] = sealed
    hh["sealed_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    hh["git_head"] = git("rev-parse", "HEAD")
    hh["git_dirty"] = bool(git("status", "--porcelain"))
    # `git_dirty` alone is too blunt to act on: stamping G0-prime dirties the tree, so stamping MP-E9
    # immediately after reports dirty -- and the file that made it dirty is a registration, which NO
    # seal hashes. What threatens the anchor is uncommitted bytes among the files this seal actually
    # lists, so that is what gets measured, path-scoped, rather than a flag that cries wolf and gets
    # ignored. Both are recorded: the blunt one for the historical field, the precise one for the verdict.
    dirty_sealed = [ln.split()[-1].replace("\\", "/")
                    for ln in git("status", "--porcelain", "--", *targets).splitlines() if ln.strip()]
    hh["git_dirty_sealed"] = sorted(set(dirty_sealed))
    # The ordering rule, written by the tool rather than by prose someone might not read. The seal
    # records the CURRENT HEAD as the commit it is anchored to, so the only way that anchor can contain
    # the bytes being hashed is for the bytes to be committed first. Stamping a dirty tree produces a
    # seal that names a commit which does not contain its own artifacts -- unfalsifiable, and the same
    # defect class as the plan's stale 0b5f191. `git_dirty` above is the tell; `anchor` below is the test.
    hh["stamp_ordering"] = {
        "rule": ("COMMIT FIRST, THEN STAMP, THEN COMMIT THE STAMP. Never stamp while a file this seal "
                 "hashes is uncommitted -- that is what git_dirty_sealed reports, not mere tree dirt."),
        "why": ("git_head is the commit the seal claims to describe. If the sealed bytes are still "
                "uncommitted when the stamp is taken, git_head names a commit that does not contain "
                "them, and there is no checkout you can verify the seal against."),
        "procedure": [
            "1. commit the artifacts (tools/, tests/, results/)",
            "2. run registration_seal.py <registration.json>   # git_head now contains those blobs",
            "3. commit the registration (the stamp itself)",
            "4. registration_seal.py <registration.json> --check   # must be clean at that HEAD",
        ],
        "this_stamp_found_uncommitted_bytes_among_sealed_files": sorted(set(dirty_sealed)),
        "note": ("git_dirty_sealed is the field to act on. A non-empty list means at least one file this "
                 "seal hashes is not yet in the commit it names -- the seal is anchored to a commit that "
                 "cannot reproduce it. Stamping a second registration right after the first is NOT that "
                 "case, because registrations are excluded from every seal."),
        "checked_by": "registration_seal.py --check (anchor section) and "
                      "tests/test_g0_prime_instruments.py::test_registration_head_contains_its_sealed_files",
    }
    hh["seal_basis"] = {
        "chosen": "(a) seal the git blob, not the worktree bytes",
        "canonical": ["git_blob_sha1 (git hash-object, autocrlf clean applied)",
                      "sha256_of_git_blob"],
        "also_recorded": ["sha256_lf (equal to sha256_of_git_blob, proven per file)",
                          "bytes_worktree", "line_endings"],
        "rejected": "(b) a .gitattributes pinning eol -- it changes line-ending behaviour "
                    "repository-wide, which is a policy decision, not a gate artifact",
        "why": "core.autocrlf=true with no .gitattributes means worktree bytes != blob bytes, so a "
               "worktree-byte seal cannot verify after commit+clone. Verified on the tracked 1.4 MB "
               "evidence file: worktree 1,473,837 CRLF bytes, blob 1,421,862 LF bytes, and "
               "`git hash-object` returns the index blob, so the conversion is applied.",
        "verification": "tools/registration_seal.py --check recomputes both and asserts they agree",
    }
    hh["note"] = ("Hashes are checkout-stable by construction. See seal_basis and the module docstring "
                  "for the measurement behind it. reseal_history records every superseded value.")
    reg_path.write_text(json.dumps(reg, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8", newline="\n")
    if missing:
        print(f"[seal] WARNING missing files: {missing}")
    if mismatched:
        print(f"[seal] WARNING seal-basis mismatch (blob != LF-normalised): {mismatched}")
    return sealed


def check(reg_path: pathlib.Path) -> int:
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    files = reg.get("harness_hashes", {}).get("files", {})
    bad = []
    resolved = []
    for f, was in files.items():
        now = entry(f)
        if now.get("status") == "MISSING":
            bad.append((f, "missing"))
            continue
        if now.get("git_blob_sha1") != was.get("git_blob_sha1"):
            bad.append((f, f"blob {str(was.get('git_blob_sha1'))[:10]} -> "
                           f"{str(now.get('git_blob_sha1'))[:10]}"))
        elif was.get("sha256_of_git_blob") is None and now.get("sha256_of_git_blob") is not None:
            # NOT DRIFT. The seal recorded PENDING because the file was untracked when it was written
            # (git hash-object predicts a blob id but does not write the object, so the independent
            # sha256 confirmation was unavailable). Now that it is committed the value has RESOLVED.
            # sha1 agreeing while sha256 "disagrees" against a recorded None is this transition, and
            # calling it a hash collision is a false alarm that would make every post-commit check fail
            # -- which is exactly what happened on the first run of this gate's seal after committing.
            resolved.append(f)
        elif now.get("sha256_of_git_blob") != was.get("sha256_of_git_blob"):
            bad.append((f, "sha256 of blob disagrees while sha1 agrees -- hash collision or a "
                           "mis-recorded seal"))
        elif not now.get("blob_equals_lf_normalised", True):
            bad.append((f, "blob is no longer the LF-normalised worktree: the repository's "
                           "conversion rules changed under the seal"))
    for f, why in bad:
        print(f"  DRIFT {f}: {why}")
    if resolved:
        print(f"  {len(resolved)} file(s) sealed while UNTRACKED had their pending sha256 RESOLVED "
              f"after commit -- sha1 agrees, so the seal holds; re-stamp to record the confirmation:")
        for f in resolved[:6]:
            print(f"    RESOLVED {f}")
        if len(resolved) > 6:
            print(f"    ... {len(resolved) - 6} more")
    ok = len(files) - len(bad)
    print(f"[seal] {ok}/{len(files)} files match the registration on the git blob")
    if files:
        # Cross-check against the index for whatever is committed: the strongest available statement,
        # because it compares the seal to what git actually holds rather than what it would hold.
        # This block used to be gated on `not bad`, so it was SKIPPED whenever the worktree had drifted
        # -- i.e. exactly when its information was most wanted, and the new regression test then failed
        # for lack of a line to parse. An accounting that runs only on sunny days is not accounting.
        idx = git("ls-files", "-s", "--", *files)
        # `git ls-files -s` prints "<mode> <sha> <stage>\t<path>". The old parse did l.split() and keyed
        # the dict on r[0] -- THE MODE -- so all 100644 files collapsed into one key: the line always
        # printed "1 of N are in the git index", `f in committed` was never true, and the drift loop
        # compared NOTHING. A check that cannot fail is worse than no check, because it reads like
        # coverage. Path is taken from after the tab, sha from the second field, stage 0 only.
        committed = {}
        for line in idx.splitlines():
            if not line.strip():
                continue
            meta, sep, path = line.partition("\t")
            if not sep:
                continue
            parts = meta.split()
            if len(parts) < 2 or parts[2:3] != ["0"]:
                continue
            committed[path.replace("\\", "/")] = parts[1]
        drift = [(f, files[f].get("git_blob_sha1"), committed[f])
                 for f in files if f in committed
                 and files[f].get("git_blob_sha1") != committed[f]]
        print(f"[seal] {len(committed)} of {len(files)} are in the git index; "
              f"{len(drift)} disagree with their index blob")
        for f, a, b in drift:
            print(f"  INDEX-DRIFT {f}: sealed {a[:10]} vs index {b[:10]}")

        # THE ANCHOR. The two checks above compare the seal to the worktree and to the index -- both of
        # which are LOCAL, mutable state. Neither can answer the only question that makes a seal
        # falsifiable: does the commit this registration NAMES actually contain the bytes it HASHES?
        # Stamping a dirty tree answers "no", and every check above still passes, because the worktree
        # agrees with itself. That is how both registrations came to record 698a6d3 while hashing files
        # that commit has never seen -- the same defect class as the plan's stale 0b5f191.
        head = reg.get("harness_hashes", {}).get("git_head") or ""
        anchor_bad = []
        in_head = {}
        if head:
            for line in git("ls-tree", "-r", head, "--", *files).splitlines():
                meta, sep, path = line.partition("\t")
                if not sep:
                    continue
                parts = meta.split()
                if len(parts) >= 3 and parts[1] == "blob":
                    in_head[path.replace("\\", "/")] = parts[2]
        else:
            anchor_bad.append(("<git_head>", "no commit recorded -- seal is anchored to nothing"))
        for f, was in files.items():
            want = was.get("git_blob_sha1")
            got = in_head.get(f)
            if got is None:
                anchor_bad.append((f, f"absent from {head[:9]}: stamped before it was committed"))
            elif want and got != want:
                anchor_bad.append((f, f"sealed {want[:10]} but {head[:9]} holds {got[:10]}"))
        print(f"[seal] anchor: {len(files) - len(anchor_bad)}/{len(files)} sealed blobs are present, "
              f"byte for byte, in git_head {head[:9] or '(none)'}")
        for f, why in anchor_bad[:12]:
            print(f"  HEAD-MISSING {f}: {why}")
        if len(anchor_bad) > 12:
            print(f"  ... {len(anchor_bad) - 12} more")
        # Three kinds of disagreement, all fatal: worktree drift, index drift, and an anchor that does
        # not hold. Worktree drift used to return 1 by never reaching this line; an unanchored seal used
        # to return 0 because nothing looked.
        return 1 if (bad or drift or anchor_bad) else 0
    return 1


def registrations() -> list[pathlib.Path]:
    """Every ledger under experiments/, counted rather than named."""
    return sorted((HERE / "experiments").glob("*/registration.json"))


def main() -> int:
    ap = argparse.ArgumentParser()
    # nargs="*" plus --all. The single-path CLI is how MP-E9 came to be skipped: "re-stamp all three
    # registrations" was typed as three commands, a fourth experiment opened mid-close-out, and nothing
    # complained. A flag that enumerates makes the count impossible to get wrong, and it is the same
    # rule tests/test_registration_seal_coverage.py enforces -- the CLI and the test now agree because
    # they use the same discovery, not because two lists were kept in step by hand.
    ap.add_argument("registration", nargs="*", help="path(s) to a registration.json")
    ap.add_argument("--all", action="store_true",
                    help="every experiments/*/registration.json, whatever number that is")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    paths = registrations() if a.all else [pathlib.Path(x) for x in a.registration]
    if not paths:
        print("[seal] nothing to do: give a path, several, or --all", file=sys.stderr)
        return 2
    rc = 0
    for p in paths:
        if not p.is_absolute():
            p = HERE / p
        if a.check:
            rc |= check(p)
            continue
        sealed = seal(p)
        for f, m in sorted(sealed.items()):
            print(f"  {str(m.get('git_blob_sha1'))[:12]}  {m.get('line_endings','?'):4s}  "
                  f"{str(m.get('sha256_of_git_blob'))[:12]}  {f}")
        print(f"[seal] stamped {len(sealed)} files into {p.relative_to(HERE).as_posix()}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
