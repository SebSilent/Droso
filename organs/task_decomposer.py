from __future__ import annotations

import re

_REQ = re.compile(
    r"\b(must|should|shall|has to|need(s)? to|ensure|return|raise|handle|"
    r"support|print|write|create|read|parse|validate|avoid|never|only)\b",
    re.I)
_SPLIT = re.compile(r"(?:;|\b(?:and then|which should|such that|where)\b|"
                    r"\n\s*(?:[-*\u2022]|\d+[.)])\s+)")
_EXTERNAL = re.compile(
    r"\b(api|http|https|endpoint|json|yaml|toml|sqlite|socket|oauth|token|"
    r"protobuf|regex|cron|smtp|imap|websocket|graphql|openai|anthropic)\b",
    re.I)
_LOCAL = re.compile(
    r"\b(rename|reformat|reorder|count|sort|dedup|move|delete|file|function|"
    r"class|loop|variable|import|print|test|assert|docstring|comment)\b", re.I)

API_PIECE_RULES = (
    "Return ONLY the code or answer for this one specific piece.\n"
    "- No surrounding HTML, no imports unless necessary\n"
    "- No explanations, no preamble, no comments unless asked\n"
    "- Under 40 lines\n"
    "- If a signature or name is given, use it exactly\n"
    "- Do not run, invoke, or pretend to run anything; you are a text source")

class Decomposition:
    def __init__(self, task: str, parts: list[dict]):
        self.task = task
        self.parts = parts

    @property
    def oracle_parts(self):
        return [p for p in self.parts if p["needs_oracle"] is True]

    @property
    def local_parts(self):
        return [p for p in self.parts if p["needs_oracle"] is False]

    @property
    def unknown_parts(self):
        return [p for p in self.parts if p["needs_oracle"] is None]

    def questions(self) -> list[str]:
        return [p["question"] for p in self.oracle_parts]

    def api_queries(self) -> list[str]:
        """Token-minimal query per oracle part -- one piece each."""
        return [p.get("api_query") or p["question"] for p in self.oracle_parts]

    def batches(self, max_per_call: int = 3) -> list[dict]:
        """Group oracle questions so each call carries the shared context once.

        Returns [{"questions": [...], "prompt": str, "context": str}].
        """
        out = []
        chunk = self.oracle_parts[:max_per_call]
        rest = self.oracle_parts[max_per_call:]
        if chunk:
            out.append(self._mk(chunk))
        while rest:
            out.append(self._mk(rest[:max_per_call]))
            rest = rest[max_per_call:]
        return out

    @staticmethod
    def _mk(items) -> dict:
        ctx = ""
        for it in items:
            ctx = ctx or it.get("context", "")
        body = [it["question"] for it in items]
        if len(items) > 1:
            body = ["Answer each numbered question separately and briefly, "
                    "as `N: answer`.",
                    "\n".join(f"{i + 1}. {q}" for i, q in enumerate(body))]
        body.append(API_PIECE_RULES)
        return {"questions": [it["question"] for it in items],
                "api_queries": [it.get("api_query") or it["question"]
                                for it in items],
                "ids": [it["id"] for it in items],
                "prompt": "\n".join(body), "context": ctx}

    def summary(self) -> dict:
        return {"parts": len(self.parts), "needs_oracle": len(self.oracle_parts),
                "local": len(self.local_parts),
                "unknown": len(self.unknown_parts),
                "batches": len(self.batches())}

    def __len__(self):
        return len(self.parts)

class TaskDecomposer:
    def __init__(self, max_parts: int = 8, known_local=None,
                 known_external=None):
        self.max_parts = int(max_parts)
        self.known_local = set(w.lower() for w in (known_local or []))
        self.known_external = set(w.lower() for w in (known_external or []))

    def split_requirements(self, text: str) -> list[str]:
        """One string per requirement, order preserved."""
        text = re.sub(r"[ \t]+", " ", str(text or "").strip())
        if not text:
            return []
        chunks = [c.strip() for c in _SPLIT.split(text) if c and c.strip()]
        reqs = [c for c in chunks if _REQ.search(c)]
        if not reqs:
            reqs = chunks or [text]
        out, seen = [], set()
        for r in reqs:
            k = normalise_key(r)
            if k in seen:
                continue
            seen.add(k)
            out.append(r[:400])
            if len(out) >= self.max_parts:
                break
        return out

    def decompose(self, task: str, context: str = "",
                  files: list[str] | None = None) -> Decomposition:
        reqs = self.split_requirements(task)
        parts = []
        for i, r in enumerate(reqs):
            verdict, why = self.classify(r)
            parts.append({"id": f"q{i}", "requirement": r,
                          "question": self.as_question(r),
                          "api_query": self._build_api_query(r),
                          "needs_oracle": verdict, "rule": why,
                          "context": _pick_context(context, r),
                          "files": [f for f in (files or [])
                                    if _shares_word(f, r)]})
        return Decomposition(task, parts)

    def _build_api_query(self, sub_task, language: str | None = None,
                         max_lines: int = 40) -> str:
        """Build a MINIMAL query for one piece.

        BAD:  "Build me a complete tetris game in HTML"
        GOOD: "Write a JavaScript function that rotates a tetris piece. Grid is
               10x20, pieces are 2D arrays. Return only the function."

        Small queries are what make the cost guarantee hold: a piece is a few
        hundred tokens, a project is thousands, and the difference is paid by the
        connectome having done the decomposition instead of outsourcing it.
        """
        q = self.as_question(str(sub_task).strip())
        if language:
            q = f"({language}) {q}"
        rules = API_PIECE_RULES
        if max_lines != 40:
            rules = rules.replace("Under 40 lines",
                                  f"Under {int(max_lines)} lines")
        return f"{q}\n\n{rules}"

    def classify(self, req: str):
        """True = ask the oracle, False = solve locally, None = unknown."""
        low = req.lower()
        words = set(re.findall(r"[a-z_][a-z_0-9]+", low))
        hit_known = words & self.known_local
        if hit_known:
            return False, f"known to this agent: {sorted(hit_known)[:3]}"
        hit_ext = words & self.known_external
        if hit_ext:
            return True, f"external surface named: {sorted(hit_ext)[:3]}"
        if _EXTERNAL.search(req):
            return True, "names an external format/protocol"
        if _LOCAL.search(req) and not _EXTERNAL.search(req):
            return False, "phrased as an operation on code we have"
        return None, "no rule fired: refused to guess"

    @staticmethod
    def as_question(req: str) -> str:
        r = req.strip().rstrip(".")
        for lead in ("must", "should", "shall", "needs to", "need to",
                     "has to", "ensure", "the code should"):
            if r.lower().startswith(lead):
                rest = r[len(lead):].strip(" :")
                return _capitalise(f"How should {rest}?") if rest else r
        if not r.endswith("?"):
            r += "?"
        return _capitalise(r)

    def explain(self, req: str) -> str:
        v, why = self.classify(req)
        return {True: "ask the oracle", False: "solve locally",
                None: "undecided"}[v] + f" -- {why}"

def normalise_key(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()

def _shares_word(a: str, b: str) -> bool:
    wa = set(re.findall(r"[a-z_]{4,}", a.lower()))
    return bool(wa & set(re.findall(r"[a-z_]{4,}", b.lower())))

def _pick_context(context: str, req: str, limit: int = 600) -> str:
    if not context:
        return ""
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n", context)
             if s.strip()]
    scored = sorted(((len(_shares_tokens(s, req)), i) for i, s in
                     enumerate(sents)), reverse=True)
    keep, used = [], 0
    for score, i in scored:
        if not score:
            break
        if used + len(sents[i]) > limit:
            continue
        keep.append(sents[i])
        used += len(sents[i])
    return "\n".join(keep)

def _shares_tokens(a: str, b: str) -> set:
    return set(re.findall(r"[a-z_][a-z_0-9]{2,}", a.lower())) & \
        set(re.findall(r"[a-z_][a-z_0-9]{2,}", b.lower()))

def _capitalise(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s