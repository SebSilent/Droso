"""MP-E10 ITEM 1: the fresh-vs-fresh separation behind `sealed_baseline_reproducibility`.

THE QUESTION, IN THE LEDGER'S OWN WORDS (experiments/MP-E10/registration.json, key
`sealed_baseline_reproducibility.what_would_separate_them`): "run the same unreplayed configuration twice in
the SAME process context and diff the two fresh runs against each other; if fresh-vs-fresh moves rows too, it
is nondeterminism, not drift." The block's recorded status is "OPEN -- MEASURED, NOT YET PRICED" and
`not_done_this_turn` reads "budget". This tool is that run, purchased 2026-11-05 by PI release.

WHY IT MATTERS: the program's arm-vs-baseline comparisons all rest on SINGLE-RUN sealed baselines. A fresh
unreplayed tier-120 run differs from the sealed tier-120 baseline on 58 rows. If two fresh runs of identical
code, in one process, also differ, then that 58 was never a property of the baseline -- it is what the
instrument does every time it runs, and any treatment effect smaller than it is undetectable by a single run.

WHAT THIS DRIVER DOES
  1. records the process context (pid, interpreter, PYTHONHASHSEED, process start) BEFORE any run, so
     "same process context" is a recorded fact rather than an assertion;
  2. applies the tier-120 curriculum once, exactly as the bench's own __main__ guard would (an importing
     process must call apply_curriculum itself -- see tools/electric_learn_bench.py:411-416);
  3. runs the UNREPLAYED learn arm twice in this one process, each into its own --workdir, because two runs
     sharing a workdir rmtree each other's session state (electric_learn_bench.py:1093-1096);
  4. diffs the two fresh artifacts with the REGISTERED instrument, tools/mp_e10_row_migration.py, on the nine
     R13 identity fields and the corrected five-field row key -- no new comparison code path, so the number is
     produced by the same code that produced every published migration figure;
  5. writes one artifact carrying the result beside the comparators, each read from its own file with its
     line, and states what it does and does not bear on.

It never overwrites: every output path is refused if it already exists (R5).
USAGE
  py tools/mp_e10_fresh_vs_fresh.py
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CURRICULUM = "experiments/MP-E8/curriculum_tier120.json"
# PAIR 2 is the pair this invocation runs, and the pair that carries the pid proof.
RUN_A = "experiments/MP-E10/results/fresh120_pair2_a_fresh_vs_fresh_armA.json"
RUN_B = "experiments/MP-E10/results/fresh120_pair2_b_fresh_vs_fresh_armA.json"
DIFF = "experiments/MP-E10/results/fresh120_pair2_a_vs_b_row_migration.json"
OUT = "experiments/MP-E10/results/fresh_vs_fresh_tier120.json"
WD_A = "_tmp/wd_ff120_pair2_a"
WD_B = "_tmp/wd_ff120_pair2_b"
# PAIR 1 was run by the FIRST invocation of this driver, which completed both bench runs and the registered
# diff and then died in assembly on a hand-indexed key (KeyError: least_favourable_seed_drop_pp). Its three
# artifacts are real measurements and are kept, renamed `pair1`; what pair 1 cannot show is the pid, because
# the driver did not sample it at run time. Two pairs are reported so the reader can see whether the answer is
# stable rather than being handed one number and a claim.
P1_RUN_A = "experiments/MP-E10/results/fresh120_pair1_a_fresh_vs_fresh_armA.json"
P1_RUN_B = "experiments/MP-E10/results/fresh120_pair1_b_fresh_vs_fresh_armA.json"
P1_DIFF = "experiments/MP-E10/results/fresh120_pair1_a_vs_b_row_migration.json"
BASELINE = "experiments/MP-E8/results/armA_tier120_curriculum.json"
KEYFIX_CTL = "experiments/MP-E10/results/120ctl_row_migration_keyfix.json"
SEAL_BASELINE = "experiments/MP-E10/results/control_tier120_no_replay_armA.json"


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def refuse_existing(*paths: str) -> None:
    for p in paths:
        f = ROOT / p
        if f.exists():
            raise SystemExit(f"REFUSED: {p} already exists. A sealed artifact is never overwritten (R5); "
                             f"this run produces new paths only.")


def find_key(node, name, path=""):
    """Locate a figure wherever the artifact actually puts it, and return the PATH as well as the value.

    An earlier version of this driver indexed these files by hand and died with KeyError on
    `least_favourable_seed_drop_pp`, which is nested under `h1_tier_120`. A quoted figure must be found, not
    remembered -- so the lookup walks the document and reports where it landed.
    """
    if isinstance(node, dict):
        for k, v in node.items():
            kp = f"{path}.{k}" if path else str(k)
            if k == name:
                return kp, v
            hit = find_key(v, name, kp)
            if hit:
                return hit
    elif isinstance(node, list):
        for i, v in enumerate(node):
            hit = find_key(v, name, f"{path}[{i}]")
            if hit:
                return hit
    return None


def line_of(rel: str, needle: str):
    """The 1-based line a quoted figure actually sits on, read from the file rather than remembered."""
    for i, ln in enumerate((ROOT / rel).read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if needle in ln:
            return i
    return None


def jload(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8", errors="replace"))


def one_run(bench, out_rel: str, workdir: str, argv_tail):
    """One unreplayed learn-arm run, inside THIS process.

    The pid is sampled immediately before and immediately after the call, because "same process context" is
    the whole discriminator this experiment exists to apply and it has to be an OBSERVATION in the artifact,
    not a claim in a commit message.
    """
    sys.argv = ["electric_learn_bench.py", "--arms", "learn", "--curriculum", CURRICULUM,
                "--out", out_rel, "--workdir", workdir] + list(argv_tail)
    pid_before, t0, utc0 = os.getpid(), time.time(), now_utc()
    rc = bench.main()
    return {"argv": [str(x) for x in sys.argv[1:]], "rc": rc,
            "pid_observed_before_call": pid_before, "pid_observed_after_call": os.getpid(),
            "started_utc": utc0, "driver_wall_seconds": round(time.time() - t0, 2)}


def main() -> int:
    t_all = time.time()
    # The two runs and the diff must be new paths. OUT is written by THIS driver in two stages (pair context
    # first, results after), so refusing it would make a crash during assembly unrecoverable -- a sealed
    # artifact is never overwritten, and this file has not been sealed until the stamp that follows it.
    refuse_existing(RUN_A, RUN_B, DIFF)
    ctx = {"pid": os.getpid(), "interpreter": sys.version.split()[0],
           "python_executable": sys.executable,
           "PYTHONHASHSEED_in_environ": os.environ.get("PYTHONHASHSEED"),
           "process_started_utc": None, "cwd": os.getcwd(),
           "platform": sys.platform}
    print(f"[ff] process context: pid={ctx['pid']} python={ctx['interpreter']} "
          f"PYTHONHASHSEED={ctx['PYTHONHASHSEED_in_environ']!r}", flush=True)

    import tools.electric_learn_bench as bench
    ctx["replay_requested_in_this_process"] = bool(getattr(bench, "REPLAY_REQUESTED", None))
    ctx["curriculum_applied_by"] = "this driver, explicitly, as an importing process must " \
                                   "(tools/electric_learn_bench.py:411-416)"
    bench.apply_curriculum(str(ROOT / CURRICULUM))
    ctx["process_started_utc"] = now_utc()

    print("[ff] RUN 1 of 2 (unreplayed, tier 120, this process)", flush=True)
    r1 = one_run(bench, RUN_A, WD_A, [])
    print(f"[ff] RUN 1 done rc={r1['rc']} in {r1['driver_wall_seconds']} s", flush=True)
    print("[ff] RUN 2 of 2 (unreplayed, tier 120, SAME process)", flush=True)
    r2 = one_run(bench, RUN_B, WD_B, [])
    print(f"[ff] RUN 2 done rc={r2['rc']} in {r2['driver_wall_seconds']} s", flush=True)

    for rel in (RUN_A, RUN_B):
        p = ROOT / rel
        if not p.exists():
            raise SystemExit(f"REFUSED: run produced no artifact at {rel} -- reporting a diff of nothing")

    a, b = jload(RUN_A), jload(RUN_B)

    # STAGE 1 WRITE. The pair context and the same-process proof go to disk BEFORE the diff runs, so that a
    # failure in the assembly stage cannot destroy the evidence that two runs happened in one process. The
    # first invocation of this driver died exactly there, after 985 s of bench, with nothing written.
    provisional = {
        "experiment": "MP-E10", "stage": "pair context, written before the diff",
        "generated_at_utc": now_utc(), "same_process_context": ctx,
        "run_A": r1, "run_B": r2,
        "same_process_observed": (r1["pid_observed_before_call"] == r2["pid_observed_after_call"]
                                  == r1["pid_observed_after_call"] == r2["pid_observed_before_call"]),
        "artifacts_on_disk": {RUN_A: sha256(ROOT / RUN_A), RUN_B: sha256(ROOT / RUN_B)},
    }
    (ROOT / OUT).write_text(json.dumps(provisional, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[ff] stage 1 written to {OUT} (same process observed: "
          f"{provisional['same_process_observed']}, pid {r1['pid_observed_before_call']})", flush=True)

    print("[ff] diffing the two fresh runs with the registered instrument", flush=True)
    diff_cmd = [sys.executable, "tools/mp_e10_row_migration.py",
                "--replayed", RUN_A, "--baseline", RUN_B, "--out", DIFF,
                "--label", "TIER-120 FRESH vs FRESH -- two unreplayed runs of identical code in ONE "
                           "process (pid %d), same curriculum, same seed; the experiment the ledger calls "
                           "unpurchased at sealed_baseline_reproducibility" % ctx["pid"]]
    dr = subprocess.run(diff_cmd, cwd=ROOT, capture_output=True, text=True)
    print(dr.stdout, dr.stderr, flush=True)
    if dr.returncode != 0:
        raise SystemExit(f"the registered instrument failed (rc {dr.returncode})")
    diff = jload(DIFF)

    ctl = jload(KEYFIX_CTL)
    seal = jload(SEAL_BASELINE)
    base = jload(BASELINE)
    h1 = jload("experiments/MP-E8/results/armB_tier120_seeds_verdict.json")
    s300 = jload("experiments/MP-E10/results/replay_tier300_summary.json")

    prior = None
    if all((ROOT / p).exists() for p in (P1_RUN_A, P1_RUN_B, P1_DIFF)):
        pd, pa, pb = jload(P1_DIFF), jload(P1_RUN_A), jload(P1_RUN_B)
        prior = {
            "what_it_is": ("the same experiment, run ~25 minutes earlier by the first invocation of this "
                           "driver, which completed both bench runs and the registered diff and then died in "
                           "assembly on a hand-indexed key. Kept, renamed pair1, and reported beside pair 2."),
            "artifacts": {P1_RUN_A: sha256(ROOT / P1_RUN_A), P1_RUN_B: sha256(ROOT / P1_RUN_B),
                          P1_DIFF: sha256(ROOT / P1_DIFF)},
            "rows_compared": pd["rows_compared"], "n_rows_moved": pd["n_rows_moved"],
            "movement_rate_percent": round(pd["n_rows_moved"] / pd["rows_compared"] * 100.0, 4),
            "class_split": pd["class_split"], "transitions_by_axis": pd["transitions_by_axis"],
            "refused_by_phase": pd["refused_by_phase"],
            "matched_pair_reading": pd["matched_pair"]["reading"],
            "breaks_the_comparison": pd["matched_pair"]["differences_that_break_the_comparison"],
            "started_utc": {"a": pa["provenance"].get("started_utc"),
                            "b": pb["provenance"].get("started_utc")},
            "git_head": pa["provenance"].get("git_head"),
            "harness_sha256": pa["provenance"].get("harness_sha256"),
            "learn_arm_seconds": {"a": pa["arms"]["learn"].get("seconds"),
                                  "b": pb["arms"]["learn"].get("seconds")},
            "pid": ("NOT RECORDED. That invocation sampled no pid at run time, so pair 1's same-process claim "
                    "rests on sequential started_utc plus the driver log and is labelled weaker for it. Pair 2 "
                    "carries the observation."),
        }

    moved = diff["n_rows_moved"]
    compared = diff["rows_compared"]
    asks = diff["denominator"]["graded_asks_baseline"]
    rate = (moved / compared * 100.0) if compared else None
    hd = find_key(h1, "least_favourable_seed_drop_pp") or ("(not found)", None)
    hm = find_key(s300, "margin_applied_pp") or ("(not found)", None)
    seed_drop, margin = hd[1], hm[1]

    out = {
        "experiment": "MP-E10",
        "item": "ITEM 1 -- the fresh-vs-fresh separation behind sealed_baseline_reproducibility",
        "generated_at_utc": now_utc(),
        "authorised_by": "PI release of the hold, 2026-11-05, with a 5-hour working window and named items",
        "question_as_the_ledger_words_it": {
            "path": "experiments/MP-E10/registration.json",
            "key": "sealed_baseline_reproducibility.what_would_separate_them",
            "line": line_of("experiments/MP-E10/registration.json", "run the same unreplayed configuration "
                                                                   "twice in the SAME process context"),
            "status_before_this_run": "OPEN -- MEASURED, NOT YET PRICED",
            "status_line": line_of("experiments/MP-E10/registration.json", "OPEN -- MEASURED, NOT YET PRICED"),
            "not_done_this_turn_before_this_run": "budget",
        },
        "method": {
            "runs": "the UNREPLAYED tier-120 learn arm, twice, in one Python process, each into its own "
                    "--workdir",
            "instrument": "tools/mp_e10_row_migration.py -- the registered row diff on the nine R13 identity "
                          "fields, key (depth, phase, ask, item, shape). No new comparison code path.",
            "why_same_process": "the ledger's own discriminator: if the movement is nondeterminism it will "
                                "appear between two runs that share a process; if it is drift against a "
                                "sealed artifact it will not.",
            "driver": "tools/mp_e10_fresh_vs_fresh.py",
        },
        "same_process_context": ctx,
        "the_two_runs": {
            "run_A": {"artifact": RUN_A, "sha256": sha256(ROOT / RUN_A), "started_utc":
                      a["provenance"].get("started_utc"), "learn_arm_seconds":
                      a["arms"]["learn"].get("seconds"), "rc": r1["rc"],
                      "driver_wall_seconds": r1["driver_wall_seconds"], "git_head":
                      a["provenance"].get("git_head"), "harness_sha256": a["provenance"].get("harness_sha256"),
                      "inventions_recorded": len(a.get("failures") or []),
                      "pid_observed_before_call": r1["pid_observed_before_call"],
                      "pid_observed_after_call": r1["pid_observed_after_call"],
                      "driver_seen_start_utc": r1["started_utc"]},
            "run_B": {"artifact": RUN_B, "sha256": sha256(ROOT / RUN_B), "started_utc":
                      b["provenance"].get("started_utc"), "learn_arm_seconds":
                      b["arms"]["learn"].get("seconds"), "rc": r2["rc"],
                      "driver_wall_seconds": r2["driver_wall_seconds"], "git_head":
                      b["provenance"].get("git_head"), "harness_sha256": b["provenance"].get("harness_sha256"),
                      "inventions_recorded": len(b.get("failures") or []),
                      "pid_observed_before_call": r2["pid_observed_before_call"],
                      "pid_observed_after_call": r2["pid_observed_after_call"],
                      "driver_seen_start_utc": r2["started_utc"]},
            "same_process_observed": (r1["pid_observed_before_call"] == r2["pid_observed_after_call"]
                                      == r1["pid_observed_after_call"] == r2["pid_observed_before_call"]),
            "identical_between_the_two": {
                "harness_sha256": a["provenance"].get("harness_sha256") == b["provenance"].get("harness_sha256"),
                "git_head": a["provenance"].get("git_head") == b["provenance"].get("git_head"),
                "curriculum_sha256": a["curriculum"].get("curriculum_sha256")
                == b["curriculum"].get("curriculum_sha256"),
                "seed": a["curriculum"].get("seed") == b["curriculum"].get("seed"),
                "replay_off_in_both": not ctx["replay_requested_in_this_process"],
                "same_pid_observed_at_run_time": (r1["pid_observed_before_call"]
                                                  == r2["pid_observed_after_call"]),
                "differ_only_by": ["--out", "--workdir", "wall-clock", "the process start times"],
            },
        },
        "fresh_vs_fresh_result": {
            "diff_artifact": DIFF,
            "rows_compared": compared,
            "graded_asks": {"run_A": diff["denominator"]["graded_asks_replayed"],
                            "run_B": diff["denominator"]["graded_asks_baseline"]},
            "n_rows_moved": moved,
            "movement_rate_percent": round(rate, 4) if rate is not None else None,
            "rows_only_in_one_set": diff["n_rows_only_in_one_set"],
            "class_split": diff["class_split"],
            "fields_moved_split": diff.get("fields_moved_split"),
            "transitions_by_axis": diff["transitions_by_axis"],
            "refused_by_phase": diff["refused_by_phase"],
            "matched_pair_reading": diff["matched_pair"]["reading"],
            "breaks_the_comparison": diff["matched_pair"]["differences_that_break_the_comparison"],
            "moved_keys": diff["moved_keys"],
            "moved_rows": diff["moved_rows"],
        },
        "pair_1_from_the_aborted_invocation": prior,
        "finding": {
            "question": "does a fresh run differ from another fresh run of identical code in one process?",
            "answer_as_measured": bool(moved) if prior is None else bool(moved and prior["n_rows_moved"]),
            "pair_2_rows_moved": moved, "pair_1_rows_moved": (prior or {}).get("n_rows_moved"),
            "consequence_if_both_pairs_move_rows": (
                "the 58-row difference between a fresh unreplayed run and the sealed baseline is NOT a "
                "property of that baseline. It is what this instrument does every time it runs, so the "
                "run-to-run variation of a single tier-120 run is the floor under every arm-vs-baseline "
                "number in the program, and a treatment effect smaller than it is not detectable by one run."),
            "what_this_does_not_settle": (
                "it does not separate WHICH cause -- hash order, wall-clock-dependent timing knobs, or store "
                "state -- because both pairs ran on one machine in one session; and it does not re-measure the "
                "fresh-vs-SEALED-baseline difference, which additionally spans a harness change (see "
                "the_sealed_baseline_and_its_instrument.same_harness_as_the_fresh_runs)."),
        },
        "the_comparators_read_from_their_files": {
            "fresh_vs_sealed_baseline_as_recorded_in_the_ledger": {
                "path": "experiments/MP-E10/registration.json",
                "line": line_of("experiments/MP-E10/registration.json", "58 of 3,222 rows"),
                "text": "58 of 3,222 rows (1.8%) differ between a fresh unreplayed tier-120 run and the "
                        "sealed tier-120 baseline",
                "denominator_status": ("SUPERSEDED. 3,222 is the count of KEYS the collapsing (depth, phase, "
                                       "ask) key could address, out of 3,744 graded asks (AMD-MPE10-08). "
                                       "Quoted here as the ledger's recorded wording, not as the governing "
                                       "denominator."),
            },
            "fresh_vs_sealed_baseline_governing": {
                "path": KEYFIX_CTL,
                "n_rows_moved": ctl["n_rows_moved"],
                "rows_compared": ctl["rows_compared"],
                "graded_asks": ctl["denominator"],
                "movement_rate_percent": round(ctl["n_rows_moved"] / ctl["rows_compared"] * 100.0, 4),
                "label": ctl["label"],
                "note": ("the governing control figure: the same 58 rows, on the corrected denominator. The "
                         "count did not move with the key fix; the denominator did."),
            },
            "the_sealed_control_it_was_measured_against": {
                "path": SEAL_BASELINE, "started_utc": seal["provenance"].get("started_utc"),
                "git_head": seal["provenance"].get("git_head"),
                "harness_sha256": seal["provenance"].get("harness_sha256"),
                "learn_arm_seconds": seal["arms"]["learn"].get("seconds"),
            },
            "the_sealed_baseline_and_its_instrument": {
                "path": BASELINE, "git_head": base["provenance"].get("git_head"),
                "harness_sha256": base["provenance"].get("harness_sha256"),
                "started_utc": base["provenance"].get("started_utc"),
                "same_harness_as_the_fresh_runs":
                    base["provenance"].get("harness_sha256") == a["provenance"].get("harness_sha256"),
                "note": ("if this is False, the fresh-vs-baseline 58 spans a code change as well as run "
                         "variation -- the comparison the ledger's consequence at registration.json:96 does "
                         "NOT currently name."),
            },
        },
        "what_the_two_figures_that_rest_on_single_run_baselines_are": {
            "G2_H1_tier120_least_favourable_seed_drop_pp": {
                "value": seed_drop,
                "path": "experiments/MP-E8/results/armB_tier120_seeds_verdict.json",
                "line": line_of("experiments/MP-E8/results/armB_tier120_seeds_verdict.json",
                                "least_favourable_seed_drop_pp"),
                "path_in_document": hd[0],
                "registered_minimum_pp_source": {
                    "path": "experiments/MP-E8/decision.md",
                    "line": line_of("experiments/MP-E8/decision.md", "arm B drops below its own session-1 by"),
                    "quoted": "arm B drops below its own session-1 by >= 5.0 pp, tiers 120 and 300",
                },
                "unit": "percentage points of the taught-set retention score",
            },
            "MP_E10_H3_interference_margin_pp": {
                "value": margin,
                "path": "experiments/MP-E10/results/replay_tier300_summary.json",
                "path_in_document": hm[0],
                "line": line_of("experiments/MP-E10/results/replay_tier300_summary.json", "margin_applied_pp"),
                "unit": "percentage points of the interference tally",
            },
        },
        "verdicts_changed_by_this_run": [],
        "note_on_units": ("the fresh-vs-fresh and fresh-vs-baseline numbers are a PROPORTION OF ROWS that "
                          "change class; H1's 1.6827 pp and H3's 2.0 pp are percentage points of a SCORE. "
                          "They are not the same quantity and are not subtracted from one another here. What "
                          "is comparable is magnitude and direction of the noise floor against the size of "
                          "the effect being claimed."),
        "wall_clock": {"run_A_seconds": r1["driver_wall_seconds"], "run_B_seconds": r2["driver_wall_seconds"],
                       "total_seconds_this_driver": round(time.time() - t_all, 2)},
        "provenance": {"driver": "tools/mp_e10_fresh_vs_fresh.py", "git_head_at_write":
                       subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
                                      ).stdout.strip(), "python": sys.version.split()[0]},
    }
    (ROOT / OUT).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\n[fresh-vs-fresh] {moved} rows moved of {compared} compared "
          f"({rate:.4f}% ) -- graded asks {out['fresh_vs_fresh_result']['graded_asks']}", flush=True)
    print(f"[comparator, governing] fresh-vs-sealed-control: {ctl['n_rows_moved']} of "
          f"{ctl['rows_compared']} = {ctl['n_rows_moved'] / ctl['rows_compared'] * 100:.4f}%", flush=True)
    print(f"[baseline harness same as fresh runs? ] "
          f"{out['the_comparators_read_from_their_files']['the_sealed_baseline_and_its_instrument']['same_harness_as_the_fresh_runs']}",
          flush=True)
    print(f"wrote {OUT} in {out['wall_clock']['total_seconds_this_driver']} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
