from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_DEFAULT = ROOT / "exocortex" / "api_cache.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
  key TEXT PRIMARY KEY, provider TEXT, model TEXT, question TEXT,
  prompt_sha TEXT, answer TEXT, purpose TEXT, mode TEXT, verified INTEGER,
  tokens_in INTEGER, tokens_out INTEGER,
  -- cost_usd is vestigial: kept only so caches written before the pricing
  -- table was deleted still open. Nothing writes or reads it any more.
  cost_usd REAL, created REAL,
  hits INTEGER DEFAULT 0, last_hit REAL DEFAULT 0, size INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_q ON entries(question);
CREATE INDEX IF NOT EXISTS idx_p ON entries(prompt_sha);
"""

def normalise(text: str) -> str:
    """Case, whitespace and punctuation-insensitive, so the same question
    phrased twice does not pay twice."""
    t = re.sub(r"\s+", " ", str(text or "").strip().lower())
    return re.sub(r"[^\w ]", "", t)

def tokens(text: str) -> set:
    return set(re.findall(r"[a-z_][a-z_0-9]{1,}", normalise(text)))

class QueryCache:
    SERVABLE_MODES = ("live",)

    def __init__(self, path: Path | None = None, max_entries: int = 20000,
                 ttl_days: float = 90.0):
        self.path = Path(path) if path else DB_DEFAULT
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_entries = int(max_entries)
        self.ttl_days = float(ttl_days)
        self._lock = threading.Lock()
        self._con = sqlite3.connect(str(self.path), check_same_thread=False)
        self._con.executescript(_SCHEMA)
        self._con.commit()
        self.hits = self.misses = self.near_hits = self.quarantined = 0
        self.tokens_saved = 0
        self.evictions = 0
        self.stale_skips = 0

    @staticmethod
    def key(provider: str, model: str, prompt: str) -> str:
        h = hashlib.sha256()
        h.update(f"{provider}|{model}|{normalise(prompt)}".encode("utf-8"))
        return h.hexdigest()[:32]

    def get(self, question: str, context: str = "", provider: str = "",
            model: str = "", approximate: bool = False,
            threshold: float = 0.55) -> dict | None:
        prompt = f"{context}\n{question}" if context else question
        key = self.key(provider, model, prompt)
        with self._lock:
            row = self._con.execute(
                "SELECT key,question,answer,mode,tokens_in,tokens_out,"
                "created,verified FROM entries WHERE key=?", (key,)).fetchone()
            if row is None and approximate:
                row = self._nearest(question)
                if row is not None:
                    self.near_hits += 1
            if row is None:
                self.misses += 1
                return None
            k, q, ans, mode, ti, to, created, verified = row
            if self.ttl_days and (time.time() - created) > self.ttl_days * 86400:
                self.stale_skips += 1
                self.misses += 1
                return None
            if mode not in self.SERVABLE_MODES:
                self.quarantined += 1
                self.misses += 1
                return None
            self.hits += 1
            self.tokens_saved += int(ti or 0) + int(to or 0)
            self._con.execute(
                "UPDATE entries SET hits=hits+1, last_hit=? WHERE key=?",
                (time.time(), k))
            self._con.commit()
        out = {"answer": ans, "question": q, "mode": mode, "exact": q == question,
               "verified": bool(verified), "cache_key": k,
               "tokens_avoided": int(ti or 0) + int(to or 0)}
        if not out["exact"]:
            out["approximate"] = True
            out["similarity"] = _jaccard(tokens(question), tokens(q))
            out["warning"] = ("served by similarity, not equality: this answer "
                              "was written for a different question")
        return out

    def _nearest(self, question: str):
        best, score = None, 0.0
        want = tokens(question)
        if not want:
            return None
        for row in self._con.execute(
                "SELECT key,question,answer,mode,tokens_in,tokens_out,"
                "created,verified FROM entries ORDER BY last_hit DESC, "
                "created DESC LIMIT 400"):
            s = _jaccard(want, tokens(row[1]))
            if s > score:
                best, score = row, s
        return best if score >= 0.55 else None

    def put(self, question: str, answer: str, context: str = "",
            provider: str = "", model: str = "", purpose: str = "",
            mode: str = "live", tokens_in: int = 0, tokens_out: int = 0,
            verified: bool | None = None) -> str:
        prompt = f"{context}\n{question}" if context else question
        key = self.key(provider, model, prompt)
        cols = ("key", "provider", "model", "question", "prompt_sha", "answer",
                "purpose", "mode", "verified", "tokens_in", "tokens_out",
                "cost_usd", "created", "hits", "last_hit", "size")
        with self._lock:
            self._con.execute(
                "INSERT OR REPLACE INTO entries ("
                + ",".join(cols) + ") VALUES ("
                + ",".join("?" * len(cols)) + ")",
                (key, provider, model, str(question).strip(),
                 hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
                 str(answer), normalise(prompt)[:64], mode,
                 int(bool(verified)) if verified is not None else 0,
                 int(tokens_in), int(tokens_out), 0.0, time.time(),
                 0, 0.0, len(str(answer))))
            self._con.commit()
            self._prune()
        return key

    def mark_verified(self, key: str, verified: bool = True):
        with self._lock:
            self._con.execute("UPDATE entries SET verified=? WHERE key=?",
                              (int(bool(verified)), key))
            self._con.commit()

    def _prune(self):
        n = self._con.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        if n <= self.max_entries:
            return
        over = n - self.max_entries
        self._con.execute(
            "DELETE FROM entries WHERE key IN (SELECT key FROM entries ORDER "
            "BY last_hit DESC, hits DESC, created ASC LIMIT ?)", (over,))
        self._con.commit()
        self.evictions += over

    def purge_non_live(self) -> int:
        """Delete rows the cache would never serve (legacy synthetic answers).

        Returns how many went. Reported rather than done at import: silently
        deleting rows from a file the user may be inspecting is its own kind of
        fabrication.
        """
        marks = ",".join("?" * len(self.SERVABLE_MODES))
        with self._lock:
            cur = self._con.execute(
                f"DELETE FROM entries WHERE mode NOT IN ({marks})",
                tuple(self.SERVABLE_MODES))
            self._con.commit()
        return cur.rowcount

    def list_entries(self, query: str = "", limit: int = 50) -> list[dict]:
        """Recent cached answers for the Learning panel. Answer text is truncated
        here rather than in the browser, so a 200 KB cached blob never becomes a
        200 KB page over the LAN."""
        lim = max(1, int(limit))
        sql = ("SELECT key, question, provider, model, mode, purpose, verified, "
               "tokens_in, tokens_out, created, hits, size, "
               "substr(answer,1,300) AS answer FROM entries")
        args: list = []
        q = str(query or "").strip()
        if q:
            sql += " WHERE question LIKE ?"
            args.append(f"%{q}%")
        sql += " ORDER BY created DESC LIMIT ?"
        args.append(lim)
        cols = ["key", "question", "provider", "model", "mode", "purpose",
                "verified", "tokens_in", "tokens_out", "created",
                "hits", "size", "answer"]
        with self._lock:
            rows = self._con.execute(sql, args).fetchall()
        return [dict(zip(cols, r)) for r in rows]

    def stats(self) -> dict:
        with self._lock:
            n, bytes_ = self._con.execute(
                "SELECT COUNT(*), COALESCE(SUM(size),0) FROM entries").fetchone()
            modes = dict(self._con.execute(
                "SELECT mode, COUNT(*) FROM entries GROUP BY mode").fetchall())
            stale = 0
            if self.ttl_days:
                cut = time.time() - self.ttl_days * 86400
                stale = self._con.execute(
                    "SELECT COUNT(*) FROM entries WHERE created < ?",
                    (cut,)).fetchone()[0]
        asked = self.hits + self.misses
        return {"entries": int(n or 0), "bytes": int(bytes_ or 0),
                "db_path": str(self.path), "modes": modes,
                "hits": self.hits, "misses": self.misses,
                "near_matches_served": self.near_hits,
                "quarantined_not_served": self.quarantined,
                "servable_modes": list(self.SERVABLE_MODES),
                "hit_rate": round(self.hits / asked, 3) if asked else None,
                "tokens_saved": self.tokens_saved,
                "stale_entries": int(stale or 0), "evictions": self.evictions,
                "ttl_days": self.ttl_days}

    def clear(self):
        with self._lock:
            self._con.execute("DELETE FROM entries")
            self._con.commit()

    def close(self):
        try:
            self._con.close()
        except sqlite3.Error:
            pass

    def __repr__(self):
        return f"<QueryCache {self.path.name} {self.stats()['entries']} entries>"

def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)