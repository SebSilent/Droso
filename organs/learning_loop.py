from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path

# One stemmer for the whole project. It was defined here and copied twice more,
# and all three copies folded "class" to "clas" -- the single example the old
# docstring said must not happen -- while failing to fold "places" to "place", so
# a plural could not meet its own singular anywhere in the system.
from .stemming import stem as _stem

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "exocortex" / "learned_procedures.json"
EVENTS = ROOT / "exocortex" / "learning_events.jsonl"

PROMOTE_STEP = 0.15
DEMOTE_STEP = 0.25
MAX_CONF = 0.98
SOLUTION_CHARS = 32000

# Not every verification is worth the same, and treating them alike lets a loop buy
# trust. A bare run of a function definition that exits zero proves it parses and
# its imports resolve -- running it again proves that again, so fifteen of them are
# still one piece of evidence. A test that passed while executing inside the
# function's own body is evidence about whether it works.
#
# These weights are why the trust floor is reachable by a test suite and not by
# repetition. "syntax" earns nothing: LanguageVerifier's python check is compile()
# and nothing more, and code that raises on every possible input still compiles.
EVIDENCE_WEIGHT = {
    "test_covered": 0.35,
    "task_check": 0.35,
    "execution": 0.15,
    "line_trace": 0.15,
    # It ran and nothing in it was called. That is not nothing -- it parses and its
    # imports resolve -- but repeating it proves the same thing again, and a
    # confidence that rises on repetition of a no-op is a confidence that can be
    # manufactured by a loop.
    "definitional": 0.0,
    "syntax": 0.0,
    "compile": 0.0,
}

_STOPWORDS = {"the", "and", "for", "with", "that", "this", "should", "must",
              "write", "creat", "make", "code", "function", "please", "when",
              "then", "into", "from"}


def signature(text: str, limit: int = 8) -> str:
    """A stable, human-readable key: the salient stems of the task, sorted, so
    the same request phrased differently still finds its procedure."""
    w = {_stem(x) for x in
         re.findall(r"[a-z_][a-z_0-9]{3,}", str(text or "").lower())}
    keep = sorted(w - _STOPWORDS)[:limit]
    return " ".join(keep) or "general"

class LearningLoop:
    def __init__(self, procedure_store=None, pattern_library=None, cache=None,
                 exocortex=None, memory=None, state_path=None, events_path=None,
                 min_confidence: float = 0.7, persist: bool = True):
        self.procedures = procedure_store if procedure_store is not None else \
            (getattr(memory, "procedural", None) if memory else None)
        self.patterns = pattern_library if pattern_library is not None else \
            (getattr(memory, "semantic", None) if memory else None)
        self.cache = cache
        self.exo = exocortex
        self.min_confidence = float(min_confidence)
        self.state_path = Path(state_path) if state_path else STATE
        self.events_path = Path(events_path) if events_path else EVENTS
        self.persist = bool(persist)
        self.store: dict[str, dict] = {}
        self.adopted: dict[str, dict] = {}
        self.discarded: dict[str, dict] = {}
        self.events = 0
        self.reuses = 0
        self.unlearnable_rejections = 0
        self.promotions = self.demotions = 0
        if self.persist and self.state_path.exists():
            self._load()

    def _load(self):
        try:
            d = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.store = d.get("procedures", {}) or {}
            self.adopted = d.get("adopted", {}) or {}
            self.discarded = d.get("discarded", {}) or {}
            self.min_confidence = float(d.get("min_confidence",
                                              self.min_confidence))
        except (OSError, ValueError):
            self.store = {}

    def load_if_exists(self) -> None:
        """Re-read from disk, adopting whatever is there now."""
        if self.state_path.exists():
            try:
                d = json.loads(self.state_path.read_text(encoding="utf-8"))
                self.store.update(d.get("procedures", {}) or {})
                self.discarded.update(d.get("discarded", {}) or {})
            except (OSError, ValueError):
                pass

    def _adopt(self, disk: dict) -> int:
        """Take on records written by someone else, into their own store.

        The house holds the main store in memory and writes it whole, which made it
        the only writer that could exist: any offline tool that learned something
        was erased on the next tick. The battery taught one procedure -- the first
        verified by doing a task -- and it was gone from the file before the report
        finished printing.

        Adopted records go into a separate map rather than the main store, because
        the main store has a lifecycle -- promote, demote, discard -- and dropping a
        foreign record into it lets a stale disk copy resurrect something that was
        deliberately thrown away, which is exactly what the first version did and
        what its own test caught. Adopted records are recalled as a fallback and
        carry evidence the same way; they simply cannot be promoted or discarded by
        a life that has never met them.
        """
        added = 0
        for key, rec in (disk.get("procedures") or {}).items():
            if key not in self.store and key not in self.discarded \
                    and key not in self.adopted:
                self.adopted[key] = rec
                added += 1
        return added

    def save(self):
        if not self.persist:
            return
        self.state_path.parent.mkdir(exist_ok=True)
        if self.state_path.exists():
            try:
                self._adopt(json.loads(
                    self.state_path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass
        self.state_path.write_text(json.dumps(
            {"procedures": self.store, "adopted": self.adopted,
             "discarded": self.discarded,
             "min_confidence": self.min_confidence,
             "saved": round(time.time(), 1)}, indent=1,
            ensure_ascii=False), encoding="utf-8")

    def _event(self, kind: str, payload: dict):
        self.events += 1
        if not self.persist:
            return
        try:
            self.events_path.parent.mkdir(exist_ok=True)
            with open(self.events_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": round(time.time(), 3),
                                    "kind": kind, **payload},
                                   ensure_ascii=False) + "\n")
        except OSError:
            pass

    def learn_from_task(self, task: str, solution, meta: dict | None = None,
                        verified: bool | None = None) -> dict:
        """Record what worked. Returns the stored record, or a refusal."""
        meta = dict(meta or {})
        src = str(meta.get("source") or meta.get("mode") or "")
        if src in ("mock", "blocked", "error", "none") or meta.get("mock") \
                or meta.get("synthetic"):
            self.unlearnable_rejections += 1
            self._event("rejected_provenance",
                        {"task": signature(task), "source": src or "unknown"})
            return {"stored": False, "reason": "unlearnable_provenance",
                    "source": src or "unknown",
                    "task_signature": signature(task)}
        if not solution or (isinstance(solution, str) and not solution.strip()):
            self._event("rejected_empty", {"task": signature(task)})
            return {"stored": False, "reason": "no_solution"}
        if verified is None:
            verified = bool(meta.get("verified", False))
        sig = signature(task)
        now = time.time()
        rec = self.store.get(sig)
        if rec is None and sig in self.discarded:
            parked = self.discarded[sig]
            if not verified:
                parked["tries"] = int(parked.get("tries", 0)) + 1
                parked["failures"] = int(parked.get("failures", 0)) + 1
                parked["blocked_relearns"] = int(
                    parked.get("blocked_relearns", 0)) + 1
                self._event("refused_revival", {"signature": sig})
                self.save()
                return {"stored": False, "reason": "discarded_needs_verification",
                        "task_signature": sig}
            parked.pop("blocked_relearns", None)
            self.discarded.pop(sig, None)
            self.store[sig] = parked
            parked["confidence"] = 0.4
            self._event("revived", {"signature": sig})
            rec = parked
        if rec is None:
            rec = {"signature": sig, "task": str(task)[:300], "tries": 0,
                   "successes": 0, "failures": 0, "confidence": 0.35,
                   "solutions": [], "source": src or "unknown", "created": now,
                   "language": meta.get("language", "python")}
        rec["tries"] += 1
        rec["successes"] += int(verified)
        rec["failures"] += int(not verified)
        rec["last_used"] = now
        rec["source_history"] = sorted(
            set(rec.get("source_history", []) + [src or "unknown"]))[:6]
        sol = solution if isinstance(solution, str) else json.dumps(
            solution, ensure_ascii=False)[:2000]
        # Cutting a solution mid-statement stores broken code that reads like a
        # solution, so the cut is recorded and _best_solution refuses it while an
        # intact one exists. The cap used to be 4,000 characters, which is shorter
        # than most real functions in this project.
        text = sol[:SOLUTION_CHARS]
        rec["solutions"] = (rec.get("solutions", []) +
                            [{"text": text, "verified": bool(verified),
                              "truncated": len(sol) > len(text),
                              "ts": now}])[-4:]
        if verified:
            step = EVIDENCE_WEIGHT.get(str(meta.get("verifier_kind") or ""),
                                       PROMOTE_STEP)
            rec["confidence"] = min(MAX_CONF, rec["confidence"] + step)
            if rec["confidence"] >= self.min_confidence:
                self.promotions += 1
            rec["last_evidence"] = str(meta.get("verifier_kind") or "")
        else:
            rec["confidence"] = max(0.0, rec["confidence"] - DEMOTE_STEP)
            self.demotions += 1
        self.store[sig] = rec
        if rec["confidence"] < 0.15 and rec["tries"] >= 3:
            self.discarded[sig] = rec
            self.store.pop(sig, None)
            self._event("discarded", {"signature": sig,
                                      "confidence": rec["confidence"]})
        self._propagate(sig, rec, meta)
        self._event("learn", {"signature": sig, "verified": bool(verified),
                             "confidence": round(rec["confidence"], 3),
                             "source": rec["source"]})
        self.save()
        return {"stored": True, "record": rec,
                "recallable": rec["confidence"] >= self.min_confidence}

    def _propagate(self, sig: str, rec: dict, meta: dict):
        """Mirror into the organs that already own memory, if they exist."""
        best = _best_solution(rec)
        if self.exo is not None and best:
            try:
                self.exo.compile_procedure({
                    "signature": sig, "task": rec["task"],
                    "steps": [{"code": best, "artifact": True}],
                    "confidence": rec["confidence"],
                    "verifier_kind": meta.get("verifier_kind", "local"),
                    "language": rec.get("language", "python"), "ts": time.time()})
            except Exception:
                pass
        if self.procedures is not None and hasattr(self.procedures, "record"):
            try:
                self.procedures.record(sig, [{"code": best}] if best else [],
                                       bool(rec["successes"]))
            except Exception:
                pass
        if self.patterns is not None and best and rec["successes"]:
            try:
                self.patterns.store(sig, best[:6000],
                                    confidence=rec["confidence"],
                                    source="learning_loop")
            except Exception:
                pass

    def recall(self, task: str, min_confidence: float | None = None) -> dict | None:
        floor = self.min_confidence if min_confidence is None else \
            float(min_confidence)
        sig = signature(task)
        rec = self.store.get(sig) or self.adopted.get(sig)
        if rec is None:
            rec = self._fuzzy(task, floor)
        if not rec or float(rec.get("confidence", 0)) < floor:
            return None
        best = _best_solution(rec)
        if not best:
            return None
        self.reuses += 1
        rec["last_used"] = time.time()
        rec["reuses"] = int(rec.get("reuses", 0)) + 1
        self._event("recall", {"signature": rec["signature"],
                              "confidence": round(rec["confidence"], 3)})
        return {"solution": best, "method": "learned",
                "signature": rec.get("signature"),
                "confidence": round(float(rec["confidence"]), 3),
                "verified": bool(rec.get("successes")),
                "provenance": f"learned({rec['signature'][:28]})"}

    # Retrieval floors. A recall that is wrong gets believed, so the bar is not
    # only "scored highly" but "scored clearly higher than the alternative".
    FUZZY_FLOOR = 0.5
    FUZZY_MARGIN_FLOOR = 0.3
    FUZZY_MARGIN = 0.15

    def _fuzzy(self, task: str, floor: float):
        """Rank by distinctive shared stems, not by raw word overlap.

        Three defects made this return nothing at all, ever, and it measured 0 of
        191 probes against a library of 273:

          the query was never stemmed while every signature was, so "candidates"
            could not meet "candidate" and no plural or past tense ever matched;
          the score was divided by the signature's eight stems, so a two-word
            request capped at 0.25 against a floor of 0.5 -- no phrasing, however
            exact, could reach it;
          every word counted the same, so agreeing on a common stem was worth as
            much as agreeing on a rare one.

        Both sides are now stemmed by the same function that built the key, words
        are weighted by how few procedures share them, and the score is the share
        of the *query's* distinctive weight that a procedure accounts for -- so a
        short specific request can win, which is what a short specific request is.
        """
        want = {_stem(w) for w in
                re.findall(r"[a-z_][a-z_0-9]{3,}", str(task or "").lower())}
        want -= _STOPWORDS
        if not want:
            return None
        n = max(1, len(self.store) + len(self.adopted))
        df: dict[str, int] = {}
        surfaces = {}
        for sig in list(self.store) + list(self.adopted):
            rec = self.adopted.get(sig) or self.store.get(sig)
            # Every surface a procedure can be found by: its own key, plus the
            # aliases the seeder recorded for its name and its arguments.
            have = set(str(sig).split())
            for al in (rec.get("aliases") or []):
                have |= set(str(al).split())
            surfaces[sig] = have
            for w in have:
                df[w] = df.get(w, 0) + 1
        wq = {w: math.log(1.0 + n / float(max(1, df.get(w, 0)))) for w in want}
        total = sum(wq.values())
        if total <= 0.0:
            return None
        ranked: list = []
        for sig, have in surfaces.items():
            rec = self.adopted.get(sig) or self.store.get(sig)
            if rec is None or float(rec.get("confidence", 0)) < floor:
                continue
            if not have:
                continue
            ranked.append((sum(wq[w] for w in (want & have)) / total, rec))
        if not ranked:
            return None
        ranked.sort(key=lambda t: -t[0])
        score, best = ranked[0]
        runner = ranked[1][0] if len(ranked) > 1 else 0.0
        if score >= self.FUZZY_FLOOR:
            return best
        # A narrow but unambiguous win still counts: most of the query's weight
        # sits in one rare stem, and nothing else is close.
        if score >= self.FUZZY_MARGIN_FLOOR and (score - runner) >= self.FUZZY_MARGIN:
            return best
        return None

    def alias_request(self, sig: str, task: str) -> dict:
        """File a new phrasing under the procedure that answered it.

        Recording the request as a procedure in its own right files the same code
        under a second key, and every novel phrasing adds another copy -- so the
        library grows by duplication while retrieval gets worse, because each copy
        takes a share of the distinctiveness weighting the ranking depends on. A
        phrasing that found a procedure is evidence about that procedure, and it
        belongs on it.
        """
        rec = self.store.get(str(sig))
        if rec is None:
            return {"aliased": False, "reason": "no such procedure"}
        key = signature(task)
        if not key or key == "general":
            return {"aliased": False, "reason": "request has no salient words"}
        have = set(str(a) for a in (rec.get("aliases") or []))
        if key in have:
            return {"aliased": False, "reason": "already an alias"}
        have.add(key)
        rec["aliases"] = sorted(have)[:16]
        self._event("aliased", {"signature": str(sig), "alias": key})
        self.save()
        return {"aliased": True, "signature": str(sig), "alias": key}

    def reinforce(self, task: str, success: bool, sig: str | None = None) -> dict:
        """Move one procedure's confidence on the evidence of a single use.

        `sig` names the record that was actually recalled, and it matters. A
        procedure found by fuzzy matching is stored under its own signature, not
        under the words that happened to find it, so re-deriving the key from the
        request promoted nothing at all -- or promoted some other record while the
        code that had just run went uncredited. This is the only path by which use
        builds trust, so getting the key wrong meant the library could never earn
        its way past the recall floor.
        """
        key = str(sig) if sig else signature(task)
        rec = self.store.get(key)
        if not rec:
            return {"known": False}
        rec["tries"] += 1
        if success:
            rec["successes"] += 1
            rec["confidence"] = min(MAX_CONF, rec["confidence"] + PROMOTE_STEP)
            self.promotions += 1
        else:
            rec["failures"] += 1
            rec["confidence"] = max(0.0, rec["confidence"] - DEMOTE_STEP)
            self.demotions += 1
        self._event("reinforce", {"signature": key, "success": bool(success),
                                 "confidence": round(rec["confidence"], 3)})
        self.save()
        return {"known": True, "confidence": round(rec["confidence"], 3)}

    def list_procedures(self, query: str = "", limit: int = 50,
                       include_discarded: bool = False) -> list[dict]:
        """What this loop actually knows, as plain rows for the panel.

        Returns the stored record verbatim plus its signature, because inventing
        a tidy schema here would mean the dashboard shows fields the store never
        wrote. Sorted by confidence, then by most recent.
        """
        src = dict(self.store)
        if include_discarded:
            for k, v in self.discarded.items():
                src.setdefault(k, dict(v or {}, discarded=True))
        q = str(query or "").strip().lower()
        rows = []
        for sig, rec in src.items():
            r = dict(rec or {})
            r["signature"] = sig
            if q and q not in str(r.get("task", "")).lower() and \
                    q not in str(sig).lower():
                continue
            rows.append(r)
        rows.sort(key=lambda r: (float(r.get("confidence", 0) or 0),
                                 float(r.get("updated", r.get("t", 0)) or 0)),
                 reverse=True)
        return rows[:max(1, int(limit))]

    def list_events(self, limit: int = 20) -> list[dict]:
        """The tail of the append-only event log: what was learned, when, and on
        whose evidence. Read from disk so a restarted process still remembers."""
        out = []
        try:
            if not self.events_path.exists():
                return []
            with open(self.events_path, encoding="utf-8") as f:
                lines = f.readlines()[-max(1, int(limit)):]
            for line in lines:
                try:
                    out.append(json.loads(line))
                except Exception:
                    out.append({"kind": "unparseable", "raw": line[:200]})
        except Exception as e:
            return [{"kind": "error", "raw": str(e)[:200]}]
        return out

    def stats(self) -> dict:
        confs = [float(r.get("confidence", 0)) for r in self.store.values()]
        verified = sum(1 for r in self.store.values() if r.get("successes"))
        return {"procedures": len(self.store),
                "discarded": len(self.discarded),
                "verified_procedures": verified,
                "recallable": sum(1 for c in confs if c >= self.min_confidence),
                "mean_confidence": round(sum(confs) / len(confs), 3)
                if confs else None,
                "min_confidence": self.min_confidence,
                "events": self.events, "reuses": self.reuses,
                "unlearnable_rejections": self.unlearnable_rejections,
                "promotions": self.promotions, "demotions": self.demotions,
                "state_path": str(self.state_path),
                "note": "confidence moves on verification, not on reuse"}

def _best_solution(rec: dict) -> str:
    sols = rec.get("solutions") or []
    if not sols:
        return ""
    # A truncated solution is broken code, so an intact unverified one is worth
    # more than a cut verified one.
    for s in sols:
        if s.get("verified") and not s.get("truncated"):
            return str(s.get("text", ""))
    for s in sols:
        if not s.get("truncated"):
            return str(s.get("text", ""))
    return str(sols[-1].get("text", ""))