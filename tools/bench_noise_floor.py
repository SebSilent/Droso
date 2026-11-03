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

# -----------------------------------------------------------------------------------------------
# R13(a) AS RULED BY THE PI (decision D-G0P-02, experiments/G0-prime/decision.md section 8).
#
# B.1 step 3 read "three clones ... must produce identical outcomes row for row". Measurement
# falsified the literal reading, and R13 pre-registered three ways out. The PI chose (a): a
# registered tolerance, written FIELD-LEVEL and narrow -- identity is required on the nine fields
# below, and only `reason` is tolerated as noise.
#
# `said` is deliberately NOT tolerated. The single graded difference the clones produced is the
# says-gap row, and `said` is the quantity MP-E9 grades: tolerating it would weaken C1/C2 on the
# exact measurement the next gate depends on. The tolerance buys reproducibility on the narration
# text and pays for it with nothing that is scored.
#
# This is a criterion changed after the result was seen, which is what R2 exists to prevent. The
# defence is that (a) was one of three options WRITTEN DOWN BEFORE THE RUN, that it is narrower than
# the literal rule rather than looser than it, and that the offending cell is EXCLUDED from the
# noise-floor claim instead of being averaged into it.
IDENTITY_FIELDS = ("cls", "said", "src", "item", "shape", "mech", "taught", "own", "answered")
TOLERATED_FIELDS = ("reason",)
# Fail-closed by construction: a graded field the ruling did not enumerate is NOT noise. `ask` is
# the one field in GRADED that the PI's list omits -- it is the probe text, fed identically to every
# clone by the harness, so a difference there would be a harness fault rather than organism noise.
# It is therefore held to the identity standard, and the choice is stated here rather than hidden in
# a set difference. Measurement says it is immaterial: zero `ask` differences were observed.
UNENUMERATED_FIELDS = tuple(f for f in GRADED
                            if f not in IDENTITY_FIELDS and f not in TOLERATED_FIELDS)
REQUIRED_FIELDS = IDENTITY_FIELDS + UNENUMERATED_FIELDS

# The cell R13(a) EXCLUDES from the noise-floor claim, per the same ruling: "step 3 is met on 2 of 3
# clones and on every phase except `reasked`/`restarted` of learn/d1, and that cell is excluded from
# the noise-floor claim rather than averaged into it." Excluding a cell is not forgiving a difference
# -- the rows in it stay in the artifact with their values, and they are counted separately.
R13A_EXCLUDED_CELLS = (("learn", "1", "reasked"), ("learn", "1", "restarted"))


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


def diff_records(a, b):
    """Row-for-row differences as structured records: coord / field / both values / identity.

    `identity` is True when the differing field is one R13(a) requires to match -- everything except
    `reason`. The difference list is NEVER filtered: the tolerance decides the VERDICT, not what gets
    REPORTED. A tolerated difference still appears here, in the artifact and in the tests, because a
    noise floor that hides the noise it forgave is not a measurement of noise.
    """
    ka = [k for k, _ in a]
    kb = [k for k, _ in b]
    if ka != kb:
        return [{"coord": "ALL", "field": "coordinate_sets", "a": len(ka), "b": len(kb),
                 "identity": True}]
    out = []
    for (k, ra), (_k2, rb) in zip(a, b):
        for f in GRADED:
            if ra[f] != rb[f]:
                out.append({"coord": k, "field": f, "a": ra[f], "b": rb[f],
                            "identity": f in REQUIRED_FIELDS})
    return out


def diff(a, b):
    """Row-for-row differences as strings: the historical interface, kept for its callers and tests.

    The coordinate-set mismatch keeps its original wording. diff_records() restructured how differences
    are STORED, and a caller that greps the message -- or a test that asserts on it -- should not have to
    change because the representation did.
    """
    out = []
    for r in diff_records(a, b):
        if r["field"] == "coordinate_sets":
            out.append(f"coordinate sets differ: {r['a']} vs {r['b']}")
        else:
            out.append(f"{r['coord']}.{r['field']}: {r['a']!r} vs {r['b']!r}")
    return out


def identity_cells(records):
    """Distinct arm/depth/phase cells carrying an IDENTITY-field difference, row index stripped."""
    return sorted({r["coord"].split("[")[0] for r in records
                   if r["identity"] and r["coord"] != "ALL"})


def cell_of(coord):
    """'learn/d1/reasked[120]' -> ('learn', '1', 'reasked')."""
    parts = coord.split("[")[0].split("/")
    arm = parts[0]
    depth = parts[1][1:] if len(parts) > 1 and parts[1].startswith("d") else (
        parts[1] if len(parts) > 1 else "")
    phase = parts[2] if len(parts) > 2 else ""
    return (arm, depth, phase)


def in_excluded_cell(coord):
    return coord != "ALL" and cell_of(coord) in R13A_EXCLUDED_CELLS


def r13a_assess(pair_recs):
    """Apply the registered tolerance and the registered exclusion to already-measured differences.

    Returns counts that keep the three categories apart -- tolerated, identity-in-excluded-cell,
    identity-outside-it -- because the gate's answer depends on which of the three moved.
    """
    recs = [r for v in pair_recs.values() for r in v]
    ident = [r for r in recs if r["identity"]]
    tol = [r for r in recs if not r["identity"]]
    inside = [r for r in ident if in_excluded_cell(r["coord"])]
    outside = [r for r in ident if not in_excluded_cell(r["coord"])]
    rows = sorted({r["coord"] for r in recs})
    return {
        "criterion": ("R13(a) as ruled by the PI -- identity required on "
                      + ", ".join(REQUIRED_FIELDS) + "; tolerated as noise: "
                      + ", ".join(TOLERATED_FIELDS) + "; cell excluded from the noise-floor claim: "
                      + ", ".join("/".join(c) for c in R13A_EXCLUDED_CELLS)),
        "differences_total": len(recs),
        "tolerated_reason_only": len(tol),
        "identity_in_excluded_cell": len(inside),
        "identity_outside_excluded_cell": len(outside),
        "identity_outside_list": [f"{r['coord']}.{r['field']}: {r['a']!r} vs {r['b']!r}"
                                  for r in outside],
        "rows_touched": len(rows),
        "rows_touched_list": rows,
        "fields_observed": {f: sum(1 for r in recs if r["field"] == f)
                            for f in sorted({r["field"] for r in recs})},
        "verdict": ("MET WITH REGISTERED EXCLUSION" if not outside
                    else "NOT REPRODUCIBLE UNDER R13(a)"),
    }


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

    pair_recs = {}
    pair_diffs = {}
    for i in range(len(flats)):
        for j in range(i + 1, len(flats)):
            recs = diff_records(flats[i], flats[j])
            pair_recs[f"clone{i + 1}vsclone{j + 1}"] = recs
            # EVERY difference is written out, uncapped. The first version of the report tool showed a
            # 10-row preview and then counted the preview, which published "8 distinct rows touched"
            # for 11 real ones; a truncated display must never be the thing a total is derived from.
            pair_diffs[f"clone{i + 1}vsclone{j + 1}"] = {
                "rows_compared": len(flats[i]),
                "differences": len(recs),
                "identity_differences": sum(1 for r in recs if r["identity"]),
                "tolerated_reason_only": sum(1 for r in recs if not r["identity"]),
                "all": [f"{r['coord']}.{r['field']}: {r['a']!r} vs {r['b']!r}" for r in recs],
            }
    r13a = r13a_assess(pair_recs)

    heads = {f"clone{i + 1}": headline(d) for i, d in enumerate(docs)}
    identical = all(v["differences"] == 0 for v in pair_diffs.values())

    # Baseline re-verification: does a fresh run reproduce the committed numbers?
    base = None
    if COMMITTED.exists():
        cd = json.loads(COMMITTED.read_text(encoding="utf-8"))
        d0 = diff(flat(cd), flats[0])
        base = {"committed_rows": len(flat(cd)), "differences_vs_clone1": len(d0),
                "all": d0,
                "committed_sha256": sha(COMMITTED.read_bytes()),
                "verdict": "reproduces" if not d0 else "DIVERGES"}

    # --reuse re-derives a VERDICT from already-sealed clone files. It must not silently rewrite the
    # record of how those files were produced, so the original run entries are carried forward.
    re_derivation = None
    if a.reuse and (OUT_DIR / "noise_floor.json").exists():
        prev = json.loads((OUT_DIR / "noise_floor.json").read_text(encoding="utf-8"))
        runs = prev.get("runs", runs)
        re_derivation = {
            "original_measured_at_utc": prev.get("measured_at_utc"),
            "original_harness_sha256": prev.get("harness_sha256"),
            "note": ("--reuse: this pass ran NO bench and measured NOTHING new. It recomputes the "
                     "verdict from the three sealed clone files under a criterion the PI registered "
                     "after those files were written. The `runs` block is the ORIGINAL measurement "
                     "record, carried forward so this artifact keeps saying how its own inputs were "
                     "made."),
        }

    res = {
        "schema": "droso.bench_noise_floor.v1",
        "configuration": {"arms": a.arms,
                          "depth": a.depth or "1,2,3 (bench default)", "clones": a.clones,
                          "graded_fields": list(GRADED), "excluded_fields": list(VOLATILE),
                          "identity_fields_r13a": list(IDENTITY_FIELDS),
                          "tolerated_fields_r13a": list(TOLERATED_FIELDS),
                          "unenumerated_held_to_identity": list(UNENUMERATED_FIELDS),
                          "excluded_cells_r13a": ["/".join(c) for c in R13A_EXCLUDED_CELLS]},
        "harness_sha256": sha(BENCH.read_bytes()),
        "runs": runs,
        "pairs": pair_diffs,
        "headline_per_clone": heads,
        "headline_identical": len({json.dumps(h, sort_keys=True) for h in heads.values()}) == 1,
        "baseline_reverify": base,
        # Two verdicts, deliberately kept apart. The literal B.1 step-3 wording is NOT overwritten by
        # the registered tolerance: a reader must be able to see that the original rule failed and
        # that the ruled rule passes only with a named cell excluded.
        "criterion_literal": "B.1 step 3 as written: identical outcomes row for row on every graded field",
        "noise_floor_verdict": "IDENTICAL" if identical else "NOT REPRODUCIBLE",
        "criterion_r13a": r13a,
        "r13a_verdict": r13a["verdict"],
        "re_derivation": re_derivation,
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
    print(f"[noise] NOISE FLOOR, B.1 step 3 as literally written: {res['noise_floor_verdict']}")
    print(f"[noise] NOISE FLOOR, R13(a) as ruled by the PI: {r13a['verdict']} -- "
          f"{r13a['tolerated_reason_only']} reason-only difference(s) tolerated, "
          f"{r13a['identity_in_excluded_cell']} identity difference(s) inside the excluded cell, "
          f"{r13a['identity_outside_excluded_cell']} outside it")
    print(f"[noise] -> {OUT_DIR / 'noise_floor.json'}")
    # The EXIT CODE now follows the criterion the PI registered, not the pre-registration wording.
    # Both verdicts are printed above and both are in the artifact: the literal rule is reported as
    # failing, so following the ruled criterion here cannot quietly rewrite what the original said.
    return 0 if r13a["verdict"].startswith("MET") else 1


if __name__ == "__main__":
    raise SystemExit(main())
