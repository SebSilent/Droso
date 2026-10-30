"""Read the UNROUNDED coverage behind two asks, so a threshold is measured not guessed.

The generation-0 journal only kept answer()'s reason string, which reports coverage
as a whole percent ("covers 57%"). The reply dict also carries `coverage` rounded to
3 decimals, and that is the number the organ actually compares against
ANSWER_COVERAGE_FLOOR. Two asks matter:

  order-first-last :: what did i tell you about before the kettle?   (55%, a failure)
  conjunction-and-absence :: where did i say the scarf is?           (57%, a PASS that
                                                     passes BY REFUSING -- require_refusal)

Whole percent leaves both ambiguous: "55%" is any best_cov in [0.545, 0.555) and
"57%" is any in [0.565, 0.575). A candidate floor of 0.566857 (generation 2's one
lowering draw) falls inside the second interval, so the journal cannot say whether
that floor flips the guarded pass. This measures it.

Read-only: builds under state/sessions/, live state untouched, oracle blocked and
the learning loop sealed by converse.build().

  py -3.10 docs/evidence/coverage_exact.py
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.converse import Session, build, guard_check, guard_live_files  # noqa: E402

FROZEN = json.loads((ROOT / "tools" / "scripts_heldout.json").read_text(encoding="utf-8"))
TARGETS = {
    "order-first-last": "what did i tell you about before the kettle?",
    "conjunction-and-absence": "where did i say the scarf is?",
}

before = guard_live_files("coverage_exact")
out = []
for name, ask in TARGETS.items():
    script = next(s for s in FROZEN["scripts"] if s["name"] == name)
    idx = next(i for i, t in enumerate(script["turns"])
               if t.get("ask") == ask)
    sd = ROOT / "state" / "sessions" / f"_cov_exact_{name}"
    if sd.exists():
        shutil.rmtree(sd)
    try:
        agent = build(sd)
        sess = Session(agent, beats=0)
        for st in script["turns"][:idx]:
            if "say" in st:
                sess.ask(st["say"], kind="tell")
        # NOT sess.ask: Session.ask passes the reply through converse._clean(), whose
        # keep-list does not include `coverage`, `required` or `nearest` -- which is
        # why the generation-0 journal only has the whole-percent reason string. This
        # is the identical call Session.ask makes, read raw.
        r = agent.language.respond(ask, speaker="you") or {}
        rec = {"script": name, "ask": ask,
               "coverage": r.get("coverage"),
               "reason": r.get("reason"),
               "spoken": bool(r.get("spoken") or r.get("answered")),
               "nearest": r.get("nearest"),
               "required": r.get("required"),
               "cue": r.get("cue")}
        out.append(rec)
        print(f"{name}")
        print(f"  ask      {ask}")
        print(f"  coverage {rec['coverage']}   <- the number the organ compares "
              f"to ANSWER_COVERAGE_FLOOR")
        print(f"  reason   {rec['reason']}")
        print(f"  spoken   {rec['spoken']}")
        print(f"  required {rec['required']}")
        print(f"  nearest  {rec['nearest']}")
        print()
    finally:
        shutil.rmtree(sd, ignore_errors=True)

moved = guard_check(before)
print("live state untouched:", not moved, moved[:6] if moved else "")

print("\nwhat each candidate floor would do (admit iff coverage >= floor):")
cov = {r["script"]: r["coverage"] for r in out if r["coverage"] is not None}
kettle = cov.get("order-first-last")
scarf = cov.get("conjunction-and-absence")
for f in (0.45, 0.50, 0.545, 0.55, 0.555, 0.565, 0.566857, 0.575, 0.60, 0.664409):
    g = "ADMIT" if (kettle is not None and kettle >= f) else "refuse"
    s = "ADMIT" if (scarf is not None and scarf >= f) else "refuse"
    note = ""
    if s == "ADMIT":
        note = "  <- the guarded pass-by-refusal is LOST at this floor"
    if g == "ADMIT" and s == "refuse":
        note = "  <- gains the target and keeps the guard"
    print(f"  floor {f:<9} kettle:{g:7s} scarf:{s:7s}{note}")

if kettle is not None and scarf is not None:
    print(f"\nkettle {kettle} vs scarf {scarf}: "
          f"{'NO floor separates them (kettle < scarf, so any floor admitting the '
           'target also admits the guarded pass)' if kettle < scarf else 'separable'}")
