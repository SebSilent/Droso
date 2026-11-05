"""A10 -- the resource ledger instrument, registered at experiments/MP-E10/registration.json under
`re_registration_2026_11_05_v1_2_BR_item1.a10_resource_ledger` before any run used it (R2).

What it measures, and what it refuses to guess:

  * peak RSS per phase. A sampler thread reads this process's own resident set through psutil on a fixed
    interval, timestamped on the same monotonic clock as the phase marks. A phase's peak is the largest
    sample whose timestamp falls inside that phase's measured window. If a phase ran shorter than the
    sampling interval and no sample landed inside it, the phase reports `samples: 0` and
    `peak_rss_bytes: null` -- it does NOT borrow its neighbour's number and it does not interpolate. That
    is the "reported as measured, never estimated" line.
  * the operating system's own peak, separately, when it can read it. On Windows psutil exposes
    `peak_wset`, on Linux `ru_maxrss`; these are recorded beside the sampled peak and never substituted
    for it, because the OS peak is per-process-lifetime, not per-phase.
  * VRAM, asserted rather than assumed: the ledger records whether torch is importable, whether CUDA was
    initialised, and the byte count it can actually see. A run that cannot show zero is not allowed to
    write "VRAM = 0".
  * cost per retained item: peak RSS of a phase divided by the items that phase retained, where retained
    means taught rows the organ answered `correct`. The definition is emitted with the number.

Usage from the bench:  LEDGER = ResourceLedger(); LEDGER.mark("live"); ... ; out["resource_ledger_a10"] =
LEDGER.finish(arms).  If psutil is missing the bench runs unchanged and the ledger says so in the artifact.
"""
from __future__ import annotations

import threading
import time


class ResourceLedger:
    def __init__(self, interval_s: float = 0.2):
        self.interval_s = interval_s
        self.samples: list[tuple[float, int]] = []
        self.marks: list[tuple[str, float]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.available = False
        self.unavailable_reason = None
        self._proc = None
        try:
            import psutil

            self._proc = psutil.Process()
            self.available = True
        except Exception as exc:  # psutil missing, or no /proc on this platform
            self.unavailable_reason = f"{type(exc).__name__}: {exc}"

    # ------------------------------------------------------------------ collection
    def start(self) -> None:
        if not self.available or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def _sample_loop(self) -> None:
        while not self._stop.is_set():
            try:
                rss = int(self._proc.memory_info().rss)
            except Exception:
                break
            self.samples.append((time.monotonic(), rss))
            self._stop.wait(self.interval_s)

    def mark(self, label: str) -> None:
        """A phase boundary, recorded when it happens -- not reconstructed afterwards."""
        self.marks.append((label, time.monotonic()))
        self.start()

    # ------------------------------------------------------------------ vram
    def vram(self) -> dict:
        out = {"asserted_zero": False, "method": None, "bytes_visible": None}
        try:
            import torch
        except Exception as exc:
            out["method"] = f"torch not importable ({type(exc).__name__}) -- nothing on this path can hold VRAM"
            out["asserted_zero"] = True
            out["bytes_visible"] = 0
            return out
        try:
            init = bool(torch.cuda.is_initialized())
            out["torch_importable"] = True
            out["cuda_initialised"] = init
            if init:
                out["bytes_visible"] = int(torch.cuda.memory_allocated())
                out["method"] = "torch.cuda.memory_allocated() after is_initialized() == True"
                out["asserted_zero"] = out["bytes_visible"] == 0
            else:
                out["bytes_visible"] = 0
                out["method"] = "torch imported; torch.cuda.is_initialized() is False, so no CUDA context exists to hold a byte"
                out["asserted_zero"] = True
        except Exception as exc:
            out["method"] = f"VRAM probe failed: {type(exc).__name__}: {exc}"
        return out

    def os_peak(self) -> dict:
        out = {"field": None, "bytes": None}
        if not self.available:
            return out
        mi = self._proc.memory_info()
        for name in ("peak_wset", "rss"):  # Windows exposes peak_wset; Linux falls back to current rss
            v = getattr(mi, name, None)
            if v is not None and name == "peak_wset":
                out = {"field": name, "bytes": int(v),
                       "note": "per-process lifetime peak, recorded beside the sampled per-phase peaks, "
                               "never substituted for them"}
                return out
        ru = None
        try:
            import resource

            ru = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        except Exception:
            pass
        if ru is not None:
            out = {"field": "ru_maxrss", "bytes": ru,
                   "note": "kilobytes on Linux; per-process lifetime peak, not per-phase"}
        return out

    # ------------------------------------------------------------------ report
    def finish(self, arms: dict) -> dict:
        if self._thread is not None:
            self._stop.set()
            self._thread.join(timeout=2.0)
        end = time.monotonic()
        windows = []
        for i, (label, t0) in enumerate(self.marks):
            t1 = self.marks[i + 1][1] if i + 1 < len(self.marks) else end
            inside = [rss for (t, rss) in self.samples if t0 <= t < t1]
            windows.append({
                "phase": label,
                "window_seconds": round(t1 - t0, 3),
                "samples": len(inside),
                "peak_rss_bytes": max(inside) if inside else None,
                "no_sample_landed_in_this_window": not inside,
            })
        retained = {}
        for mode, r in (arms or {}).items():
            # the bench passes its own artifact shape, where graded rows live under `probes`, keyed by the
            # plain depth string ("1"), while the phase mark is written "learn-d1:live". Both spellings are
            # indexed here; the first smoke run found that matching only the marked spelling silently left
            # every retained count null, which would have emptied cost-per-retained-item without saying so.
            for depth, ph in (r.get("probes") or r.get("depths") or {}).items():
                for phase, rows in ph.items():
                    n = sum(1 for x in rows if x.get("taught") and x.get("cls") == "correct")
                    key = f"{mode}-d{depth}-{phase}"
                    retained[key] = n
                    retained[f"{mode}-{depth}-{phase}"] = n
        for w in windows:
            key = None
            if ":" in w["phase"]:
                prefix, pp = w["phase"].split(":", 1)          # "learn-d1", "live"
                want = f"{prefix}-{pp}"                        # the mark IS the key's prefix, no leading dash
                key = want if want in retained else next(
                    (k for k in retained if k.endswith(f"-{want}")), None)
            n = retained.get(key) if key else None
            w["retained_items"] = n
            w["cost_per_retained_item_bytes"] = (
                round(w["peak_rss_bytes"] / n, 1)
                if w.get("peak_rss_bytes") and n else None)
        return {
            "instrument": "tools/mp_e10_resource_ledger.py",
            "registered_at": "experiments/MP-E10/registration.json -> "
                             "re_registration_2026_11_05_v1_2_BR_item1.a10_resource_ledger",
            "available": self.available,
            "unavailable_reason": self.unavailable_reason,
            "sampling_interval_seconds": self.interval_s,
            "n_samples": len(self.samples),
            "whole_run_peak_rss_bytes": max((r for _, r in self.samples), default=None),
            "per_phase": windows,
            "os_peak": self.os_peak(),
            "vram": self.vram(),
            "retained_items_by_phase": retained,
            "definition_of_cost_per_retained_item": "peak RSS of the phase window divided by taught rows the "
                "organ answered `correct` in that phase; null where no sample landed in the window or no item "
                "was retained -- never interpolated",
            "what_is_not_estimated": "phase boundaries come from mark() calls at the boundary itself; a phase "
                "with no sample in its window reports null and says so",
        }
