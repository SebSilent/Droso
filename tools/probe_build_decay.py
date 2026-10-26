"""Does the build itself fire the SAN time-decay, and does it vary?

Builds the agent twice in one process from the same shadow, wrapping
NeuralLanguage.live to timestamp every call and count decay firings
(_last_decay advancing).  Compares post-build san_w between the two builds:
if they differ, the build's wiring path is time-dependent (the decay fired a
different number of times) and that is the generation effect.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import converse                                    # noqa: E402
from organs import neural_language as nl           # noqa: E402

SHADOW = ROOT / "state" / "sessions" / "drift_shadow_20261026_044855"
PROBE_DIR = ROOT / "state" / "sessions" / "probe_tmp"


def build_once(tag: str, calls: list) -> tuple:
    orig_live = nl.NeuralLanguage.live
    t0 = time.time()

    def wrapped(self, text, *a, **k):
        r = orig_live(self, text, *a, **k)
        calls.append({"tag": tag, "at": round(time.time() - t0, 2),
                      "text": str(text)[:40]})
        return r

    nl.NeuralLanguage.live = wrapped
    try:
        agent = converse.build(PROBE_DIR, project_root=str(SHADOW))
    finally:
        nl.NeuralLanguage.live = orig_live
    lang = agent.language
    fired = lang._last_decay - t0 > 10.0
    return agent, lang, time.time() - t0, fired, t0


def main() -> int:
    out = {}
    calls: list = []
    a1, l1, d1, f1, t01 = build_once("b1", calls)
    w1 = l1.san_w.copy()
    ld1 = float(l1._last_decay) - t01
    n1 = sum(1 for c in calls if c["tag"] == "b1")
    a2, l2, d2, f2, t02 = build_once("b2", calls)
    w2 = l2.san_w.copy()
    ld2 = float(l2._last_decay) - t02
    n2 = sum(1 for c in calls if c["tag"] == "b2")
    same = bool((w1 == w2).all())
    diff = float(abs(w1 - w2).sum())
    nz = int(((w1 != w2).any(axis=1) | (w1 != w2).any(axis=0)).sum())
    out.update({"build1_s": round(d1, 2), "build1_live_calls": n1,
                "build1_decay_fired": f1, "build1_last_decay_at": round(ld1, 2),
                "build2_s": round(d2, 2), "build2_live_calls": n2,
                "build2_decay_fired": f2, "build2_last_decay_at": round(ld2, 2),
                "san_w_identical": same, "san_w_absdiff": round(diff, 6),
                "san_w_rows_touched": nz})
    print(json.dumps(out, indent=1))
    first = [c for c in calls if c["tag"] == "b1"][:6]
    last = [c for c in calls if c["tag"] == "b1"][-6:]
    print("b1 first live calls:", json.dumps(first))
    print("b1 last live calls:", json.dumps(last))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())