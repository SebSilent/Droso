r"""Defect K: does the description rewrite generalise, and do its controls hold?

Replays the hop script's tells, then asks the target, the two pre-registered
paraphrases (written before the code) and the four controls. The controls are
the point: a rewrite that answers the reversal, or that disturbs a single-memory
question, is over-eager and reverts.
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
    ("target", "what does the thing the frost bites hold?", "door"),
    ("N1    ", "what is the thing the frost bites holding?", "door"),
    ("N2    ", "the thing the frost bites holds what?", "door"),
    ("C1    ", "does the door hold the frost?", ""),
    ("C2    ", "does the latch hold the door?", "yes"),
    ("C3    ", "what does the frost bite?", "latch"),
]


def main() -> int:
    script = next(s for s in SCRIPTS if s["name"] == "hop-and-inventory")
    turns = script["turns"]
    stop = next(k for k, st in enumerate(turns) if "ask" in st)

    sd = ROOT / "state" / "sessions" / "hopprobe"
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
                  or (reply or {}).get("response") or "").strip()
        src = str((reply or {}).get("source")
                  or (reply or {}).get("reason") or "")
        if want == "":
            mark = "PASS" if want not in got.lower() or not got else \
                   ("PASS" if got == "" else "FAIL")
            mark = "PASS" if got == "" else "FAIL"
        else:
            mark = "PASS" if want in got.lower() else "FAIL"
        ok += mark == "PASS"
        bad += mark == "FAIL"
        print(f"{label} {mark:4s} said={got[:34]!r:36s} src={src[:20]:20s} {ask}")
    print(f"TOTAL: {ok} pass, {bad} fail")
    shutil.rmtree(sd, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())