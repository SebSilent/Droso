r"""Does ordinal selection generalise, or did it learn the phrasing?

Replays the order-first-last tells into a fresh house, then asks the two target
asks plus the three paraphrases pre-registered in docs/speech_log.md. Reporting
is mechanical: an answer is printed, right or wrong.
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
    ("target  ", "which did i tell you first the lantern or the kettle?", "lantern"),
    ("target  ", "which did i tell you last the kettle or the gate?", "gate"),
    ("P1      ", "which did you tell me first, the lantern or the kettle?", "lantern"),
    ("P2      ", "of the lantern and the kettle, which did i say first?", "lantern"),
    ("P3      ", "between the gate and the kettle, which did i tell you last?", "gate"),
    ("control ", "which did i tell you first the gate or the gate?", "?"),
    ("control ", "does the door hold the frost?", "(silence, must not be 'no')"),
    ("control ", "did i ever tell you about the moon?", "(silence, must not be 'no')"),
]


def main() -> int:
    script = next(s for s in SCRIPTS if s["name"] == "order-first-last")
    turns = script["turns"]
    stop = next(k for k, st in enumerate(turns) if "ask" in st)

    sd = ROOT / "state" / "sessions" / "ordinalprobe"
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
        got = (reply or {}).get("utterance") or (reply or {}).get("response") or ""
        src = (reply or {}).get("source") or (reply or {}).get("reason") or ""
        verdict = "PASS" if want in (got, "(silence, must not be 'no')") and (
            want == "(silence, must not be 'no')" and not got
            or want != "(silence, must not be 'no')" and want.lower() in str(got).lower()
        ) else "FAIL"
        if want == "?":
            verdict = "info"
        ok += verdict == "PASS"
        bad += verdict == "FAIL"
        print(f"{label} {verdict:4s} said={got!r:24s} src={src[:20]:20s} {ask}")
    print(f"PARAPHRASE+TRUE: {ok} pass, {bad} fail")
    shutil.rmtree(sd, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())