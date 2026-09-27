"""CodeContests: the HARD corpus, for the screened pool.

WHY THIS EXISTS. The screened pool needs tasks the being CANNOT solve -- it removes every
task local composition handles, so it can only be grown by harder material. Measured on a
300-problem sample: 23% carry a PYTHON 3 reference solution that passes its own tests, and
their subjects land on all four of the experiment's groups (number 38, string 18,
collection 9, geometry 5). The pool that needs this is the concept-split one.

WHY IT CANNOT GROW THE OTHER POOL. The self-distillation pool needs tasks solved SLOWLY, and
four admissible problems put to the being came back `{unsolved: 4}`. Harder material cannot
supply "solvable but slow" -- that is a property of the being's state, not of a problem. See
the generated-source work for that side.

TRUST BY EXECUTION, NOT BY PROVENANCE. A problem is admitted only when a Python 3 solution
of its own passes its own tests, run here. 24 of 26 first-listed solutions are Python 2
(`print` statements, raw_input, xrange) and are REJECTED rather than auto-converted: a
converted solution that happens to parse is not a verified one, and this project does not
trust things it has not executed.

THE BRIDGE. These are stdin/stdout PROGRAMS; the task contract is a function called by
assertions. `_bridge_check` closes that gap by executing the candidate as a program under
redirected stdin/stdout and comparing real output against the real expected output -- so the
check tests genuine equivalence rather than merely producing something that passes.
`validate_bridge` is the deliberate sample that proves both directions.

    python tools/make_codecontests.py --validate        # controls: right passes, wrong fails
    python tools/make_codecontests.py --rows 600        # fetch, verify, admit
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "state" / "curriculum"
LICENCE = "cc-by-4.0 (DeepMind, google-deepmind/code_contests)"
SENTINEL = "# ---END-CANDIDATE---"
_API = ("https://datasets-server.huggingface.co/rows"
        "?dataset=deepmind/code_contests&config=default&split=train")


def fetch(offset: int, length: int = 100, tries: int = 3) -> list:
    """Rows from the datasets-server, so nothing has to be downloaded whole."""
    u = f"{_API}&offset={int(offset)}&length={int(length)}"
    for a in range(tries):
        try:
            with urllib.request.urlopen(u, timeout=60) as r:
                return [x["row"] for x in json.loads(r.read().decode())["rows"]]
        except Exception:
            if a == tries - 1:
                return []
            time.sleep(2 * (a + 1))
    return []


def tests_of(problem: dict, cap: int = 4) -> list:
    """(input, output) pairs from the problem's own public and generated tests."""
    pairs = []
    for key in ("public_tests", "generated_tests"):
        d = problem.get(key) or {}
        pairs += list(zip(d.get("input") or [], d.get("output") or []))
    return pairs[:cap]


def looks_python2(code: str) -> bool:
    return (("raw_input" in code) or ("xrange" in code)
            or ("\nprint " in code) or code.lstrip().startswith("print "))


def run_program(code: str, stdin_text: str, timeout: float = 10.0):
    """Run a candidate PROGRAM the way the grader will: stdin in, stdout out.

    Via a real FILE, not `python -c`: the bridge check reads its own source back through
    `sys.argv[0]`, and under `-c` that is the literal string "-c". Running it here the same
    way the sandbox does is what makes this validation mean anything.
    """
    import os
    import tempfile
    handle = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                         encoding="utf-8")
    try:
        handle.write(code)
        handle.close()
        r = subprocess.run([sys.executable, handle.name], input=stdin_text,
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout, (r.stderr or "")[-160:]
    except Exception as exc:
        return False, "", "%s: %s" % (type(exc).__name__, str(exc)[:60])
    finally:
        try:
            os.unlink(handle.name)
        except OSError:
            pass


def verified_python3(problem: dict, cap: int = 4):
    """A Python 3 solution of this problem's own that passes its own tests, or None."""
    tests = tests_of(problem, cap)
    if not tests:
        return None
    solutions = (problem.get("solutions") or {}).get("solution") or []
    langs = (problem.get("solutions") or {}).get("language") or []
    for code, lang in zip(solutions, langs):
        if lang != 1 or looks_python2(str(code)):
            continue
        ok = True
        for inp, outp in tests:
            rc, out, _err = run_program(str(code), str(inp))
            if not rc or out.strip().split() != str(outp).strip().split():
                ok = False
                break
        if ok:
            return str(code)
    return None


def bridge_check(tests, cap: int = 4) -> str:
    """A check that runs the CANDIDATE AS A PROGRAM against the problem's real tests.

    The harness executes `code + "\\n\\n" + check` in one file, so the check can read that
    file back, cut at the sentinel, and execute everything before it. That is what makes
    this a genuine equivalence test rather than a shape that merely passes: the comparison
    is between the candidate's ACTUAL stdout and the problem's actual expected output.
    """
    pairs = [[str(i), str(o)] for i, o in tests[:cap]]
    return (
        SENTINEL + "\n"
        "import io, sys, os, contextlib\n"
        "_tests = %r\n"
        "_path = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else __file__\n"
        "_src = open(_path, encoding='utf-8', errors='replace').read()\n"
        "_cand = _src.split(%r)[0]\n"
        "for _inp, _out in _tests:\n"
        "    _buf = io.StringIO()\n"
        "    _old = sys.stdin\n"
        "    sys.stdin = io.StringIO(_inp)\n"
        "    try:\n"
        "        with contextlib.redirect_stdout(_buf):\n"
        "            exec(compile(_cand, '<candidate>', 'exec'), {'__name__': '__main__'})\n"
        "    except SystemExit:\n"
        "        pass\n"
        "    finally:\n"
        "        sys.stdin = _old\n"
        "    assert _buf.getvalue().strip().split() == _out.strip().split(), (\n"
        "        'output mismatch for input ' + repr(_inp[:40]))\n"
        % (pairs, SENTINEL))


def validate_bridge() -> dict:
    """THE DELIBERATE SAMPLE. A bridge that passes everything proves nothing.

    Positive control: the real program must PASS. Negative control: a program that runs
    cleanly and prints the WRONG answer must FAIL -- if it passes, the check is vacuous and
    every number built on it would be meaningless.
    """
    problem = {"public_tests": {"input": ["3\n", "5\n"], "output": ["9\n", "25\n"]}}
    good = "import sys\nn = int(sys.stdin.read().strip())\nprint(n * n)"
    wrong = "import sys\nn = int(sys.stdin.read().strip())\nprint(n + 1)"
    broken = "import sys\nraise ValueError('boom')"
    check = bridge_check(tests_of(problem))
    out = {"good_passes": False, "wrong_fails": False, "broken_fails": False}
    for name, code, want in (("good", good, True), ("wrong", wrong, False),
                             ("broken", broken, False)):
        full = code + "\n\n" + check
        rc, so, err = run_program(full, "", timeout=20)
        got = bool(rc) and bool(so.strip())
        # the check raises AssertionError on mismatch -> nonzero exit
        passed = (rc is True)
        out[name + "_passes" if want else name + "_fails"] = (
            passed if want else (not passed))
        out[name + "_exit"] = rc
    out["ok"] = bool(out["good_passes"] and out["wrong_fails"] and out["broken_fails"])
    return out


def _split(task_id: str, holdout_pct: float = 0.2) -> str:
    h = int(hashlib.sha256(task_id.encode("utf-8")).hexdigest(), 16)
    return "holdout" if (h % 100) < int(holdout_pct * 100) else "train"


def build(rows: int = 600, holdout_pct: float = 0.2, cap: int = 4) -> dict:
    """Fetch, verify, admit. Never admits anything it has not run."""
    seen, admitted, rejected = set(), [], 0
    offset = 0
    while len(seen) < int(rows):
        page = fetch(offset, 100)
        if not page:
            break
        for p in page:
            name = p.get("name") or f"idx{offset}"
            if name in seen:
                continue
            seen.add(name)
            gold = verified_python3(p, cap)
            if not gold:
                rejected += 1
                continue
            tests = tests_of(p, cap)
            tid = f"cc:{name}"
            admitted.append({
                "id": tid, "source": "codecontests", "licence": LICENCE,
                "task": str(p.get("description") or "")[:1200],
                "check": bridge_check(tests, cap),
                "gold": gold, "split": _split(tid, holdout_pct),
                "challenge": str(p.get("difficulty")),
            })
        offset += 100
        if offset > 20000:
            break
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "codecontests.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in admitted), encoding="utf-8")
    from collections import Counter
    return {"fetched": len(seen), "admitted": len(admitted), "rejected": rejected,
            "yield_pct": round(100.0 * len(admitted) / max(1, len(seen)), 1),
            "splits": dict(Counter(r["split"] for r in admitted)), "path": str(path)}


def load(split: str | None = None, source: str | None = None) -> list:
    p = OUT / "codecontests.jsonl"
    if not p.exists():
        return []
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [r for r in rows if split is None or r.get("split") == split]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--rows", type=int, default=600)
    ap.add_argument("--cap", type=int, default=4)
    a = ap.parse_args()
    if a.validate:
        print(json.dumps(validate_bridge(), indent=1))
        return 0
    print(json.dumps(build(a.rows, cap=a.cap), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
