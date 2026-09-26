"""Track H: branches, and the control that decides what the branching bought.

The alien claim is that pooling lifetimes compounds: several lives, each on a
different problem, merged into one library that knows what none of them knew alone.
The thing that claim usually is not is *pooling* -- the same total exposure delivered
through one life instead of several. Those two produce the same number of solved
problems and different libraries, and the only way to tell them apart is to run both
with matched compute.

So this builds:

    branches   N individuals, each on a DISJOINT slice of the training tasks
    control    ONE individual on the union of those same slices, same total tasks

Then it merges the branches and puts merged and control against the held-out set. The
verdict is one of two, and both are results:

    merge passes, control fails   compounding -- the branch structure bought something
    both pass                     pooling, not compounding -- the structure added
                                  nothing the control's equal compute did not already get
    neither passes                the exposure itself is the limit

What gets merged is not just vocabulary and weights. Procedures are unioned with their
evidence, compositions are carried as procedures in their own right, and the loop's
search traces -- which candidate was tried, which surprised, which passed -- travel
with them, because the order a life learned to try things in is knowledge too.

Every arm keeps its own store file, so no arm can overwrite another's memory. That is
the single-writer rule applied to the experiment itself.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

H_DIR = ROOT / "state" / "h"


def _arm(name: str) -> Path:
    H_DIR.mkdir(parents=True, exist_ok=True)
    return H_DIR / f"{name}.json"


def _track(task_id: str, n: int) -> int:
    """Disjoint slices by hash -- the same id always lands in the same track."""
    h = int(hashlib.blake2b(str(task_id).encode(), digest_size=4).hexdigest(), 16)
    return h % max(1, int(n))


def _learn_arm(name: str, tasks: list, fresh: bool = True) -> dict:
    """One life: work a set of tasks, keep what passes the gate, in its own store."""
    from organs.local_solver import LocalSolver
    from organs.learning_loop import LearningLoop
    from organs.language_verifier import LanguageVerifier
    from organs.sandbox import Sandbox

    path = _arm(name)
    if fresh and path.exists():
        path.unlink()
    learning = LearningLoop(state_path=path, persist=True)
    zone = ROOT / "house_workspace"
    zone.mkdir(exist_ok=True)
    sb = Sandbox(project_root=str(ROOT), workzone=str(zone),
                 auto_approve_writes=True)
    solver = LocalSolver(verifier=LanguageVerifier(), learning=learning,
                         sandbox=sb, min_confidence=0.7, trial_floor=0.35)
    counts = {"local": 0, "composed": 0, "corpus": 0, "failed": 0}
    t0 = time.time()
    for r in tasks:
        task, check = r["task"], r["check"]
        code, src = "", None
        rec = solver.recall_procedure(task)
        if rec is not None:
            code = str(getattr(rec, "solution", "") or "")
            ok, _ = solver._verify_detail(code + "\n\n" + check, check)
            if ok:
                src = "local"
        if src is None:
            rp = solver.repair_against(code, check) if code.strip() else {}
            if rp.get("ok"):
                code, src = rp["code"], "local"
        if src is None:
            try:
                comp = solver.compose_against(task, check, budget=6) or {}
            except Exception:
                comp = {}
            if comp.get("ok"):
                code, src = comp["code"], "composed"
        if src is None and r.get("gold", "").strip():
            ok, _ = solver._verify_detail(r["gold"] + "\n\n" + check, check)
            if ok:
                code, src = r["gold"], "corpus"
        counts[src or "failed"] += 1
        if src:
            try:
                learning.learn_from_task(task, code, {
                    "source": src, "verified": True, "language": "python",
                    "verifier_kind": "task_check"}, verified=True)
            except Exception:
                pass
    learning.save()
    return {"arm": name, "tasks": len(tasks), "sources": counts,
            "library": len(learning.store),
            "trusted": sum(1 for r in learning.store.values()
                           if float(r.get("confidence", 0)) >= 0.70),
            "seconds": round(time.time() - t0, 1), "store": str(path)}


def _merge(sources: list, out_name: str) -> dict:
    """Union procedures with their evidence, keeping the stronger record."""
    from organs.learning_loop import LearningLoop
    out = LearningLoop(state_path=_arm(out_name), persist=True)
    out.store = {}
    adopted = 0
    for p in sources:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        for sig, rec in (d.get("procedures") or {}).items():
            cur = out.store.get(sig)
            if cur is None:
                out.store[sig] = rec
            else:
                # Same signature from two lives: keep the higher confidence and the
                # evidence that came with it. Evidence does not average.
                if float(rec.get("confidence", 0)) > float(cur.get("confidence", 0)):
                    out.store[sig] = rec
                    adopted += 1
    out.save()
    return {"merged": out_name, "library": len(out.store),
            "upgraded": adopted, "store": str(_arm(out_name))}


def _eval(store: str, tasks: list) -> dict:
    """What a library can do on tasks it has never seen: recall and compose only."""
    from organs.local_solver import LocalSolver
    from organs.learning_loop import LearningLoop
    from organs.language_verifier import LanguageVerifier
    from organs.sandbox import Sandbox
    learning = LearningLoop(state_path=Path(store), persist=True)
    zone = ROOT / "house_workspace"
    zone.mkdir(exist_ok=True)
    sb = Sandbox(project_root=str(ROOT), workzone=str(zone),
                 auto_approve_writes=True)
    solver = LocalSolver(verifier=LanguageVerifier(), learning=learning,
                         sandbox=sb, min_confidence=0.7, trial_floor=0.35)
    solved = 0
    how = {"local": 0, "composed": 0}
    for r in tasks:
        task, check = r["task"], r["check"]
        code = ""
        rec = solver.recall_procedure(task)
        if rec is not None:
            code = str(getattr(rec, "solution", "") or "")
            ok, _ = solver._verify_detail(code + "\n\n" + check, check)
            if ok:
                solved += 1
                how["local"] += 1
                continue
        if code.strip():
            rp = solver.repair_against(code, check)
            if rp.get("ok"):
                ok, _ = solver._verify_detail(rp["code"] + "\n\n" + check, check)
                if ok:
                    solved += 1
                    how["local"] += 1
                    continue
        try:
            comp = solver.compose_against(task, check, budget=6) or {}
        except Exception:
            comp = {}
        if comp.get("ok"):
            solved += 1
            how["composed"] += 1
    return {"store": store, "tasks": len(tasks), "solved": solved,
            "rate": round(solved / max(1, len(tasks)), 3), "how": how}


def run(arms: int = 3, per_arm: int = 30, eval_limit: int | None = None) -> dict:
    from tools.make_curriculum import load
    train = load("train")
    holdout = load("holdout")
    if eval_limit:
        holdout = holdout[:int(eval_limit)]
    # Disjoint slices; every train task belongs to exactly one branch.
    slices = [[] for _ in range(int(arms))]
    for r in train:
        slices[_track(r["id"], arms)].append(r)
    slices = [s[:int(per_arm)] for s in slices]
    union = [t for s in slices for t in s]
    out = {"arms": int(arms), "per_arm": int(per_arm),
           "union_tasks": len(union), "holdout_tasks": len(holdout),
           "branch_results": [], "note": "control sees the same union, one life"}
    for i, s in enumerate(slices):
        out["branch_results"].append(_learn_arm(f"branch{i}", s))
    out["control_result"] = _learn_arm("control", union)
    out["merge"] = _merge([b["store"] for b in out["branch_results"]], "merged")
    out["eval_control"] = _eval(out["control_result"]["store"], holdout)
    out["eval_merged"] = _eval(out["merge"]["store"], holdout)
    c, m = out["eval_control"]["solved"], out["eval_merged"]["solved"]
    n = max(1, len(holdout))
    # FIRST ASK WHETHER THERE WAS ANYTHING TO DIVIDE. If every arm answered from the
    # corpus, then every arm learned the same kind of procedure, the merge just unions
    # copies of the corpus, and the comparison is a corpus-union against the same corpus
    # split three ways. That is exactly what the first complete run did -- 97-100% of each
    # arm's solutions came from the corpus with local at zero -- so there was no branch
    # structure in it to measure, and a "compounding" verdict was printed off two tasks
    # that had nothing to do with the branches. Lives have nothing to divide when the
    # corpus already covers the work, and that is a result about the corpus, not about
    # the arrangement of lives. This has to outrank any verdict, because a verdict about
    # an experiment that did not happen is worse than no verdict.
    novel = sum(int(b["sources"].get("local", 0)) + int(b["sources"].get("composed", 0))
                for b in out["branch_results"])
    out["arm_novel_solutions"] = novel
    if novel < 2:
        out["verdict"] = ("vacuous: the arms did not diverge (%d local/composed "
                          "solutions between them) -- the corpus answered for every "
                          "life, so the branches had no work of their own to do and "
                          "nothing was tested about splitting work across lives" % novel)
        return out
    # Both arms are evaluated on the SAME held-out tasks, so the honest null is that the
    # two libraries are equal and any difference is sampling. The old rule was "m > c",
    # and it declared "compounding" on 3 against 1 out of 98 -- two tasks at a solve rate
    # near 2%, about one standard error. Printing that as a finding is the same mistake
    # as quoting a transient peak as a steady state: a sample reported as a property. The
    # verdict now has to clear the noise band before it is allowed to be a verdict.
    p1, p2 = m / n, c / n
    se = math.sqrt(p1 * (1 - p1) / n + p2 * (1 - p2) / n) * n
    out["delta"] = m - c
    out["noise_band_tasks"] = round(se, 1)
    out["z"] = round((p1 - p2) / (se / n), 2) if se > 0 else 0.0
    if abs(out["z"]) < 2.0:
        out["verdict"] = ("within noise: no verdict (%d vs %d on %d, need %.1f tasks)"
                          % (m, c, n, 2 * se))
    elif m > c:
        out["verdict"] = "compounding"
    elif m == c:
        out["verdict"] = "pooling, not compounding"
    else:
        out["verdict"] = "merge worse than control"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", type=int, default=3)
    ap.add_argument("--per-arm", type=int, default=30)
    ap.add_argument("--eval-limit", type=int, default=None,
                    help="cap the held-out slice used for the verdict")
    a = ap.parse_args()
    print(json.dumps(run(a.arms, a.per_arm, a.eval_limit), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
