"""Run the library, and let execution decide what he trusts.

Seeding puts procedures in the store at confidence 0.35 with `verified: False`.
Nothing promotes them but running them. This is that running.

The evidence is per-function and it is real: the test suite is executed under a
line tracer, and a procedure counts as verified only if a line inside its own body
actually ran. "The suite passed" is not evidence about a particular function --
most of a codebase is never called by its tests, and treating an uncalled function
as verified would be exactly the confident-wrong failure this gate exists to
prevent.

Promotion goes through learn_from_task, so it obeys the store's own arithmetic:
+0.15 per verified run, -0.25 per failure, recallable at 0.70. A seeded procedure
therefore needs three executions under him before the router will replay it
without asking anyone. That is the gate working, not a bug in it.

Also probes retrieval, which is the weak link in the whole local path: the store
is keyed by a signature of stems, so a task phrased differently has to land on the
same key. The probe asks for each procedure by its function name in words -- a
phrasing the docstring never used -- and reports how often recall still finds it.

Usage:
    python tools/practice.py             # verify + probe
    python tools/practice.py --no-tests  # probe only (no promotion)
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from organs.learning_loop import LearningLoop, signature, _stem  # noqa: E402

# Must match the store the live agent reads; see seed_procedures.py.
AGENT_STATE = ROOT / "state" / "house_agent_learning.json"
AGENT_EVENTS = ROOT / "state" / "house_agent_learning_events.jsonl"


def _span(path: Path) -> tuple:
    """(by_line, by_name) -> (first, last) line of each def in the file.

    By name as well as by line, because line numbers drift the first time anyone
    edits the file and the provenance recorded a line.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return {}, {}
    by_line, by_name = {}, {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            span = (int(node.lineno),
                    int(getattr(node, "end_lineno", node.lineno)))
            by_line[int(node.lineno)] = span
            by_name.setdefault(node.name, span)
    return by_line, by_name


class _PerTestTracer:
    """Attributes executed lines to the test that executed them.

    A whole-suite trace can say a function ran. It cannot say what proved it ran
    correctly, which is the only thing that makes "verified" mean more than
    "did not crash". Per-test attribution can: a function covered by a test that
    passed has been checked by someone, and a function covered only by tests that
    failed has not.
    """

    def __init__(self, root: str):
        self.root = root
        self.hits: dict = {}
        self.outcome: dict = {}
        self._cur = None

    def _trace(self, frame, event, arg):
        if event == "call":
            return self._trace
        if event == "line" and self._cur is not None:
            fn = frame.f_code.co_filename.replace("\\", "/")
            if fn.startswith(self.root) and "/tests/" not in fn:
                self.hits[self._cur].setdefault(fn, set()).add(frame.f_lineno)
        return self._trace

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item):
        self._cur = item.nodeid
        self.hits.setdefault(self._cur, {})
        sys.settrace(self._trace)
        try:
            yield
        finally:
            sys.settrace(None)
            self._cur = None

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        out = yield
        rep = out.get_result()
        if getattr(rep, "when", "") == "call":
            self.outcome[item.nodeid] = bool(getattr(rep, "passed", False))


def trace_tests() -> dict:
    """One suite run, traced per test node."""
    import contextlib
    import io
    t0 = time.time()
    tr = _PerTestTracer(ROOT.as_posix())
    buf = io.StringIO()
    try:
        # pytest writes to stdout and this tool's report is JSON on stdout;
        # without the redirect the two interleave and cannot be parsed.
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = pytest.main(["tests", "-q", "--no-header",
                              "--continue-on-collection-errors", "-p",
                              "no:cacheprovider"], plugins=[tr])
    finally:
        sys.settrace(None)
    executed: dict = {}
    for per in tr.hits.values():
        for f, lines in per.items():
            executed.setdefault(f, set()).update(lines)
    return {"hits": tr.hits, "outcome": tr.outcome, "executed": executed,
            "returncode": int(rc), "seconds": round(time.time() - t0, 1),
            "pytest_tail": [l for l in buf.getvalue().splitlines()
                            if l.strip()][-3:]}


def verify(loop: LearningLoop, tr: dict) -> dict:
    """Promote a procedure only where a test that PASSES exercised its body."""
    hits, outcome = tr["hits"], tr["outcome"]
    spans: dict = {}
    promoted = already = unexercised = failing_only = same_evidence = 0
    conf_before = {k: float(v.get("confidence", 0)) for k, v in loop.store.items()}
    covering_all: set = set()
    for sig, rec in list(loop.store.items()):
        prov = dict(rec.get("provenance") or {})
        rel = str(prov.get("file") or "")
        if not rel:
            continue
        line = int(prov.get("line") or 0)
        name = str(prov.get("function") or "")
        ap = (ROOT / rel).as_posix()
        if ap not in spans:
            spans[ap] = _span(ROOT / rel)
        by_line, by_name = spans[ap]
        got = by_line.get(line) or (by_name.get(name) if name else None)
        if got is None:
            continue
        first, last = got
        covering = [nid for nid, files in hits.items()
                    if any(first <= ln <= last
                           for ln in (files.get(ap) or ()))]
        if not covering:
            unexercised += 1
            continue
        passing = sorted(n for n in covering if outcome.get(n))
        if not passing:
            # Covered, but only by tests that fail. That is evidence about the
            # function and it is not favourable, so it earns nothing.
            failing_only += 1
            prov["covered_by_failing"] = sorted(covering)[:8]
            rec["provenance"] = prov
            continue
        covering_all.update(passing)
        if list(prov.get("covered_by") or []) == passing[:12]:
            # The same tests, covering the same body, passing again. That is the
            # same evidence and not new evidence, so it earns nothing. Without this
            # a loop of practice runs would walk every procedure to the recall
            # floor on information it already had -- and the arithmetic would look
            # like growing trust while nothing was being learned.
            same_evidence += 1
            continue
        if float(rec.get("confidence", 0)) >= loop.min_confidence:
            already += 1
        prov["covered_by"] = passing[:12]
        prov["verifier_kind"] = "test_covered"
        rec["provenance"] = prov
        loop.learn_from_task(rec.get("task") or sig,
                             _best_text(rec),
                             {"source": "pytest", "verified": True,
                              "language": rec.get("language", "python"),
                              "verifier_kind": "test_covered",
                              "covering_tests": len(passing)},
                             verified=True)
        promoted += 1
    loop.save()
    moved = sum(1 for k, v in loop.store.items()
                if float(v.get("confidence", 0)) > conf_before.get(k, 0.0))
    return {"suite_returncode": tr["returncode"],
            "tests_traced": len(hits),
            "tests_passed": sum(1 for v in outcome.values() if v),
            "procedures_covered_by_a_passing_test": promoted,
            "covered_only_by_failing_tests": failing_only,
            "never_called_by_any_test": unexercised,
            "same_evidence_not_recounted": same_evidence,
            "already_trusted": already,
            "distinct_covering_tests": len(covering_all),
            "confidence_increased": moved,
            "trace_seconds": tr["seconds"],
            "pytest_tail": tr.get("pytest_tail")}


def _best_text(rec: dict) -> str:
    for s in reversed(rec.get("solutions") or []):
        if not s.get("truncated"):
            return str(s.get("text", ""))
    return str((rec.get("solutions") or [{}])[-1].get("text", ""))


def probe(loop: LearningLoop) -> dict:
    """Ask for each procedure two ways its own key was never written.

    by_name: the function name in words. This is how a person who has read the
      code asks, and it only works because the name is now a retrieval surface --
      keyed on the docstring alone it scored 0 of 191, since revise_plan is
      documented as "abandon the local approach when the caller fails" and shares
      not one word with its own name.
    by_paraphrase: the docstring's own sentence with its rarest word struck out.
      This is how a person who has NOT read the code asks -- they describe the job
      without knowing the term of art for it. It is the harder and more honest
      probe, and the one that decides whether the local path is usable.
    """
    n = max(1, len(loop.store))
    df: dict[str, int] = {}
    for sig in loop.store:
        for w in set(str(sig).split()):
            df[w] = df.get(w, 0) + 1
    by_name = {"probes": 0, "found": 0, "misses": []}
    by_para = {"probes": 0, "found": 0, "misses": []}
    for sig, rec in list(loop.store.items()):
        prov = rec.get("provenance") or {}
        name = str(prov.get("function") or "")
        task = str(rec.get("task") or "")
        if name:
            ask = name.strip("_").replace("_", " ")
            if len(ask.split()) >= 2:
                got = loop.recall(ask, min_confidence=0.0)
                by_name["probes"] += 1
                ok = bool(got) and got.get("signature") == sig
                by_name["found"] += int(ok)
                if not ok and len(by_name["misses"]) < 5:
                    by_name["misses"].append(
                        {"asked": ask, "wanted": sig[:50],
                         "got": str((got or {}).get("signature"))[:50]})
        words = [w for w in re.findall(r"[a-z_][a-z_0-9]{3,}", task.lower())]
        if len(words) >= 5:
            rarest = min(words, key=lambda w: df.get(_stem(w), 0))
            ask = " ".join(w for w in words if w != rarest)
            got = loop.recall(ask, min_confidence=0.0)
            by_para["probes"] += 1
            ok = bool(got) and got.get("signature") == sig
            by_para["found"] += int(ok)
            if not ok and len(by_para["misses"]) < 5:
                by_para["misses"].append(
                    {"asked": ask[:60], "dropped": rarest, "wanted": sig[:40],
                     "got": str((got or {}).get("signature"))[:40]})
    for d in (by_name, by_para):
        d["rate"] = round(d["found"] / d["probes"], 3) if d["probes"] else None
    return {"by_name": by_name, "by_paraphrase": by_para}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-tests", action="store_true",
                    help="probe retrieval only; promote nothing")
    ap.add_argument("--state", default=None,
                    help="procedure store to practise on; defaults to the live agent's")
    a = ap.parse_args()
    sp = Path(a.state) if a.state else AGENT_STATE
    loop = LearningLoop(state_path=sp, events_path=AGENT_EVENTS, persist=True)
    out: dict = {"library_size": len(loop.store),
                 "min_confidence": loop.min_confidence}
    if not a.no_tests:
        tr = trace_tests()
        out["trace"] = verify(loop, tr)
        loop = LearningLoop(state_path=sp, events_path=AGENT_EVENTS,
                            persist=True)
    out["retrieval"] = probe(loop)
    out["confidence_histogram"] = {}
    for rec in loop.store.values():
        b = round(float(rec.get("confidence", 0)) * 10) / 10
        out["confidence_histogram"][str(b)] = \
            out["confidence_histogram"].get(str(b), 0) + 1
    out["recallable_at_default_floor"] = sum(
        1 for v in loop.store.values()
        if float(v.get("confidence", 0)) >= loop.min_confidence)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
