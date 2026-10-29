r"""Does counting generalise, and does it refuse where it must?

Replays the count-frequency tells (`the coat is wet` x3, `the coat is torn`) into
a fresh house and asks the targets, the three paraphrases and the controls
pre-registered in docs/speech_log.md. Also checks that a world-count question
(`how many times does the bell turn?`) is not hijacked and that defect B still
answers.
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
    ("target", "how many times did i tell you the coat is wet?", "three"),
    ("target", "how many things did i tell you about the coat?", "two"),
    ("target", "how many times did i tell you about the scarf?", "zero"),
    ("P1    ", "how many times did i say the coat is wet?", "three"),
    ("P2    ", "how many things did i tell you about the scarf?", "zero"),
    ("P3    ", "how many items did i tell you about the coat?", "two"),
    ("C1    ", "how many eggs did i mention first?", ""),
    ("C2    ", "did i ever tell you about the moon?", "no"),
    ("C3    ", "how many times does the bell turn?", ""),
]


def main() -> int:
    script = next(s for s in SCRIPTS if s["name"] == "count-frequency")
    turns = script["turns"]
    stop = next(k for k, st in enumerate(turns) if "ask" in st)

    sd = ROOT / "state" / "sessions" / "countprobe"
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
        print(f"{label} {'PASS' if good else 'FAIL'} said={got!r:12s} "
              f"src={src[:20]:20s} {ask}")
    print(f"TOTAL: {ok} pass, {bad} fail")
    shutil.rmtree(sd, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())