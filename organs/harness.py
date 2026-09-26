"""The harness: one entry point, and the branch that fired is a measurement.

WHAT THE 90/10 GOAL ACTUALLY IS, made explicit. It has been implicit and spread across
local_solver, reasoning_loop and knowledge for a while, which means nobody could state it
and no run could report it. Here it is a shape:

    System 1   cheap, tried first, no candidate generation at all
               - a fact already filed for this exact (concept, subject)
               - a trusted procedure recalled by task similarity
    System 2   deliberate, only after System 1 misses
               - local composition and the grammar
               - and when a task KEYS to a fact we do not have, the HOLE escalates

THE HOLE ESCALATES, NOT THE TASK. That is the difference between this and asking a model to
solve a problem. A task keyed (surface_area, sphere) with no fact on file is a specific,
nameable absence -- so the oracle is asked what the surface area of a sphere IS, and the
answer is slotted into the shape and then put to the task's own assertions. Asked for the
task instead, an answer can be right about the task and useless for the next one; asked for
the fact, the answer is filed under the key and can be reached by a differently-worded
sibling. That is the whole reason the Fact Store exists.

NOTHING HERE IS A NEW TRUST MECHANISM. `task_check` gates every promotion identically
regardless of which system or which source produced the candidate. What is new is only that
the split is reportable: every solve records which of

    system1_fact | system1_recall | system2_local | system2_oracle_hole | unsolved

produced it. That log IS the 90/10 number, and it cannot be produced by a design that does
not know which branch ran.
"""
from __future__ import annotations

import time

BRANCHES = ("system1_fact", "system1_recall", "system2_local", "system2_oracle_hole",
            "code_repair", "unsolved")


def is_code_chunk(task, check: str = "") -> bool:
    """A bare snippet rather than a task specification.

    The distinction that matters: a snippet goes straight to repair_against and NEVER
    through candidate generation, because generating candidates for something that already
    exists as code is how you end up with a second repair mechanism that disagrees with the
    first one.
    """
    t = str(task if isinstance(task, str) else (task or {}).get("text", ""))
    if check:
        return False
    looks_like_code = any(m in t for m in ("def ", "return ", "import ", "class ",
                                           "for ", "while ", "    "))
    has_prose = any(w in t.lower() for w in ("write a function", "write a python",
                                             "given ", "implement a function"))
    return looks_like_code and not has_prose


class Harness:
    def __init__(self, *, loop, solver=None, sandbox=None, learning=None,
                 channel=None, log=None):
        self.loop = loop
        self.solver = solver if solver is not None else getattr(loop, "solver", None)
        self.sandbox = sandbox if sandbox is not None else getattr(loop, "sandbox", None)
        self.learning = learning if learning is not None else getattr(loop, "learning", None)
        self.channel = channel
        self.log: list = log if log is not None else []
        self.counts: dict = {}

    # ------------------------------------------------------------------ the entry
    def solve(self, task, check: str = "", *, learn: bool = True,
              oracle: bool = True) -> dict:
        """`oracle=False` is the fence, and it is checked here rather than at the caller.

        The house may only reach the oracle when the request asks for it. A harness that
        escalated the hole regardless would be a SECOND door into the same ledger, and the
        whole reason the ledger exists is that there is exactly one place the oracle is
        reachable. Offline tools default to True because measuring the hole is what they
        are for.
        """
        t0 = time.time()
        # 1. A snippet is not a task. Repair it with the mechanism that exists.
        if is_code_chunk(task, check):
            r = self.solve_code(str(task), check, learn=learn)
            self.log.append({"task": str(task)[:60], "branch": r["branch"]})
            return r

        task_text = str(task if isinstance(task, str) else (task or {}).get("text", ""))
        if not check.strip():
            # No assertions means nothing can be verified, and nothing unverified is ever
            # kept. Refusing here is the same rule as everywhere else, applied at the door.
            r = {"solved": False, "branch": "unsolved", "reason": "no check: without "
                 "assertions nothing can be verified", "task": task_text[:80]}
            self._count("unsolved")
            return r

        # 2. SYSTEM 1 — a fact for this exact key.
        fact = self._fact(task_text, check)
        if fact.get("found"):
            ok, why = self.loop._attempt({"code": fact["code"],
                                          "label": "fact:%s+%s" % (fact.get("concept"),
                                                                   fact.get("subject"))},
                                         check)
            if ok:
                self._count("system1_fact")
                return self._done(task_text, "system1_fact", fact["code"], t0,
                                  {"key": [fact.get("concept"), fact.get("subject")]})

        # 3. SYSTEM 1 — a procedure recalled by task similarity, no search.
        out = self.loop.step(task_text, check, learn=learn)
        if out.get("outcome") == "solved":
            lbl = str(out.get("candidate") or "")
            branch = ("system1_fact" if lbl.startswith("fact:")
                      else "system1_recall" if lbl.startswith("library:")
                      else "system2_local")
            self._count(branch)
            return self._done(task_text, branch, out.get("code"), t0,
                              {"candidate": lbl, "loop": out})

        # 4. SYSTEM 2 WITH A HOLE — the task keys to a fact we do not have. Escalate the
        #    HOLE, not the task, and slot the answer into the shape the task asked for.
        if not oracle:
            hole = {"solved": False, "reason": "oracle not requested"}
        else:
            hole = self._fill_hole(task_text, check)
            if hole.get("solved"):
                self._count("system2_oracle_hole")
                return self._done(task_text, "system2_oracle_hole", hole.get("code"),
                                  t0, hole)

        self._count("unsolved")
        return {"solved": False, "branch": "unsolved", "task": task_text[:80],
                "loop": out, "hole": hole.get("reason"),
                "seconds": round(time.time() - t0, 2)}

    # ------------------------------------------------------------------ helpers
    def solve_code(self, code: str, check: str, *, learn: bool = True) -> dict:
        """A snippet: repair, verify, and only then consider keeping it."""
        if self.solver is None or not hasattr(self.solver, "repair_against"):
            return {"solved": False, "branch": "unsolved",
                    "reason": "no repair mechanism on this solver", "task": code[:60]}
        try:
            r = self.solver.repair_against(code, check) or {}
        except Exception as exc:
            return {"solved": False, "branch": "unsolved",
                    "reason": "%s: %s" % (type(exc).__name__, str(exc)[:80]),
                    "task": code[:60]}
        ok = bool(r.get("ok") or r.get("success"))
        self._count("code_repair" if ok else "unsolved")
        return {"solved": ok, "branch": "code_repair" if ok else "unsolved",
                "code": r.get("code"), "reason": str(r.get("reason") or "")[:120],
                "task": code[:60]}

    def _fact(self, task: str, check: str) -> dict:
        try:
            return self.solver.recall_fact(task, check) or {}
        except Exception as exc:
            return {"found": False, "reason": "%s: %s" % (type(exc).__name__,
                                                          str(exc)[:70])}

    def _fill_hole(self, task: str, check: str) -> dict:
        """Ask the oracle for the FACT this task keys to, then slot it.

        Only reached when the search has already refused, and only when the task names a
        concept AND a subject -- because a hole with no name is not a hole, it is a wish.
        """
        if self.channel is None:
            return {"solved": False, "reason": "no knowledge channel attached"}
        from .concepts import extract_concept_subject
        concept, subject = extract_concept_subject(task, check)
        if not concept or not subject:
            return {"solved": False, "reason": "the task does not key to a fact"}
        # Ask about the FAILURES, not the task in the abstract: these are the errors the
        # search actually produced, in order, and they are what make the prompt specific
        # enough to be answerable.
        trace = getattr(self.loop, "trace", None) or []
        fails = [t.get("why") for t in list(trace)[-6:]
                 if isinstance(t, dict) and t.get("why")]
        kr = self.channel.ask(task, check, failures=fails or None)
        if not kr.get("accepted"):
            return {"solved": False, "reason": "the oracle's answer did not pass",
                    "key": [concept, subject], "why": str(kr.get("why")
                                                          or kr.get("reason") or "")[:100]}
        return {"solved": True, "code": kr.get("code"), "key": [concept, subject],
                "fact": kr.get("fact")}

    def _done(self, task: str, branch: str, code, t0: float, extra: dict) -> dict:
        out = {"solved": True, "branch": branch, "task": task[:80], "code": code,
               "seconds": round(time.time() - t0, 2)}
        out.update(extra or {})
        # The log IS the 90/10 number. A design that cannot say which branch fired cannot
        # report what its own autonomy is.
        self.log.append({"task": task[:60], "branch": branch})
        return out

    def _count(self, branch: str) -> None:
        self.counts[branch] = self.counts.get(branch, 0) + 1

    def report(self) -> dict:
        """The 90/10 number, and honest about the denominator.

        Autonomy over ATTEMPTS and autonomy over SOLVES are different questions and both
        are reported. Over attempts, "he solved nothing and needed no oracle" reads as
        perfect autonomy -- which is the same confident zero this project keeps having to
        remove. Over solves, it is undefined when nothing was solved, and says so.
        """
        attempts = sum(self.counts.values())
        solved = sum(v for k, v in self.counts.items() if k != "unsolved")
        oracle = self.counts.get("system2_oracle_hole", 0)
        denom = attempts or 1
        return {"counts": dict(sorted(self.counts.items())),
                "share_of_attempts": {k: round(v / denom, 3)
                                      for k, v in sorted(self.counts.items())},
                "attempts": attempts, "solved": solved,
                "unsolved": self.counts.get("unsolved", 0),
                "oracle_share_of_attempts": round(oracle / denom, 3),
                "oracle_share_of_solves": (round(oracle / solved, 3) if solved else None),
                "autonomy_over_solves": (round(1.0 - oracle / solved, 3)
                                         if solved else None),
                "branches_seen": sorted(self.counts)}
