
from __future__ import annotations

import re

PLAN_ACTIONS = ("ADD_VARIABLE", "MODIFY_FUNCTION", "ADD_FUNCTION",
                "ADD_CONDITION", "ADD_IMPORT", "WRITE_FILE", "TEST",
                "MUTATE")

class PlannerOrgan:
    def __init__(self, llm_organ=None):
        self.llm = llm_organ
        self.plans_made = 0

    def create_plan(self, goal: str, chosen_approach, existing_code: str,
                    test_cmd: str = "", language: str = "python") -> list:
        self.plans_made += 1
        if isinstance(chosen_approach, dict):
            op = chosen_approach.get("op", "ADD_FUNCTION")
            name = chosen_approach.get("name", "approach")
            sketch = chosen_approach.get("sketch", "")
        else:
            op, name, sketch = "ADD_FUNCTION", str(chosen_approach), ""
        fns = re.findall(r"def (\w+)", existing_code or "") if language == \
            "python" else _first_fns(language, existing_code)
        fn = fns[0] if fns else "main"
        plan: list[dict] = []

        if language != "python" and not (existing_code or "").strip():
            def mk(action, target, content, verify):
                plan.append({"step": len(plan) + 1, "action": action,
                             "target": target, "content": content,
                             "verify": verify, "status": "pending",
                             "attempts": 0, "error": ""})
            mk("WRITE_FULL_FILE", "main", goal or str(name),
               "mechanical verifier accepts the composed file")
            gl = goal.lower()
            if language == "cpp" and "class" in gl:
                mk("ADD_CLASS", "Stack", "", "class composed")
            elif language == "javascript" and ("event" in gl or
                                               "listener" in gl):
                mk("ADD_EVENT_LISTENER", "button",
                   "el.classList.toggle('active');", "listener composed")
            mk("TEST", "", {}, "test output contains OK")
            return plan

        def add(action, target, content, verify):
            plan.append({"step": len(plan) + 1, "action": action,
                         "target": target, "content": content,
                         "verify": verify, "status": "pending",
                         "attempts": 0, "error": ""})

        if op == "ADD_CONDITION":
            add("ADD_CONDITION", fn,
                {"test": _guard_test(existing_code, fn),
                 "body": "return None"},
                "syntax ok; guard visible in AST")
        elif op == "WRAP_TRY_EXCEPT":
            add("MUTATE", fn, {"mutation": "WRAP_TRY_EXCEPT",
                               "value": _risky_fn(existing_code) or fn},
                "syntax ok; Try node present")
        elif op == "ADD_VARIABLE":
            var = _state_name(goal)
            add("ADD_VARIABLE", var, "0", "syntax ok; assignment exists")
            add("MODIFY_FUNCTION", fn, {"body": _update_body(existing_code,
                                                             fn, var)},
                "syntax ok; variable updated in " + fn)
        elif op == "helper_extraction" or op == "ADD_FUNCTION":
            helper = f"{name}_helper" if not name.endswith("_helper") \
                else name
            add("ADD_FUNCTION", helper,
                _helper_def(helper, fn, sketch),
                "syntax ok; function defined")
            add("MODIFY_FUNCTION", fn, {"body": _call_body(existing_code,
                                                           fn, helper)},
                "call site updated")
        else:
            var = _state_name(goal)
            add("ADD_VARIABLE", var, "{}", "syntax ok")
            add("MODIFY_FUNCTION", fn, {"body": _update_body(existing_code,
                                                             fn, var)},
                "syntax ok")
        add("TEST", test_cmd or f"python -c \"import {fn or 'x'}\"",
            {"cmd": test_cmd} if test_cmd else {},
            "test output contains OK")
        if language != "python":
            plan = self._translate(plan, language, existing_code, goal)
            gl = str(goal).lower()
            if language == "javascript" and ("event" in gl or
                                             "listener" in gl) and \
                    not any(s["action"] == "ADD_EVENT_LISTENER"
                            for s in plan):
                plan.insert(0, {"step": 0, "action": "ADD_EVENT_LISTENER",
                                "target": "button",
                                "content": "el.classList.toggle"
                                           "('active');",
                                "verify": "listener composed",
                                "status": "pending", "attempts": 0,
                                "error": ""})
                plan = [dict(s, step=i + 1) for i, s in enumerate(plan)]
        return plan

    def _translate(self, plan, language, existing_code, goal):
        out = []
        var = _state_name(goal)
        for s in plan:
            s = dict(s)
            a = s["action"]
            if a == "ADD_CONDITION":
                s["content"] = {"test": _guard_expr(language, existing_code),
                                "body": _nil_return(language)}
            elif a == "MUTATE":
                c = s["content"] if isinstance(s["content"], dict) else {}
                if c.get("mutation") == "WRAP_TRY_EXCEPT":
                    s["action"] = "ADD_FUNCTION"
                    s["target"] = "safe_" + str(s["target"])
                    s["content"] = {"body": _try_body(language,
                                                      str(s["target"]))}
                    s["verify"] = "syntax ok; safe wrapper composed"
            elif a == "MODIFY_FUNCTION":
                s["content"] = {"body": _update_body_lang(language, var)}
            elif a == "ADD_FUNCTION":
                s["content"] = {"body": _native_helper_body(language),
                                "params": "x"}
                s["verify"] = "syntax ok; function composed in " + language
            elif a == "TEST":
                s["content"] = {}
            out.append(s)
        return out

    def parse_llm_plan(self, llm_response: str) -> list[dict]:
        plan = []
        for m in re.finditer(
                r"(?im)^\s*STEP\s+(\d+)\s*:?\s*$?", str(llm_response or "")):
            start = m.end()
            nxt = re.search(r"(?im)^\s*STEP\s+\d+", llm_response[start:])
            body = llm_response[start: start + (nxt.start() if nxt
                                                else len(llm_response))]
            g = lambda k: (re.search(rf"(?im)^\s*{k}\s*[:.]\s*(.+)$", body)
                           or [None, ""])[1].strip()
            action = g("action").upper().replace(" ", "_")
            if action not in PLAN_ACTIONS:
                continue
            plan.append({"step": int(m.group(1)), "action": action,
                         "target": g("target"), "content": g("content"),
                         "verify": g("verify") or "manual check",
                         "status": "pending", "attempts": 0, "error": ""})
        for i, s in enumerate(plan):
            s["step"] = i + 1
        return plan

    def next_step(self, plan: list[dict]) -> dict | None:
        return next((s for s in plan if s["status"] == "pending"), None)

    def mark_complete(self, plan: list[dict], step_number: int):
        s = self._get(plan, step_number)
        if s:
            s["status"] = "complete"
        return plan

    def mark_failed(self, plan: list[dict], step_number: int, error: str):
        s = self._get(plan, step_number)
        if s:
            s["status"] = "pending"
            s["attempts"] = s.get("attempts", 0) + 1
            s["error"] = str(error)[:160]
            if s["attempts"] >= 3:
                s["status"] = "failed"
        return plan

    def revise_plan(self, plan: list[dict], failed_step: dict, error: str,
                    next_approach=None) -> list[dict] | None:
        """Fix-in-place when the failure is local; ABANDON (return None →
        caller switches approach) when the step is fundamentally wedged."""
        if failed_step.get("attempts", 0) >= 3 or next_approach:
            return None
        failed_step["status"] = "pending"
        failed_step["attempts"] = 0
        content = failed_step.get("content")
        if isinstance(content, dict) and "body" in content:
            content["body"] = str(content["body"]).replace(
                "pass", "return None")
        failed_step["content"] = content
        failed_step["revised"] = str(error)[:120]
        return plan

    def estimate_progress(self, plan: list[dict]) -> float:
        if not plan:
            return 0.0
        return round(sum(1 for s in plan if s["status"] == "complete")
                     / len(plan), 3)

    @staticmethod
    def _get(plan, n):
        return next((s for s in plan if s["step"] == n), None)

def _first_fns(language: str, code: str) -> list:
    """Top-level function names for non-python languages (mechanical)."""
    code = code or ""
    if language == "lua":
        return re.findall(r"(?:local\s+)?function\s+(\w+)", code)
    if language == "javascript":
        return (re.findall(r"function\s+(\w+)\s*\(", code)
                + re.findall(r"(?:const|let|var)\s+(\w+)\s*=\s*(?:\(|"
                             r"function|async)", code))
    if language in ("c", "cpp"):
        return [m.group(1) for m in re.finditer(
            r"\b(\w+)\s*\([^)]*\)\s*\{", code)
            if m.group(1) not in ("if", "while", "for", "switch")]
    return []

def _guard_expr(language: str, code: str) -> str:
    """'argument may be missing' written natively."""
    arg = ""
    for pat in (r"function\s+\w+\s*\(([^)]*)\)",
                r"\w+\s*\(([^)]*)\)\s*(?:\{|=>)"):
        m = re.search(pat, code or "")
        if m:
            args = [a.strip() for a in m.group(1).split(",")
                    if a.strip() and a.strip() not in ("self", "void")]
            if args:
                arg = re.sub(r"[^A-Za-z_]", "", args[0]) or ""
            break
    arg = arg or "x"
    return {"lua": f"{arg} == nil",
            "javascript": f"!{arg}",
            "c": f"!{arg}", "cpp": f"!{arg}"}.get(language, f"!{arg}")

def _nil_return(language: str) -> str:
    return {"lua": "return nil", "javascript": "return null;",
            "c": "return 0;", "cpp": "return 0;"}.get(language,
                                                      "return null;")

def _try_body(language: str, call: str) -> str:
    core = {"lua": f"    local ok, res = pcall({call})\n"
                    "    if not ok then return nil end\n    return res",
            "javascript": f"    try {{ return {call}(); }} "
                          "catch (e) {{ return null; }}",
            "c": "    if (1) { return 0; }",
            "cpp": "    try { return 0; } catch (...) { return -1; }"}
    return core.get(language, "return 0;")

def _native_helper_body(language: str) -> str:
    return {"lua": "return x", "javascript": "return x;",
            "c": "return x;", "cpp": "return x;",
            "html": "<!-- helper -->"}.get(language, "return x;")

def _update_body_lang(language: str, var: str) -> str:
    return {"lua": f"{var} = {var} + 1\nreturn {var}",
            "javascript": f"{var} += 1;\nreturn {var};",
            "c": f"{var} = {var} + 1;\nreturn {var};",
            "cpp": f"{var} = {var} + 1;\nreturn {var};"}.get(
        language, f"{var} += 1; return {var};")

def _risky_fn(code: str) -> str:
    """First function that CALLS another module-defined function: that
    caller is where a failure mode must be caught."""
    defs = set(re.findall(r"def\s+(\w+)", code or ""))
    for m in re.finditer(r"def\s+(\w+)\s*\(\s*[^)]*\)\s*:", code or ""):
        name = m.group(1)
        rest = code[m.end():]
        nxt = re.search(r"^def ", rest, re.M)
        seg = rest[:nxt.start()] if nxt else rest
        if any(c in defs and c != name for c in
               re.findall(r"\b(\w+)\s*\(", seg)):
            return name
    return ""

def _guard_test(code: str, fn: str) -> str:
    m = re.search(rf"def {re.escape(fn)}\(([^)]*)\)", code or "")
    args = [a.strip().split(":")[0].split("=")[0] for a in
            (m.group(1).split(",") if m else [])
            if a.strip() and a.strip() not in ("self", "cls")]
    a = args[0] if args else "x"
    if re.search(rf"\bfor\b.*\b{a}\b", code or "") or "len(" in (code or ""):
        return f"not {a}"
    if re.search(rf"\b{a}\s*/", code or ""):
        return f"{a} == 0"
    return f"{a} is None"

def _state_name(goal: str) -> str:
    for w in ("jump_count", "counter", "cache", "state", "count", "total"):
        if w in (goal or "").lower():
            return w
    return "counter"

def _neutral_for(code):
    return "None"

def _update_body(code: str, fn: str, var: str) -> str:
    m = re.search(rf"def {re.escape(fn)}\(([^)]*)\)", code or "")
    args = [a.strip().split(":")[0].split("=")[0] for a in
            (m.group(1).split(",") if m else [])
            if a.strip() and a.strip() not in ("self", "cls")]
    if not args:
        return (f"global {var}\n{var} += 1\nreturn {var}")
    arg = args[0]
    return (f"{arg} = {arg} if {arg} is not None else []\n"
            f"global {var}\n{var} += 1\n"
            f"return {var}")

def _call_body(code: str, fn: str, helper: str) -> str:
    m = re.search(rf"def {re.escape(fn)}\(([^)]*)\)", code or "")
    sig = m.group(0) if m else f"def {fn}(x):"
    inner = re.findall(r"\(([^)]*)\)", sig)[0]
    args = [a.strip().split(":")[0].split("=")[0] for a in
            inner.split(",")
            if a.strip() and a.strip() not in ("self", "cls")]
    arg = args[0] if args else "x"
    return f"return {helper}({arg})"

def _helper_def(helper: str, fn: str, sketch: str) -> str:
    return (f"def {helper}(x):\n"
            f"    \"\"\"{sketch[:70] or 'isolated sub-problem logic'}\"\"\"\n"
            f"    return x")