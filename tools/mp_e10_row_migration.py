"""Row-level migration between two bench runs, on the nine R13 identity fields.

Promoted out of `_tmp/row_migration.py` on 2026-11-04 under the same rule that moved the k-sweep driver:
R10 -- a number a gate depends on cannot live in `_tmp/`, which is swept. Three published, sealed MP-E10
artifacts were produced by that scratch file (`replay_tier120_row_migration.json`,
`control_tier120_no_replay_row_migration.json`, `replay_tier300_row_migration.json`) while the code that
computes them was one `git clean` from non-existence.

WHY A ROW DIFF AND NOT A TALLY. The tallies can agree while rows move: `correct` and `invented` were
identical at every depth, yet `refused` dropped by 3, 7 and 14. A tally cannot show WHICH rows moved or
WHERE they went, and the registered H3 quantity is a tally. This diffs the row sets directly.

KEYING. (depth, phase, ask). Rows are classified by the item label the bench itself uses: `distNN` is a
distractor -- future curriculum, asked about before it was told -- and anything else is a taught item.
That distinction is the finding: a refusal that becomes an answer on a distractor is movement on the
refusal axis, which is what R6 and C1/C2 care about, and it is invisible to an interval computed on
taught-item correctness.

MATCHED PAIRS ARE CHECKED, NOT ASSUMED. Before diffing, the two artifacts' curriculum sha, bench
harness_sha256, seed and argv are compared and the result is written into the artifact. Two runs on
different instruments differ by more than the treatment, and a migration number that quietly spans a code
change attributes the code change to the flag.

USAGE
  py tools/mp_e10_row_migration.py --pair 300ctl
  py tools/mp_e10_row_migration.py --replayed A.json --baseline B.json --out C.json --label "..."
An --out that already exists is refused unless --overwrite is passed: a sealed artifact is never clobbered.
"""
import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

R13 = ("cls", "said", "src", "item", "shape", "mech", "taught", "own", "answered")


def _rel(p):
    """Repo-relative for display and for the artifact's own path fields, absolute if it is elsewhere.

    These two fields are not cosmetic here: they are the artifact's record of WHICH FILES the diff ran on,
    so a caller pointing --replayed at a path outside the repo used to crash after the comparison completed
    -- the bug class suite_manifest.py records three times. The pair registry is the sealed provenance; it
    has to survive being read from anywhere.
    """
    pp = Path(p).resolve()
    try:
        return pp.relative_to(ROOT).as_posix()
    except ValueError:
        return pp.as_posix()


# The registered pairs. Each entry is (replayed-or-new run, the baseline it is diffed against).
PAIRS = {
    "120": ("experiments/MP-E10/results/replay_tier120_armA.json",
            "experiments/MP-E8/results/armA_tier120_curriculum.json",
            "experiments/MP-E10/results/replay_tier120_row_migration.json",
            "tier 120, replay ON, against MP-E8's sealed tier-120 baseline"),
    "300": ("experiments/MP-E10/results/replay_tier300_armA.json",
            "experiments/MP-E8/results/armA_tier300_curriculum.json",
            "experiments/MP-E10/results/replay_tier300_row_migration.json",
            "tier 300, replay ON, against MP-E8's sealed tier-300 baseline"),
    "120ctl": ("experiments/MP-E10/results/control_tier120_no_replay_armA.json",
               "experiments/MP-E8/results/armA_tier120_curriculum.json",
               "experiments/MP-E10/results/control_tier120_no_replay_row_migration.json",
               "tier 120 CONTROL -- replay OFF, same tree, same curriculum"),
    "300ctl": ("experiments/MP-E10/results/control_tier300_no_replay_armA.json",
               "experiments/MP-E8/results/armA_tier300_curriculum.json",
               "experiments/MP-E10/results/control_tier300_no_replay_row_migration.json",
               "tier 300 CONTROL -- replay OFF, same tree, same curriculum, same seed"),
    # THE SHARP ONE. Both sides are MP-E10's own tier-300 runs, on IDENTICAL instrument bytes
    # (harness_sha256 5cf038c2 on both) and an identical curriculum hash, differing only by --replay.
    # Diffing either of them against MP-E8's sealed baseline also drags in a harness change -- the
    # baseline was produced by build 6e09171a -- so that pair measures drift-plus-treatment, while this
    # one measures the treatment plus run-to-run noise and nothing else.
    "300_replay_vs_control": (
        "experiments/MP-E10/results/replay_tier300_armA.json",
        "experiments/MP-E10/results/control_tier300_no_replay_armA.json",
        "experiments/MP-E10/results/tier300_replay_vs_control_row_migration.json",
        "tier 300, replay ON vs replay OFF -- same instrument bytes, same curriculum, same seed"),
}


def learn_rows(art):
    """Index the learn arm's rows by (depth, phase, ask). Returns (index, duplicate_keys)."""
    out, dupes = {}, []
    probes = (art.get("arms", {}).get("learn", {}) or {}).get("probes", {}) or {}
    for depth, phases in probes.items():
        for phase, rows in (phases or {}).items():
            for r in rows or []:
                key = (str(depth), phase, str(r.get("ask")))
                if key in out:
                    dupes.append(list(key))
                out[key] = r
    return out, dupes


def is_distractor(item):
    s = str(item or "")
    return s.lower().startswith("dist") or "dist" in s.lower()[:6]


def identity(art, which):
    """The facts that decide whether two runs may be compared at all."""
    pr = art.get("provenance") or {}
    cur = art.get("curriculum") or {}
    return {
        "artifact": which,
        "git_head": pr.get("git_head"),
        "harness": pr.get("harness"),
        "harness_sha256": pr.get("harness_sha256"),
        "argv": pr.get("argv"),
        "replay_requested_in_argv": ("--replay" in (pr.get("argv") or [])),
        "curriculum_sha256": cur.get("curriculum_sha256"),
        "curriculum_path": cur.get("path"),
        "seed": cur.get("seed"),
        "tier": cur.get("tier"),
        "started_utc": pr.get("started_utc"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pair", choices=sorted(PAIRS), help="a registered pair; sets the other paths")
    ap.add_argument("--replayed", help="the new run to read as the right-hand side")
    ap.add_argument("--baseline", help="the run to diff against")
    ap.add_argument("--out", help="where to write; an existing file is refused without --overwrite")
    ap.add_argument("--label", default="")
    ap.add_argument("--overwrite", action="store_true")
    a = ap.parse_args()

    if a.pair:
        rp, bp, dp, lab = PAIRS[a.pair]
        rep_p, base_p, out_p, label = ROOT / rp, ROOT / bp, ROOT / (a.out or dp), a.label or lab
    else:
        if not (a.replayed and a.baseline and a.out):
            print("give --pair, or all of --replayed --baseline --out", file=sys.stderr)
            return 2
        rep_p = ROOT / a.replayed
        base_p = ROOT / a.baseline
        out_p = ROOT / a.out
        label = a.label or "ad-hoc pair"
    if out_p.exists() and not a.overwrite:
        print(f"REFUSED: {out_p} exists. A sealed artifact is never overwritten (R5). "
              f"Another --out, or --overwrite deliberately.", file=sys.stderr)
        return 3
    for p in (rep_p, base_p):
        if not p.exists():
            print(f"REFUSED: {p} not found", file=sys.stderr)
            return 2

    rep = json.loads(rep_p.read_text(encoding="utf-8", errors="replace"))
    base = json.loads(base_p.read_text(encoding="utf-8", errors="replace"))
    ri, r_dupes = learn_rows(rep)
    bi, b_dupes = learn_rows(base)

    moved, missing = [], []
    for key in sorted(set(bi) | set(ri)):
        x, y = bi.get(key), ri.get(key)
        if x is None or y is None:
            missing.append({"key": list(key), "only_in": "replayed" if x is None else "baseline"})
            continue
        diffs = {f: {"baseline": x.get(f), "replayed": y.get(f)} for f in R13 if x.get(f) != y.get(f)}
        if diffs:
            moved.append({"depth": key[0], "phase": key[1], "ask": key[2],
                          "item_baseline": x.get("item"), "item_replayed": y.get("item"),
                          "class": "distractor/unanswerable" if is_distractor(x.get("item"))
                          else "taught item",
                          "cls_from": x.get("cls"), "cls_to": y.get("cls"),
                          "fields_moved": sorted(diffs), "detail": diffs})

    trans = Counter((m["depth"], m["phase"], m["cls_from"], m["cls_to"], m["class"]) for m in moved)
    by_axis = defaultdict(Counter)
    for (depth, phase, frm, to, cls), n in trans.items():
        by_axis[f"{depth}/{phase}"][f"{frm} -> {to} [{cls}]"] += n

    refused_delta = {}
    for depth in sorted({k[0] for k in ri}):
        for phase in ("live", "restarted", "reasked"):
            try:
                br = (base["summary"]["learn"][depth][phase] or {}).get("refused")
                rr = (rep["summary"]["learn"][depth][phase] or {}).get("refused")
                if br is not None and rr is not None:
                    refused_delta[f"{depth}/{phase}"] = {"baseline": br, "replayed": rr,
                                                         "delta": rr - br}
            except (KeyError, TypeError):
                pass

    idr, idb = identity(rep, "replayed"), identity(base, "baseline")
    comparable = []
    for f in ("curriculum_sha256", "harness_sha256", "seed", "tier"):
        if idr[f] != idb[f]:
            comparable.append(f"{f} differs: baseline={idb[f]} replayed={idr[f]}")
    same_tree = idr["git_head"] == idb["git_head"]

    out = {
        "experiment": "MP-E10",
        "label": label,
        "is_control": "CONTROL" in label.upper(),
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": ("row-level diff on the nine R13 identity fields, keyed (depth, phase, ask); the same "
                   "code path runs for every tier and for the control -- tools/mp_e10_row_migration.py"),
        "artifacts": {"replayed": _rel(rep_p), "baseline": _rel(base_p)},
        "matched_pair": {
            "replayed": idr, "baseline": idb,
            "same_git_head": same_tree,
            "differences_that_break_the_comparison": comparable,
            "reading": ("the two runs differ ONLY by the treatment" if not comparable and same_tree else
                        "the two runs differ by more than the treatment; see the fields above. A migration "
                        "count spanning a code change or a different curriculum hash cannot be read as an "
                        "effect of replay."),
        },
        "duplicate_keys_within_either_index": {"replayed": r_dupes[:10], "baseline": b_dupes[:10],
                                               "replayed_n": len(r_dupes), "baseline_n": len(b_dupes)},
        "rows_compared": len(set(bi) & set(ri)),
        "rows_only_in_one_set": missing[:20],
        "n_rows_only_in_one_set": len(missing),
        "n_rows_moved": len(moved),
        "moved_rows": moved,
        "moved_keys": sorted([[m["depth"], m["phase"], m["ask"]] for m in moved]),
        "transitions_by_axis": {k: dict(v) for k, v in sorted(by_axis.items())},
        "refused_by_phase": refused_delta,
        "class_split": dict(Counter(m["class"] for m in moved)),
        "fields_moved_split": dict(Counter(f for m in moved for f in m["fields_moved"])),
        "taught_rows_moved": [m for m in moved if m["class"] == "taught item"][:20],
        "reading": ("a tally of `correct` can be unchanged while refusals become answers: the interval "
                    "measures retention of taught items, the migration measures the refusal axis. Both are "
                    "reported."),
        "provenance": {
            "driver": "tools/mp_e10_row_migration.py",
            "promoted_from": "_tmp/row_migration.py",
            "promotion_reason": ("R10: three sealed MP-E10 artifacts were produced by a scratch file. "
                                 "A swept driver cannot reproduce a sealed number."),
            "git_head_at_write": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                capture_output=True, text=True).stdout.strip(),
            "python": sys.version.split()[0],
        },
    }
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{label}: {out['n_rows_moved']} rows moved of {out['rows_compared']} compared; "
          f"class split {out['class_split']}; same tree={same_tree}; "
          f"breaks={comparable or 'none'}")
    for k, v in sorted(by_axis.items()):
        print("  ", k, dict(v))
    print("wrote", _rel(out_p))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
