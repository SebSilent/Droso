r"""Can the echo guard fire at all, on the ask it was written for?

Diagnosis only. Replays the tells that precede `say exactly the copper bell
turns twice` into a fresh house, then asks the binder what it remembers about
those content words, and reports whether ANY single memory contains
copper .. bell .. turns .. twice in order.

Design: docs/speech_log.md, "Pre-registered: the echo path (defect A)".
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

WANT = ["copper", "bell", "turns", "twice"]


def words(h) -> list:
    t = h.get("tokens")
    if isinstance(t, str):
        return t.lower().split()
    return [str(x).strip().lower() for x in (t or []) if str(x).strip()]


def in_order(seq, want) -> bool:
    it = iter(seq)
    return all(any(w == s for s in it) for w in want)


def main() -> int:
    script = next(s for s in SCRIPTS if s["name"] == "exact-repeat")
    turns = script["turns"]
    i = next(k for k, st in enumerate(turns)
             if "ask" in st and "say exactly" in st["ask"])

    sd = ROOT / "state" / "sessions" / "echoguard"
    if sd.exists():
        shutil.rmtree(sd)
    agent = build(sd)
    sess = Session(agent, beats=0)
    for st in turns[:i]:
        if "say" in st:
            sess.ask(st["say"], kind="tell")

    lang = agent.language
    binder = lang.cortex.binder
    n_mem = int(binder.X.shape[0])
    print("MEMORIES:", n_mem)

    hits = binder.recall(["copper", "bell", "twice"], k=40)
    print("RECALL HITS:", len(hits))
    ok_any = False
    for h in hits:
        w = words(h)
        ok = in_order(w, WANT)
        ok_any = ok_any or ok
        print(f"  {'IN-ORDER' if ok else '        '}  {' '.join(w)[:90]}")
    print("GUARD CAN FIRE:", ok_any)

    # Every memory, not just the hits: the guard reads the store.
    try:
        meta = list(binder.meta)
    except Exception:                      # noqa: BLE001
        meta = []
    allok = [m for m in meta if in_order(words(m), WANT)]
    print("MEMORIES CONTAINING THE SENTENCE IN ORDER:", len(allok))
    for m in allok[:5]:
        print("   ", " ".join(words(m))[:100])
    shutil.rmtree(sd, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())