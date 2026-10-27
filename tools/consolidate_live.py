"""Consolidate the LIVE brain: bounded 200-row runs until the urgency
scan comes back empty.

Design entry: docs/speech_log.md, "2026-10-27 (late) -- the consolidator
reaches the live state (design before code)".  The A/B
(tmp_consolidate_ab.py) proved the mechanics on a copy: consolidate()
replays high-value propositions through live()'s Hebb rule, and restored
rows land above the 0.1 urgency line, so they self-select out of the
next scan.  This tool runs that same call against the real state
directory -- the first live write the consolidator has ever made -- with
a per-run backup, a file guard around every write, a census of the
strong band before and after, and a report to state/fitness/.

The house must be down (no serve.py process): a concurrent writer would
fight the guard, not lose to it.  Every run is the proven shape -- one
consolidate(budget=200) call, 600 replay calls -- never one mega-call;
the 200-row budget bounds how many rows one body-state snapshot wires.

Exit codes: 0 drained (or dry-run clean), 1 fatal (guard, save or
invariant failure), 2 max-runs reached with urgent rows remaining.
"""

import argparse
import json
import shutil
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The guard is the harness's own (tools/converse.py): same KNOWN_CHURN
# content-keying for banc_brain.npz, same (size, mtime_ns) keys, so a
# verdict here reads the same way it does in a session.
from tools.converse import guard_check, guard_live_files

# A forced save (save_state(force_san=True)) rewrites the json doc, the
# SAN matrix, and the sequence and cortex stores -- and the cortex and
# sequence saves each write their own JSON sidecar (higher_cortex.py:857
# and :864; sequence_organ.py:412), so the moved set is seven files, not
# the four the audit counted.  The cortex's error trace (.err.npy) is
# written only when the predictor holds errors; the live tree has none,
# so it is allowed-if-appears rather than expected.
EXPECTED_MOVE = {
    "language_state.json",
    "language_state.san.npz",
    "language_state.json.seq.npz",
    "language_state.json.seq.slots.json",
    "language_state.json.cortex.npz",
    "language_state.json.cortex.meta.json",
    "language_state.json.cortex.facts.json",
    "language_state.json.cortex.npz.err.npy",  # allowed-if-appears
}

# The watch's method (tmp_san_watch.py), on the in-memory matrix: nnz is
# every non-zero cell (the dust counts), real is |w| >= 1e-6, and the
# strong band is positive values >= 1.0 -- the wiring the drain exists to
# hold above the line.
def census(lang) -> dict:
    import numpy as np
    w = np.asarray(lang.san_w)
    real = w[np.abs(w) >= 1e-6]
    strong = real[real >= 1.0]
    return {
        "nnz": int(np.count_nonzero(w)),
        "real": int(real.size),
        "real_median": float(np.median(real)) if real.size else 0.0,
        "sum": float(w.sum()),
        "strong_count": int(strong.size),
        "strong_median": float(np.median(strong)) if strong.size else 0.0,
        "strong_max": float(strong.max()) if strong.size else 0.0,
    }


def build_live():
    """The harness build (tools/converse.py:136-197) minus the
    re-pointing: the organ stays on the live tree, everything else is
    the same -- background life stopped, procedure library read-only,
    oracle blocked, prosthesis off, books off, persist on."""
    from world.connectome_house import build_house_agent

    cfg_path = ROOT / "config" / "hybrid_config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) \
        if cfg_path.exists() else {}
    agent = build_house_agent(cfg, project_root=str(ROOT))

    lang = getattr(agent, "language", None)
    if lang is None:
        raise RuntimeError("the agent built without a language organ")

    for name in ("heartbeat", "neural_growth", "learning_loop",
                 "autotraining", "exposure_thread"):
        organ = getattr(agent, name, None)
        for meth in ("stop", "shutdown", "close"):
            if organ is not None and hasattr(organ, meth):
                try:
                    getattr(organ, meth)()
                except Exception:
                    pass
                break

    ll = getattr(agent, "learning_loop", None)
    if ll is not None:
        ll.read_only = True
        for attr in ("persist", "enabled"):
            if hasattr(ll, attr):
                try:
                    setattr(ll, attr, False)
                except Exception:
                    pass

    ao = getattr(agent, "api_oracle", None)
    if ao is not None and hasattr(ao, "api_key"):
        ao.api_key = None
    lang.voice_prosthesis = False
    lang.exposure_enabled = False
    lang.persist = True
    return agent, lang


def assert_invariants(lang) -> None:
    """The two facts that make a live write safe: the organ is pointed at
    the real state file, and it is allowed to save."""
    live_sp = ROOT / "state" / "language_state.json"
    sp = Path(lang.state_path)
    if sp.resolve() != live_sp.resolve():
        raise RuntimeError(
            f"state_path is {sp}, not the live {live_sp} -- refusing to "
            "consolidate an organ that is not on the live tree")
    if not lang.persist:
        raise RuntimeError("lang.persist is False; the drain could not save")


def backup_run(state_dir: Path, backup_root: Path, run_tag: str) -> list:
    """Copy every live language_state file for this run's rollback point.
    The guard snapshot is taken AFTER this returns, so the backup's own
    files sit in the before-state and never flag."""
    dest = backup_root / run_tag
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for p in sorted(state_dir.glob("language_state*")):
        shutil.copy2(p, dest / p.name)
        copied.append(p.name)
    return copied


def fmt_census(c: dict) -> str:
    return (f"nnz {c['nnz']:,} real {c['real']:,} "
            f"(med {c['real_median']:.3e}) sum {c['sum']:.1f} | "
            f"strong {c['strong_count']:,} "
            f"(med {c['strong_median']:.3f} max {c['strong_max']:.3f})")


def write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, default=str),
                    encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Consolidate the live brain in bounded 200-row runs.")
    ap.add_argument("--dry-run", action="store_true",
                    help="scan + replay in memory, no backup, no save; "
                         "the guard proves the live files stay untouched")
    ap.add_argument("--budget", type=int, default=200,
                    help="rows replayed per run (the proven shape is 200)")
    ap.add_argument("--max-runs", type=int, default=12,
                    help="give up with exit 2 if still urgent after this")
    ap.add_argument("--no-backup", action="store_true",
                    help="refuse nothing -- but a live write without a "
                         "rollback point is exactly what the design entry "
                         "forbids, so this is here only for reruns whose "
                         "backup already exists")
    args = ap.parse_args()

    state_dir = ROOT / "state"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = state_dir / "fitness" / f"consolidate_live_{ts}.json"
    report = {"ts": ts, "dry_run": args.dry_run, "budget": args.budget,
              "runs": []}

    print("[consolidate_live] building the live organ (the house must be "
          "down -- no serve.py process)...", flush=True)
    t0 = time.time()
    agent, lang = build_live()
    assert_invariants(lang)
    print(f"[consolidate_live] built in {time.time() - t0:.1f}s; "
          f"state_path={lang.state_path}", flush=True)

    pre = census(lang)
    report["census_at_boot"] = pre
    print(f"[consolidate_live] census at boot: {fmt_census(pre)}", flush=True)

    if args.dry_run:
        g0 = guard_live_files("dry-run")
        res = lang.consolidate(budget=args.budget)
        moved = guard_check(g0)
        post = census(lang)
        report["dry_run"] = {"consolidate": res, "moved": moved,
                             "census_after": post}
        write_report(report_path, report)
        print(f"[consolidate_live] dry-run: rows_scanned "
              f"{res.get('rows_scanned')} rows_urgent {res.get('rows_urgent')} "
              f"rows_replayed {res.get('rows_replayed')} "
              f"elapsed {res.get('elapsed_s', 0):.1f}s", flush=True)
        print(f"[consolidate_live] dry-run: san_real "
              f"{res.get('san_real_before'):,} -> "
              f"{res.get('san_real_after'):,} (in memory only)", flush=True)
        print(f"[consolidate_live] dry-run: census after: "
              f"{fmt_census(post)}", flush=True)
        print(f"[consolidate_live] dry-run: guard moved {moved or 'nothing'}",
              flush=True)
        print(f"[consolidate_live] report: {report_path}", flush=True)
        return 0 if not moved else 1

    backup_root = state_dir / f"backup_pre_consolidate_{ts}"
    drained = False
    for i in range(1, args.max_runs + 1):
        run_tag = f"run{i:02d}"
        run_rec = {"run": i}
        try:
            if args.no_backup:
                copied = []
            else:
                copied = backup_run(state_dir, backup_root, run_tag)
            run_rec["backup"] = copied
            print(f"[consolidate_live] {run_tag}: backed up "
                  f"{len(copied)} files -> {backup_root / run_tag}",
                  flush=True)

            g0 = guard_live_files(run_tag)  # after the backup, deliberately
            pre_census = census(lang)
            res = lang.consolidate(budget=args.budget)
            save_res = lang.save_state(force_san=True)
            if not save_res.get("saved"):
                raise RuntimeError(f"save refused: {save_res}")
            moved = guard_check(g0)
            unexpected = [m for m in moved if m not in EXPECTED_MOVE]
            post_census = census(lang)

            run_rec.update({"consolidate": res, "save": save_res,
                            "moved": moved, "unexpected": unexpected,
                            "census_before": pre_census,
                            "census_after": post_census})
            report["runs"].append(run_rec)

            d_real = (res.get("san_real_after", post_census["real"])
                      - res.get("san_real_before", pre_census["real"]))
            print(f"[consolidate_live] {run_tag}: rows_scanned "
                  f"{res.get('rows_scanned')} rows_urgent "
                  f"{res.get('rows_urgent')} rows_replayed "
                  f"{res.get('rows_replayed')} elapsed "
                  f"{res.get('elapsed_s', 0):.1f}s", flush=True)
            print(f"[consolidate_live] {run_tag}: san_real "
                  f"{res.get('san_real_before'):,} -> "
                  f"{res.get('san_real_after'):,} ({d_real:+,})", flush=True)
            print(f"[consolidate_live] {run_tag}: before "
                  f"{fmt_census(pre_census)}", flush=True)
            print(f"[consolidate_live] {run_tag}: after  "
                  f"{fmt_census(post_census)}", flush=True)
            print(f"[consolidate_live] {run_tag}: guard moved "
                  f"{len(moved)} files, unexpected {unexpected or 'none'}",
                  flush=True)
            if res.get("deltas"):
                print(f"[consolidate_live] {run_tag}: first restored "
                      f"delta {res['deltas'][0].get('min_pair_before')}"
                      f" -> {res['deltas'][0].get('min_pair_after')}",
                      flush=True)

            write_report(report_path, report)
            if unexpected:
                print(f"[consolidate_live] FATAL: the guard caught files "
                      f"outside the expected save set: {unexpected}; "
                      f"rollback point: {backup_root / run_tag}", flush=True)
                return 1
            if res.get("rows_urgent", 1) == 0:
                drained = True
                print(f"[consolidate_live] drained: the urgency scan came "
                      f"back empty on run {i}.", flush=True)
                break
        except Exception as e:
            run_rec["fatal"] = f"{type(e).__name__}: {e}"
            run_rec["traceback"] = traceback.format_exc()
            report["runs"].append(run_rec)
            write_report(report_path, report)
            print(f"[consolidate_live] FATAL on {run_tag}: "
                  f"{type(e).__name__}: {e}", flush=True)
            return 1

    write_report(report_path, report)
    print(f"[consolidate_live] report: {report_path}", flush=True)
    if not drained:
        print(f"[consolidate_live] NOT drained after {args.max_runs} runs "
              f"-- run the tool again (the backlog only decays upward).",
              flush=True)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())