"""Can two lives do something one life could not? An experiment that is allowed to say no.

WHY THE LAST ONE WAS WORTHLESS, AND WHAT CHANGED. The previous run declared "compounding"
off 3 held-out tasks against 1 -- z 1.01, inside the noise band -- and worse, every arm had
solved 97-100% of its own slice FROM THE CORPUS, so nothing had ever depended on which arm
you were in. The branch structure was never exercised. Two guards now refuse to speak in
that situation, and this file is what tries again with a split that might actually be
disjoint.

THE SPLIT IS BY FACT, NOT AT RANDOM. Tasks are partitioned by the (concept, subject) key
their own text yields: solids and figures to one arm, integers and numbers to the other.
The point of partitioning by fact is that each arm's fact store can then be genuinely
unable to answer the other's slice -- which is a property no random split has.

THE CHAIN THAT HAS TO HOLD, and each link is checked rather than assumed:

    arm A, no oracle, on slice B      ->  must be 0, or the split is not disjoint
    arm B, no oracle, on slice A      ->  must be 0, same check from the other side
    A's facts merged into one binder  ->  on slice B, must now be MORE than 0

If the first two are not zero, the split created no disjoint capability and THE VERDICT IS
REFUSED -- because then the merge could not have added anything, and a number would be
measuring the corpus instead of the arrangement of lives.

WHAT THIS CANNOT DO YET, stated here rather than discovered by a reader. The instruction
asked for one task needing a fact from BOTH categories combined. That task cannot be built
on this architecture: the harness slots ONE fact into ONE shape, so a body needing a sphere
formula and a prime count is not expressible as a candidate, and the merged individual would
fail it too -- for a reason that has nothing to do with lives. So the combined task is
replaced by the cross-slice test, which asks the same question at the resolution the machine
actually has: does a fact from the OTHER life make a task solvable that neither this life nor
the corpus could reach. The gap is real and is left visible.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GEOMETRY = {"sphere", "cylinder", "circle", "cone", "cube", "cuboid", "triangle",
            "rectangle"}
NUMBER = {"integer", "number"}
STRING = {"string", "character"}
# PAIRINGS. `geometry_number` is the original split. `geometry_string` is chosen to be
# MAXIMALLY UNRELATED -- solids against text, which share almost no surface at all -- so a
# result that survives it cannot be an artefact of the two slices being math-adjacent.
PAIRINGS = {
    "geometry_number": (GEOMETRY, NUMBER),
    "geometry_string": (GEOMETRY, STRING),
    "number_string": (NUMBER, STRING),
}
# FOUR SLICES, so the experiment can run more than two lives. The pairwise pairing can only
# ever ask "does B's knowledge help A"; with four groups the same question is asked across
# every ordered pair, and the marginal-life question -- does a fourth arm add anything a
# third did not -- becomes answerable at all.
GROUPS = {
    "geometry": GEOMETRY,
    "number": NUMBER,
    "string": STRING,
    "collection": {"list", "tuple", "dictionary"},
}


def _agent():
    from tools.knowledge_run import _agent as kagent
    return kagent()


def slice_by_fact(rows, pairing: str = "geometry_number"):
    from organs.concepts import extract_key
    set_a, set_b = PAIRINGS.get(pairing, PAIRINGS["geometry_number"])
    a, b, other = [], [], []
    for r in rows:
        c, s, _sh = extract_key(r["task"], r["check"])
        if not c:
            other.append(r)
        elif s in set_a:
            a.append(r)
        elif s in set_b:
            b.append(r)
        else:
            other.append(r)
    return a, b, other


def slice_multi(rows, names):
    """Partition rows into one slice per named group. First match wins, so a task belongs to
    exactly one life and no arm is handed another arm's work by accident."""
    from organs.concepts import extract_key
    out = {n: [] for n in names}
    other = []
    for r in rows:
        c, s, _sh = extract_key(r["task"], r["check"])
        placed = False
        for n in names:
            if c and s in GROUPS.get(n, ()):
                out[n].append(r)
                placed = True
                break
        if not placed:
            other.append(r)
    return out, other


def _run_arm(tasks, label: str, max_calls: int = 1) -> dict:
    """A life that has only ever seen its own slice, with the oracle available."""
    from organs.knowledge import KnowledgeChannel
    from organs.harness import Harness
    agent = _agent()
    loop = agent.reasoning_loop
    ch = KnowledgeChannel(oracle=agent.api_oracle, loop=loop,
                          learning=getattr(agent, "learning_loop", None),
                          max_calls_per_task=int(max_calls))
    h = Harness(loop=loop, solver=loop.solver, sandbox=loop.sandbox,
                learning=getattr(agent, "learning_loop", None), channel=ch)
    for r in tasks:
        # learn=True IS the point of an arm: a life that works something out KEEPS it. It was
        # False, which meant the procedure was never stored -- and the fact-filing guard then
        # refused to file anything, oracle or self, because the fact would have pointed at
        # nothing. So the arms were silently unable to self-distil at all, which is the one
        # behaviour this round exists to measure. Nothing leaks: a tool agent is read-only
        # and the save path is replaced, so this is in-memory only.
        h.solve(r["task"], r["check"], learn=True)
    binder = getattr(getattr(agent.language, "cortex", None), "binder", None)
    facts = dict(getattr(binder, "facts", {}) or {})
    return {"label": label, "agent": agent, "loop": loop, "binder": binder,
            "facts": facts,
            "fact_sources": dict(getattr(binder, "fact_sources", {}) or {}),
            "report": h.report(), "channel": ch.stats(),
            "store": dict(getattr(getattr(agent, "learning_loop", None), "store", {}) or {})}


def _eval_no_oracle(arm: dict, tasks, extra_facts=None, store=None,
                    extra_sources=None) -> dict:
    """Evaluate with the oracle OFF. No oracle means a fact can only come from a store.

    Returns the harness report PLUS a provenance breakdown, because a `system1_fact` hit is
    two different claims at once: a fact the ORACLE supplied, or one a LIFE worked out for
    itself. Only the second is evidence that the lives compound.
    """
    from organs.harness import Harness
    from organs.concepts import extract_key
    loop = arm["loop"]
    binder = arm["binder"]
    saved = dict(getattr(binder, "facts", {}) or {})
    saved_sources = dict(getattr(binder, "fact_sources", {}) or {})
    learning = getattr(loop, "learning", None)
    saved_store = dict(getattr(learning, "store", {}) or {})
    if extra_facts is not None and binder is not None:
        binder.facts = dict(extra_facts)
    if extra_sources is not None and binder is not None:
        binder.fact_sources = dict(extra_sources)
    if store is not None and learning is not None:
        learning.store = dict(store)
    h = Harness(loop=loop, solver=loop.solver, sandbox=loop.sandbox,
                learning=learning, channel=None)   # channel=None IS the no-oracle fence
    provenance: dict = {}
    for r in tasks:
        out = h.solve(r["task"], r["check"], learn=False)
        if not out.get("solved"):
            continue
        branch = str(out.get("branch"))
        if branch == "system1_fact":
            c, s, sh = extract_key(r["task"], r["check"])
            src = (getattr(binder, "fact_sources", {}) or {}).get((c, s, sh), "unknown")
            branch = "system1_fact:%s" % src
        provenance[branch] = provenance.get(branch, 0) + 1
    rep = h.report()
    rep["provenance"] = provenance
    if binder is not None:
        binder.facts = saved
        binder.fact_sources = saved_sources
    if learning is not None:
        learning.store = saved_store
    return rep


def _screen(rows, cache: str | None = None) -> tuple:
    """Admit only the tasks the being CANNOT already solve.

    WHY THE LAST DISJOINTNESS CHECK FAILED, measured rather than guessed. The geometry/
    number split was never disjoint once the tools read the real brain: arm B, which had
    never seen a geometry task, solved "find the surface area of a sphere" -- and the branch
    was `system2_local`, NOT `system1_recall`. So it was not a recalled procedure and not a
    fact: his own 60,000 propositions let local composition answer a geometry question. A
    split by CONCEPT LABEL cannot be disjoint when the memory behind it already generalises
    across that label.

    So the pool is screened first, against the real state with the oracle and the fact store
    both OFF, and only tasks that fail there are admitted. Expect a much smaller pool than
    the holdout, and expect it to be harder -- that is the point.
    """
    from tools.curriculum_run import _loop_agent
    from organs.harness import Harness
    import json as _json
    from pathlib import Path as _Path
    if cache and _Path(cache).exists():
        d = _json.loads(_Path(cache).read_text(encoding="utf-8"))
        # ONLY REUSE FOR THE SAME POOL. Keying purely on survivor ids silently DROPS any row
        # the cache did not see -- so screening a larger pool with a smaller pool's cache
        # would quietly shrink the input and return a confident number about a subset. The
        # ids are compared as a set and a mismatch falls through to a real screening.
        if set(d.get("pool_ids") or []) == {r.get("id") for r in rows}:
            ids = set(d.get("survivor_ids") or [])
            keep = [r for r in rows if r.get("id") in ids]
            info = dict(d.get("info") or {})
            info["survivors"] = len(keep)
            info["from_cache"] = cache
            return keep, info
    agent = _loop_agent()
    loop = agent.reasoning_loop
    h = Harness(loop=loop, solver=loop.solver, sandbox=loop.sandbox,
                learning=getattr(agent, "learning_loop", None), channel=None)
    keep, solved, branches = [], 0, {}
    for r in rows:
        out = h.solve(r["task"], r["check"], learn=False, oracle=False)
        b = out.get("branch")
        branches[b] = branches.get(b, 0) + 1
        if out.get("solved"):
            solved += 1
        else:
            keep.append(r)
    info = {"input": len(rows), "solved_already": solved,
            "survivors": len(keep), "branches": branches,
            "note": "screened with the oracle and the fact store OFF, against the "
                    "real 60,000-proposition state"}
    # Screening is deterministic given the being's state and costs ~2 s per task, so it is
    # cached: that makes comparing PAIRINGS affordable without re-paying for it each time.
    if cache:
        try:
            _Path(cache).parent.mkdir(parents=True, exist_ok=True)
            _Path(cache).write_text(
                _json.dumps({"pool_ids": [r.get("id") for r in rows],
                             "survivor_ids": [r.get("id") for r in keep],
                             "info": info}), encoding="utf-8")
        except Exception:
            pass
    return keep, info


def _pool(name: str) -> list:
    """Which tasks the screening stage draws from.

    `holdout` is the clean 98 and the default. `mbpp_all` adds the 329 TRAIN tasks -- which
    were used to teach him, and that is exactly why they are safe here: the screening stage
    admits a task only if he cannot solve it anyway, so a learned task is filtered out and
    the survivors are genuinely-unsolved ones. Growing the pool is the difference between a
    result at n=4/n=8 and a result at n=40/n=80.
    """
    from tools.make_curriculum import load
    if name == "mbpp_all":
        return load("train") + load("holdout")
    if name == "all":
        return (load("train") + load("holdout")
                + load("train", "exercism") + load("holdout", "exercism"))
    return load("holdout")


def run_multi(limit: int | None = None, pool: str = "holdout", screen: bool = True,
              cache: str | None = None,
              groups=("geometry", "number", "string", "collection")) -> dict:
    """N lives, each alone on its own slice, then merged -- with provenance.

    THE QUESTION THIS ANSWERS, which pairwise merging could not: does a fact a LIFE worked
    out for itself do real work crossing between lives, or is the oracle the only thing that
    ever moves? And does a fourth arm add anything past a third, or does the marginal life
    plateau?
    """
    rows = _pool(pool)
    if limit:
        rows = rows[:int(limit)]
    screen_info = None
    if screen:
        rows, screen_info = _screen(rows, cache=cache)
    slices, other = slice_multi(rows, list(groups))
    out = {"mode": "multi", "pool": pool, "groups": [g for g in groups],
           "survivors": len(rows), "slice_sizes": {k: len(v) for k, v in slices.items()},
           "unkeyed_or_other": len(other), "screening": screen_info}
    arms = {g: _run_arm(slices[g], g) for g in groups if slices[g]}
    out["arms"] = {g: {"tasks": len(slices[g]), "facts": len(a["facts"]),
                       "self_facts": sum(1 for v in a["fact_sources"].values()
                                         if v == "self"),
                       "oracle_facts": sum(1 for v in a["fact_sources"].values()
                                           if v == "oracle"),
                       "channel": a["channel"]} for g, a in arms.items()}

    def _others(not_g):
        return [g for g in groups if g != not_g and slices.get(g)]

    def _merge_from(target, givers):
        # THE STORE MERGES TOO, and leaving it out is why every merge read 0. A fact's value
        # is a REFERENCE into the learning store it was filed from, so facts from another
        # life resolve to nothing unless that life's store comes with them -- `recall_fact`
        # finds the key and then reports "the fact points at a procedure with no code". The
        # pairwise version always merged the store; this one did not, and the resolvability
        # guard turns that omission into a zero rather than a wrong answer.
        f, s, st = {}, {}, {}
        for g in givers:
            f.update(arms[g]["facts"])
            s.update(arms[g]["fact_sources"])
            st.update(arms[g]["store"])
        return f, s, st

    # DISJOINTNESS, every ordered pair. If any arm can already do another's work, the split
    # bought nothing and no merge number below is about sharing knowledge between lives.
    disjoint = {}
    for g, a in arms.items():
        for h in _others(g):
            disjoint["%s_alone_on_%s" % (g, h)] = _eval_no_oracle(a, slices[h])["solved"]
    out["disjoint"] = disjoint
    out["disjoint_max"] = max(disjoint.values()) if disjoint else 0

    merges = {}
    for g, a in arms.items():
        for h in _others(g):
            ctrl = _eval_no_oracle(a, slices[h], extra_facts=dict(a["facts"]),
                                   extra_sources=dict(a["fact_sources"]))
            # ALL THE OTHER LIVES, INCLUDING THE ONE THAT OWNS THIS SLICE. Excluding the
            # slice's own arm -- `_others(h)` minus `g`, which is what this said -- leaves
            # out the facts that actually answer these tasks, so every merge read 0 and
            # looked like a finding instead of a bug. The pairwise version never made that
            # mistake: it gives A the facts of B, and B IS the owner of the slice.
            mf, ms, mst = _merge_from(h, _others(g))
            mrg = _eval_no_oracle(a, slices[h], extra_facts=mf, extra_sources=ms,
                                  store=mst)
            merges["%s_on_%s" % (g, h)] = {
                "n": len(slices[h]), "control": ctrl["solved"], "merged": mrg["solved"],
                "delta": mrg["solved"] - ctrl["solved"],
                "provenance": mrg.get("provenance")}
    out["merges"] = merges

    # MARGINAL LIFE: give one receiver the facts of 1, then 2, then 3 other lives, and see
    # whether the third one adds anything the second did not.
    marginal = {}
    for h in groups:
        if not slices.get(h):
            continue
        rpair = next(((g, a) for g, a in arms.items() if g != h), None)
        if rpair is None:
            continue
        recv_g, receiver = rpair
        curve, acc_f, acc_s, acc_st = [], {}, {}, {}
        # The receiver's OWN facts are excluded so the curve measures what OTHER lives add.
        for g in _others(recv_g):
            acc_f.update(arms[g]["facts"])
            acc_s.update(arms[g]["fact_sources"])
            acc_st.update(arms[g]["store"])
            r = _eval_no_oracle(receiver, slices[h], extra_facts=dict(acc_f),
                                extra_sources=dict(acc_s), store=dict(acc_st))
            curve.append({"lives_giving": len(curve) + 1, "solved": r["solved"],
                          "provenance": r.get("provenance")})
        marginal[h] = {"n": len(slices[h]), "curve": curve}
    out["marginal"] = marginal
    return out


def run(limit: int | None = None, screen: bool = True, pool: str = "holdout",
        pairing: str = "geometry_number", cache: str | None = None) -> dict:
    rows = _pool(pool)
    if limit:
        rows = rows[:int(limit)]
    screen_info = None
    if screen:
        rows, screen_info = _screen(rows, cache=cache)
    A, B, other = slice_by_fact(rows, pairing)
    out = {"pool": pool, "pairing": pairing, "tasks_in": len(rows),
           "holdout": len(rows), "slice_geometry": len(A), "slice_number": len(B),
           "slice_a": len(A), "slice_b": len(B),
           "unkeyed_or_other": len(other), "screening": screen_info,
           "note": "slices are small; see caveat"}

    t0 = time.time()
    arm_a = _run_arm(A, "geometry")
    arm_b = _run_arm(B, "number")
    out["arm_a"] = {"tasks": len(A), "facts_filed": len(arm_a["facts"]),
                    "channel": arm_a["channel"]}
    out["arm_b"] = {"tasks": len(B), "facts_filed": len(arm_b["facts"]),
                    "channel": arm_b["channel"]}

    # THE DISJOINTNESS CHECK, both directions, oracle off.
    a_on_b = _eval_no_oracle(arm_a, B)
    b_on_a = _eval_no_oracle(arm_b, A)
    out["arm_a_alone_on_slice_B"] = a_on_b["solved"]
    out["arm_b_alone_on_slice_A"] = b_on_a["solved"]

    # THE MERGE: one of them, given the other's facts and procedures.
    merged_facts = dict(arm_a["facts"])
    merged_facts.update(arm_b["facts"])
    merged_store = dict(arm_a["store"])
    merged_store.update(arm_b["store"])
    a_merged_on_b = _eval_no_oracle(arm_a, B, extra_facts=merged_facts,
                                    store=merged_store)

    # AND THE CONTROL: the same arm, same evaluation, WITHOUT the other life's facts. At
    # equal compute, so the only difference is where the knowledge came from.
    a_control_on_b = _eval_no_oracle(arm_a, B, extra_facts=dict(arm_a["facts"]),
                                     store=dict(arm_a["store"]))
    out["arm_a_control_on_slice_B"] = a_control_on_b["solved"]
    out["arm_a_merged_on_slice_B"] = a_merged_on_b["solved"]
    out["merged_solved_by"] = a_merged_on_b.get("counts")
    out["control_solved_by"] = a_control_on_b.get("counts")
    out["seconds"] = round(time.time() - t0, 1)

    # THE GUARD, BEFORE ANY VERDICT. If either arm could already do the other's work, the
    # split bought nothing and any difference below is the corpus, not the lives.
    if out["arm_a_alone_on_slice_B"] or out["arm_b_alone_on_slice_A"]:
        out["verdict"] = ("REFUSED: the split is not disjoint (arm A solved %d of B's "
                          "slice, arm B solved %d of A's), so nothing here is about "
                          "splitting work across lives"
                          % (out["arm_a_alone_on_slice_B"],
                             out["arm_b_alone_on_slice_A"]))
        return out
    if not arm_b["facts"]:
        out["verdict"] = ("REFUSED: arm B filed no facts, so the merge has nothing to "
                          "carry across")
        return out
    delta = out["arm_a_merged_on_slice_B"] - out["arm_a_control_on_slice_B"]
    out["delta"] = delta
    if delta > 0:
        out["verdict"] = ("COMPOUNDING: %d of %d tasks in slice B are solvable with the "
                          "other life's facts and %d without"
                          % (out["arm_a_merged_on_slice_B"], len(B),
                             out["arm_a_control_on_slice_B"]))
    elif delta == 0:
        out["verdict"] = ("POOLING, NOT COMPOUNDING: the split is disjoint and the other "
                          "life's facts change nothing (%d vs %d)"
                          % (out["arm_a_merged_on_slice_B"],
                             out["arm_a_control_on_slice_B"]))
    else:
        out["verdict"] = "merge WORSE than control: %d vs %d" % (
            out["arm_a_merged_on_slice_B"], out["arm_a_control_on_slice_B"])
    return out


def main() -> int:
    # Flags take a VALUE, so the value of `--pool mbpp_all` must not be mistaken for the
    # positional task limit. (It was: `--pool mbpp_all` parsed as `int("mbpp_all")`.)
    argv = sys.argv[1:]
    flags = {"--pool", "--pairing", "--cache", "--groups"}
    opts: dict = {}
    positionals: list = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in flags:
            opts[a] = argv[i + 1] if i + 1 < len(argv) else None
            i += 2
            continue
        if not a.startswith("--"):
            positionals.append(a)
        i += 1
    lim = int(positionals[0]) if positionals else None
    if "--screen-only" in argv:
        # RE-MEASURE, DO NOT ASSUME. `cache=None` on purpose: this path exists to check that
        # screening still means what it meant when it was designed, and reading a cached
        # result back would answer a different question -- "did this change since I last ran
        # it?" -- while looking exactly like an answer to this one.
        rows = _pool(opts.get("--pool") or "holdout")
        if lim:
            rows = rows[:lim]
        keep, info = _screen(rows, cache=None)
        out = dict(info)
        out["kept_ids"] = [r.get("id") for r in keep]
        print(json.dumps(out, indent=1))
        return 0
    if "--multi" in argv:
        gl = opts.get("--groups") or "geometry,number,string,collection"
        res = run_multi(lim, pool=opts.get("--pool") or "holdout",
                        screen="--no-screen" not in argv,
                        cache=opts.get("--cache"),
                        groups=tuple(x.strip() for x in str(gl).split(",") if x.strip()))
    else:
        res = run(lim, screen="--no-screen" not in argv,
                  pool=opts.get("--pool") or "holdout",
                  pairing=opts.get("--pairing") or "geometry_number",
                  cache=opts.get("--cache"))
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
