r"""Does disjunctive resolution generalise, and does it refuse when it should?

Replays the conjunction-and-absence tells into a fresh house, asks the target,
the three paraphrases and the two controls pre-registered in
docs/speech_log.md, and reports what came out of the mouth.
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
    ("target", "is the coat dry or wet?", "wet"),
    ("P1    ", "is the coat wet or dry?", "wet"),
    ("P2    ", "the coat, is it dry or wet?", "wet"),
    ("P3    ", "would you say the coat is dry or wet?", "wet"),
    ("C1    ", "is the scarf dry or wet?", "wet"),
    ("C2    ", "is the hook dry or wet?", ""),          # must be silence
]


def main() -> int:
    script = next(s for s in SCRIPTS if s["name"] == "conjunction-and-absence")
    turns = script["turns"]
    stop = next(k for k, st in enumerate(turns) if "ask" in st)

    sd = ROOT / "state" / "sessions" / "disjprobe"
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
        good = (want == "" and want not in got) or \
               (want != "" and want.lower() in got.lower() and want.lower()
                and len(got.split()) <= 2)
        ok += bool(good)
        bad += not good
        print(f"{label} {'PASS' if good else 'FAIL'} said={got!r:26s} "
              f"src={src[:18]:18s} {ask}")
    print(f"TOTAL: {ok} pass, {bad} fail")
    shutil.rmtree(sd, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())