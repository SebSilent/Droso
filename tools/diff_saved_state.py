"""Diff the post-run language state of two CLI runs from the same shadow.

Compares scalar organ fields and array fields (norms + a few cells) between
the drift check's CLI side (04:50) and the repro run (05:2x).  Turn-dependent
logs (thought_stream, narration, events) are skipped except for their lengths.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

A = ROOT / "state" / "sessions" / "drift_cli_accumulation_20261026_045029" / \
    "language_state.json"
B = ROOT / "state" / "sessions" / "repro_cli_1" / "language_state.json"

SKIP = {"thought_stream", "narration", "events", "diary", "log", "history"}


def flat(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flat(v, key + "."))
        elif isinstance(v, list):
            out[key + ".__len__"] = len(v)
        else:
            out[key] = v
    return out


def main() -> int:
    a = json.loads(A.read_text(encoding="utf-8"))
    b = json.loads(B.read_text(encoding="utf-8"))
    fa, fb = flat(a), flat(b)
    keys = sorted(set(fa) | set(fb))
    diffs = []
    for k in keys:
        if any(s in k.lower() for s in SKIP):
            continue
        va, vb = fa.get(k, "<absent>"), fb.get(k, "<absent>")
        if isinstance(va, float) and isinstance(vb, float):
            if abs(va - vb) > 1e-6:
                diffs.append((k, va, vb))
        elif va != vb:
            diffs.append((k, va, vb))
    print(f"compared {len(keys)} scalar/list-length keys; "
          f"{len(diffs)} differ")
    for k, va, vb in diffs[:80]:
        print(f"  {k}: drift={va!r} repro={vb!r}")
    if len(diffs) > 80:
        print(f"  ... and {len(diffs) - 80} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())