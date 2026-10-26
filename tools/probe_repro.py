"""Run the drift check's CLI side twice from the same shadow.

If the two runs' replies differ, the reply chain is per-process stochastic
(unseeded numpy global RNG in the beats' mood drift and the attention gate)
and the drift report's turn-3 flip is threshold noise, not a systematic
HTTP-vs-CLI difference.  If they match, the procedure is deterministic and
whatever differed in probe_drift_timing (the _last_decay anchor) is real.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import converse                      # noqa: E402
import drift_check as dc             # noqa: E402

SHADOW = ROOT / "state" / "sessions" / "drift_shadow_20261026_044855"
SCRIPTS = json.loads((ROOT / "tools" / "scripts.json").read_text(
    encoding="utf-8"))["scripts"]


def pick_script() -> dict:
    for s in SCRIPTS:
        if "box is heavy" in json.dumps(s):
            return s
    raise SystemExit("no script mentions 'box is heavy'")


def main() -> int:
    script = pick_script()
    print("script:", script.get("name"))
    runs = []
    for i in (1, 2):
        sdir = ROOT / "state" / "sessions" / f"repro_cli_{i}"
        turns = dc.run_cli_side(script, SHADOW, sdir)
        runs.append(turns)
        for t in turns:
            print(f"  run{i} [{t['kind']}] said={t['said']!r} "
                  f"-> {t['reply_text']!r}")
    same = all(
        a["reply_text"] == b["reply_text"] and a["spoken"] == b["spoken"]
        for a, b in zip(runs[0], runs[1]))
    print("runs identical:", same)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())