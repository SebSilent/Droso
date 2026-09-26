"""Does the knowledge channel move the number, and does what it teaches transfer?

Three passes over the same held-out slice, and the third one is the whole point:

    pass 1  local only              -> local_before
    pass 2  search first, then the knowledge channel on refusal
            -> how many were solved locally, how many needed a call, how many calls
    pass 3  local only again, on the SAME slice -> local_after

If the oracle supplied knowledge, pass 3 should beat pass 1: what it taught should help a
later, different task. If pass 3 equals pass 1, then he was taught individual answers that
transfer to nothing -- memorisation with extra steps and a bill attached. That distinction
is the difference between a knowledge channel and a very expensive lookup table, and it
cannot be settled by asserting which one it is.

THE COLUMNS ARE NEVER MERGED. local and oracle are reported separately, always, because an
oracle-assisted solve is not a local solve and a number that adds them together is a number
that lies about the only thing this project is trying to measure.

This tool reads his state and never writes it: persist is off on the language and on the
learning loop, so an oracle-taught procedure cannot land in the library he is living in.
That is not a precaution, it is a rule this project learned the hard way.

    python tools/knowledge_run.py --split holdout --limit 25
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


def _agent():
    """A headless being that can READ the state and cannot write it.

    The oracle is deliberately left reachable: _loop_agent sets HYBRIDLLM_OFFLINE so that
    a measurement of the search cannot quietly bill an account, and this tool is the one
    that wants the provider. The fence is a property read at call time, so removing the
    variable here is what opens it -- for this process only, and only because reaching the
    oracle is the entire purpose of the run.
    """
    from tools.curriculum_run import _loop_agent
    agent = _loop_agent()
    os.environ.pop("HYBRIDLLM_OFFLINE", None)
    # _loop_agent builds from a stub config -- provider qwen, no key -- because everything
    # that uses it is measuring the SEARCH, where reaching a provider would be a bug. A
    # knowledge channel is the one thing that wants the real one, so it is swapped in from
    # the harness's own factory, reading the same config/hybrid_config.json and the same
    # credential store the live house reads. The oracle stays a single thing built a single
    # way; this tool does not get its own.
    try:
        import json as _json
        from pathlib import Path as _Path
        from organs.api_oracle import oracle_from_config
        # The config has to be passed EXPLICITLY. oracle_from_config() with no argument
        # runs `cfg = cfg or {}` and therefore builds from the library defaults -- which
        # is openai/gpt-4o-mini with a 300-token query budget, not this project's
        # ollama_cloud/deepseek-v4.1-flash with 1200. It reported a real key and the
        # wrong provider, which is the most dangerous shape a bug like this can take:
        # it looks like it worked.
        cfg_path = _Path(__file__).resolve().parents[1] / "config" / "hybrid_config.json"
        cfg = _json.loads(cfg_path.read_text(encoding="utf-8"))
        real = oracle_from_config(cfg)
        if getattr(real, "has_key", False):
            agent.api_oracle = real
    except Exception:
        pass
    # Belt and braces on top of _loop_agent: the language organ is not the only thing
    # rooted at ROOT, and a learning loop that saves would write this tool's small
    # library over the one he is living in. That happened once already.
    for name in ("language", "learning_loop"):
        obj = getattr(agent, name, None)
        if obj is not None:
            try:
                obj.persist = False
            except Exception:
                pass
    return agent


def _pass(agent, rows, channel, use_oracle: bool) -> dict:
    """One pass over the slice, with the identity of every task that was solved.

    The identities are the point. A count alone cannot tell 'it taught him something that
    helped elsewhere' from 'he got the same three tasks back', and those are memorisation
    and transfer -- the two things this tool exists to separate. Exactly +3 was returned on
    the first run with exactly 3 oracle solves, and a coarse count cannot say whether that
    was knowledge or recall.
    """
    loop = agent.reasoning_loop
    local = oracle = refused = 0
    solved_idx, taught_idx = [], []
    # WHICH PATH SOLVED IT. Read off the winning candidate's label, so the distinction
    # between recall and transfer is a property of the run and not of somebody reading the
    # identities afterwards -- which is the only reason the last measurement caught it.
    solved_by: dict = {}
    detail = []
    for i, r in enumerate(rows):
        out = loop.step(r["task"], r["check"], learn=False)
        was_local = out.get("outcome") == "solved"
        col = "local" if was_local else "neither"
        kr = None
        if was_local:
            local += 1
            solved_idx.append(i)
            lbl = str(out.get("candidate") or "?")
            kind = ("transfer_fact" if lbl.startswith("fact:")
                    else "recall_task" if lbl.startswith("library:")
                    else "local_synthesis")
            solved_by[kind] = solved_by.get(kind, 0) + 1
        elif use_oracle and channel is not None:
            fails = [t.get("why") for t in loop.trace[-6:] if t.get("why")]
            kr = channel.ask(r["task"], r["check"], failures=fails)
            if kr.get("accepted"):
                col = "oracle"
                oracle += 1
                solved_idx.append(i)
                taught_idx.append(i)
            else:
                refused += 1
        else:
            refused += 1
        # Both fields: the acceptance path reports `why` and the failure path reports
        # `reason`, and reading only the first made every refusal look like an empty
        # string -- which is how a budget error stayed invisible through a whole run.
        detail.append({"task": str(r["task"])[:70], "column": col,
                       "reason": str((kr or {}).get("why") or
                                     (kr or {}).get("reason") or "")[:90]})
    return {"local": local, "oracle": oracle, "refused": refused,
            "tasks": len(rows), "solved_idx": solved_idx, "taught_idx": taught_idx,
            "solved_by": solved_by, "detail": detail}


def run(split: str = "holdout", limit: int | None = None,
        max_calls: int = 1) -> dict:
    from tools.make_curriculum import load
    rows = load(split)
    if limit:
        rows = rows[:int(limit)]
    agent = _agent()
    loop = agent.reasoning_loop
    oracle = getattr(agent, "api_oracle", None)
    if oracle is None:
        return {"error": "no oracle on this agent"}
    from organs.knowledge import KnowledgeChannel
    channel = KnowledgeChannel(oracle=oracle, loop=loop,
                               learning=getattr(agent, "learning_loop", None),
                               max_calls_per_task=int(max_calls))

    t0 = time.time()
    before = _pass(agent, rows, None, use_oracle=False)
    with_oracle = _pass(agent, rows, channel, use_oracle=True)
    after = _pass(agent, rows, None, use_oracle=False)
    # THE DECISIVE SPLIT. gained are tasks solved in pass 3 but not pass 1; taught are the
    # ones the oracle answered. Their intersection is recall of the answer he was just
    # given -- memorisation, and worth nothing. What is left is a DIFFERENT task that pass 3
    # can solve because the knowledge was there. Only that second set is transfer, and the
    # first run could not distinguish the two because it only reported a count.
    gained = sorted(set(after["solved_idx"]) - set(before["solved_idx"]))
    taught = set(with_oracle["taught_idx"])
    recall = [i for i in gained if i in taught]
    transfer = [i for i in gained if i not in taught]
    out = {
        "split": split, "tasks": len(rows),
        "columns_never_merged": True,
        "pass1_local_only": before["local"],
        "pass2_local": with_oracle["local"],
        "pass2_oracle": with_oracle["oracle"],
        "pass2_refused": with_oracle["refused"],
        "pass3_local_only": after["local"],
        "gained_in_pass3": len(gained),
        "of_which_recall": len(recall),
        "of_which_transfer": len(transfer),
        "recall_tasks": [str(rows[i]["task"])[:64] for i in recall],
        "transfer_tasks": [str(rows[i]["task"])[:64] for i in transfer],
        "channel": channel.stats(),
        "solved_by": with_oracle.get("solved_by") or {},
        "recall_vs_transfer": {
            "recall_task": (with_oracle.get("solved_by") or {}).get("recall_task", 0),
            "transfer_fact": (with_oracle.get("solved_by") or {}).get("transfer_fact", 0),
            "local_synthesis": (with_oracle.get("solved_by") or {}).get("local_synthesis", 0),
        },
        "seconds": round(time.time() - t0, 1),
        "detail": with_oracle["detail"],
    }
    return out


def fact_transfer(agent, channel, rows, limit_groups: int = 12,
                  seed_with_gold: bool = False) -> dict:
    """Teach ONE task per (concept, subject); see whether the OTHERS solve locally.

    THE DISTINCTION THE LAST MEASUREMENT COULD ONLY MAKE BY HAND. Last time, three tasks
    were solved after the oracle and three tasks were gained on the later pass, and the
    numbers matched exactly -- which is the signature of recall and not transfer, but only
    because someone looked. This asks the question directly and structurally: group the
    held-out tasks by key, seed ONE per group, and then measure how many of the OTHERS are
    solved by the fact path with no further oracle call.

    A group of one proves nothing and is skipped. If every group has one member, the answer
    is "this slice cannot show transfer", which is the honest result and not a zero.
    """
    # GROUPED BY THE KEY THE STORE USES. Grouping by (concept, subject) while the facts are
    # filed under (concept, subject, shape) means the test measures a partition nothing
    # implements -- it reported the same 7 groups after the shape was added, which is how
    # this was caught.
    from organs.concepts import extract_key, keyable
    groups: dict = {}
    for i, r in enumerate(rows):
        c, s, sh = extract_key(r["task"], r["check"])
        if keyable(r["task"], r["check"]):
            groups.setdefault((c, s, sh), []).append(i)
    multi = {k: v for k, v in groups.items() if len(v) >= 2}
    result = {"groups_with_one_task": sum(1 for v in groups.values() if len(v) == 1),
              "groups_with_several": len(multi), "tested": [], "transfer_hits": 0,
              "taught": 0}
    if not multi:
        result["verdict"] = ("this slice cannot show transfer: no two tasks share a "
                             "concept+subject key")
        return result
    loop = agent.reasoning_loop
    for (c, s, sh), idxs in list(sorted(multi.items()))[:int(limit_groups)]:
        seed, others = idxs[0], idxs[1:]
        r0 = rows[seed]
        before = []
        for j in others:
            before.append(loop.step(rows[j]["task"], rows[j]["check"],
                                    learn=False).get("outcome") == "solved")
        # SEEDING WITH GOLD REMOVES THE PROVIDER FROM THE MEASUREMENT. The question this
        # test exists to answer is "does a correctly-keyed fact carry", and answering it
        # does not require the oracle -- it requires a CORRECT FACT. Asking the oracle
        # made the whole measurement depend on whether a provider answered over the last
        # four calls, which is how the previous attempt came back inconclusive twice. The
        # gold solution is verified by the same task_check gate before it is filed, so this
        # is the identical trust decision with the flaky part taken out.
        kr = None
        if seed_with_gold and str(r0.get("gold") or "").strip():
            code = str(r0["gold"])
            ok, why = loop._attempt({"code": code, "label": "gold"}, r0["check"])
            if ok:
                loop.learning.learn_from_task(
                    r0["task"], code, {"source": "corpus", "verified": True,
                                       "language": "python",
                                       "verifier_kind": "task_check"}, verified=True)
                fc = channel.distill_fact(r0["task"], r0["check"], code)
                kr = {"accepted": True, "code": code, "fact": fc, "call_ok": True,
                      "seeded_from": "gold"}
            else:
                kr = {"accepted": False, "call_ok": True, "seeded_from": "gold",
                      "reason": "the gold solution does not pass its own check: %s"
                                % str(why or "")[:60]}
        else:
            kr = channel.ask(r0["task"], r0["check"], failures=None)
        after = []
        for j in others:
            o = loop.step(rows[j]["task"], rows[j]["check"], learn=False)
            after.append((o.get("outcome") == "solved",
                          str(o.get("candidate") or "")))
        if not kr.get("accepted"):
            # "THE ORACLE RETURNED NOTHING" AND "THE ORACLE WAS WRONG" ARE DIFFERENT RESULTS
            # and the first verdict conflated them. An answer that came back and was
            # rejected by the task's own assertions is the gate working on a wrong formula:
            # it is information about the oracle, and it is the commonest outcome. A call
            # that returned nothing is information about the provider. Calling both
            # "returned nothing" was a confident wrong reason, again.
            kind = ("call_failure" if not kr.get("call_ok") else "answered_and_rejected")
            result[kind] = result.get(kind, 0) + 1
            result["tested"].append({"key": "%s+%s+%s" % (c, s, sh), "seeded": False,
                                     "kind": kind,
                                     "reason": str(kr.get("reason") or kr.get("why")
                                                   or "")[:70]})
            continue
        result["taught"] += 1
        gained = [(j, lbl) for j, (ok, lbl) in zip(others, after)
                  if ok and lbl.startswith("fact:")]
        result["transfer_hits"] += len(gained)
        # A SIBLING THAT WAS ALREADY SOLVABLE CANNOT SHOW TRANSFER. If it solved by the
        # library before the fact existed, this group is uninformative about transfer and
        # saying "0 of 1" would blame the fact path for a question that was never asked.
        was_before = sum(1 for b in before if b)
        now_any = sum(1 for ok, _lbl in after if ok)
        result["already_solvable"] = result.get("already_solvable", 0) + was_before
        result["informative_groups"] = result.get("informative_groups", 0) + (
            1 if was_before < len(others) else 0)
        result["tested"].append({"key": "%s+%s+%s" % (c, s, sh), "seeded": True,
                                 "from": kr.get("seeded_from", "oracle"),
                                 "others": len(others),
                                 "already_solved_before": was_before,
                                 "solved_after": now_any,
                                 "solved_via_fact": len(gained),
                                 "labels": [lbl for _j, lbl in gained][:4]})
    if result["transfer_hits"]:
        result["verdict"] = "transfer happens: a sibling task was solved by the fact path"
    elif not result["taught"]:
        # NOTHING WAS SEEDED, so nothing could transfer and NOTHING IS LEARNED -- but say
        # WHICH kind of nothing, because they mean opposite things about the system.
        result["verdict"] = ("inconclusive: %d group(s) had a sibling and not one was "
                             "seeded -- %d call failure(s) and %d answer(s) the assertions "
                             "rejected. No fact ever existed to transfer."
                             % (result["groups_with_several"],
                                result.get("call_failure", 0),
                                result.get("answered_and_rejected", 0)))
    elif not result.get("informative_groups"):
        result["verdict"] = ("no transfer observed, but NO GROUP COULD SHOW IT: every "
                             "sibling was already solvable, so the fact was never needed")
    else:
        result["verdict"] = ("no transfer: the fact was filed, %d group(s) had an "
                             "unsolved sibling, and none of them reached it"
                             % result["informative_groups"])
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="holdout", choices=["train", "holdout"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--max-calls", type=int, default=1)
    ap.add_argument("--harness", action="store_true",
                    help="run the System 1/2 harness over the slice and report which "
                         "branch fired -- that log IS the 90/10 number")
    ap.add_argument("--seed-gold", action="store_true",
                    help="seed the transfer test from the task's GOLD solution instead of "
                         "the oracle -- answers 'does a keyed fact carry' without making "
                         "the answer depend on the provider's uptime")
    ap.add_argument("--transfer", action="store_true",
                    help="the structural transfer test: seed ONE task per concept+subject "
                         "and see whether its siblings solve locally, no further call")
    a = ap.parse_args()
    if a.harness:
        from tools.make_curriculum import load
        from organs.knowledge import KnowledgeChannel
        from organs.harness import Harness
        agent = _agent()
        loop = agent.reasoning_loop
        rows = load(a.split)
        if a.limit:
            rows = rows[:int(a.limit)]
        ch = KnowledgeChannel(oracle=agent.api_oracle, loop=loop,
                              learning=getattr(agent, "learning_loop", None),
                              max_calls_per_task=int(a.max_calls))
        h = Harness(loop=loop, solver=loop.solver, sandbox=loop.sandbox,
                    learning=getattr(agent, "learning_loop", None), channel=ch)
        for r in rows:
            h.solve(r["task"], r["check"], learn=False)
        rep = h.report()
        rep["channel"] = ch.stats()
        rep["tasks"] = len(rows)
        print(json.dumps(rep, indent=1))
        return 0
    if a.transfer:
        from tools.make_curriculum import load
        from organs.knowledge import KnowledgeChannel
        agent = _agent()
        rows = load(a.split)
        if a.limit:
            rows = rows[:int(a.limit)]
        ch = KnowledgeChannel(oracle=agent.api_oracle, loop=agent.reasoning_loop,
                              learning=getattr(agent, "learning_loop", None),
                              max_calls_per_task=int(a.max_calls))
        print(json.dumps(fact_transfer(agent, ch, rows,
                                       seed_with_gold=bool(a.seed_gold)), indent=1))
        return 0
    out = run(a.split, a.limit, a.max_calls)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
