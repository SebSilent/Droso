"""Does the generator's CHECK actually discriminate, or does it accept anything?

WHY THIS IS NOT PARANOIA. The pilot verified 10 of 10 -- and "verified" there means the
oracle's solution passes the oracle's own assertions, written by the same model in the same
call. A check that accepts everything makes that statement empty. This is the stdin-bridge
lesson again: a test that cannot fail proves nothing.

So: run deliberately wrong solutions against every generated check. A sound check rejects
all of them. Anything a dumb solution satisfies is dropped, not patched.

    python tools/check_quality.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CUR = ROOT / "state" / "curriculum"


def _name(check: str):
    from organs.knowledge import KnowledgeChannel
    return KnowledgeChannel.target_of(check)


def _assertions(check: str) -> list:
    """The assertion LINES, normalised, each line its own distinctness key.

    COUNTING LINES, NOT A REGEX-MATCHED ARGUMENT TUPLE. The old pattern required a comparison
    operator immediately after the call, so six tasks were reported as having ZERO assertions
    when they compare with a tolerance -- `assert abs(volume(r, h) - 12.566) < 1e-6`, which no
    `==` pattern matches. Every one of them was a float geometry task. The count was measuring
    my regex, not the check.
    """
    out = []
    for line in str(check).splitlines():
        s = line.strip()
        if s.startswith("assert"):
            out.append(re.sub(r"\s+", " ", s))
    return out


def wrong_solutions(check: str, gold: str) -> dict:
    """Four dumb solutions. The last only where a cheap off-by-one exists."""
    n = _name(check)
    if not n:
        return {}
    out = {
        "constant": f"def {n}(*a, **k):\n    return 0\n",
        "first_arg": f"def {n}(*a, **k):\n    return a[0] if a else None\n",
        "returns_none": f"def {n}(*a, **k):\n    return None\n",
    }
    # off-by-one: shift the reference's own answer. THE MUTATION MUST BE TYPE-AWARE, because
    # the old fallback was `return r` -- the CORRECT answer. For a task returning a dict or a
    # set, `r + 1` and `r[:-1]` both raise, so the "wrong" solution handed back the right one
    # and the check was accused of accepting it. Measured: all seven tasks the battery flagged
    # as weak returned a dict or a set. When nothing cheap can be perturbed the variant returns
    # a sentinel that cannot collide with a correct answer, so a check that accepts THAT is
    # genuinely weak rather than being blamed for my wrapper.
    alias = re.sub(rf"def\s+{re.escape(n)}\s*\(", "def _g(", gold, count=1)
    if alias != gold:
        out["off_by_one"] = (
            alias + "\n\n"
            f"def {n}(*a, **k):\n"
            "    r = _g(*a, **k)\n"
            "    if isinstance(r, bool):\n"
            "        return not r\n"
            "    if isinstance(r, (int, float)):\n"
            "        return r + 1\n"
            "    if isinstance(r, (list, tuple, str)):\n"
            "        return r[:-1]\n"
            "    return ('__NOT_THE_REFERENCE__',)\n"
        )
    return out


def audit(paths, label: str) -> dict:
    from tools.curriculum_run import _loop_agent
    agent = _loop_agent()
    loop = agent.reasoning_loop
    rep = {"bucket": label, "tasks": 0, "too_few_assertions": [], "weak": [],
           "rejected": 0, "assertion_counts": [], "no_name": []}
    for p in paths:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            rep["tasks"] += 1
            check, gold = r["check"], r["gold"]
            args = _assertions(check)
            rep["assertion_counts"].append(len(args))
            if not _name(check):
                rep["no_name"].append(r["task"][:60])
                continue
            if len(args) < 2 or len(set(args)) < 2:
                # one assertion, or the same input twice: it cannot pin down behaviour
                rep["too_few_assertions"].append((r["task"][:60], len(args), len(set(args))))
            weak = []
            for wname, code in wrong_solutions(check, gold).items():
                # MUST append the check. `_verify_detail` runs the code ALONE and returns
                # (True, "definitional") when it merely defines functions and exits 0 -- so
                # passing the code by itself reports every solution as correct, including
                # `return None`. The real callers build `code + "\n\n" + check`; this must too.
                ok, _kind = loop.solver._verify_detail(code + "\n\n" + check, check)
                if ok:
                    weak.append(wname)
            if weak:
                rep["weak"].append((r["task"][:60], weak))
            else:
                rep["rejected"] += 1
    return rep


def main() -> int:
    # THE FILENAMES DO NOT FOLLOW THE BUCKET NAMES. `generated_selfdistill.jsonl` has no
    # underscore; building the path from the label silently audited a file that does not
    # exist and reported `tasks: 0` -- a clean-looking zero for "nothing was checked".
    files = {"self_distill": "generated_selfdistill.jsonl",
             "screened": "generated_screened.jsonl"}
    rep = {}
    for label, fname in files.items():
        p = CUR / fname
        rep[label] = audit([p], label)
        if not p.exists():
            rep[label]["MISSING_FILE"] = str(p)
    # combined verdict
    total = sum(r["tasks"] for r in rep.values())
    clean = sum(r["rejected"] for r in rep.values())
    print(json.dumps(rep, indent=1))
    print()
    print(f"TASKS {total} | every dumb solution rejected on {clean} "
          f"({(clean / total if total else 0):.0%}) | rejection rate {(1 - clean / total if total else 0):.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
