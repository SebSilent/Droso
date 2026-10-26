# Timing probe for the accumulation turn-3 drift (drift_check_20261026_050019).
#
# The drift: CLI side spoke "vagabond pruned" on turn 3, HTTP side was silent.
# Hypothesis: the HTTP side's slower pacing (POST gaps 5s/4s/2s/2s after a 7s
# build gap) let the time-based SAN decay fire once between turns 1 and 2
# (>=10s since _last_decay), shrinking the spread component of act; the
# turn-3 thought gate (cosine resonance >= reply_threshold=0.55) flipped.
#
# This probe replays the HTTP side's exact timeline in a plain CLI process:
# build from the same shadow, set _last_decay 7s in the past (build->turn-1
# gap), then run the script's turns with the observed POST gaps as sleeps.
# Expected if the hypothesis holds: turn 1 matches the drift report, turn 3
# comes out silent (spoken=false) instead of "vagabond pruned".
#
# Read-only against the live tree: build(project_root=shadow), writes go to
# the probe's own session dir.

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import converse  # noqa: E402

SHADOW = ROOT / "state" / "sessions" / "drift_shadow_20261026_044855"
SESSION_DIR = ROOT / "state" / "sessions" / "drift_timing_probe_accumulation"

# The accumulation script's turns, verbatim from tools/scripts_fresh.json
# (as replayed in drift_check_20261026_050019.json).
TURNS = [
    ("tell", "the box is heavy"),
    ("tell", "the box is red"),
    ("tell", "the box is on the shelf"),
    ("ask", "how is the box"),
    ("ask", "where is the box"),
]
# Observed HTTP pacing: seconds to sleep BEFORE each turn (from the server
# log's POST timestamps: 04:51:57, 04:52:02, 04:52:06, 04:52:08, 04:52:10,
# with the build finishing ~04:51:50 and _last_decay set at organ
# construction ~then).  turn1 +7s after build, then +5, +4, +2, +2.
GAPS = [7.0, 5.0, 4.0, 2.0, 2.0]


def main() -> int:
    t0 = time.time()
    agent = converse.build(SESSION_DIR, project_root=str(SHADOW))
    lang = agent.language
    build_s = time.time() - t0
    # Anchor the decay clock as if the organ was built 7s before turn 1
    # (the observed build->first-POST gap).  The build itself takes ~20s,
    # so without this anchor the first gather would already be past the
    # 10s threshold and turn 1 would run decayed, unlike the HTTP side.
    lang._last_decay = time.time() - GAPS[0]
    session = converse.Session(agent, beats=2)
    print(f"build {build_s:.1f}s; decay anchored {GAPS[0]:.1f}s back")
    for i, ((kind, text), gap) in enumerate(zip(TURNS, GAPS)):
        if i > 0:
            time.sleep(gap)
        turn = session.ask(text, kind=kind)
        r = turn.get("reply") or {}
        said = str(r.get("utterance") or r.get("response") or "")
        spoken = bool(r.get("spoken"))
        extra = "" if spoken else (
            f" reason={r.get('reason')!r}"
            f" best_resonance={r.get('best_resonance')}"
            f" threshold={r.get('threshold')}")
        print(f"turn {turn['n']} [{kind}] said={text!r} -> "
              f"spoken={spoken} reply={said!r}{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())