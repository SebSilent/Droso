"""G0-prime step 1b -- re-derive the pre-flag benchmark snapshot from a commit, not from a file.

WHY THIS EXISTS. `docs/HANDOVER.md` records a row matrix computed against
`_tmp/bench_pre_arbiter_tell_HEAD.json`. That file is real -- its sha256 matches the one the handover
publishes -- but it is (a) inside the swept `_tmp/`, (b) referenced only from `docs/HANDOVER.md`,
which is itself gitignored at `.gitignore:42`, and (c) the sole copy of the pre-flag state. Under R10
that is an instrument that lives in untracked space, and MP-E9 checklist step 5 depends on it.

WHAT IT DOES. Checks out the pre-flag commit in a throwaway git worktree, runs the benchmark there
with this tree's interpreter, and promotes the result into `experiments/MP-E9/baselines/` with its
seals. The surviving `_tmp` copy is used only to CHECK the re-derivation, never as its source: if the
two disagree, that is reported, because then the published row matrix rests on a run nobody can
reproduce.

The bench is re-derivable from a clean worktree because it does not read the live brain:
`run_arm()` builds a fresh house under `_tmp/electric_learn_bench/root/<mode>` and rmtree's it per
depth (tools/electric_learn_bench.py:490-498), so the only external inputs are `connectome/data` and
`config/`, both tracked.

Run:  .venv/Scripts/python.exe tools/derive_pre_flag_snapshot.py [--keep]
Takes roughly ten minutes: it is a full three-arm, three-depth bench run in a worktree that has to
rebuild the substrate cache first.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parents[1]
WT = HERE / "_tmp" / "g0prime" / "preflag_worktree"
OUT_DIR = HERE / "experiments" / "MP-E9" / "baselines"
OUT_JSON = OUT_DIR / "bench_pre_arbiter_tell_HEAD.json"
OUT_MANIFEST = OUT_DIR / "bench_pre_arbiter_tell_HEAD.manifest.json"
SURVIVOR = HERE / "_tmp" / "bench_pre_arbiter_tell_HEAD.json"

# af32c0f = ELECTRIC_QA_ANSWER_MEMORY, the commit before af2a739 added ELECTRIC_ARBITER_TELL.
# docs/STATE.md names it as the home of the pre-flag numbers.
PRE_FLAG = "af32c0f"
GRADED = ("ask", "said", "cls", "src", "item", "shape", "mech", "taught", "own", "reason",
          "answered")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git(*a, cwd=None) -> str:
    r = subprocess.run(["git", *a], cwd=str(cwd or HERE), capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"git {' '.join(a)}: {r.stderr.strip()}")
    return r.stdout.strip()


def rows_of(doc):
    """Every probe row, in positional order: arm -> depth -> phase -> [row]."""
    out = {}
    for arm, a in (doc.get("arms") or {}).items():
        out[arm] = {}
        for depth, ph in (a.get("probes") or {}).items():
            out[arm][depth] = {p: list(rows) for p, rows in ph.items()}
    return out


def _rows(doc):
    """Every probe row, positionally, as (coordinate, row)."""
    out = []
    for arm, a in sorted((doc.get("arms") or {}).items()):
        for depth, ph in sorted((a.get("probes") or {}).items(), key=lambda kv: str(kv[0])):
            for phase, rows in sorted(ph.items()):
                for i, r in enumerate(rows):
                    out.append((f"{arm}/d{depth}/{phase}[{i}]", r))
    return out


def _tally(doc):
    """Reply-source counts over the whole run -- the numbers the handover matrix is read from."""
    t = {}
    for _k, r in _rows(doc):
        s = str(r.get("src"))
        t[s] = t.get(s, 0) + 1
    return t


def compare(new, old):
    """Positional, row by row, on the graded fields only.

    Timing and the provenance block are excluded on purpose: a clone that took a different number of
    seconds is not a different measurement, and `started_utc` differs by construction.
    """
    diffs, n = [], 0
    rn, ro = rows_of(new), rows_of(old)
    for arm in sorted(set(rn) | set(ro)):
        for depth in sorted(set(rn.get(arm, {})) | set(ro.get(arm, {})), key=str):
            for phase in sorted(set(rn.get(arm, {}).get(depth, {}))
                                | set(ro.get(arm, {}).get(depth, {}))):
                a = rn.get(arm, {}).get(depth, {}).get(phase, [])
                b = ro.get(arm, {}).get(depth, {}).get(phase, [])
                if len(a) != len(b):
                    diffs.append(f"{arm}/d{depth}/{phase}: row count {len(a)} vs {len(b)}")
                    continue
                for i, (x, y) in enumerate(zip(a, b)):
                    n += 1
                    for k in GRADED:
                        if x.get(k) != y.get(k):
                            diffs.append(f"{arm}/d{depth}/{phase}[{i}].{k}: "
                                         f"{x.get(k)!r} vs {y.get(k)!r}")
    return n, diffs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", default=PRE_FLAG)
    ap.add_argument("--keep", action="store_true", help="leave the worktree in place")
    ap.add_argument("--finish", action="store_true",
                    help="adopt an already-completed worktree run instead of re-running the bench")
    ap.add_argument("--python", default=str(HERE / ".venv" / "Scripts" / "python.exe"))
    a = ap.parse_args()

    if not pathlib.Path(a.python).exists():
        print(f"[derive] no interpreter at {a.python}")
        return 1

    head_at_derivation = git("rev-parse", "HEAD")

    src = WT / "docs" / "evidence" / "electric_learn_bench.json"
    r = None
    elapsed = None
    if a.finish:
        # The bench run already completed in this worktree; only manifest assembly failed. Re-running
        # an eight-minute measurement to rebuild a JSON header would be re-measuring a known result.
        if not src.exists():
            print(f"[derive] --finish needs the worktree evidence at {src}")
            return 1
        print(f"[derive] --finish: adopting the completed worktree run at {src}", flush=True)
        body = src.read_bytes()
    else:
        WT.parent.mkdir(parents=True, exist_ok=True)
        if WT.exists():
            shutil.rmtree(WT, ignore_errors=True)
            git("worktree", "prune")
        print(f"[derive] worktree at {a.commit} -> {WT}", flush=True)
        git("worktree", "add", "--detach", str(WT), a.commit)

        bench_sha = sha((WT / "tools" / "electric_learn_bench.py").read_bytes())
        t0 = time.time()
        r = subprocess.run([a.python, "tools/electric_learn_bench.py"], cwd=str(WT),
                           capture_output=True, text=True)
        elapsed = round(time.time() - t0, 1)
        print(f"[derive] bench exit={r.returncode} in {elapsed}s", flush=True)
        for line in (r.stdout or "").strip().splitlines()[-8:]:
            print("   | " + line, flush=True)
        if r.returncode not in (0, 1):   # 1 = an invention was found; still a valid measurement
            print(r.stderr[-2000:])
            return 1
        if not src.exists():
            print("[derive] the worktree run produced no evidence file")
            return 1
        body = src.read_bytes()

    bench_sha = sha((WT / "tools" / "electric_learn_bench.py").read_bytes())
    doc = json.loads(body.decode("utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_bytes(body)

    man = {
        "artifact": "pre-ELECTRIC_ARBITER_TELL benchmark snapshot",
        "derived_from_commit": git("rev-parse", f"{a.commit}^{{commit}}"),
        "derived_from_commit_subject": git("log", "-1", "--format=%s", a.commit),
        "derived_at_head": head_at_derivation,
        "derived_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "interpreter": sys.version.split()[0],
        "bench_harness_sha256": bench_sha,
        "snapshot_sha256": sha(body),
        "snapshot_bytes": len(body),
        "bench_exit_code": (r.returncode if r is not None else "adopted from a completed run"),
        "bench_seconds": elapsed if r is not None else "not re-run (--finish)",
        "arms": sorted(doc.get("arms") or {}),
        "items": doc.get("items"),
        "probes": doc.get("probes"),
        "told": len(doc.get("told") or []),
        "failures": len(doc.get("failures") or []),
        "rederived_from_scratch": True,
        # The proof this is the PRE-flag state and not the current one wearing different bytes:
        # docs/HANDOVER.md publishes arbiter head 1034 -> 1014 and silence 1535 -> 1519 across the
        # flag, and 36 arbiter-tell rows post-flag. A pre-flag run must show 1034, 1535 and zero.
        "src_tally": _tally(doc),
        "pre_flag_signature": {
            "arbiter_head": _tally(doc).get("arbiter head"),
            "arbiter_tell": _tally(doc).get("arbiter tell", 0),
            "silence": _tally(doc).get("", 0),
            "says_rows": sum(1 for _k, r in _rows(doc) if r.get("said") == "says"),
            "guarded_absence_rows": _tally(doc).get("electric_absence"),
            "expected_from_handover": {"arbiter_head": 1034, "arbiter_tell": 0, "silence": 1535,
                                       "says_rows": 0, "guarded_absence_rows": 24},
        },
    }
    sig = man["pre_flag_signature"]
    exp = sig["expected_from_handover"]
    sig["MATCHES"] = all(sig[k] == exp[k] for k in exp)
    print(f"[derive] pre-flag signature: arbiter head={sig['arbiter_head']} "
          f"arbiter tell={sig['arbiter_tell']} silence={sig['silence']} "
          f"says={sig['says_rows']} absence={sig['guarded_absence_rows']} -> "
          f"{'MATCHES' if sig['MATCHES'] else 'DOES NOT MATCH'}", flush=True)

    # The survivor is the CHECK, never the source. If the re-derivation disagrees with the file the
    # published row matrix was computed against, that is reported: it would mean the matrix rests on
    # a run nobody can reproduce.
    HANDOVER_SHA = "83a774515c5adc676283f30f48625d363db5c941116fbb55a499a73949d6cb26"
    if SURVIVOR.exists():
        sv_bytes = SURVIVOR.read_bytes()
        sv_sha = sha(sv_bytes)
        sv = json.loads(sv_bytes.decode("utf-8"))
        n, diffs = compare(doc, sv)
        man["cross_check"] = {
            "survivor_path": SURVIVOR.relative_to(HERE).as_posix(),
            "survivor_sha256": sv_sha,
            "survivor_matches_handover": sv_sha == HANDOVER_SHA,
            "rows_compared": n,
            "row_differences": len(diffs),
            "first_differences": diffs[:12],
            "verdict": "reproduces" if not diffs else "DIVERGES",
        }
        print(f"[derive] cross-check vs survivor: {n} rows compared, {len(diffs)} differences "
              f"-> {man['cross_check']['verdict']}", flush=True)
    else:
        man["cross_check"] = {"survivor_path": None, "survivor_matches_handover": None,
                              "verdict": "no survivor on this machine; re-derivation stands alone"}

    OUT_MANIFEST.write_text(json.dumps(man, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8", newline="\n")
    print(json.dumps(man, indent=2, sort_keys=True), flush=True)

    if not a.keep:
        git("worktree", "remove", "--force", str(WT))
        git("worktree", "prune")
        print("[derive] worktree removed", flush=True)
    else:
        print(f"[derive] worktree kept at {WT}", flush=True)
    print(f"[derive] snapshot -> {OUT_JSON}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
