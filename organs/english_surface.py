
from __future__ import annotations

import json
import re
from pathlib import Path

TEMPLATES = {
    "command":        "Run: {command}",
    "command_result": "Command `{command}` exited {code}: {output}",
    "read":           "File {path} contains: {snippet}",
    "write":          "Patch file {path} with {change}",
    "missing_dep":    "Missing dependency: {package}. Run: {command}",
    "cause":          "The likely cause is {cause}.",
    "test_fail":      "The test failed because {reason}.",
    "test_pass":      "All checks passed: {detail}",
    "concept":        "Related concepts: {concepts}",
    "relation":       "{src} relates to {dst} (score {score}).",
    "procedure":      "Reusing stored procedure {signature} ({confidence:.0%} confidence).",
    "stored":         "Stored procedure {signature} for reuse.",
    "submit_ok":      "Task complete: {result}",
    "submit_fail":    "Submission rejected: {reason}",
    "need_user":      "I need clarification: {question}",
}

class EnglishSurfaceOrgan:
    def __init__(self, templates: dict[str, str] | None = None):
        self.templates = dict(TEMPLATES)
        if templates:
            self.templates.update(templates)

    def render(self, kind: str, **slots) -> str:
        tpl = self.templates.get(kind)
        if tpl is None:
            return f"[{kind}] " + " ".join(f"{k}={v}" for k, v in slots.items())
        try:
            return tpl.format(**slots)
        except KeyError:
            return re.sub(r"\{[^}]+\}", "…", tpl)

    def intent_words(self, text: str) -> list[str]:
        return [w for w in re.findall(r"[a-z0-9_]+", str(text).lower())
                if len(w) > 2][:12]

    def summarize_result(self, action_name: str, out: dict) -> str:
        """Verified organ outcome -> one English line (untrusted content is
        quoted, never interpreted)."""
        if not out.get("ok", False):
            return self.render("cause", cause=str(out.get("error", "organ refused"))[:90])
        if action_name == "EXECUTE_TERMINAL":
            return self.render("command_result",
                               command=str(out.get("query", ""))[:80],
                               code=out.get("returncode", 0),
                               output=str(out.get("output", ""))[:120])
        if action_name == "READ_FILE":
            return self.render("read", path=out.get("path", "?"),
                               snippet=str(out.get("content", ""))[:100])
        if action_name == "WRITE_FILE":
            return self.render("write", path=out.get("path", "?"),
                               change=f"{out.get('n_chars', 0)} chars")
        if action_name == "EMBED_SEARCH":
            return self.render("concept", concepts=", ".join(
                t.strip() for t in out.get("tokens", [])[:6]))
        if action_name == "RELATION_TRAVERSE":
            return self.render("relation", **{k: out[k] for k in
                                              ("src", "dst", "score") if k in out}
                               or {"src": "?", "dst": "?", "score": 0})
        if action_name == "RECALL_PROCEDURE":
            return self.render("procedure", signature=out.get("signature", "?"),
                               confidence=float(out.get("confidence", 0)))
        if action_name == "STORE_PROCEDURE":
            return self.render("stored", signature=out.get("signature", "?"))
        if action_name == "SUBMIT_RESULT":
            return self.render("submit_ok" if out.get("success") else "submit_fail",
                               result=str(out.get("submitted", ""))[:120],
                               reason=str(out.get("error", "verifier rejected")))
        return f"{action_name}: ok"