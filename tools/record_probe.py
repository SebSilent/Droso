r"""Does record absence answer the record, refuse the world, and not negate?

Replays the count-frequency tells into a fresh house and asks the target, the
three paraphrases and the three controls pre-registered in docs/speech_log.md.
C1 is the one that matters most: a blanket negator says `no` there and fails.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.converse import Session, build  # noqa: E402

SCRIPTS = json.loads((ROOT / "tools" / "scripts_heldout.json")
                     .read_text(encoding="utf-8"))
if isinstance(SCRIPTS, dict):
    SCRIPTS = SCRIPTS.get("scripts", [])

CASES = [
    ("target", "did i ever tell you about the moon?", "no"),
    ("P1    ", "did i ever mention the moon to you?", "no"),
    ("P2    ", "have i told you anything about the moon?", "no"),
    ("P3    ", "did i ever tell you about the kite?", "no"),
    ("C1    ", "did i ever tell you about the coat?", "yes"),
    ("C2    ", "does the door hold the frost?", ""),
    ("C3    ", "how many things did i tell you about the coat?", ""),
]


def main() -> int:
    script = next(s for s in SCRIPTS if s["name"] == "count-frequency")
    turns = script["turns"]
    stop = next(k for k, st in enumerate(turns) if "ask" in st)

    sd = ROOT / "state" / "sessions" / "recordprobe"
    if sd.exists():
        shutil.rmtree(sd)
    agent = build(sd)
    sess = Session(agent, beats=0)
    for st in turns[:stop]:
        if "say" in st:
            sess.ask(st["say"], kind="tell")

    ok = bad = 0
    for label, ask, want in CASES:
        said = sess.ask(ask)
        reply = said.get("reply") if isinstance(said, dict) else None
        got = str((reply or {}).get("utterance")
                  or (reply or {}).get("response") or "")
        src = str((reply or {}).get("source") or (reply or {}).get("reason") or "")
        if want == "":
            good = got.strip() == ""
        else:
            good = got.strip().lower() == want
        ok += bool(good)
        bad += not good
        print(f"{label} {'PASS' if good else 'FAIL'} said={got!r:14s} "
              f"src={src[:18]:18s} {ask}")
    print(f"TOTAL: {ok} pass, {bad} fail")
    shutil.rmtree(sd, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())