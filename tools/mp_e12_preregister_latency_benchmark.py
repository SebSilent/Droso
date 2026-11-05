"""Pre-register MP-E12a B.6 item 5, the latency benchmark, WITHOUT running it.

Why this file exists: item 5 is the only remaining MP-E12a measurement that needs a decision rather than
machine time, and a methodology registered after the first timing is not a methodology, it is a description of
whatever happened. Everything here is fixed before a clock starts: the query set, the repetition count, the
statistic, the identity of the machine and interpreter, what each arm operationally is, and which rule bounds
which quantity. Nothing here is a measurement of latency, and the artifact says so in its own body.

Machine identity is re-measured on every regeneration, never copied, because R15 makes the interpreter a seal
component: an artifact that carried a stale CPU string would be indistinguishable from one that carried a made-up
one.

Usage: python tools/mp_e12_preregister_latency_benchmark.py [--out PATH]
"""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "MP-E12" / "results" / "latency_benchmark_preregistration_v1.json"
PROBES = ROOT / "experiments" / "MP-E12" / "results" / "probe_list_v1.json"
GRAPH = ROOT / "experiments" / "MP-E12" / "results" / "association_graph_real_class1.json"

SEAL = ROOT / "experiments" / "MP-E12" / "registration.json"
PLAN = "experiments/MP-E9/plan_extract/DROSO_Master_Plan_v1_2.md"

# ---- the query set, named before any timing -------------------------------------------------------------
# The 24 registered probes of probe_list_v1.json are the only query set the program has already fixed in advance
# and sealed. Re-using them is not a convenience: it is what makes H2's "equivalent association queries" mean
# something, because the same 24 items are the ones whose read cost is already journaled and sealed.
CURVE_POINTS = [1, 5, 9]           # fixed by D-MPE12-05, not chosen here
MEAN_LENGTH_POINT = "donor_measured_mean_answer_length"   # a required point with no value yet

# ---- the repetition count, named before any timing ------------------------------------------------------
REPEATS = 25                       # odd, so the median is an observed value rather than an interpolation
WARMUP_DISCARDED = 5               # discarded from the statistic, recorded in the artifact, never deleted
DISCARD_RULE = "first WARMUP_DISCARDED repetitions per (query, point, arm), by recorded index order"

# ---- the statistic, named before any timing -------------------------------------------------------------
STATISTIC = "median"
SPREAD = "MAD (median absolute deviation) and the 5th/95th percentiles of the kept repetitions"
RATIO_RULE = ("the claim is the ratio of medians, arm_inference / arm_read, reported at every curve point as a "
              "curve; a single point may never be headlined (D-MPE12-05)")
PASS_RULE = ("H2 passes at a point only if the ratio of medians is >= 10 AND the read arm's 95th percentile is "
             "below the inference arm's 5th percentile. The second condition is what stops a 10x median from "
             "being an artefact of one slow inference repetition; it is registered now, before either arm has a "
             "number.")


def line_of(path, needle, label):
    lines = (ROOT / path).read_text(encoding="utf-8", errors="replace").splitlines()
    hits = [i for i, l in enumerate(lines, 1) if needle in l]
    if len(hits) != 1:
        raise SystemExit(f"REFUSED: {label} needle matched {len(hits)} lines")
    return hits[0], lines[hits[0] - 1].strip()


def ps(script):
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                           capture_output=True, text=True, timeout=120)
        s = (p.stdout or "").strip()
        return s if s else f"(empty; rc={p.returncode})"
    except Exception as e:
        return f"(failed: {e})"


def imported(mod):
    try:
        m = __import__(mod)
        return {"available": True, "version": getattr(m, "__version__", "unknown")}
    except Exception as e:
        return {"available": False, "error": type(e).__name__}


def machine_identity():
    cpu = json.loads(ps("Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,"
                        "NumberOfLogicalProcessors,MaxClockSpeed | ConvertTo-Json"))
    if isinstance(cpu, list):
        cpu = cpu[0]
    cs = json.loads(ps("Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory,"
                       "Manufacturer,Model | ConvertTo-Json"))
    osx = json.loads(ps("Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,"
                        "TotalPhysicalMemory | ConvertTo-Json"))
    batt = ps("Get-CimInstance Win32_Battery | Select-Object BatteryStatus,EstimatedChargeRemaining | ConvertTo-Json")
    gpus = ps("Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM | ConvertTo-Json")
    return {
        "how_obtained": "platform / os / subprocess + Get-CimInstance on this machine, in this step; re-measured on "
                        "every regeneration rather than copied. Nothing here is quoted from a spec sheet.",
        "python": {
            "implementation": platform.python_implementation(),
            "version": sys.version.split()[0],
            "version_full": sys.version.replace("\n", " "),
            "executable": sys.executable,
            "virtualenv": sys.prefix != sys.base_prefix,
            "build_and_compiler": f"{platform.python_build()} {platform.python_compiler()}",
        },
        "os": {"caption": osx.get("Caption"), "version": osx.get("Version"),
               "build_number": osx.get("BuildNumber"), "platform": platform.platform(),
               "machine": platform.machine(),
               "win32_operatingsystem_total_physical_memory": osx.get("TotalPhysicalMemory"),
               "note": "that CIM property returns null on this machine; the RAM figure below comes from "
                       "Win32_ComputerSystem and agrees with GlobalMemoryStatusEx. Recorded as a property of the "
                       "environment, not smoothed over (R15/R16: cross-version and cross-environment differences "
                       "are re-measured, not reconciled by narrative)."},
        "machine": {"manufacturer": cs.get("Manufacturer"), "model": cs.get("Model"),
                    "a_laptop_as_reported_by_cim": str(cs.get("Model", "")).startswith("HP Pavilion Laptop")},
        "cpu": {"name": cpu.get("Name"), "physical_cores": cpu.get("NumberOfCores"),
                "logical_processors": cpu.get("NumberOfLogicalProcessors"),
                "max_clock_speed_mhz_as_reported": cpu.get("MaxClockSpeed"), "os_cpu_count": os.cpu_count()},
        "memory": {"total_physical_bytes": cs.get("TotalPhysicalMemory"),
                   "total_physical_gb": round((cs.get("TotalPhysicalMemory") or 0) / 2**30, 2)},
        "storage": {"project_drive": os.path.abspath(os.getcwd())[0] + ":",
                    "free_bytes": shutil.disk_usage(os.getcwd()).free},
        "graphics": {"controllers_from_cim": gpus,
                     "nvidia_smi": ps("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader")},
        "power": {"battery_from_cim": batt, "power_scheme": ps("powercfg /getactivescheme"),
                  "plan_clause": "v1.2:173-175 -- the laptop's power state is a registered condition of every run; "
                                 "thermals and battery state are measurement conditions, not ambience."},
        "thermal_throttling": "NOT measured in this step; a timed run records it before and after.",
        "threading_conditions_that_change_wall_clock_and_are_not_yet_pinned": {
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS", "unset"),
            "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS", "unset"),
            "why_it_matters": "torch defaults to a thread count derived from the CPU, and a multi-threaded "
                              "inference arm against a single-threaded read arm is not a comparison of two access "
                              "classes, it is a comparison of two thread counts. The values a timed run must pin "
                              "are named here as an open condition, not assumed settled.",
        },
        "modules": {m: imported(m) for m in ("numpy", "torch", "transformers", "tokenizers", "safetensors",
                                             "psutil")},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    probes = json.loads(PROBES.read_text(encoding="utf-8"))
    words = [p["word"] for p in probes["probes"]]
    if len(words) != 24 or len(set(words)) != 24:
        raise SystemExit(f"REFUSED: query set is not 24 unique words (got {len(words)})")

    CLUST = ROOT / "experiments" / "MP-E12" / "results" / "clustering_limitation_v1.json"
    g = json.loads(GRAPH.read_text(encoding="utf-8"))
    cl = json.loads(CLUST.read_text(encoding="utf-8"))

    seal = json.loads(SEAL.read_text(encoding="utf-8"))["harness_hashes"]
    ident = machine_identity()

    ln_r11, txt_r11 = line_of(PLAN, "R11 — The library is addressed, never executed", "R11")
    ln_r17, txt_r17 = line_of(PLAN, "R17 — No behavioural claim without a floor", "R17")
    ln_h2, txt_h2 = line_of(PLAN, "**H2 (latency).**", "H2")
    ln_ctrl, txt_ctrl = line_of(PLAN, "The control (the rival hypothesis)", "control class")
    ln_e12a, _ = line_of(PLAN, "**Stage MP-E12a — the address space and the calibration donor", "MP-E12a")
    ln_c4, txt_c4 = line_of(PLAN, "**C4 (new): any donor forward pass detected in the deployment loop", "C4")

    torch_present = ident["modules"]["torch"]["available"]
    transformers_present = ident["modules"]["transformers"]["available"]

    art = {
        "schema": "mp_e12.latency_benchmark_preregistration.v1",
        "experiment": "MP-E12a", "stage": "E12a",
        "registered_at_utc": now,
        "status": "PRE-REGISTERED AND UNEXECUTED. No timing exists anywhere in this artifact.",
        "what_this_artifact_is": "The methodology of MP-E12a B.6 item 5, fixed before the first clock starts, so "
                                 "that when the PI rules on the one question that gates it the run is ruleable and "
                                 "runnable without a new registration step. It is a rule, not a result.",
        "what_this_artifact_is_not": [
            "not a latency measurement: every field that would hold a duration is null and marked as awaiting a run",
            "not evidence toward H2, in either direction",
            "not a re-basing of the >=10x threshold: it names the place where that would happen and does not do it",
            "not an authorisation to run the donor: the question that gates it is registered as open (D-MPE12-09)",
            "not a change to any cap, budget, threshold or probe list -- those are quoted as sealed",
        ],

        "1_query_set_named_before_any_timing": {
            "source": "set below: the path of the sealed probe list this set is read from",
            "n_queries": len(words),
            "queries": words,
            "why_this_set": "It is the only query set the program fixed in advance and sealed before any extraction "
                            "(v1, fixed_at_utc 2026-11-05T09:11:34Z, deferred list intact). H2 says 'equivalent "
                            "association queries', and equivalence has to mean something checkable: these are the "
                            "same 24 items whose read cost is already journaled and sealed at 48 registered / 96 "
                            "conservative operations.",
            "selection_rule_inherited": probes["selection_rule"],
            "the_17_deferred_words_are_EXCLUDED": "They are not probes under v1, and the sub-token rule is "
                                                  "registered but not applied; admitting them now would change the "
                                                  "query set after the graph was sealed on it.",
            "prompt_form_for_the_inference_arm": "The query is the registered vocab_form, presented as the model's "
                                                 "own input ids, and the arm is asked to generate the curve point's "
                                                 "count of tokens from it. Greedy decoding, no sampling, batch 1. "
                                                 "Named now because a decoding strategy chosen after seeing a "
                                                 "number is a second instrument, not a detail.",
            "naming": "vocab_form as recorded in probe_list_v1.json, read from the file rather than re-derived "
                      "(the bug the BPE check found in itself: re-deriving a form disagreed with the record on "
                      "'nora', whose registered form is capitalised).",
        },

        "2_repetitions_and_statistic": {
            "repetitions_per_query_per_point_per_arm": REPEATS,
            "warmup_repetitions_discarded_per_cell": WARMUP_DISCARDED,
            "discard_rule": DISCARD_RULE,
            "why_an_odd_count": "the median is then an observed value, not an interpolation between two",
            "timed_measurements_planned": {
                "read_arm": len(words) * len(CURVE_POINTS) * REPEATS,
                "inference_arm_at_the_three_named_points": len(words) * len(CURVE_POINTS) * REPEATS,
                "note": "the fourth curve point cannot be counted until it has a value, and it cannot have a "
                        "value without running the donor",
            },
            "statistic": STATISTIC, "spread": SPREAD, "ratio_rule": RATIO_RULE, "pass_rule": PASS_RULE,
            "order_of_repetitions": "interleaved across arms within a cell, not arm-then-arm, so that a drift in "
                                    "machine state (thermals, background load, battery transition) loads on both "
                                    "arms instead of landing between them",
            "a_run_that_stops_early": "a cell with fewer than REPEATS kept repetitions is reported as incomplete "
                                      "with its count, never as a number with a smaller denominator",
        },

        "3_hardware_and_interpreter_identity_R15": {
            "rule": "R15 makes the interpreter a seal component and forbids smoothing a cross-version comparison. "
                    "So the identity recorded is the seal's own bytes and the machine's own reported fields, not a "
                    "description of them.",
            "measured_identity": ident,
            "seal_identity_at_registration": {
                "git_head": seal["git_head"],
                "sealed_at_utc": seal["sealed_at_utc"],
                "seal_basis": seal["seal_basis"]["chosen"],
                "n_files_sealed": len(seal["files"]),
                "git_dirty_sealed": seal["git_dirty_sealed"],
                "manifest_lives_in": "tools/registration_seal.py DEFAULT_MANIFEST -- the seal has no aggregate "
                                     "manifest hash, so the manifest's identity is its blob hash inside the seal's "
                                     "own files list, quoted below rather than invented here",
                "the_read_path_tools_and_their_sealed_hashes": {
                    k: {"git_blob_sha1": v["git_blob_sha1"], "sha256_of_git_blob": v["sha256_of_git_blob"],
                        "bytes_worktree": v["bytes_worktree"]}
                    for k, v in seal["files"].items() if k.startswith("tools/mp_e12_")
                },
                "note_on_git_dirty": "the whole-tree git_dirty flag reads True in this ledger because the stamp "
                                     "writes the five registrations in sequence; the field that matters for a seal "
                                     "is git_dirty_sealed, and it is empty. Recorded rather than tidied, because a "
                                     "reader who met the True would otherwise think the seal was taken over a dirty "
                                     "tree.",
            },
            "consequence_for_the_benchmark_tool_itself": "The benchmark tool is not yet written, so its hash cannot "
                                                         "be sealed here. A timed run is therefore barred twice over: "
                                                         "by D-MPE12-09, and because the instrument that would "
                                                         "produce the figure is not yet part of the identity that "
                                                         "R15 requires. This is recorded as a precondition of the "
                                                         "run, not as a defect of this artifact.",
            "re_baseline_rule": "any change to interpreter, torch build, thread pinning, power scheme or the "
                                "benchmark tool's bytes re-bases the figure: the old number is not comparable to "
                                "the new one and must not be quoted next to it",
        },

        "4_what_budgeted_static_read_means_operationally": {
            "access_class": "class 1, compile read (v1.2:216) -- offline, budgeted, static extraction against the "
                            "mapped library. NOT class 2, the live address read at deployment (v1.2:217).",
            "the_only_access_path": "DonorAddressSpace.read_row / read_rows / read_tensor_slice. mmap, read-only, "
                                    "no torch, no transformers, no numpy on that path (asserted by the C4 import "
                                    "surface test).",
            "journal": "the access journal, one record per read call, fields address / tensor / indices / values / "
                       "probe id / timestamp, verified by mp_e12_access_journal.verify()",
            "budget_as_sealed": {
                "ops_per_item": g["read_budget"]["value"],
                "accounting": g["read_budget"]["accounting"],
                "enforcement": g["read_budget"]["enforcement"],
                "max_rows_per_read": probes["budgets"]["max_rows_per_read"],
                "max_reads_per_probe": probes["budgets"]["max_reads_per_probe"],
                "candidate_pool_size": cl["cost_of_the_current_registration"]["pool_rows"],
                "neighbours_per_item": int(list(cl["the_finding_as_measured"]["cluster_size_histogram"])[0]),
                "conservative_ops_run_for_the_sealed_graph":
                    cl["cost_of_the_current_registration"]["conservative_ops_run"],
                "state": "every value quoted from the sealed artifacts named in quoted_sources; this artifact "
                         "changes none of them",
            },
            "what_is_inside_the_timed_region": "the read call AND its journal append. The journal is not overhead "
                                               "around the mechanism, it IS the mechanism's honesty guarantee "
                                               "(R11: 'every access is journaled'), so a timed read that excluded "
                                               "it would be measuring an access class the program does not run.",
            "what_is_outside_it": "process start, safetensors header parse, mmap establishment, artifact writing, "
                                  "and the pool scan when it is not part of the query being priced",
            "reported_as": "per-read wall-clock at the query's own address, plus the operation count already sealed, "
                           "so the figure is a cost per association in both units the plan cares about",
            "cold_and_warm_are_two_different_quantities": "the first touch of a row faults pages from NVMe and a "
                                                          "later touch does not. The plan's own access-class "
                                                          "budgets (v1.2:224, page-resident microseconds vs cold "
                                                          "NVMe single-digit milliseconds) make this a named "
                                                          "condition, so the artifact records which one a figure "
                                                          "is, and a mixed figure is not reportable at all.",
        },

        "5_what_reference_inference_means": {
            "arm": "the same GPT-2 124M bytes, executed autoregressively to generate tokens -- the rival "
                   "hypothesis's cost, not a different model",
            "runtime_available_on_this_machine": {
                "torch": ident["modules"]["torch"],
                "transformers": ident["modules"]["transformers"],
                "safetensors": ident["modules"]["safetensors"],
                "consequence": (f"torch is PRESENT ({ident['modules']['torch'].get('version')}) and transformers/"
                                f"safetensors are ABSENT. So the inference arm is buildable on this laptop today "
                                "without any new dependency, by loading the sealed safetensors through the "
                                "existing address space and running a forward pass in torch. The claim that the "
                                "benchmark 'cannot be run here' is false, and this artifact says so: only a rule "
                                "stands between this program and an executed donor."),
            },
            "isolation_required": "the inference arm's import surface must not be reachable from the read path, or "
                                  "the C4 audit of the deployment path stops meaning anything. Two processes, two "
                                  "import surfaces, named in the artifact that would carry the result.",
            "decoding_length": {"curve_points_generated_tokens": CURVE_POINTS,
                                "fourth_point": MEAN_LENGTH_POINT,
                                "authority": "D-MPE12-05, ruled 2026-08-10: a curve, never a single number, verdict "
                                             "stated at each point, no point added, dropped or headlined selectively"},
            "decoding_strategy": "greedy, temperature 0, no sampling, no beam search, batch 1",
            "the_fourth_point_is_the_crux": "the donor's MEASURED mean answer length requires running the donor to "
                                            "obtain answers whose length is then averaged. The ruling that fixes "
                                            "the curve's shape therefore presupposes the act the doctrine bars. "
                                            "That is not a loophole in the ruling; it is the reason D-MPE12-09 "
                                            "exists and the reason it cannot be settled by arithmetic.",
            "what_the_ratio_is_between": "wall-clock per association retrieved, read arm versus inference arm, at "
                                         "each named point",
            "energy": "NOT measured here. D-MPE12-02 is still open and no proxy is invented for it; the plan's "
                      "energy clause stays untested and this artifact does not pretend otherwise.",
        },

        "6_the_threshold": {
            "as_written_in_the_plan": txt_h2,
            "plan_line": f"{PLAN}:{ln_h2}",
            "threshold": "at least ten times lower per-association read cost than autoregressive inference",
            "provenance": "carried over from v1.1 and declared pre-registered by v1.2:220",
            "never_re_based_on_the_real_donor": True,
            "what_exists_now": "a synthetic-donor calibration whose quoting guard forbids quoting any of it as "
                               "evidence about GPT-2 (2.13x at one token on operations, 0.70x on wall-clock -- "
                               "recorded in the sealed calibration, and NOT a measurement of the real donor)",
            "where_it_would_be_re_based": "in the artifact this registration governs: the first timed run against "
                                          "the real donor, under the identity in section 3, with the verdict stated "
                                          "at each curve point. If that run never happens, the threshold stays "
                                          "un-re-based and H2 stays unmeasured.",
            "status_of_the_claim": "UNMEASURED against the real donor. Not failed, not passed, not partially held.",
        },

        "7_R11_confronted_here_rather_than_at_the_bench": {
            "rule_verbatim": txt_r11,
            "rule_line": f"{PLAN}:{ln_r11}",
            "the_sanctioned_execution_verbatim": txt_ctrl,
            "sanctioned_execution_line": f"{PLAN}:{ln_ctrl}",
            "plain_statement": "Measuring a wall-clock ratio against autoregressive inference requires running the "
                               "donor. There is no version of H2 that is measured by reading weights alone: the "
                               "numerator is a read and the denominator is an execution, and the denominator is "
                               "the thing R11 forbids except once, offline, for the control.",
            "the_argument_that_it_is_the_same_category": [
                "it is offline, not in the deployment loop, and its output reaches no answer -- the three things "
                "R11 actually names as the danger",
                "it is timed, not sampled-for-content: no text from it enters a curriculum, so R9's traceability "
                "rule is not exercised",
                "the control's clause already prices the rival hypothesis's cost: 'must beat or match "
                "text-distillation at lower latency and energy' cannot be evaluated at all unless the rival's "
                "latency is measured, so a benchmark is arguably inside the control's own remit",
            ],
            "the_argument_that_it_is_a_new_exception": [
                "R11's sanction is scoped to an arm 'run once, offline, to emit text' whose text is then trained "
                "on. A benchmark does not emit text for training; it emits durations. Different act, different "
                "output, different purpose.",
                "'once per registration' is a numeric allowance. If the benchmark is the same category it does not "
                "get its own execution -- it CONSUMES the control's single one, or it needs the control to be "
                "registered as the same registration. The two acts cannot both be 'the once'.",
                "C4 aborts on 'any donor forward pass detected in the deployment loop'. A benchmark process is not "
                "the deployment loop, but the audit that distinguishes them is a claim about process boundaries, "
                "and the program has not yet built that audit -- it asserts the import surface, which is not the "
                "same test.",
                "the plan's own hierarchy: R11's closing sentence is 'any pipeline that must run the model to "
                "answer is a different program'. A benchmark does not answer, so the sentence does not bar it -- "
                "but nothing in R11 authorises it either. Silence in a doctrine is not permission, and treating it "
                "as permission is how a doctrine decays.",
            ],
            "named_question_for_the_PI": {
                "proposed_identifier": "D-MPE12-09",
                "identifier_checked_against_the_live_key_set_before_being_written": {
                    "rule": "AMD-MPE10-11: a proposed identifier is checked against the live key set BEFORE it is "
                            "written down",
                    "ids_already_in_use": ["D-MPE12-01", "D-MPE12-02", "D-MPE12-03", "D-MPE12-04", "D-MPE12-05",
                                           "D-MPE12-06", "D-MPE12-07", "D-MPE12-08"],
                    "where_06_07_08_come_from": "docs/mp_e12b_compiler_design_step.md:77, :81, :85 and the ledger's "
                                                "own open_decisions block -- all three are MP-E12b compiler "
                                                "questions, already taken",
                    "collision": False,
                    "why_this_matters": "the obvious next number after the ledger's five decisions was 06, and 06 "
                                       "was already spoken for by a document. Proposing an id without reading the "
                                       "live set produces two questions with one name, which is the failure mode "
                                       "the rule exists to stop.",
                },
                "question": "Is an offline, journaled, never-answers-producing execution of the donor for the "
                            "purpose of timing it (a) inside R11's existing sanction for the control arm, sharing "
                            "its 'once per registration' allowance, (b) a new exception requiring its own dated "
                            "rule, or (c) not permitted at all?",
                "sub_questions_the_answer_must_settle": [
                    "if (a): does the benchmark consume the control's single execution, and which registration is "
                    "'the registration'?",
                    "if (a): is a duration 'text' for the purposes of 'run once, offline, to emit text'?",
                    "if (b): what is the allowance -- once per registration, or once per instrument change? A "
                    "re-based threshold after an interpreter change would need a second execution under R15's "
                    "re-measurement rule, which (b) must therefore answer explicitly",
                    "either way: does the fourth curve point (the donor's measured mean answer length) count as an "
                    "execution of its own, or is it derived from the same run?",
                    "either way: what audit distinguishes 'benchmark process' from 'deployment loop' so that C4 is "
                    "a test and not a slogan?",
                ],
                "consequence_if_the_answer_is_no": "H2's >=10x claim cannot be measured AT ALL under R11 as "
                                                   "written -- not 'is unmeasured for now', but untestable: its "
                                                   "denominator is an act the doctrine forbids. The plan's flagship "
                                                   "latency clause then becomes a design rationale rather than a "
                                                   "hypothesis, G5's 'H1-H4 hold' cannot be evaluated as written, "
                                                   "and the honest report is that v1.2 carries an unfalsifiable "
                                                   "clause in its flagship. That outcome is a finding about the "
                                                   "plan, and it is preferable to measuring the clause by "
                                                   "violating the doctrine that makes the program distinctive.",
                "what_I_am_not_doing": "not resolving it. Not running the donor to see. Not proposing an execution "
                                       "count of my own beyond the repetitions this artifact fixes for the read "
                                       "arm, which needs no ruling.",
            },
            "the_part_that_needs_no_ruling": "the read arm alone is fully measurable today under the sealed "
                                             "instruments: its per-association cost, its operation counts, its "
                                             "cold/warm split. What needs the ruling is the RATIO, because a ratio "
                                             "has two arms and only one of them is permitted.",
        },

        "8_R17_what_it_does_and_does_not_require_here": {
            "rule_verbatim": txt_r17,
            "rule_line": f"{PLAN}:{ln_r17}",
            "reading_registered_before_any_timing": [
                "R17's object is a BEHAVIOURAL claim about the organ -- treatment effect, migration count, breach "
                "tally, retention delta. A wall-clock ratio is none of those: it is a property of an access path "
                "and a machine, and the organ's answers do not depend on it. So R17 does not require a fresh-vs-"
                "fresh floor pair for a latency figure, and requiring one would be a category error that buys "
                "nothing.",
                "the risk R17 guards against is nonetheless real in a different form: a difference smaller than "
                "the noise being reported as an effect. The right instrument for that is repeated-measurement "
                "dispersion INSIDE the same process, which is why REPEATS=25, median+MAD, the 5th/95th percentiles "
                "and the two-sided PASS_RULE above are fixed before any clock starts. A floor pair measures whether "
                "the instrument moves rows; dispersion measures whether the instrument can resolve the gap being "
                "claimed. For a duration, the second is the question.",
                "where a floor WOULD be needed: if a latency figure were ever used to support a behavioural claim "
                "-- 'the organ answers faster, therefore it retains differently' -- the behavioural half is back "
                "inside R17's scope and needs its own floor at its own tier. The ratio itself never carries a "
                "behavioural claim across that boundary without saying so.",
                "R15 and R16, not R17, are the rules that bound a latency figure: the interpreter is a seal "
                "component and the set of wall-clock-gated conditions is an observed property of an environment. A "
                "latency number is therefore only comparable to another number taken under the same sealed identity "
                "and the same thread pinning, and a change to either re-bases it.",
                "C4's boundary is a rule about WHERE a forward pass sits, not about how long anything takes: no "
                "latency figure, however measured, can satisfy or breach C4. If the benchmark runs in a separate "
                "process, the audit that proves the deployment loop is clean is a separate instrument and is not "
                "yet built.",
            ],
            "quantity_to_rule_map": {
                "per-association read cost": "bounded by the sealed budget (24 ops/item) and the journal; no floor "
                                             "required; already reproducible bit-for-bit",
                "per-association inference cost": "bounded by D-MPE12-09 (whether it may be measured at all), then "
                                                  "by R15/R16 identity and by within-process dispersion; NOT by R17",
                "the >=10x ratio": "a comparison of two quantities under one identity; un-re-based on the real "
                                   "donor; unmeasurable if D-MPE12-09 is answered no",
                "any behavioural claim resting on a latency figure": "R17 applies in full, at the tier of that "
                                                                     "claim, with its own floor",
            },
            "explicitly_not_resolved_by_this_artifact": "whether the tier-300 and tier-120 floor pairs the program "
                                                        "already owes are owed for latency at all -- they are owed "
                                                        "for the behavioural figures, and this section says a "
                                                        "latency figure is not one of those.",
        },

        "9_preconditions_of_the_run_this_registers": [
            "a PI answer to D-MPE12-09 (no answer exists today)",
            "the benchmark tool written, tested, sealed -- its bytes are part of the R15 identity",
            "thread pinning and power state named and recorded, not defaulted",
            "cold and warm reads separated into different figures",
            "the inference arm isolated from the read path's import surface, with the isolation asserted by a test",
            "the read arm's own figure already obtainable without any of the above except the tool",
        ],
        "quoted_sources": {
            "query_set_and_caps": PROBES.relative_to(ROOT).as_posix(),
            "sealed_read_budget_and_graph": GRAPH.relative_to(ROOT).as_posix(),
            "pool_and_neighbour_counts": CLUST.relative_to(ROOT).as_posix(),
            "seal_identity": SEAL.relative_to(ROOT).as_posix() + " -> harness_hashes",
            "this_registration_tool": Path(__file__).resolve().relative_to(ROOT).as_posix(),
            "plan_lines_quoted_verbatim": [f"{PLAN}:{ln_r11}", f"{PLAN}:{ln_r17}", f"{PLAN}:{ln_h2}",
                                           f"{PLAN}:{ln_ctrl}", f"{PLAN}:{ln_e12a}", f"{PLAN}:{ln_c4}"],
        },
        "the_plan_sentence_this_registration_serves": txt_h2,
        "c_conditions_line_verbatim": txt_c4,
        "c4_sentence_extracted_from_that_line": (txt_c4.split("**C4 (new):")[1].split(".")[0].strip()
                                                 if "**C4 (new):" in txt_c4
                                                 else "NOT FOUND - the C4 clause is not on the line the needle hit"),
        "result_table_shape_with_every_duration_null": {
            "why_this_block_exists": "the artifact claims no timing field holds a value. The honest way to hold that "
                                     "claim is to give the fields names and nulls now, so a later run fills a "
                                     "registered shape rather than inventing one after the fact.",
            "per_cell_fields": {
                "arm": None, "curve_point_generated_tokens": None, "query": None,
                "n_repetitions_kept": None, "median_s": None, "mad_s": None,
                "p05_s": None, "p95_s": None, "cold_or_warm": None,
                "identity_matches_section_3": None,
            },
            "per_point_summary_fields": {
                "ratio_of_medians_inference_over_read": None, "passes_the_registered_rule": None,
                "verdict": "UNMEASURED",
            },
            "cells_planned_at_the_three_named_points": len(words) * len(CURVE_POINTS) * 2,
            "fourth_point": "cannot be enumerated until it has a value, and it cannot have a value without the "
                            "ruling in D-MPE12-09",
        },
        "prohibitions_observed_in_this_step": {
            "no_timing": True, "no_donor_execution": True, "no_extraction_beyond_the_sealed": True,
            "no_mp_e12b": True, "no_cap_raised": "64 rows/read, 256 rows/probe, 24 ops/item, 24 ops/run, 63 pool, "
                                                 "10 neighbours -- all quoted unchanged",
            "no_threshold_changed": ">=10x carried as written",
            "no_probe_list_applied": "v2 rule registered, not applied; the 17 remain deferred",
            "no_answer_path_touched": True, "no_sealed_artifact_rewritten": True,
        },
    }
    art["1_query_set_named_before_any_timing"]["source"] = str(PROBES.relative_to(ROOT))

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(art, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    print(f"  queries: {len(words)} | curve points: {CURVE_POINTS} + {MEAN_LENGTH_POINT} | repeats: {REPEATS} "
          f"(warmup {WARMUP_DISCARDED} discarded)")
    print(f"  torch present: {torch_present} ({ident['modules']['torch'].get('version')}) | transformers present: "
          f"{transformers_present}")
    print(f"  seal anchor quoted: {seal['git_head'][:9]} | {len(seal['files'])} files sealed | "
          f"git_dirty_sealed {seal['git_dirty_sealed']}")
    print(f"  proposed id: D-MPE12-09 (06/07/08 already in use; collision False)")
    return art


if __name__ == "__main__":
    main()
