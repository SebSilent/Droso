import hashlib
import re
import time

ESCALATE = "escalate"
SIMPLIFY = "simplify"
CONTINUE = "continue"

def error_signature(text: str) -> str:
    """Normalise an error so 'line 12' and 'line 47' of the same complaint
    collide. Keeps the exception class and the first non-numeric words."""
    s = re.sub(r"\d+", "N", str(text or "").lower())
    s = re.sub(r"[\"'`][^\"'`]*[\"'`]", "X", s)
    s = re.sub(r"\s+", " ", s).strip()
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12] if s else ""

class CircuitBreaker:
    def __init__(self, max_retries: int = 3, max_tokens_per_task: int = 5000,
                 max_time_per_task: float = 120.0, repeat_limit: int = 2,
                 on_trip=None):
        self.max_retries = int(max_retries)
        self.max_tokens = int(max_tokens_per_task)
        self.max_time = float(max_time_per_task)
        self.repeat_limit = max(2, int(repeat_limit))
        self.on_trip = on_trip
        self.current_retries = 0
        self.current_tokens = 0
        self.current_time = 0.0
        self.start_time: float | None = None
        self.task = ""
        self.state = "idle"
        self.status: dict = {"action": CONTINUE, "reason": "no task", "level": 1}
        self._sigs: dict[str, int] = {}
        self._last_sig = ""
        self.trips = 0
        self.simplifications = 0
        self.history: list[dict] = []
        self.escalations: list[dict] = []

    def begin_task(self, task: str = "") -> dict:
        self.current_retries = 0
        self.current_tokens = 0
        self.current_time = 0.0
        self.start_time = time.time()
        self.task = str(task)[:200]
        self.state = "closed"
        self._sigs = {}
        self._last_sig = ""
        self.status = {"action": CONTINUE, "reason": "task started", "level": 1}
        return self.status

    def reset(self, by: str = "human") -> dict:
        """Only a human (or the dashboard's answer endpoint) clears an open
        breaker. The loop cannot reset itself -- that is the whole point."""
        self.state = "idle"
        self.current_retries = 0
        self.current_tokens = 0
        self.current_time = 0.0
        self.status = {"action": CONTINUE, "reason": f"reset by {by}",
                       "level": 1}
        self._push({"kind": "reset", "by": by})
        return self.status

    def can_try(self, want_tokens: int = 0) -> dict:
        """Ask before spending. The counters only escalate *after* an attempt,
        which means the last one is always over budget; this is the check that
        stops a call from being made at all."""
        if self.state == "open":
            return {"allow": False, "reason": "circuit open: awaiting human",
                    "level": 3}
        if self.start_time is None:
            return {"allow": True, "reason": "no task in progress", "level": 1}
        if self.current_tokens + want_tokens > self.max_tokens:
            return {"allow": False, "reason": f"would exceed token budget "
f"({self.current_tokens}+{want_tokens} > {self.max_tokens})", "level": 3}
        if self._elapsed() > self.max_time:
            return {"allow": False, "reason": f"would exceed time limit "
f"({self._elapsed():.1f}s > {self.max_time}s)", "level": 3}
        return {"allow": True, "reason": "within limits", "level": 1}

    def record_attempt(self, tokens_used: int = 0, error: str = "",
                       progress: bool = False, phase: str = "") -> dict:
        """Log one attempt and get the verdict for what to do next."""
        if self.state == "open":
            self.status = {"action": ESCALATE, "level": 3,
                           "reason": "circuit already open; attempt refused"}
            self.escalations.append({"task": self.task, "attempt": "ignored",
                                     "reason": self.status["reason"],
                                     "at": time.time()})
            return dict(self.status)
        self.current_retries += 1
        self.current_tokens += int(tokens_used or 0)
        self.current_time = self._elapsed()
        sig = error_signature(error) if error else ""
        repeats = 0
        if sig:
            self._sigs[sig] = self._sigs.get(sig, 0) + 1
            repeats = self._sigs[sig]
        self._last_sig = sig
        prev = self.status
        self.status = self._check_limits(repeats=repeats, progress=progress)
        self._push({"kind": "attempt", "n": self.current_retries,
                    "tokens": self.current_tokens,
                    "seconds": round(self.current_time, 2), "phase": phase,
                    "action": self.status["action"],
                    "level": self.status["level"], "same_error_as_before":
                    bool(sig) and repeats >= 2, "changed": self.status["action"]
                    != prev["action"]})
        if self.status["action"] == SIMPLIFY:
            self.simplifications += 1
        if self.status["action"] == ESCALATE:
            self.state = "open"
            self.trips += 1
            self.escalations.append({"task": self.task, "attempt":
                                     self.current_retries,
                                     "reason": self.status["reason"],
                                     "tokens": self.current_tokens,
                                     "seconds": round(self.current_time, 1),
                                     "at": time.time()})
            if self.on_trip is not None:
                try:
                    self.on_trip(dict(self.status))
                except Exception:
                    pass
        return dict(self.status)

    def _check_limits(self, repeats: int = 0, progress: bool = False) -> dict:
        if repeats >= self.repeat_limit:
            return {"action": ESCALATE, "level": 3,
                    "reason": f"same failure {repeats}x -- repeating is not "
                              f"retrying", "detector": "repeat_signature"}
        if self.current_retries >= self.max_retries:
            return {"action": ESCALATE, "level": 3,
                    "reason": f"exceeded {self.max_retries} retries",
                    "detector": "retries"}
        if self.current_tokens >= self.max_tokens:
            return {"action": ESCALATE, "level": 3,
                    "reason": f"exceeded {self.max_tokens} token budget",
                    "detector": "tokens"}
        if self.current_time >= self.max_time:
            return {"action": ESCALATE, "level": 3,
                    "reason": f"exceeded {self.max_time:.0f}s time limit",
                    "detector": "time"}
        if self.current_retries >= self.max_retries - 1 and not progress:
            return {"action": SIMPLIFY, "level": 2,
                    "reason": "approaching retry limit, simplify approach",
                    "detector": "retries"}
        return {"action": CONTINUE, "level": 1, "reason": "within limits",
                "detector": "none"}

    def _elapsed(self) -> float:
        return time.time() - self.start_time if self.start_time else 0.0

    def _push(self, item: dict):
        item["timestamp"] = time.time()
        self.history.append(item)
        if len(self.history) > 200:
            del self.history[:len(self.history) - 200]

    def get_status(self) -> dict:
        return {"state": self.state, "task": self.task,
                "retries": self.current_retries, "max_retries": self.max_retries,
                "tokens_used": self.current_tokens,
                "max_tokens": self.max_tokens,
                "time_elapsed": round(self._elapsed(), 1),
                "max_time": self.max_time, "action": self.status.get("action"),
                "level": self.status.get("level"),
                "reason": self.status.get("reason"),
                "distinct_errors": len(self._sigs),
                "last_error_repeat": self._last_sig and
                self._sigs.get(self._last_sig, 0)}

    def stats(self) -> dict:
        return dict(self.get_status(), trips=self.trips,
                    simplifications=self.simplifications,
                    attempts=len([h for h in self.history
                                  if h.get("kind") == "attempt"]),
                    last_escalation=self.escalations[-1] if self.escalations
                    else None, escalations=len(self.escalations),
                    open_breaker_awaits_human=True)

def breaker_from_config(cfg: dict | None = None) -> CircuitBreaker:
    c = dict((cfg or {}).get("connectome", {}) or {})
    return CircuitBreaker(max_retries=int(c.get("max_retries", 3)),
                          max_tokens_per_task=int(c.get("max_tokens_per_task",
                                                        5000)),
                          max_time_per_task=float(c.get("max_time_per_task",
                                                        120)),
                          repeat_limit=int(c.get("repeat_limit", 2)))