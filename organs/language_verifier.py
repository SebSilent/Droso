
from __future__ import annotations

import re
import shutil
import tempfile
from html.parser import HTMLParser
from pathlib import Path

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
         "link", "meta", "param", "source", "track", "wbr", "!doctype"}

class LanguageVerifier:
    def __init__(self, terminal_organ=None, workdir: str | Path | None = None):
        self.terminal = terminal_organ
        self.workdir = Path(workdir or tempfile.mkdtemp(prefix="langverify_"))
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.checks: dict[str, int] = {}
        self.have = {"node": shutil.which("node"),
                     "luac": shutil.which("luac") or shutil.which("lua"),
                     "gcc": shutil.which("gcc"), "gxx": shutil.which("g++")}

    def check(self, code: str, language: str) -> dict:
        language = str(language or "").lower()
        code = str(code or "")
        self.checks[language] = self.checks.get(language, 0) + 1
        fn = {"python": self._check_python, "lua": self._check_lua,
              "javascript": self._check_javascript, "js": self._check_javascript,
              "html": self._check_html, "htm": self._check_html,
              "css": self._check_html, "c": self._check_c,
              "h": self._check_c, "cpp": self._check_cpp,
              "cc": self._check_cpp}.get(language, self._check_basic)
        r = fn(code)
        r.setdefault("language", language)
        return r

    def _check_python(self, code: str) -> dict:
        try:
            compile(code, "<verify.py>", "exec")
            return {"valid": True, "error": None, "tool": "python.compile"}
        except (SyntaxError, ValueError) as exc:
            return {"valid": False, "error": str(exc),
                    "tool": "python.compile"}

    def _check_lua(self, code: str) -> dict:
        src = code.strip()
        if not src:
            return {"valid": False, "error": "empty lua source",
                    "tool": "lua.block-stack"}
        if self.have["luac"] and self.terminal is not None:
            p = self._write_temp(code, ".lua")
            r = self.terminal.run(f'luac -p "{p}"')
            if r.get("ok"):
                return {"valid": True, "error": None, "tool": "luac -p"}
            if r.get("error") and "not in allowlist" not in str(r["error"]):
                return {"valid": False, "error": str(
                    r.get("output") or r.get("error"))[:200],
                    "tool": "luac -p"}
        return self._lua_structural(code)

    def _lua_structural(self, code: str) -> dict:
        s = _strip_lua(code)
        depth, i, n = 0, 0, len(s)
        for m in re.finditer(r"\b(function|if|elseif|then|else|end|do|"
                             r"repeat|until|for|while)\b", s):
            w = m.group(1)
            if w in ("function", "do", "then"):
                depth += 1
            elif w == "repeat":
                depth += 1
            elif w in ("end", "until"):
                depth -= 1
                if depth < 0:
                    return {"valid": False,
                            "error": f"unmatched '{w}' at offset {m.start()}",
                            "tool": "lua.block-stack"}
        if depth != 0:
            return {"valid": False,
                    "error": f"block depth unresolved: {depth} opener(s) "
                             "unclosed", "tool": "lua.block-stack"}
        bad = re.search(r"\bdef\b|\"\"\"|=>|\blet\b|\bconst\b|\bclass\b"
                        r"|\blet\s|\belif\b", s)
        if bad:
            return {"valid": False,
                    "error": "non-lua syntax token: " + bad.group(0).strip(),
                    "tool": "lua.block-stack"}
        return {"valid": True, "error": None, "tool": "lua.block-stack"}

    def _check_javascript(self, code: str) -> dict:
        src = str(code).strip()
        if not src:
            return {"valid": False, "error": "empty js source",
                    "tool": "js.balance"}
        if self.have["node"] and self.terminal is not None:
            p = self._write_temp(code, ".js")
            r = self.terminal.run(f"node --check \"{p}\"")
            if r.get("ok"):
                return {"valid": True, "error": None, "tool": "node --check"}
            out = str(r.get("output") or r.get("error") or "")
            if "not in allowlist" in out:
                pass
            else:
                return {"valid": False, "error": out[:200],
                        "tool": "node --check"}
        return self._balance(code, ("{", "}", "(", ")", "[", "]"),
                             ("//", "/*"), ("'", '"', "`"), "js.balance")

    def _check_html(self, code: str) -> dict:
        class _P(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.stack: list[str] = []
                self.err = ""

            def handle_starttag(self, tag, attrs):
                if tag not in _VOID:
                    self.stack.append(tag)

            def handle_endtag(self, tag):
                if tag in _VOID:
                    return
                if not self.stack:
                    self.err = self.err or f"stray </{tag}>"
                    return
                if self.stack[-1] == tag:
                    self.stack.pop()
                elif tag in self.stack:
                    while self.stack and self.stack[-1] != tag:
                        self.stack.pop()
                    self.stack and self.stack.pop()
                else:
                    self.err = self.err or f"unmatched </{tag}>"

        p = _P()
        try:
            p.feed(str(code))
            p.close()
        except Exception as exc:
            return {"valid": False, "error": f"html parse: {exc}"[:160],
                    "tool": "html.parser"}
        if p.err:
            return {"valid": False, "error": p.err[:160],
                    "tool": "html.parser"}
        if p.stack:
            return {"valid": False,
                    "error": "unclosed: " + ", ".join(p.stack[:4]),
                    "tool": "html.parser"}
        if not str(code).strip():
            return {"valid": False, "error": "empty html",
                    "tool": "html.parser"}
        return {"valid": True, "error": None, "tool": "html.parser"}

    def _check_c(self, code: str) -> dict:
        return self._c_like(code, "gcc")

    def _check_cpp(self, code: str) -> dict:
        return self._c_like(code, "gxx")

    def _c_like(self, code: str, which: str) -> dict:
        exe = self.have[which]
        ext = ".c" if which == "gcc" else ".cpp"
        if exe and self.terminal is not None:
            p = self._write_temp(code, ext)
            std = "" if which == "gcc" else " -std=c++17"
            r = self.terminal.run(f'{Path(exe).name} -fsyntax-only{std} "{p}"')
            if r.get("ok"):
                return {"valid": True, "error": None,
                        "tool": Path(exe).name + " -fsyntax-only"}
            out = str(r.get("output") or r.get("error") or "")
            if "not in allowlist" not in out and "invalid env" not in out:
                return {"valid": False, "error": out[:220],
                        "tool": Path(exe).name + " -fsyntax-only"}
        return self._balance(code, ("{", "}", "(", ")", "[", "]"),
                             ("//", "/*"), ('"', "'"),
                             "c.balance" if which == "gcc" else "cpp.balance")

    def _check_basic(self, code: str) -> dict:
        src = str(code).strip()
        if len(src) < 10:
            return {"valid": False, "error": "code too short to be real",
                    "tool": "basic"}
        return self._balance(code, ("{", "}", "(", ")", "[", "]"),
                             ("//",), ('"', "'"), "basic")

    def _balance(self, code: str, pairs, line_comments, quotes,
                 tool: str) -> dict:
        s = _strip_clike(code, line_comments, quotes)
        stack: list[tuple[str, int]] = []
        openers, closers = {}, {}
        for o, c in zip(pairs[0::2], pairs[1::2]):
            openers[o] = c
            closers[c] = o
        for i, ch in enumerate(s):
            if ch in openers:
                stack.append((ch, i))
            elif ch in closers:
                if not stack or stack[-1][0] != closers[ch]:
                    line = s[:i].count("\n") + 1
                    return {"valid": False,
                            "error": f"unbalanced '{ch}' near line {line}",
                            "tool": tool}
                stack.pop()
        if stack:
            line = s[:stack[-1][1]].count("\n") + 1
            return {"valid": False,
                    "error": f"unclosed '{stack[-1][0]}' opened near "
                             f"line {line}", "tool": tool}
        if not s.strip():
            return {"valid": False, "error": "nothing but comments",
                    "tool": tool}
        return {"valid": True, "error": None, "tool": tool}

    def _write_temp(self, code: str, ext: str) -> str:
        p = self.workdir / f"check_{len(self.checks)}{ext}"
        p.write_text(str(code), encoding="utf-8", newline="\n")
        return str(p).replace("\\", "/")

    def stats(self) -> dict:
        return {"checks": dict(self.checks), "tools": {
            k: bool(v) for k, v in self.have.items()}}

def _ws(chunk: str) -> str:
    """Length-preserving blank-out: offsets in the stripped view stay
    valid for slicing the RAW text (span locators depend on this)."""
    return re.sub(r"[^\n]", " ", chunk)

def _strip_lua(code: str) -> str:
    out, i, n = [], 0, len(code)
    while i < n:
        three = code[i:i + 3]
        if three == "--[":
            j = code.find("]]", i + 3)
            j = n if j < 0 else j + 2
            out.append(_ws(code[i:j]))
            i = j
            continue
        if code.startswith("--", i):
            j = code.find("\n", i)
            j = n if j < 0 else j
            out.append(_ws(code[i:j]))
            i = j
            continue
        if code[i] in "\"'":
            q = code[i]
            k = i + 1
            while k < n and code[k] != q:
                k += 2 if code[k] == "\\" else 1
            k = min(k + 1, n)
            out.append(_ws(code[i:k]))
            i = k
            continue
        if code.startswith("[[", i):
            j = code.find("]]", i + 2)
            j = n if j < 0 else j + 2
            out.append(_ws(code[i:j]))
            i = j
            continue
        out.append(code[i])
        i += 1
    return "".join(out)

def _strip_clike(code: str, line_comments=("//",), quotes=('"', "'")) -> str:
    out, i, n = [], 0, len(code)
    while i < n:
        ch = code[i]
        matched = False
        for lc in line_comments:
            if code.startswith(lc, i):
                j = code.find("\n", i)
                j = n if j < 0 else j
                out.append(_ws(code[i:j]))
                i = j
                matched = True
                break
        if matched:
            continue
        if code.startswith("/*", i):
            j = code.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(_ws(code[i:j]))
            i = j
            continue
        if ch in quotes:
            k = i + 1
            while k < n and code[k] != ch:
                k += 2 if code[k] == "\\" else 1
            k = min(k + 1, n)
            out.append(_ws(code[i:k]))
            i = k
            continue
        out.append(ch)
        i += 1
    return "".join(out)