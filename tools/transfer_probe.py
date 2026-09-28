"""Can a program-shaped fact transfer? Measure the CEILING, without touching the harness.

WHY PROBE INSTEAD OF BUILDING. Making `KnowledgeChannel.ask` engage on program tasks is
necessary but probably not sufficient. A FUNCTION-shaped fact ports because the calling
convention is shared: `f(a)`, read `a[0]`. Two PROGRAM tasks about the same concept can read
entirely different input layouts -- one line of integers, a grid, a count followed by that many
tokens -- and the fact key has no field for that. Its answer shape is `unknown` for program
checks. Discovering that with a 2.5-hour experiment is an expensive way to find out.

So: ask the oracle for complete programs on a sample, keep only the ones that pass the task's
OWN tests in program mode, then run A's program against B's tests for every sibling pair.

  sibling hits      an upper bound on what a fact store could transfer on this pool
  non-sibling hits  the control: must be zero, or the comparison is too lenient

    python tools/transfer_probe.py --sample 20
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROMPT = """Write a complete Python program that solves this problem.

PROBLEM:
%s

The program must read from standard input and write the answer to standard output.
Here is one example of the input and the output it should produce:

INPUT:
%s
OUTPUT:
%s

Reply with the Python code only, no explanation, no markdown fences."""


def _rows():
    from tools.make_curriculum import load
    return load("train", "codecontests") + load("holdout", "codecontests")


def _tests(check: str) -> list:
    from organs.program_task import decode_meta
    try:
        return decode_meta(check)["tests"]
    except Exception:
        return []


def _key(row):
    from organs.concepts import extract_key
    return tuple(extract_key(row["task"], row["check"]))


def _clean(text: str) -> str:
    from organs.knowledge import _fenced
    code = _fenced(text) or str(text or "").strip()
    return code.strip()


def siblings(rows, keys):
    """Pairs that SHARE (concept, subject), with genuinely different tests.

    Two arms of a split can only test transfer if the same hole recurs with different
    specifics; an identical pair is a duplicate wearing a key.
    """
    groups = defaultdict(list)
    for r, k in zip(rows, keys):
        groups[(k[0], k[1])].append(r)
    pairs = []
    for k, members in groups.items():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                if _tests(a["check"]) != _tests(b["check"]):
                    pairs.append((k, a, b))
    return groups, pairs


def probe(sample_n: int, seed: int = 7) -> dict:
    """Opens the fence for the duration through the sanctioned mechanism, then measures.

    This used to juggle `os.environ.pop` by hand and depend on doing it in the right order
    relative to a local agent's `setdefault`. That ordering produced a 20/20 NoAPIKeyError
    run that looked like the oracle failing on program tasks. `oracle_open()` restores the
    fence on exit and the key is now resolved per call, so no ordering can matter.
    """
    from organs.api_oracle import oracle_open
    with oracle_open():
        return _run(sample_n, seed)


def _run(sample_n: int, seed: int = 7) -> dict:
    import random
    from tools.make_generated_pool import _agent

    # USE THE AGENT'S ORACLE, NOT A FRESHLY BUILT ONE. `_agent()` pops the offline fence and
    # swaps in the real oracle when it has a key; building an oracle straight from the config
    # in this process produced NoAPIKeyError on all 20 calls -- a zero that looks exactly like
    # "the oracle cannot solve these", which is the finding this probe is supposed to
    # establish. Ask the thing that is known to work, and check it has a key BEFORE measuring.
    agent = _agent()
    loop = agent.reasoning_loop
    oracle = getattr(agent, "api_oracle", None)
    if oracle is None or not getattr(oracle, "has_key", False):
        return {"error": "no oracle key", "has_key": bool(getattr(oracle, "has_key", None)),
                "provider": getattr(oracle, "provider", None),
                "note": "refusing to report a solve rate of 0 for a closed oracle"}

    rows = _rows()
    keys = [_key(r) for r in rows]
    groups, pairs = siblings(rows, keys)

    rep = {"tasks": len(rows), "distinct_keys": len(groups),
           "multi_member_keys": sum(1 for m in groups.values() if len(m) > 1),
           "sibling_pairs": len(pairs), "sample": sample_n,
           "oracle": {"calls": 0, "empty": 0, "accepted": 0, "rejected": 0},
           "pair_results": {"sibling_tested": 0, "sibling_hits": 0,
                            "control_tested": 0, "control_hits": 0},
           "accepted_ids": [], "notes": []}

    rng = random.Random(seed)
    # Prefer tasks that HAVE a sibling, so the pair test actually gets material.
    in_pairs = []
    for _k, a, b in pairs:
        if a["id"] not in in_pairs:
            in_pairs.append(a["id"])
        if b["id"] not in in_pairs:
            in_pairs.append(b["id"])
    by_id = {r["id"]: r for r in rows}
    pool = [by_id[i] for i in in_pairs if i in by_id]
    rest = [r for r in rows if r["id"] not in set(in_pairs)]
    rng.shuffle(pool)
    rng.shuffle(rest)
    sample = (pool + rest)[:sample_n]

    programs = {}
    for r in sample:
        tests = _tests(r["check"])
        if not tests:
            continue
        inp, exp = tests[0]
        rep["oracle"]["calls"] += 1
        # EACH PROBLEM IS ITS OWN TASK. `Budget` has per_query, per_TASK and per_day ceilings,
        # and `task_spent` accumulates across every call until `start_task()` clears it. It
        # was never called here, so all 20 problems were billed against ONE problem's 4000
        # token ceiling -- 15 of 20 came back `task_budget_exceeded`, which reads exactly like
        # an oracle that cannot answer and is not. (`knowledge.py` records the same bug
        # costing 15 of 15 refusals there.)
        try:
            oracle.budget.start_task()
        except Exception:
            pass
        # PROMPT HYGIENE. A full CodeContests statement is ~3600 tokens on its own, so with a
        # 700-token completion it cannot fit a 4000-token per-task ceiling however the task
        # bookkeeping is done. The statement is bounded rather than the ceiling raised: the
        # budget lives in config and changing it is a billing decision, not mine.
        try:
            res = oracle.query(PROMPT % (str(r["task"])[:2600], str(inp)[:600], str(exp)[:300]),
                               max_tokens=700, temperature=0.2, purpose="transfer_probe",
                               no_reasoning=True)
        except Exception as exc:
            rep["oracle"]["empty"] += 1
            rep["notes"].append(f"{r['id']}: {type(exc).__name__}")
            continue
        text = str(res.get("text") or "")
        code = _clean(text)
        if not code:
            # WHY IT WAS EMPTY, ON THE ROW. A bare count of empty completions cannot tell a
            # spent token budget from a refusal from a model that answered with nothing --
            # and that ambiguity is what made this probe's first two readings useless.
            rep["oracle"]["empty"] += 1
            rep["notes"].append(
                "%s: empty ok=%s reason=%s finish=%s"
                % (r["id"], res.get("ok"), str(res.get("reason"))[:70],
                   res.get("finish_reason")))
            continue
        ok, _kind = loop.solver._verify_detail(code, r["check"])
        if ok:
            rep["oracle"]["accepted"] += 1
            programs[r["id"]] = code
            rep["accepted_ids"].append(r["id"])
        else:
            rep["oracle"]["rejected"] += 1
        time.sleep(0.4)

    # --- the transfer test: A's program against B's OWN tests -----------------------
    hit_pairs = []
    for k, a, b in pairs:
        for x, y in ((a, b), (b, a)):
            if x["id"] not in programs:
                continue
            ok, _kind = loop.solver._verify_detail(programs[x["id"]], y["check"])
            rep["pair_results"]["sibling_tested"] += 1
            if ok:
                rep["pair_results"]["sibling_hits"] += 1
                hit_pairs.append((k, x["id"], y["id"]))
    # --- the control: pairs that do NOT share (concept, subject) --------------------
    nonsib = []
    for i in range(len(sample)):
        for j in range(i + 1, len(sample)):
            a, b = sample[i], sample[j]
            ka, kb = _key(a), _key(b)
            if (ka[0], ka[1]) != (kb[0], kb[1]):
                nonsib.append((a, b))
    rng.shuffle(nonsib)
    for a, b in nonsib[:max(12, rep["pair_results"]["sibling_tested"])]:
        for x, y in ((a, b), (b, a)):
            if x["id"] not in programs:
                continue
            ok, _kind = loop.solver._verify_detail(programs[x["id"]], y["check"])
            rep["pair_results"]["control_tested"] += 1
            if ok:
                rep["pair_results"]["control_hits"] += 1
    rep["hit_pairs_sample"] = hit_pairs[:10]
    rate = (rep["oracle"]["accepted"] / rep["oracle"]["calls"]
            if rep["oracle"]["calls"] else None)
    rep["oracle"]["solve_rate"] = round(rate, 3) if rate is not None else None
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=20)
    a = ap.parse_args()
    rep = probe(a.sample)
    Path("state/transfer_probe.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(json.dumps(rep, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
