r"""What the mouth said, and what the trace says it was thinking.

Diagnosis only -- renders nothing, fixes nothing. Replays the tells that precede
one ask into a fresh house, puts that ask, and prints the reply plus the trace
keys that decide rendering (filler, source, verdict, reason).
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


def main() -> int:
    name = sys.argv[1]
    needle = sys.argv[2]
    script = next(s for s in SCRIPTS if s["name"] == name)
    turns = script["turns"]
    i = next(k for k, st in enumerate(turns)
             if "ask" in st and needle in st["ask"])

    sd = ROOT / "state" / "sessions" / "mouthprobe"
    if sd.exists():
        shutil.rmtree(sd)
    agent = build(sd)
    sess = Session(agent, beats=0)
    for st in turns[:i]:
        if "say" in st:
            sess.ask(st["say"], kind="tell")

    ask = turns[i]["ask"]
    print("ASK      :", ask)
    print("EXPECT   :", json.dumps(turns[i].get("expect", {}), sort_keys=True))
    said = sess.ask(ask)
    print("SAID     :", json.dumps(getattr(said, "text", said),
                                   ensure_ascii=False))
    tr = getattr(said, "trace", None) or {}
    keep = ("reason", "source", "recovered_filler", "verdict", "parser",
            "cue", "spoken")
    print("TRACE    :", json.dumps({k: tr.get(k) for k in keep
                                    if k in tr}, sort_keys=True)[:1200])
    print("ALLKEYS  :", sorted(tr.keys()))
    shutil.rmtree(sd, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())