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


def collect(python: str) -> tuple[list[str], int]:
    r = subprocess.run([python, "-m", "pytest", "tests", "--collect-only", "-q",
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


def execute(python: str, xml: pathlib.Path) -> tuple[list[str], int, float, dict]:
    t0 = time.time()
    r = subprocess.run([python, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider",
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
    a = ap.parse_args()
    xml = pathlib.Path(a.xml)
    xml.parent.mkdir(parents=True, exist_ok=True)

    print("[manifest] collecting...", flush=True)
    collected, collect_rc = collect(a.python)
    print(f"[manifest] collected {len(collected)} (collect exit {collect_rc})", flush=True)

    print("[manifest] running the suite ONCE with --junit-xml. Do not share this machine.", flush=True)
    executed, rc, dur, counters = execute(a.python, pathlib.Path(xml))
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
        "command": f"{pathlib.Path(a.python).name} -m pytest tests -q -p no:cacheprovider "
                   f"--junit-xml={xml.relative_to(HERE).as_posix()}",
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
        "junit_xml_kept_in_scratch": xml.relative_to(HERE).as_posix(),
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
    print(f"[manifest] -> {out.relative_to(HERE).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
