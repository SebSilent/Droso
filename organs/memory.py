
from __future__ import annotations

import json
import time
from collections import deque
from pathlib import Path

class EpisodicMemory:
    def __init__(self, capacity: int = 1000):
        self.capacity = int(capacity)
        self.episodes: deque[dict] = deque(maxlen=self.capacity)

    def record(self, tick: int, task: str, action, outcome, reward: float) -> dict:
        e = {"tick": int(tick), "task": task, "action": action,
             "outcome": outcome, "reward": float(reward), "t": time.time()}
        self.episodes.append(e)
        return e

    def recent(self, n: int = 10) -> list[dict]:
        return list(self.episodes)[-n:]

    def success_rate(self, last_n: int = 100) -> float:
        eps = list(self.episodes)[-last_n:]
        if not eps:
            return 0.0
        return sum(1 for e in eps if e["reward"] > 0) / len(eps)

    def to_list(self) -> list[dict]:
        return list(self.episodes)

    def load(self, items: list[dict]) -> None:
        for e in items[-self.capacity:]:
            self.episodes.append(e)

class SemanticMemory:
    def __init__(self, capacity: int = 10000):
        self.capacity = int(capacity)
        self.facts: dict[str, dict] = {}
        self._clock = 0.0

    def _tick(self) -> float:
        self._clock += 1.0
        return self._clock

    def store(self, key: str, value, confidence: float = 1.0, source: str = "") -> dict:
        if len(self.facts) >= self.capacity and key not in self.facts:
            lru = min(self.facts, key=lambda k: self.facts[k]["last_accessed"])
            del self.facts[lru]
        fact = self.facts.get(key, {"key": key})
        fact.update({"value": value, "confidence": float(confidence),
                     "source": source, "last_accessed": self._tick()})
        self.facts[key] = fact
        return fact

    def query(self, key: str):
        """Exact-key lookup; returns the fact dict or None, touching LRU."""
        fact = self.facts.get(key)
        if fact is not None:
            fact["last_accessed"] = self._tick()
        return fact

    def search(self, substring: str, limit: int = 10) -> list[dict]:
        sub = substring.lower()
        hits = [f for k, f in self.facts.items() if sub in k.lower()
                or sub in str(f["value"]).lower()]
        hits.sort(key=lambda f: -f["confidence"])
        return hits[:limit]

    def to_list(self) -> list[dict]:
        return list(self.facts.values())

    def load(self, items: list[dict]) -> None:
        for f in items:
            self.facts[f["key"]] = f

class ProceduralMemory:
    def __init__(self, capacity: int = 500):
        self.capacity = int(capacity)
        self.procedures: dict[str, dict] = {}

    def record(self, trigger_pattern: str, action_sequence: list, success: bool) -> dict:
        key = trigger_pattern.lower().strip()
        proc = self.procedures.get(key)
        if proc is None:
            if len(self.procedures) >= self.capacity:
                lru = min(self.procedures, key=lambda k: self.procedures[k]["last_used"])
                del self.procedures[lru]
            proc = {"trigger_pattern": key, "action_sequence": list(action_sequence),
                    "successes": 0, "tries": 0, "last_used": time.time()}
            self.procedures[key] = proc
        proc["tries"] += 1
        proc["successes"] += int(bool(success))
        proc["success_rate"] = proc["successes"] / proc["tries"]
        proc["last_used"] = time.time()
        return proc

    MATCH_FLOOR = 0.5
    MATCH_MARGIN_FLOOR = 0.3
    MATCH_MARGIN = 0.15

    def match(self, task_description: str, min_success_rate: float = 0.6) -> dict | None:
        """Rank by distinctive shared stems; the clearest winner above the floor.

        This carried the same defects as the learning loop's fuzzy matcher, with
        the same consequence -- it matched nothing, ever. The query was split on
        whitespace and never stemmed, while every trigger_pattern is a signature of
        stems, so a plural could not meet its own singular. And Jaccard over the
        union caps a two-word query against an eight-stem pattern near 0.25, so no
        phrasing could win however exact.

        A recall that is wrong gets believed, so the bar is not only "scored
        highly" but "scored clearly higher than the runner-up".
        """
        import math
        import re
        from .learning_loop import _stem, _STOPWORDS
        want = {_stem(w) for w in re.findall(
            r"[a-z_][a-z_0-9]{3,}", str(task_description or "").lower())}
        want -= _STOPWORDS
        if not want:
            return None
        pool = {k: set(str(p.get("trigger_pattern", "")).split())
                for k, p in self.procedures.items()}
        n = max(1, len(pool))
        df: dict = {}
        for toks in pool.values():
            for w in toks:
                df[w] = df.get(w, 0) + 1
        wq = {w: math.log(1.0 + n / float(max(1, df.get(w, 0)))) for w in want}
        total = sum(wq.values())
        if total <= 0.0:
            return None
        ranked = []
        for key, proc in self.procedures.items():
            if proc.get("success_rate", 0.0) < min_success_rate:
                continue
            toks = pool.get(key) or set()
            if not toks:
                continue
            ranked.append((sum(wq[w] for w in (want & toks)) / total, proc))
        if not ranked:
            return None
        ranked.sort(key=lambda t: -t[0])
        score, best = ranked[0]
        runner = ranked[1][0] if len(ranked) > 1 else 0.0
        if score >= self.MATCH_FLOOR:
            return best
        if score >= self.MATCH_MARGIN_FLOOR and \
                (score - runner) >= self.MATCH_MARGIN:
            return best
        return None

    def to_list(self) -> list[dict]:
        return list(self.procedures.values())

    def load(self, items: list[dict]) -> None:
        for p in items:
            self.procedures[p["trigger_pattern"]] = p

class MemoryOrgan:
    """The three memories under one organ, with one save/load."""

    def __init__(self, config: dict | None = None, persist_path: str | None = None):
        cfg = config or {}
        self.episodic = EpisodicMemory(int(cfg.get("episodic_capacity", 1000)))
        self.semantic = SemanticMemory(int(cfg.get("semantic_capacity", 10000)))
        self.procedural = ProceduralMemory(int(cfg.get("procedural_capacity", 500)))
        self.persist_path = Path(persist_path) if persist_path else None
        if self.persist_path and self.persist_path.exists():
            self._load_file()

    def _load_file(self) -> None:
        d = json.loads(self.persist_path.read_text(encoding="utf-8"))
        self.episodic.load(d.get("episodic", []))
        self.semantic.load(d.get("semantic", []))
        self.procedural.load(d.get("procedural", []))

    def save(self) -> None:
        if self.persist_path is None:
            return
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        self.persist_path.write_text(json.dumps({
            "episodic": self.episodic.to_list(),
            "semantic": self.semantic.to_list(),
            "procedural": self.procedural.to_list(),
        }, indent=1), encoding="utf-8")

    def note_episode(self, tick, task, action, outcome, reward):
        return self.episodic.record(tick, task, action, outcome, reward)