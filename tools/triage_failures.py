"""Sort the failing tests into three buckets mechanically, before a human reads one.

The instruction, and the reason for it: the last round of this work found that `toggle_organ`
and its `advisory_only` flag had been failing since the FIRST COMMIT -- the code never had
them -- while seven broken endpoints were real regressions a deletion would have buried.
From the outside those look identical. Reading 45 test bodies to find out costs hours and
depends on the reader noticing; this costs seconds and does not.

    NEVER-REAL            the symbol the test targets did not resolve AT THE COMMIT THAT
                          INTRODUCED THE TEST. It was born broken, or describes an interface
                          somebody designed and then built differently.
    DELIBERATELY REMOVED  it resolved then, it is gone now, and a commit says it was removed.
    SILENT REGRESSION     it resolved then, it is gone now, and nothing claims to have
                          removed it. ONLY this bucket needs an eye on the test body.

It is a heuristic and says so. `symbol_present` greps the tree at a commit, which finds a
name anywhere -- a docstring or a comment counts. It is deliberately biased towards
NEVER-REAL being small and SILENT REGRESSION being large, because over-reporting a
regression costs a look and under-reporting one costs a bug.

    python tools/triage_failures.py
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SEARCH_DIRS = ("organs", "world", "tools", "connectome", "server")
# Names that are not "the symbol under test" -- ordinary local variables and helpers.
IGNORE = {"self", "house", "agent", "h", "a", "tp", "tmp_path", "hub", "serving",
          "light_agent", "monkeypatch", "tmp_path_factory", "print", "len", "range",
          "str", "int", "float", "list", "dict", "set", "sorted", "json", "Path"}


def _run(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, cwd=str(ROOT), **kw)


# The symbol named in the failure itself. This is the precise signal, and it took a wrong
# version of this file to notice: extracting attribute names from the test body gives
# `route_get`, `pending_actions`, `stats` -- generic names that resolve at every commit --
# so every test came back SILENT REGRESSION and the report was uniform and meaningless. The
# traceback NAMES the thing that is gone, and that name is the whole discriminator.
_SYMBOL_PATTERNS = (
    re.compile(r"has no attribute '([A-Za-z_][A-Za-z0-9_]*)'"),
    re.compile(r"cannot import name '([A-Za-z_][A-Za-z0-9_]*)'"),
    re.compile(r"KeyError: '([A-Za-z_][A-Za-z0-9_]*)'"),
    re.compile(r"module '([\w.]+)' has no attribute '([A-Za-z_][A-Za-z0-9_]*)'"),
    re.compile(r"unexpected keyword argument '([A-Za-z_][A-Za-z0-9_]*)'"),
)


def missing_symbol(error_line: str):
    for rx in _SYMBOL_PATTERNS:
        m = rx.search(error_line or "")
        if m:
            return m.group(m.lastindex)
    return None


def failing_tests() -> list:
    """[(path, test, error_line)] -- zipped from one --tb=line run.

    --tb=line prints exactly one line per failure, in the same order as the FAILED summary,
    so the two lists zip. It is a fragile pairing and it is checked: if the lengths differ,
    the errors are dropped rather than mis-attributed to the wrong test.
    """
    r = _run([sys.executable, "-m", "pytest", "tests", "--tb=line", "-q", "--no-header",
              "-p", "no:cacheprovider"])
    errs = [l.strip() for l in (r.stdout or "").splitlines()
            if re.match(r"^(?:[A-Za-z]:\|/).*\.py:\d+:", l.strip())]
    failed = []
    for line in (r.stdout or "").splitlines():
        m = re.match(r"^FAILED\s+(\S+?)::(\S+)", line.strip())
        if m:
            failed.append((m.group(1), m.group(2).split("[")[0]))
    if len(errs) != len(failed):
        errs = [""] * len(failed)
    return sorted(set(zip([f[0] for f in failed], [f[1] for f in failed], errs)))


def test_lineno(path: str, name: str):
    src = (ROOT / path).read_text(encoding="utf-8")
    for i, line in enumerate(src.splitlines(), start=1):
        if re.match(r"\s*def\s+%s\s*\(" % re.escape(name), line):
            return i
    return None


def intro_commit(path: str, lineno: int):
    r = _run(["git", "blame", "-L", "%d,%d" % (lineno, lineno), "--porcelain", path])
    m = re.search(r"^([0-9a-f]{40})", r.stdout or "")
    return m.group(1) if m else None


def target_symbols(path: str, name: str) -> list:
    """The attributes the test calls on the fixtures -- a guess, and a cheap one."""
    try:
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            fn = node
            break
    if fn is None:
        return []
    found = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id not in IGNORE:
            found.append(node.attr)
    # also names imported from the modules under test
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and \
                ("connectome_house" in node.module or "organs" in node.module):
            found += [a.name for a in node.names]
    return sorted({f for f in found if f and not f.startswith("__")})


def symbol_present(symbol: str, commit: str) -> bool:
    r = _run(["git", "grep", "-q", "-w", symbol, commit, "--"] + list(SEARCH_DIRS))
    return r.returncode == 0


def removal_intent(symbol: str) -> str | None:
    r = _run(["git", "log", "--oneline", "-S", symbol, "--format=%h %s", "-20", "--"]
             + list(SEARCH_DIRS))
    for line in (r.stdout or "").splitlines():
        low = line.lower()
        if any(w in low for w in ("remove", "delete", "drop", "retire", "strip",
                                  "no longer", "take out", "took out")):
            return line[:90]
    return None


def classify(path: str, name: str, error_line: str = "") -> dict:
    lineno = test_lineno(path, name)
    if lineno is None:
        return {"test": name, "file": path, "bucket": "UNKNOWN",
                "why": "could not find the test function"}
    ic = intro_commit(path, lineno)
    named = missing_symbol(error_line)
    if not named:
        return {"test": name, "file": path, "bucket": "SILENT REGRESSION",
                "why": "no missing symbol in the failure -- it is a behaviour difference, "
                       "so the test body has to be read",
                "intro": (ic or "")[:8], "error": (error_line or "")[-90:]}
    syms = [named]
    if not ic:
        return {"test": name, "file": path, "bucket": "UNKNOWN",
                "why": "no blame for this line", "symbols": syms}
    dead = [s for s in syms if not symbol_present(s, ic)]
    if not dead:
        return {"test": name, "file": path, "bucket": "SILENT REGRESSION",
                "why": "every symbol it names existed at its own commit and some are gone now",
                "intro": ic[:8], "symbols": syms}
    # Every symbol it names was missing at the moment it was written: born broken.
    if len(dead) == len(syms):
        return {"test": name, "file": path, "bucket": "NEVER-REAL",
                "why": "NONE of %s existed at the commit that introduced it" % dead[:3],
                "intro": ic[:8], "symbols": syms}
    rem = removal_intent(dead[0])
    return {"test": name, "file": path,
            "bucket": "DELIBERATELY REMOVED" if rem else "SILENT REGRESSION",
            "why": ("a commit claims to have removed %s: %s" % (dead[0], rem)) if rem
                   else ("%s is gone and nothing claims to have removed it" % dead[0]),
            "intro": ic[:8], "symbols": syms, "dead": dead}


def main() -> int:
    tests = failing_tests()  # (path, test, error_line)
    rows = [classify(p, n, e) for p, n, e in tests]
    counts: dict = {}
    for r in rows:
        counts[r["bucket"]] = counts.get(r["bucket"], 0) + 1
    print(json.dumps({"failing": len(rows), "counts": counts,
                      "rows": rows}, indent=1))
    print("\nTHE THREE COUNTS (report these before touching anything):")
    for k in ("NEVER-REAL", "DELIBERATELY REMOVED", "SILENT REGRESSION", "UNKNOWN"):
        if counts.get(k):
            print("  %-22s %d" % (k, counts[k]))
    print("\nOnly SILENT REGRESSION needs a human eye on the test body.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
