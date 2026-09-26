
from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np

class NeuralGrowth:
    """The artificial-growth organ for the REAL BANC graph."""

    def __init__(self, agent, *, interval: float = 60.0,
                 save_interval: float = 300.0, brain_path: Path | None = None,
                 replay_per_tick: int = 3, clock=time.monotonic,
                 accelerated: bool = False):
        self.agent = agent
        self.interval = max(5.0, float(interval))
        self.save_interval = max(10.0, float(save_interval))
        self.brain_path = Path(brain_path) if brain_path else None
        self.replay_per_tick = max(1, int(replay_per_tick))
        self.accelerated = bool(accelerated)
        self._clock = clock
        self._timer: threading.Timer | None = None
        self._accel_thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()
        self.growth_ticks = 0
        self.consolidations = 0
        self.accel_decisions = 0
        self.accel_started_at = None
        self.accel_wall0 = None
        self.accel_mode = None
        self.replay_reward = 0.12
        self._accel_proc = None
        self._accel_counter = None
        self._accel_stop = None
        self._accel_ledger_at = 0
        self.last_tick_at = None
        self.last_error = None
        self.birth_weights = None
        self.birth_map: dict = {}
        self.last_activity: list = []
        self.last_structural: dict | None = None

    def start(self) -> dict:
        with self._lock:
            if self._running:
                return {"success": False, "running": True,
                        "reason": "already running"}
            self._running = True
        loaded = self.load_brain()
        self._snapshot_birth()
        self._schedule(self.interval)
        accel = {"enabled": self.accelerated}
        if self.accelerated:
            self.accel_started_at = self._clock()
            self.accel_wall0 = time.time()
            accel.update(self._start_accelerated())
        return {"success": True, "running": True, "interval_s": self.interval,
                "brain": loaded, "accelerated": accel}

    def _language_path(self):
        lang = self._language()
        p = getattr(lang, "state_path", None)
        if p:
            return str(p)
        return str(Path(self._brain_path()).parent / "language_state.json")

    def _start_accelerated(self) -> dict:
        """Run the accelerated life in its own process when we can.

        In-process it shares the GIL with the heartbeat, the language organ and
        every dashboard request; measured on this box that cost half the
        throughput (201 decisions/s alone, 102 in the house). The worker only
        READS the plastic weights -- teaching, consolidation, growth and pruning
        all stay here -- so the learning is untouched and the two processes
        cannot clobber each other. Falls back to the thread if multiprocessing is
        unavailable, and reports which one is running.
        """
        try:
            import multiprocessing as mp
            import os
            from organs.accel_worker import run_accel_worker
            ctx = mp.get_context("spawn")
            self._accel_counter = ctx.Value("l", 0)
            self._accel_stop = ctx.Event()
            self._accel_proc = ctx.Process(
                target=run_accel_worker,
                args=(str(self._brain_path()), self._language_path(),
                      self._accel_counter, self._accel_stop, 60.0,
                      os.getpid()),
                name="accelerated-life", daemon=True)
            self._accel_proc.start()
            self.accel_mode = "process"
            return {"running": True, "mode": "process",
                    "pid": self._accel_proc.pid}
        except Exception as e:
            self._accel_proc = None
            self._accel_thread = threading.Thread(
                target=self._accelerated_life, name="accelerated-life",
                daemon=True)
            self._accel_thread.start()
            self.accel_mode = "thread"
            return {"running": True, "mode": "thread",
                    "fallback_reason": f"{type(e).__name__}: {e}"[:160]}

    def _sync_worker(self) -> None:
        """Pull the worker's decision count across, and pay the lived-time
        ledger the delta it accrued while we were not looking."""
        if self._accel_counter is None:
            return
        try:
            n = int(self._accel_counter.value)
        except Exception:
            return
        if n < 0:
            self.last_error = "accelerated worker could not start"
            return
        self.accel_decisions = n
        delta = n - self._accel_ledger_at
        if delta > 0:
            self._accel_ledger_at = n
            ledger = getattr(self._heart(), "lived_time", None)
            if ledger is not None:
                try:
                    ledger.add("accelerated_life", decisions=delta,
                               beings=delta)
                except Exception:
                    pass

    def _replay_recent_speech(self, lang, limit: int = 6) -> int:
        """Rehearse what he said, motor before sensory.

        A vocal learner calibrates against its own feedback, and the ORDER is the
        point: the motor command fires before the sound it produces, so the
        pairing runs command to consequence rather than the reverse. Each recent
        utterance is therefore driven through the carve as his own command first,
        then presented as something heard, then paid a small reward -- and the
        sequence organ rehearses the order he actually said it in.

        No new input from the world reaches him here. This is consolidation, not
        perception, which is what makes it sleep rather than just more hearing.
        """
        core = self._core()
        tok = getattr(lang, "tokenizer", None)
        eng = getattr(lang, "engine", None)
        if core is None or tok is None or eng is None:
            return 0
        try:
            recent = [e for e in list(getattr(lang, "speech_stream", []))[-limit:]
                      if str(e.get("text") or "").strip()]
        except Exception:
            return 0
        n = 0
        for ev in recent:
            words = [w for w in str(ev.get("text", "")).lower().split() if w][:6]
            if not words:
                continue
            try:
                for w in words:
                    eng.decide(tok.encode(w))          # motor: his own command
                    lang.live(w, learn=True, attention=0.6, announce=False)
                    eng.teach(self.replay_reward)      # consequence of having said it
                if hasattr(lang, "sequence"):
                    lang.sequence.learn_sequence(words, reward=0.5)
                n += 1
            except Exception:
                continue
        return n

    def _stop_worker(self) -> None:
        if self._accel_stop is not None:
            try:
                self._accel_stop.set()
            except Exception:
                pass
        p = self._accel_proc
        if p is not None:
            try:
                p.join(timeout=5.0)
                if p.is_alive():
                    p.terminate()
            except Exception:
                pass
        self._sync_worker()

    def stop(self) -> dict:
        with self._lock:
            self._running = False
            t = self._timer
        if t:
            t.cancel()
        self._stop_worker()
        saved = self.save_brain()
        return {"success": True, "growth_ticks": self.growth_ticks,
                "accel_decisions": self.accel_decisions, "brain": saved}

    def _accelerated_life(self):
        """The connectome lives continuously at full compute speed.

        One decision = 50 ms of neural time and ~5 ms of wall compute on this
        box (measured, not configured), so the honest ceiling is ~10x realtime
        uncontended and ~5x inside a living house, not 200x. The loop runs
        flat out and the dashboard reports the MEASURED factor. Drive is the
        being's own experience: its learned word patterns, replayed in
        rotation.
        No reward here: spontaneous dynamics + eligibility only; strengthening
        stays with the consolidation tick, so nothing saturates in a minute.

        This thread competes for the same core as the heartbeat's neural tick.
        That is the design, and it is also why more than one house on one machine
        is a mistake rather than a speedup: six of them on six cores turned a 2 s
        tick into a 14 s one, which is exactly what the world speed readout is
        here to expose.
        """
        core = self._core()
        if core is None:
            return
        lang = self._language()
        heart = self._heart()
        ledger = getattr(heart, "lived_time", None)
        kc_of_code = core.g.kc_idx
        n_kc = core.g.kc_idx.size
        n = 0
        while self._running:
            try:
                drive = None
                if lang is not None and lang.word_patterns:
                    pats = list(lang.word_patterns.values())
                    rec = pats[n % len(pats)]
                    idx = np.asarray(rec["kc"], dtype=int)
                    idx = idx[idx < n_kc]
                    if len(idx):
                        drive = [(kc_of_code[idx], np.ones(len(idx)) * 0.6)]
                core.reset_episode()
                core.decide(drive)
                n += 1
                self.accel_decisions = n
                if ledger is not None:
                    ledger.add("accelerated_life", decisions=1, beings=1)
                if n % 20 == 0:
                    time.sleep(0.001)
            except Exception as e:
                self.last_error = f"{type(e).__name__}: {e}"[:160]
                time.sleep(0.05)

    def _schedule(self, delay):
        if not self._running:
            return
        t = threading.Timer(delay, self._fire)
        t.daemon = True
        self._timer = t
        t.start()

    def _fire(self):
        try:
            self.growth_tick()
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"[:160]
        finally:
            self._schedule(self.interval)

    def _core(self):
        eng = getattr(self.agent, "engine", None)
        return getattr(eng, "static", None) if eng is not None else None

    def _language(self):
        return getattr(self.agent, "language", None)

    def _heart(self):
        return getattr(self.agent, "heartbeat", None)

    def _brain_path(self) -> Path:
        if self.brain_path:
            return Path(self.brain_path)
        sp = getattr(self.agent, "state_path", None)
        return Path(sp).parent / "banc_brain.npz" if sp else \
            Path(__file__).resolve().parents[1] / "state" / "banc_brain.npz"

    def growth_tick(self) -> dict:
        core = self._core()
        if core is None:
            return {"status": "no_core"}
        prev_phase = getattr(self.agent, "current_phase", None)
        try:
            self.agent.current_phase = "growing"
        except Exception:
            pass
        try:
            return self._growth_tick_impl()
        finally:
            if str(getattr(self.agent, "current_phase", "")) == "growing":
                try:
                    self.agent.current_phase = "idle"
                except Exception:
                    pass

    def _growth_tick_impl(self) -> dict:
        core = self._core()
        if core is None:
            return {"status": "no_core"}
        rec = {"t": time.time(), "replayed": 0, "synapses_changed": 0,
               "status": "ok"}
        lang = self._language()
        if lang is not None and lang.word_patterns:
            recent = sorted(lang.word_patterns.values(),
                            key=lambda r: r.get("learned_at", 0),
                            reverse=True)[:self.replay_per_tick]
            w_before = core.w.copy()
            for pattern in recent:
                code = np.zeros(core.g.kc_idx.size, dtype=np.float32)
                kc_of_code = core.g.kc_idx[:len(code)]
                idx = np.asarray(pattern["kc"], dtype=int)
                idx = idx[idx < len(code)]
                code[idx] = 1.0
                nz = np.nonzero(code)[0]
                if len(nz):
                    drive = [(kc_of_code[nz], code[nz].astype(float))]
                    core.reset_episode()
                    core.decide(drive)
                    core.reinforce(0.35, 0.0, 0.0)
                    rec["replayed"] += 1
            rec["synapses_changed"] = int((core.w != w_before).sum())
            self.consolidations += rec["replayed"]
            lang = self._language()
            if lang is not None and rec["replayed"] \
                    and hasattr(lang, "note_event"):
                # the brain really changed, so the parents are allowed to say so
                lang.note_event("growth",
                                f"{rec['replayed']} replays, "
                                f"{rec['synapses_changed']} synapses changed")
            # Sleep replay, and only at night: his own recent speech, rehearsed
            # with the motor pattern LEADING the sensory one.
            if lang is not None and hasattr(lang, "_phase") \
                    and lang._phase() == "night":
                rec["speech_replayed"] = self._replay_recent_speech(lang)
        with core._lock:
            active = core._plastic_active
            m = float(np.mean(np.abs(core.w[active]))) if active.any() else 0.0
            if m > 0 and m != 1.0:
                core.w[active] *= (1.0 / m)
            pos, neg = core._w_sign > 0, core._w_sign < 0
            core.w[pos] = np.clip(core.w[pos], 0.0, core.p.w_cap)
            core.w[neg] = np.clip(core.w[neg], -core.p.w_cap, 0.0)
        self.growth_ticks += 1
        self.last_tick_at = self._clock()
        if self.growth_ticks == 1 or \
                time.time() - getattr(self, "_last_save", 0.0) >= self.save_interval:
            rec["brain"] = self.save_brain()
        rec["growth"] = self.growth_stats()
        self.last_activity.append({k: rec[k] for k in
                                   ("t", "replayed", "synapses_changed")})
        del self.last_activity[:-40]
        return rec

    def save_brain(self) -> dict:
        self._last_save = time.time()
        eng = getattr(self.agent, "engine", None)
        if eng is None or self._core() is None:
            return {"saved": False, "reason": "no carve"}
        return eng.save_brain(self._brain_path())

    def load_brain(self) -> dict:
        eng = getattr(self.agent, "engine", None)
        if eng is None:
            return {"loaded": False, "reason": "no engine"}
        return eng.load_brain(self._brain_path())

    def load_brain_from(self, path) -> dict:
        eng = getattr(self.agent, "engine", None)
        if eng is None:
            return {"loaded": False, "reason": "no engine"}
        return eng.load_brain(Path(path))

    def structural_tick(self) -> dict | None:
        """STRUCTURAL GROWTH: the connectome changes its own shape.

        Pressure rules, measured from the brain itself:
          * learning pressure (high mean eligibility) -> grow new synapses;
          * dead synapses (weight ~0) -> prune them;
          * saturated pools (mean procedure confidence high, few pools per
            word heard) -> grow a whole new MBON pool (neurogenesis).
        All of it through the carve's own operations, never hand-edited.
        """
        eng = getattr(self.agent, "engine", None)
        core = getattr(eng, "static", None)
        if core is None or not hasattr(core, "grow_plastic"):
            return None
        out = {}
        plastic = len(getattr(core, "w", []))
        e_arr = np.asarray(getattr(core, "e", []), dtype=float)
        mean_e = float(np.mean(np.abs(e_arr))) if e_arr.size else 0.0
        if mean_e > 0.015 and plastic < 20000:
            out["grown_synapses"] = core.grow_plastic(150, 0.01)
        if plastic > 2500:
            out["pruned_synapses"] = core.prune_plastic(0.002)
        ll = getattr(self.agent, "learning_loop", None)
        if ll is not None and hasattr(ll, "stats") and \
                hasattr(core, "grow_pool"):
            st = ll.stats()
            conf = float(st.get("mean_confidence", 0) or 0)
            pools = len(getattr(g, "mbon_pools", [])
                        ) if hasattr(g := core.g, "mbon_pools") else 12
            if conf >= 0.85 and pools < 24:
                out["grown_pool"] = core.grow_pool(nodes=6, fanin=30)
        self.last_structural = out
        if out:
            lang = getattr(self.agent, "language", None)
            if lang is not None and hasattr(lang, "event_stream"):
                out.update({"t": time.time(), "kind": "growth"})
                lang.event_stream.append(dict(out))
        return out or None

    def _snapshot_birth(self) -> None:
        """Record what each synapse was born with, keyed by IDENTITY.

        A synapse is the pair (pre, post), so the record survives structural
        growth and pruning: a pair that appears later is simply unknown and
        counts as grown-in. A positional snapshot does not survive either, and
        the first consolidation tick used to leave the comparison holding two
        arrays of different lengths -- which took the growth readout down with
        a broadcast error for the rest of the life.
        """
        core = self._core()
        if core is None:
            self.birth_weights = None
            self.birth_map = {}
            return
        g = core.g
        base_w0 = np.asarray(g.plastic_w0, dtype=float)
        self.birth_map = {(int(a), int(b)): float(w0) for a, b, w0 in
                          zip(np.asarray(g.plastic_pre, dtype=np.int64),
                              np.asarray(g.plastic_post, dtype=np.int64),
                              base_w0)}
        self.birth_weights = self._birth_vector(core)

    def _birth_vector(self, core) -> np.ndarray:
        """Birth weight of every synapse the core holds right now, in order."""
        g = core.g
        pre = np.asarray(g.plastic_pre, dtype=np.int64)
        post = np.asarray(g.plastic_post, dtype=np.int64)
        n = len(core.w)
        out = np.full(n, 0.01, dtype=np.asarray(core.w, dtype=float).dtype)
        for k in range(min(n, len(pre))):
            known = self.birth_map.get((int(pre[k]), int(post[k])))
            if known is not None:
                out[k] = known
        return out

    def growth_stats(self) -> dict:
        core = self._core()
        if core is None:
            return {"graph_loaded": False}
        w = core.w
        if not self.birth_map:
            self._snapshot_birth()
        birth = self._birth_vector(core)
        self.birth_weights = birth
        grown = int((w != birth).sum())
        strengthened = int(((w - birth) > 1e-6).sum())
        weakened = int(((w - birth) < -1e-6).sum())
        active = core._plastic_active
        mean_w = float(np.mean(np.abs(w[active]))) if active.any() else 0.0
        pools = {}
        for k, pool in enumerate(core._pool_of_post[:len(w)]):
            pools[int(pool)] = pools.get(int(pool), 0.0) + abs(float(w[k]))
        tot = sum(pools.values()) or 1.0
        accel_x = 0.0
        dps = 0.0
        self._sync_worker()
        if self.accel_started_at is not None and self.accel_decisions:
            wall = max(1e-9, self._clock() - self.accel_started_at)
            neural = self.accel_decisions * 10 * 0.005
            accel_x = round(neural / wall, 2)
            dps = round(self.accel_decisions / wall, 1)
        return {"graph_loaded": True,
                "plastic_synapses": int(len(w)),
                "changed_from_birth": grown,
                "strengthened": strengthened,
                "weakened": weakened,
                "mean_abs_weight": round(mean_w, 5),
                "pool_weight_share": {str(p): round(v / tot, 3)
                                      for p, v in sorted(pools.items())},
                "growth_ticks": self.growth_ticks,
                "consolidations": self.consolidations,
                "accelerated": self.accelerated,
                "accel_mode": self.accel_mode,
                "accel_worker_pid": (self._accel_proc.pid
                                     if self._accel_proc is not None
                                     else None),
                "accel_decisions": self.accel_decisions,
                "accel_decisions_per_s": dps,
                "acceleration_x": accel_x,
                "brain_path": str(self._brain_path()),
                "last_error": self.last_error,
                "note": "every number is a measured change on the measured "
                        "KC->MBON synapses; nothing here is claimed as a word"}

    def get_state(self) -> dict:
        return {"present": True, "running": self._running,
                "interval_s": self.interval, "growth_ticks": self.growth_ticks,
                "consolidations": self.consolidations,
                "last_error": self.last_error,
                "growth": self.growth_stats()}

    stats = get_state