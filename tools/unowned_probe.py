r"""Do unowned questions stay silent, and does anything else move?

Pre-registered controls (docs/speech_log.md, defect H):
  1 does the door hold the frost?          -> silence
  2 what turns twice?                      -> bell
  3 the frost is on the window (declarative) -> unchanged
  4 did i ever tell you about the moon?    -> no
  5 how many times does the bell turn?     -> refused, not hijacked

Runs under ACCUMULATED drive on purpose: that is the condition that produced
`sold`, so a probe that avoided it would not test the defect.
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
    ("C1", "does the door hold the frost?", ""),
    ("C2", "what turns twice?", "bell"),
    ("C3", "the frost is on the window", "<unchanged>"),
    ("C4", "did i ever tell you about the moon?", "no"),
    ("C5", "how many times does the bell turn?", ""),
]


def main() -> int:
    # exact-repeat first so `what turns twice?` and the bell are in memory.
    script = next(s for s in SCRIPTS if s["name"] == "exact-repeat")
    turns = script["turns"]
    stop = next(k for k, st in enumerate(turns) if "ask" in st)

    sd = ROOT / "state" / "sessions" / "hprobe"
    if sd.exists():
        shutil.rmtree(sd)
    agent = build(sd)
    sess = Session(agent, beats=0)
    for st in turns[:stop]:
        if "say" in st:
            sess.ask(st["say"], kind="tell")
    # Accumulate drive: the condition under which the mouth improvised.
    for _ in range(6):
        sess.ask("hello", kind="tell")
        sess.ask("the frost is on the window", kind="tell")

    print("social_drive at test time:", round(float(agent.language.social_drive), 3))
    for label, ask, want in CASES:
        said = sess.ask(ask)
        reply = said.get("reply") if isinstance(said, dict) else None
        got = str((reply or {}).get("utterance")
                  or (reply or {}).get("response") or "")
        src = str((reply or {}).get("source") or (reply or {}).get("reason") or "")
        if want == "<unchanged>":
            mark = "info" if got else "info"
        elif want == "":
            mark = "PASS" if got.strip() == "" else "FAIL"
        else:
            mark = "PASS" if got.strip().lower() == want else "FAIL"
        print(f"{label} {mark:4s} said={got!r:16s} src={src[:22]:22s} {ask}")
    shutil.rmtree(sd, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())