
from __future__ import annotations

import json
import re
import time
from pathlib import Path

EXO = Path("C:/Projects/HybridLLM/exocortex")

_PATTERNS = [
    (r"NameError: name '(\w+)' is not defined", "NameError:*not defined",
     ["missing_import", "typo_in_variable", "scope_issue"]),
    (r"NameError", "NameError:*", ["missing_import", "typo_in_variable"]),
    (r"SyntaxError", "SyntaxError:*", ["unbalanced_brackets",
                                       "bad_indentation", "template_scribble"]),
    (r"IndentationError", "IndentationError:*", ["bad_indentation"]),
    (r"TypeError", "TypeError:*", ["wrong_arg_count", "type_mismatch"]),
    (r"ValueError", "ValueError:*", ["bad_parse", "empty_input"]),
    (r"KeyError", "KeyError:*", ["missing_dict_key"]),
    (r"IndexError", "IndexError:*", ["off_by_one"]),
    (r"ImportError|ModuleNotFoundError", "ImportError:*", ["missing_import"]),
    (r"ZeroDivisionError", "ZeroDivisionError:*", ["missing_guard"]),
    (r"AssertionError", "AssertionError:*", ["wrong_logic"]),
    (r"RecursionError", "RecursionError:*", ["missing_base_case"]),
    (r"AttributeError", "AttributeError:*", ["wrong_method", "none_receiver"]),
]

_PRIOR_FIXES = {
    "NameError:*not defined": ["ADD_IMPORT", "REPLACE_NAME"],
    "NameError:*": ["ADD_IMPORT", "REPLACE_NAME"],
    "SyntaxError:*": ["REPLACE_RETURN", "WRAP_TRY_EXCEPT"],
    "IndentationError:*": ["REPLACE_RETURN"],
    "TypeError:*": ["INJECT_ARGUMENT", "REPLACE_CONST"],
    "ValueError:*": ["WRAP_TRY_EXCEPT", "REPLACE_CONST"],
    "KeyError:*": ["REPLACE_CONST", "WRAP_TRY_EXCEPT"],
    "IndexError:*": ["REPLACE_CONST"],
    "ImportError:*": ["ADD_IMPORT"],
    "ZeroDivisionError:*": ["WRAP_TRY_EXCEPT"],
    "AssertionError:*": ["REPLACE_RETURN"],
    "RecursionError:*": ["REPLACE_RETURN"],
    "AttributeError:*": ["REPLACE_NAME"],
}

class ErrorExpertise:
    def __init__(self, path: str | Path = EXO / "error_knowledge.json"):
        self.path = Path(path)
        self.kb: dict = json.loads(self.path.read_text(encoding="utf-8")) \
            if self.path.exists() else {}
        self.applied: list[tuple[str, str]] = []

    def save(self):
        self.path.write_text(json.dumps(self.kb, indent=0), encoding="utf-8")

    def signature(self, error_text: str) -> str | None:
        t = str(error_text or "")
        for rx, sig, _causes in _PATTERNS:
            if re.search(rx, t):
                return sig
        return None

    def observe_error(self, error_text: str) -> str | None:
        sig = self.signature(error_text)
        if not sig:
            return None
        e = self.kb.setdefault(sig, {
            "error_signature": sig,
            "root_causes": next((c for r, s, c in _PATTERNS if s == sig), []),
            "fix_procedures": [{"action": a, "confidence": 0.4}
                               for a in _PRIOR_FIXES.get(sig, [])],
            "occurrence_count": 0, "fix_success_rate": 0.0,
            "_tries": 0, "_ok": 0})
        e["occurrence_count"] += 1
        self.save()
        return sig

    def suggest(self, sig: str) -> str | None:
        """Highest-confidence known fix (equal confidences break by order
        tried - experience, not convention, will separate them)."""
        e = self.kb.get(sig)
        if not e:
            return None
        fixes = sorted(e["fix_procedures"], key=lambda f: -f["confidence"])
        tried = {a for s, a in self.applied if s == sig}
        for f in fixes:
            if f["action"] not in tried:
                self.applied.append((sig, f["action"]))
                return f["action"]
        return "REWRITE_FROM_CONTEXT"

    def report(self, sig: str, action: str, fixed: bool):
        e = self.kb.get(sig)
        if not e:
            return
        e["_tries"] += 1
        f = next((x for x in e["fix_procedures"] if x["action"] == action),
                 None)
        if f is None and action != "REWRITE_FROM_CONTEXT":
            f = {"action": action, "confidence": 0.0}
            e["fix_procedures"].append(f)
        if fixed:
            e["_ok"] += 1
            if f:
                f["confidence"] = round(min(0.98, f["confidence"] * 0.8 + 0.3), 3)
        elif f:
            f["confidence"] = round(max(0.02, f["confidence"] * 0.8), 3)
        e["fix_success_rate"] = round(e["_ok"] / max(e["_tries"], 1), 3)
        self.applied = [(s, a) for s, a in self.applied if s != sig]
        self.save()

    def stats(self) -> dict:
        return {"signatures": len(self.kb),
                "total_errors": sum(e["occurrence_count"]
                                    for e in self.kb.values()),
                "fix_rate": round(sum(e["_ok"] for e in self.kb.values())
                                  / max(sum(e["_tries"] for e in self.kb.values()), 1), 3)}