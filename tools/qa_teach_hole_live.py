"""What ELECTRIC_ASK_SHAPE_STORE costs, in a real house.

`tools/qa_teach_mode_live.py` already shows the hole closing in a real house (section 6): one
pair taught, `what rings the bell twice` asked, and the house answering its own question back --
with the guard off. That is the buy. This file is the cost, and a guard that only ever gets
praised for what it refuses is not a guard anyone should trust.

The claim has three parts, and the house runs the SAME battery of lines twice, once per arm, so
every difference has to be attributable to one switch:

  (1) it eats no STATEMENT. The genuine tells and the relative clauses `question_shape` is
      documented to reject are filed in both arms, at both the row and the sentence.
  (2) it moves nothing the graded contract reads. `_absence_inv` is the licence's input and is
      written one line ABOVE the guard; the inventory and the cortex rows come out identical,
      and so does the admitted-absence reply.
  (3) it has a residual, measured rather than argued away. A short free-relative statement --
      `who rings the bell keeps the gate` -- is shape-identical to the ask `who rings the bell`,
      and this guard declines it. What that costs is recorded here: the PAIR, and only the pair.

And a fourth thing, found by this file rather than expected by it: the guard can change WHICH
STORE ANSWERS. With the residual filed under subj='rings' the ask `what rings the bell` has two
candidate subjects, `_electric_bind` rejects ambiguity and returns None, and the QA store answers;
with the residual declined the bind resolves cleanly to 'bell' and a different tell -- one the
person actually said, verbatim, keyed -- answers instead. Deleting a wrong entry made a right one
reachable. That is inside this flag's blast radius, so it is asserted at the only boundary that
holds (the reply is a sentence the house was told and is not itself a question) and printed in the
evidence file as `unmasking_note`. Anyone who reads this guard as pure subtraction should read
that note before trusting the reading.

The pair is the whole of the LOSS at the write site. A filed sentence does two things: it answers a
recall, and it is remembered as a tell. The second survives -- the row is written by `hear`
before this path runs, and the inventory entry is written before the guard is consulted. The
first was never available anyway: the frame the off-arm files is `('agent','rings','bell keeps
gate')`, a subject slot holding the verb, because the extractor reads by position and there is
no noun left to put in the slot once the relative clause has eaten it. That is the same misparse
the hole is made of, which is why this class was never a fact the house could use.

Writes docs/evidence/qa_teach_hole_live.json. Run:  python tools/qa_teach_hole_live.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

import tools.qa_elicit_live as q                       # noqa: E402
import tools.qa_teach_mode_live as m                   # noqa: E402

q.TMP = Path("_tmp/qa_teach_hole_live")     # not the mode check's scratch dir
EVIDENCE = Path("docs/evidence/qa_teach_hole_live.json")

# Lines a person might TELL the house, grouped by what the guard is supposed to do with them.
# `hear` is the door, not `respond`: this write site only sees tells.
STATEMENTS = ["the copper bell rings",
              "droso keeps the lantern in the pantry",
              "the latch holds the door",
              "mira carried the scarf home",
              "the kettle warms the room"]

# The documented reject set: a question word with a subject after it, a copula away from
# position two, a line too long for the binder to have a cap for. All facts, none of them asks.
RELATIVES = ["who sacrificed everything for him chimed in the ledger",
             "what the loop does at midnight surprises the clerk",
             "where the river bends the reed grows tall",
             "the bell that rings at midnight keeps the gate"]

# THE RESIDUAL. Shape-identical to `who rings the bell`, and this guard refuses it.
RESIDUAL = ["who rings the bell keeps the gate"]

# Questions, told as text -- but NOT through `hear`, which is a finding of the first run: with
# elicitation on (the mode arms all have it), an ask handed to `hear` starts a pending pair
# instead of being filed, so the tell door never reaches the write site for these lines and the
# measurement would be of elicitation, not of the guard. Their verdict is taken from the guard's
# own predicate below, and the hole itself is measured in section 1 through `respond`.
ASKS = ["what rings the bell?", "who holds the door?", m.HOLE_ASK, "where is the moon"]

BATTERY = [("statement", STATEMENTS), ("relative", RELATIVES), ("residual", RESIDUAL)]


def filed_map(lang):
    """{the sentence as told: (subject, relation)} for everything in `_taught_says`."""
    out = {}
    for subj, rels in lang._taught_says.items():
        for rel, text in rels.items():
            out[text] = (subj, rel)
    return out


def shape(lang, line):
    """What the detector itself says, recorded so a disagreement between the guard's verdict and
    the detector's is visible in the evidence rather than inferred from an assertion."""
    try:
        toks = [t for t in lang.tokenizer.tokenize(line) if t]
        return {"tokens": len(toks), "question_shape": bool(lang.question_shape(toks))
                if toks and len(toks) <= int(getattr(lang.cortex.binder, "max_roles", 0) or 0)
                else None}
    except Exception as exc:                            # noqa: BLE001 - a record, not a verdict
        return {"tokens": None, "question_shape": None, "error": str(exc)[:60]}


def battery_arm(guard, tag):
    """One real house, the mode in every respect, the guard as asked, the whole battery told."""
    lang = m.fresh("mode", tag, m.CONV[:2], off=() if guard else (m.GUARD_ATTR,))
    assert bool(lang.ELECTRIC_ASK_SHAPE_STORE) == bool(guard), \
        f"the house is not in the arm it was named: {guard}"
    rows0 = len(lang.cortex.binder.meta)
    rec = {"guard": bool(guard), "max_roles": int(getattr(lang.cortex.binder, "max_roles", 0)),
           "lines": {}, "asks": {}}
    for group, lines in BATTERY:
        for line in lines:
            before = filed_map(lang)
            lang.hear(line, speaker="you")
            after = filed_map(lang)
            # `filed` is PRESENCE in the store, not "this tell put it there": the house is told
            # some of these lines by its own boot TELLS before the battery runs, and `_taught_says`
            # is first-tell-wins, so a re-tell is declined by the store's own rule and has been
            # since before this guard existed. `newly` is the delta, recorded beside it because the
            # two answers mean different things and only one of them is this guard's verdict.
            rec["lines"][line] = {
                "group": group, "filed": line in after, "newly": line in set(after) - set(before),
                "frame": list(after[line]) if line in after else None,
                "shape": shape(lang, line)}
            print(f"      [guard={'on ' if guard else 'off'}] "
                  f"{'FILED  ' if line in after else 'declined'}{'' if line in before else ' (new)'}"
                  f" {line!r} -> {rec['lines'][line]['frame']} shape="
                  f"{rec['lines'][line]['shape']['question_shape']}", flush=True)
    # The asks, from the guard's own predicate. `hear` cannot be used for these: with
    # elicitation on it opens a pending pair instead of reaching the write site.
    for line in ASKS:
        rec["asks"][line] = {"guard_sees_an_ask": bool(lang._shape_files_as_ask(line)),
                             "shape": shape(lang, line)}
        print(f"      [guard={'on ' if guard else 'off'}] ask {line!r} -> guard sees an ask="
              f"{rec['asks'][line]['guard_sees_an_ask']} (unchanged by the flag; the flag decides "
              f"whether to act on it)", flush=True)
    rec["rows"] = len(lang.cortex.binder.meta) - rows0
    rec["inv"] = {s: sorted(d) for s, d in sorted(lang._absence_inv.items())}
    rec["filed"] = sorted(filed_map(lang))
    # The two replies that matter, after the battery: the pair the guard was installed to stop
    # drowning, and the absence the graded licence admits.
    r = lang.respond(m.PAIR_KEY, speaker="you") or {}
    lang._qa_pending = None
    said = str(r.get("utterance") or r.get("response") or "").strip()[:70]
    rec["pair_reply"] = {"said": said, "src": str(r.get("source") or ""),
                         # The reply's OWN shape, because the thing worth knowing about an
                         # answer a write-side guard just changed is whether it is a question.
                         "shape": shape(lang, said)["question_shape"]}
    g = lang.answer(m.GUARD_ASK, speaker="you") or {}
    g = g if isinstance(g, dict) else {"response": g}
    rec["guard_reply"] = {"spoken": bool(g.get("spoken")),
                          "said": str(g.get("utterance") or g.get("response") or "").strip()[:70],
                          "refused": bool(g.get("licensed_refusal")),
                          "reason": str(g.get("reason") or "")[:70]}
    print(f"      [guard={'on ' if guard else 'off'}] rows+{rec['rows']} "
          f"inv={len(rec['inv'])} asked {m.PAIR_KEY!r} -> {rec['pair_reply']['said']!r} "
          f"({rec['pair_reply']['src']}) | {m.GUARD_ASK!r} -> {rec['guard_reply']['said']!r} "
          f"refused={rec['guard_reply']['refused']}", flush=True)
    return rec


def main():
    t0 = time.time()
    res = {"tool": "qa_teach_hole_live", "started": t0}
    print("--- the hole, in the house this guard was found in (guard OFF) ---", flush=True)
    res["hole_off"] = m.hole("mode", 1, "H_hole_off", guard=False)
    res["hole_on"] = m.hole("mode", 1, "H_hole_on", guard=True)
    assert res["hole_off"]["polluted"], \
        f"the hole no longer reproduces in a real house -- it moved: {res['hole_off']}"
    assert not res["hole_on"]["polluted"] and res["hole_on"]["answered_from_store"], \
        f"the guard does not close it in a real house: {res['hole_on']}"

    print("\n--- the battery, twice: what the guard refuses and what that costs ---", flush=True)
    off = battery_arm(False, "B_off")
    on = battery_arm(True, "B_on")
    res["battery"] = {"off": off, "on": on}
    res["max_roles"] = on["max_roles"]

    # (1) NO STATEMENT EATEN. Every statement and every relative clause is filed in both arms.
    for line in STATEMENTS + RELATIVES:
        assert off["lines"][line]["filed"] and on["lines"][line]["filed"], \
            f"the guard declined a tell that is not an ask: {line} {on['lines'][line]}"
    # (2) NOTHING MOVED THAT THE CONTRACT READS. The inventory is the licence's input and the
    # rows are the house's memory; both are written before and independently of this guard.
    assert on["inv"] == off["inv"], \
        f"the guard reached `_absence_inv`, which is the graded store: on={on['inv']} " \
        f"off={off['inv']}"
    assert on["rows"] == off["rows"], \
        f"the guard changed what the house remembers as a row: on={on['rows']} off={off['rows']}"
    assert on["guard_reply"] == off["guard_reply"], \
        f"the admitted-absence reply moved with the guard: on={on['guard_reply']} " \
        f"off={off['guard_reply']}"
    # (3) The asks: the detector's verdict is the same in both arms, because the flag decides
    # whether to ACT on a verdict, not whether to have one. Every one of these is seen as an ask
    # -- including `where is the moon`, which the house has no pair for and which `hear` would
    # have opened a pending pair on. That is the guard's reach, stated as a reach.
    for line in ASKS:
        assert on["asks"][line]["guard_sees_an_ask"] == off["asks"][line]["guard_sees_an_ask"], \
            f"the flag changed the detector's verdict, not just its effect: {line}"
    # (4) THE FINDING, and it is not the one this file was written to print. The guard changes
    # WHICH STORE ANSWERS, and the assertion of equality I wrote here first FAILED in a real
    # house. Mechanism, read off the two arms: in the OFF arm the declined residual is filed
    # under subj='rings', so `what rings the bell` has two candidate subjects ('rings' and
    # 'bell') and `_electric_bind` REJECTS AMBIGUITY -- it returns None, the taught path falls
    # through, and the QA store answers 'the copper bell rings'. With the guard ON that bogus
    # entry is not in the store, the bind resolves cleanly to 'bell', and the house speaks
    # 'the bell that rings at midnight keeps the gate' -- a tell the person actually said,
    # verbatim, keyed. So deleting a wrong entry UNMASKED a right one, and the reply moved.
    #
    # That is inside the flag's blast radius and must be said out loud: this guard does not only
    # subtract, it can change which answer wins. What it must never do is invent one, and THAT
    # is what is asserted -- the reply is a sentence the house was told, and it is not an ask.
    res["pair_reply_changed"] = on["pair_reply"] != off["pair_reply"]
    assert on["pair_reply"]["said"] in on["filed"], \
        f"the guard produced an answer the house was never told: {on['pair_reply']} " \
        f"{on['filed']}"
    assert on["pair_reply"]["said"] not in ASKS and on["pair_reply"]["shape"] is not True, \
        f"the guard answered an ask with a question: {on['pair_reply']}"
    assert off["pair_reply"]["said"] in off["filed"] or \
        off["pair_reply"]["src"] == "electric_qa_store", \
        f"the control arm's reply is not accounted for either: {off['pair_reply']}"
    res["unmasking_note"] = (
        "guard OFF: subj='rings' holds the declined residual, the ask binds ambiguously, "
        "_electric_bind returns None, the QA store answers. guard ON: that entry is absent, "
        "the bind resolves to 'bell', and a tell the person actually said answers instead. "
        "Removing a wrong entry changed which right entry was reachable -- this flag is not "
        "pure subtraction, and the silence it replaced was accidental.")

    # (5) THE RESIDUAL, stated plainly: refused, and the row and the inventory entry survive.
    # What is lost is the PAIR -- and the frame the other arm filed was `('agent','rings',
    # 'bell keeps gate')`, a subject slot holding the verb, which is the same misparse the hole
    # is made of. Recorded, not argued: the evidence file holds both arms' frames.
    res["residual"] = {"line": RESIDUAL[0], "off": off["lines"][RESIDUAL[0]],
                       "on": on["lines"][RESIDUAL[0]]}
    assert not on["lines"][RESIDUAL[0]]["filed"], \
        "the residual is no longer declined -- either the guard moved or the detector did"
    assert off["lines"][RESIDUAL[0]]["filed"], \
        f"the residual is declined even with the guard OFF -- re-diagnose: {off}"
    subj = off["lines"][RESIDUAL[0]]["frame"][0]
    assert subj in on["inv"], \
        f"declining the pair lost the inventory entry for {subj!r} too -- that is the cost this " \
        "check exists to catch and the unit tests cannot"

    res["declined_with_guard_on"] = sorted(set(off["filed"]) - set(on["filed"]))
    res["filed_with_guard_on"] = on["filed"]
    res["elapsed_s"] = round(time.time() - t0, 1)
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(res, indent=1, sort_keys=True), encoding="utf-8")
    print(f"\n    binder cap (max_roles) = {on['max_roles']}; a line longer than it is left "
          "alone by the guard, which is the row tagger's own cap and not one this flag invented",
          flush=True)
    print(f"    declined by the guard and nothing else: {res['declined_with_guard_on']}",
          flush=True)
    print(f"    rows {off['rows']}=={on['rows']}  inventory identical  licence reply identical",
          flush=True)
    print(f"    pair reply: guard OFF {off['pair_reply']['src']}={off['pair_reply']['said']!r} / "
          f"guard ON {on['pair_reply']['src']}={on['pair_reply']['said']!r} -- "
          f"{'CHANGED, both are tells the house was told' if res['pair_reply_changed'] else 'same'}",
          flush=True)
    print(f"    wrote {EVIDENCE} in {res['elapsed_s']}s", flush=True)


if __name__ == "__main__":
    main()
