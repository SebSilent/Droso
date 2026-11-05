"""STEP 4 -- the tier-300 fresh-vs-fresh floor pair, required by R17 (v1.2:147) before any tier-300
behavioural attribution.

What it buys: two unreplayed learn-only runs at tier 300, identical code, identical curriculum, identical
seed, inside ONE process, diffed by the registered instrument (tools/mp_e10_row_migration.py, nine R13
fields). That is the identical-code floor at the tier where every published tier-300 figure was produced, and
until it exists the 111-row replay-vs-control difference, the 251/302 migration counts and the 91/92/100
invention-breach tallies are unattributable.

Three things this driver refuses to do:
  * overwrite anything. Every output path is refused if it already exists, except the summary, which this
    driver itself writes in two stages -- stage 1 (pair context + same-process proof) lands on disk BEFORE
    the diff runs, because the tier-120 attempt lost 985 s of completed bench to an assembly crash that left
    nothing written (tools/mp_e10_fresh_vs_fresh.py records it as pair 1).
  * assert same-process. The pid is sampled before run A and after run B and written as an observation. If
    the four samples do not agree, the artifact says the pair cannot prove same-process rather than claiming
    it anyway.
  * claim a floor transfer across instrument bytes. The run's own harness_sha256 is read back from the
    artifact and compared with the bytes the sealed figures were made on; if they differ, the summary says so.

Run:  .venv/Scripts/python.exe tools/mp_e10_floor_tier300.py
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# This file is launched as `python tools/mp_e10_floor_tier300.py`, which puts tools/ (not the repo root) on
# sys.path -- the first launch died on `import tools.electric_learn_bench` after 37 s with nothing produced.
# The root goes on the path explicitly so the bench is imported the way every other driver imports it.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CURRICULUM = "experiments/MP-E8/curriculum_tier300.json"
RUN_A = "experiments/MP-E10/results/floor300_a_fresh_vs_fresh_armA.json"
RUN_B = "experiments/MP-E10/results/floor300_b_fresh_vs_fresh_armA.json"
DIFF = "experiments/MP-E10/results/floor300_a_vs_b_row_migration.json"
OUT = "experiments/MP-E10/results/floor_tier300.json"
WD_A, WD_B = "_tmp/wd_floor300_a", "_tmp/wd_floor300_b"
SEALED_FIGURES_HARNESS = "5cf038c211d6f0cfed19aead1b9e7419d07e8a0a1e7e4a5577ef314fca83059e"


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def jload(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8", errors="replace"))


def line_of(rel: str, needle: str):
    for i, ln in enumerate((ROOT / rel).read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if needle in ln:
            return i
    return None


def refuse_existing(*rels: str) -> None:
    for rel in rels:
        if (ROOT / rel).exists():
            raise SystemExit(f"REFUSED: {rel} already exists -- a sealed artifact is never overwritten")


def one_run(bench, out_rel: str, workdir: str):
    sys.argv = ["electric_learn_bench.py", "--arms", "learn", "--curriculum", CURRICULUM,
                "--out", out_rel, "--workdir", workdir]
    pid_before, t0, utc0 = os.getpid(), time.time(), now_utc()
    rc = bench.main()
    return {"argv": [str(x) for x in sys.argv[1:]], "rc": rc,
            "pid_observed_before_call": pid_before, "pid_observed_after_call": os.getpid(),
            "started_utc": utc0, "driver_wall_seconds": round(time.time() - t0, 2)}


def main() -> int:
    t_all = time.time()
    refuse_existing(RUN_A, RUN_B, DIFF)
    print(f"[floor300] process pid={os.getpid()} python={sys.version.split()[0]} "
          f"PYTHONHASHSEED={os.environ.get('PYTHONHASHSEED')!r}", flush=True)

    import tools.electric_learn_bench as bench
    if getattr(bench, "REPLAY_REQUESTED", None):
        raise SystemExit("REFUSED: replay is ON in this process; a floor pair must have no treatment difference")
    bench.apply_curriculum(str(ROOT / CURRICULUM))

    print("[floor300] RUN 1 of 2 (tier 300, learn-only, unreplayed)", flush=True)
    r1 = one_run(bench, RUN_A, WD_A)
    print(f"[floor300] RUN 1 rc={r1['rc']} in {r1['driver_wall_seconds']} s", flush=True)
    print("[floor300] RUN 2 of 2 (SAME process)", flush=True)
    r2 = one_run(bench, RUN_B, WD_B)
    print(f"[floor300] RUN 2 rc={r2['rc']} in {r2['driver_wall_seconds']} s", flush=True)

    for rel in (RUN_A, RUN_B):
        if not (ROOT / rel).exists():
            raise SystemExit(f"REFUSED: no artifact at {rel}")

    a, b = jload(RUN_A), jload(RUN_B)
    same_proc = (r1["pid_observed_before_call"] == r1["pid_observed_after_call"]
                 == r2["pid_observed_before_call"] == r2["pid_observed_after_call"])
    provisional = {
        "experiment": "MP-E10", "purpose": "the tier-300 identical-code floor required by R17 (v1.2:147)",
        "stage": "pair context, written before the diff so an assembly crash cannot destroy the evidence",
        "generated_at_utc": now_utc(),
        "curriculum_applied_by": "this driver, explicitly, as an importing process must",
        "curriculum": a.get("curriculum"),
        "replay_requested_in_this_process": bool(getattr(bench, "REPLAY_REQUESTED", None)),
        "run_A": r1, "run_B": r2,
        "same_process_observed": same_proc,
        "same_process_statement": ("the four pid samples agree, so both runs executed in one Python process"
                                   if same_proc else
                                   "CANNOT PROVE same-process: the pid samples disagree -- this pair is not a "
                                   "same-process measurement and must not be read as one"),
        "harness_sha256_of_this_pair": a["provenance"].get("harness_sha256"),
        "harness_sha256_of_the_sealed_tier300_figures": SEALED_FIGURES_HARNESS,
        "same_bytes_as_the_sealed_figures": (a["provenance"].get("harness_sha256")
                                             == SEALED_FIGURES_HARNESS),
        "artifacts_on_disk": {RUN_A: sha256(ROOT / RUN_A), RUN_B: sha256(ROOT / RUN_B)},
    }
    (ROOT / OUT).write_text(json.dumps(provisional, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[floor300] stage 1 written; same process: {same_proc}, pid {r1['pid_observed_before_call']}",
          flush=True)

    print("[floor300] diffing with the registered instrument", flush=True)
    cmd = [sys.executable, "tools/mp_e10_row_migration.py", "--replayed", RUN_A, "--baseline", RUN_B,
           "--out", DIFF, "--label",
           "TIER-300 FRESH vs FRESH -- two unreplayed runs of identical code in ONE process "
           f"(pid {r1['pid_observed_before_call']}), same curriculum, same seed; the identical-code floor "
           "R17 requires before any tier-300 behavioural attribution"]
    rc = subprocess.call(cmd, cwd=ROOT)
    print(f"[floor300] migration diff rc={rc}", flush=True)

    diff = jload(DIFF) if (ROOT / DIFF).exists() else None
    moved = diff.get("n_rows_moved") if diff else None
    rows = diff.get("rows_compared") if diff else None
    rate = round(100.0 * moved / rows, 4) if (moved is not None and rows) else None

    # tally-field stability: which of the graded classes moved, and whether `correct` held
    def cls_counts(art):
        out = {}
        for mode, r in (art.get("arms") or {}).items():
            for depth, ph in (r.get("probes") or {}).items():
                for phase, rows_ in ph.items():
                    for x in rows_:
                        out[f"{mode}/d{depth}/{phase}"] = out.get(f"{mode}/d{depth}/{phase}", {})
                        k = x.get("cls")
                        out[f"{mode}/d{depth}/{phase}"][k] = out[f"{mode}/d{depth}/{phase}"].get(k, 0) + 1
        return out

    ca, cb = cls_counts(a), cls_counts(b)
    moved_fields = sorted({f"{key}:{k}" for key in ca for k in set(ca[key]) | set(cb.get(key, {}))
                           if ca[key].get(k) != cb.get(key, {}).get(k)})
    correct_identical = all(ca[key].get("correct") == cb.get(key, {}).get("correct") for key in ca)

    summary = {
        "floor_registered": {
            "tier": 300, "rows_compared": rows, "rows_moved": moved, "movement_rate_percent": rate,
            "same_process_observed": same_proc,
            "pid": r1["pid_observed_before_call"],
            "instrument": "tools/mp_e10_row_migration.py (nine R13 identity fields)",
            "diff_artifact": DIFF, "diff_line_rows_moved": line_of(DIFF, '"n_rows_moved"'),
            "harness_sha256": a["provenance"].get("harness_sha256"),
            "registered_at_utc": now_utc(),
        },
        "tally_stability": {
            "correct_count_identical_across_the_pair": correct_identical,
            "moved_class_fields": moved_fields[:40],
            "n_moved_class_fields": len(moved_fields),
        },
        "byte_condition_for_bounding_the_sealed_figures": {
            "this_pair_ran_on": a["provenance"].get("harness_sha256"),
            "the_sealed_tier300_figures_ran_on": SEALED_FIGURES_HARNESS,
            "identical": (a["provenance"].get("harness_sha256") == SEALED_FIGURES_HARNESS),
            "consequence": ("this floor bounds tier-300 claims made on these bytes. It does NOT retroactively "
                            "bound figures produced on different instrument bytes; R17 re-measures a floor "
                            "whenever the bytes change, so bounding the sealed figures would require a pair "
                            "run on those bytes." if a["provenance"].get("harness_sha256")
                            != SEALED_FIGURES_HARNESS else
                            "same bytes: this floor applies directly to the sealed figures."),
        },
        "wall_clock": {"run_A_seconds": r1["driver_wall_seconds"], "run_B_seconds": r2["driver_wall_seconds"],
                       "driver_total_seconds": round(time.time() - t_all, 2)},
    }
    provisional["stage"] = "complete: pair context, diff, floor registration"
    provisional["floor_registered"] = summary["floor_registered"]
    provisional["tally_stability"] = summary["tally_stability"]
    provisional["byte_condition"] = summary["byte_condition_for_bounding_the_sealed_figures"]
    provisional["wall_clock"] = summary["wall_clock"]
    (ROOT / OUT).write_text(json.dumps(provisional, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[floor300] DONE floor = {moved} of {rows} ({rate}%) | correct identical: {correct_identical} | "
          f"total {summary['wall_clock']['driver_total_seconds']} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
