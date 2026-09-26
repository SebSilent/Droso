
from __future__ import annotations

import re

import numpy as np

_LIBRARY = [
    ("guard_clauses", "validate inputs early and return neutral values",
     "defensive checks at function entry; no behavior change for valid input",
     ["simplicity:high", "integration:low-risk"], ["shallow for logic bugs"],
     "ADD_CONDITION"),
    ("try_except_wrap", "catch the failure class and degrade gracefully",
     "wrap risky calls; handle typed exceptions per failure mode",
     ["handles unknown inputs", "keeps caller alive"],
     ["may mask real bugs", "needs the right exception class"],
     "WRAP_TRY_EXCEPT"),
    ("helper_extraction", "pull the sub-problem into a tested helper",
     "new pure function + call site replaces inline scribble",
     ["unit-testable", "clear ownership"], ["touches call sites"],
     "ADD_FUNCTION"),
    ("state_tracking", "add explicit state/counter variable + updates",
     "module or attribute variable, updated at the one true place",
     ["makes implicit explicit"], ["must reset correctly"],
     "ADD_VARIABLE"),
    ("structure_upgrade", "re-express control flow as data (state machine)",
     "dict of handlers + dispatch replaces nested branching",
     ["scales with cases", "each state testable alone"],
     ["bigger diff", "overkill for 2 cases"],
     "ADD_VARIABLE"),
    ("memoized_fast_path", "cache/short-circuit the hot path",
     "dict memo + early return on cache hit",
     ["direct perf win"], ["staleness risk, needs key discipline"],
     "ADD_VARIABLE"),
]

class HypothesisGeneratorOrgan:
    def __init__(self, llm_organ, exocortex_organ, rng: int = 0):
        self.llm = llm_organ
        self.exo = exocortex_organ
        self.rng = np.random.RandomState(rng)
        self.generated = 0

    def generate_approaches(self, problem_description: str,
                            existing_code: str = "", count: int = 3,
                            language: str | None = None,
                            paradigms: dict | None = None) -> list:
        self.generated += 1
        patterns = []
        try:
            patterns = [c.get("concept") or c.get("token") or "" for c in
                        self.exo.search_concepts(problem_description, k=5)]
        except Exception:
            pass
        knowledge = ""
        if self.llm is not None:
            try:
                knowledge = self.llm.query(
                    problem_description + "\n" + existing_code[:400]
                   ).get("text", "")
            except Exception:
                knowledge = ""
        ranked = self._rank_paradigms(problem_description, existing_code,
                                      patterns, count)
        out = []
        for i, (pid, why_fit) in enumerate(ranked):
            name, desc, sketch, pros, cons, op = _LIBRARY[pid]
            out.append({
                "name": name if i == 0 else f"{name}_{i + 1}",
                "description": desc,
                "sketch": sketch,
                "pros": list(pros), "cons": list(cons),
                "integration": f"applies via {op} on "
                               f"{self._target_hint(existing_code)}; "
                               f"{why_fit}",
                "op": op,
                "knowledge": [p for p in patterns[:3]],
                "llm_source": bool(knowledge),
            })
        language = str(language or "").lower() or None
        if language and language != "python":
            from organs.language_paradigms import LanguageParadigms
            pats = (paradigms or
                    LanguageParadigms().get_paradigms(language))
            hints = LanguageParadigms().get_pattern_for_task(
                problem_description, language)
            for a in out:
                a["language"] = language
                a["paradigm_hints"] = [k for k, _v in hints[:4]]
                if hints:
                    a["integration"] += "; idiomatic " + language + ": " + \
                        "; ".join(f"{k} ({str(v)[:40]})"
                                  for k, v in hints[:3])[:180]
                elif pats:
                    a["integration"] += "; " + language + " patterns: " + \
                        ", ".join(list(pats)[:4])
        return out

    def _target_hint(self, code: str) -> str:
        fns = re.findall(r"def (\w+)", code or "")
        return f"function {fns[0]}()" if fns else "module top level"

    def _rank_paradigms(self, text: str, code: str, patterns, count):
        t = (text or "").lower()
        c = code or ""
        scored = []
        for i, (name, _d, _s, _p, _c, _op) in enumerate(_LIBRARY):
            s = 0.0
            def _w(*words):
                return sum(2.0 for w in words if w in t)
            s += _w("valid", "check", "negative", "empty",
                    "guard") if i == 0 else 0.0
            s += _w("error", "exception", "fail", "crash", "handle", "api",
                    "network", "risky") if i == 1 else 0.0
            s += _w("extract", "helper", "clean", "separate",
                    "function") if i == 2 else 0.0
            s += _w("count", "track", "state", "reset", "jump",
                    "skip") if i == 3 else 0.0
            s += _w("state machine", "refactor", "dispatch",
                    "transition") if i == 4 else 0.0
            s += _w("optimi", "perf", "faster", "loop", "slow",
                    "cach") if i == 5 else 0.0
            if c.count("def ") >= 3 and i in (2, 4):
                s += 0.5
            if "try" in c and i == 1:
                s += 0.5
            if patterns and i in (2, 3, 5):
                s += 0.25
            scored.append((s + 0.001 * ((i * 7) % 3), i,
                           "matches the brief's vocabulary" if s else
                           "generic fallback paradigm"))
        scored.sort(key=lambda x: -x[0])
        return [((i), why) for _s, i, why in scored[:count]]

    def parse_response(self, llm_response: str) -> list:
        out = []
        blocks = re.split(r"(?m)^\s*(?:Approach|Option|Hypothesis)\s+\d+[:.]",
                          str(llm_response or ""))[1:]
        for b in blocks:
            g = lambda k: (re.search(rf"(?im)^\s*{k}\s*[:.-]\s*(.+)$", b)
                           or [None, ""])[1]
            d = {"name": (g("name") or b.split("\n")[0][:32]).strip(),
                 "description": g("description").strip(),
                 "sketch": g("sketch").strip() or g("implementation").strip(),
                 "pros": [x.strip(" -•*") for x in
                          re.findall(r"(?im)^\s*[-*]\s*(.+)$",
                                     _sec(b, "Pros"))][:4] or ["stated"],
                 "cons": [x.strip(" -•*") for x in
                          re.findall(r"(?im)^\s*[-*]\s*(.+)$",
                                     _sec(b, "Cons"))][:4] or ["stated"],
                 "integration": g("integration").strip(),
                 "op": "ADD_FUNCTION", "parsed": True}
            out.append(d)
        if not out and str(llm_response or "").strip():
            out = [{"name": "raw_suggestion", "description": "",
                    "sketch": str(llm_response)[:600], "pros": [],
                    "cons": ["unstructured - verify against tests"],
                    "integration": "", "op": "ADD_FUNCTION", "parsed": True}]
        return out

    def refine_approach(self, approach: dict, feedback: str) -> dict:
        refined = dict(approach)
        refined.setdefault("refinements", []).append(str(feedback)[:200])
        low = str(feedback).lower()
        if "edge case" in low or "empty" in low or "none" in low:
            refined["op"] = "ADD_CONDITION"
            refined["description"] += " (+ explicit edge-case guard)"
        if "reset" in low or "state" in low:
            refined["op"] = "ADD_VARIABLE"
        if "perf" in low or "slow" in low:
            refined["op"] = "ADD_VARIABLE"
            refined["description"] += " (+ cached fast path)"
        refined["name"] = (refined["name"].removesuffix("_refined")
                           + "_refined")
        return refined

def _sec(block: str, header: str) -> str:
    m = re.search(rf"(?im){header}\s*[:.]\s*(.*?)(?=(?:Pros|Cons|"
                  r"Integration|Name|Description|Sketch)|\Z)", block, re.S)
    return m.group(1) if m else ""