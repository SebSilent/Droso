"""
Why the held-out set went 0/10 -- per task, what each rung saw.

Read-only against the library: recall and pattern queries touch nothing, and
compose_against verifies candidates in the sandbox but stores nothing (a
composition that passes is returned, not learned -- that is the caller's
decision). So this trace can run against the live state without turning the
first-contact set into replay.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.task_battery import HELDOUT, _build            # noqa: E402


def main() -> int:
    router, solver, learning, sb = _build(True)
    out = []
    for entry in HELDOUT:
        task, check = entry["task"], entry["check"]
        label = " ".join(task.split()[:5])
        rec = None
        try:
            rec = solver.recall_procedure(task, min_confidence=0.35)
        except Exception as exc:
            rec = f"error {type(exc).__name__}"
        pats = []
        try:
            pats = solver.query_patterns(task)
        except Exception:
            pass
        route = router.route(task)
        comp = {}
        try:
            comp = solver.compose_against(task, check, budget=8) or {}
        except Exception as exc:
            comp = {"ok": False, "reason": f"{type(exc).__name__}: {exc}"[:80]}
        out.append({
            "id": label,
            "recall": (None if rec is None else
                       (f"conf={rec.confidence}" if hasattr(rec, "confidence")
                        else str(rec))),
            "patterns": len(pats),
            "route": route["path"],
            "route_reason": route["reason"],
            "compose_ok": bool(comp.get("ok")),
            "compose_reason": str(comp.get("reason") or "")[:90],
            "compose_tried": comp.get("tried"),
            "compose_rejects": comp.get("static_rejections") or {},
        })
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())