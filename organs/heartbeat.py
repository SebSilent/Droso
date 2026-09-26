
from __future__ import annotations

import threading
import time
from collections import deque
from pathlib import Path

import numpy as np

from connectome.clock import LivedTime

from organs import tempstore


class CountingDeque(deque):
    """A capped window that also remembers everything that ever passed through.

    The badge reports a lifetime count while the panel shows the last dozen. A
    counter that has to be incremented at every append site is a counter that
    eventually gets forgotten, which is how "0 thoughts" ended up on the header
    of a brain that had thought tens of thousands of times.
    """

    total = 0

    def append(self, x):
        self.total += 1
        super().append(x)

    def appendleft(self, x):
        self.total += 1
        super().appendleft(x)

    def extend(self, it):
        it = list(it)
        self.total += len(it)
        super().extend(it)


class Heartbeat:
    """The metronome of a mind: think, pulse, remember, exist."""

    def __init__(self, agent, config=None, think_interval: float = 30.0,
                 sleep_threshold: float = 1800.0, max_thoughts: int = 200,
                 background_drive: str = "noise",
                 neural_tick_interval: float = 5.0,
                 lived_time_path=None):
        self.agent = agent
        self.engine = getattr(agent, "engine", None)
        self.config = config or {}
        self.think_interval = max(0.5, float(think_interval))
        self.sleep_threshold = max(0.0, float(sleep_threshold))
        self.max_thoughts = int(max_thoughts)
        self.state = "IDLE"
        self.started_at = self._clock()
        self.last_user_activity = self._clock()
        self.ticks = 0
        self.errors = 0
        self.last_error = None
        self.thoughts = CountingDeque(maxlen=self.max_thoughts)
        self._timer = None
        self._running = False
        self.current_task = None
        self.counters = {"blocked": 0, "stuck": 0, "curious": 0,
                         "cautious": 0, "researched": 0}
        self.neural_ticks = 0
        self.neural_activity_log = deque(maxlen=1000)
        self.last_neural_tick = None
        self.last_neural_error = None
        self._neural_timer = None
        self.background_drive = str(background_drive or "noise").lower()
        self.neural_tick_interval = max(0.2, float(neural_tick_interval))
        self.world_speed = "max"
        self.max_tick_interval = 0.05
        self.world_ticks = 0
        self.world_clock = 0.0
        self._measured_tps = 0.0
        self._lived_save_at = 0.0
        self._lived_save_interval = max(5.0, float(
            ((self.config.get("connectome", {}) or {})
             .get("lived_time_save_interval", 60)) or 60))
        self.lived_time = self._open_lived_time(lived_time_path)
        self._research_queue = []
        self._lock = threading.RLock()

    def _clock(self) -> float:
        return time.time()

    @classmethod
    def from_config(cls, agent, config) -> "Heartbeat":
        h = (config.get("heartbeat", {}) or {})
        c = (config.get("connectome", {}) or {})
        interval = float(h.get("neural_tick_interval",
                               c.get("neural_tick_interval", 5) or 5))
        root = c.get("project_root")
        lived = Path(root) / "lived_time.json" if root else None
        return cls(agent, config=config,
                   think_interval=float(h.get("think_interval", 30.0)),
                   sleep_threshold=float(h.get("sleep_threshold", 1800.0)),
                   max_thoughts=int(h.get("max_thoughts", 200)),
                   background_drive=str(c.get("background_drive", "noise")),
                   neural_tick_interval=interval,
                   lived_time_path=lived)

    def _open_lived_time(self, path):
        try:
            return LivedTime.load(Path(path)) if path else LivedTime()
        except Exception:
            return LivedTime()

    def save_lived_time(self) -> None:
        try:
            self.lived_time.save()
            self._lived_save_at = self._clock()
        except Exception as e:
            self.last_error = "lived_time: " + str(e)[:120]

    def start(self):
        """Arm the timers. Non-blocking; the timer threads are daemons."""
        with self._lock:
            if self._running:
                return {"success": False, "state": self.state,
                        "reason": "already running"}
            self._running = True
            self.started_at = self._clock()
        self._schedule(self.think_interval)
        self._schedule_neural(self._tick_delay())
        return {"success": True, "state": self.state,
                "interval_s": self.think_interval,
                "neural_tick_interval_s": self._tick_delay(),
                "world_speed": self.world_speed}

    def stop(self) -> dict:
        with self._lock:
            self._running = False
            for t in (self._timer, self._neural_timer):
                if t is not None:
                    t.cancel()
            self._timer = None
            self._neural_timer = None
        self.save_lived_time()
        return {"success": True, "stats": self.status(),
                "neural_ticks": self.neural_ticks}

    def _schedule(self, delay):
        if not self._running:
            return
        t = threading.Timer(delay, self._fire)
        t.daemon = True
        self._timer = t
        t.start()

    def _fire(self):
        try:
            # Housekeeping rides the pulse: the temp folder is swept on a timer
            # here, so it cannot grow without bound while the house is up. The
            # whole thing is guarded -- a cleaner that can fail a pulse is worse
            # than the mess it was written to prevent.
            try:
                root = getattr(getattr(self.agent, "sandbox", None),
                               "temp_root", None)
                if root is not None:
                    tempstore.sweep_if_due(root)
            except Exception:
                pass
            self._tick()
        except Exception as e:
            self.errors += 1
            self.last_error = type(e).__name__ + ": " + str(e)[:150]
            self.thoughts.append({"kind": "error",
                                  "text": "tick failed: " + str(e),
                                  "provenance": ["heartbeat"],
                                  "t": self._clock()})
        finally:
            self._schedule(self.think_interval)

    def _tick_delay(self) -> float:
        return self.neural_tick_interval if self.world_speed == "1x" \
            else self.max_tick_interval

    def _world_dt(self) -> float:
        """World seconds advanced by one tick. 1x paces ticks at the real
        interval so world time matches wall time; max ticks as fast as the
        hardware allows while advancing the same world time per tick."""
        return self.neural_tick_interval

    def set_world_speed(self, mode: str) -> dict:
        if mode not in ("paused", "1x", "max"):
            return {"success": False, "reason": "unknown speed: " + str(mode)}
        self.world_speed = mode
        if mode == "paused":
            if self._neural_timer is not None:
                self._neural_timer.cancel()
                self._neural_timer = None
            self.last_neural_tick = None
            return {"success": True, "speed": mode}
        if self._running:
            self._schedule_neural(self._tick_delay())
        return {"success": True, "speed": mode}

    def world_state(self) -> dict:
        return {"speed": self.world_speed,
                "world_dt_per_tick": round(self._world_dt(), 3),
                "ticks": self.world_ticks,
                "measured_ticks_per_s": round(self._measured_tps, 3),
                "measured_speed_x": round(
                    self._measured_tps * self._world_dt(), 2),
                "world_clock": round(self.world_clock, 1),
                "last_neural_error": self.last_neural_error}

    def _schedule_neural(self, delay):
        if not self._running or self.world_speed == "paused":
            return
        t = threading.Timer(delay, self._fire_neural)
        t.daemon = True
        self._neural_timer = t
        t.start()

    def _fire_neural(self):
        t0 = time.perf_counter()
        try:
            self._neural_tick()
        except Exception as e:
            self.errors += 1
            self.last_neural_error = type(e).__name__ + ": " + str(e)[:150]
            self._adversity("failed",
                            "a neural tick broke: " + str(e)[:80], 0.5)
        finally:
            real_dt = time.perf_counter() - t0
            self.world_ticks += 1
            self.world_clock += self._world_dt()
            if real_dt > 0:
                self._measured_tps = 0.7 * self._measured_tps + 0.3 * (1.0 / real_dt)
            self._schedule_neural(self._tick_delay())

    def activity(self, kind: str = "user"):
        """Mark that something happened, so SLEEPING means what it says."""
        self.last_user_activity = self._clock()
        if kind == "user" and self.state == "SLEEPING":
            self.state = "IDLE"

    def begin_task(self, text: str):
        self.current_task = str(text or "")[:200]
        self.activity("task")
        self._tell_language("task", self.current_task)
        self._ground("task", self.current_task)

    def end_task(self):
        self.current_task = None
        self._tell_language("task", "the work is finished")

    def _ground(self, kind: str, name: str) -> None:
        """Make a real happening in the world into a percept he can feel."""
        lang = getattr(self.agent, "language", None)
        if lang is not None and hasattr(lang, "ground"):
            try:
                lang.ground(kind, name)
            except Exception:
                pass

    def _adversity(self, kind: str, detail: str = "",
                   severity: float = 0.4) -> None:
        """Something went wrong for real, and it is delivered to the body.

        Not logged and not counted: a negative teaching signal, a cost in energy
        and mood, and an event the parents may describe only while it is true. His
        own malfunctions are adverse experiences, which is the honest version --
        a tick that throws is a bad thing happening to him, not a line in a file.
        """
        lang = getattr(self.agent, "language", None)
        if lang is not None and hasattr(lang, "adversity"):
            try:
                lang.adversity(kind, detail, severity)
            except Exception:
                pass

    def _tell_language(self, kind: str, detail: str = "") -> None:
        """Hand a real event to the parents so they can describe it.

        The heartbeat knows what happened in the world; the language organ knows
        how to say it. Neither should have to guess the other's half, and a
        phrase with no event behind it is just noise.
        """
        lang = getattr(self.agent, "language", None)
        if lang is not None and hasattr(lang, "note_event"):
            try:
                lang.note_event(kind, detail)
            except Exception:
                pass

    def pending_approvals(self):
        sb = getattr(self.agent, "sandbox", None)
        return list(getattr(sb, "pending_approvals", []) or [])

    def observed_state(self) -> str:
        """SLEEPING is a timer, not a mood: quiet too long means asleep."""
        if self._clock() - self.last_user_activity >= self.sleep_threshold:
            return "SLEEPING"
        return "IDLE"

    def _note(self, kind: str, text: str, provenance,
              auto_derived: bool = True) -> dict:
        n = {"kind": kind, "text": text, "provenance": list(provenance),
             "t": self._clock(), "auto_derived": auto_derived}
        self.thoughts.append(n)
        return n

    def status(self) -> dict:
        return {"running": bool(self._running),
                "state": self.observed_state(),
                "ticks": self.ticks,
                "thoughts": len(self.thoughts),
                "errors": self.errors,
                "think_interval": self.think_interval,
                "neural_tick_interval": self.neural_tick_interval,
                "neural_ticks": self.neural_ticks,
                "background_drive": self.background_drive,
                "last_neural_error": self.last_neural_error,
                "world": self.world_state()}

    def stats(self) -> dict:
        s = self.status()
        s["state"] = self.observed_state()
        return s

    def get_consciousness(self) -> dict:
        gaps = [t for t in self.thoughts if t.get("kind") == "gap"]
        return {"present": True, "state": self.observed_state(),
                "thought_count": int(getattr(self.thoughts, "total",
                                             len(self.thoughts))),
                "neural_ticks": self.neural_ticks,
                "recent_thoughts": list(self.thoughts)[-12:],
                "knowledge_gaps": list(gaps)[-8:],
                "research_queue": list(self._research_queue)[-8:],
                "honesty": {"research":
                            "auto-research is OFF: questions are recorded, "
                            "not answered behind your back"},
                "pending_approvals": len(self.pending_approvals()),
                "world": self.world_state()}

    def research(self, question: str) -> dict:
        """Record a question. Auto-research is OFF: the ask is honest
        book-keeping, and a human decides what gets answered."""
        q = str(question or "").strip()
        self.counters["researched"] += 1
        self._research_queue.append({"q": q[:160], "t": self._clock()})
        self._note("researched", "recorded question: " + q[:80],
                   ["heartbeat"])
        self._note("gap", "unanswered: " + q[:80], ["heartbeat"])
        return {"success": False,
                "reason": "auto-research is OFF; the question is recorded",
                "queued": True}

    def _tick(self):
        self.ticks += 1
        self.state = self.observed_state()
        made = []
        sb = getattr(self.agent, "sandbox", None)
        approvals = self.pending_approvals()
        if approvals:
            kinds = sorted({str(a.get("op", a.get("what", "WRITE"))).upper()
                            for a in approvals})
            made.append(self._note(
                "blocked",
                str(len(approvals)) + " change(s) await a human: "
                + ", ".join(kinds), ["sandbox"]))
        blocked = int(getattr(sb, "blocked", 0) or 0)
        if blocked:
            made.append(self._note(
                "blocked", str(blocked) + " destructive command(s) were blocked",
                ["sandbox"]))
        if self.current_task:
            made.append(self._note(
                "curious", "working on: " + self.current_task[:80], ["house"]))
        if self._research_queue:
            made.append(self._note(
                "curious", str(len(self._research_queue))
                + " question(s) recorded, awaiting a human", ["heartbeat"]))
        made = [m for m in made if m]
        return made[-1] if made else None

    def _static_core(self):
        eng = getattr(self.agent, "engine", None)
        return getattr(eng, "static", None) if eng is not None else None

    def _thinking_code(self):
        """(ctx_text, code) from the declared drive. noise = dreaming,
        replay = the last perception, context = the actual situation,
        off = nothing (handled by the caller)."""
        drive = self.background_drive
        eng = getattr(self.agent, "engine", None)
        tok = getattr(self.agent, "tokenizer", None)
        if drive == "replay" and eng is not None \
                and getattr(eng, "last_code", None) is not None:
            return "last perception", eng.last_code
        if drive == "context":
            parts = []
            wm = getattr(self.agent, "working_memory", None)
            if wm is not None:
                goal = wm.retrieve("goal")
                if goal:
                    parts.append("goal:" + str(goal))
            phase = getattr(self.agent, "current_phase", "idle")
            parts.append("phase:" + str(phase))
            ctx = " ".join(parts) or "context:house"
            code = tok.encode(ctx) if tok is not None else None
            return ctx, code
        ctx = "dreaming (noise drive)"
        code = tok.encode(ctx) if tok is not None else None
        return ctx, code

    def _log_neural_activity(self, action, valuation, extra, ctx_text) -> dict:
        rec = {"t": self._clock(),
               "action": int(action) if action is not None else None,
               "valuation_max": (float(np.max(valuation))
                                 if valuation is not None and len(valuation)
                                 else 0.0),
               "active_neurons": None, "drive": self.background_drive,
               "ctx": ctx_text,
               "neurons_driven": None}
        try:
            code = getattr(self.agent.engine, "last_code", None)
            if code is not None:
                rec["active_neurons"] = int(np.count_nonzero(code))
                rec["neurons_driven"] = rec["active_neurons"] * 10
        except Exception:
            pass
        self.neural_activity_log.append(rec)
        return rec

    def _interact_with_organ(self, pool: int, ctx_text: str):
        """Pools that mean recall are FOLLOWED: the organ is actually asked."""
        recall = {3: ("memory", "recall_episodic"),
                  4: ("memory", "recall_semantic"),
                  5: ("memory", "recall_procedural")}
        if pool not in recall:
            return None
        organ_name, what = recall[pool]
        organ = getattr(self.agent, organ_name, None)
        if organ is None:
            return None
        try:
            if what == "recall_episodic":
                seen = organ.episodic.recent(3) if hasattr(
                    organ, "episodic") else None
            elif what == "recall_semantic":
                seen = organ.semantic.search(ctx_text[:60]) if hasattr(
                    organ, "semantic") else None
            else:
                seen = (organ.procedural.best(ctx_text[:60]) if hasattr(
                    organ, "procedural") else None)
            return {"organ": organ_name, "what": what, "found": bool(seen)}
        except Exception as e:
            return {"organ": organ_name, "what": what,
                    "error": str(e)[:80]}

    def _neural_tick(self):
        """Force the connectome to THINK about its actual situation.

        This is not a lullaby pulse: the current working-memory state is
        encoded and propagated through the carved BANC graph, the WTA picks
        a cognitive pool, and pools that map to read-only organ recall are
        actually asked. Every pulse is logged with real counters, and the
        language cortex lives on this same beat.
        """
        core = self._static_core()
        if core is None or self.background_drive == "off":
            return None
        ctx_text, code = self._thinking_code()
        if code is None:
            return None
        prev_phase = getattr(self.agent, "current_phase", None)
        try:
            self.agent.current_phase = "thinking"
        except Exception:
            pass
        try:
            action = self.engine.decide(code)
        finally:
            try:
                self.agent.current_phase = prev_phase or "idle"
            except Exception:
                pass
        valuation = self.engine.last_v
        rec = self._log_neural_activity(action, valuation, None, ctx_text)
        try:
            lang = getattr(self.agent, "language", None)
            if lang is not None and hasattr(lang, "tick"):
                lang.tick(world_dt=self._world_dt())
                mod = getattr(self.agent, "modulation", None)
                if mod is not None and lang is not None:
                    # Turn the dials before anything else runs this tick, so the
                    # decisions and the writing that follow happen under the
                    # chemistry this moment actually calls for.
                    try:
                        inner = lang.inner_state()
                        mod.update(
                            energy=inner.get("energy", 0.8),
                            need_social=inner.get("need_social", 0.3),
                            need_novelty=inner.get("need_novelty", 0.2),
                            mood=inner.get("mood", 0.5),
                            surprise=float(getattr(
                                getattr(lang, "cortex", None), "last_error",
                                0.0) or 0.0),
                            adversity=(lang.adversity_level()
                                       if hasattr(lang, "adversity_level")
                                       else 0.0),
                            phase=inner.get("phase", "day"))
                        mod.note_learning()
                    except Exception:
                        pass
                if hasattr(lang, "curriculum_tick"):
                    lang.curriculum_tick(self._world_dt())
                if hasattr(lang, "expose_tick"):
                    lang.expose_tick(self._world_dt())
                # The speech tutor is gone. It bought batches of sentences from
                # an outside model and dropped them into the air whether or not
                # they meant anything to him -- "I love you" out of nowhere is
                # not a lesson, it is noise with a source. Lessons now come from
                # the parents (grounded in what is actually happening) and from
                # the operator, through the same ear.
                ng = getattr(self.agent, "neural_growth", None)
                if ng is not None and hasattr(ng, "structural_tick"):
                    ng.structural_tick()
        except Exception as e:
            self.last_neural_error = ("lang: " + type(e).__name__
                                      + ": " + str(e)[:120])
            self._adversity("failed", "the language organ broke: "
                                      + str(e)[:80], 0.4)
        interaction = self._interact_with_organ(action, ctx_text)
        if interaction:
            rec["interaction"] = interaction
        lang = getattr(self.agent, "language", None)
        if lang is not None and getattr(lang, "can_speak", lambda: False)():
            try:
                # A sentence first, and a single resonant word only if the chain has
                # nothing to carry. It used to be the other way round -- speak() is a
                # one-word readout of the current pool, which is why everything he
                # said unprompted was one word long while the organ that could say
                # six was reserved for the tutor and the API.
                #
                # The associates fallback is refused here on purpose. Unprompted, a
                # string of loose associates is not speech and does not look like a
                # young animal either; it looks like a broken one.
                sp = {}
                if hasattr(lang, "speak_sentence"):
                    sp = lang.speak_sentence(ctx_text, max_words=6,
                                             allow_associates=False) or {}
                if not sp.get("spoken"):
                    sp = lang.speak(ctx_text)
                if sp.get("spoken"):
                    rec["utterance"] = sp.get("utterance") or sp.get("sentence")
            except Exception as e:
                self.last_neural_error = "speak: " + type(e).__name__[:80]
        self.lived_time.add("house_heartbeat", decisions=1, beings=1)
        if time.time() - self._lived_save_at >= self._lived_save_interval:
            self.save_lived_time()
        self.state = self.observed_state()
        self.neural_ticks += 1
        self._note("neural",
                   "pool " + str(action) + " won the pulse ("
                   + ctx_text[:60] + ")", ["connectome"])
        return rec