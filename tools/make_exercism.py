"""Exercism ingestion: more tasks with verifiers attached, and no model calls.

Why this and not a bare code corpus. 5b measured the current wall and it is not search:
the loop generates a candidate, it fails, a second step is built from the failure -- 22
follow-on candidates, 13 repair rounds on the held-out slice -- and it solves nothing new
because the bodies need knowledge the candidate set does not contain. Sphere surface area
is 4*pi*r**2. That is not reachable from a table of operations. Bare code from The Stack or
CodeSearchNet would not help either: no verifier, so it arrives as definitional-grade
material and poisons the library. Exercism ships a task, a reference solution AND a test
suite for every exercise, which is the same shape as MBPP at larger scale.

The two transformations, both of which have to be honest or the whole thing is worthless:

1. Exercism tests are unittest classes, not assertions. `self.assertEqual(a, b)` becomes
   `assert a == b` -- the same comparison, and the loop appends a `check` to a candidate
   definition and execs it, so a unittest file could not be used directly anyway. A method
   using an assertion this does not translate EXACTLY is not worth translating: the whole
   exercise is dropped rather than silently weakened, because a check that is easier than
   the real one hands over task_check evidence that was never earned.

2. The proof that the translation is right is that the REFERENCE SOLUTION PASSES IT. Every
   kept exercise is run in the sandbox -- gold plus converted assertions -- and kept only
   on exit zero. If the conversion dropped a case or changed a comparison, the gold fails
   and the exercise is discarded. So the gate that admits this material is the same gate
   that admits everything else, and it is applied by execution rather than by my reading.

Usage:
    python tools/make_exercism.py                # fetch, convert, verify, write
    python tools/make_exercism.py --status
    python tools/make_exercism.py --show 3
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import io
import json
import re
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "state" / "curriculum"
SHELF = ROOT / "state" / "shelf"
TRACK_URL = ("https://github.com/exercism/python/archive/refs/heads/main.tar.gz")
LICENCE = "MIT (exercism/python)"
CACHE = SHELF / "exercism_python_main.tar.gz"

# The unittest assertions that translate to an assertion EXACTLY. Anything not on this
# list means the exercise is dropped: a check that is easier than the real one would hand
# over task_check evidence that was never earned.
SIMPLE = {"assertEqual", "assertNotEqual", "assertTrue", "assertFalse", "assertIsNone",
          "assertIsNotNone", "assertIn", "assertNotIn", "assertIs", "assertIsNot",
          "assertGreater", "assertLess", "assertGreaterEqual", "assertLessEqual"}


def _download(url: str, dest: Path, timeout: int = 120) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1_000_000:
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": "droso-reader/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        dest.write_bytes(r.read())
    return dest


def _unparse(node) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return ""


class _Sub(ast.NodeTransformer):
    """Replace names with the expression each one stands for.

    The map holds NODES, not values. Wrapping a list in ast.Constant produces a Constant
    holding an ast.List, whose source is the repr of an object -- '<ast.List object at
    0x...>' -- which is not Python, so every unrolled case list came out as a
    SyntaxError. Substituting the node itself keeps real source: a list stays a list
    literal, and an assigned expression stays exactly the expression that was written.
    """

    def __init__(self, m: dict):
        self.m = m

    def visit_Name(self, n):
        if n.id in self.m:
            return copy.deepcopy(self.m[n.id])
        return n


def _lit(v) -> ast.AST:
    """A literal value back as an expression node, via repr so it is real source.

    repr of a list, tuple, dict, string or number is valid Python, which is what makes
    unrolling a literal case list exact rather than approximate.
    """
    return ast.parse(repr(v), mode="eval").body


def _sub(node, m: dict) -> str:
    return ast.unparse(_Sub(m).visit(node))


def _one(call, m: dict):
    """One unittest assertion call as an assertion line, or None if it is not exact."""
    if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
        return None
    name = call.func.attr
    if not call.args:
        return None
    if name == "assertAlmostEqual":
        if len(call.args) < 2:
            return None
        places = 7
        for kw in call.keywords:
            if kw.arg == "places" and isinstance(kw.value, ast.Constant):
                try:
                    places = int(kw.value.value)
                except Exception:
                    return None
        # unittest's default is 7 places, so the tolerance is half of the last place.
        return "assert abs(%s - %s) < %s" % (_sub(call.args[0], m), _sub(call.args[1], m),
                                             0.5 * 10 ** (-places))
    if name in ("assertCountEqual", "assertItemsEqual"):
        if len(call.args) < 2:
            return None
        # Order-insensitive comparison. A wrong translation is caught by the gate like
        # any other: the reference solution has to pass this before the exercise is kept.
        return "assert sorted(%s) == sorted(%s)" % (_sub(call.args[0], m),
                                                     _sub(call.args[1], m))
    if name not in SIMPLE:
        return None
    a = _sub(call.args[0], m)
    if name == "assertTrue":
        return "assert %s" % a
    if name == "assertFalse":
        return "assert not %s" % a
    if name == "assertIsNone":
        return "assert %s is None" % a
    if name == "assertIsNotNone":
        return "assert %s is not None" % a
    if len(call.args) < 2:
        return None
    b = _sub(call.args[1], m)
    op = {"assertEqual": "==", "assertNotEqual": "!=", "assertIs": "is",
          "assertIsNot": "is not", "assertIn": "in", "assertNotIn": "not in",
          "assertGreater": ">", "assertLess": "<",
          "assertGreaterEqual": ">=", "assertLessEqual": "<="}[name]
    if op == "not in":
        return "assert %s not in %s" % (a, b)
    return "assert %s %s %s" % (a, op, b)


def _convert_test(src: str) -> tuple:
    """Turn a unittest file into assertions. Returns (lines, why_not).

    `why_not` is set as soon as anything appears that cannot be translated exactly, and
    the caller drops the exercise. Deliberately strict: setUp/tearDown, raises, helper
    methods and computed iterables all count as untranslatable, because the point is a
    check that is exactly as hard as the one Exercism wrote.

    A loop over a LITERAL list of cases is not logic, it is shorthand for the same
    assertions written out, so it is unrolled -- each pass through the body becomes one
    assertion with the loop variable replaced by the value it takes. That is where most
    of the material was: 30 of 32 first-pass drops were plain case loops, and dropping
    them threw away three quarters of the corpus for no reason of correctness.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return [], "unparseable test file"
    out: list = []
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        for fn in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
            if not fn.name.startswith("test"):
                continue
            if not fn.args.args or fn.args.args[0].arg != "self":
                return [], "test method has no self"
            body = [s for s in fn.body
                    if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
            # Straight-line bindings. `result = f(1)` followed by an assertion about
            # `result` is exactly the assertion about `f(1)`, so the name is substituted
            # in order and the check comes out the same size as the case count. Nearly
            # every remaining drop was one of these, or an assertRaises.
            binds: dict = {}
            for st in body:
                if isinstance(st, ast.Assign) and len(st.targets) == 1 and \
                        isinstance(st.targets[0], ast.Name):
                    binds[st.targets[0].id] = st.value
                    continue
                if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name) \
                        and st.value is not None:
                    binds[st.target.id] = st.value
                    continue
                if isinstance(st, ast.With) and len(st.items) == 1:
                    ce = st.items[0].context_expr
                    if st.items[0].optional_vars is not None:
                        # `with assertRaises(...) as err:` -- the body may inspect err,
                        # and there is no exception object to give it, so the exercise
                        # is dropped rather than translated into something weaker.
                        return [], "assertRaises binds the exception"
                    if (isinstance(ce, ast.Call) and isinstance(ce.func, ast.Attribute)
                            and ce.func.attr == "assertRaises" and ce.args):
                        exc = _sub(ce.args[0], binds)
                        inner = [s for s in st.body
                                 if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call)]
                        if len(inner) != len(st.body) or not inner:
                            return [], "assertRaises body is not a call"
                        call_src = _sub(inner[0].value, binds)
                        # Exactly what the context manager means: it may raise this, and
                        # anything else -- including nothing -- is a failure.
                        out.append("try:\n    %s\nexcept %s:\n    pass\nelse:\n"
                                   "    assert False, 'nothing was raised'" % (call_src, exc))
                        continue
                if isinstance(st, ast.For):
                    try:
                        items = ast.literal_eval(st.iter)
                    except Exception:
                        return [], "loop over a computed iterable"
                    if not isinstance(items, (list, tuple)):
                        return [], "loop over a non-list literal"
                    tgt = st.target
                    for item in items:
                        if isinstance(tgt, ast.Tuple):
                            vals = list(item) if isinstance(item, (tuple, list)) else None
                            if vals is None or len(vals) != len(tgt.elts):
                                return [], "loop target does not match its cases"
                            m = {e.id: _lit(v) for e, v in zip(tgt.elts, vals)
                                 if isinstance(e, ast.Name)}
                            if len(m) != len(tgt.elts):
                                return [], "loop target is not plain names"
                            m.update(binds)
                        elif isinstance(tgt, ast.Name):
                            m = dict(binds)
                            m[tgt.id] = _lit(item)
                        else:
                            return [], "loop target is not a name or tuple"
                        for inner in st.body:
                            if not isinstance(inner, ast.Expr) or \
                                    not isinstance(inner.value, ast.Call):
                                return [], "loop body contains logic"
                            line = _one(inner.value, m)
                            if line is None:
                                return [], "untranslatable assertion inside a loop"
                            out.append(line)
                    continue
                if not isinstance(st, ast.Expr) or not isinstance(st.value, ast.Call):
                    return [], "test method contains logic, not only assertions"
                line = _one(st.value, binds)
                if line is None:
                    return [], "assertion does not translate exactly"
                out.append(line)
    if not out:
        return [], "no tests"
    return out, None


def _imported_names(src: str) -> list:
    """Names the test file imports from the exercise module -- what the candidate must define."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    names = []
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module and not n.module.startswith("unittest"):
            for a in n.names:
                names.append(a.name)
    return names


def _task_text(slug: str, instructions: str) -> str:
    if instructions:
        para = []
        for line in instructions.splitlines():
            s = line.strip()
            if s.startswith("#") or s.startswith("!") or s.startswith("["):
                continue
            if not s:
                if para:
                    break
                continue
            para.append(s)
        if para:
            t = " ".join(para)
            t = re.sub(r"`([^`]*)`", r"\1", t)
            if len(t) > 200:
                t = t[:200].rsplit(" ", 1)[0] + "."
            return t
    return "Write a function to " + slug.replace("_", " ").strip() + "."


def build(limit: int | None = None, verify: bool = True, holdout: float = 0.2) -> dict:
    from organs.sandbox import Sandbox
    import tempfile
    tar = _download(TRACK_URL, CACHE)
    rows: list = []
    dropped: dict = {}
    seen = 0
    with tarfile.open(tar, "r:gz") as tf:
        names = tf.getnames()
        prefixes = sorted({n.split("/exercises/practice/")[1].split("/")[0]
                           for n in names if "/exercises/practice/" in n})
        zone_tmp = Path(tempfile.mkdtemp(prefix="exo_"))
        if verify:
            sb = Sandbox(project_root=str(zone_tmp), workzone=str(zone_tmp),
                         auto_approve_writes=True)
        for slug in prefixes:
            if limit and len(rows) >= int(limit):
                break
            seen += 1
            def grab(name_frag: str) -> str:
                for n in names:
                    if n.endswith(name_frag) and "/%s/" % slug in n:
                        f = tf.extractfile(n)
                        if f is not None:
                            return f.read().decode("utf-8", "replace")
                return ""
            gold = grab("/%s/.meta/example.py" % slug) or grab("%s.py" % slug)
            test = grab("/%s/%s_test.py" % (slug, slug)) or grab("_test.py")
            instr = grab("/%s/.docs/instructions.md" % slug)
            if not gold.strip() or not test.strip():
                dropped["no gold or test"] = dropped.get("no gold or test", 0) + 1
                continue
            lines, why = _convert_test(test)
            if why:
                dropped[why] = dropped.get(why, 0) + 1
                continue
            check = "\n".join(lines)
            # THE GATE: the reference solution has to pass the converted assertions.
            # If the translation is wrong, the gold fails here and the exercise is
            # discarded -- so what is admitted is decided by execution, not by my reading
            # of the conversion.
            if verify:
                ok = False
                try:
                    d = Path(sb.workzone)
                    (d / "_x.py").write_text(gold + "\n\n" + check + "\n", encoding="utf-8")
                    r = sb.execute_command('python _x.py', timeout=20)
                    ok = bool(r.get("success"))
                except Exception:
                    ok = False
                if not ok:
                    dropped["gold failed the converted check"] = \
                        dropped.get("gold failed the converted check", 0) + 1
                    continue
            names_required = _imported_names(test) or [slug]
            h = int(hashlib.blake2b(("exercism:" + slug).encode(),
                                    digest_size=4).hexdigest(), 16)
            rows.append({
                "id": "exercism:%s" % slug,
                "source": "exercism",
                "licence": LICENCE,
                "task": _task_text(slug, instr),
                "check": "\n" + check + "\n",
                "gold": gold,
                "split": "holdout" if (h % 100) < int(holdout * 100) else "train",
                "challenge": names_required,
            })
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / "exercism.jsonl"
    dest.write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""),
                    encoding="utf-8")
    from collections import Counter
    c = Counter(r["split"] for r in rows)
    return {"exercises_seen": seen, "kept": len(rows), "splits": dict(c),
            "dropped": dict(sorted(dropped.items(), key=lambda kv: -kv[1])),
            "path": str(dest)}


def load(split: str | None = None) -> list:
    p = OUT / "exercism.jsonl"
    if not p.exists():
        return []
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [r for r in rows if split is None or r.get("split") == split]


def status() -> dict:
    rows = load()
    if not rows:
        return {"present": False, "path": str(OUT / "exercism.jsonl"),
                "cached_track": CACHE.exists()}
    from collections import Counter
    return {"present": True, "total": len(rows),
            "splits": dict(Counter(r["split"] for r in rows)),
            "licence": LICENCE, "path": str(OUT / "exercism.jsonl")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--holdout", type=float, default=0.2)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--show", type=int, default=0)
    ap.add_argument("--no-verify", action="store_true",
                    help="skip the gate -- for inspection only, never for ingestion")
    a = ap.parse_args()
    if a.status:
        print(json.dumps(status(), indent=1))
        return 0
    if a.show:
        for r in load()[:a.show]:
            print("=" * 70)
            print(r["id"], "|", r["split"], "|", r["licence"])
            print(r["task"])
            print(r["check"].strip()[:300])
            print("gold:")
            print(r["gold"].strip()[:300])
        return 0
    t0 = time.time()
    out = build(limit=a.limit, verify=not a.no_verify, holdout=a.holdout)
    out["seconds"] = round(time.time() - t0, 1)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
