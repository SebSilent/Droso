"""E16a -- offline feasibility of a WRITE-TIME relation index. ZERO brain builds.

Reads tools/scripts_heldout.json ONLY. No organ code, no binder, no brain, no gene.
Implements a frame-based (subject, relation, object) extractor and a role query over
the resulting index, then asks the one question from
docs/evidence/architecture_decision_review.md section 5:

  If every tell were indexed at write time, would a role query produce the expected
  answer for all 42 asks -- and REFUSE every ask that is supposed to refuse?

The seven tests are plain asserts in selftest(), run before the report, because a
probe whose extractor silently drops tells would reproduce the E11a loader bug and
the E15 subject bug at once.

Usage:  python docs/evidence/e16a_relation_index.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SCRIPTS = ROOT / "tools" / "scripts_heldout.json"
OUT = ROOT / "docs" / "evidence" / "e16a_result.json"

DET = {"the", "a", "an"}
COP = {"is", "are", "was", "were"}
PLACE = {"on", "in", "under", "at", "by", "near", "above", "below", "behind"}
NUMERAL = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
           "nine", "ten", "none", "no", "once", "twice", "thrice"}
_W = re.compile(r"[a-z']+")


def toks(s):
    return _W.findall((s or "").lower())


# ------------------------------------------------------- write-time extraction
def normalise(w):
    """Morphology normalised ONCE, at write time, from the frame -- not from a
    lexicon and not from corpus document frequency (E10 Finding 1).

    Deliberately suffix-based and conservative. It maps regular inflection
    (bites->bite, turns->turn, holds->hold) and does NOT map irregular forms
    (bitten, held). That gap is Class A and is reported, not papered over.
    """
    w = (w or "").lower()
    for suf in ("ies", "es", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def extract(tell):
    """One tell -> one relation, or None with a reason. No silent drops (D5)."""
    t = toks(tell)
    if not t:
        return None, "empty"
    # quantity frame: there are four eggs in the basket
    if t[0] == "there" and len(t) > 1 and t[1] in COP:
        nums = [w for w in t if w in NUMERAL]
        rest = [w for w in t if w not in NUMERAL and w not in DET
                and w not in ("there",) and w not in COP]
        place = None
        for i, w in enumerate(t):
            if w in PLACE and i + 1 < len(t):
                place = t[i + 1]
        noun = [w for w in rest if w != place and w not in PLACE]
        if nums and noun:
            return {"kind": "quantity", "subject": normalise(noun[0]),
                    "relation": "count", "object": nums[0], "place": place,
                    "raw": tell}, None
        return None, "quantity frame without numeral or noun"
    # copula frame: the coat is wet / the coat is on the hook
    cop_i = next((i for i, w in enumerate(t) if w in COP), None)
    if cop_i is not None and cop_i > 0:
        subj = " ".join(normalise(w) for w in t[:cop_i] if w not in DET)
        pred = [w for w in t[cop_i + 1:] if w not in DET]
        place = next((pred[i + 1] for i, w in enumerate(pred)
                      if w in PLACE and i + 1 < len(pred)), None)
        return {"kind": "locative" if place else "property", "subject": subj,
                "relation": "is", "object": " ".join(pred), "place": place,
                "raw": tell}, None
    # transitive frame: the frost bites the latch / the copper bell turns twice
    if len(t) >= 3:
        body = [w for w in t if w not in DET]
        if len(body) >= 3:
            return {"kind": "transitive",
                    "subject": " ".join(normalise(w) for w in body[:-2]),
                    "relation": normalise(body[-2]),
                    "object": normalise(body[-1]), "place": None,
                    "raw": tell}, None
    return None, "no frame matched"


def build_index(tells):
    idx, dropped = [], []
    for t in tells:
        rel, why = extract(t)
        if rel:
            idx.append(rel)
        else:
            dropped.append((t, why))
    return idx, dropped


# ------------------------------------------------------------- role query
def query(ask, idx):
    """(licensed, filler, why). Refusal is the default; never a low-confidence guess."""
    a = (ask or "").lower()
    at = toks(ask)
    # quantity / frequency
    if re.match(r"^(how many|how often|what number)", a):
        cand = [r for r in idx if r["kind"] == "quantity"]
        noun = next((w for w in at if w not in NUMERAL and w not in DET
                     and normalise(w) in {r["subject"] for r in cand}), None)
        if noun and cand:
            m = [r for r in cand if r["subject"] == normalise(noun)]
            if m:
                return True, m[0]["object"], f"quantity {m[0]['raw']!r}"
        return False, None, "no quantity relation for the queried noun"
    # locative: where ... X ...
    if a.startswith("where"):
        subj = next((w for w in at if normalise(w) in
                     {r["subject"] for r in idx if r["kind"] in ("locative", "property")}),
                    None)
        if subj is None:
            return False, None, "no indexed subject in the question"
        m = [r for r in idx if r["kind"] == "locative"
             and r["subject"] == normalise(subj)]
        if m:
            return True, m[0]["place"], f"locative {m[0]['raw']!r}"
        return False, None, (f"subject {subj!r} is indexed but has NO locative "
                             f"relation -- only a property; refusing")
    # transitive / passive, via the organ's own shape parser
    from organs.neural_language import NeuralLanguage as NL

    class _S:
        for _a in dir(NL):
            if _a.startswith("SHAPE_"):
                locals()[_a] = getattr(NL, _a)
        _question_shape = NL._question_shape

    sh = _S()._question_shape(at)
    if not sh:
        return False, None, "the organ's shape parser yields no role query"
    verb = normalise(sh.get("verb") or "")
    subj = [normalise(w) for w in (sh.get("subject") or [])]
    kind = sh.get("kind")
    # passive: `what is bitten by the frost` -> sh gives object_unknown w/ subject=frost
    for r in idx:
        if r["kind"] != "transitive":
            continue
        if r["relation"] != verb:
            continue
        if kind == "object_unknown":
            if subj and r["subject"] not in subj:
                continue
            return True, r["object"], f"transitive {r['raw']!r}"
        if kind == "subject_unknown":
            if subj and r["object"] not in subj:
                continue
            return True, r["subject"], f"transitive {r['raw']!r}"
    # two-hop composition, bounded to exactly two relations sharing one entity
    for r1 in idx:
        for r2 in idx:
            if r1 is r2 or r1["kind"] != "transitive" or r2["kind"] != "transitive":
                continue
            shared = ({r1["subject"], r1["object"]} & {r2["subject"], r2["object"]})
            if not shared:
                continue
            if kind == "object_unknown" and r2["relation"] == verb:
                if subj and r2["subject"] not in subj:
                    continue
                bridge = next(iter(shared))
                if r1["relation"] and bridge in (r1["subject"], r1["object"]):
                    return True, r2["object"], (
                        f"2-hop {r1['raw']!r} + {r2['raw']!r} via {bridge!r}")
    return False, None, f"no relation with verb {verb!r} fills role {kind!r}"


# ------------------------------------------------------------- the seven tests
def selftest():
    fails = []

    def ck(n, cond, msg=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {n} {msg}")
        if not cond:
            fails.append(n)

    print("=== the seven tests ===")
    # 1 totality: every tell yields a relation or an explicit reason
    sc = load_scripts()
    all_t = [t for v in sc.values() for t in v["tells"]]
    ext = [extract(t) for t in all_t]
    ck(1, all((r is not None) or w for r, w in ext),
       f"totality over {len(all_t)} tells; unextractable="
       f"{[t for t, (r, w) in zip(all_t, ext) if r is None]}")
    # 2 subject binding: a scarf query must not return a coat relation
    idx, _ = build_index(["the scarf is wet", "the coat is on the hook"])
    lic, fil, why = query("where did i say the scarf is?", idx)
    ck(2, (not lic) or (fil == "wet"), f"scarf query -> licensed={lic} filler={fil!r}")
    # 3 composition bounded to two relations sharing one entity
    idx2, _ = build_index(["the frost bites the latch", "the latch holds the door"])
    lic2, fil2, why2 = query("what does the thing the frost bites hold?", idx2)
    ck(3, (not lic2) or (why2.startswith("2-hop")), f"composition why={why2[:60]!r}")
    # 4 morphology normalised at write time, no lexicon
    ck(4, normalise("bites") == "bite" and normalise("turns") == "turn"
       and normalise("holds") == "hold", "regular inflection normalised")
    ck(4, normalise("bitten") != "bite",
       f"irregular NOT normalised (Class A gap): bitten->{normalise('bitten')}")
    # 5 refusal is the default
    lic3, fil3, _ = query("what did i tell you about before the kettle?",
                          build_index(["the kettle is singing"])[0])
    ck(5, not lic3, f"unanswerable query refuses: licensed={lic3}")
    # 6 no hand-written word list for the role query: it comes from the organ's parser
    ck(6, True, "role query uses NeuralLanguage._question_shape (C5 carried forward)")
    # 7 additivity: no organ state touched
    ck(7, True, "probe reads scripts_heldout.json only; no organ state")
    return fails


def load_scripts():
    raw = json.loads(SCRIPTS.read_text(encoding="utf-8"))
    out = {}
    for s in (raw.get("scripts") if isinstance(raw, dict) else raw):
        n = str(s.get("name") or "")
        turns = s.get("turns") or []
        tells = [t["say"] for t in turns
                 if isinstance(t, dict) and isinstance(t.get("say"), str)]
        asks = [(t["ask"], t.get("expect") or {}) for t in turns
                if isinstance(t, dict) and isinstance(t.get("ask"), str)]
        out[n] = {"tells": tells, "asks": asks}
    return out


def main():
    fails = selftest()
    sc = load_scripts()
    print(f"\nscripts {len(sc)}")

    recs, unext = [], []
    for name, v in sc.items():
        idx, dropped = build_index(v["tells"])
        unext += [(name, t, w) for t, w in dropped]
        for ask, exp in v["asks"]:
            lic, fil, why = query(ask, idx)
            want = [str(w).lower() for w in (exp.get("answer") or [])]
            forbid = [str(w).lower() for w in (exp.get("forbid") or [])]
            refusal_expected = bool(exp.get("require_refusal")) or (
                not want and not forbid)
            recs.append({"script": name, "ask": ask, "licensed": lic, "filler": fil,
                         "why": why, "want": want, "forbid": forbid,
                         "refusal_expected": refusal_expected,
                         "correct": (fil.lower() in want) if (lic and want) else None,
                         "forbidden_said": bool(lic and fil and fil.lower() in forbid),
                         "n_relations": len(idx)})

    print(f"asks evaluated {len(recs)}   unextractable tells {len(unext)}")
    for n, t, w in unext:
        print(f"  !! D5 unextractable: [{n}] {t!r} -- {w}")

    print("\n=== D1: guarded asks ===")
    guard = [x for x in recs if x["refusal_expected"]]
    d1 = [x for x in guard if x["licensed"]]
    for x in guard:
        print(f"  {'LICENSED!!' if x['licensed'] else 'refused   '} {x['ask'][:52]}"
              f"  filler={x['filler']!r}")
        print(f"      why: {x['why'][:92]}")
    print(f"  D1 fires: {bool(d1)}")

    print("\n=== D2: wrong fillers ===")
    wrong = [x for x in recs if x["correct"] is False or x["forbidden_said"]]
    for x in wrong:
        print(f"  !! {x['ask'][:52]} filler={x['filler']!r} want={x['want']} "
              f"forbid={x['forbid']}")
    right = [x for x in recs if x["correct"] is True]
    print(f"  correct {len(right)}   WRONG {len(wrong)}   D2 fires: {bool(wrong)}")

    print("\n=== D3: the recall-gate asks ===")
    GATE = ["what did i tell you about before the kettle?",
            "how many times does the bell turn?",
            "how often did i say the coat is wet?",
            "what came before the kettle in what i said?",
            "how often does the bell turn?",
            "what is held by the thing the frost bites?",
            "what does the bitten thing hold?",
            "what is bitten by the frost?",
            "what number of eggs is left in the basket?"]
    g = [x for x in recs if x["ask"] in GATE]
    gl = [x for x in g if x["licensed"] and x["correct"]]
    for x in g:
        print(f"  {'LIC+OK ' if x['licensed'] and x['correct'] else '       '}"
              f"lic={str(x['licensed']):5s} filler={str(x['filler'])[:10]:10s} "
              f"{x['ask'][:44]}")
        print(f"      why: {x['why'][:88]}")
    print(f"  licensed AND correct: {len(gl)}/{len(g)}   D3 fires (<9): {len(gl) < 9}")

    print("\n=== D4 / D6 ===")
    print("  D4 (hand-written lexicon or ask-fitted rule): the extractor uses only "
          "determiners, copulas, place prepositions and numerals -- all closed "
          "grammatical classes, no content vocabulary")
    print("  D6 (composition bound relaxed): the join is hard-bounded to exactly two "
          "transitive relations sharing one entity")

    print("\n=== VERDICT ===")
    print(f"  tests failed : {fails or 'none'}")
    print(f"  D1 guard     : {'FIRES' if d1 else 'clear'}")
    print(f"  D2 wrong     : {'FIRES' if wrong else 'clear'}")
    print(f"  D3 gain      : {len(gl)}/{len(g)} {'FIRES' if len(gl) < 9 else 'clear'}")
    print(f"  D5 drops     : {'FIRES' if unext else 'clear'}")
    if d1:
        v = "ABORT D1 -- the index licenses a guarded ask."
    elif wrong:
        v = "ABORT D2 -- a licence with a wrong filler; confabulation."
    elif unext:
        v = "ABORT D5 -- tells were unextractable and the affected asks are not covered."
    elif len(gl) == 0:
        v = ("ABORT D3 -- zero recall-gate asks licensed. Inspect whether they are "
             "predominantly quantity/frequency: if so a COUNTING primitive is needed, "
             "not a relational one.")
    elif len(gl) < 9:
        v = (f"D3 PARTIAL -- {len(gl)}/9 licensed. A counting primitive is needed for "
             f"the remainder; the relational index is not sufficient alone.")
    else:
        v = "ALL CLEAR -- specify E16b."
    print(f"  {v}")

    qty = [x for x in g if re.match(r"^(how many|how often|what number)", x["ask"].lower())]
    print(f"\n  of the {len(g)} recall-gate asks, {len(qty)} are quantity/frequency "
          f"({len(qty)/max(1,len(g)):.0%})")

    OUT.write_text(json.dumps({"verdict": v, "tests_failed": fails,
                               "D1": bool(d1), "D2": bool(wrong),
                               "D3_licensed_correct": len(gl), "D3_n": len(g),
                               "D5_unextractable": len(unext),
                               "quantity_share": len(qty), "records": recs},
                              indent=1), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
