
from __future__ import annotations

import ast
import re

class CausalReasonerOrgan:
    def __init__(self, llm_organ=None, filesystem_organ=None):
        self.llm = llm_organ
        self.fs = filesystem_organ
        self.traced = 0

    def trace_dependencies(self, entity, code: str) -> list[dict]:
        """Every read / write / call site of `entity` in `code`."""
        self.traced += 1
        if isinstance(entity, (list, tuple)):
            out = []
            for e in entity:
                out.extend(self.trace_dependencies(e, code))
            return out
        name = str(entity).strip()
        hits: list[dict] = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            for i, line in enumerate(code.splitlines()):
                if re.search(rf"\b{re.escape(name)}\b", line):
                    hits.append({"line": i + 1, "type": "text",
                                 "context": line.strip()[:90]})
            return hits
        for node in ast.walk(tree):
            ln = getattr(node, "lineno", None)
            ctx = code.splitlines()[ln - 1].strip()[:90] if ln else ""
            if isinstance(node, ast.Name) and node.id == name:
                kind = ("write" if isinstance(node.ctx, ast.Store)
                        else "read")
                hits.append({"line": ln, "type": kind, "context": ctx})
            elif isinstance(node, ast.Attribute) and node.attr == name:
                hits.append({"line": ln, "type": "attr", "context": ctx})
            elif isinstance(node, ast.FunctionDef) and node.name == name:
                hits.append({"line": ln, "type": "define", "context": ctx})
            elif isinstance(node, ast.Call):
                f = node.func
                fn = f.id if isinstance(f, ast.Name) else \
                    (f.attr if isinstance(f, ast.Attribute) else "")
                if fn == name:
                    hits.append({"line": ln, "type": "call", "context": ctx})
        return hits

    def predict_effects(self, proposed_change: str, existing_code: str) -> dict:
        touched = set(re.findall(
            r"(?:def|for|if|=)\s+([A-Za-z_]\w+)", str(proposed_change)))
        for m in re.finditer(r"([A-Za-z_]\w+)\s*[=(.]", str(proposed_change)):
            touched.add(m.group(1))
        affected = []
        for t in sorted(touched):
            if len(t) < 3 or t in ("def", "for", "if", "ret"):
                continue
            sites = [h for h in self.trace_dependencies(t, existing_code)
                     if h["type"] in ("read", "call", "attr")]
            if sites:
                affected.append({"symbol": t,
                                 "readers": len(sites),
                                 "lines": [s["line"] for s in sites][:6]})
        edge = []
        cd = existing_code or ""
        if "def " in str(proposed_change) and "return" not in str(
                proposed_change):
            edge.append("added function has no return: callers get None")
        if re.search(r"\bwhile\b", cd) and "break" not in str(proposed_change):
            edge.append("loop present: guard termination if touching it")
        if "except" in str(proposed_change):
            edge.append("bare handler may swallow KeyboardInterrupt-class "
                        "issues")
        llm_notes = ""
        if self.llm is not None:
            try:
                llm_notes = self.llm.query(
                    "failure modes of change " + str(proposed_change)[:200]
                    + " in " + cd[:200]).get("text", "")[:300]
            except Exception:
                pass
        return {"affected_symbols": affected, "possible_edge_cases": edge,
                "knowledge": llm_notes}

    def find_root_cause(self, error_message: str, code: str) -> dict:
        err = str(error_message or "")
        m = re.search(r"(\w*Error|Exception|Warning):?\s*(.*)", err)
        kind, msg = (m.group(1), m.group(2)) if m else ("Error", err[:80])
        loc = re.search(r'File "([^"]+)", line (\d+)', err)
        cause = {"cause": f"{kind}: {msg.strip()[:120]}",
                 "location": (f"{loc.group(1)}:{loc.group(2)}" if loc
                              else "unknown"),
                 "fix_suggestion": "", "symbol": ""}
        if kind == "NameError":
            sym = re.search(r"name '(\w+)'", msg)
            cause["symbol"] = sym.group(1) if sym else ""
            cause["fix_suggestion"] = (
                f"define/import {cause['symbol']!r} before use"
                if cause["symbol"] else "define the missing name")
        elif kind == "SyntaxError":
            ln = re.search(r"line (\d+)", err)
            cause["location"] = f"line {ln.group(1)}" if ln else "unknown"
            cause["fix_suggestion"] = ("repair the malformed statement "
                                       "shown in the traceback")
        elif kind == "TypeError":
            cause["fix_suggestion"] = ("check argument count/type at the "
                                       "call site in the traceback")
        elif kind == "ZeroDivisionError":
            cause["fix_suggestion"] = "guard the divisor before dividing"
        elif kind in ("KeyError", "IndexError"):
            cause["fix_suggestion"] = "membership/bounds check before access"
        elif kind == "AssertionError":
            cause["fix_suggestion"] = "logic differs from the invariant " \
                                      "the test asserts; fix the function"
        if cause["symbol"] and code:
            sites = self.trace_dependencies(cause["symbol"], code)
            if sites:
                cause["location"] = f"first use at line {sites[0]['line']}"
        return cause

    def verify_logic(self, logic_description: str, code: str) -> dict:
        d = (logic_description or "").lower()
        facts = set()
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.If):
                    facts.add("branch")
                elif isinstance(node, ast.For) or isinstance(node, ast.While):
                    facts.add("loop")
                elif isinstance(node, ast.Try):
                    facts.add("try/except")
                elif isinstance(node, (ast.FunctionDef,)):
                    facts.add("function " + node.name)
                elif isinstance(node, ast.Return):
                    facts.add("return")
        except SyntaxError:
            return {"matches": False,
                    "discrepancies": ["code does not parse"]}
        want = []
        for w, f in (("if", "branch"), ("loop", "loop"), ("for", "loop"),
                     ("try", "try/except"), ("except", "try/except"),
                     ("return", "return")):
            if w in d:
                want.append(f)
        missing = [f for f in want if f not in facts]
        return {"matches": not missing,
                "discrepancies": ([f"described '{m}' absent in code"
                                   for m in missing])}

    def suggest_variables(self, task: str, existing_code: str) -> list[dict]:
        t = (task or "").lower()
        out = []
        seen = set()
        for m in re.finditer(r"\b([a-z_][a-z0-9_]{2,})\b\s*(?:=|:=)",
                             existing_code or ""):
            seen.add(m.group(1))
        pats = [("count", "counter", "int", "0", "tracks repetitions"),
                ("seen", "seen", "set", "set()", "dedupe membership"),
                ("cache", "cache", "dict", "{}", "memoized fast path"),
                ("flag", "found", "bool", "False", "search success flag"),
                ("state", "state", "dict", "{}", "explicit state machine"),
                ("total", "total", "int", "0", "accumulator"),
                ("result", "result", "list", "[]", "output collector"),
                ("index", "i", "int", "0", "cursor position")]
        for key, name, ty, init, why in pats:
            if key in t and name not in seen:
                out.append({"name": name, "type": ty, "initial_value": init,
                            "purpose": why})
        if not out:
            fns = re.findall(r"def (\w+)", existing_code or "")
            out.append({"name": "result", "type": "list",
                        "initial_value": "[]",
                        "purpose": f"collect output for {fns[0] if fns else 'the task'}()"})
        return out[:3]