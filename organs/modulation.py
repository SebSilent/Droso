"""Modulation: the same wiring, computing something different.

A connectome does not determine what a circuit computes. Identical anatomy under
different chemistry is a different machine -- that is how small brains get large
repertoires without growing a single neuron, and it is the cheapest source of
behavioural range available to us. So this organ adds no cells and no synapses.
It reads the body and the moment, and turns four dials on the carve that is
already there.

THE FOUR DIALS

arousal      input gain and speed of dynamics. A surprising moment is perceived
             harder and settles faster.
tone         the leak. Tired tissue forgets between sub-steps; rested tissue
             holds its state and integrates further.
plasticity   how hard the teaching signal writes.
exploration  how often the winning pool is overridden.

Nothing here is a mood label painted on a dashboard. Each dial multiplies a
parameter the propagation loop actually uses, so the same sentence presented at
two different arousal levels settles a different trajectory and leaves a
different trace.

THE INVERTED U

Plasticity is not monotonic in arousal: it rises, peaks, and then falls. That is
the Yerkes-Dodson shape, and rather than assert it we make it a property of this
animal and then MEASURE it -- every teach records the arousal it happened at and
the weight change it produced, in a ring buffer, so the curve can be plotted from
his own life instead of from a textbook. If the peak is in the wrong place, that
is a finding about him, not a bug to hide.

Everything is bounded, and every bound is a constant at the top of the file,
because a modulator that can drive gain without limit is just a way of crashing
a brain slowly.
"""
from __future__ import annotations

import time
from collections import deque

import numpy as np

# bounds, so modulation can bend the dynamics but never break them
GAIN_RANGE = (0.5, 2.5)
LEAK_RANGE = (0.30, 0.85)
PLASTICITY_RANGE = (0.2, 2.5)
EPSILON_RANGE = (0.02, 0.45)
# where the inverted U peaks, in normalised arousal
OPTIMAL_AROUSAL = 0.55
U_WIDTH = 0.45


class ModulationOrgan:
    """Four dials on the existing carve, driven by his actual state."""

    def __init__(self, core, history: int = 400):
        self.core = core
        self.base = {
            "input_gain": float(getattr(core.p, "input_gain", 2.0)),
            "leak": float(getattr(core.p, "leak", 0.6)),
            "lr": float(getattr(core.p, "lr", 3.0)),
            "epsilon": float(getattr(core.p, "epsilon", 0.15)),
        }
        self.state = {"arousal": 0.5, "tone": 0.5, "plasticity": 1.0,
                      "exploration": 0.5}
        self.applied: dict = {}
        self.updates = 0
        self.last_surprise = 0.0
        # (arousal, plasticity multiplier, |weight change|) for the U curve
        self.learning_samples: deque = deque(maxlen=int(history))
        self._last_w = None

    # ------------------------------------------------------------------
    def _u(self, arousal: float) -> float:
        """Inverted U: 0.2 at both extremes, 1.0 at the optimum."""
        d = (float(arousal) - OPTIMAL_AROUSAL) / U_WIDTH
        return float(np.exp(-0.5 * d * d))

    def update(self, *, energy: float = 0.8, need_social: float = 0.3,
               need_novelty: float = 0.2, mood: float = 0.5,
               surprise: float = 0.0, adversity: float = 0.0,
               phase: str = "day") -> dict:
        """Read the body and the moment, turn the dials.

        Every input is a real measured quantity from somewhere else in him: the
        language organ's body state, the higher cortex's prediction error, the
        adversity channel, the world clock's phase. Nothing is invented here.
        """
        energy = float(np.clip(energy, 0.0, 1.0))
        surprise = float(np.clip(surprise, 0.0, 1.0))
        adversity = float(np.clip(adversity, 0.0, 1.0))
        self.last_surprise = surprise

        # arousal: surprise and need wake him; exhaustion and night quiet him
        arousal = float(np.clip(
            0.25 + 0.85 * surprise + 0.35 * float(np.clip(need_novelty, 0, 1))
            + 0.45 * adversity - 0.45 * (1.0 - energy)
            - (0.20 if phase == "night" else 0.0), 0.0, 1.0))
        # tone: rested tissue integrates, tired tissue leaks
        tone = float(np.clip(0.2 + 0.8 * energy + 0.15 * mood, 0.0, 1.0))
        u = self._u(arousal)
        plasticity = float(np.clip(0.35 + 0.9 * u, 0.0, 1.0))
        # exploration: novelty seeking raises it, exhaustion and company lower it
        exploration = float(np.clip(
            0.15 + 0.7 * float(np.clip(need_novelty, 0, 1))
            + 0.25 * surprise - 0.35 * (1.0 - energy)
            - 0.25 * float(np.clip(need_social, 0, 1)), 0.0, 1.0))

        self.state = {"arousal": round(arousal, 4), "tone": round(tone, 4),
                      "plasticity": round(plasticity, 4),
                      "exploration": round(exploration, 4),
                      "u_component": round(u, 4)}
        self._apply()
        self.updates += 1
        return dict(self.state)

    def _apply(self) -> None:
        """Turn the dials into the parameters the propagation loop reads."""
        p = self.core.p
        s = self.state
        lo, hi = GAIN_RANGE
        gain = self.base["input_gain"] * (lo + (hi - lo) * s["arousal"]) / 1.25
        lo, hi = LEAK_RANGE
        leak = lo + (hi - lo) * s["tone"]
        lo, hi = PLASTICITY_RANGE
        lr = self.base["lr"] * (lo + (hi - lo) * s["plasticity"]) / 1.35
        lo, hi = EPSILON_RANGE
        eps = lo + (hi - lo) * s["exploration"]
        try:
            p.input_gain = float(np.clip(gain, *GAIN_RANGE))
            p.leak = float(np.clip(leak, *LEAK_RANGE))
            p.lr = float(np.clip(lr, *PLASTICITY_RANGE))
            p.epsilon = float(np.clip(eps, *EPSILON_RANGE))
        except Exception:
            return
        self.applied = {"input_gain": round(p.input_gain, 4),
                        "leak": round(p.leak, 4), "lr": round(p.lr, 4),
                        "epsilon": round(p.epsilon, 4)}

    # ------------------------------------------------------------------
    def note_learning(self) -> None:
        """Sample the U curve from his own life: what arousal was he at, and how
        much did his synapses actually move?"""
        try:
            w = np.asarray(self.core.w, dtype=float)
        except Exception:
            return
        if self._last_w is not None and self._last_w.shape == w.shape:
            delta = float(np.mean(np.abs(w - self._last_w)))
            self.learning_samples.append(
                (self.state["arousal"], self.state["plasticity"], delta))
        self._last_w = w.copy()

    def u_curve(self, bins: int = 8) -> dict:
        """The Yerkes-Dodson curve, measured rather than asserted."""
        if not self.learning_samples:
            return {"bins": [], "note": "no learning sampled yet"}
        xs = np.array([s[0] for s in self.learning_samples], dtype=float)
        ys = np.array([s[2] for s in self.learning_samples], dtype=float)
        edges = np.linspace(0.0, 1.0, bins + 1)
        out = []
        for i in range(bins):
            m = (xs >= edges[i]) & (xs < edges[i + 1] if i < bins - 1 else xs <= 1.0)
            if m.any():
                out.append({"arousal_mid": round(float((edges[i] + edges[i + 1]) / 2), 3),
                            "n": int(m.sum()),
                            "mean_weight_change": round(float(ys[m].mean()), 8),
                            "predicted_u": round(self._u(
                                float((edges[i] + edges[i + 1]) / 2)), 4)})
        peak = max(out, key=lambda r: r["mean_weight_change"]) if out else None
        return {"bins": out, "samples": len(self.learning_samples),
                "measured_peak_arousal": peak["arousal_mid"] if peak else None,
                "declared_optimum": OPTIMAL_AROUSAL}

    def state_report(self) -> dict:
        return {"dials": dict(self.state), "applied_to_carve": dict(self.applied),
                "baseline": dict(self.base), "updates": self.updates,
                "last_surprise": round(self.last_surprise, 4),
                "bounds": {"input_gain": GAIN_RANGE, "leak": LEAK_RANGE,
                           "lr": PLASTICITY_RANGE, "epsilon": EPSILON_RANGE},
                "u_curve": self.u_curve(),
                "note": "no cells and no synapses added: the same carve, "
                        "reconfigured"}
