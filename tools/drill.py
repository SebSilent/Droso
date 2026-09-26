"""Drive the coding path end to end and report whether the loop closes.

Everything upstream of this was measured in isolation: retrieval finds a procedure
(84% by name, 100% by paraphrase), the store promotes on a verified run, the router
now tries what it does not yet trust. None of that proves the circuit is complete,
because until now no request had ever travelled the whole way -- recall, trial,
execution, verdict, promotion.

Requests are drawn from the library itself but never in its own words: each
procedure's task text with its rarest word struck out, which is how a person asks
who does not know the term of art. The answer is either a replay he trusted, a
trial he ran and kept, a trial he ran and dropped, or nothing -- and only the last
is a gap.

It works on a COPY of the store. The live individual holds his library in memory
and saves over it, so drilling him in place would have the results discarded by the
next snapshot.

Usage:
    python tools/drill.py --limit 40
    python tools/drill.py --limit 40 --no-sandbox   # syntax check only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LIVE = ROOT / "state" / "house_agent_learning.json"


def _solver(store_path: Path, use_sandbox: bool):
    from organs.local_solver import LocalSolver
    from organs.learning_loop import LearningLoop
    from organs.language_verifier import LanguageVerifier
    learning = LearningLoop(state_path=store_path, persist=True)
    verifier = LanguageVerifier()
    sandbox = None
    if use_sandbox:
        try:
            from organs.sandbox import Sandbox
            zone = ROOT / "house_workspace"
            zone.mkdir(exist_ok=True)
            sandbox = Sandbox(project_root=str(ROOT), workzone=str(zone),
                              auto_approve_writes=True)
        except Exception as e:
            sandbox = None
            print("  (no sandbox: %s)" % str(e)[:80])
    return LocalSolver(verifier=verifier, learning=learning, sandbox=sandbox,
                       min_confidence=0.7, trial_floor=0.35), learning


def _requests(learning, limit: int) -> list:
    """Task text with its rarest word removed -- a phrasing the key never used."""
    from organs.learning_loop import _stem
    n = max(1, len(learning.store))
    df: dict = {}
    for sig in learning.store:
        for w in set(str(sig).split()):
            df[w] = df.get(w, 0) + 1
    out = []
    for sig, rec in learning.store.items():
        task = str(rec.get("task") or "")
        words = re.findall(r"[a-z_][a-z_0-9]{3,}", task.lower())
        if len(words) < 5:
            continue
        rarest = min(words, key=lambda w: df.get(_stem(w), 0))
        ask = " ".join(w for w in words if w != rarest)
        if len(ask.split()) >= 3:
            out.append({"ask": ask, "signature": sig, "dropped": rarest,
                        "confidence": float(rec.get("confidence", 0))})
        if len(out) >= limit:
            break
    return out


def drill(limit: int, use_sandbox: bool, live: bool = False) -> dict:
    work = LIVE if live else ROOT / "state" / "drill_store.json"
    if not live:
        shutil.copy(LIVE, work)
    solver, learning = _solver(work, use_sandbox)
    from organs.fast_router import FastRouter
    from organs.fast_router import (PROCEDURE_REPLAY, TRIAL_REPLAY,
                                    REASONING_LOOP, COMPOSITION, DIRECT_API)
    router = FastRouter(local_solver=solver, reasoning_agent=None,
                        replay_confidence=0.9)
    reqs = _requests(learning, limit)
    before = {k: float(v.get("confidence", 0)) for k, v in learning.store.items()}
    tally = {"trusted_replay": 0, "trial_kept": 0, "trial_dropped": 0,
             "no_recall": 0}
    evidence: dict = {}
    examples = []
    t0 = time.time()
    for q in reqs:
        rec = solver.recall_procedure(q["ask"])
        if rec is None:
            tally["no_recall"] += 1
            continue
        out = router.run(q["ask"])
        path = out.get("route_path")
        if path == PROCEDURE_REPLAY:
            tally["trusted_replay"] += 1
        elif path == TRIAL_REPLAY:
            if out.get("trial_verified") is False:
                tally["trial_dropped"] += 1
            else:
                tally["trial_kept"] += 1
        learn = router.last_learn or {}
        k = str(learn.get("evidence") or "none")
        evidence[k] = evidence.get(k, 0) + 1
        if len(examples) < 5:
            examples.append({"asked": q["ask"][:56], "path": path,
                             "trial_verified": out.get("trial_verified"),
                             "learned": learn.get("learned"),
                             "evidence": learn.get("evidence"),
                             "solution_chars": len(str(out.get("solution") or ""))})
    loop2 = type(learning)(state_path=work, persist=True)
    after = {k: float(v.get("confidence", 0)) for k, v in loop2.store.items()}
    moved = [(k, before.get(k, 0.0), after.get(k, 0.0)) for k in after
             if abs(after.get(k, 0.0) - before.get(k, 0.0)) > 1e-9]
    res = {"requests": len(reqs), "tally": tally,
           "evidence_kind": evidence,
           "sandbox": bool(use_sandbox and solver.sandbox is not None),
           "seconds": round(time.time() - t0, 1),
           "confidence_moved": len(moved),
           "up": sum(1 for _, b, a in moved if a > b),
           "down": sum(1 for _, b, a in moved if a < b),
           "recallable_at_0.70": sum(1 for v in after.values() if v >= 0.70),
           "library": len(after),
           "examples": examples,
           "store_copy": str(work)}
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--no-sandbox", action="store_true",
                    help="syntax check only; do not execute")
    ap.add_argument("--keep", action="store_true",
                    help="leave the drilled copy in place")
    ap.add_argument("--live", action="store_true",
                    help="drill the real store instead of a copy; only safe with "
                         "the house stopped, since a running house holds the "
                         "library in memory and saves over it")
    a = ap.parse_args()
    out = drill(a.limit, not a.no_sandbox, a.live)
    if not a.keep and not a.live:
        try:
            os.remove(out.pop("store_copy"))
        except OSError:
            pass
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
