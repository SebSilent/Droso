
from __future__ import annotations

import re
from pathlib import Path

class LanguageDetector:
    SIGNATURES = {
        "python": {
            "extensions": [".py", ".pyw"],
            "keywords": ["python", "pip", "django", "flask", "numpy",
                         "pandas", "def ", "import "],
            "platforms": ["python"],
        },
        "lua": {
            "extensions": [".lua", ".luau"],
            "keywords": ["lua", "roblox", "robloxstudio", "luau",
                         "coroutine", "metatable", "end", "then", "local"],
            "platforms": ["roblox", "love2d", "garrysmod"],
        },
        "javascript": {
            "extensions": [".js", ".jsx", ".ts", ".tsx", ".mjs"],
            "keywords": ["javascript", "typescript", "node", "react",
                         "vue", "dom", "addEventListener",
                         "event listener", "toggle", "onclick", "const ",
                         "=> {"],
            "platforms": ["browser", "node"],
        },
        "html": {
            "extensions": [".html", ".htm", ".css", ".svg"],
            "keywords": ["html", "css", "webpage", "website", "canvas",
                         "<div", "<button", "<style", "<!doctype"],
            "platforms": ["browser"],
        },
        "c": {
            "extensions": [".c", ".h"],
            "keywords": ["malloc", "pointer", "struct", "printf",
                         "char *", "#include"],
            "platforms": ["gcc", "clang"],
            "patterns": [r"\bc\b(?![+#])"],   # bare letter needs a fence
        },
        "cpp": {
            "extensions": [".cpp", ".hpp", ".cc", ".cxx"],
            "keywords": ["std::", "vector<", "template", "cout",
                         "unique_ptr", "class"],
            "platforms": [],
            "patterns": [r"c\+\+", r"\bcpp\b"],
        },
    }
    _CODE_MARKERS = {
        "python": [(r"^def \w+\(", 2.0), (r"^import |^from \w+ import", 1.5),
                   (r":\s*$", 0.3), (r"print\(", 0.5)],
        "lua": [(r"function \w+\s*\(", 1.2), (r"\blocal \w+ =", 2.0),
                 (r"\bend\b", 0.8), (r"\bthen\b", 1.0), (r"~=", 1.0),
                 (r"--[^\n]", 0.5)],
        "javascript": [(r"=>", 1.5), (r"\bconst \w+ =", 1.5),
                        (r"\bfunction \w*\s*\([^)]*\)\s*\{", 1.5),
                        (r"\bconsole\.log", 1.0), (r"[{};]", 0.2)],
        "html": [(r"<!doctype", 3.0), (r"<\w+[^>]*>", 1.0),
                  (r"</\w+>", 1.0), (r"<script", 0.5)],
        "c": [(r"#include <", 3.0), (r"\bint main\s*\(", 2.0),
              (r"\bprintf\s*\(", 1.5), (r"char \*", 1.0)],
        "cpp": [(r"#include <(iostream|vector|string)", 3.0),
                (r"\bstd::", 2.0), (r"\bcout <<", 2.0),
                (r"\btemplate\s*<", 2.0), (r"\bclass \w+", 1.0)],
    }

    def __init__(self, extra: dict | None = None):
        self.SIGNATURES = dict(self.SIGNATURES)
        for lang, sig in (extra or {}).items():
            cur = self.SIGNATURES.setdefault(
                lang, {"extensions": [], "keywords": [], "platforms": []})
            for k in ("extensions", "keywords", "platforms"):
                cur[k] = list(cur[k]) + list(sig.get(k, []))
        self.detects = 0

    def detect(self, task_description: str, file_paths=None,
               existing_code: str | None = None) -> dict:
        self.detects += 1
        task = str(task_description or "")
        for path in file_paths or []:
            ext = Path(str(path)).suffix.lower()
            for lang, sig in self.SIGNATURES.items():
                if ext in sig["extensions"]:
                    return {"language": lang, "confidence": 1.0,
                            "reason": f"file extension {ext}"}
        scores: dict[str, float] = {}
        reasons: dict[str, str] = {}
        low = task.lower()
        for lang, sig in self.SIGNATURES.items():
            s = sum(1.0 for kw in sig["keywords"] if kw.lower() in low)
            p = sum(2.0 for plat in sig["platforms"] if plat in low)
            p += sum(2.0 for pat in sig.get("patterns", [])
                     if re.search(pat, low))
            if s + p:
                scores[lang] = scores.get(lang, 0.0) + s + p
                reasons.setdefault(lang, "keyword/platform match")
        if existing_code:
            code_scores = self._code_scores(existing_code)
            for lang, v in code_scores.items():
                scores[lang] = scores.get(lang, 0.0) + v
                reasons.setdefault(lang, "code patterns")
        if scores:
            best = max(scores, key=lambda k: scores[k])
            total = sum(scores.values()) or 1.0
            share = scores[best] / total
            conf = round(min(0.98, 0.45 + 0.55 * share), 2) if best != \
                "python" or scores.get("python", 0) <= 1e-9 else \
                round(max(share, 0.5), 2)
            if reasons.get(best) == "code patterns" and share < 0.4:
                conf = max(conf, 0.6)
            return {"language": best, "confidence": conf,
                    "reason": f"{reasons.get(best, 'lexical')} "
                              f"(score {round(scores[best], 2)}/{round(total, 2)})"}
        return {"language": "python", "confidence": 0.3, "reason": "default"}

    def detect_from_file(self, file_path: str,
                         read=None) -> dict:
        p = Path(str(file_path))
        ext = p.suffix.lower()
        for lang, sig in self.SIGNATURES.items():
            if ext in sig["extensions"]:
                return {"language": lang, "confidence": 1.0,
                        "reason": f"file extension {ext}"}
        try:
            text = (read or (lambda q: Path(q).read_text(encoding="utf-8",
                                                          errors="replace")))(str(p))
        except OSError:
            return {"language": "python", "confidence": 0.2,
                    "reason": "unreadable file"}
        code = self._code_scores(text)
        if code:
            best = max(code, key=lambda k: code[k])
            return {"language": best, "confidence": 0.8,
                    "reason": "content patterns"}
        return {"language": "python", "confidence": 0.3,
                "reason": "default"}

    def _code_scores(self, code: str) -> dict:
        out = {}
        for lang, pats in self._CODE_MARKERS.items():
            s = 0.0
            for pat, w in pats:
                n = len(re.findall(pat, code, re.M))
                if n:
                    s += w * min(n, 4)
            if s:
                out[lang] = s
        return out