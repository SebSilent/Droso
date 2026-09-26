"""The number behind the 90/10 claim: what does he actually do with a real task?

Everything measured so far about coding has been about the machinery -- retrieval
rates, how many procedures carry evidence, whether a trial promotes. None of it
answers the question the goal is stated in, which is: given a task he has not seen,
does he solve it locally, or does he need the model?

This runs a battery of ordinary small coding tasks through the router and reports
the route each one took and whether the result survived its own check. Each task
carries a check -- assertions that run against the produced code -- so verification
here means "it solves the task", which is the evidence kind worth 0.35 and the only
one that should ever make a procedure trusted. "It exited zero" is not that; a
function definition exits zero without being called.

The battery is deliberately split. `own` tasks are things his library plausibly
holds, because they are his own functions described in other words. `novel` tasks
are ordinary programming he has no reason to have seen. The honest expectation is
that he does well on the first and badly on the second, and the ratio between them
is the actual state of goal B -- not the 90% in the brief.

There is no API key in this configuration, so the oracle rung fails rather than
answering. That is the right condition to measure under: it shows what the local
path does on its own, with nothing to fall back on.

Usage:
    python tools/task_battery.py
    python tools/task_battery.py --only novel
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Each check runs after the solution, in the same file, and must raise to fail.
BATTERY = [
    # ---- things his own library plausibly holds -----------------------------
    {"group": "own",
     "task": "fold plural and verbal suffixes so related words match",
     "check": "assert stem('holding') == stem('holds')\n"
              "assert stem('places') == stem('place')\n"
              "assert stem('class') == 'class'\n"},
    {"group": "own",
     "task": "compute a stable signature key from a task description",
     "check": "assert signature('sort the rows by key') == "
              "signature('rows sorted by a key')\n"},
    {"group": "own",
     "task": "match a task to the best procedure above a success floor",
     "check": "assert match is not None\n"},
    # ---- ordinary programming he has no reason to have seen -----------------
    {"group": "novel",
     "task": "write a function fib(n) returning the nth fibonacci number",
     "check": "assert [fib(i) for i in range(8)] == [0, 1, 1, 2, 3, 5, 8, 13]\n"},
    {"group": "novel",
     "task": "write a function reverse(s) that reverses a string",
     "check": "assert reverse('droso') == 'osord'\n"
              "assert reverse('') == ''\n"},
    {"group": "novel",
     "task": "write a function word_counts(text) returning a dict of word "
             "frequencies, lowercased",
     "check": "assert word_counts('the day the night') == "
              "{'the': 2, 'day': 1, 'night': 1}\n"},
    {"group": "novel",
     "task": "write a function flatten(nested) that flattens one level of "
             "nesting",
     "check": "assert flatten([[1, 2], [3], [4, 5]]) == [1, 2, 3, 4, 5]\n"},
    {"group": "novel",
     "task": "write a function is_palindrome(s) ignoring case and spaces",
     "check": "assert is_palindrome('Never odd or even')\n"
              "assert not is_palindrome('droso')\n"},
    {"group": "novel",
     "task": "write a function chunk(items, n) splitting a list into groups of n",
     "check": "assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]\n"},
    {"group": "novel",
     "task": "write a function safe_div(a, b) returning None when b is zero",
     "check": "assert safe_div(6, 3) == 2\nassert safe_div(1, 0) is None\n"},
    {"group": "novel",
     "task": "write a function read_json_lines(path) parsing one json object "
             "per line",
     "check": "import tempfile, os, json as _j\n"
              "p = os.path.join(tempfile.mkdtemp(), 'x.jsonl')\n"
              "open(p, 'w').write('{\"a\": 1}\\n{\"a\": 2}\\n')\n"
              "assert read_json_lines(p) == [{'a': 1}, {'a': 2}]\n"},
    {"group": "novel",
     "task": "write a function dedupe(items) preserving first-seen order",
     "check": "assert dedupe([3, 1, 3, 2, 1]) == [3, 1, 2]\n"},
]


def _extract_code(text: str) -> str:
    """Code out of a model reply, fenced or bare."""
    s = str(text or "")
    if "```" in s:
        parts = s.split("```")
        for i in range(1, len(parts), 2):
            body = parts[i]
            nl = body.find("\n")
            if nl >= 0 and body[:nl].strip().lower() in (
                    "python", "py", "python3", "", "bash", "sh"):
                body = body[nl + 1:]
            if body.strip():
                return body.strip()
    return s.strip()


def _ask_oracle(oracle, task: str, check: str, sb) -> dict:
    """The rung that produces novel code. Its output is verified like anything else.

    Nothing here is trusted because a model wrote it. The model supplies a candidate
    and the sandbox decides, which is the whole reason the evidence taxonomy exists:
    a model that writes code that passes its own task's assertions has produced a
    task_check, worth 0.35, the same as a passing test -- and a model that writes
    code that fails produces nothing at all.
    """
    prompt = ("Write Python code that solves this task. Reply with the code only, "
              "no explanation.\n\nTask: " + str(task))
    try:
        r = oracle.query(prompt, max_tokens=400, temperature=0.0,
                         purpose="task_battery")
    except Exception as e:
        return {"ok": False, "reason": f"{type(e).__name__}: {str(e)[:90]}",
                "mode": "error"}
    if not r.get("ok"):
        return {"ok": False, "mode": r.get("mode"),
                "reason": str(r.get("reason") or r.get("mode") or "no answer")[:110]}
    code = _extract_code(r.get("text") or "")
    chk = _check(sb, code, check)
    return {"ok": chk["passed"], "code": code, "mode": r.get("mode"),
            "tokens": r.get("tokens"), "reason": chk["reason"]}


def _build(use_library: bool):
    from organs.local_solver import LocalSolver
    from organs.learning_loop import LearningLoop
    from organs.language_verifier import LanguageVerifier
    from organs.fast_router import FastRouter
    from organs.sandbox import Sandbox

    # The store the live agent actually reads. LearningLoop's default path is
    # exocortex/learned_procedures.json, which is the seeder's output, not the
    # house's -- so the first version of this battery measured a stale library of
    # 277 at 0.35 and reported that the animal could barely recall his own code.
    agent_state = ROOT / "state" / "house_agent_learning.json"
    learning = LearningLoop(state_path=agent_state,
                            events_path=ROOT / "state"
                            / "house_agent_learning_events.jsonl",
                            persist=True) if use_library else None
    zone = ROOT / "house_workspace"
    zone.mkdir(exist_ok=True)
    sb = Sandbox(project_root=str(ROOT), workzone=str(zone),
                 auto_approve_writes=True)
    solver = LocalSolver(verifier=LanguageVerifier(), learning=learning,
                         sandbox=sb, min_confidence=0.7, trial_floor=0.35)
    router = FastRouter(local_solver=solver, reasoning_agent=None,
                        replay_confidence=0.9)
    return router, solver, learning, sb


def _check(sb, solution: str, check: str) -> dict:
    """Run the solution and its check together. Raising is failing."""
    if not str(solution or "").strip():
        return {"ran": False, "passed": False, "reason": "no code produced"}
    name = "_battery_%d.py" % (int(time.time() * 1000) % 10 ** 8)
    try:
        r = sb.run_python(str(solution) + "\n\n" + check, timeout=25, name=name)
    except Exception as e:
        return {"ran": False, "passed": False, "reason": str(e)[:120]}
    ok = bool(r.get("success", r.get("ok", False))) and \
        int(r.get("returncode", r.get("exit_code", 0)) or 0) == 0
    err = str(r.get("stderr") or r.get("output") or "")[-240:]
    return {"ran": True, "passed": ok,
            "reason": None if ok else err.strip()[-160:] or "nonzero exit"}


def run(only: str | None = None, learn: bool = True,
        use_oracle: bool = True, provider: str = "ollama") -> dict:
    router, solver, learning, sb = _build(True)
    try:
        from tools import _experience
    except Exception:                                          # pragma: no cover
        _experience = None
    # Every sandbox run in this tool reports itself as an act, through the sandbox's
    # own hook so there is one record per execution rather than two.
    if _experience is not None:
        sb.on_run = lambda name, ok: _experience.ran(str(name), bool(ok))
    oracle = None
    oracle_mode = "disabled"
    if use_oracle:
        try:
            # The same construction path the house uses, so the key comes from the
            # user-profile credential store rather than the environment, and the
            # provider/base/model all come from one place. A battery that built its
            # own APIOracle would read a different key resolution than the being it
            # is measuring.
            import json as _json
            from pathlib import Path as _Path
            from organs.api_oracle import oracle_from_config
            _cfg = _json.loads((ROOT / "config" / "hybrid_config.json")
                               .read_text(encoding="utf-8"))
            o = oracle_from_config(_cfg, provider=provider or None)
            oracle_mode = o.mode
            oracle = o if o.has_key else None
        except Exception as e:
            oracle_mode = f"error: {type(e).__name__}"
    rows = []
    routes: dict = {}
    for item in BATTERY:
        if only and item["group"] != only:
            continue
        t0 = time.time()
        if _experience is not None:
            _experience.tries(item["task"])
        try:
            out = router.run(item["task"])
        except Exception as e:
            out = {"solution": "", "route_path": "error", "error": str(e)[:120]}
        route = str(out.get("route_path") or "?")
        routes[route] = routes.get(route, 0) + 1
        sol = str(out.get("solution") or "")
        chk = _check(sb, sol, item["check"])
        repaired = None
        if not chk["passed"] and sol.strip():
            # A recalled function is not a solution to a task: it carries its own
            # name, while the task asks for a particular one. Let the failure say
            # what to change -- NameError('fib') means the artifact defines the
            # right thing under the wrong name, and renaming it is mechanical.
            rp = solver.repair_against(sol, item["check"])
            if rp.get("ok"):
                sol = rp["code"]
                chk = _check(sb, sol, item["check"])
                repaired = rp.get("renames")
            elif rp.get("renames"):
                repaired = rp.get("renames")
        # The 10%: only when the local rungs have declined. Its output is verified
        # by the task's own assertions, and stored only if it passes them.
        oracle_calls = 0
        oracle_used = False
        if not chk["passed"] and oracle is not None:
            o = _ask_oracle(oracle, item["task"], item["check"], sb)
            oracle_calls = 1
            if o.get("ok"):
                sol = o["code"]
                chk = _check(sb, sol, item["check"])
                oracle_used = True
            else:
                chk = {"ran": chk["ran"], "passed": False,
                       "reason": str(o.get("reason"))[:160]}
        if learn and chk["ran"] and learning is not None and sol.strip():
            # A check that ran is the strongest evidence there is: not "it parsed",
            # not "it exited zero", but "it did the task".
            try:
                learning.learn_from_task(
                    item["task"], sol,
                    {"source": route, "verified": chk["passed"],
                     "language": "python", "verifier_kind": "task_check"},
                    verified=chk["passed"])
            except Exception:
                pass
        rows.append({"group": item["group"], "task": item["task"][:56],
                     "route": route, "method": out.get("method"),
                     "solution_chars": len(sol),
                     "checked": chk["ran"], "passed": chk["passed"],
                     "repaired": repaired, "from_oracle": oracle_used,
                     "reason": chk["reason"],
                     "oracle_calls": oracle_calls,
                     "ms": round((time.time() - t0) * 1000, 1)})
        if _experience is not None:
            _experience.outcome(item["task"], bool(chk["passed"]))
    by_group = {}
    for g in ("own", "novel"):
        sub = [r for r in rows if r["group"] == g]
        if sub:
            by_group[g] = {"tasks": len(sub),
                           "passed": sum(1 for r in sub if r["passed"]),
                           "needed_repair_to_pass": sum(
                               1 for r in sub if r["passed"] and r["repaired"]),
                           "produced_code": sum(1 for r in sub
                                                if r["solution_chars"]),
                           "local_only": sum(1 for r in sub
                                             if r["oracle_calls"] == 0)}
    return {"tasks": len(rows), "routes": routes, "by_group": by_group,
            "oracle_provider": provider, "oracle_mode": oracle_mode,
            "passed": sum(1 for r in rows if r["passed"]),
            "solved_locally": sum(1 for r in rows if r["passed"]
                                  and not r["from_oracle"]),
            "solved_by_oracle": sum(1 for r in rows if r["from_oracle"]),
            "needed_oracle": sum(1 for r in rows if r["oracle_calls"] > 0),
            "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["own", "novel"], default=None)
    ap.add_argument("--no-learn", action="store_true")
    ap.add_argument("--no-oracle", action="store_true",
                    help="measure the local path alone")
    ap.add_argument("--provider", default=None,
                    help="override the configured provider; default is whatever "
                         "config/hybrid_config.json names")
    a = ap.parse_args()
    out = run(a.only, not a.no_learn, not a.no_oracle, a.provider)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
