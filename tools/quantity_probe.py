r"""Does content arithmetic generalise, and does it leak into the count path?

Replays the quantity-change tells (`there are four eggs in the basket`,
`then two eggs break`) and asks the three targets, the three pre-registered
paraphrases, the yes/no question, and two controls: a record count (must still
be answered by the count path) and a world count (must stay refused).
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
    ("target", "how many eggs did i mention first?", "four"),
    ("target", "how many eggs broke?", "two"),
    ("target", "did any egg break?", "yes"),
    ("target", "how many eggs are left in the basket?", "two"),
    ("P1    ", "how many eggs did i say break?", "two"),
    ("P2    ", "how many eggs were there at the start?", "four"),
    ("P3    ", "how many eggs remain in the basket?", "two"),
    ("N1    ", "how many eggs did we begin with?", "four"),
    ("N2    ", "what count of eggs was there originally?", "four"),
    ("C1    ", "how many times did i tell you the eggs are in the basket?", "?"),
    ("C2    ", "how many times does the bell turn?", ""),
]


def main() -> int:
    script = next(s for s in SCRIPTS if s["name"] == "quantity-change")
    turns = script["turns"]
    stop = next(k for k, st in enumerate(turns) if "ask" in st)

    sd = ROOT / "state" / "sessions" / "qtyprobe"
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
        if want == "?":
            mark = "info"
        elif want == "":
            mark = "PASS" if got.strip() == "" else "FAIL"
        else:
            mark = "PASS" if got.strip().lower() == want else "FAIL"
        ok += mark == "PASS"
        bad += mark == "FAIL"
        print(f"{label} {mark:4s} said={got!r:10s} src={src[:22]:22s} {ask}")
    print(f"TOTAL: {ok} pass, {bad} fail")
    shutil.rmtree(sd, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())