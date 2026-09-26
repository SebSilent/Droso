"""Track F runner: work the curriculum, keep the held-out fifth untouched.

Three candidate sources, three columns, never merged:

  local   recall from the library, then repair_against the task's check. His own work.
  corpus  the task's gold solution, verified by the task's OWN tests before anything
          is kept. This is the "code knowledge from a database instead of a model
          call" path: 427 tasks with verifiers attached, no API involved. Labelled
          separately because counting borrowed solutions as local would inflate
          exactly the number the referee exists to keep honest.
  oracle  the model, only if a key is configured and only after both of the above.

The gate is identical for all three: the task's own assertions must pass in the
sandbox, and the result is stored through the one existing path with
verifier_kind="task_check". Nothing here bypasses that, and nothing is trusted for
having come from a particular place.

Holdout tasks are never a candidate source, never composed against, and never learned
from. They are measured and thrown away. That is the only number that says whether
anything generalised rather than memorised -- a task stored under its own task text is
memory, and its pass rate will rise whether or not the being got better.

Usage:
    python tools/curriculum_run.py --split train --limit 60
    python tools/curriculum_run.py --split holdout          # measurement only
    python tools/curriculum_run.py --split train --no-gold  # local ability alone
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _build(use_oracle: bool):
    from organs.local_solver import LocalSolver
    from organs.learning_loop import LearningLoop
    from organs.language_verifier import LanguageVerifier
    from organs.fast_router import FastRouter
    from organs.sandbox import Sandbox

    agent_state = ROOT / "state" / "house_agent_learning.json"
    learning = LearningLoop(state_path=agent_state,
                            events_path=ROOT / "state"
                            / "house_agent_learning_events.jsonl", persist=True)
    zone = ROOT / "house_workspace"
    zone.mkdir(exist_ok=True)
    sb = Sandbox(project_root=str(ROOT), workzone=str(zone),
                 auto_approve_writes=True)
    solver = LocalSolver(verifier=LanguageVerifier(), learning=learning,
                         sandbox=sb, min_confidence=0.7, trial_floor=0.35)
    router = FastRouter(local_solver=solver, reasoning_agent=None,
                        replay_confidence=0.9)
    oracle = None
    if use_oracle:
        try:
            from organs.api_oracle import oracle_from_config
            cfg = json.loads((ROOT / "config" / "hybrid_config.json")
                             .read_text(encoding="utf-8"))
            o = oracle_from_config(cfg)
            oracle = o if o.has_key else None
        except Exception:
            oracle = None
    try:
        from tools import _experience
    except Exception:
        _experience = None
    if _experience is not None:
        sb.on_run = lambda name, ok: _experience.ran(str(name), bool(ok))
    return router, solver, learning, sb, oracle, _experience


def _check(sb, code: str, check: str, tag: str = "cur") -> dict:
    if not str(code or "").strip():
        return {"ran": False, "passed": False, "why": "no code"}
    name = "_%s_%d.py" % (tag, int(time.time() * 1000) % 10 ** 8)
    try:
        r = sb.run_python(str(code) + "\n\n" + str(check), timeout=25, name=name)
    except Exception as e:
        return {"ran": False, "passed": False, "why": str(e)[:100]}
    ok = bool(r.get("success", r.get("ok", False))) and \
        int(r.get("returncode", r.get("exit_code", 0)) or 0) == 0
    return {"ran": True, "passed": ok,
            "why": None if ok else str(r.get("stderr") or r.get("output")
                                       or "")[-140:].strip()}


def run(split: str = "train", limit: int | None = None, use_gold: bool = True,
        use_oracle: bool = False, learn: bool = True) -> dict:
    from tools.make_curriculum import load
    rows = load(split)
    if limit:
        rows = rows[:int(limit)]
    router, solver, learning, sb, oracle, exp = _build(use_oracle)
    counts = {"local": 0, "composed": 0, "corpus": 0, "oracle": 0,
              "failed": 0}
    detail = []
    t0 = time.time()
    for r in rows:
        task, check = r["task"], r["check"]
        if exp is not None:
            exp.tries(task)
        route, src, code, verdict = "none", None, "", None
        comp = {}
        # 1. his own: recall, then let the failure name the interface it wanted.
        try:
            out = router.run(task)
            route = str(out.get("route_path") or "?")
            code = str(out.get("solution") or "")
            verdict = _check(sb, code, check)
            if verdict["passed"]:
                src = "local"
            elif code.strip():
                rp = solver.repair_against(code, check)
                if rp.get("ok"):
                    code, verdict, src = rp["code"], _check(sb, rp["code"], check), "local"
        except Exception as e:
            verdict = {"ran": False, "passed": False, "why": str(e)[:90]}
        # 1b. composition, from the verified library. This is the rung that is
        # supposed to generalise, so the held-out slice gets it too -- composing his
        # own procedures is his own work, unlike a gold solution.
        if src is None:
            try:
                comp = solver.compose_against(task, check, budget=8) or {}
                if comp.get("ok"):
                    code = comp["code"]
                    src = "composed"
                    verdict = {"ran": True, "passed": True, "why": None}
            except Exception as e:
                comp = {"ok": False, "reason": f"{type(e).__name__}"[:60]}
        # 2. the corpus, verified by the task's own tests before anything is kept.
        #    Never on the held-out slice, which is the whole point of reserving it.
        if src is None and use_gold and split != "holdout" and \
                r.get("gold", "").strip():
            g = _check(sb, r["gold"], check)
            if g["passed"]:
                code, verdict, src = r["gold"], g, "corpus"
        # 3. the model, last, and gated identically.
        if src is None and oracle is not None:
            try:
                from tools.task_battery import _ask_oracle
                o = _ask_oracle(oracle, task, check, sb)
                if o.get("ok"):
                    code, src = o["code"], "oracle"
                    verdict = _check(sb, code, check)
            except Exception:
                pass
        counts[src or "failed"] += 1
        stored = False
        if learn and src and split != "holdout" and verdict and verdict["passed"]:
            try:
                learning.learn_from_task(task, code, {
                    "source": src, "verified": True, "language": "python",
                    "verifier_kind": "task_check"}, verified=True)
                stored = True
            except Exception:
                pass
        if exp is not None and split != "holdout":
            exp.outcome(task, bool(verdict and verdict["passed"]))
        detail.append({"id": r["id"], "source": src or "failed", "route": route,
                       "stored": stored, "why": (verdict or {}).get("why"),
                       "compose": (comp or {}).get("method") if src == "composed"
                       else (comp or {}).get("reason"),
                       "static_rejects": (comp or {}).get("static_rejections")})
    el = max(1e-9, time.time() - t0)
    total = len(rows)
    passed = total - counts["failed"]
    return {"split": split, "tasks": total, "passed": passed,
            "pass_rate": round(passed / max(1, total), 3),
            "sources": counts, "seconds": round(el, 1),
            "per_task_s": round(el / max(1, total), 2),
            "stored_procedures": sum(1 for d in detail if d["stored"]),
            "library_size": len(learning.store),
            "composed_how": [d["compose"] for d in detail
                             if d["source"] == "composed"][:8],
            "compose_rejections": [d["compose"] for d in detail
                                   if d["source"] == "failed"
                                   and d.get("compose")][:6],
            "note": ("holdout: measured only, never learned from"
                     if split == "holdout" else
                     "train: candidates stored through the task_check gate"),
            "failures": [d for d in detail if d["source"] == "failed"][:6]}


def _loop_agent():
    """A headless being, offline, with the live library and its own connectome.

    The reasoning loop needs the language organ (that is where the goal-conditioned
    head and the held goal live) and the engine (whose decide() sets the eligibility
    trace), so it cannot be built from a bare solver. Offline so nothing escalates to
    a provider: the number this measures is what the search does on its own.
    """
    os.environ.setdefault("HYBRIDLLM_OFFLINE", "1")
    from world.connectome_house import build_house_agent
    cfg = {"model": {"api_key": None, "provider": "qwen"},
           # POINT THE TOOL AT THE BEING'S ACTUAL BRAIN.
           # `build_house_agent` sets the agent's own state to state/house_agent.json, which
           # is NOT the library default, and `_mental_state_paths` therefore resolves a
           # configured language path to `<agent_state_dir>/<name>` -- i.e. exactly the file
           # the live house uses. Omitting the language block (as this cfg used to) makes it
           # fall back to `state/house_agent_language_state.json`, A FILE THAT DOES NOT
           # EXIST, so every tool here ran with an EMPTY binder: 0 propositions against the
           # being's 60,000. Every fact-store, transfer and role-recovery number produced by
           # these tools was therefore about a blank head, not about him.
           # READ-ONLY: persist=False below, and `_forbid_writes` replaces the write path
           # itself, because a flag is not a guard. See Invariant #1.
           "language": {"auto_train": False,
                        "state_path": str(ROOT / "state" / "language_state.json")},
           "connectome": {"accelerated_life": False},
           "sandbox": {"auto_approve_writes": True},
           "house": {"enabled": False}}
    agent = build_house_agent(cfg, project_root=str(ROOT))
    # A tool rooted at the project root SHARES the being's language state path, and
    # when it saved it wrote its own small binder over the live one: 30,091
    # propositions became 86, with no error anywhere, because the save succeeded and
    # the load of the smaller file also succeeded. A tool may READ his state; it must
    # never write it. persist=False keeps the read and forbids the write.
    # A TOOL MAY READ HIS STATE AND MUST NEVER WRITE IT. Only the language organ was
    # guarded here, and the LEARNING LOOP was not -- so any probe that called
    # learn_from_task wrote straight into the live library. One did: it appended an ORACLE
    # solution to a real record and moved the procedure count, and an oracle solution in
    # the store is exactly the contamination the three-column rule exists to prevent. The
    # guard now covers both, because a guard on some fields of an object is not a guard on
    # the object.
    for _name in ("language", "learning_loop"):
        _o = getattr(agent, _name, None)
        if _o is not None:
            try:
                _o.persist = False
            except Exception:
                pass
    _forbid_writes(agent)
    for name in ("heartbeat", "autotraining", "neural_growth"):
        organ = getattr(agent, name, None)
        if organ is not None and hasattr(organ, "stop"):
            try:
                organ.stop()
            except Exception:
                pass
    _warn_if_brain_is_blank(agent)
    return agent


def _make_refusal(organ, meth):
    def _refused(*a, **k):
        print("READ-ONLY GUARD: refused %s.%s() -- a tool may READ the being's state and "
              "must never WRITE it." % (type(organ).__name__, meth))
        return {"saved": False,
                "reason": "read-only tool agent: write refused by _forbid_writes"}
    return _refused


def _forbid_writes(agent) -> list:
    """Make a read-only tool organ MECHANICALLY unable to write itself.

    `persist=False` is a convention, and Invariant #1 is the story of what a convention
    is worth here: a tool rooted at the project root saved its own small binder over the
    live one and 30,091 propositions became 86 with `load_error: None` and
    `last_error: None`, because the save succeeded and so did the load of the smaller
    file. Nothing raised. A flag that is set once and never re-read is not a guard.

    So the write path itself is replaced. This matters more now than it did yesterday:
    the tools read the REAL 5.8 MB / 344 MB state, so the blast radius of getting this
    wrong is the being's whole memory rather than a throwaway file.

    Returns the list of methods it replaced, so a caller (or a test) can assert the guard
    is actually installed rather than assumed.
    """
    lang = getattr(agent, "language", None)
    organs = [lang,
              getattr(lang, "cortex", None),
              getattr(lang, "sequence", None),
              getattr(agent, "learning_loop", None)]
    guarded = []
    for organ in organs:
        if organ is None:
            continue
        for meth in ("save_state", "save", "flush"):
            fn = getattr(organ, meth, None)
            if fn is None or not callable(fn):
                continue
            try:
                setattr(organ, meth, _make_refusal(organ, meth))
                guarded.append("%s.%s" % (type(organ).__name__, meth))
            except Exception:
                pass
    return guarded


def _warn_if_brain_is_blank(agent) -> bool:
    """Say so when the tool is measuring a head with nothing in it.

    The guard is not cosmetic. Every tool here builds its agent from a MINIMAL cfg that
    omits the language block, so the organ falls back to
    `state/house_agent_language_state.json` -- a file that DOES NOT EXIST. The tool
    therefore runs with an empty binder: 0 propositions against the being's 60,000.

    Separating tool state from his is deliberate and correct (a tool may READ his state
    and must never WRITE it), but silence is not: a transfer verdict or a role-recovery
    number computed over an empty binder looks exactly like a result about him. This is
    the same shape as the collapsed candidate pool that made `binding` read 0.0 by
    construction -- an answer to a question nobody asked.

    Returns True when the brain is blank.
    """
    try:
        cortex = getattr(getattr(agent, "language", None), "cortex", None)
        held = int(getattr(cortex.binder, "X", None).shape[0]) if cortex is not None else 0
        where = getattr(getattr(agent, "language", None), "state_path", None)
    except Exception:
        return False
    if held:
        print("tool agent: %s propositions loaded READ-ONLY from %s" % (f"{held:,}", where))
        return False
    print("NOTE: this tool is measuring an EMPTY binder (0 propositions). Tools build a "
          "separate, non-existent state file (state/house_agent_language_state.json), so "
          "anything read from the binder here -- facts, role recovery, transfer -- is "
          "about a blank head, not about the being (60,000 propositions).")
    return True


def run_loop(split: str = "holdout", limit: int | None = None,
             learn: bool = False, source: str | None = None) -> dict:
    """Measure the search itself: the reasoning loop, per task, no other source."""
    from tools.make_curriculum import load
    rows = load(split, source=source)
    if limit:
        rows = rows[:int(limit)]
    agent = _loop_agent()
    loop = agent.reasoning_loop
    counts = {"solved": 0, "refused": 0, "no_candidates": 0, "below_floor": 0}
    detail = []
    t0 = time.time()
    for r in rows:
        out = loop.step(r["task"], r["check"], learn=(learn and split != "holdout"))
        o = out.get("outcome", "?")
        counts[o] = counts.get(o, 0) + 1
        detail.append({"id": r["id"], "outcome": o,
                       "candidate": out.get("candidate"),
                       "attempts": out.get("attempts"),
                       "pred": out.get("best_pred")})
    el = max(1e-9, time.time() - t0)
    head = None
    if getattr(agent.language, "cortex", None) is not None:
        head = getattr(agent.language.cortex, "outcome", None)
    return {"split": split, "tasks": len(rows),
            "solved": counts.get("solved", 0),
            "solve_rate": round(counts.get("solved", 0) / max(1, len(rows)), 3),
            "outcomes": counts, "seconds": round(el, 1),
            "per_task_s": round(el / max(1, len(rows)), 2),
            "outcome_head": head.stats() if head is not None else None,
            "solved_by": [d["candidate"] for d in detail
                          if d["outcome"] == "solved"][:12],
            "refused": [d["id"] for d in detail
                        if d["outcome"] == "refused"][:8],
            "note": ("held out: never learned from, measured only"
                     if split == "holdout" else "train slice")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="train", choices=["train", "holdout"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-gold", action="store_true")
    ap.add_argument("--oracle", action="store_true")
    ap.add_argument("--no-learn", action="store_true")
    ap.add_argument("--loop", action="store_true",
                    help="measure the reasoning loop alone, per task")
    ap.add_argument("--source", default=None, choices=["mbpp", "exercism"],
                    help="which curriculum; mbpp by default so its number stays comparable")
    a = ap.parse_args()
    if a.loop:
        print(json.dumps(run_loop(a.split, a.limit, not a.no_learn, a.source),
                         indent=1))
        return 0
    out = run(a.split, a.limit, not a.no_gold, a.oracle, not a.no_learn)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
