"""The number behind the 90/10 claim: what does he actually do with a real task?

Everything measured so far about coding has been about the machinery -- retrieval
rates, how many procedures carry evidence, whether a trial promotes. None of it
answers the question the goal is stated in, which is: given a task he has not seen,
does he solve it locally, or does he need the model?

This runs a battery of ordinary small coding tasks through the router and reports
the route each one took and whether the result survived its own check. Each task
carries a check -- assertions that run against the produced code -- so verification
here means "it solves the task", which is the evidence kind worth 0.35 and the only
one that should ever make a procedure trusted. "It exited zero" is not that; a
function definition exits zero without being called.

The battery is deliberately split. `own` tasks are things his library plausibly
holds, because they are his own functions described in other words. `novel` tasks
are ordinary programming he has no reason to have seen. The honest expectation is
that he does well on the first and badly on the second, and the ratio between them
is the actual state of goal B -- not the 90% in the brief.

There is no API key in this configuration, so the oracle rung fails rather than
answering. That is the right condition to measure under: it shows what the local
path does on its own, with nothing to fall back on.

Usage:
    python tools/task_battery.py
    python tools/task_battery.py --only novel
    python tools/task_battery.py --heldout --no-learn   # first-contact set
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Each check runs after the solution, in the same file, and must raise to fail.
BATTERY = [
    # ---- things his own library plausibly holds -----------------------------
    {"group": "own",
     # Same spec/check fix the signature task got: the text is the spec the
     # oracle sees, and it used to under-describe its own check. "fold plural
     # and verbal suffixes" never named the interface, so the oracle answered
     # with a text-level regex rewriter (fold_suffixes(text)) -- a plausible
     # reading of the words and wrong for the check, which calls stem(word)
     # per word. Measured 2026-07-29: repair renamed it and it still failed
     # on substance (places -> plac, class -> clas). The text now names the
     # function, its argument, and the identity case the check enforces.
     # After the reword the oracle answers with a real stem(word) function --
     # the interface fix held -- but its rule is a naive suffix stripper
     # (es before s, no ss guard), the exact defect this library's own stem
     # docstring documents as fixed; every variant fails at least one
     # assertion. The check is not over-strict: the library's stem passes all
     # three. The task still fails locally because recall ranks the stem
     # procedure first (0.264) yet below the fuzzy floors (0.5 / 0.3+0.15).
     "task": "write a stem(word) function returning the word's stem, "
             "inflection-invariant: plural and verbal suffixes fold so "
             "related words match (holding/holds, places/place), and a word "
             "with no suffix to fold is returned unchanged",
     "check": "assert stem('holding') == stem('holds')\n"
              "assert stem('places') == stem('place')\n"
              "assert stem('class') == 'class'\n"},
    {"group": "own",
     # The task text is the spec the oracle sees; the check is the spec the
     # sandbox enforces. They used to disagree: the text said only "stable",
     # while the check demanded phrasing-invariance, so a correct-by-its-text
     # answer (sha256 of the normalized string) still failed the assertions.
     # Measured 2026-07-29: oracle returned exactly that hash, check failed.
     # A second ask with "phrased differently" stated still failed: it sorted
     # raw tokens, so "sorted" and "sort" hashed apart. The text now describes
     # the function his library actually holds -- stems, sorted -- because a
     # spec that under-describes its own check teaches the wrong procedure.
     "task": "compute a stable signature key from a task description: the "
             "salient word stems, sorted, so the same request phrased "
             "differently (word order, plurals, sort/sorted) gives the same "
             "key",
     # THE SPEC/CHECK MISMATCH. The check used to call signature(...) while
     # the solution's namespace defined signature_key(...) -- measured:
     # NameError: name 'signature' is not defined. Did you mean:
     # 'signature_key'? -- so the task failed on a NAME, not on the answer.
     # The task asks for a stable key function; which name he gave it is
     # incidental, so the check binds whichever of the two exists.
     "check": "f = globals().get('signature_key') or globals().get('signature')\n"
              "assert f is not None, 'no signature function defined'\n"
              "assert f('sort the rows by key') == f('rows sorted by a key')\n"},
    {"group": "own",
     "task": "match a task to the best procedure above a success floor",
     "check": "assert match is not None\n"},
    # ---- ordinary programming he has no reason to have seen -----------------
    {"group": "novel",
     "task": "write a function fib(n) returning the nth fibonacci number",
     "check": "assert [fib(i) for i in range(8)] == [0, 1, 1, 2, 3, 5, 8, 13]\n"},
    {"group": "novel",
     "task": "write a function reverse(s) that reverses a string",
     "check": "assert reverse('droso') == 'osord'\n"
              "assert reverse('') == ''\n"},
    {"group": "novel",
     "task": "write a function word_counts(text) returning a dict of word "
             "frequencies, lowercased",
     "check": "assert word_counts('the day the night') == "
              "{'the': 2, 'day': 1, 'night': 1}\n"},
    {"group": "novel",
     "task": "write a function flatten(nested) that flattens one level of "
             "nesting",
     "check": "assert flatten([[1, 2], [3], [4, 5]]) == [1, 2, 3, 4, 5]\n"},
    {"group": "novel",
     "task": "write a function is_palindrome(s) ignoring case and spaces",
     "check": "assert is_palindrome('Never odd or even')\n"
              "assert not is_palindrome('droso')\n"},
    {"group": "novel",
     "task": "write a function chunk(items, n) splitting a list into groups of n",
     "check": "assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]\n"},
    {"group": "novel",
     "task": "write a function safe_div(a, b) returning None when b is zero",
     "check": "assert safe_div(6, 3) == 2\nassert safe_div(1, 0) is None\n"},
    {"group": "novel",
     "task": "write a function read_json_lines(path) parsing one json object "
             "per line",
     "check": "import tempfile, os, json as _j\n"
              "p = os.path.join(tempfile.mkdtemp(), 'x.jsonl')\n"
              "open(p, 'w').write('{\"a\": 1}\\n{\"a\": 2}\\n')\n"
              "assert read_json_lines(p) == [{'a': 1}, {'a': 2}]\n"},
    {"group": "novel",
     "task": "write a function dedupe(items) preserving first-seen order",
     "check": "assert dedupe([3, 1, 3, 2, 1]) == [3, 1, 2]\n"},
]

# First-contact set, built 2026-10-25. The `novel` group above has been in the
# battery for 30 days and every one of its tasks is now a verified library
# member, so 9/9 replay measures retrieval, not first contact. These ten were
# checked against the live library (state/house_agent_learning.json, 680
# procedures) before being called novel: count_vowels, second_largest,
# slugify, intersperse, flatten_deep, rot13, levenshtein, pig_latin,
# running_total have zero mentions; most_common appears only as an incidental
# Counter call inside two unrelated solutions. decimal_to_binary, roman,
# snake_to_camel and hamming_distance were considered and REJECTED -- the
# library already holds them. Run with --heldout --no-learn: the store must
# stay read-only, because the point is what he does on first contact, not
# what he banks from it.
HELDOUT = [
    {"group": "novel",
     "task": "write a function count_vowels(s) counting the vowels a, e, i, "
             "o, u in a string, case-insensitively",
     "check": "assert count_vowels('droso') == 2\n"
              "assert count_vowels('xyz') == 0\n"
              "assert count_vowels('AeIoU') == 5\n"},
    {"group": "novel",
     "task": "write a function second_largest(items) returning the second "
             "largest DISTINCT value in a list, or None if there are fewer "
             "than two distinct values",
     "check": "assert second_largest([3, 1, 4, 1, 5]) == 4\n"
              "assert second_largest([7]) is None\n"
              "assert second_largest([5, 5, 5]) is None\n"},
    {"group": "novel",
     "task": "write a function slugify(text) returning a lowercase slug: "
             "every run of characters that are not letters or digits becomes "
             "a single hyphen, with no leading or trailing hyphen",
     "check": "assert slugify('Hello, World!') == 'hello-world'\n"
              "assert slugify('already-clean') == 'already-clean'\n"
              "assert slugify('A  B') == 'a-b'\n"},
    {"group": "novel",
     "task": "write a function intersperse(items, sep) returning a new list "
             "with sep inserted between every pair of consecutive elements",
     "check": "assert intersperse([1, 2, 3], '-') == [1, '-', 2, '-', 3]\n"
              "assert intersperse([1], '-') == [1]\n"
              "assert intersperse([], '-') == []\n"},
    {"group": "novel",
     "task": "write a function most_common(items) returning the most "
             "frequent item; if several tie, return the one whose first "
             "occurrence comes first",
     "check": "assert most_common([1, 2, 2, 3, 3]) == 2\n"
              "assert most_common(['a', 'b', 'b']) == 'b'\n"},
    {"group": "novel",
     "task": "write a function flatten_deep(nested) flattening a list "
             "arbitrarily deeply nested into one flat list, in order",
     "check": "assert flatten_deep([1, [2, [3, [4]]], 5]) == [1, 2, 3, 4, 5]\n"
              "assert flatten_deep([]) == []\n"},
    {"group": "novel",
     "task": "write a function rot13(s) applying the ROT13 cipher: each "
             "letter is replaced by the letter 13 later in the alphabet "
             "wrapping around, preserving case, leaving every other "
             "character unchanged",
     "check": "assert rot13('hello') == 'uryyb'\n"
              "assert rot13('uryyb') == 'hello'\n"
              "assert rot13('Hello, World!') == 'Uryyb, Jbeyq!'\n"},
    {"group": "novel",
     "task": "write a function levenshtein(a, b) returning the edit distance "
             "between two strings: the minimum number of single-character "
             "insertions, deletions or substitutions to turn a into b",
     "check": "assert levenshtein('kitten', 'sitting') == 3\n"
              "assert levenshtein('', 'abc') == 3\n"
              "assert levenshtein('same', 'same') == 0\n"},
    {"group": "novel",
     "task": "write a function pig_latin(word) moving an initial consonant "
             "cluster to the end and adding 'ay', or adding 'way' if the "
             "word already starts with a vowel",
     "check": "assert pig_latin('hello') == 'ellohay'\n"
              "assert pig_latin('apple') == 'appleway'\n"
              "assert pig_latin('smile') == 'ilesmay'\n"},
    {"group": "novel",
     "task": "write a function running_total(items) returning the cumulative "
             "sums of a list of numbers, as a list of the same length",
     "check": "assert running_total([1, 2, 3]) == [1, 3, 6]\n"
              "assert running_total([]) == []\n"
              "assert running_total([5]) == [5]\n"},
]


def _extract_code(text: str) -> str:
    """Code out of a model reply, fenced or bare."""
    s = str(text or "")
    if "```" in s:
        parts = s.split("```")
        for i in range(1, len(parts), 2):
            body = parts[i]
            nl = body.find("\n")
            if nl >= 0 and body[:nl].strip().lower() in (
                    "python", "py", "python3", "", "bash", "sh"):
                body = body[nl + 1:]
            if body.strip():
                return body.strip()
    return s.strip()


def _ask_oracle(oracle, task: str, check: str, sb) -> dict:
    """The rung that produces novel code. Its output is verified like anything else.

    Nothing here is trusted because a model wrote it. The model supplies a candidate
    and the sandbox decides, which is the whole reason the evidence taxonomy exists:
    a model that writes code that passes its own task's assertions has produced a
    task_check, worth 0.35, the same as a passing test -- and a model that writes
    code that fails produces nothing at all.
    """
    prompt = ("Write Python code that solves this task. Reply with the code only, "
              "no explanation.\n\nTask: " + str(task))
    try:
        # no_reasoning=True is not cosmetic here. Measured on ollama_cloud's
        # deepseek-v4.1-flash at max_tokens=320: thinking={"type":"disabled"} is
        # accepted and IGNORED (finish=length, content=0) while
        # reasoning_effort="none" returns finish=stop with content. Without it
        # the hidden trace ate the whole budget and every oracle rung read as
        # thinking_ate_the_budget -- the baseline's own-task failure.
        r = oracle.query(prompt, max_tokens=400, temperature=0.0,
                         purpose="task_battery", no_reasoning=True)
    except Exception as e:
        return {"ok": False, "reason": f"{type(e).__name__}: {str(e)[:90]}",
                "mode": "error"}
    if not r.get("ok"):
        return {"ok": False, "mode": r.get("mode"),
                "reason": str(r.get("reason") or r.get("mode") or "no answer")[:110]}
    code = _extract_code(r.get("text") or "")
    chk = _check(sb, code, check)
    return {"ok": chk["passed"], "code": code, "mode": r.get("mode"),
            "tokens": r.get("tokens"), "reason": chk["reason"]}


def _build(use_library: bool, learn: bool = True):
    from organs.local_solver import LocalSolver
    from organs.learning_loop import LearningLoop
    from organs.language_verifier import LanguageVerifier
    from organs.fast_router import FastRouter
    from organs.sandbox import Sandbox

    # The store the live agent actually reads. LearningLoop's default path is
    # exocortex/learned_procedures.json, which is the seeder's output, not the
    # house's -- so the first version of this battery measured a stale library of
    # 277 at 0.35 and reported that the animal could barely recall his own code.
    agent_state = ROOT / "state" / "house_agent_learning.json"
    # read_only seals the writers the learn flag alone does not reach: the
    # router's recall branch reinforces and aliases on its own account, and a
    # --no-learn regression run wrote 12 reinforces through it (measured
    # 2026-10-25). With the seal, learn=False means zero writes anywhere, and
    # the store-count guard below still verifies it end to end.
    learning = LearningLoop(state_path=agent_state,
                            events_path=ROOT / "state"
                            / "house_agent_learning_events.jsonl",
                            persist=True, read_only=not learn) \
        if use_library else None
    zone = ROOT / "house_workspace"
    zone.mkdir(exist_ok=True)
    sb = Sandbox(project_root=str(ROOT), workzone=str(zone),
                 auto_approve_writes=True)
    solver = LocalSolver(verifier=LanguageVerifier(), learning=learning,
                         sandbox=sb, min_confidence=0.7, trial_floor=0.35)
    router = FastRouter(local_solver=solver, reasoning_agent=None,
                        replay_confidence=0.9)
    return router, solver, learning, sb


def _check(sb, solution: str, check: str) -> dict:
    """Run the solution and its check together. Raising is failing."""
    if not str(solution or "").strip():
        return {"ran": False, "passed": False, "reason": "no code produced"}
    name = "_battery_%d.py" % (int(time.time() * 1000) % 10 ** 8)
    try:
        r = sb.run_python(str(solution) + "\n\n" + check, timeout=25, name=name)
    except Exception as e:
        return {"ran": False, "passed": False, "reason": str(e)[:120]}
    ok = bool(r.get("success", r.get("ok", False))) and \
        int(r.get("returncode", r.get("exit_code", 0)) or 0) == 0
    err = str(r.get("stderr") or r.get("output") or "")[-240:]
    return {"ran": True, "passed": ok,
            "reason": None if ok else err.strip()[-160:] or "nonzero exit"}


def run(only: str | None = None, learn: bool = True,
        use_oracle: bool = True, provider: str = "ollama",
        tasks: list | None = None) -> dict:
    if tasks is HELDOUT and learn:
        # Second layer behind main()'s implication: a programmatic caller that
        # hands the first-contact set to a learning run is misusing the
        # instrument, and the run must refuse rather than bank the answers.
        raise ValueError(
            "run(tasks=HELDOUT) with learn=True would bank the first-contact "
            "solutions and turn the set into replay; pass learn=False")
    router, solver, learning, sb = _build(True, learn)
    # Third layer of the no-learn guard. The CLI implication and the run()
    # signature refuse misuse before the loop starts, but neither watches the
    # store itself: a learn=False run that ends with a different library than
    # it started with is a broken instrument no matter which line leaked, so
    # the count is captured here and verified after the loop. getattr, because
    # unit tests stub the organs and a stub without a store cannot be watched
    # -- absence is skipped, not faked.
    store_count = None
    if not learn and learning is not None:
        store = getattr(learning, "store", None)
        if isinstance(store, dict):
            store_count = len(store)
    try:
        from tools import _experience
    except Exception:                                          # pragma: no cover
        _experience = None
    # Every sandbox run in this tool reports itself as an act, through the sandbox's
    # own hook so there is one record per execution rather than two.
    if _experience is not None:
        sb.on_run = lambda name, ok: _experience.ran(str(name), bool(ok))
    oracle = None
    oracle_mode = "disabled"
    if use_oracle:
        try:
            # The same construction path the house uses, so the key comes from the
            # user-profile credential store rather than the environment, and the
            # provider/base/model all come from one place. A battery that built its
            # own APIOracle would read a different key resolution than the being it
            # is measuring.
            import json as _json
            from pathlib import Path as _Path
            from organs.api_oracle import oracle_from_config
            _cfg = _json.loads((ROOT / "config" / "hybrid_config.json")
                               .read_text(encoding="utf-8"))
            o = oracle_from_config(_cfg, provider=provider or None)
            oracle_mode = o.mode
            oracle = o if o.has_key else None
        except Exception as e:
            oracle_mode = f"error: {type(e).__name__}"
    rows = []
    routes: dict = {}
    for item in (tasks if tasks is not None else BATTERY):
        if only and item["group"] != only:
            continue
        t0 = time.time()
        if _experience is not None:
            _experience.tries(item["task"])
        try:
            out = router.run(item["task"])
        except Exception as e:
            out = {"solution": "", "route_path": "error", "error": str(e)[:120]}
        route = str(out.get("route_path") or "?")
        routes[route] = routes.get(route, 0) + 1
        # The rung that produced the pass: "router" covers the router and its
        # repair rung, "compose" and "grammar" the two local rungs below, and
        # "oracle" the model. The route stays what the router chose; the rung
        # is where the pass actually came from.
        rung = "router"
        sol = str(out.get("solution") or "")
        chk = _check(sb, sol, item["check"])
        repaired = None
        if not chk["passed"] and sol.strip():
            # A recalled function is not a solution to a task: it carries its own
            # name, while the task asks for a particular one. Let the failure say
            # what to change -- NameError('fib') means the artifact defines the
            # right thing under the wrong name, and renaming it is mechanical.
            rp = solver.repair_against(sol, item["check"])
            if rp.get("ok"):
                sol = rp["code"]
                chk = _check(sb, sol, item["check"])
                repaired = rp.get("renames")
            elif rp.get("renames"):
                repaired = rp.get("renames")
        # Rung A -- composition, called directly. curriculum_run.py gives the
        # held-out slice this same rung (its 1b) because it is the one supposed
        # to generalise; the battery's silence on it was the 0/10. budget=8
        # matches the diagnose run that measured that 0/10, so the number stays
        # comparable. compose_against only verifies candidates without
        # persisting them, and the battery's own gate re-verifies anyway.
        compose_info = None
        if not chk["passed"]:
            try:
                comp = solver.compose_against(item["task"], item["check"],
                                              budget=8) or {}
            except Exception as e:
                comp = {"ok": False,
                        "reason": f"{type(e).__name__}: {str(e)[:80]}"}
            compose_info = {"tried": comp.get("tried"),
                            "reason": str(comp.get("reason") or "")[:140]}
            if comp.get("ok") and str(comp.get("code") or "").strip():
                c2 = _check(sb, comp["code"], item["check"])
                compose_info["battery_gate"] = c2["passed"]
                if c2["passed"]:
                    sol, chk, rung = comp["code"], c2, "compose"
        # Rung B -- the reasoning loop's grammar: the machinery that can
        # generate two-arg programs (prog:), chain a follow-on step from a
        # failure (step2:), and rank library, fact, hint, primitive and
        # composed candidates against each other. learn=False gates the only
        # store write inside step(), and the store-count guard below watches
        # the result either way. A fresh loop per task: `tried` and `trace`
        # are per-episode state, and the trace is what the row reports.
        grammar_info = None
        if not chk["passed"]:
            from organs.reasoning_loop import ReasoningLoop
            agent = ReasoningLoop(solver=solver, learning=learning,
                                  sandbox=sb)
            try:
                res = agent.step(item["task"], item["check"], learn=False)
            except Exception as e:
                res = {"outcome": "error",
                       "reason": f"{type(e).__name__}: {str(e)[:80]}"}
            grammar_info = {
                "outcome": res.get("outcome"),
                "reason": str(res.get("reason") or "")[:140],
                "candidate": res.get("candidate"),
                "candidates": res.get("candidates"),
                "attempts": res.get("attempts"),
                "best_pred": res.get("best_pred"),
                "steps": [{"label": t.get("label"), "passed": t.get("passed"),
                           "why": t.get("why")} for t in agent.trace]}
            if res.get("outcome") == "solved":
                # step() verified the winner against the task's own assertions
                # (solver._verify_detail appends the check), but it returns the
                # label and not the code. The candidate list is deterministic
                # given task, check and library, so the code is recovered by
                # re-deriving it and matching the label -- then the battery's
                # own gate decides, the same as every other rung.
                code = None
                try:
                    for c in agent._candidates(item["task"], item["check"])[0]:
                        if c.get("label") == res.get("candidate"):
                            code = c.get("code")
                            break
                except Exception:
                    code = None
                if code:
                    c3 = _check(sb, code, item["check"])
                    grammar_info["battery_gate"] = c3["passed"]
                    if c3["passed"]:
                        sol, chk, rung = code, c3, "grammar"
                else:
                    grammar_info["code_recovered"] = False
        # The 10%: only when the local rungs have declined. Its output is verified
        # by the task's own assertions, and stored only if it passes them.
        oracle_calls = 0
        oracle_used = False
        oracle_repaired = None
        if not chk["passed"] and oracle is not None:
            o = _ask_oracle(oracle, item["task"], item["check"], sb)
            oracle_calls = 1
            if o.get("ok"):
                sol = o["code"]
                chk = _check(sb, sol, item["check"])
                oracle_used = True
                if chk["passed"]:
                    rung = "oracle"
            elif o.get("code"):
                # The same rung the local solution gets. A correctly-shaped
                # oracle answer can still die on a name -- the check calls
                # stem(...) while the model defined stem_word(...) -- and
                # without this branch that was recorded as the oracle being
                # wrong when only its name was. Measured 2026-07-29: the stem
                # task's oracle answer failed exactly that way and was never
                # offered to repair_against.
                rp = solver.repair_against(o["code"], item["check"])
                oracle_repaired = rp.get("renames")
                if rp.get("ok"):
                    sol = rp["code"]
                    chk = _check(sb, sol, item["check"])
                    oracle_used = True
                    if chk["passed"]:
                        rung = "oracle"
                else:
                    # The repair's reason beats the oracle's: after the
                    # mechanical rename it says what still fails, which is
                    # the substance of the answer, not its name.
                    chk = {"ran": chk["ran"], "passed": False,
                           "reason": str(rp.get("reason")
                                         or o.get("reason"))[:160]}
            else:
                chk = {"ran": chk["ran"], "passed": False,
                       "reason": str(o.get("reason"))[:160]}
        if learn and chk["ran"] and learning is not None and sol.strip():
            # A check that ran is the strongest evidence there is: not "it parsed",
            # not "it exited zero", but "it did the task".
            try:
                learning.learn_from_task(
                    item["task"], sol,
                    {"source": route, "verified": chk["passed"],
                     "language": "python", "verifier_kind": "task_check"},
                    verified=chk["passed"])
            except Exception:
                pass
        rows.append({"group": item["group"], "task": item["task"][:56],
                     "route": route, "method": out.get("method"),
                     "solution_chars": len(sol),
                     "checked": chk["ran"], "passed": chk["passed"],
                     "rung": rung, "compose": compose_info,
                     "grammar": grammar_info,
                     "repaired": repaired, "oracle_repaired": oracle_repaired,
                     "from_oracle": oracle_used,
                     "reason": chk["reason"],
                     "oracle_calls": oracle_calls,
                     "ms": round((time.time() - t0) * 1000, 1)})
        if _experience is not None:
            _experience.outcome(item["task"], bool(chk["passed"]))
    # The no-learn guard's third layer, verified: the count captured before the
    # loop must be the count after it. A stub without a store was never watched
    # (store_count is None), which is reported by absence, not faked.
    if store_count is not None:
        now = getattr(learning, "store", None)
        now = len(now) if isinstance(now, dict) else None
        if now != store_count:
            raise RuntimeError(
                "a learn=False run changed the live library "
                f"({store_count} -> {now} procedures): the no-learn guard "
                "leaked and the instrument is not honest")
    by_group = {}
    for g in ("own", "novel"):
        sub = [r for r in rows if r["group"] == g]
        if sub:
            by_group[g] = {"tasks": len(sub),
                           "passed": sum(1 for r in sub if r["passed"]),
                           "needed_repair_to_pass": sum(
                               1 for r in sub if r["passed"] and r["repaired"]),
                           "produced_code": sum(1 for r in sub
                                                if r["solution_chars"]),
                           "local_only": sum(1 for r in sub
                                             if r["oracle_calls"] == 0)}
    # Per-rung accounting: which machinery produced each pass. This is the
    # number the held-out report is for -- the 0/10 was a rung the battery
    # never fired, and without this field the next report could repeat it.
    by_rung = {}
    for r in rows:
        if r["passed"]:
            by_rung[r["rung"]] = by_rung.get(r["rung"], 0) + 1
    return {"tasks": len(rows), "routes": routes, "by_group": by_group,
            "by_rung": by_rung,
            "oracle_provider": provider, "oracle_mode": oracle_mode,
            "passed": sum(1 for r in rows if r["passed"]),
            "solved_locally": sum(1 for r in rows if r["passed"]
                                  and not r["from_oracle"]),
            "solved_by_oracle": sum(1 for r in rows if r["from_oracle"]),
            "needed_oracle": sum(1 for r in rows if r["oracle_calls"] > 0),
            "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["own", "novel"], default=None)
    ap.add_argument("--no-learn", action="store_true")
    ap.add_argument("--no-oracle", action="store_true",
                    help="measure the local path alone")
    ap.add_argument("--heldout", action="store_true",
                    help="run the first-contact set (HELDOUT) instead of the "
                         "30-day-old battery; pair with --no-learn")
    ap.add_argument("--provider", default=None,
                    help="override the configured provider; default is whatever "
                         "config/hybrid_config.json names")
    a = ap.parse_args()
    if a.heldout and not a.no_learn:
        # The held-out set is only a first-contact measure while it stays
        # unseen. Learning from it would bank the solutions and turn the next
        # run into replay -- exactly how the 30-day-old novel group decayed.
        print("--heldout implies --no-learn: the first-contact set is not "
              "for banking.", file=sys.stderr)
        a.no_learn = True
    out = run(a.only, not a.no_learn, not a.no_oracle, a.provider,
              tasks=HELDOUT if a.heldout else None)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
