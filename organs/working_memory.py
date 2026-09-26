
from __future__ import annotations

import hashlib
import time

import numpy as np

class WorkingMemoryOrgan:
    def __init__(self, capacity: int = 7):
        self.slots: dict[str, dict] = {}
        self.capacity = capacity
        self.stored = self.evicted = 0

    def store(self, key: str, value, priority: float = 1.0):
        if key in self.slots:
            return self.update(key, value, priority)
        if len(self.slots) >= self.capacity:
            victim = min(self.slots.items(),
                         key=lambda kv: (kv[1]["priority"],
                                         kv[1]["timestamp"]))[0]
            del self.slots[victim]
            self.evicted += 1
        self.slots[key] = {"value": value, "priority": float(priority),
                           "timestamp": time.time(), "access_count": 0}
        self.stored += 1
        return key

    def retrieve(self, key: str):
        s = self.slots.get(key)
        if not s:
            return None
        s["access_count"] += 1
        s["timestamp"] = time.time()
        return s["value"]

    def update(self, key: str, value, priority: float | None = None):
        if key in self.slots:
            self.slots[key]["value"] = value
            self.slots[key]["timestamp"] = time.time()
            if priority is not None:
                self.slots[key]["priority"] = float(priority)
        else:
            self.store(key, value, priority or 1.0)
        return key

    def remove(self, key: str):
        return self.slots.pop(key, None) is not None

    def active_context(self) -> dict:
        return {k: v["value"] for k, v in
                sorted(self.slots.items(),
                       key=lambda kv: -kv[1]["priority"])}

    def decay(self, rate: float = 0.05):
        """Attention-like forgetting: untouched thoughts fade; below 0.1
        they drop out of mind entirely (goal-class priorities survive -
        only ACCESS refreshes, never priority inflation)."""
        gone = []
        for k, s in self.slots.items():
            s["priority"] -= rate * max(0, 1.0 - 0.25 * s["access_count"])
            s["access_count"] = max(0, s["access_count"] - 1)
            if s["priority"] < 0.1:
                gone.append(k)
        for k in gone:
            del self.slots[k]
            self.evicted += 1
        return len(gone)

    def to_sensory_vector(self, dimension: int = 3840) -> np.ndarray:
        """Sparse KC-compatible code: every held (key,value) pair hashes to
        a small bump of active units - the same substrate text_code uses."""
        v = np.zeros(dimension, np.float32)
        for k, val in self.active_context().items():
            blob = f"{k}={str(val)[:120]}".encode("utf-8", "replace")
            h = hashlib.blake2b(blob, digest_size=8).digest()
            n = int.from_bytes(h[:4], "little") % dimension
            m = int.from_bytes(h[4:6], "little") % max(1, dimension - n)
            v[n:n + m if m else n + 1] = 1.0
            i = int.from_bytes(h[6:], "little") % dimension
            v[i] = 1.0
        return v

    def summary(self) -> str:
        keys = sorted(self.slots.items(), key=lambda kv: -kv[1]["priority"])
        return "Holding: " + (", ".join(k for k, _ in keys)
                              if keys else "(nothing yet)")

    def stats(self) -> dict:
        return {"slots": len(self.slots), "capacity": self.capacity,
                "stored": self.stored, "evicted": self.evicted,
                "priorities": {k: round(s["priority"], 2)
                               for k, s in self.slots.items()}}

    def clear(self):
        self.slots.clear()