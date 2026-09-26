"""Track F: a curriculum with verifiers attached.

The generated corpus taught him his own implementation and nothing else -- a library
can only contain what has been seen, and the only rung that produced new code was the
oracle. A task battery with tests attached changes that without any model call at all:
the task is new, and the check is what decides whether anything gets kept.

MBPP (cc-by-4.0, Google Research) is 974 crowd-sourced Python problems, each with a
task description, a gold solution and three automated test cases. Exercism's
problem-specifications (MIT) is the same shape at larger scale across 83 tracks. Both
carry the property this architecture actually needs, which a bare code corpus like The
Stack or CodeSearchNet does not: **a verifier**. Bare code would poison the library
with definitional-grade material; these hand over task_check evidence at the strongest
weight, decided by execution.

A held-out fifth is fixed by hashing the task id, so it never changes between runs and
never reaches candidate generation. That is the whole point of it: the training slice
can be memorised and the number will rise, and only the held-out slice says whether
anything generalised. The referee's own warning applies -- a task stored under its own
task text is memory, not learning.

Gold solutions are ingested as a candidate source of their own and labelled `corpus`,
never merged into the local-synthesis column. They are verified by the task's own tests
before anything is kept, so this does not bypass the gate; but counting borrowed
solutions as the being's own work would inflate exactly the number the referee exists
to keep honest. Three columns: local, oracle, corpus.

Usage:
    python tools/make_curriculum.py                 # fetch and split
    python tools/make_curriculum.py --status        # what is on disk
    python tools/make_curriculum.py --show train 3  # inspect a few
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "state" / "curriculum"
MBPP_URL = ("https://raw.githubusercontent.com/google-research/google-research"
            "/master/mbpp/sanitized-mbpp.json")
LICENCES = {
    "mbpp": "cc-by-4.0 (Google Research, google-research/mbpp)",
    "exercism": "MIT (exercism/problem-specifications)",
}


def _split(task_id: str, holdout_pct: float) -> str:
    """Stable split by hash. Same id, same slice, every run, forever."""
    h = int(hashlib.blake2b(str(task_id).encode(), digest_size=4).hexdigest(), 16)
    return "holdout" if (h % 100) < int(holdout_pct * 100) else "train"


def fetch_mbpp(url: str = MBPP_URL, timeout: float = 90.0) -> list:
    req = urllib.request.Request(url, headers={"User-Agent": "droso-curriculum/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
    data = json.loads(raw)
    if isinstance(data, dict):
        data = data.get("rows") or data.get("data") or []
    return list(data)


def _as_list(v) -> list:
    """MBPP stores these as the *repr* of a Python list, not as JSON.

    `test_list` arrives as the string "['assert f(1) == 2', ...]". json.loads rejects
    it, and the first version of this loader treated every row as malformed and kept
    nothing at all -- 427 fetched, 0 kept, which reads like an empty dataset rather
    than a parsing bug.
    """
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v if str(x).strip()]
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return []
        try:
            import ast
            parsed = ast.literal_eval(s)
            if isinstance(parsed, (list, tuple)):
                return [str(x) for x in parsed if str(x).strip()]
            return [str(parsed)]
        except (ValueError, SyntaxError):
            try:
                got = json.loads(s)
                if isinstance(got, list):
                    return [str(x) for x in got if str(x).strip()]
            except ValueError:
                pass
            return [s]
    return [str(v)]


def build(holdout_pct: float = 0.2, limit: int | None = None,
          url: str = MBPP_URL) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = fetch_mbpp(url)
    out = []
    for r in rows:
        tid = r.get("task_id")
        # The GitHub copy calls it `prompt`; the HuggingFace card calls it `text`.
        text = str(r.get("prompt") or r.get("text") or "").strip()
        tests = _as_list(r.get("test_list"))
        imports = _as_list(r.get("test_imports"))
        setup = str(r.get("test_setup_code") or "").strip()
        if not text or not tests:
            continue
        check = "\n".join([setup] + imports + tests)
        out.append({"id": f"mbpp:{tid}", "source": "mbpp",
                    "licence": LICENCES["mbpp"], "task": text,
                    "check": check,
                    "gold": str(r.get("code") or ""),
                    "split": _split(tid, holdout_pct),
                    "challenge": _as_list(r.get("challenge_test_list"))})
        if limit and len(out) >= int(limit):
            break
    path = OUT / "mbpp.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in out) + "\n",
                    encoding="utf-8")
    train = [x for x in out if x["split"] == "train"]
    hold = [x for x in out if x["split"] == "holdout"]
    return {"fetched": len(rows), "kept": len(out), "train": len(train),
            "holdout": len(hold), "holdout_pct": holdout_pct,
            "path": str(path), "licence": LICENCES["mbpp"],
            "with_gold": sum(1 for x in out if x["gold"].strip()),
            "seconds": round(time.time(), 1)}


def load(split: str | None = None, source: str | None = None) -> list:
    """Curriculum rows, mbpp by default.

    The default is unchanged on purpose: the held-out number everyone reads (98 tasks,
    19 solved) is MBPP's, and silently folding a second corpus into it would move a
    figure that is only meaningful because it has not moved. Exercism is reachable by
    source and counted separately.
    """
    if source == "exercism":
        import sys as _s
        if str(ROOT) not in _s.path:
            _s.path.insert(0, str(ROOT))
        from tools.make_exercism import load as _ex
        return _ex(split)
    p = OUT / "mbpp.jsonl"
    if not p.exists():
        return []
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    return [r for r in rows if split is None or r.get("split") == split]


def status() -> dict:
    rows = load()
    if not rows:
        return {"present": False, "path": str(OUT / "mbpp.jsonl")}
    from collections import Counter
    c = Counter(r.get("split") for r in rows)
    return {"present": True, "total": len(rows), "splits": dict(c),
            "sources": dict(Counter(r.get("source") for r in rows)),
            "with_gold": sum(1 for r in rows if r.get("gold", "").strip()),
            "licences": LICENCES, "path": str(OUT / "mbpp.jsonl")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", type=float, default=0.2)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--url", default=MBPP_URL)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--show", nargs=2, metavar=("SPLIT", "N"), default=None)
    a = ap.parse_args()
    if a.status:
        print(json.dumps(status(), indent=1))
        return 0
    if a.show:
        split, n = a.show[0], int(a.show[1])
        for r in load(split)[:n]:
            print("---", r["id"], "|", r["split"])
            print("task:", r["task"][:150])
            print("check:", r["check"][:150])
        return 0
    print(json.dumps(build(a.holdout, a.limit, a.url), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
