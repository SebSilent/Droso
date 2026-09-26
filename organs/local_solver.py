from __future__ import annotations

import ast
import re

def _words(s: str, min_len: int = 4) -> set:
    """Words of at least `min_len` characters *in total*.

    The obvious `r"[a-z_][a-z_0-9]{min_len,}"` is off by one: the leading class
    already supplies one character, so with min_len=4 it silently demanded 5 and
    dropped "sort", "rows" and "dict" -- which is every word a code task tends
    to contain. Pattern recall returned nothing and looked like a miss.
    """
    n = max(1, int(min_len) - 1)
    return set(re.findall(r"[a-z_][a-z_0-9]{%d,}" % n, str(s or "").lower()))

def _defines_only(code: str) -> bool:
    """True when running this code could only ever have proved that it parses.

    A module of function definitions and imports exits zero without executing a
    single line of its own. Treating that as verification is how a memory system
    learns to lie: composition concatenates up to four remembered blocks, the
    artifact defines four unrelated functions, the sandbox reports success, and a
    paste is handed back as a solution with a confidence attached. Fixing the
    verifier made this reachable -- before, every verification returned False and
    composition declined for the wrong reason.
    """
    try:
        tree = ast.parse(str(code or ""))
    except (SyntaxError, ValueError):
        return False
    if not tree.body:
        return False
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                             ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            continue                      # a module docstring
        # Anything else at top level -- an assignment, a call, an assert -- is the
        # module doing something rather than describing something, and doing
        # something is what a clean exit code can speak about. The first version of
        # this allowed Assign and Expr, so "rows = sorted(prep())" counted as
        # definitional and a composition that really ran was refused.
        return False
    return True


class Recalled:
    """A remembered procedure, shaped the way the fast router wants it.

    `replay()` hands back the stored artifact. It does not re-run anything: a
    replayed procedure is a *citation* of something that was verified when it
    was learned, and the freshness of that claim is exactly what
    `verified_now` is for.
    """

    __slots__ = ("confidence", "signature", "solution", "verified",
                 "method", "language", "api_calls", "tokens", "trusted")

    def __init__(self, hit: dict):
        self.confidence = float(hit.get("confidence", 0.0) or 0.0)
        # The store's own signature when it has one; provenance is a display
        # string and is no good for crediting the record that actually ran.
        self.signature = str(hit.get("signature")
                             or hit.get("provenance", ""))[:64]
        self.solution = hit.get("solution", "")
        self.verified = bool(hit.get("verified"))
        self.trusted = bool(hit.get("trusted"))
        self.method = hit.get("method", "procedure")
        self.language = hit.get("language", "python")
        self.api_calls = 0
        self.tokens = 0

    def replay(self, require_verified: bool = True) -> dict | None:
        if require_verified and not self.verified:
            return None
        return {"solution": self.solution, "method": "procedure_replay",
                "confidence": round(self.confidence, 3),
                "verified": self.verified, "replayed": True,
                "trusted": self.trusted, "signature": self.signature,
                "provenance": self.signature, "api_calls": 0, "tokens": 0,
                "language": self.language}

    def __repr__(self):
        return (f"<Recalled {self.signature!r} conf={self.confidence:.2f} "
                f"verified={self.verified}>")

def _single_function_name(code: str) -> str | None:
    """The name of the only top-level function, or None if it is not that simple."""
    try:
        tree = ast.parse(str(code or ""))
    except (SyntaxError, ValueError):
        return None
    fns = [n for n in tree.body
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return fns[0].name if len(fns) == 1 else None


def _rename_function(code: str, new_name: str) -> str:
    """Rename the single top-level function, and its own recursion with it."""
    try:
        tree = ast.parse(str(code or ""))
    except (SyntaxError, ValueError):
        return code
    fns = [n for n in tree.body
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(fns) != 1:
        return code
    old = fns[0].name
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == old:
            node.id = new_name
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == old:
            node.func.id = new_name
    fns[0].name = new_name
    try:
        return ast.unparse(tree)
    except Exception:
        return code


_MISSING = re.compile(r"NameError: name '([^']+)' is not defined")


def _functions_in(code: str) -> list:
    """Every top-level def in a snippet: (name, arg_count, source).

    `self` and `cls` are dropped, because a stored method extracted from a class is
    still one more argument than the check will ever pass.
    """
    try:
        tree = ast.parse(str(code or ""))
    except (SyntaxError, ValueError):
        return []
    out = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = [a.arg for a in getattr(node.args, "args", [])
                if a.arg not in ("self", "cls")]
        try:
            src = ast.get_source_segment(str(code), node) or ""
        except Exception:
            src = ""
        out.append({"name": node.name, "arity": len(args), "src": src,
                    "varargs": bool(getattr(node.args, "vararg", None))})
    return out


def _imports_in(code: str) -> str:
    """Top-level import statements, so a candidate keeps its own dependencies."""
    try:
        tree = ast.parse(str(code or ""))
    except (SyntaxError, ValueError):
        return ""
    lines = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            try:
                lines.append(ast.get_source_segment(str(code), node) or "")
            except Exception:
                pass
    return "\n".join(l for l in lines if l.strip())


def _requested(check: str) -> dict:
    """The interface the tests want: which names they call, and with how many args.

    This is read off the assertions rather than guessed, and it is the only source of
    truth about what a composition has to look like. A name called with two arguments
    cannot be satisfied by a one-argument function, whatever it computes.
    """
    try:
        tree = ast.parse(str(check or ""))
    except (SyntaxError, ValueError):
        return {"names": {}, "imports": []}
    names: dict = {}
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            n = node.func.id
            arity = len([a for a in node.args])
            prev = names.get(n)
            if prev is None or arity > prev:
                names[n] = arity
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            try:
                imports.append(ast.get_source_segment(str(check), node) or "")
            except Exception:
                pass
    return {"names": names, "imports": [i for i in imports if i.strip()]}


class LocalSolver:
    def __init__(self, procedure_store=None, pattern_library=None,
                 verifier=None, exocortex=None, assembler=None,
                 filesystem=None, memory=None, min_confidence: float = 0.7,
                 writer=None, learning=None, trial_floor: float = 0.35,
                 sandbox=None, verify_timeout: float = 15.0):
        self.procedures = procedure_store if procedure_store is not None else \
            (getattr(memory, "procedural", None) if memory else None)
        self.patterns = pattern_library if pattern_library is not None else \
            (getattr(memory, "semantic", None) if memory else None)
        self.verifier = verifier
        self.exo = exocortex
        self.assembler = assembler
        self.writer = writer
        self.filesystem = filesystem
        self.learning = learning
        self.sandbox = sandbox
        self.verify_timeout = float(verify_timeout)
        self._last_verify_error = ""
        # Attached by the reasoning loop from the language cortex's binder. Left None by
        # default so a LocalSolver built in isolation reports a miss rather than pretending
        # it looked somewhere.
        self.fact_store = None
        self.min_confidence = float(min_confidence)
        # Below min_confidence a procedure is not trusted, but it is still worth
        # trying -- because trying means running it, and running it is what
        # produces the evidence that moves its confidence. A floor that demanded
        # trust before use made the library unusable forever: nothing could be
        # replayed until it was trusted, and nothing could be trusted until it was
        # replayed.
        self.trial_floor = float(trial_floor)
        self.attempts = 0
        self.solved = 0
        self.refusals = 0
        self.by_method: dict[str, int] = {}

    def solve(self, task: str, context: str = "", language: str | None = None,
              require_verified: bool = False) -> dict | None:
        """Return {solution, method, confidence, provenance, verified} or None.

        `require_verified=True` makes a solution that nothing checked count as
        no solution -- the right setting when the caller would otherwise ship
        unverified code to the world.
        """
        self.attempts += 1
        probes = []
        for name, fn in (("procedure", self._from_procedure),
                         ("pattern", self._from_pattern),
                         ("atlas", self._from_atlas)):
            try:
                hit = fn(task)
            except Exception as exc:
                hit = None
                probes.append(f"{name}:error:{type(exc).__name__}")
            if hit:
                hit["provenance"] = probes + [hit["provenance"]]
                if require_verified and not hit["verified"]:
                    break
                self.solved += 1
                self.by_method[name] = self.by_method.get(name, 0) + 1
                return hit
            probes.append(f"{name}:miss")
        self.refusals += 1
        return None

    def _from_procedure(self, task: str, trial: bool = False) -> dict | None:
        """A remembered procedure for this task.

        `trial` selects which floor applies, and the difference is the safety
        property the old single floor was trying and failing to express. An answer
        must be trusted or have actually run. A trial may be merely plausible,
        because the caller that asked for a trial is the router, and the router
        executes what it recalls before it will hand any of it back.
        """
        floor = self.trial_floor if trial else self.min_confidence
        # The learning loop's store is the library that actually exists: it holds
        # confidence, provenance and the verified solutions, and its retrieval
        # retrieves. The two mirrors below are fed only by propagation from it, so
        # consulting them first meant the replay path had nothing to replay no
        # matter how much was known -- and it was consulted first for the whole
        # life of the project.
        if self.learning is not None:
            try:
                hit = self.learning.recall(str(task or ""),
                                           min_confidence=floor)
            except Exception:
                hit = None
            if hit and str(hit.get("solution") or "").strip():
                conf = float(hit.get("confidence", 0.0) or 0.0)
                return {"solution": str(hit["solution"]), "method": "learned",
                        "confidence": round(conf, 3),
                        "verified": bool(hit.get("verified")),
                        "trusted": conf >= self.min_confidence,
                        "signature": hit.get("signature"),
                        "provenance": str(hit.get("provenance") or "")[:64],
                        "steps": 1,
                        "language": hit.get("language", "python")}
        proc = None
        if self.exo is not None:
            sig = None
            try:
                sig = self.exo.signature(task)
                proc = self.exo.recall_procedure(sig)
            except Exception:
                proc = None
        if proc is None and self.procedures is not None:
            try:
                proc = self.procedures.match(task, min_success_rate=0.6)
            except TypeError:
                proc = self.procedures.match(task)
        if not proc:
            return None
        conf = float(proc.get("confidence", proc.get("success_rate", 0.0)) or 0)
        if conf < floor:
            return None
        steps = proc.get("dag") or proc.get("action_sequence") or []
        code = _embedded_code(steps)
        if not code:
            return None
        verified = bool(proc.get("successes")) and self._verify(code, task)
        return {"solution": code, "method": "procedure",
                "confidence": round(conf, 3),
                "verified": verified,
                "trusted": conf >= self.min_confidence,
                "provenance": f"procedure({(proc.get('signature') or '')[:24]},"
                              f"conf={conf:.2f})",
                "steps": len(steps) if isinstance(steps, list) else 0,
                "language": proc.get("language", "python")}

    def _pattern_candidates(self, task: str) -> list:
        """Every pattern hit at or above the confidence floor, best first, as
        (confidence, code, key) triples. Split out of `_from_pattern` because
        composition needs the runners-up, not just the winner."""
        if self.patterns is None:
            return []
        key = _short_key(task)
        found = []
        try:
            direct = self.patterns.query(key)
            if direct:
                found.append(direct)
            for sub in sorted(_words(task), key=len, reverse=True)[:6]:
                for hit in self.patterns.search(sub, limit=3):
                    if hit not in found:
                        found.append(hit)
        except Exception:
            return []
        out = []
        for h in found:
            val = h.get("value") if isinstance(h, dict) else h
            if not val:
                continue
            conf = float((h or {}).get("confidence", 0.0) or 0.0) \
                if isinstance(h, dict) else 0.0
            code = val if isinstance(val, str) and _looks_like_code(val) \
                else _embedded_code(val)
            if code and conf >= self.min_confidence:
                out.append((conf, code,
                            str(h.get("key") if isinstance(h, dict) else "")))
        out.sort(key=lambda t: -t[0])
        return out

    def _from_pattern(self, task: str) -> dict | None:
        cands = self._pattern_candidates(task)
        if not cands:
            return None
        conf, code, key = cands[0]
        if not code:
            return None
        verified = self._verify(code, task)
        return {"solution": code, "method": "pattern",
                "confidence": round(conf, 3), "verified": verified,
                "provenance": f"pattern({key[:28]})"}

    def recall_procedure(self, task: str, min_confidence: float | None = None
                         ) -> Recalled | None:
        """A remembered procedure for this task, if one clears the floor.

        The router passes a trial floor and then executes what comes back, so a
        procedure below the trust floor is still worth handing over here -- it is
        the only way it can ever gather the evidence that raises it.

        The default has to agree with the floor _from_procedure just used. It used
        to re-apply min_confidence here, a second and higher gate, which quietly
        undid the trial: every caller that did not pass an explicit floor got
        nothing back, however good the recall, and a drill of 40 requests reported
        40 misses against a library of 275.
        """
        hit = self._from_procedure(task, trial=True)
        if not hit:
            return None
        floor = self.trial_floor if min_confidence is None \
            else float(min_confidence)
        if hit["confidence"] < floor:
            return None
        return Recalled(hit)

    def query_patterns(self, task: str, limit: int = 6) -> list:
        return [{"confidence": round(c, 3), "code": code, "key": key}
                for c, code, key in self._pattern_candidates(task)[:limit]]

    def compose(self, patterns, task: str, require_verified: bool = True
                ) -> dict | None:
        """Assemble a solution from remembered pieces, and only claim it if the
        verifier agrees.

        This is the one rung with no intelligence behind it -- it concatenates.
        Which is precisely why it must be verified: unverified composition is a
        paste, and a paste presented as a solution is how a memory system learns
        to lie.
        """
        cands = list(patterns or [])
        if not cands:
            cands = self.query_patterns(task)
        if len(cands) < 2:
            return None
        seen, blocks, keys = set(), [], []
        for p in cands[:4]:
            code = str(p.get("code") if isinstance(p, dict) else p).strip()
            if not code or code in seen:
                continue
            seen.add(code)
            blocks.append(code)
            keys.append(str(p.get("key", "snippet") if isinstance(p, dict)
                           else "snippet"))
        if len(blocks) < 2:
            return None
        artifact = "\n\n".join(blocks)
        ok, kind = self._verify_detail(artifact, task)
        if require_verified and (not ok or kind != "execution"):
            # Concatenation is not composition, and a clean exit is not evidence
            # when nothing was called. This declines for a reason it can state,
            # rather than declining because a verifier method did not exist.
            self.composed_failed = getattr(self, "composed_failed", 0) + 1
            self.composed_refusal = (
                "artifact did not run" if not ok else
                "artifact only defined things; running it checked nothing")
            return None
        conf = min(float(p.get("confidence", 0.0) or 0.0)
                   for p in cands[:len(blocks)] if isinstance(p, dict)) \
            if all(isinstance(p, dict) for p in cands[:len(blocks)]) else 0.0
        self.composed = getattr(self, "composed", 0) + 1
        return {"solution": artifact, "method": "composition",
                "confidence": round(conf, 3), "verified": bool(ok),
                "api_calls": 0, "tokens": 0, "components": keys[:4],
                "provenance": "composition(" + "+".join(keys[:4]) + ")"}

    def _from_atlas(self, task: str) -> dict | None:
        """The atlas answers *what*, never *write the function*. It is used to
        enrich context, so it reports knowledge=None-with-note rather than
        pretending a concept list is a solution."""
        if self.exo is None:
            return None
        try:
            hits = self.exo.search_concepts(task, k=4)
        except Exception:
            return None
        names = [h.get("concept") or h.get("name") or h.get("token") or ""
                 for h in (hits or [])]
        names = [n for n in names if n]
        if not names:
            return None
        return None if not names else {
            "solution": "", "method": "atlas_knowledge", "confidence": 0.0,
            "verified": False, "knowledge": names,
            "provenance": "atlas(" + ",".join(names[:3]) + ")",
            "note": ("concepts recalled, no artifact: the atlas is knowledge, "
                     "not a generator -- the caller must still write the code")}

    def recall_fact(self, task: str, check: str = "") -> dict:
        """A verified procedure for this task's FACT, or a miss.

        A MISS IS THE POINT. The key is (concept, subject) from a controlled vocabulary,
        so a cylinder asks for (surface_area, cylinder) and gets NOTHING rather than the
        sphere formula. There is deliberately no similarity fallback: a near-miss would
        hand over a formula that was never right, the task's assertions would reject it,
        and the failure would look like the search's fault instead of the wrong question's.

        The reference resolves through the FACT KEY and not through the task text, which is
        what lets a differently-worded task about the same thing find it -- "area of a ball"
        and "surface area of a sphere" reach the same procedure because both key to
        (surface_area, sphere), not because their words overlap.
        """
        from .concepts import extract_key
        store = getattr(self, "fact_store", None)
        concept, subject, shape = extract_key(task, check)
        base = {"code": None, "ref": None, "concept": concept, "subject": subject,
                "shape": shape}
        if not concept or not subject:
            return dict(base, found=False, reason="no concept+subject key")
        if store is None:
            return dict(base, found=False, reason="no fact store attached")
        ref = store.recall_fact(concept, subject, shape)
        if not ref:
            return dict(base, found=False, reason="nothing filed for this key")
        rec = (getattr(self.learning, "store", {}) or {}).get(ref) or {}
        sols = rec.get("solutions") or []
        code = str((sols[-1] or {}).get("text") or "") if sols else ""
        if not code.strip():
            return dict(base, found=False, ref=ref,
                        reason="the fact points at a procedure with no code")
        return dict(base, found=True, reason="fact", code=code, ref=ref,
                    confidence=rec.get("confidence"))

    def compose_against(self, task: str, check: str, max_steps: int = 3,
                        candidates: int = 60, budget: int = 12) -> dict:
        """Build a solution out of verified procedures, and let the tests decide.

        Interface adaptation -- renaming a recalled function to the name the tests
        ask for -- got the tasks whose knowledge was already in the library and
        nothing else. Composition is the next rung: put two or three verified
        procedures together as a pipeline and see whether the task's own assertions
        accept the result.

        The interface is READ OFF THE ASSERTIONS, not guessed: which names the tests
        call and with how many arguments. A name called with two arguments cannot be
        satisfied by a one-argument function however good it is, and knowing that
        before executing anything is most of the work.

        Static filters, run before the sandbox so only plausible shapes pay for a
        run: call shape (the wrapper's arity must equal the arity the tests use, and
        a pipeline's final stage must accept what the previous one returns), name
        availability, and dependency closure -- each candidate keeps its own imports,
        because a stored solution that needs `heapq` is not a solution without it.

        What this does NOT do, and will not claim: trace types. Python signatures do
        not declare them, so a static type check across a composition boundary is not
        available here. The filters are the ones the language actually permits, and
        the tests are what decide in the end.

        Nothing passes without the task's assertions. A composition that runs and
        fails is not stored, whatever it cost to build.
        """
        req = _requested(check)
        want = dict(req.get("names") or {})
        # The test harness's own names are not the solution's interface.
        for junk in ("assert", "print", "len", "range", "set", "list", "tuple",
                     "sorted", "sum", "max", "min", "abs", "int", "str",
                     "float", "bool", "dict", "zip", "enumerate", "reversed",
                     "isinstance", "type", "round", "any", "all", "map",
                     "filter", "open", "compile", "eval", "Exception"):
            want.pop(junk, None)
        if not want:
            return {"ok": False, "reason": "the tests call nothing to implement",
                    "tried": 0}
        target, arity = sorted(want.items(),
                               key=lambda kv: -kv[1])[0]
        # Rank the library against the task text, cheaply and without an organ: the
        # store already carries the distinctiveness weighting retrieval uses.
        pool = []
        try:
            for sig, rec in (self.learning.store or {}).items():
                if not (rec.get("successes") or rec.get("confidence", 0) >= 0.5):
                    continue
                sols = rec.get("solutions") or []
                code = ""
                for s in reversed(sols):
                    if s.get("text") and not s.get("truncated"):
                        code = str(s["text"])
                        break
                if not code.strip():
                    continue
                pool.append((rec.get("task", ""), code))
        except Exception:
            pool = []
        if not pool:
            return {"ok": False, "reason": "nothing verified to compose from",
                    "tried": 0}
        want_terms = set(re.findall(r"[a-z]{4,}", str(task or "").lower()))

        def score(item):
            t = set(re.findall(r"[a-z]{4,}", str(item[0]).lower()))
            return len(want_terms & t) / max(1, len(want_terms | t))

        pool.sort(key=score, reverse=True)
        pool = pool[:max(2, int(candidates))]

        tried = 0
        rejects: dict = {}

        def static_ok(artifact: str) -> str | None:
            fns = _functions_in(artifact)
            if target not in {f["name"] for f in fns}:
                return "target name not defined"
            entry = next(f for f in fns if f["name"] == target)
            if not entry["varargs"] and entry["arity"] != arity:
                return (f"call shape {entry['arity']} args against "
                        f"{arity} the tests use")
            names = [f["name"] for f in fns]
            if len(names) != len(set(names)):
                return "duplicate definitions"
            return None

        def attempt(artifact: str, label: str) -> dict | None:
            nonlocal tried
            why = static_ok(artifact)
            if why:
                rejects[why] = rejects.get(why, 0) + 1
                return None
            if tried >= int(budget):
                return None
            tried += 1
            ok, kind = self._verify_detail(artifact + "\n\n" + check, check)
            if ok:
                return {"ok": True, "code": artifact, "method": label,
                        "tried": tried, "evidence": kind}
            return None

        # one step: a stored solution used as it is, under the name the tests want
        for src_task, code in pool[:6]:
            fns = _functions_in(code)
            if not fns:
                continue
            f = fns[0]
            if f["arity"] != arity:
                rejects["call shape at step 1"] = \
                    rejects.get("call shape at step 1", 0) + 1
                continue
            artifact = "\n".join(filter(None, [_imports_in(code),
                                              _rename_function(code, target)]))
            got = attempt(artifact, "rename")
            if got:
                got["source_task"] = str(src_task)[:80]
                return got

        # two and three steps: pipeline the procedures, arity-checked at the seam
        if int(max_steps) >= 2:
            firsts = [c for _, c in pool if _functions_in(c) and
                      _functions_in(c)[0]["arity"] == arity]
            nexts = [c for _, c in pool if _functions_in(c) and
                     _functions_in(c)[0]["arity"] in (1, 2)]
            for inner in firsts[:8]:
                for outer in nexts[:8]:
                    fi, fo = _functions_in(inner)[0], _functions_in(outer)[0]
                    if fi["name"] == fo["name"]:
                        continue
                    calls = fi["name"] + "(*a)"
                    if fo["arity"] == 2:
                        calls = fo["name"] + "(" + calls + ", *a[1:])"
                    else:
                        calls = fo["name"] + "(" + calls + ")"
                    wrapper = (f"def {target}(*a):\n"
                               f"    return {calls}\n")
                    artifact = "\n".join(filter(None, [
                        _imports_in(inner), _imports_in(outer), inner, outer,
                        wrapper]))
                    got = attempt(artifact, "pipeline2")
                    if got:
                        return got
        return {"ok": False, "tried": tried, "target": target,
                "arity": arity,
                "reason": ("no combination passed" if tried else
                           "every combination was rejected statically"),
                "static_rejections": rejects,
                "pool": len(pool)}

    def repair_against(self, code: str, check: str, max_tries: int = 3) -> dict:
        """Let the failure say what to change.

        A recalled function is not a solution to a task. It carries its own name,
        its own signature and its own imports, while the task asks for a particular
        interface -- which is why 'fold plural and verbal suffixes' recalled the
        right function and still failed its check, calling stem(...) at module level
        while the artifact defined stem inside a class.

        The check knows what it wanted: it fails with NameError('fib') when the
        artifact defines the right thing under the wrong name. Renaming a single
        top-level function to the name that was asked for is mechanical, needs no
        model, and turns retrieval into an answer for every task whose knowledge is
        already in the library. When the check fails for any other reason, or the
        artifact is not a single function, there is nothing mechanical to do and this
        says so rather than guessing.
        """
        code = str(code or "")
        if not code.strip() or not str(check or "").strip():
            return {"ok": False, "reason": "nothing to repair", "code": code}
        tried = 0
        last = ""
        for _ in range(max(1, int(max_tries))):
            ok, kind = self._verify_detail(code + "\n\n" + str(check), check)
            if ok:
                return {"ok": True, "code": code, "renames": tried,
                        "evidence": kind}
            last = self._last_verify_error or ""
            m = _MISSING.search(last) or _MISSING.search(str(code))
            if not m:
                return {"ok": False, "code": code, "renames": tried,
                        "reason": (last.strip()[-160:] or "check failed"),
                        "evidence": kind}
            wanted = m.group(1)
            if _single_function_name(code) == wanted:
                return {"ok": False, "code": code, "renames": tried,
                        "reason": f"defined {wanted} already and still failed",
                        "evidence": kind}
            renamed = _rename_function(code, wanted)
            if renamed == code:
                return {"ok": False, "code": code, "renames": tried,
                        "reason": f"could not rename to {wanted}",
                        "evidence": kind}
            code = renamed
            tried += 1
        return {"ok": False, "code": code, "renames": tried,
                "reason": (last.strip()[-160:] or "still failing")}

    def _verify(self, code: str, task: str) -> bool:
        return self._verify_detail(code, task)[0]

    def _verify_detail(self, code: str, task: str) -> tuple:
        """(held_up, how_strong_the_evidence_is).

        Two levels, and telling them apart is the whole point of a design that
        rests on execution:

          "execution"  the sandbox ran it and it exited clean. Real evidence.
          "syntax"     it compiles and nothing more. LanguageVerifier's python
                       check is only compile(), so a function that raises on every
                       possible input still passes it -- weak, and recorded as
                       weak rather than passed off as a run.

        This used to call verifier.verify(), a method no verifier in the project
        has ever defined; the real one is check(). The AttributeError was swallowed
        by the except underneath, so every verification in production returned
        False. That is why composition always declined to hand back an assembly,
        why no procedure was ever marked verified however often it ran, and why a
        trial replay could never have succeeded.
        """
        code = str(code or "")
        if not code.strip():
            return False, ""
        sb = getattr(self, "sandbox", None)
        if sb is not None and hasattr(sb, "run_python"):
            self._last_verify_error = ""
            # A unique name every time. run_python defaults to one fixed filename,
            # and the sandbox's write gate refuses to overwrite without approval --
            # so the first verification in a process ran and every one after it was
            # DENIED, which read exactly like the recalled code failing. A drill of
            # five trials kept one and dropped four for this reason alone.
            import time as _time
            self._verify_seq = int(getattr(self, "_verify_seq", 0)) + 1
            name = "_verify_%d_%d.py" % (int(_time.time()), self._verify_seq)
            try:
                r = sb.run_python(code, timeout=self.verify_timeout, name=name)
            except Exception:
                r = None
            if isinstance(r, dict):
                self._last_verify_error = str(
                    r.get("stderr") or r.get("output") or r.get("error") or "")
                ok = bool(r.get("success", r.get("ok", False))) and \
                    int(r.get("returncode", r.get("exit_code", 0)) or 0) == 0
                if ok and _defines_only(code):
                    return True, "definitional"
                return ok, "execution"
        v = self.verifier
        if v is None:
            return False, ""
        for meth in ("check", "verify"):
            fn = getattr(v, meth, None)
            if fn is None:
                continue
            try:
                out = fn(code, "python")
            except TypeError:
                try:
                    out = fn(code)
                except Exception:
                    continue
            except Exception:
                continue
            if isinstance(out, dict):
                return bool(out.get("valid", out.get("ok", False))), "syntax"
            return bool(out), "syntax"
        return False, ""

    def list_patterns(self, query: str = "", limit: int = 50) -> dict:
        """The pattern library, as rows. Says so when there is no library.

        A panel that shows "0 patterns" when the truth is "no library was
        attached" teaches the reader that the agent has learned nothing, which is
        a different claim from the one the evidence supports.
        """
        lib = self.patterns
        if lib is None:
            return {"present": False, "patterns": [],
                    "note": "no pattern library attached to local_solver"}
        rows: list[dict] = []
        try:
            raw = lib.to_list() if hasattr(lib, "to_list") else []
        except Exception as e:
            return {"present": True, "patterns": [],
                    "note": f"library unreadable: {type(e).__name__}: {e}"}
        q = str(query or "").strip().lower()
        for r in raw or []:
            d = dict(r) if isinstance(r, dict) else {"value": str(r)[:300]}
            hay = " ".join(str(d.get(k, "")) for k in
                           ("key", "trigger_pattern", "value", "name"))
            if q and q not in hay.lower():
                continue
            rows.append(d)
        rows.sort(key=lambda d: float(d.get("confidence", 0) or 0), reverse=True)
        return {"present": True, "total": len(rows),
                "patterns": rows[:max(1, int(limit))]}

    def explain(self, task: str) -> dict:
        return {"would_try": ["procedure", "pattern", "atlas"],
                "have_procedures": self.exo is not None or
                                   self.procedures is not None,
                "have_patterns": self.patterns is not None,
                "have_verifier": self.verifier is not None,
                "min_confidence": self.min_confidence,
                "note": "verification absent means a local answer is reported "
                        "verified=False, never assumed true"}

    def stats(self) -> dict:
        return {"attempts": self.attempts, "solved": self.solved,
                "refused": self.refusals, "by_method": dict(self.by_method),
                "solve_rate": round(self.solved / max(1, self.attempts), 3),
                "min_confidence": self.min_confidence}

def _embedded_code(steps) -> str:
    """Pull a code artifact out of a recalled procedure, if it has one."""
    if isinstance(steps, str) and _looks_like_code(steps):
        return steps
    cands = []
    items = steps if isinstance(steps, list) else [steps]
    for s in items:
        if isinstance(s, dict):
            for k in ("code", "artifact", "snippet", "body", "solution"):
                if s.get(k):
                    cands.append(str(s[k]))
        elif isinstance(s, str) and _looks_like_code(s):
            cands.append(s)
    return "\n\n".join(cands) if cands else ""

def _looks_like_code(s: str) -> bool:
    if not s or len(s) < 12:
        return False
    return bool(re.search(r"^\s*(def |class |import |from |for |while |if |"
                          r"return |async def )", s, re.M)) or \
        ("(" in s and ")" in s and ":" in s and "\n" in s)

def _short_key(text: str, n: int = 6) -> str:
    w = sorted(_words(text))[:n]
    if not w:
        w = sorted(set(re.findall(r"[a-z_]{2,}", str(text or "").lower())))[:n]
    return " ".join(w)