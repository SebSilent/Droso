"""Generate toward RECURRING HARD concepts, not hard tasks in general.

WHY THE LAST POOL FAILED. Filtering the existing pool by hardness left seven tasks with ZERO
recurring concepts among them. Hardness and transferability turned out to be in tension: an
alternating split needs concepts that appear more than once, and broad-generate-then-filter
optimises only for hardness. So the pilot aims at both properties AT ONCE -- pick concepts
already known to recur, ask for several deliberately hard variants of each, and then measure
whether the survivors still recur by concept.

SAME DISCIPLINE AS EVERY OTHER POOL: the oracle's own solution must pass the task's own
assertions before admission, the dumb-solution battery must reject, and hardness is MEASURED
(both thresholds, reported where they disagree) rather than assumed from the prompt's intent.

    python tools/concept_band_pilot.py --per-concept 4
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Concepts already recurring in the corpora -- there is no point generating a hard one-off.
SEEDS = [("even_odd", "list"), ("unique", "list"), ("sort", "list"),
         ("intersection", "list"), ("minimum", "list"), ("maximum", "list"),
         ("count", "string"), ("frequency", "dictionary"), ("sum", "list"),
         ("reverse", "string"), ("unique", "string"), ("vowel", "string"),
         ("join", "string"), ("digit", "number")]

PROMPT = """Write a HARD coding exercise for a Python student.

It must be about the operation %r applied to a %r.

Make it HARD in the sense that solving it needs several steps of reasoning and careful case
analysis -- NOT hard in the sense of being unclear. It must be unambiguous, solvable in one
function, and stated in one sentence.

BEFORE YOU REPLY, RUN YOUR OWN SOLUTION AGAINST EVERY ASSERTION YOU WROTE. Measured: 9 of 16
earlier replies failed because the assertion set contained an edge case the reply's own
solution could not handle -- adjacent intervals, duplicate values, `1` aliasing with `True`.
A reply whose own check it fails is worthless, so either fix the solution or drop that
assertion. Do not include a case you cannot solve.

Reply with JSON only, exactly:
{"task": "<one sentence>", "check": "<3 or more assert lines calling ONE function>", "solution": "<a complete function definition satisfying them>"}
"""


def generate(oracle, concept: str, subject: str):
    """One variant, or (None, why). The reason is always captured -- see the fence history."""
    oracle.budget.start_task()
    try:
        res = oracle.query(PROMPT % (concept, subject), max_tokens=700, temperature=0.8,
                           purpose="concept_band", no_reasoning=True)
    except Exception as exc:
        return None, "%s: %s" % (type(exc).__name__, str(exc)[:60])
    text = str(res.get("text") or "")
    if not res.get("ok") or not text.strip():
        return None, str(res.get("reason") or "empty")[:60]
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None, "no json object"
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None, "unparseable json"
    task, check, sol = (str(d.get("task") or "").strip(),
                        str(d.get("check") or "").strip(),
                        str(d.get("solution") or "").strip())
    if not (task and "assert" in check and "def " in sol):
        return None, "malformed fields"
    return {"task": task, "check": check, "gold": sol,
            "concept": concept, "subject": subject}, None


def measure(agent, rows) -> None:
    """Re-derivation cost per task. `attempts_total` is CUMULATIVE across the process, so the
    per-task search cost is the difference between successive readings."""
    from organs.harness import Harness
    loop = agent.reasoning_loop
    h = Harness(loop=loop, solver=loop.solver, sandbox=loop.sandbox,
                learning=getattr(agent, "learning_loop", None), channel=None)
    prev = None
    for r in rows:
        t0 = time.time()
        out = h.solve(r["task"], r["check"], learn=False, oracle=False)
        r["rederive_s"] = round(time.time() - t0, 3)
        c = (out.get("loop") or {}).get("attempts_total")
        r["candidates"] = None if c is None else (c - (prev if prev is not None else 0))
        if c is not None:
            prev = c


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-concept", type=int, default=4)
    a = ap.parse_args()

    from organs.api_oracle import oracle_open
    from tools.make_generated_pool import _agent, verify, existing_texts, _norm
    from tools.check_quality import wrong_solutions

    with oracle_open():
        agent = _agent()
        oracle = getattr(agent, "api_oracle", None)
        if oracle is None or not getattr(oracle, "has_key", False):
            print(json.dumps({"error": "no oracle key"}))
            return 1
        loop = agent.reasoning_loop
        known = existing_texts()

        rep = {"attempted": 0, "generated": 0, "duplicate": 0, "verification_failed": 0,
               "empty": 0, "reasons": {}, "admitted": 0, "weak": 0}
        cands = []
        for concept, subject in SEEDS:
            for _k in range(a.per_concept):
                rep["attempted"] += 1
                c, why = generate(oracle, concept, subject)
                if not c:
                    rep["empty"] += 1
                    rep["reasons"][str(why)] = rep["reasons"].get(str(why), 0) + 1
                    continue
                rep["generated"] += 1
                if _norm(c["task"]) in known:
                    rep["duplicate"] += 1
                    continue
                if not verify(agent, c["task"], c["check"], c["gold"]):
                    rep["verification_failed"] += 1
                    continue
                cands.append(c)

        # THE BATTERY, before anything is measured or admitted.
        for c in cands:
            bad = [w for w, code in wrong_solutions(c["check"], c["gold"]).items()
                   if loop.solver._verify_detail(code + "\n\n" + c["check"], c["check"])[0]]
            c["weak"] = bad
        admit = [c for c in cands if not c["weak"]]
        rep["admitted"] = len(admit)
        rep["weak"] = len(cands) - len(admit)

        measure(agent, admit)

        by_cand = [c for c in admit if (c["candidates"] or 0) >= 5]
        by_time = [c for c in admit if c["rederive_s"] >= 3.0]
        both = [c for c in admit if c in by_cand and c in by_time]
        either = [c for c in admit if c in by_cand or c in by_time]

        def hist(rows):
            from collections import Counter
            h = Counter(c["concept"] for c in rows)
            return {"n": len(rows), "distinct_concepts": len(h),
                    "concepts_recurring": sum(1 for v in h.values() if v > 1),
                    "histogram": dict(h.most_common())}

        # THE TWO THRESHOLDS DISAGREE. Reported, not silently resolved: last round found a task
        # with 10 candidates and a ratio of only 2.48, so "hard by search" and "hard by time"
        # are not the same filter and the choice between them is a human one.
        rep["band"] = {
            "by_candidates_only": hist(by_cand),
            "by_time_only": hist(by_time),
            "by_both": hist(both),
            "by_either": hist(either),
            "cand_only_not_time": [c["task"][:50] for c in by_cand if c not in by_time],
            "time_only_not_cand": [c["task"][:50] for c in by_time if c not in by_cand],
        }
        rep["per_task"] = [{"concept": c["concept"], "task": c["task"][:64],
                            "rederive_s": c["rederive_s"], "candidates": c["candidates"]}
                           for c in admit]
        if admit:
            rep["rederive_median_s"] = round(statistics.median(
                [c["rederive_s"] for c in admit]), 3)

        # ADMITTED, BAND-FILTERED MATERIAL IS WRITTEN OUT so a volume run accumulates rather
        # than overwriting. Only tasks that are hard by at least one measured threshold are
        # kept -- the recurring-concept property is checked on the file afterwards, by
        # measurement, not assumed to survive at scale.
        banded = [c for c in admit
                  if (c["candidates"] or 0) >= 5 or c["rederive_s"] >= 3.0]
        out_path = Path("state/curriculum/generated_band.jsonl")
        existing = []
        if out_path.exists():
            existing = [json.loads(l) for l in
                        out_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        seen = {_norm(r.get("task", "")) for r in existing}
        added = 0
        for c in banded:
            if _norm(c["task"]) in seen:
                continue
            existing.append({
                "id": "band:" + hashlib.sha256(c["task"].encode()).hexdigest()[:10],
                "task": c["task"], "check": c["check"], "gold": c["gold"],
                "concept": c["concept"], "subject": c["subject"],
                "rederive_s": c["rederive_s"], "candidates": c["candidates"],
                "source": "generated", "split": "train"})
            seen.add(_norm(c["task"]))
            added += 1
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(json.dumps(r) for r in existing), encoding="utf-8")
        rep["band_added"] = added
        rep["band_pool_size"] = len(existing)

    Path("state/concept_band_pilot.json").write_text(json.dumps(rep, indent=1),
                                                     encoding="utf-8")
    print(json.dumps({k: v for k, v in rep.items() if k != "per_task"}, indent=1))
    print("\nper task:")
    for c in rep["per_task"]:
        print(f"   {c['concept']:14} cands={str(c['candidates']):>4} {c['rederive_s']:6.2f}s  {c['task']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
