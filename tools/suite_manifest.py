"""Suite manifest -- name the collected-but-not-executed tests, do not re-run hoping for a better number.

WHY THIS EXISTS. A serial suite run reported `917 passed, 3 skipped` (920 executed) while
`pytest tests --collect-only -q` reported **1,164 collected**. A 244-test gap between what is collected
and what runs is not a rounding difference: it is either a module-level guard, a collection error
swallowed by `-q`, or a crash part-way through. "The suite looks green" cannot be cited as a sealed
baseline until someone can say which files those tests live in. This tool answers it by node id, once,
without a second full pass.

WHAT IT COUNTS AS EXECUTED. Every `<testcase>` element in the JUnit XML -- passed, failed, errored and
skipped all appear there, because each was reached. A test that was collected and never reached appears
nowhere, and that is precisely the set worth naming.

THE SELF-REFERENCE, stated rather than hidden. The suite contains
`tests/test_g0_prime_instruments.py::test_registration_seal_verifies_against_the_registration`, which
verifies that the seal in `experiments/G0-prime/registration.json` matches the working tree -- and one
of the sealed files is `experiments/G0-prime/decision.md`, which cites this run. The document cannot
both quote the number and be sealed against the moment the number was taken. So the procedure is: run
this tool, write the result into the decision record, re-stamp, then re-run ONLY the seal test to prove
the seal is fresh. The full suite is not run twice to chase a number; the seal test is re-run because
its input legitimately changed after the run.

Run ALONE. Nothing else on the machine: the bench arms read wall-clock time, and contention changes
what a measurement of a time-dependent organism means (see decision.md §4).

    .venv/Scripts/python.exe tools/suite_manifest.py
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict

HERE = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_XML = HERE / "_tmp" / "suite_manifest.xml"
DEFAULT_OUT = HERE / "experiments" / "G0-prime" / "results" / "suite_manifest.json"


def _rel(p) -> str:
    """Repo-relative for display, absolute when it genuinely is elsewhere.

    This helper exists because the same bug was found three times in this one file: every place that
    showed a user-supplied path called Path.relative_to(HERE) on it, which raises ValueError for a
    relative argument. Two of the three crashed AFTER the measurement had been taken -- once in the
    final summary line, once while building the record's own "command" string, 679 seconds into a run
    whose results were already on disk in the XML. A cosmetic path must not be able to destroy a
    measurement, and it must not be able to decide the exit code either.
    """
    pp = pathlib.Path(p).resolve()      # resolve FIRST: a relative argument is still inside HERE,
                                        # and showing it as repo-relative is the point of the field
    try:
        return pp.relative_to(HERE).as_posix()
    except ValueError:
        return pp.resolve().as_posix()


def collect(python: str, target: str = "tests") -> tuple[list[str], int]:
    r = subprocess.run([python, "-m", "pytest", target, "--collect-only", "-q",
                        "-p", "no:cacheprovider"], capture_output=True, text=True, cwd=str(HERE))
    out = (r.stdout or "") + (r.stderr or "")
    ids = [l.strip() for l in out.splitlines() if "::" in l and l.strip()]
    return ids, r.returncode


def testcase_path(tc) -> str:
    """Normalise a JUnit <testcase> to a pytest node id as --collect-only prints it.

    classname is a dotted module, optionally with a trailing CamelCase class; the file attribute, when
    pytest provides it, is the direct answer and is preferred.
    """
    name = tc.get("name") or ""
    f = tc.get("file")
    if f:
        p = str(f).replace("\\", "/")
        return f"{p}::{name}"
    cls = (tc.get("classname") or "").split(".")
    # A trailing capitalised segment is a class, not a module part.
    if cls and re.match(r"^[A-Z_]", cls[-1] or "x"):
        cls = cls[:-1]
    mod = "/".join(cls)
    for cand in (f"{mod}.py", f"{mod}/__init__.py"):
        if (HERE / cand).exists():
            return f"{cand}::{name}"
    return f"{'/'.join(cls)}::{name}"


def execute(python: str, xml: pathlib.Path, target: str = "tests") -> tuple[list[str], int, float, dict]:
    t0 = time.time()
    r = subprocess.run([python, "-m", "pytest", target, "-q", "-p", "no:cacheprovider",
                        f"--junit-xml={xml}"], capture_output=True, text=True, cwd=str(HERE))
    dur = round(time.time() - t0, 2)
    if not xml.exists():
        return [], r.returncode, dur, {"error": "no junit xml written"}
    root = ET.parse(str(xml)).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    ids = [testcase_path(tc) for tc in suite.iter("testcase")]
    counters = {k: suite.get(k) for k in ("tests", "errors", "failures", "skipped", "time")}
    return ids, r.returncode, dur, counters


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--xml", default=str(DEFAULT_XML))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--target", default="tests",
                    help="what to run. The published baseline uses the default 'tests'; a narrower "
                         "target exists so this tool can be exercised WITHOUT paying 11 minutes for "
                         "every change to it -- the alternative was discovering the relative-path "
                         "crash 679 s into a full run. A manifest from a narrower target says so in "
                         "its command field and must not be read as the suite baseline.")
    a = ap.parse_args()
    xml = pathlib.Path(a.xml)
    xml.parent.mkdir(parents=True, exist_ok=True)

    print("[manifest] collecting...", flush=True)
    collected, collect_rc = collect(a.python, a.target)
    print(f"[manifest] collected {len(collected)} (collect exit {collect_rc})", flush=True)

    print("[manifest] running the suite ONCE with --junit-xml. Do not share this machine.", flush=True)
    executed, rc, dur, counters = execute(a.python, pathlib.Path(xml), a.target)
    print(f"[manifest] executed {len(executed)} testcases, pytest returncode {rc}, {dur}s", flush=True)

    cset, eset = set(collected), set(executed)
    missing = sorted(cset - eset)
    extra = sorted(eset - cset)
    by_file = defaultdict(list)
    for nid in missing:
        by_file[nid.split("::")[0]].append(nid)

    # Whole-file absence is a different fault from scattered absence, and the two have different
    # causes. Say which one this is instead of leaving the reader to count.
    per_file_collected = defaultdict(int)
    for nid in collected:
        per_file_collected[nid.split("::")[0]] += 1
    whole_files = sorted(f for f, ids in by_file.items() if len(ids) == per_file_collected[f])
    partial = sorted({f for f, ids in by_file.items() if len(ids) != per_file_collected[f]})

    summary = {
        "schema": "droso.suite_manifest.v1",
        "generated_by": "tools/suite_manifest.py",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "command": f"{pathlib.Path(a.python).name} -m pytest {a.target} -q -p no:cacheprovider "
                   f"--junit-xml={_rel(xml)}",
        # Which tree this measurement is about. The published baseline did not record this, and it is
        # the first thing a reader needs: a suite result with no commit is a number about no tree, and
        # the seal test inside it can only be interpreted against one.
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(HERE),
                                   capture_output=True, text=True).stdout.strip() or None,
        "git_dirty": [l for l in subprocess.run(["git", "status", "--porcelain=v1"], cwd=str(HERE),
                                                 capture_output=True, text=True).stdout.splitlines()
                      if l.strip()],
        "interpreter": sys.version.split()[0],
        "collected": len(collected),
        "executed": len(executed),
        "collected_not_executed": len(missing),
        "collected_not_executed_by_file": {f: ids for f, ids in sorted(by_file.items())},
        "files_missing_entirely": whole_files,
        "files_partially_missing": partial,
        "executed_not_collected": extra[:20],
        "pytest_returncode": rc,
        "collect_returncode": collect_rc,
        "wall_seconds": dur,
        "junit_counters": counters,
        "junit_xml_kept_in_scratch": _rel(xml),
        "note": ("The XML stays in _tmp/ because .gitignore sweeps it and organs/tempstore.py declares "
                 "the area non-normative; this JSON summary is the tracked artifact. A test counts as "
                 "executed if it appears as a <testcase>, including skips -- skipped means reached and "
                 "deliberately not run, which is not the same fault as never being reached at all."),
    }
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8",
                   newline="\n")

    print(f"\n[manifest] collected={len(collected)} executed={len(executed)} "
          f"missing={len(missing)} returncode={rc}")
    if missing:
        print(f"[manifest] MISSING grouped by file ({len(by_file)} files):")
        for f, ids in sorted(by_file.items()):
            tag = "WHOLE FILE" if f in whole_files else f"{len(ids)}/{per_file_collected[f]}"
            print(f"   {f}: {tag}")
            for nid in ids[:5]:
                print(f"        {nid}")
            if len(ids) > 5:
                print(f"        ... {len(ids) - 5} more")
    else:
        print("[manifest] every collected test was reached: collected-minus-executed is empty.")
    if extra:
        print(f"[manifest] {len(extra)} executed ids not in the collected set (id normalisation "
              f"artefacts or dynamic collection); first 5: {extra[:5]}")
    print(f"[manifest] -> {_rel(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
