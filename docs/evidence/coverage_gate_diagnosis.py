"""WHERE DO THE FAILING ASKS ACTUALLY DIE? Part 2 of the coverage measurement.

`docs/evidence/coverage_exact.py` (part 1) read the unrounded coverage behind two
asks and proved no ANSWER_COVERAGE_FLOOR separates the kettle target from the scarf
guard. It is cited by docs/selection_design.md and is left exactly as it was.

This part exists because of E5. R1/R1'/R2 turned out to be inert: `which thing
turns twice?` fails at `recall`, upstream of the shape arbiter, and it fails there
even though it now parses IDENTICALLY to `what turns twice?`, which passes. So the
shape is not the cause. The hypothesis recorded in
docs/answer_path_repair_design.md section 3c is the coverage/recall gate. This
script tests it by reading the organ's own raw reply dict for every failing ask and
classifying the death:

  ABSENT   `required` is empty -- informative() dropped every content word because
           none of them has a binder posting. There is nothing to recall, so no
           gate setting could have helped.
  GATE     memories DO exist and were scored, but best_cov < ANSWER_COVERAGE_FLOOR,
           so the recall gate refused them. This is the ONLY class a gate repair
           can fix, and its size is the whole question.
  VETO     the shape arbiter rejected the best candidate
  MOUTH    the answer was assembled but the mouth refused to say it
  OTHER    refused for a reason this probe does not classify

  SPOKE    the organ produced an answer. This is NOT a harness pass: the content may
           be wrong, or the ask may expect a refusal. Four of the five SPOKE rows in
           the recorded run are harness failures.

CONTRAST ASKS AND A CAVEAT THAT COST A RUN. Asks that already work are measured too,
for contrast. But a contrast ask is not a turn in the script it is asked against, so
it can only be asked after ALL of that script's tells, and its coverage is therefore
NOT comparable with an ask the script positions. In the recorded run this bit hard:
`what turns twice?` reads cov=0.586, below the floor, yet it PASSES in the frozen
battery -- because there it belongs to a different script with different tells. That
number is labelled `after-all-tells` in the JSON and must not be used as evidence
about the passing form. The first version of this probe replayed every tell before
every ask, which silently put later tells into the binder for ALL asks; the fix is to
walk the turns in order and ask each at its own position. The corrected run agrees
with part 1 exactly on the one ask they share -- kettle = 0.555 -- which is the
cross-check that says the walk is right.

Read-only: it does not patch the organ, does not write persistent state, does not
change a gene, and it verifies with guard_live_files that no live file moved.

This is a DIAGNOSTIC, not a scored measurement. It uses one build per script and
replays that script's tells once, then asks every failing ask belonging to it --
about 6 builds instead of about 19. That is legitimate here because the question is
"why does this ask refuse", which is a property of the organ's own reply dict and
not of the scored harness. Anything that feeds a selection decision must still go
through tools/run_generation.py --isolate.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.converse import Session, build, guard_check, guard_live_files  # noqa: E402

HELDOUT = json.loads((ROOT / "tools" / "scripts_heldout.json").read_text(encoding="utf-8"))
SELECTION = json.loads((ROOT / "tools" / "scripts_selection.json").read_text(encoding="utf-8"))
BASELINE = json.loads((ROOT / "tools" / "selection_baseline.json").read_text(encoding="utf-8"))
OUT = ROOT / "docs" / "evidence" / "coverage_gate_diagnosis.json"

FROZEN_FAIL = set(BASELINE.get("frozen_fail_set") or [])
PARAPHRASE = set(BASELINE.get("paraphrase_set") or [])
GUARD = set(BASELINE.get("regression_pass_set") or [])

# asks that PASS, kept as contrast so a repair is checked against working forms.
# `what turns twice?` is the decisive one: with R1' on it parses identically to
# `which thing turns twice?`, yet it passes and that one fails.
CONTRAST = {
    "conjunction-and-absence": ["what turns twice?"],
    "frequency": ["the bell turns how often?", "how many eggs broke?"],
}


def _scripts(doc):
    return doc.get("scripts") or doc


def _spoken(r):
    return bool(r.get("spoken") or r.get("answered") or r.get("ok"))


def classify(r):
    """Where did this ask die? Read from the organ's own reply, not guessed.

    SPOKE is deliberately NOT called PASS. `spoken` means the organ produced an
    answer; the harness may still score it a failure, because the content was wrong
    or because the ask expected a refusal. Four of the five SPOKE rows here are
    harness failures. Conflating the two would have made this probe look like it
    disagreed with the recorded floor when it does not.
    """
    if _spoken(r):
        return "SPOKE"
    reason = str(r.get("reason") or "")
    required = r.get("required")
    cov = r.get("coverage")
    if "veto" in reason or "shape" in reason:
        return "VETO"
    if not required:
        return "ABSENT"
    if "covers" in reason or cov is not None:
        return "GATE"
    if "say" in reason and ("mouth" in reason or "sayable" in reason):
        return "MOUTH"
    return "OTHER"


def main():
    before = guard_live_files("coverage_gate_diagnosis")

    # The baseline sets hold "script::ask" composite keys, not bare asks. Splitting
    # them is what makes the plan match; matching on the bare ask alone would have
    # silently planned nothing, which is exactly what the first run did.
    def _split(composite):
        name, _, ask = str(composite).partition("::")
        return (name, ask) if ask else (None, str(composite))

    # script name -> (turns, [(tier, ask, expect)])
    plan = {}
    for doc, tiers in ((HELDOUT, (("frozen_fail", FROZEN_FAIL), ("guard", GUARD))),
                       (SELECTION, (("generalisation", PARAPHRASE),))):
        for sc in _scripts(doc):
            name = sc.get("name") or sc.get("id")
            for t in sc.get("turns") or []:
                q = t.get("ask")
                if not q:
                    continue
                for tier, want in tiers:
                    if (name, q) in {_split(w) for w in want}:
                        blk = plan.setdefault(name, {"turns": sc["turns"], "asks": []})
                        expect = {k: v for k, v in t.items() if k not in ("ask", "say")}
                        blk["asks"].append((tier, q, expect))
    for name, asks in CONTRAST.items():
        if name in plan:
            for q in asks:
                plan[name]["asks"].append(("contrast", q, {}))

    floor = None
    try:
        from organs.neural_language import NeuralLanguage
        floor = NeuralLanguage.ANSWER_COVERAGE_FLOOR
    except Exception as exc:  # pragma: no cover - diagnostic only
        floor = "unreadable: %r" % (exc,)

    total = sum(len(b["asks"]) for b in plan.values())
    print("=" * 78)
    print("COVERAGE / RECALL-GATE DIAGNOSIS")
    print("ANSWER_COVERAGE_FLOOR =", floor)
    print("frozen failures:", len(FROZEN_FAIL), "generalisation:", len(PARAPHRASE),
          "guarded:", len(GUARD), "contrast:", sum(len(v) for v in CONTRAST.values()))
    print("scripts to build:", len(plan), " asks:", total)
    print("=" * 78)

    tally = {}
    rows = []
    for n, (name, blk) in enumerate(sorted(plan.items()), 1):
        print("\n--- build %d/%d  script %s  (%d asks) ---"
              % (n, len(plan), name, len(blk["asks"])))
        sd = ROOT / "state" / "sessions" / ("_covdiag_%s" % name)
        if sd.exists():
            shutil.rmtree(sd)
        try:
            agent = build(sd)
            sess = Session(agent, beats=0)
            lang = agent.language
            # Walk the turns IN ORDER and ask each planned ask at its own position,
            # so the binder holds exactly the tells that preceded it. Replaying every
            # tell in the script first -- which is what the first run did -- puts
            # later tells into the binder and changes coverage, making the numbers
            # incomparable with the harness and with coverage_exact.py, which replays
            # turns[:idx]. One build per script is still enough, because tells
            # accumulate: ask at idx1, then keep telling up to idx2, then ask.
            pending = {}
            for tier, q, expect in blk["asks"]:
                if tier != "contrast":
                    pending.setdefault(q, []).append((tier, expect))
            results = []
            for t in blk["turns"]:
                if "say" in t:
                    sess.ask(t["say"], kind="tell")
                    continue
                q = t.get("ask")
                if q in pending:
                    r = lang.respond(q, speaker="you") or {}
                    for tier, expect in pending.pop(q):
                        results.append((tier, q, expect, r, "at-position"))
            # contrast asks are not turns in this script, so they can only be asked
            # after every tell. That is labelled, not hidden: their coverage is not
            # comparable with an ask the script itself positions.
            for tier, q, expect in blk["asks"]:
                if tier == "contrast":
                    r = lang.respond(q, speaker="you") or {}
                    results.append((tier, q, expect, r, "after-all-tells"))
            for tier, q, expect, r, position in results:
                cls = classify(r)
                tally[cls] = tally.get(cls, 0) + 1
                rows.append({"script": name, "tier": tier, "ask": q, "class": cls,
                             "position": position, "expect": expect,
                             "reply": {k: v for k, v in r.items()
                                       if not isinstance(v, (list, dict))
                                       or k in ("required", "nearest", "vote",
                                                "parser", "cue")}})
                print("  [%-14s] %-7s %s" % (tier, cls, q))
                print("      reason   %r" % (r.get("reason"),))
                print("      coverage %r  required %r" % (r.get("coverage"),
                                                          r.get("required")))
                print("      nearest  %r" % (r.get("nearest"),))
                for k in ("vote", "parser", "cue", "source", "stage"):
                    if r.get(k) is not None:
                        print("      %-9s%r" % (k, r[k]))
        finally:
            if sd.exists():
                shutil.rmtree(sd, ignore_errors=True)

    print("\n" + "=" * 78)
    print("TALLY:", json.dumps(tally, sort_keys=True))
    print("=" * 78)

    moved = guard_check(before)
    print("live state untouched:", not moved, (moved or [])[:6])

    OUT.write_text(json.dumps({"floor": floor, "tally": tally, "rows": rows},
                              indent=1, sort_keys=True, default=str),
                   encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
