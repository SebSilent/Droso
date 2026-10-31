"""E9 P2/P3 probe: does session scoping actually engage, and does it EXCLUDE the
attractor rather than merely out-score it?

Same four mouth asks and the same scratch isolation as docs/evidence/mouth_probe.py,
but with RESONANCE_SESSION_SCOPE = True. Read-only: no core code changed, no live
learner state touched, each ask on its own freshly built brain in SCRATCH.

P2 -- the scoped pool is < 100 and contains the wanted word. If it is empty or still
      11,439 the mechanism did not engage and E9 is VOID rather than failed.
P3 -- `numbered`, `sold` and `agin` are ABSENT from the scoped pool. This is the claim
      that distinguishes scoping from reweighting: if they remain candidates and merely
      lose, P3 is falsified even if the ask passes.

Also recorded, because the pre-registration says the echo ask is outside the target
set: whether the wanted word now WINS its scoped pool, and what is actually said.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from organs.neural_language import NeuralLanguage          # noqa: E402
from tools.converse import build                           # noqa: E402
from tools.run_generation import SCRATCH                   # noqa: E402

SELECTION = ROOT / "tools" / "scripts_selection.json"

CASES = [
    ("sel-conjunction-and-absence",
     "name the wet thing that is not on the hook", ["scarf"], True),
    ("sel-conjunction-and-absence",
     "which of them is wet and is not on the hook?", ["scarf"], True),
    ("sel-exact-repeat",
     "repeat after me the copper bell turns twice",
     ["copper", "bell", "turns", "twice"], False),   # rendering-limited, not a target
    ("sel-order-first-last",
     "which thing did i mention earlier than the kettle?", ["lantern"], True),
]

ATTRACTORS = ["numbered", "sold", "agin"]


def scripts_by_name() -> dict:
    d = json.loads(SELECTION.read_text(encoding="utf-8"))
    items = d if isinstance(d, list) else d.get("scripts", [])
    return {s["name"]: s for s in items}


def main() -> None:
    NeuralLanguage.RESONANCE_SESSION_SCOPE = True
    by_name = scripts_by_name()
    out = []
    for i, (name, ask, wanted, is_target) in enumerate(CASES):
        script = by_name[name]
        sd = SCRATCH / f"e9scope_{name}_{i}"
        if sd.exists():
            shutil.rmtree(sd)
        agent = build(sd, project_root=None)
        lang = agent.language
        assert lang.RESONANCE_SESSION_SCOPE is True

        tells = [t["say"] for t in script["turns"] if "say" in t]
        for say in tells:
            lang.hear(say, speaker="you")

        # What the flag does to the candidate pool, measured directly.
        full = [m for m in lang.word_patterns if lang._speakable(m)]
        session = lang._session_words()
        scoped = lang._resonance_mates(ask)

        reply = lang.respond(ask, speaker="you")
        said = reply.get("utterance") or ""
        source = reply.get("source") or ""

        heard = lang.hear(ask, speaker="you")
        act = heard.get("act") if isinstance(heard, dict) else None
        if act is None:
            act = getattr(lang, "san_act", None)
        res = {m: lang._resonance(m, act) for m in scoped}
        ranked = sorted(res.items(), key=lambda kv: -kv[1])
        pos = {w: n + 1 for n, (w, _s) in enumerate(ranked)}

        row = {
            "script": name,
            "ask": ask,
            "wanted": wanted,
            "is_target": is_target,
            "said": said,
            "source": source,
            "spoken": bool(reply.get("spoken")),
            "reason": reply.get("reason"),
            "full_pool": len(full),
            "session_words": len(session),
            "scoped_pool": len(scoped),
            # P2
            "P2_engaged": bool(0 < len(scoped) < 100),
            "P2_wanted_in_pool": {w: (w in res) for w in wanted},
            # P3
            "P3_attractors_absent": {a: (a not in scoped) for a in ATTRACTORS},
            "P3_pass": all(a not in scoped for a in ATTRACTORS),
            "scoped_top5": [[w, round(s, 4)] for w, s in ranked[:5]],
            "scoped_argmax": ranked[0][0] if ranked else None,
            "scoped_argmax_score": round(ranked[0][1], 4) if ranked else None,
            "wanted_rank_in_scoped": {w: pos.get(w) for w in wanted},
            "wanted_score_in_scoped": {w: (round(res[w], 4) if w in res else None)
                                       for w in wanted},
            "wanted_wins_scoped_pool": bool(
                ranked and any(w == ranked[0][0] for w in wanted)),
            "reply_threshold": lang.reply_threshold,
        }
        out.append(row)
        print(json.dumps(row, ensure_ascii=False))
        shutil.rmtree(sd, ignore_errors=True)

    NeuralLanguage.RESONANCE_SESSION_SCOPE = False
    p = ROOT / "docs" / "evidence" / "e9_scope_probe.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                 encoding="utf-8")
    print("\nwrote", p)


if __name__ == "__main__":
    main()
