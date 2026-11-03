"""G0-prime step 3 -- measure the bench's noise floor instead of assuming it.

The battery earned its credibility by running generation 0 as three clones of one genome and
reporting that all three scored 19/24 with identical failure stages and no ask changing membership.
That is the standard G0-prime extends to the capability instrument: three clones of ONE
configuration, at depths 1/2/3, must produce identical outcomes row for row before any treatment arm
is allowed to be scored.

WHY IT RUNS CLONES AS SEPARATE PROCESSES. Same-process clones would share module state, and a shared
module state is exactly the thing that can make two "identical" runs agree for the wrong reason. Each
clone gets its own `--workdir` (two runs sharing one scratch tree would rmtree each other's taught
state, and a clone that lost its own state would still print a clean number) and its own `--out` (a
clone must never overwrite the committed baseline).

WHAT COUNTS AS A DIFFERENCE. The graded fields only. `seconds` and `started_utc` differ by
construction and are excluded; a run that took longer is not a run that measured something else.

Run:  .venv/Scripts/python.exe tools/bench_noise_floor.py --clones 3
Roughly eleven minutes per clone, so a three-clone run is around half an hour: background it.
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
BENCH = HERE / "tools" / "electric_learn_bench.py"
OUT_DIR = HERE / "experiments" / "G0-prime" / "results" / "noise_floor"
COMMITTED = HERE / "docs" / "evidence" / "electric_learn_bench.json"

GRADED = ("ask", "said", "cls", "src", "item", "shape", "mech", "taught", "own", "reason",
          "answered")
# Fields the clone comparison is allowed to disagree on without being a different measurement.
VOLATILE = ("seconds", "started_utc")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def rows_of(doc):
    out = {}
    for arm, a in sorted((doc.get("arms") or {}).items()):
        out[arm] = {}
        for depth, ph in sorted((a.get("probes") or {}).items(), key=lambda kv: str(kv[0])):
            out[arm][depth] = {p: list(rows) for p, rows in sorted(ph.items())}
    return out


def flat(doc):
    """Positional list of (coordinate, {graded fields})."""
    out = []
    for arm, depths in rows_of(doc).items():
        for depth, phases in depths.items():
            for phase, rows in phases.items():
                for i, r in enumerate(rows):
                    out.append((f"{arm}/d{depth}/{phase}[{i}]",
                                {k: r.get(k) for k in GRADED}))
    return out


def headline(doc):
    """The numbers the gate is read for, recomputed from the rows rather than copied from a table."""
    res = {}
    for arm, a in (doc.get("arms") or {}).items():
        res[arm] = {}
        for depth, ph in (a.get("probes") or {}).items():
            res[arm][str(depth)] = {}
            for phase, rows in ph.items():
                c = {}
                for r in rows:
                    k = str(r.get("cls"))
                    c[k] = c.get(k, 0) + 1
                res[arm][str(depth)][phase] = c
    return res


def diff(a, b):
    """Row-for-row differences between two flattened runs."""
    out = []
    ka = [k for k, _ in a]
    kb = [k for k, _ in b]
    if ka != kb:
        out.append(f"coordinate sets differ: {len(ka)} vs {len(kb)} rows")
        return out
    for (k, ra), (_k2, rb) in zip(a, b):
        for f in GRADED:
            if ra[f] != rb[f]:
                out.append(f"{k}.{f}: {ra[f]!r} vs {rb[f]!r}")
    return out


def run_clone(i, args, py):
    out = OUT_DIR / f"clone_{i}.json"
    if args.skip_existing and out.exists():
        # A completed clone is a measurement. Re-running it because the runner restarted would throw
        # away eight minutes of work AND make the "three clones" set actually four. Only the bench
        # harness's own hash guards this: if it changed, an old clone is not comparable, and the
        # caller must delete the file deliberately.
        sealed = json.loads(out.read_text(encoding="utf-8")).get("provenance", {})
        now = sha(BENCH.read_bytes())
        if sealed.get("harness_sha256") and sealed["harness_sha256"] != now:
            print(f"[noise] clone {i} exists but was measured on a DIFFERENT harness "
                  f"({sealed['harness_sha256'][:12]} vs {now[:12]}) -- refusing to mix", flush=True)
            raise SystemExit(1)
        print(f"[noise] clone {i}: reusing existing {out.name} "
              f"(harness {now[:12]} unchanged)", flush=True)
        return {"clone": i, "reused_existing": True, "produced_output": True,
                "crashed": False, "out": out.relative_to(HERE).as_posix()}

    wd = HERE / "_tmp" / "g0prime" / f"clone{i}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if wd.exists():
        shutil.rmtree(wd, ignore_errors=True)
    cmd = [py, str(BENCH), "--arms", args.arms, "--out", str(out), "--workdir", str(wd)]
    if args.depth:
        cmd += ["--depth", args.depth]
    t0 = time.time()
    r = subprocess.run(cmd, cwd=str(HERE), capture_output=True, text=True)
    el = round(time.time() - t0, 1)
    produced = out.exists()
    print(f"[noise] clone {i}: exit={r.returncode} in {el}s -> "
          f"{'wrote ' + out.name if produced else 'NO OUTPUT FILE'}", flush=True)
    # Exit 1 is the bench's LEGITIMATE "an invention was found" code, so the return code alone cannot
    # tell a crash from a result. The first clone run of this gate died inside seals() after 471
    # seconds and the runner reported only "exit=1" because it trusted that code. Any nonzero exit
    # now prints stderr, and a missing output file is recorded as the crash signal it is.
    if r.returncode != 0 or not produced:
        print("--- stderr ---", flush=True)
        print((r.stderr or "")[-2500:], flush=True)
    return {"clone": i, "exit_code": r.returncode, "seconds": el,
            "produced_output": produced,
            "crashed": not produced,
            "out": out.relative_to(HERE).as_posix(),
            "stderr_tail": (r.stderr or "").strip().splitlines()[-6:] if not produced else [],
            "stdout_tail": (r.stdout or "").strip().splitlines()[-4:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clones", type=int, default=3)
    ap.add_argument("--arms", default="control,teach,learn")
    # Omitted by default on purpose: the bench runs depths 1/2/3 when --depth is absent, and the
    # gate's requirement is three clones AT ALL THREE DEPTHS, not one depth three times.
    ap.add_argument("--depth", default=None)
    ap.add_argument("--python", default=str(HERE / ".venv" / "Scripts" / "python.exe"))
    ap.add_argument("--reuse", action="store_true",
                    help="compare existing clone files instead of running them")
    ap.add_argument("--skip-existing", action="store_true",
                    help="keep completed clones, run only the missing ones (refuses if the harness "
                         "hash changed)")
    a = ap.parse_args()

    files = []
    runs = []
    for i in range(1, a.clones + 1):
        f = OUT_DIR / f"clone_{i}.json"
        if not a.reuse:
            runs.append(run_clone(i, a, a.python))
        if not f.exists():
            print(f"[noise] missing {f} -- clone {i} produced no evidence")
            return 1
        files.append(f)

    docs = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    flats = [flat(d) for d in docs]

    pair_diffs = {}
    for i in range(len(flats)):
        for j in range(i + 1, len(flats)):
            d = diff(flats[i], flats[j])
            pair_diffs[f"clone{i + 1}vs{j + 1}"] = {"rows_compared": len(flats[i]),
                                                    "differences": len(d),
                                                    "first": d[:10]}

    heads = {f"clone{i + 1}": headline(d) for i, d in enumerate(docs)}
    identical = all(v["differences"] == 0 for v in pair_diffs.values())

    # Baseline re-verification: does a fresh run reproduce the committed numbers?
    base = None
    if COMMITTED.exists():
        cd = json.loads(COMMITTED.read_text(encoding="utf-8"))
        d0 = diff(flat(cd), flats[0])
        base = {"committed_rows": len(flat(cd)), "differences_vs_clone1": len(d0),
                "first": d0[:10],
                "committed_sha256": sha(COMMITTED.read_bytes()),
                "verdict": "reproduces" if not d0 else "DIVERGES"}

    res = {
        "schema": "droso.bench_noise_floor.v1",
        "configuration": {"arms": a.arms,
                          "depth": a.depth or "1,2,3 (bench default)", "clones": a.clones,
                          "graded_fields": list(GRADED), "excluded_fields": list(VOLATILE)},
        "harness_sha256": sha(BENCH.read_bytes()),
        "runs": runs,
        "pairs": pair_diffs,
        "headline_per_clone": heads,
        "headline_identical": len({json.dumps(h, sort_keys=True) for h in heads.values()}) == 1,
        "baseline_reverify": base,
        "noise_floor_verdict": "IDENTICAL" if identical else "NOT REPRODUCIBLE",
        "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "noise_floor.json").write_text(json.dumps(res, indent=1, sort_keys=True) + "\n",
                                              encoding="utf-8", newline="\n")

    print(f"\n[noise] rows per clone: {len(flats[0])}")
    for k, v in pair_diffs.items():
        print(f"   {k}: {v['differences']} differences over {v['rows_compared']} rows")
    if base:
        print(f"   vs committed baseline: {base['differences_vs_clone1']} differences -> "
              f"{base['verdict']}")
    print(f"[noise] NOISE FLOOR: {res['noise_floor_verdict']}")
    print(f"[noise] -> {OUT_DIR / 'noise_floor.json'}")
    return 0 if identical else 1


if __name__ == "__main__":
    raise SystemExit(main())
