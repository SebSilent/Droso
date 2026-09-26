"""The knowledge channel: the oracle, asked for the one thing he cannot invent.

Where this comes from is a measurement, not a plan. Four levers were pulled at the coding
goal and all four read zero -- 56 verified exercises into the library (MBPP held-out
19 -> 19), a second step chosen by the previous step's failure (22 follow-on candidates,
13 repair rounds, no new solve), a goal-conditioned head for ranking (five tasks in a
hundred), and a program grammar that emits loops and accumulators instead of expressions
(19 -> 19 again).

Then the failures were read instead of guessed at. Of 24 refused tasks, hints generated for
19 and programs for 14, so it was not a generation gap. The tasks were the surface area of a
sphere, the circumference of a circle, the angle of a complex number, the Eulerian number
a(n, m), the sum of the divisors, square roots by the Babylonian method. Each was written as
a one-line formula and put to the task's OWN assertions, and four of six were accepted.
Those tasks were always solvable. He was not failing to find the answer; he did not have
it. 4*pi*r**2 cannot be reached from a table of operations by any arrangement of steps.

That is what the oracle is for here, and the only thing it is for: not to solve the task,
but to supply the fact the generator cannot derive. The system prompt it already carries
says exactly this -- a knowledge oracle for a program-synthesis agent, answer the question
only, never take actions.

THE FOUR RULES THIS KEEPS.

1. Nothing is kept that the task's own assertions do not accept. The oracle is a source of
   text. Execution decides. A wrong formula is dropped exactly like a wrong primitive, and
   the rejection is recorded with the reason.

2. Every call is recorded with its purpose, so an oracle-assisted solve can never be
   counted as his. The referee's columns -- local, corpus, oracle -- stay separate, because
   a number that merges them is a number that lies.

3. It lives in ONE place. The channel is constructed by the harness and by the tools that
   measure, and nowhere else. An oracle reachable from several places is an oracle whose
   call count nobody can state.

4. It asks about the FAILURE, not the task in the abstract. The errors the search already
   produced go into the question, so the ask is aimed at what actually went wrong rather
   than at the task as written.

    python tools/knowledge_run.py --split holdout --limit 20

MEASURED, AND WHAT IT DOES NOT PROVE. Three passes over 25 held-out tasks: local-only 10,
then with the channel local 10 / oracle 3 / refused 12, then local-only again 13. Gained 3,
all three RECALL of an oracle answer, TRANSFER 0. The three tasks pass 3 won are the same
three the oracle answered.

Before calling that a property of the mechanism, the slice was checked for somewhere to
transfer TO, and it had 12 pairs of tasks sharing two or more concept words -- including the
ideal case, 'surface area of a sphere' beside 'surface area of a cylinder'. Nothing carried
across, and there are two separable reasons, only one of which is this code's fault:

  (a) The shared concepts do not imply a shared fact. A sphere's surface area is 4*pi*r**2
      and a cylinder's is 2*pi*r*h + 2*pi*r**2. Concept-level retrieval would fetch the
      wrong formula -- and the assertions would reject it, correctly, which is the gate
      behaving exactly as designed. On a slice of independent facts, transfer is limited by
      the facts, not by the plumbing.

  (b) THE ACTIONABLE ONE. The channel stores the oracle's ANSWER keyed to the task. It does
      not distil the FACT and key it to the concept, so even where two tasks genuinely share
      a fact -- 'circumference of a circle' beside 'perimeter of a circle' -- there is nothing
      retrievable under 'circumference' for the second to find. The store is a lookup table
      of answers, and calling it a knowledge channel would be a claim the measurement does
      not support.

So the next move is to ask the oracle for the FACT rather than the answer -- a formula in
terms of its own symbols, stored under the concepts it names -- and then to see whether it
carries. Expect (a) to cap the gain on a slice like this one, and do not read a low transfer
number as evidence about the mechanism without first counting how many tasks could have
been helped at all.
"""
from __future__ import annotations

import ast
import json
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "state" / "knowledge_ledger.jsonl"

# Names the assertions call that are never the function under test.
_NOT_THE_TARGET = {"assert", "print", "len", "range", "sum", "set", "list", "tuple",
                   "sorted", "max", "min", "abs", "int", "str", "float", "bool", "dict",
                   "isinstance", "reversed", "all", "any", "round", "map", "filter",
                   "open", "self", "enumerate", "zip", "type"}


def _fenced(text: str) -> str:
    """The first fenced code block, if there is one."""
    m = re.search(r"```(?:python)?\s*(.*?)```", str(text or ""), re.S)
    return m.group(1).strip() if m else ""


def _needs_imports(src: str) -> str:
    """Bring in the module the body actually references.

    The oracle writes `math.pi` and its own example imports math; the body alone does not
    carry the import, and the check is appended to a definition in a fresh file. Importing
    only what is referenced keeps the candidate honest about what it depends on.
    """
    head = []
    for mod in ("math", "cmath", "collections", "itertools", "functools", "re", "string"):
        if re.search(r"\b%s\." % mod, src) and not re.search(r"\bimport\s+%s\b" % mod, src):
            head.append("import %s" % mod)
    for fn in ("prod", "gcd", "lcm", "comb", "perm", "factorial", "isqrt"):
        if re.search(r"\bmath\.%s\b" % fn, src):
            break
    return ("\n".join(head) + "\n\n") if head else ""


class KnowledgeChannel:
    """Ask the oracle for a missing fact; keep it only if the assertions accept it."""

    def __init__(self, *, oracle, loop, learning=None, ledger: Path | None = LEDGER,
                 max_calls_per_task: int = 1, max_tokens: int = 320,
                 retries: int = 2, retry_delay: float = 1.5):
        self.oracle = oracle
        self.loop = loop
        self.learning = learning if learning is not None else getattr(loop, "learning", None)
        self.ledger = ledger
        self.max_calls_per_task = int(max_calls_per_task)
        self.max_tokens = int(max_tokens)
        # An empty completion is not an answer, and asking again is not fabricating: the
        # provider was asked and returned nothing. On the first measured run 12 of 15 calls
        # came back empty while the same question asked directly returned
        # `return a[0].count(a[1])` with finish_reason=stop at both token budgets -- so the
        # empties were transient, and without a retry the channel threw away 80% of its own
        # reach and reported it as a refusal. Retries are counted and still cost what they
        # cost, because a call that returns nothing is not a free call.
        self.retries = int(retries)
        self.retry_delay = float(retry_delay)
        self.retry_count = 0
        self.asked = 0
        self.accepted = 0
        self.facts_filed = 0
        self.facts_skipped = 0
        self.refused = 0
        self.call_failures = 0
        self.tokens = 0
        self.last: dict | None = None

    # ------------------------------------------------------------- the question
    @staticmethod
    def target_of(check: str) -> str | None:
        from .local_solver import _requested
        try:
            names = dict(_requested(check).get("names") or {})
        except Exception:
            return None
        for junk in _NOT_THE_TARGET:
            names.pop(junk, None)
        if not names:
            return None
        return sorted(names.items(), key=lambda kv: -kv[1])[0][0]

    def _question(self, task: str, check: str, target: str, failures) -> str:
        lines = ["In Python, what does %s need to compute?" % target,
                 "Task: %s" % str(task)[:200]]
        calls = [l.strip() for l in str(check).splitlines()
                 if l.strip().startswith("assert")]
        if calls:
            # The calling convention, taken from the assertions themselves, so the answer
            # is shaped for how it will actually be called.
            lines.append("The assertions use it like this: " + calls[0][:150])
        errs = [str(f) for f in (failures or []) if str(f).strip()]
        if errs:
            lines.append("Earlier attempts failed with: " + "; ".join(e[:80] for e in errs[:3]))
        lines.append("Give the complete body of %s as Python. It receives its arguments "
                     "positionally in the tuple a, so the first argument is a[0]. "
                     "Reply with the code only, no explanation." % target)
        return "\n".join(lines)

    # ----------------------------------------------------------- the adaptation
    def _adapt(self, text: str, target: str) -> str | None:
        """The oracle's answer as `def target(*a):` so the assertions can call it.

        If it named its own parameters, they are bound from `a` positionally: the
        assertions call the function positionally, so the parameter names are the oracle's
        business and not the task's, and rebinding them is what lets a correct answer
        survive being written with different names.
        """
        code = _fenced(text) or str(text or "").strip()
        if not code:
            return None
        tree = None
        try:
            tree = ast.parse(code)
        except SyntaxError:
            tree = None
        if tree is not None:
            fns = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
            if fns:
                fn = fns[0]
                names = [a.arg for a in fn.args.args]
                try:
                    body = ast.unparse(ast.fix_missing_locations(
                        ast.Module(body=list(fn.body), type_ignores=[])))
                except Exception:
                    return None
                binds = "\n".join("    %s = a[%d]" % (nm, i) for i, nm in enumerate(names))
                ind = "\n".join(("    " + ln) if ln.strip() else ln
                                for ln in body.splitlines())
                src = "%sdef %s(*a):\n%s\n%s\n" % (_needs_imports(body + code),
                                                   target, binds, ind)
                return src
        # Not a function. If it reads as one expression, that is the whole answer; if it
        # reads as statements, they become the body. Either way the assertions decide.
        body_src = code.strip()
        try:
            expr = ast.parse(body_src, mode="eval")
            inner = ast.unparse(expr.body) if hasattr(ast, "unparse") else body_src
            return "%sdef %s(*a):\n    return %s\n" % (_needs_imports(inner), target, inner)
        except SyntaxError:
            pass
        try:
            ast.parse(body_src)
        except SyntaxError:
            return None
        ind = "\n".join(("    " + ln) if ln.strip() else ln
                        for ln in body_src.splitlines())
        return "%sdef %s(*a):\n%s\n" % (_needs_imports(body_src), target, ind)

    # ----------------------------------------------------------------- the ask
    def ask(self, task: str, check: str, failures=None) -> dict:
        """One question, and the task's own assertions as the only judge."""
        t0 = time.time()
        target = self.target_of(check)
        if not target:
            return {"asked": False, "accepted": False,
                    "reason": "no target name in the assertions"}
        # THE CEILING IS PER TASK, AND NOTHING WAS RESETTING IT. Budget.check enforces
        # per_query, per_TASK and per_day, and start_task() exists to clear the middle
        # one -- and had no caller anywhere in the project. So every call in a process was
        # counted against the first task's ceiling, and from about the fifth call on, every
        # request came back task_budget_exceeded. On the measured run that was 15 of 15
        # refusals with ZERO accepted, while the identical question asked directly worked
        # fine -- because eight short calls happened to fit under 4000 tokens and fifteen
        # long ones do not.
        try:
            self.oracle.budget.start_task()
        except Exception:
            pass
        # The hole is computed BEFORE the call and carried on BOTH paths. It is what was
        # ASKED, and it exists whether or not an answer came back -- a ledger that only
        # records the hole on success is a ledger that cannot show which questions went
        # unanswered, which is the thing worth knowing when the provider is failing.
        try:
            from .concepts import extract_key
            _hole = list(extract_key(task, check))
        except Exception:
            _hole = None
        q = self._question(task, check, target, failures)
        res: dict = {}
        attempts = 0
        while True:
            attempts += 1
            try:
                res = self.oracle.query(q, max_tokens=self.max_tokens, temperature=0.0,
                                        purpose="knowledge")
            except Exception as exc:
                res = {"ok": False,
                       "reason": "%s: %s" % (type(exc).__name__, str(exc)[:110])}
            self.asked += 1
            if res.get("ok") and str(res.get("text") or "").strip():
                break
            if attempts > self.retries:
                break
            self.retry_count += 1
            time.sleep(self.retry_delay * attempts)
        if not res.get("ok") or not str(res.get("text") or "").strip():
            self.call_failures += 1
            reason = str(res.get("reason") or "")
            if not reason or (res.get("ok") and not str(res.get("text") or "").strip()):
                reason = "empty_completion"
            out = {"asked": True, "accepted": False, "call_ok": False,
                   "reason": reason[:120], "attempts": attempts, "hole": _hole,
                   "seconds": round(time.time() - t0, 2)}
            self._record(task, target, out, res=res)
            return out
        self.tokens += int(res.get("prompt_tokens_est") or 0) + \
            int(res.get("completion_tokens_est") or 0)
        code = self._adapt(str(res.get("text") or ""), target)
        if not code:
            self.refused += 1
            out = {"asked": True, "accepted": False, "call_ok": True,
                   "reason": "the answer did not read as code",
                   "answer": str(res.get("text") or "")[:200],
                   "seconds": round(time.time() - t0, 2)}
            self._record(task, target, out, res=res)
            return out
        ok, why = self.loop._attempt({"code": code, "label": "knowledge:oracle"}, check)
        stored = False
        fact = None
        if ok:
            self.accepted += 1
            # The answer passed the task's own assertions, so its fact is now something
            # already trusted. Filing does not depend on whether THIS task needed it: the
            # complaint about the last measurement was that an answer keyed to its task
            # transferred to nothing, and this is the second key.
            try:
                fact = self.distill_fact(task, check, code)
            except Exception as exc:
                fact = {"filed": False, "reason": "%s: %s"
                        % (type(exc).__name__, str(exc)[:80])}
            if self.learning is not None:
                try:
                    self.learning.learn_from_task(
                        task, code, {"source": "oracle", "verified": True,
                                     "language": "python",
                                     "verifier_kind": "task_check"}, verified=True)
                    stored = True
                except Exception:
                    stored = False
        else:
            self.refused += 1
        out = {"asked": True, "accepted": bool(ok), "call_ok": True, "stored": stored,
               "target": target, "code": code, "fact": fact, "hole": _hole,
               "why": (why or "")[:160],
               "model": res.get("model"), "latency_s": res.get("latency_s"),
               "tokens": int(res.get("prompt_tokens_est") or 0) +
                         int(res.get("completion_tokens_est") or 0),
               "seconds": round(time.time() - t0, 2)}
        self._record(task, target, out, res=res)
        return out

    def distill_fact(self, task: str, check: str, code: str) -> dict:
        """File the FACT of an answer under concept+subject.

        Called ONLY after the task's own assertions have accepted the answer, so this adds
        a second index to something already trusted rather than making a new trust
        decision. The reference is the learning store's own key for that procedure, so the
        fact points at a gated object and not at a copied formula -- which is what stops a
        fact outliving the evidence it was filed on.

        If either half of the key cannot be identified the answer is NOT filed. A guessed
        key would be retrieved for the wrong task later, and a fact that arrives when it
        should not is worse than a fact that never arrives.
        """
        from .concepts import extract_key, keyable
        from .learning_loop import signature
        concept, subject, shape = extract_key(task, check)
        if not keyable(task, check):
            self.facts_skipped += 1
            return {"filed": False, "concept": concept, "subject": subject,
                    "shape": shape,
                    "reason": "no usable key -- not filing on a guess (a 'mixed' shape "
                              "means the assertions disagree about what the answer IS)"}
        cortex = getattr(getattr(self.loop, "language", None), "cortex", None)
        binder = getattr(cortex, "binder", None)
        if binder is None or not hasattr(binder, "bind_fact"):
            self.facts_skipped += 1
            return {"filed": False, "concept": concept, "subject": subject,
                    "reason": "no binder to file into"}
        ref = signature(task)
        filed = bool(binder.bind_fact(concept, subject, ref, shape))
        if filed:
            self.facts_filed += 1
        return {"filed": filed, "concept": concept, "subject": subject, "shape": shape,
                "ref": ref, "reason": "filed" if filed else "already filed for this key"}

    # --------------------------------------------------------------- the ledger
    def _record(self, task: str, target: str, out: dict, res=None) -> None:
        # THE HOLE, NOT THE WHOLE TASK. The ledger is the record of what was ASKED, and what
        # was asked is a key -- (concept, subject, shape) -- not a paragraph of task text.
        # Recording the task made the log a list of sentences, which is exactly the shape
        # that hides whether the same hole was asked twice or two tasks were asked once
        # each. The key is the unit of knowledge here and it has to be the unit of the log.
        fact = out.get("fact") or {}
        hole = None
        if out.get("hole"):
            hole = list(out["hole"])
        elif fact.get("concept") or out.get("concept"):
            hole = [fact.get("concept") or out.get("concept"),
                    fact.get("subject") or out.get("subject"),
                    fact.get("shape") or out.get("shape")]
        row = {"at": round(time.time(), 1), "hole": hole,
               "task": str(task)[:140], "target": target,
               "accepted": bool(out.get("accepted")), "call_ok": bool(out.get("call_ok")),
               "reason": str(out.get("why") or out.get("reason") or "")[:160],
               "model": (res or {}).get("model"),
               "tokens": out.get("tokens"),
               "latency_s": (res or {}).get("latency_s"),
               "stored": bool(out.get("stored"))}
        self.last = row
        if self.ledger is None:
            return
        try:
            self.ledger.parent.mkdir(parents=True, exist_ok=True)
            with open(self.ledger, "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
        except Exception:
            pass

    def stats(self) -> dict:
        return {"asked": self.asked, "accepted": self.accepted, "refused": self.refused,
                "facts_filed": self.facts_filed, "facts_skipped": self.facts_skipped,
                "call_failures": self.call_failures, "retries": self.retry_count,
                "tokens": self.tokens,
                "accept_rate": (round(self.accepted / self.asked, 3)
                                if self.asked else None),
                "provider": getattr(self.oracle, "provider", None),
                "model": getattr(self.oracle, "model", None)}
