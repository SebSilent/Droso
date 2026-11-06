"""STEP 5 -- the scored tier-120 replay run, as re-registered by B.R item 1 (D-MPE10-12, Amendment D).

WHAT IS SCORED HERE, AND AGAINST WHAT
    H3's primary tier is 120 (v1.2:200). Two runs execute in this one process on the current instrument bytes:
    the replay configuration (--replay) and its own unreplayed control. They are diffed by the registered
    instrument on the nine R13 identity fields, and the difference is read against the tier-120 floor measured
    on the SAME bytes -- not against a floor from another byte-set. Tier 300 is not run here: under C6 a
    tier-300 saturation event makes such a run a capacity datum, and B.R item 1 says tier 300 is reported as
    the saturation curve and never as an interference measurement.

THINGS THIS DRIVER REFUSES TO DO
  *  score anything before the preflight lands. Stage 1 writes the quoted ledger lines for the configuration,
     the phase basis and the gain to disk BEFORE the first bench minute, and refuses if any citation fails to
     resolve or the floor artifact is absent. A prior attempt lost 985 s of completed bench to an assembly
     crash that left nothing written; incremental writes are the answer to that, not a convenience.
  *  restate the registered numbers. It quotes the lines it read and refuses to paraphrase them.
  *  invent a metric. Mouth stages come from heldout_eval.stage_of, content words from
     word_provenance.content_words, row diffs from mp_e10_row_migration -- all registered code.
  *  substitute a near neighbour for a missing precondition. Where an emission needs an instrument this run
     cannot reach, the artifact says what is missing and what would be needed, in the same file as the numbers
     it could produce.
  *  overwrite. Every output path is refused if it already exists.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

TIER = 120
CURRICULUM = "experiments/MP-E8/curriculum_tier120.json"
REG = "experiments/MP-E10/registration.json"
RESULTS = ROOT / "experiments/MP-E10/results"
OUT = RESULTS / "step5_scored_tier120.json"
RUN_REPLAY = "experiments/MP-E10/results/step5_tier120_replay_armA.json"
RUN_CONTROL = "experiments/MP-E10/results/step5_tier120_control_armA.json"
DIFF_RC = "experiments/MP-E10/results/step5_tier120_replay_vs_control_row_migration.json"
BASELINE_MPE8 = "experiments/MP-E8/results/armA_tier120_curriculum.json"
WD_R, WD_C = "_tmp/wd_step5_replay", "_tmp/wd_step5_control"


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm(s: str) -> str:
    return " ".join(str(s).split())


def quote(rel: str, needle: str, why: str) -> dict:
    """Resolve a citation against the file AS IT IS NOW. A needle that does not resolve stops the run."""
    ls = (ROOT / rel).read_text(encoding="utf-8", errors="replace").splitlines()
    hits = [i for i, l in enumerate(ls, 1) if norm(needle) in norm(l)]
    if len(hits) != 1:
        raise SystemExit(f"PREFLIGHT REFUSED: {rel} holds {len(hits)} lines matching {needle[:70]!r} "
                         f"(needed exactly 1) -- cannot quote the registered {why}")
    return {"pointer": f"{rel}:{hits[0]}", "line_reads": ls[hits[0] - 1].strip(), "it_is": why}


def save(artifact: dict) -> None:
    """Write the artifact after every stage, so a later crash cannot erase an earlier proof."""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(OUT)


def stage(name: str, artifact: dict, payload) -> None:
    artifact[name] = payload
    artifact[f"{name}_at_utc"] = now_utc()
    save(artifact)
    print(f"[step5] {name} written", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--floor", required=True,
                    help="the pair artifact that registers the tier-120 floor on these bytes")
    a = ap.parse_args()

    for rel in (RUN_REPLAY, RUN_CONTROL, DIFF_RC):
        if (ROOT / rel).exists():
            raise SystemExit(f"REFUSED: {rel} already exists -- this driver never overwrites")
    if OUT.exists():
        raise SystemExit(f"REFUSED: {OUT.name} exists. Delete it only if you intend to re-run STEP 5.")

    floor_path = ROOT / a.floor
    if not floor_path.exists():
        raise SystemExit(f"PREFLIGHT REFUSED: no floor artifact at {a.floor}. STEP 5 does not run without a "
                         f"tier-120 floor measured on the bytes it is about to execute on.")
    fl = json.loads(floor_path.read_text(encoding="utf-8"))

    # ---- STAGE 1: the preflight, on disk before the first scored minute -------------------------------
    bench_sha = fl["the_two_runs"]["run_A"]["harness_sha256"]
    import hashlib
    now_sha = hashlib.sha256((ROOT / "tools/electric_learn_bench.py").read_bytes()).hexdigest()
    if now_sha != bench_sha:
        raise SystemExit(f"PREFLIGHT REFUSED: the floor was measured on harness {bench_sha[:12]} but the bench "
                         f"now hashes {now_sha[:12]}. R17 measures a floor per byte-set; this floor does not "
                         f"bound this run.")

    preflight = {
        "recorded_at_utc": now_utc(),
        "before_the_first_scored_minute": True,
        "what_this_confirms": ("the configuration, the phase basis and the gain are the registered ones, quoted "
                               "from the ledger rather than restated, and the floor is the one measured on the "
                               "bytes this run executes on"),
        "registered_configuration": {
            "replay_gain": quote(REG, '"replay_gain": 0.35,', "the registered gain"),
            "replay_passes_per_tier": quote(REG, '"replay_passes_per_tier": 2,', "the registered passes"),
            "ceiling": quote(REG, '"ceiling": 4.0,', "the registered ceiling"),
            "h3_primary_tier": quote(REG, '"h3_primary_tier": 120,', "H3's primary tier"),
            "margin_pp": quote(REG, '"value_pp": 2.0', "the pre-registered interference margin"),
            "phase_basis_primary": quote(REG, '"primary": "reasked",', "the H3 phase basis"),
            "tier_300_role": quote(REG, '"tier_300_role"', "what tier 300 may be reported as"),
            "gain_registered_where_non_saturating": quote(REG, '"where_it_is_non_saturating"',
                                                          "where this gain does not saturate"),
        },
        "the_floor_it_scores_against": {
            "artifact": a.floor,
            "n_rows_moved": quote(a.floor, '"n_rows_moved":', "the floor's row count"),
            "movement_rate_percent": quote(a.floor, '"movement_rate_percent":', "the floor's rate"),
            "graded_asks": quote(a.floor, '"graded_asks_replayed": 3744', "the denominator"),
            "harness_sha256_it_bounds": bench_sha,
            "same_process_observed": quote(a.floor, '"same_pid_observed_at_run_time": true',
                                           "the floor's own same-process proof"),
        },
        "measured_unit_costs_it_is_judged_by": {
            "pre_A10_pair_seconds": [quote(REG, '"tier120_pair_run_A_seconds": 480.91', "pre-A10 run A"),
                                     quote(REG, '"tier120_pair_run_B_seconds": 462.37', "pre-A10 run B")],
        },
        "instrument_bytes_at_preflight": now_sha,
    }
    artifact: dict = {"experiment": "MP-E10", "step": "STEP 5 scored tier-120 replay run",
                      "preflight": preflight, "preflight_at_utc": now_utc(), "generated_at_utc": now_utc()}
    save(artifact)
    print("[step5] PREFLIGHT on disk; bench bytes match the floor's bytes", flush=True)

    # ---- STAGE 2 and 3: the two runs, in this process --------------------------------------------------
    import mp_e10_resource_ledger          # noqa: F401  -- prove the sampler is reachable BEFORE any run
    import tools.electric_learn_bench as bench
    bench.apply_curriculum(str(ROOT / CURRICULUM))
    ctx = {"pid": os.getpid(), "interpreter": sys.version.split()[0], "cwd": os.getcwd(),
           "a10_sampler_module": mp_e10_resource_ledger.__file__}
    print(f"[step5] process context pid={ctx['pid']}", flush=True)

    def one(out_rel: str, workdir: str, replay: bool):
        argv = ["electric_learn_bench.py", "--arms", "learn", "--curriculum", CURRICULUM,
                "--out", out_rel, "--workdir", workdir]
        if replay:
            argv.append("--replay")
        sys.argv = argv
        pid0, t0 = os.getpid(), time.time()
        rc = bench.main()
        return {"argv": argv[1:], "rc": rc, "replay": replay, "pid_before": pid0, "pid_after": os.getpid(),
                "wall_seconds": round(time.time() - t0, 2), "started_utc": now_utc()}

    print("[step5] RUN 1/2 -- replay ON, tier 120", flush=True)
    r_rep = one(RUN_REPLAY, WD_R, True)
    print(f"[step5] replay run rc={r_rep['rc']} in {r_rep['wall_seconds']} s", flush=True)
    stage("run_replay", artifact, r_rep)

    print("[step5] RUN 2/2 -- control, SAME process", flush=True)
    r_ctl = one(RUN_CONTROL, WD_C, False)
    print(f"[step5] control run rc={r_ctl['rc']} in {r_ctl['wall_seconds']} s", flush=True)
    artifact["run_control"] = r_ctl
    artifact["same_process_proof"] = {
        "samples": [r_rep["pid_before"], r_rep["pid_after"], r_ctl["pid_before"], r_ctl["pid_after"]],
        "all_agree": len({r_rep["pid_before"], r_rep["pid_after"], r_ctl["pid_before"], r_ctl["pid_after"]}) == 1,
        "statement": ("four pid samples taken around both runs. If they do not agree the pair cannot prove "
                      "same-process and this run does not score."),
    }
    stage("same_process_proof", artifact, artifact["same_process_proof"])
    if not artifact["same_process_proof"]["all_agree"]:
        raise SystemExit("REFUSED: the two runs did not execute in one process; STEP 5 does not score")

    # ---- STAGE 4: the registered diff ------------------------------------------------------------------
    cmd = [sys.executable, "-B", "-X", "utf8", str(ROOT / "tools/mp_e10_row_migration.py"),
           "--replayed", RUN_REPLAY, "--baseline", RUN_CONTROL, "--out", DIFF_RC,
           "--row-key", "probe",
           "--label", "STEP 5 -- replay vs its own unreplayed control, tier 120, one process, current bytes"]
    subprocess.run(cmd, check=True, cwd=str(ROOT))
    diff = json.loads((ROOT / DIFF_RC).read_text(encoding="utf-8"))
    stage("row_migration_replay_vs_control", artifact, {
        "artifact": DIFF_RC,
        "n_rows_moved": diff["n_rows_moved"],
        "rows_compared": diff["rows_compared"],
        "denominator": diff["denominator"],
        "class_split": diff["class_split"],
        "fields_moved_split": diff["fields_moved_split"],
        "transitions_by_axis": diff["transitions_by_axis"],
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
