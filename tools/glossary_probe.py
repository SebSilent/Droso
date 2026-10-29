r"""What the glossary ask gets today, and what provenance says he used.

Diagnosis only. Replays the exact-repeat tells into a fresh house, asks
`which word did i use for the metal?`, prints the reply, then reports the words
carrying who == "you" -- the same provenance the second brain trusts -- so the
pre-registered candidate set can be checked against reality rather than assumed.
"""
from __future__ import annotations

import json
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.converse import Session, build  # noqa: E402

SCRIPTS = json.loads((ROOT / "tools" / "scripts_heldout.json")
                     .read_text(encoding="utf-8"))
if isinstance(SCRIPTS, dict):
    SCRIPTS = SCRIPTS.get("scripts", [])


def words(h):
    t = h.get("tokens")
    if isinstance(t, str):
        return t.lower().split()
    return [str(x).strip().lower() for x in (t or []) if str(x).strip()]


def main() -> int:
    script = next(s for s in SCRIPTS if s["name"] == "exact-repeat")
    turns = script["turns"]
    i = next(k for k, st in enumerate(turns)
             if "ask" in st and "metal" in st["ask"])

    sd = ROOT / "state" / "sessions" / "glossaryprobe"
    if sd.exists():
        shutil.rmtree(sd)
    agent = build(sd)
    sess = Session(agent, beats=0)
    for st in turns[:i]:
        if "say" in st:
            sess.ask(st["say"], kind="tell")

    ask = turns[i]["ask"]
    said = sess.ask(ask)
    print("ASK   :", ask)
    print("EXPECT:", json.dumps(turns[i].get("expect", {}), sort_keys=True))
    print("SAID  :", json.dumps(getattr(said, "text", said), ensure_ascii=False))

    lang = agent.language
    binder = lang.cortex.binder
    meta = list(binder.meta)
    print("META KEYS:", sorted(meta[0].keys()) if meta else None)
    t0 = float(getattr(lang, "session_t0", 0.0) or 0.0)
    print("SESSION_T0:", t0)
    mine = [m for m in meta
            if str(m.get("who") or "") == "you"
            and float(m.get("when", 0.0) or 0.0) >= t0]
    print("MEMORIES BY 'you' THIS SESSION:", len(mine))
    cnt = Counter()
    for m in mine:
        cnt.update(words(m))
    print("WORDS HE USED:", dict(cnt))
    session_all = [m for m in meta if float(m.get("when", 0.0) or 0.0) >= t0]
    print("MEMORIES THIS SESSION (any who):", len(session_all),
          "| who values:",
          sorted({str(m.get("who")) for m in session_all}))
    shutil.rmtree(sd, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())