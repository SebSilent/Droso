"""Track E: the reasoning loop.

Three things make this a loop rather than a router.

**Candidates come from three places at once.** Verified procedures from the library,
compositions of them, and bare primitives that no procedure covers. A router picks one
rung; a search has to have several things to compare before it can compare anything.

**The choice is made by a goal-conditioned head, not by similarity.** Similarity says
which memory is nearest the question. It cannot say whether trying it will pass, which
is the only thing that matters when the task must be solved or refused. So
`higher_cortex.OutcomeHead` is trained on (state, action, goal) -> did it pass, and the
candidates are ranked by what it expects. It is wrong at first by construction; the
measurement that matters is whether its error trends DOWN on attempted actions, which
is the difference between a loop that searches and a loop that only executes.

**Every attempt goes through the connectome before it is executed.** `engine.decide()`
sets the eligibility trace that three-factor plasticity needs, and `teach()` fires
afterwards with the outcome. Skip the decide and teach gates nothing: the loop would
score and execute candidates while its own brain learned from none of them. That
ordering is not optional and it is the reason this module exists rather than a scoring
function inside the router.

The hard constraint, which must not be relaxed: **`task_check` is the only gate that
promotes a procedure.** Goal-drive overlap and predicted progress decide the ORDER
candidates are tried in, never whether one is kept. Ranking is a hypothesis; the task's
own assertions are the evidence. A loop that let drive-overlap promote would be
rewarding the feeling of having solved something, which is a failure mode nothing else
in this project's evidence taxonomy covers and one worth not inventing.

A refusal is a first-class outcome. When nothing plausible remains the loop says so and
stops; it does not promote the least-bad attempt.
"""
from __future__ import annotations

import time

import numpy as np

# Operation hints. The task says what it wants, and it says it in plain words --
# "find the largest", "count the elements", "reverse the string". Mapping those words
# to candidate bodies is generation without a model, and it is honest because the
# candidate is only a hypothesis: the task's own assertions accept or reject it, and
# nothing is kept that does not run.
#
# This is aimed squarely at the measured bottleneck. diagnose() on held-out tasks found
# that 65% of failures had NO passing candidate ever generated and only 5% were a
# ranking miss, so the fix was never a better head -- it was more things to choose from.
HINTS = (
    (("largest", "biggest", "greatest", "maximum", " max"), "return max(a[0])"),
    (("smallest", "least", "minimum", " min"), "return min(a[0])"),
    (("count", "number of", "how many", "length", "size"), "return len(a[0])"),
    (("sum", "total of", "add all", "adds all"), "return sum(a[0])"),
    (("average", "mean"), "return sum(a[0]) / len(a[0])"),
    (("reverse", "reversed", "backwards", "backward"), "return a[0][::-1]"),
    (("descending", "decreasing"), "return sorted(a[0], reverse=True)"),
    (("sort", "sorted", "ascending", "increasing", "order"), "return sorted(a[0])"),
    (("unique", "distinct", "duplicate"), "return list(set(a[0]))"),
    (("even"), "return [x for x in a[0] if x % 2 == 0]"),
    (("odd"), "return [x for x in a[0] if x % 2 == 1]"),
    (("square"), "return [x * x for x in a[0]]"),
    (("cube", "cubic"), "return [x * x * x for x in a[0]]"),
    (("product", "multiply", "multiplication"), "return math.prod(a[0])"),
    (("absolute", "modulus"), "return abs(a[0])"),
    (("negate", "negative", "invert sign"), "return -a[0]"),
    (("uppercase", "upper", "capital"), "return a[0].upper()"),
    (("lowercase", "lower"), "return a[0].lower()"),
    (("first", "beginning"), "return a[0][0]"),
    (("last", "final", "end of"), "return a[0][-1]"),
    (("join", "concatenate", "combine"), "return ''.join(str(x) for x in a[0])"),
    (("flatten", "nested list"), "return [y for x in a[0] for y in x]"),
    (("factorial"),
     "return math.factorial(a[0]) if isinstance(a[0], int) and 0 <= a[0] <= 200 else None"),
    (("prime"), "return all(a[0] % i for i in range(2, int(a[0] ** 0.5) + 1)) if a[0] > 1 else False"),
    (("gcd", "greatest common"), "return math.gcd(a[0], a[1])"),
    (("power", "exponent"),
     "return a[0] ** a[1] if isinstance(a[1], int) and abs(a[1]) <= 64 else None"),
    (("nth", "index of", "element at"), "return a[0][a[1]]"),
    (("slice", "first n", "last n"), "return a[0][:a[1]]"),
    (("difference", "subtract"), "return a[0] - a[1]"),
    (("divisible", "divisor", "divides"), "return a[0] % a[1] == 0"),
    (("swap", "exchange"), "return (a[1], a[0])"),
    (("remove", "delete", "without"), "return [x for x in a[0] if x != a[1]]"),
    (("append", "add the"), "return list(a[0]) + [a[1]]"),
    (("union", "common", "intersection", "shared"), "return list(set(a[0]) & set(a[1]))"),
    (("contains", "whether", "present"), "return a[1] in a[0]"),
    (("split"), "return a[0].split()"),
    (("replace", "substitute"), "return a[0].replace(a[1], a[2])"),
    (("strip", "trim", "whitespace"), "return a[0].strip()"),
)

# Two operations in sequence, for the tasks whose own words name both halves.
HINT_PAIRS = (
    ("sorted", "reverse", "return sorted(a[0])[::-1]"),
    ("set", "sorted", "return sorted(set(a[0]))"),
    ("even", "count", "return len([x for x in a[0] if x % 2 == 0])"),
    ("odd", "count", "return len([x for x in a[0] if x % 2 == 1])"),
    ("sum", "count", "return sum(a[0]) / len(a[0])"),
    ("largest", "count", "return len([x for x in a[0] if x == max(a[0])])"),
    ("split", "count", "return len(a[0].split())"),
    ("unique", "count", "return len(set(a[0]))"),
)

PRIMITIVES = (
    ("return a[0]", "arg0"),
    ("return sorted(a[0])", "sorted_arg0"),
    ("return sorted(a[0], reverse=True)", "sorted_desc_arg0"),
    ("return max(a[0])", "max_arg0"),
    ("return min(a[0])", "min_arg0"),
    ("return sum(a[0])", "sum_arg0"),
    ("return len(a[0])", "len_arg0"),
    ("return list(set(a[0]))", "dedupe_arg0"),
    ("return a[0][::-1]", "reverse_arg0"),
    ("return a[0] + a[1]", "sum_two"),
    ("return a[0] - a[1]", "diff_two"),
    ("return a[0] * a[1]", "product_two"),
    ("return a[0] / a[1]", "quotient_two"),
    ("return a[0] % a[1]", "mod_two"),
    ("return a[0] in a[1]", "contains_two"),
    ("return a[0].lower()", "lower_arg0"),
    ("return a[0].upper()", "upper_arg0"),
    ("return a[0].split()", "split_arg0"),
    ("return a[0].strip()", "strip_arg0"),
    ("return [x for x in a[0] if x]", "truthy_arg0"),
)


class ReasoningLoop:
    def __init__(self, *, solver, learning, sandbox, language=None, goal=None,
                 router=None, engine=None, tokenizer=None, floor: float = 0.15,
                 top_k: int = 3, budget: int = 10, use_primitives: bool = True,
                 repair_budget: int = 4):
        self.solver = solver
        self.learning = learning
        self.sandbox = sandbox
        self.language = language
        self.goal = goal
        self.router = router
        self.engine = engine
        self.tokenizer = tokenizer
        self.floor = float(floor)
        self.top_k = int(top_k)
        self.budget = int(budget)
        self.use_primitives = bool(use_primitives)
        # 5b. Follow-on steps are paid for out of a SEPARATE budget, so multi-step can
        # only ever add attempts to an episode and never take one away from the main
        # list. Without that, repairing a bad first guess would compete with exploring
        # the candidates that were ranked below it, and the change could quietly make
        # the loop worse while looking like progress.
        self.repair_budget = int(repair_budget)
        self.repairs = 0
        self.episodes = 0
        self.attempts = 0
        self.solved = 0
        self.tried: dict = {}          # label -> attempts, for need_novelty
        # ONE TRUST-GATED OBJECT, TWO INDEXES. The fact store IS the language cortex's
        # binder: a procedure is reachable by task similarity as it always was, and by
        # concept+subject through a separate exact key. Nothing new is trusted; the same
        # task_check gate promotes the procedure either way, and the fact only ever
        # points at one that already passed.
        try:
            cortex = getattr(self.language, "cortex", None) if self.language else None
            binder = getattr(cortex, "binder", None)
            if self.solver is not None and binder is not None:
                self.solver.fact_store = binder
        except Exception:
            pass
        self.trace: list = []

    # ---------------------------------------------------------------- candidates
    def _from_library(self, task: str) -> list:
        """Verified procedures, ranked by how much of the task they share."""
        import re
        want = set(re.findall(r"[a-z]{4,}", str(task or "").lower()))
        out = []
        for sig, rec in (self.learning.store or {}).items():
            if not (rec.get("successes") or float(rec.get("confidence", 0)) >= 0.5):
                continue
            code = ""
            for s in reversed(rec.get("solutions") or []):
                if s.get("text") and not s.get("truncated"):
                    code = str(s["text"])
                    break
            if not code.strip():
                continue
            have = set(re.findall(r"[a-z]{4,}", str(rec.get("task", "")).lower()))
            ov = len(want & have) / max(1, len(want | have))
            out.append({"code": code, "label": f"lib:{sig[:40]}",
                        "score": ov, "task": str(rec.get("task", ""))[:80]})
        out.sort(key=lambda c: -c["score"])
        return out[:12]

    def _from_primitives(self, task: str, check: str) -> list:
        if not self.use_primitives:
            return []
        from .local_solver import _requested
        req = _requested(check)
        names = dict(req.get("names") or {})
        for junk in ("assert", "print", "len", "range", "set", "list", "tuple",
                     "sorted", "sum", "max", "min", "abs", "int", "str", "float",
                     "bool", "dict", "zip", "enumerate", "reversed", "isinstance",
                     "type", "round", "any", "all", "map", "filter", "open"):
            names.pop(junk, None)
        if not names:
            return []
        target, arity = sorted(names.items(), key=lambda kv: -kv[1])[0]
        out = []
        for body, label in PRIMITIVES:
            if arity < 1:
                continue
            if ("a[1]" in body) and arity < 2:
                continue
            if ("a[1]" not in body) and arity != 1:
                continue
            out.append({"code": f"def {target}(*a):\n    {body}\n",
                        "label": f"prim:{label}", "score": 0.0,
                        "task": label})
        return out

    def _from_hints(self, task: str, check: str) -> list:
        """Candidates whose body is chosen by the words of the task itself.

        Ranked above the blind primitives, because a body the task asked for is a better
        hypothesis than the next one in a list, and the ranking it feeds is only about
        what to try first -- the assertions still decide.
        """
        from .local_solver import _requested
        req = _requested(check)
        names = dict(req.get("names") or {})
        for junk in ("assert", "print", "len", "range", "set", "list", "tuple",
                     "sorted", "sum", "max", "min", "abs", "int", "str", "float",
                     "bool", "dict", "zip", "enumerate", "reversed", "isinstance",
                     "type", "round", "any", "all", "map", "filter", "open"):
            names.pop(junk, None)
        if not names:
            return []
        target, arity = sorted(names.items(), key=lambda kv: -kv[1])[0]
        low = " " + " ".join(str(task).lower().split()) + " "
        out = []
        for words, body in HINTS:
            if not any(w in low for w in words):
                continue
            needs_two = "a[1]" in body or "a[2]" in body
            if needs_two and arity < 2:
                continue
            if not needs_two and arity != 1:
                continue
            code = "import math\n\ndef %s(*a):\n    %s\n" % (target, body)
            if "math." not in body:
                code = "def %s(*a):\n    %s\n" % (target, body)
            out.append({"code": code, "label": "hint:" + words[0],
                        "score": 0.35, "task": words[0]})
        for w1, w2, body in HINT_PAIRS:
            if w1 in low and w2 in low and arity == 1:
                out.append({"code": "def %s(*a):\n    %s\n" % (target, body),
                            "label": "hint2:%s+%s" % (w1, w2),
                            "score": 0.4, "task": w1 + " " + w2})
        return out

    # ------------------------------------------------------- 5b, the other half
    # THE MEASURED WALL. Three things were tried and all three read zero: 56 verified
    # exercises into the library (MBPP holdout 19 -> 19), a second step chosen by the
    # previous step's failure (22 follow-ons, 13 repair rounds, no new solve), and a
    # goal-conditioned head for ranking (five tasks in a hundred). What is left is the one
    # thing that was always left: every candidate so far has been a SINGLE EXPRESSION.
    # `return max(a[0])`. An acronym builder, an affine cipher, a beer song are not
    # expressions, and no amount of retrieval, chaining or re-ranking reaches them from a
    # table of expressions. So the candidate is now a PROGRAM -- a statement sequence with
    # a loop and an accumulator, chosen by the words of the task.
    #
    # This is generation from a small grammar rather than more search over a bigger list,
    # and the grammar is deliberately tiny and legible. Every candidate is still only a
    # hypothesis: the task's own assertions accept or reject it, and nothing that does not
    # run is kept.
    PROGRAM_SHAPES = (
        # (words that call for this shape, the indented body, the inner-expression class)
        (("count", "occurrences", "how many", "number of times", "times ", "divisible"),
         "    return sum(1 for x in a[0] if {c})", "cond"),
        (("frequency", "occurrence of each", "each element", "tally", "how many times each"),
         "    d = {}\n    for x in a[0]:\n        d[x] = d.get(x, 0) + 1\n    return d", "none"),
        (("squares", "double", "individual element", "each element", "apply", "cube"),
         "    out = []\n    for x in a[0]:\n        out.append({e})\n    return out", "map"),
        (("sum", "total", "add"),
         "    t = 0\n    for x in a[0]:\n        t += {e}\n    return t", "sum"),
        (("even", "odd", "filter", "only", "positive", "negative", "greater than"),
         "    out = []\n    for x in a[0]:\n        if {c}:\n            out.append(x)\n    return out",
         "cond"),
        (("acronym", "initials", "first letter", "first character"),
         "    return ''.join(w[0] for w in a[0].split()).upper()", "none"),
        (("uppercase", "capital", "title case"),
         "    return ' '.join(w.capitalize() for w in a[0].split())", "none"),
        (("word", "words", "split"),
         "    return a[0].split()", "none"),
        (("reverse", "backward", "backwards"),
         "    return a[0][::-1]", "none"),
        (("flatten", "nested", "each list"),
         "    out = []\n    for xs in a[0]:\n        for x in xs:\n            out.append(x)\n    return out",
         "none"),
        (("pairs", "combinations", "two lists", "every pair"),
         "    out = []\n    for x in a[0]:\n        for y in a[1]:\n            out.append((x, y))\n    return out",
         "none"),
        (("join", "concatenate", "combine all"),
         "    return ''.join(str(x) for x in a[0])", "none"),
        (("maximum", "largest", "biggest"),
         "    m = a[0][0]\n    for x in a[0]:\n        if x > m:\n            m = x\n    return m",
         "none"),
        (("minimum", "smallest"),
         "    m = a[0][0]\n    for x in a[0]:\n        if x < m:\n            m = x\n    return m",
         "none"),
        (("distinct", "unique", "duplicate", "remove duplicates"),
         "    out = []\n    for x in a[0]:\n        if x not in out:\n            out.append(x)\n    return out",
         "none"),
    )
    # The inner expressions a shape may be filled with. Kept small and legible: this is a
    # grammar, not a search space to be fuzzed.
    _INNER = {
        "map": (("square", "x * x"), ("double", "x * 2"), ("cube", "x ** 3"),
                ("string", "str(x)"), ("length", "len(x)"), ("first", "x[0]"),
                ("letter", "ord(x)"), ("upper", "x.upper()"), ("lower", "x.lower()"),
                ("increment", "x + 1"), ("absolute", "abs(x)"), ("", "x")),
        "sum": (("square", "x * x"), ("count", "1"), ("length", "len(x)"),
                ("absolute", "abs(x)"), ("", "x")),
        "cond": (("element", "x == a[1]"), ("even", "x % 2 == 0"),
                 ("odd", "x % 2 == 1"), ("in the", "x in a[1]"),
                 ("positive", "x > 0"), ("negative", "x < 0"),
                 ("zero", "x != 0"), ("", "True")),
    }

    def _from_programs(self, task: str, check: str, cap: int = 14) -> list:
        """Candidates that are programs, chosen by the words of the task."""
        from .local_solver import _requested
        names = dict(_requested(check).get("names") or {})
        for junk in ("assert", "print", "len", "range", "set", "list", "tuple", "sorted",
                     "sum", "max", "min", "abs", "int", "str", "float", "bool", "dict",
                     "zip", "enumerate", "reversed", "isinstance", "type", "round", "any",
                     "all", "map", "filter", "open", "self"):
            names.pop(junk, None)
        if not names:
            return []
        target = sorted(names.items(), key=lambda kv: -kv[1])[0][0]
        low = " " + " ".join(str(task).lower().split()) + " "
        out: list = []
        for words, body, kind in self.PROGRAM_SHAPES:
            hits = [w for w in words if w in low]
            if not hits:
                continue
            if kind == "none":
                out.append(self._prog(target, body, "prog:%s" % hits[0], 0.45,
                                      task, hits[0]))
                continue
            for w, expr in self._INNER[kind]:
                # Prefer the fill the task actually names, but offer the rest: the words
                # rank the candidates and the assertions still decide.
                score = 0.45 if (w and w in low) else 0.3
                if kind == "cond":
                    filled = body.replace("{c}", expr)
                else:
                    filled = body.replace("{e}", expr)
                tag = "%s+%s" % (hits[0], w or "plain")
                out.append(self._prog(target, filled, "prog:%s" % tag, score, task, tag))
        # Highest-scoring first, and capped: execution costs a subprocess each, so the
        # grammar has to be ranked before it is run rather than enumerated blindly.
        out.sort(key=lambda c: -float(c.get("score") or 0))
        return out[:int(cap)]

    @staticmethod
    def _prog(target: str, body: str, label: str, score: float, task: str,
              tag: str) -> dict:
        return {"code": "def %s(*a):\n%s\n" % (target, body), "label": label,
                "score": score, "task": tag}

    def _candidates(self, task: str, check: str) -> list:
        cands = list(self._from_library(task))
        # SYSTEM 1, BEFORE THE SEARCH: a fact already filed for this exact (concept,
        # subject). Tried first because it is the cheapest thing there is -- one fixed-key
        # store lookup and no candidate generation at all.
        #
        # The label is the point. `fact:surface_area+sphere` in the solve record is what
        # makes TRANSFER structural instead of something a human has to notice: a task
        # solved by this path was solved by knowledge that came from a DIFFERENT task,
        # whereas `library:` is the same task coming back. The last measurement conflated
        # the two and only reported transfer 0 because someone read the identities by hand.
        self.last_fact = None
        try:
            fact = self.solver.recall_fact(task, check)
        except Exception as exc:
            fact = {"found": False,
                    "reason": "%s: %s" % (type(exc).__name__, str(exc)[:60])}
        self.last_fact = fact
        if fact and fact.get("found") and str(fact.get("code") or "").strip():
            cands.insert(0, {"code": fact["code"],
                             "label": "fact:%s+%s" % (fact.get("concept"),
                                                      fact.get("subject")),
                             "score": 0.6, "task": ""})
        # Hints before blind primitives: a body the task's own words asked for is a
        # better first hypothesis than the next entry in a fixed list.
        try:
            cands += self._from_hints(task, check)
        except Exception:
            pass
        # Programs before expressions: a shape the task named is a better hypothesis
        # than a one-liner, and this is the class that has never been generated at all.
        try:
            cands += self._from_programs(task, check)
        except Exception:
            pass
        if self.use_primitives:
            cands += self._from_primitives(task, check)
        comp = {}
        try:
            comp = self.solver.compose_against(task, check, budget=4) or {}
        except Exception as e:
            comp = {"ok": False, "reason": f"{type(e).__name__}"[:60]}
        if comp.get("ok"):
            cands.insert(0, {"code": comp["code"],
                             "label": "compose:" + str(comp.get("method")),
                             "score": 1.0, "task": task[:80]})
        return cands, comp

    # ---------------------------------------------------------------- scoring
    def _vectors(self, task: str, cand: dict, goal_vec):
        """state = what the task means, action = what the candidate is, goal = held."""
        space = None
        for who in (self.language, None):
            if who is not None and getattr(who, "cortex", None) is not None:
                space = who.cortex.space
                break
        if space is None:
            return None, None, goal_vec
        s = space.of(" ".join(str(task).lower().split()[:12]))
        a = space.of(str(cand.get("task") or cand.get("label") or "").lower()[:120])
        return s, a, goal_vec

    def _goal_vector(self):
        if self.goal is None or not getattr(self.goal, "text", None):
            return None
        if self.language is not None and getattr(self.language, "cortex", None):
            return self.language.cortex.space.of(self.goal.text)
        return None

    # ---------------------------------------------------------------- the loop
    def step(self, task: str, check: str, *, learn: bool = True) -> dict:
        t0 = time.time()
        self.episodes += 1
        from .local_solver import _requested
        req = _requested(check)
        names = dict(req.get("names") or {})
        for junk in ("assert", "print"):
            names.pop(junk, None)
        target = sorted(names.items(), key=lambda kv: -kv[1])[0][0] if names else None

        if self.goal is not None and hasattr(self.goal, "hold"):
            try:
                self.goal.hold(f"solve: {str(task)[:70]}")
            except Exception:
                pass
        goal_vec = self._goal_vector()
        goal_drive = None
        if self.goal is not None and hasattr(self.goal, "drive"):
            try:
                goal_drive = self.goal.drive()
            except Exception:
                goal_drive = None

        cands, comp = self._candidates(task, check)
        if not cands:
            return self._finish(task, None, None, {
                "outcome": "no_candidates", "escalate": True,
                "reason": (comp or {}).get("reason") or "nothing to try",
                "seconds": round(time.time() - t0, 2)})

        # Rank by the goal-conditioned head. This decides order only.
        head = None
        if self.language is not None and getattr(self.language, "cortex", None):
            head = getattr(self.language.cortex, "outcome", None)
        scored = []
        for c in cands:
            s, a, g = self._vectors(task, c, goal_vec)
            conf = float(c.get("score") or 0.0)
            if head is not None and s is not None:
                p = head.predict(s, a, g)
            else:
                p = 0.5
            # Retrieval agreement and predicted success both rank; neither promotes.
            c["_pred"] = round(float(p), 4)
            c["_rank"] = 0.5 * float(p) + 0.5 * conf
            c["_state"] = s
            c["_action"] = a
            scored.append(c)
        scored.sort(key=lambda c: -c["_rank"])
        top = scored[:max(1, self.top_k)]
        # need_novelty: at least one candidate never tried before, or the loop keeps
        # rerunning the same first idea and learns nothing new about the rest.
        untried = [c for c in scored if self.tried.get(c["label"], 0) == 0]
        if untried and not any(self.tried.get(c["label"], 0) == 0 for c in top):
            top[-1] = untried[0]

        best_pred = max((c["_pred"] for c in scored), default=0.0)
        if best_pred < self.floor and not any(c.get("score", 0) > 0 for c in scored):
            return self._finish(task, None, None, {
                "outcome": "below_floor", "escalate": True,
                "best_pred": best_pred, "floor": self.floor,
                "candidates": len(scored),
                "seconds": round(time.time() - t0, 2)})

        tried = 0
        # The head's top_k sets the ORDER, and the budget sets how far down it the loop
        # will go. But the sources have to be interleaved first, or the biggest one
        # starves the rest: with 620 procedures in the library, twelve retrieved
        # candidates plus fourteen primitives against a budget of ten means the
        # primitives are never reached at all, and the loop looks like it only knows
        # how to recall. Round-robin by source, so each gets a turn before the budget
        # runs out.
        ranked_order = list(top) + [c for c in scored if c not in top]
        by_source: dict = {}
        for c in ranked_order:
            src = str(c["label"]).split(":")[0]
            by_source.setdefault(src, []).append(c)
        order: list = []
        depth = 0
        while any(len(v) > depth for v in by_source.values()):
            for src in sorted(by_source,
                              key=lambda s: (s != "compose", s)):
                bucket = by_source[src]
                if depth < len(bucket):
                    order.append(bucket[depth])
            depth += 1
        # 5b makes this an index loop: a step that fails can put a follow-on step in
        # front of the rest of the list, so the order is no longer fixed before it runs.
        i = 0
        repairs = 0
        max_tries = int(self.budget) + int(self.repair_budget)
        while i < len(order):
            c = order[i]
            i += 1
            if tried >= max_tries:
                break
            tried += 1
            self.attempts += 1
            self.tried[c["label"]] = self.tried.get(c["label"], 0) + 1
            # 1. through the connectome FIRST: decide() sets the eligibility trace
            #    that teach() needs. Without it the brain learns from none of this.
            decided = None
            if self.engine is not None and self.tokenizer is not None:
                try:
                    code = self.tokenizer.encode(str(c.get("task") or c["label"]))
                    extra = [goal_drive] if goal_drive is not None else None
                    decided = int(self.engine.decide(code, extra_drive=extra))
                except Exception:
                    decided = None
            # 2. execute, and let the task's own assertions decide
            passed, why = self._attempt(c, check)
            # 3. the two heads learn, separately
            err_state = err_out = None
            if head is not None and c.get("_state") is not None:
                pred_out = float(c["_pred"])
                err_out = head.update(c["_state"], c["_action"], goal_vec,
                                      1.0 if passed else 0.0)
                # The state head keeps its own target: what actually happened.
                err_state = None
            # 4. reward is the difference between what he expected and what happened
            rpe = (1.0 if passed else 0.0) - float(c.get("_pred") or 0.5)
            if self.engine is not None and decided is not None:
                try:
                    self.engine.teach(float(rpe) * 2.0)
                except Exception:
                    pass
            if self.language is not None:
                if passed and hasattr(self.language, "note_event"):
                    try:
                        self.language.note_event("task", f"passed {str(task)[:50]}")
                    except Exception:
                        pass
                if not passed and hasattr(self.language, "adversity"):
                    try:
                        self.language.adversity("task_failed",
                                                str(why or "")[:120], 0.4)
                    except Exception:
                        pass
                # Four propositions per attempt is right in principle and wrong at
                # this scale: Binder.remember grows X with np.vstack, so every one of
                # them copies the whole proposition matrix -- 123 MB per call at
                # 30,091 propositions, four times per attempt, ten attempts per task.
                # The house reached 6.9 GB resident. Two are kept because they carry
                # the facts that matter for later questions (what was tried, and
                # whether it worked); the prediction and the surprise are still in
                # the loop's own trace and in the outcome head's error history, so
                # nothing is lost except the duplicate record of it.
                for verb, obj in (("tries", c["label"]),
                                  ("passes" if passed else "fails",
                                   str(task)[:60])):
                    try:
                        self.language.experience("droso", verb, obj)
                    except Exception:
                        pass
            rec = {"label": c["label"], "pred": c.get("_pred"),
                   "fact": (self.last_fact or {}).get("reason"),
                   "rank": round(float(c.get("_rank") or 0), 4),
                   "passed": bool(passed), "why": (why or "")[:120],
                   "outcome_error": err_out, "rpe": round(float(rpe), 4),
                   "step": c.get("_step"), "because": c.get("_because"),
                   "from": c.get("_from"),
                   "decided_pool": decided}
            self.trace.append({"task": str(task)[:60], **rec})
            if passed:
                self.solved += 1
                stored = False
                if learn and target:
                    try:
                        self.learning.learn_from_task(
                            task, c["code"],
                            {"source": c["label"].split(":")[0], "verified": True,
                             "language": "python", "verifier_kind": "task_check"},
                            verified=True)
                        stored = True
                    except Exception:
                        pass
                out = self._finish(task, c, rec, {
                    "outcome": "solved", "stored": stored,
                    "best_pred": best_pred, "candidates": len(scored),
                    "seconds": round(time.time() - t0, 2)})
                if self.goal is not None and hasattr(self.goal, "release"):
                    try:
                        self.goal.release()
                    except Exception:
                        pass
                return out
            # 5b. A failure is information, not only a verdict: use it to choose the
            # next step. The follow-on is built from the candidate that just failed, so
            # it is a second step and not another first guess, and it goes in at the
            # FRONT of what remains because it is conditioned on what was just observed.
            # The goal is not re-held here -- it is held for the whole episode and the
            # organ's half-life spans the chain, so one goal conditions every step.
            if repairs < self.repair_budget and not str(c["label"]).startswith("step2:"):
                try:
                    follow = self._next_from_failure(c, why, check)
                except Exception:
                    follow = []
                follow = [f for f in follow if self.tried.get(f["label"], 0) == 0]
                if follow:
                    for f in follow:
                        f["_step"] = 2
                    order[i:i] = follow
                    repairs += 1
                    self.repairs += 1
        out = self._finish(task, None, None, {
            "outcome": "refused", "best_pred": best_pred,
            "candidates": len(scored), "attempts": tried,
            "seconds": round(time.time() - t0, 2)})
        # release-on-timeout is a different fact from release-on-success, and the goal
        # organ already records them separately.
        if self.goal is not None and hasattr(self.goal, "release"):
            try:
                self.goal.release()
            except Exception:
                pass
        return out

    # ------------------------------------------------------------------ 5b
    # MULTI-STEP: the next step is chosen by what the last one actually did.
    #
    # This was the missing half. The loop generated candidates, executed them, recorded
    # the failure and moved to the next item on a list -- so no step ever depended on the
    # outcome of any other, and a task needing two operations in sequence could only be
    # solved if a single candidate happened to contain both. A chain chosen by an
    # observed result is reasoning; a chain chosen by a fixed list is enumeration with
    # extra steps.
    #
    # What the step actually did is in the error, or in the fact that it ran and returned
    # the wrong shape. Both are read here, and the follow-on is generated from the
    # candidate that failed rather than from the task again -- which is what makes it a
    # second step instead of another first guess. The goal is not re-derived either: it
    # was held at the start of the episode and the organ's half-life spans the chain, so
    # the same goal conditions every step of it.
    _FAIL_SHAPE = (
        ("not subscriptable", "scalar_indexed", "it indexed a scalar"),
        ("not iterable", "scalar_iterated", "it iterated a scalar"),
        ("NoneType", "none_returned", "it worked on nothing"),
        ("index out of range", "length", "it ran off the end"),
        ("unexpected keyword argument", "arity", "the signature was wrong"),
        ("required positional argument", "arity", "the signature was wrong"),
        ("too many positional", "arity", "the signature was wrong"),
        ("is not defined", "name", "the name was wrong"),
        ("has no attribute", "attribute", "it called a method the type lacks"),
        ("unsupported operand type", "operand", "the types did not combine"),
        ("ZeroDivisionError", "degenerate", "it divided by nothing"),
        ("RecursionError", "runaway", "it called itself forever"),
        ("KeyError", "missing_key", "the key was absent"),
        ("ValueError", "bad_value", "the value was malformed"),
        ("assert", "wrong_result", "it ran and returned the wrong thing"),
    )

    def _next_from_failure(self, cand: dict, why: str, check: str) -> list:
        """The next step, built from the one that failed and the way it failed.

        Returns candidates whose labels carry the chain (step2:<label>), so an episode
        shows what was tried, what it did, and what was tried because of it -- rather
        than a list of unrelated attempts.
        """
        import re as _re
        code = str(cand.get("code") or "")
        m = _re.search(r"def\s+(\w+)\s*\(", code)
        if not m:
            return []
        target = m.group(1)
        bm = _re.search(r"def\s+\w+\s*\([^)]*\):\s*\n(.*)\Z", code, _re.S)
        if not bm:
            return []
        body = bm.group(1).rstrip()
        w = str(why or "")
        # Case-insensitive: the commonest failure in the corpus is a plain
        # "AssertionError" -- the step ran and returned the wrong thing -- and a
        # case-sensitive match against "assert" missed every one of them.
        wl = w.lower()
        kind, said = None, ""
        for needle, k, phrase in self._FAIL_SHAPE:
            if needle.lower() in wl:
                kind, said = k, phrase
                break
        if kind is None:
            return []

        def mk(b: str, tag: str, score: float = 0.3) -> dict:
            head = "import math\n\n" if "math." in b else ""
            return {"code": "%sdef %s(*a):\n    %s\n" % (head, target, b),
                    "label": "step2:%s" % tag, "score": score,
                    "task": cand.get("task") or "",
                    "_because": said, "_from": cand.get("label")}

        out: list = []
        if kind in ("scalar_indexed", "scalar_iterated", "wrong_result", "length",
                    "none_returned"):
            # The operation is at the wrong nesting level. This is the commonest shape
            # failure: the step is right about WHAT to do and wrong about how deep to
            # reach for it. Deeper, shallower, and wrapped are the three answers.
            if "a[0]" in body:
                out.append(mk(body.replace("a[0]", "a[0][0]"), "deeper"))
                out.append(mk(body.replace("a[0]", "a"), "shallower"))
                out.append(mk(body.replace("a[0]", "list(a[0])"), "as_list"))
                out.append(mk(body.replace("a[0]", "str(a[0])"), "as_str"))
        if kind in ("scalar_iterated", "wrong_result"):
            out.append(mk("return [x for x in a[0]]", "wrap"))
        if kind == "attribute":
            meth = _re.search(r"'\w+' object has no attribute '(\w+)'", w)
            if meth:
                for alt in ("strip()", "split()", "lower()", "upper()", "copy()",
                            "keys()", "values()", "items()"):
                    if alt.split("(")[0] != meth.group(1):
                        out.append(mk("return a[0].%s" % alt,
                                      "attr_" + alt.split("(")[0]))
        if kind == "operand":
            out.append(mk("return len(list(a[0]))", "as_len"))
            out.append(mk("return str(a[0])", "as_str"))
        if kind in ("degenerate", "bad_value", "missing_key"):
            out.append(mk("return None if not a[0] else a[0]", "guard_empty"))
        if kind == "name":
            # A rename is always cheap to try when the failure was about the name
            # rather than the work.
            try:
                from .local_solver import _requested
                for nm in (_requested(check).get("names") or {}):
                    if nm != target and nm not in ("assert", "print"):
                        out.append({"code": code.replace("def " + target, "def " + nm),
                                    "label": "step2:rename_%s" % nm, "score": 0.3,
                                    "task": cand.get("task") or "",
                                    "_because": said, "_from": cand.get("label")})
            except Exception:
                pass
        return out[:6]

    def _attempt(self, cand: dict, check: str) -> tuple:
        """Execute the candidate AND its check, together.

        `_verify_detail(code, task)` runs `code` alone -- the check has to be appended
        by the caller, which is what repair_against and compose_against both do. This
        did not, so every attempt ran a bare function definition: exit zero, nothing
        called, and the loop was ranking and teaching on a verdict that had never
        touched the task. The gate is the task's own assertions, so they go in.
        """
        code = str(cand.get("code") or "")
        if not code.strip():
            return False, "no code"
        try:
            ok, kind = self.solver._verify_detail(
                code + "\n\n" + str(check), check)
            return bool(ok), None if ok else (
                (self.solver._last_verify_error or "")[-120:])
        except Exception as e:
            return False, f"{type(e).__name__}: {str(e)[:80]}"

    def _finish(self, task, cand, rec, extra: dict) -> dict:
        return {"task": str(task)[:80], "candidate": (cand or {}).get("label"),
                "attempt": rec, **extra, "episodes": self.episodes,
                "attempts_total": self.attempts, "solved_total": self.solved}

    # ---------------------------------------------------------------- diagnosis
    def diagnose(self, task: str, check: str, max_test: int = 40) -> dict:
        """Which stage failed: generation, or ranking?

        A refused task has two completely different causes and they need opposite
        fixes. Either no candidate that passes was ever produced -- generation is the
        bottleneck, and the answer is more forms of candidate -- or one was produced
        and the loop did not try it, in which case generation is fine and the ranking
        is what is broken.

        So this tests EVERY candidate against the task's own assertions, not just the
        ones the loop chose, and reports whether a passing one existed and where it
        sat in the order. Same gate, applied exhaustively rather than selectively.
        """
        cands, comp = self._candidates(task, check)
        goal_vec = self._goal_vector()
        # Rank exactly as step() does, or the diagnosis measures a different loop.
        # The first version compared the passing candidates against GENERATION order
        # and reported five tasks as "a passing candidate would have been tried" that
        # step() had in fact refused -- an instrument disagreeing with the thing it
        # instruments, which is worse than no instrument.
        head = None
        if self.language is not None and getattr(self.language, "cortex", None):
            head = getattr(self.language.cortex, "outcome", None)
        ranked = []
        for c in cands:
            s, a, g = self._vectors(task, c, goal_vec)
            p = head.predict(s, a, g) if (head is not None and s is not None) else 0.5
            c["_pred"] = round(float(p), 4)
            c["_rank"] = 0.5 * float(p) + 0.5 * float(c.get("score") or 0)
            ranked.append(c)
        ranked.sort(key=lambda c: -c["_rank"])
        passing = []
        for i, c in enumerate(ranked[:max_test]):
            ok, why = self._attempt(c, check)
            if ok:
                passing.append({"rank": i, "label": c["label"],
                                "score": round(float(c.get("score") or 0), 4)})
        tried_labels = [c["label"] for c in ranked[:self.budget]]
        return {"candidates": len(cands), "tested": min(len(ranked), max_test),
                "passing": passing,
                "would_have_been_tried": any(p["label"] in tried_labels
                                             for p in passing),
                "stage": ("generation" if not passing else
                          ("ranking" if not any(p["label"] in tried_labels
                                                for p in passing)
                           else "none: it passed")),
                "compose": (comp or {}).get("reason") or (comp or {}).get("method"),
                "goal_vec": goal_vec is not None}

    # ---------------------------------------------------------------- reporting
    def stats(self) -> dict:
        head = None
        if self.language is not None and getattr(self.language, "cortex", None):
            head = getattr(self.language.cortex, "outcome", None)
        return {"episodes": self.episodes, "attempts": self.attempts,
                "solved": self.solved,
                "solve_rate": round(self.solved / max(1, self.episodes), 3),
                "outcome_head": head.stats() if head is not None else None,
                "candidates_tried": len(self.tried),
                "engine_wired": self.engine is not None,
                "recent": self.trace[-6:]}
