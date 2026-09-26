"""A goal that outlives the moment it was set. Phase 5a.

Working memory was a Python dict. A goal existed while some function held it in a
local variable and vanished on return, so every step of every task started from
scratch and the only continuity lived in the caller's stack. Nothing multi-step was
possible before this, which is why Phase 5 is ordered the way it is: 5b searches
and needs somewhere to hold what it is searching for, 5c checks itself against a
goal it must still have, and 5d merges traces that are sequences of steps.

What a brain does instead is delay activity -- a pattern that keeps itself lit
after the thing that lit it has gone. This holds a goal on the same projection
neurons a scent or a grounded object uses, leaks it slowly, and injects it as extra
drive into every decision he makes. So the goal biases what he does next for as
long as it is held, including when nothing in the world currently mentions it.
That last part is the whole point and it is the part a dict cannot do: a goal that
only exists while something reminds you of it is not a goal.

The leak is real time, applied lazily on read, so the organ needs no tick hook and
cannot drift out of step with the world clock. Half-life is HOLD_HALF_LIFE_S: long
enough to survive a multi-step task, short enough that an abandoned goal fades
instead of haunting him forever.

Nothing here invents a mechanism. `extra_drive` is how a scent already enters,
`_pn_percept` is how a grounded thing already gets its cells, and the leak is an
exponential. The new thing is that the pattern persists.
"""
from __future__ import annotations

import math
import time


class GoalOrgan:
    HOLD_HALF_LIFE_S = 180.0
    FLOOR = 0.05
    MAX_STRENGTH = 4.0

    def __init__(self, language, half_life: float | None = None):
        self.language = language
        self.half_life = float(half_life or self.HOLD_HALF_LIFE_S)
        self.text: str | None = None
        self.strength = 0.0
        self._set_at = 0.0
        self._touched_at = 0.0
        self._perc = None
        self.held = 0
        self.expired = 0
        self.refreshes = 0

    # ------------------------------------------------------------------
    def _leak(self) -> None:
        """Apply the decay that has accrued since the last read."""
        if self.strength <= 0.0 or not self.text:
            return
        now = time.time()
        dt = max(0.0, now - self._touched_at)
        self._touched_at = now
        if dt <= 0.0:
            return
        self.strength *= math.exp(-math.log(2.0) * dt / self.half_life)
        if self.strength < self.FLOOR:
            # Faded out on its own. Recorded, because "he dropped the goal" and
            # "he never had one" are different facts about the same silence.
            self.strength = 0.0
            self.text = None
            self._perc = None
            self.expired += 1

    def hold(self, text: str, strength: float = 1.0) -> dict:
        """Take a goal, or refresh one already held.

        Refreshing the same goal strengthens it rather than resetting it, so a goal
        he keeps returning to survives longer than one mentioned once -- which is
        what attention to a goal looks like from inside.
        """
        t = " ".join(str(text or "").strip().lower().split()[:12])
        if not t:
            return {"held": False, "reason": "a goal needs words"}
        self._leak()
        same = (t == self.text)
        if same:
            self.strength = min(self.MAX_STRENGTH,
                                self.strength + float(strength))
            self.refreshes += 1
        else:
            perc = None
            lang = self.language
            if lang is not None and hasattr(lang, "_pn_percept"):
                perc = lang._pn_percept("goal|" + t)
            if perc is None:
                return {"held": False, "reason": "no projection neurons"}
            self.text = t
            self._perc = perc
            self.strength = min(self.MAX_STRENGTH, max(0.1, float(strength)))
            self._set_at = time.time()
            self._touched_at = self._set_at
            self.held += 1
        return {"held": True, "goal": self.text,
                "strength": round(self.strength, 3),
                "refreshed": bool(same)}

    def drive(self):
        """The drive to inject into a decision, or None if nothing is held.

        Same shape as a scent or a ground: (node indices, amplitudes), scaled by
        how strongly the goal is still held. A faded goal contributes nothing
        rather than contributing weakly forever.
        """
        self._leak()
        if self.strength <= 0.0 or self._perc is None:
            return None
        idx, amp = self._perc[0], self._perc[1]
        try:
            import numpy as np
            return (np.asarray(idx), np.asarray(amp, dtype=float) * self.strength)
        except Exception:
            return None

    def release(self) -> dict:
        """Drop the goal on purpose, as against letting it fade."""
        had = self.text
        self.text = None
        self.strength = 0.0
        self._perc = None
        return {"released": had}

    # ------------------------------------------------------------------
    def sustained_for(self) -> float:
        """Seconds this goal has been held without anyone restating it.

        The number that says whether delay activity is happening. A dict scores
        zero on this forever: it is either in scope or it is gone.
        """
        self._leak()
        if not self.text:
            return 0.0
        return round(time.time() - self._set_at, 2)

    def report(self) -> dict:
        self._leak()
        return {"goal": self.text,
                "strength": round(self.strength, 3),
                "sustained_s": self.sustained_for(),
                "half_life_s": self.half_life,
                "cells": len(self._perc[0]) if self._perc else 0,
                "held_total": self.held,
                "refreshed_total": self.refreshes,
                "expired_total": self.expired}
