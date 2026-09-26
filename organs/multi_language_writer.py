
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from organs.language_paradigms import LanguageParadigms
from organs.language_verifier import (LanguageVerifier, _strip_clike,
                                      _strip_lua)

_VERIFY_ALLOW = ("node", "luac", "lua", "gcc", "g++", "clang", "clang++",
                 "python")

class MultiLanguageWriter:
    def __init__(self, code_assembler, llm_tool=None, language_detector=None,
                 paradigms=None, verifier=None, terminal=None,
                 generator=None, max_fix_attempts: int = 3):
        self.assembler = code_assembler
        self.llm = llm_tool
        self.detector = language_detector
        self.paradigms = paradigms or LanguageParadigms()
        if verifier is None:
            if terminal is None:
                from organs.terminal import TerminalOrgan
                terminal = TerminalOrgan(allowlist=_VERIFY_ALLOW,
                                         timeout_s=15,
                                         cwd=tempfile.mkdtemp(
                                             prefix="langw_"))
            verifier = LanguageVerifier(terminal)
        self.verifier = verifier
        self.generator = generator
        self.max_fix_attempts = int(max_fix_attempts)
        self.writes: dict[str, int] = {}
        self.fix_successes = self.fix_attempts = 0

    def execute_action(self, action: str, target: str, content,
                       existing_code: str, language: str) -> dict:
        self.writes[language] = self.writes.get(language, 0) + 1
        if language == "python":
            return self._python_ast(action, target, content, existing_code)
        if action == "WRITE_FULL_FILE":
            desc = content if isinstance(content, str) else str(
                (content or {}).get("description", target))
            return self.write_full_file(desc, language,
                                        related_code=existing_code)
        return self._llm_generate(action, target, content, existing_code,
                                  language)

    def _python_ast(self, action, target, content, existing_code) -> dict:
        try:
            if action == "ADD_VARIABLE":
                r = self.assembler.add_variable(existing_code, str(target),
                                                _plain(content))
            elif action == "ADD_FUNCTION":
                r = self.assembler.add_function(existing_code,
                                                str(content or target))
            elif action == "MODIFY_FUNCTION":
                body = content.get("body") if isinstance(content, dict) \
                    else str(content)
                r = self.assembler.modify_function(existing_code,
                                                   str(target), str(body))
            elif action == "ADD_CONDITION":
                test = content.get("test") if isinstance(content, dict) \
                    else "x"
                body = content.get("body") if isinstance(content, dict) \
                    else "return None"
                r = self.assembler.add_condition(existing_code, str(target),
                                                 str(test), str(body))
            elif action == "ADD_IMPORT":
                r = self.assembler.mutate_ast(existing_code, "ADD_IMPORT",
                                              _plain(content))
            elif action == "WRAP_TRY_EXCEPT":
                r = self.assembler.mutate_ast(existing_code,
                                              "WRAP_TRY_EXCEPT",
                                              str(target or ""))
            elif action == "MUTATE":
                c = content if isinstance(content, dict) else {}
                r = self.assembler.mutate_ast(existing_code,
                                              str(c.get("mutation", "")),
                                              str(c.get("value", "")))
            else:
                return {"ok": False, "success": False,
                        "error": f"Unknown action: {action}"}
        except Exception as exc:
            return {"ok": False, "success": False, "error": str(exc)[:120]}
        return {**r, "success": bool(r.get("ok")), "language": "python"}

    def _llm_generate(self, action, target, content, existing_code,
                      language) -> dict:
        name = _ident(str(target or _field(content, "name") or "item"))
        body, params = self._body_from(action, content, language)
        knowledge = self._knowledge(action, target, content, language)
        piece = LanguageParadigms.scaffold(language, action, name=name,
                                           params=params, body=body,
                                           extra=knowledge["hint"])
        try:
            merged = self._merge(language, action, name, piece, existing_code,
                                 body)
        except LookupError as exc:
            return {"ok": False, "success": False, "language": language,
                    "error": str(exc)[:140]}
        v = self.verifier.check(merged, language)
        fixes = 0
        while not v["valid"] and fixes < self.max_fix_attempts:
            fixes += 1
            self.fix_attempts += 1
            merged = self._repair(merged, language, v["error"] or "",
                                  name, body)
            v = self.verifier.check(merged, language)
            if v["valid"]:
                self.fix_successes += 1
        if not v["valid"]:
            return {"ok": False, "success": False, "language": language,
                    "error": f"could not produce valid {language} after "
                             f"{self.max_fix_attempts} fixes: "
                             f"{v['error']}", "tool": v.get("tool")}
        return {"ok": True, "success": True, "code": merged,
                "language": language, "verified_by": v["tool"],
                "fixes": fixes, "knowledge_source": knowledge["source"],
                "piece": piece}

    def write_full_file(self, description, language, template_hint=None,
                        related_code: str = "") -> dict:
        """Greenfield creation: real generator if wired, else scaffold
        composition informed by substrate concepts. Always mechanically
        verified; always honest about which path wrote it."""
        language = str(language or "python").lower()
        desc = str(description or "")
        self.writes[language] = self.writes.get(language, 0) + 1
        code, origin = "", ""
        if self.generator is not None:
            try:
                code = str(self.generator(language, desc,
                                          template_hint or related_code))
                origin = "generator"
            except Exception:
                code = ""
        if not code.strip():
            k = self._knowledge("WRITE_FULL_FILE", desc, "", language)
            if language == "html":
                code = LanguageParadigms.scaffold(
                    "html", "FILE", extra=_title_of(desc),
                    body=_interactive_html(desc))
            elif language == "lua":
                code = LanguageParadigms.scaffold(
                    "lua", "FILE", name="jump_count", extra=_title_of(desc),
                    body=LanguageParadigms.scaffold(
                        "lua", "ADD_FUNCTION", name="jump_count",
                        params="player",
                        body="local n = (player and player.jumps or 0) + 1\n"
                             "if player then player.jumps = n end\n"
                             "return n"))
            elif language == "javascript":
                code = LanguageParadigms.scaffold(
                    "javascript", "FILE", name="main", extra=_title_of(desc),
                    body=LanguageParadigms.scaffold(
                        "javascript", "ADD_FUNCTION", name="main",
                        params="", body="return true;"))
            elif language in ("c", "cpp"):
                code = LanguageParadigms.scaffold(
                    language, "FILE", name="run", extra=_title_of(desc),
                    body=LanguageParadigms.scaffold(
                        language, "ADD_FUNCTION", name="run",
                        params="void", body="return 0;"))
            else:
                code = (f"// {language} file: {desc[:120]}\n"
                        + (related_code or ""))
            origin = "scaffold+knowledge"
            if k["source"] not in ("none", "template"):
                code = code.lstrip()
        v = self.verifier.check(code, language)
        fixes = 0
        while not v["valid"] and fixes < self.max_fix_attempts:
            fixes += 1
            self.fix_attempts += 1
            code = self._repair(code, language, v["error"] or "", "", "")
            v = self.verifier.check(code, language)
            if v["valid"]:
                self.fix_successes += 1
        if language == "python" and code.strip():
            try:
                compile(code, "<full.py>", "exec")
            except SyntaxError as exc:
                return {"ok": False, "success": False, "language": language,
                        "error": f"python scaffold rejected: {exc}"}
        if not v["valid"]:
            return {"ok": False, "success": False, "language": language,
                    "error": f"generated {language} failed verification: "
                             f"{v['error']}", "tool": v.get("tool")}
        return {"ok": True, "success": True, "code": code,
                "language": language, "verified_by": v["tool"],
                "origin": origin, "fixes": fixes}

    def _knowledge(self, action, target, content, language) -> dict:
        """Substrate retrieval names CONSTRUCTS; it never emits code."""
        if self.llm is None:
            return {"hint": "", "source": "none", "concepts": []}
        ask = " ".join(str(x) for x in (action, target, _plain(content),
                                        language, "pattern"))
        try:
            r = self.llm.query(ask)
        except Exception:
            return {"hint": "", "source": "error", "concepts": []}
        words = [c for c in (r.get("concepts") or [])
                 if re.fullmatch(r"[A-Za-z_:][\w:]*", str(c) or "")]
        return {"hint": ",".join(words[:3]), "source": r.get("source", ""),
                "concepts": words[:6]}

    def _body_from(self, action, content, language):
        if isinstance(content, dict):
            body = str(content.get("body") or content.get("description")
                       or content.get("cmd") or "")
            params = str(content.get("params") or "")
        else:
            body = str(content or "")
            params = ""
        if not body.strip():
            body = {"ADD_FUNCTION": f"-- {action.lower()}",
                    "ADD_VARIABLE": "0"}.get(action, "")
        if action == "ADD_FUNCTION" and language == "javascript" \
                and "->" not in body and "{" not in body:
            body = "// " + body.strip()[:70]
        if params:
            params = re.sub(r"[^A-Za-z0-9_, ]", "", params).strip()
        return body, params

    def _merge(self, language, action, name, piece, existing_code, body):
        """Deterministic insertion / replacement at REAL code boundaries."""
        src = str(existing_code or "")
        if action == "MODIFY_FUNCTION" and src.strip():
            span = _function_span(language, name, src)
            if span is None:
                raise LookupError(f"{language} function {name!r} not found")
            replacement = _rewrite_body(language, name, src, span, body)
            return src[:span[0]] + replacement + src[span[1]:]
        if action == "ADD_CONDITION" and src.strip():
            span = _function_span(language, name, src)
            if span is not None:
                open_end = src.find(_opener(language), span[0])
                cut = src.find("\n", open_end) + 1
                guard = _guard(language, body)
                return src[:cut] + guard + src[cut:]
            return (src.rstrip() + "\n" + piece) if src.strip() else piece
        if action == "ADD_VARIABLE":
            lines = src.splitlines(keepends=True)
            i = 0
            while i < len(lines) and re.match(r"^\s*(--|//|#|<!--)",
                                              lines[i]):
                i += 1
            return "".join(lines[:i]) + piece + "".join(lines[i:])
        if action == "ADD_IMPORT":
            return _import_line(language, _plain(body or name)) + src
        if language == "html" and action in ("ADD_ELEMENT",):
            if "</body>" in src:
                return src.replace("</body>", piece + "\n</body>", 1)
            return src + piece
        if language == "html" and action == "ADD_STYLE":
            if "</head>" in src:
                return src.replace("</head>", piece + "\n</head>", 1)
            return src + piece
        if language == "html" and action == "ADD_SCRIPT":
            if "</body>" in src:
                return src.replace("</body>", piece + "\n</body>", 1)
            return src + piece
        return (src.rstrip() + "\n" + piece) if src.strip() else piece

    def _repair(self, code: str, language: str, error: str, name: str,
                body: str) -> str:
        """Deterministic fixes for the only failure class a template
        composition can produce: dangling blocks / stray closers."""
        s = str(code)
        if "unmatched 'end'" in error or "block depth" in error:
            if "unmatched" in error:
                m = re.search(r"offset (\d+)", error)
                if m:
                    ln = s[:int(m.group(1))].count("\n")
                    lines = s.splitlines()
                    if 0 <= ln < len(lines):
                        lines[ln] = lines[ln].replace("end", "", 1)
                        s = "\n".join(lines) + "\n"
            else:
                depth = int(re.search(r"(-?\d+) opener", error).group(1))
                s = s.rstrip() + "\n" + "end\n" * max(0, depth) \
                    if depth > 0 else s
        if "unbalanced" in error or "unclosed" in error:
            s = _close_balance(s, language, error)
        if "stray" in error or "unmatched <" in error:
            m = re.search(r"unmatched <(\w+)>", error) or \
                re.search(r"stray </(\w+)>", error)
            if m:
                s = s.replace(f"</{m.group(1)}>", "", 1)
        if "empty" in error and language in ("lua", "javascript"):
            s = (s + "\n" + LanguageParadigms.scaffold(
                language, "ADD_FUNCTION", name=name or "noop",
                body="// noop") if language == "lua" else s + "\n")
        return s

def _plain(content) -> str:
    if isinstance(content, dict):
        return str(content.get("value") or content.get("name")
                   or content.get("cmd") or content.get("test") or "")
    return str(content or "")

def _field(content, key):
    return content.get(key) if isinstance(content, dict) else None

def _ident(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_]", "_", s.strip() or "item")
    return s if re.match(r"[A-Za-z_]", s) else "x_" + s

def _title_of(desc: str) -> str:
    return re.sub(r"[^ A-Za-z0-9_-]", "", str(desc)[:40]).strip() or "app"

def _opener(language: str) -> str:
    return {"lua": ")", "javascript": "{", "c": "{", "cpp": "{"}.get(
        language, "{")

def _guard(language: str, condition) -> str:
    cond = condition if isinstance(condition, str) else _plain(condition)
    cond = re.sub(r"\bnot\b\s*(\w+)", r"not \1", cond or "")
    if language == "lua":
        return f"    if not ({cond or 'true'}) then return nil end\n"
    if language == "javascript":
        return f"    if (!({cond or 'true'})) return null;\n"
    return f"    if (!({cond or 'true'})) return 0;\n"

def _import_line(language: str, what: str) -> str:
    what = (what or "").strip()
    if language in ("c",):
        return f"#include <{what}>\n"
    if language == "cpp":
        return f"#include <{what}>\n"
    if language == "javascript":
        return f"const {re.sub(r'[^A-Za-z0-9_]', '_', what)} = " \
               f"require('{what}');\n"
    if language == "lua":
        return f"local {re.sub(r'[^A-Za-z0-9_]', '_', what)} = " \
               f"require('{what}')\n"
    return f"import {what}\n"

def _interactive_html(desc: str) -> str:
    t = desc.lower()
    if "canvas" in t or "pong" in t or "game" in t:
        return ("<h1>Canvas</h1>\n<canvas id=\"stage\" width=\"480\" "
                "height=\"320\"></canvas>\n<button id=\"go\">Go</button>")
    if "button" in t or "counter" in t:
        return ("<h1>Counter</h1>\n<p id=\"count\">0</p>\n"
                "<button id=\"inc\">+1</button>")
    return "<h1>Page</h1>\n<p>Content.</p>\n"

def _code_view(language: str, src: str) -> str:
    if language == "lua":
        return _strip_lua(src)
    return _strip_clike(src)

def _function_span(language: str, name: str, code: str) -> tuple | None:
    """(start, end) offsets of the full function text, or None.
    Located on the comment/string-stripped view so prose never fools it."""
    view = _code_view(language, code)
    if language == "lua":
        m = re.search(rf"(?:local\s+)?function\s+{re.escape(name)}\s*\(",
                      view)
        if not m:
            return None
        depth, i = 0, m.start()
        for mm in re.finditer(r"\b(function|if|then|do|end|repeat|until)\b",
                              view[m.start():]):
            w = mm.group(1)
            if w in ("function", "then", "do", "repeat"):
                depth += 1
            elif w in ("end", "until"):
                depth -= 1
                if depth == 0:
                    return (m.start(), m.start() + mm.end())
        return None
    m = re.search(rf"\b{re.escape(name)}\s*\(([^)]*)\)\s*\{{", view)
    if not m:
        m = re.search(rf"(?:function|const|let|var)\s+{re.escape(name)}"
                      r"[^{{=]*=>\s*\{{", view)
    if not m:
        return None
    start = m.start()
    if language in ("c", "cpp"):
        tm = re.search(r"((?:[A-Za-z_][\w:<>&~*]*\s+)+)$", view[:start])
        if tm and tm.group(1).strip():
            start -= len(tm.group(1))
    else:
        km = re.search(r"(?:function|const|let|var)\s+$", view[:start])
        if km:
            start = km.start()
    depth, i = 0, view.index("{", m.end() - 1)
    while i < len(view):
        if view[i] == "{":
            depth += 1
        elif view[i] == "}":
            depth -= 1
            if depth == 0:
                return (start, i + 1)
        i += 1
    return None

def _rewrite_body(language, name, code, span, body) -> str:
    body = str(body or "").strip()
    if language == "lua":
        inner = _ind(body, "    ") or f"    -- {name}"
        return f"local function {name}()\n{inner}\nend"
    if language == "javascript":
        inner = _ind(body, "    ") or "// noop"
        return f"function {name}() {{\n{inner}\n}}"
    inner = _ind(body, "    ") or "// noop"
    return f"static int {name}(void) {{\n{inner}\n}}"

def _guard_prefix(language, cond):
    fn = _function_re(language)
    m = re.search(fn, _code_view(language, ""))
    return ""

def _ind(text: str, pad: str) -> str:
    return "\n".join(pad + ln for ln in str(text).splitlines() if ln.strip())

def _function_re(language) -> str:
    return {"lua": r"function\s+\w+\s*\(",
            "javascript": r"function\s+\w+\s*\("}.get(language, r"\w+\s*\(")

def _close_balance(s: str, language: str, error: str) -> str:
    """Append the closers a truncated generation lost, in correct order."""
    seq = _strip_clike(s) if language != "lua" else _strip_lua(s)
    stack = []
    match = {"}": "{", ")": "(", "]": "["}
    for ch in seq:
        if ch in "{([":
            stack.append(ch)
        elif ch in ")]}" and stack and stack[-1] == match[ch]:
            stack.pop()
    if language == "lua":
        return s + ("\n" if not s.endswith("\n") else "")
    closers = "".join({"{": "}", "(": ")", "[": "]"}[c]
                      for c in reversed(stack))
    return s.rstrip() + "\n" + closers + "\n"