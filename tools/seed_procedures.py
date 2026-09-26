"""Seed the procedure library from code that already runs.

The coding path was complete except for its contents. The router prefers a
learned procedure, the local solver can compose patterns and refuses to hand back
an unverified paste, and learning is now gated on execution -- but the library had
never held a single entry, because the only caller of learn_from_task sat on the
API path. An empty library means every task is novel, which means the 90% has
nothing to stand on.

Cold start, honestly labelled. The seed is his own source: functions with a
docstring, which is to say code that says what task it answers. Each candidate is
gated on compilation, keyed by the signature the recall path actually uses, and
recorded with provenance (file and line) and `verified: False`. Nothing here
claims to have been run.

Confidence starts at the same 0.35 any new record gets -- being innate earns no
privilege. Promotion comes from tools/practice.py executing the code and reporting
back, and only execution moves it. The default recall floor is 0.70, so a seeded
procedure is *present* but not *trusted* until it has passed under him.

Usage:
    python tools/seed_procedures.py            # seed and report
    python tools/seed_procedures.py --dry-run  # report only, write nothing
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from organs.learning_loop import LearningLoop, signature  # noqa: E402

# The live agent does not use the module default. reasoning_agent builds its loop
# with state_path=<root>/state/house_agent_learning.json, so seeding the default
# exocortex path fills a library he never reads -- which is exactly what happened
# first: 274 procedures on disk, one visible from inside the house.
AGENT_STATE = ROOT / "state" / "house_agent_learning.json"
AGENT_EVENTS = ROOT / "state" / "house_agent_learning_events.jsonl"

SCAN = ("organs", "world", "connectome", "server", "tools")
MIN_DOC_WORDS = 5
MIN_CODE_CHARS = 120
# A truncated procedure is worse than no procedure: it is broken code presented as
# a solution, and it compiles or fails at random depending on where the cut fell.
# The gate below compiles the full source, so storing a prefix of it silently
# invalidated the gate -- 11 of the first 275 seeds did not parse. Anything over
# the cap is skipped whole.
MAX_CODE_CHARS = 32000


def _first_sentence(doc: str) -> str:
    """The task a function answers, in the words its own author used."""
    text = " ".join(str(doc or "").split())
    if not text:
        return ""
    # stop at the first sentence end that is not inside an abbreviation
    for i, ch in enumerate(text):
        if ch == "." and (i + 1 >= len(text) or text[i + 1] == " "):
            return text[:i].strip()
    return text.strip()


def _task_text(name: str, doc: str) -> str:
    s = _first_sentence(doc)
    words = s.split()
    if len(words) < MIN_DOC_WORDS:
        return ""
    return s


def candidates() -> list[dict]:
    out: list[dict] = []
    for folder in SCAN:
        base = ROOT / folder
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if "test" in path.name or "__pycache__" in rel:
                continue
            try:
                src = path.read_text(encoding="utf-8")
                tree = ast.parse(src)
            except (OSError, SyntaxError, ValueError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                doc = ast.get_docstring(node) or ""
                task = _task_text(node.name, doc)
                if not task:
                    continue
                try:
                    code = ast.get_source_segment(src, node) or ""
                except Exception:
                    continue
                if len(code) < MIN_CODE_CHARS or len(code) > MAX_CODE_CHARS:
                    continue
                try:
                    compile(code, f"<seed {rel}:{node.lineno}>", "exec")
                except SyntaxError:
                    continue
                sig = signature(task)
                if not sig or sig == "general":
                    continue
                args = [str(a.arg) for a in getattr(node.args, "args", [])
                        if str(a.arg) not in ("self", "cls")]
                name_words = node.name.strip("_").replace("_", " ")
                out.append({"signature": sig, "task": task, "code": code,
                            "name": node.name, "file": rel,
                            "line": int(node.lineno),
                            "args": args, "name_words": name_words,
                            "chars": len(code)})
    return out


def _best_by_signature(rows: list[dict]) -> dict:
    """One procedure per signature: the fullest code that answers it.

    Several functions can describe the same task. Keeping the longest body is a
    crude tie-break but a defensible one -- a stub and its implementation share a
    signature, and the implementation is the one worth replaying.
    """
    best: dict[str, dict] = {}
    for r in rows:
        cur = best.get(r["signature"])
        if cur is None or r["chars"] > cur["chars"]:
            best[r["signature"]] = r
    return best


def seed(dry_run: bool = False, state_path: Path | None = None) -> dict:
    rows = candidates()
    chosen = _best_by_signature(rows)
    loop = LearningLoop(state_path=state_path or AGENT_STATE,
                        events_path=AGENT_EVENTS, persist=not dry_run)
    now = time.time()
    added = skipped = 0
    alias_total = 0
    for sig, r in sorted(chosen.items()):
        if sig in loop.store or sig in loop.discarded:
            skipped += 1
            continue
        # A procedure is findable by three surfaces, because a request matches
        # different ones at different times: what its docstring says, what it is
        # called, and what it takes. Keying on the docstring alone lost every
        # probe -- revise_plan is documented as "abandon the local approach when
        # the caller fails", which shares not one word with its own name.
        aliases = sorted({sig,
                          signature(r["name_words"]),
                          signature(r["name_words"] + " " + " ".join(r["args"]))})
        aliases = [a for a in aliases if a and a != "general"]
        alias_total += len(aliases)
        loop.store[sig] = {
            "signature": sig, "task": r["task"][:300], "tries": 0,
            "successes": 0, "failures": 0, "confidence": 0.35,
            "aliases": aliases,
            "solutions": [{"text": r["code"], "verified": False,
                           "ts": now}],
            "source": "innate", "created": now, "language": "python",
            "provenance": {"file": r["file"], "line": r["line"],
                           "function": r["name"],
                           "verifier_kind": "compile",
                           "note": "seeded from his own source; not yet run"},
        }
        added += 1
    if not dry_run:
        loop.save()
        loop._event("seeded", {"added": added, "skipped_existing": skipped,
                               "candidates": len(rows),
                               "distinct_signatures": len(chosen)})
    return {"dry_run": dry_run, "candidates": len(rows),
            "distinct_signatures": len(chosen), "added": added,
            "skipped_existing": skipped,
            "aliases_per_procedure": round(alias_total / max(1, added), 2),
            "library_size": len(loop.store),
            "recallable_at_default_floor": sum(
                1 for v in loop.store.values()
                if float(v.get("confidence", 0)) >= loop.min_confidence),
            "min_confidence": loop.min_confidence,
            "state_file": str(loop.state_path)}


def repair() -> dict:
    """Re-extract stored code from source and drop what still will not parse.

    The first seed stored a 6,000 character prefix of each function after gating
    on the whole of it, so the library held procedures that could not compile. This
    reads each record's provenance, takes the current source of that function, and
    replaces the stored text -- or discards the record if the source is gone or the
    result still does not parse. Confidence is left alone: the evidence about
    whether it ran is untouched by a change in how much of it was kept.
    """
    loop = LearningLoop(state_path=AGENT_STATE, events_path=AGENT_EVENTS,
                        persist=True)
    src_by_file: dict = {}
    spans: dict = {}
    fixed = dropped = intact = missing = 0
    for sig, rec in list(loop.store.items()):
        prov = rec.get("provenance") or {}
        rel, line = str(prov.get("file") or ""), int(prov.get("line") or 0)
        if not rel or not line:
            intact += 1
            continue
        p = ROOT / rel
        if not p.exists():
            missing += 1
            continue
        if rel not in src_by_file:
            try:
                src_by_file[rel] = p.read_text(encoding="utf-8")
                spans[rel] = {}
                for node in ast.walk(ast.parse(src_by_file[rel])):
                    if isinstance(node, (ast.FunctionDef,
                                           ast.AsyncFunctionDef)):
                        spans[rel][int(node.lineno)] = node
            except (OSError, SyntaxError, ValueError):
                src_by_file[rel] = ""
        node = (spans.get(rel) or {}).get(line)
        if node is None:
            # Line numbers drift the moment anyone edits the file, and provenance
            # recorded a line. Fall back to the function name, which is why the
            # name was stored alongside it.
            want = str(prov.get("function") or "")
            if want:
                for cand in (spans.get(rel) or {}).values():
                    if cand.name == want:
                        node = cand
                        break
        if node is None or not src_by_file.get(rel):
            missing += 1
            continue
        code = ast.get_source_segment(src_by_file[rel], node) or ""
        if not code or len(code) > MAX_CODE_CHARS:
            loop.store.pop(sig, None)
            dropped += 1
            continue
        try:
            compile(code, f"<repair {rel}:{line}>", "exec")
        except SyntaxError:
            loop.store.pop(sig, None)
            dropped += 1
            continue
        sols = rec.get("solutions") or []
        old = str(sols[-1].get("text", "")) if sols else ""
        if old == code:
            intact += 1
            continue
        if sols:
            sols[-1]["text"] = code
            sols[-1].pop("truncated", None)
        else:
            rec["solutions"] = [{"text": code, "verified": False,
                                 "ts": time.time()}]
        fixed += 1
    loop.save()
    loop._event("repaired", {"fixed": fixed, "dropped": dropped,
                             "intact": intact, "source_missing": missing})
    return {"fixed": fixed, "dropped": dropped, "intact": intact,
            "source_missing": missing, "library_size": len(loop.store)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--repair", action="store_true",
                    help="re-extract stored code from source; drop what will not parse")
    ap.add_argument("--state", default=None,
                    help="procedure store to fill; defaults to the live agent's")
    a = ap.parse_args()
    if a.repair:
        print(json.dumps(repair(), indent=1))
        return 0
    print(json.dumps(seed(a.dry_run,
                          Path(a.state) if a.state else None), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
