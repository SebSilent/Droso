r"""Which clause of _shape_matches refused, and on what tokens.

Not a fix. It replays the tells that precede one ask into a fresh house, puts
that one ask, and wraps `_shape_matches` so every candidate the arbiter offers
is printed with the outcome of each guard. Design: docs/speech_log.md,
"Pre-registered: the instrument fix, and how the veto may be judged".
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from organs.stemming import stem          # noqa: E402
from tools.converse import Session, build  # noqa: E402

SCRIPTS = json.loads((ROOT / "tools" / "scripts_heldout.json")
                     .read_text(encoding="utf-8"))
if isinstance(SCRIPTS, dict):
    SCRIPTS = SCRIPTS.get("scripts", [])


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "hop-and-inventory"
    needle = sys.argv[2] if len(sys.argv) > 2 else "thing the frost"
    script = next(s for s in SCRIPTS if s["name"] == name)
    turns = script["turns"]
    i = next(k for k, st in enumerate(turns)
             if "ask" in st and needle in st["ask"])

    sd = ROOT / "state" / "sessions" / "vetoprobe"
    if sd.exists():
        shutil.rmtree(sd)
    agent = build(sd)
    sess = Session(agent, beats=0)
    for st in turns[:i]:
        if "say" in st:
            sess.ask(st["say"], kind="tell")

    ask = turns[i]["ask"]
    lang = agent.language                 # NeuralLanguage, not the agent
    shape = None
    try:
        shape = lang._question_shape(re.findall(r"[a-z']+", ask.lower()))
    except Exception as exc:               # noqa: BLE001
        print("question_shape failed:", exc)
    print("ASK     :", ask)
    print("SHAPE   :", json.dumps(shape, sort_keys=True))

    orig = lang._shape_matches
    rows = []

    def probe(self, shp, tokens=None, *rest):
        toks = [str(t).strip().lower() for t in (tokens or []) if str(t).strip()]
        stems = [stem(t) for t in toks]
        vs = stem(shp["verb"])
        vi = next((k for k, s in enumerate(stems) if s == vs), None)
        row = {"tokens": " ".join(toks), "vi": vi}
        if vi is None:
            row["refused_at"] = "verb_not_in_memory"
        else:
            if shp.get("kind") == "object_unknown":
                miss = [t for t in shp.get("subject", [])
                        if not any(s == stem(t) for s in stems[:vi])]
                row["subject_missing"] = miss
            pos, tail_fail = vi + 1, None
            for t in shp.get("tail", []):
                nxt = next((k for k, s in enumerate(stems[pos:], start=pos)
                            if s == stem(t)), None)
                if nxt is None:
                    tail_fail = t
                    break
                pos = nxt + 1
            row["tail_fail"] = tail_fail
        row["result"] = orig(self, shp, tokens)
        rows.append(row)
        print("CANDIDATE:", json.dumps(row, sort_keys=True))
        return row["result"]

    lang._shape_matches = probe.__get__(lang, type(lang))
    said = sess.ask(ask)
    print("SAID    :", getattr(said, "text", said))
    print("CANDIDATES TRIED:", len(rows),
          "| any None:", any(r["result"] is None for r in rows),
          "| any answer:", any(r["result"] for r in rows))
    shutil.rmtree(sd, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())