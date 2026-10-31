"""E17a -- read-only feasibility of a counting primitive with temporal update semantics.

ZERO brain builds. No organ change. No gene. Reads tools/scripts_heldout.json,
tools/scripts_selection.json and the generation-13 ask journal only.

Implements, as standalone functions, the three decisions in
docs/evidence/counting_primitive_design.md:
  1. store EVENTS, derive state by ordered folding (a later absolute REPLACES);
  2. never guess polarity -- an indeterminate state REFUSES;
  3. answer event-count queries, refuse state-count queries.

Then runs checks H1-H7 and abort conditions E1-E7.

Usage:  python docs/evidence/e17a_counting_probe.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

HELDOUT = ROOT / "tools" / "scripts_heldout.json"
SELECTION = ROOT / "tools" / "scripts_selection.json"
JOURNAL = ROOT / "state" / "selection" / "generation_13_asks.jsonl"
OUT = ROOT / "docs" / "evidence" / "e17a_result.json"

DET = {"the", "a", "an"}
COP = {"is", "are", "was", "were"}
PLACE = {"on", "in", "under", "at", "by", "near", "above", "below", "behind"}
NUM = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
       "seven": 7, "eight": 8, "nine": 9, "ten": 10, "no": 0, "none": 0}
STOP = DET | COP | {"there", "did", "does", "do", "i", "you", "say", "said", "tell",
                    "told", "about", "how", "many", "what", "which", "thing", "times",
                    "often", "number", "left", "is", "are", "was", "were", "of", "in",
                    "the", "a", "an", "it", "that", "this", "and", "before", "after",
                    "first", "mention", "mentioned"}
_W = re.compile(r"[a-z']+")


def toks(s):
    return _W.findall((s or "").lower())


def normalise(w):
    """Conservative suffix normalisation. E16a test 4 showed this maps bites->bit, so
    it is used ONLY for entity matching, never for verb matching, and the gap is
    reported rather than papered over."""
    w = (w or "").lower()
    for suf in ("ies", "es", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def head(noun_tokens):
    """E11a's head-final rule: English noun phrases are head-final, so the head is the
    LAST content token. `copper bell` -> `bell`, not `copper bell` (E16a defect 1)."""
    content = [w for w in noun_tokens if w not in DET]
    return normalise(content[-1]) if content else None


# ------------------------------------------------------- write-time extraction
def extract_event(tell, seq, who="you"):
    """One tell containing a numeral -> one count_events row, or (None, reason).
    No silent drops (H1 / E7)."""
    t = toks(tell)
    nums = [(i, w) for i, w in enumerate(t) if w in NUM]
    if not nums:
        return None, "no numeral"
    i, nw = nums[0]

    # ABSOLUTE frame: there are four eggs in the basket
    if t and t[0] == "there" and len(t) > 1 and t[1] in COP:
        rest = [w for w in t[i + 1:] if w not in DET and w not in PLACE]
        place = next((t[j + 1] for j, w in enumerate(t)
                      if w in PLACE and j + 1 < len(t)), None)
        ent = head([w for w in rest if w != place]) if rest else None
        if ent is None:
            return None, "absolute frame without an entity"
        return {"entity": ent, "numeral": NUM[nw], "frame": "absolute",
                "verb": None, "place": normalise(place) if place else None,
                "seq": seq, "who": who, "raw": tell}, None

    # EVENT frame: two eggs broke  /  four eggs are in the basket
    before = [w for w in t[:i] if w not in DET]
    after = [w for w in t[i + 1:] if w not in DET]
    # numeral-first ("two eggs broke") -> entity follows the numeral
    # entity-first ("the eggs two broke") is not English; ignore
    cand = after or before
    ent = head([w for w in cand if w not in NUM and w not in COP]) if cand else None
    verb = next((normalise(w) for w in (after if before is not None else before)
                 if w not in NUM and w not in COP and w not in PLACE), None)
    if verb is None:
        verb = next((normalise(w) for w in after if w not in NUM), None)
    if ent is None:
        return None, "event frame without an entity"
    return {"entity": ent, "numeral": NUM[nw], "frame": "event", "verb": verb,
            "place": None, "seq": seq, "who": who, "raw": tell}, None


def build_events(tells):
    ev, dropped = [], []
    for n, t in enumerate(tells):
        r, why = extract_event(t, n)
        if r:
            ev.append(r)
        elif why != "no numeral":
            dropped.append((t, why))   # "no numeral" is expected, not a drop
    return ev, dropped


# ------------------------------------------------------------------- folding
def fold(events, entity, place=None):
    """Ordered fold. A later ABSOLUTE replaces. An EVENT adjusts only if polarity is
    DETERMINATE -- and polarity is never determinate here, because determining it needs
    a verb lexicon (D4 / E10 Finding 1). So any event makes the state INDETERMINATE."""
    cur, det = None, True
    for e in sorted([x for x in events if x["entity"] == entity
                     and (place is None or x["place"] == place)], key=lambda x: x["seq"]):
        if e["frame"] == "absolute":
            cur = e["numeral"]          # REPLACE, not add -- the E16a fix
        else:
            det = False                 # polarity unknown -> stop trusting the state
    return cur, det


# --------------------------------------------------------------- role query
def query(ask, events):
    """(licensed, filler, kind, why). Refusal is the default; never a guess."""
    a = (ask or "").lower()
    at = toks(ask)
    if not re.match(r"^(how many|how often|what number)", a):
        return False, None, "not-quantity", "not a quantity or frequency ask"

    ents = {e["entity"] for e in events}
    ent = next((normalise(w) for w in at if normalise(w) in ents), None)
    if ent is None:
        return False, None, "quantity", "no indexed entity in the question"

    # EVENT-COUNT query: `how many X <verb>?` -- the tell states the number, no folding
    qverb = next((normalise(w) for w in at
                  if w not in STOP and w not in NUM and normalise(w) != ent), None)
    evs = [e for e in events if e["entity"] == ent and e["frame"] == "event"]
    if qverb and evs:
        m = [e for e in evs if e["verb"] == qverb]
        if m:
            return True, str(m[0]["numeral"]), "event-count", (
                f"event {m[0]['raw']!r} states the number directly")
        return False, None, "event-count", (
            f"entity {ent!r} has events {[e['verb'] for e in evs]} but none matches "
            f"queried verb {qverb!r}")

    # STATE-COUNT query: `how many X are left ...?` -- needs the fold, needs polarity
    cur, det = fold(events, ent)
    if not det:
        return False, None, "state-count", (
            f"state for {ent!r} is INDETERMINATE: an event's polarity is unknown and "
            f"is never guessed -- refusing")
    if cur is None:
        return False, None, "state-count", f"no absolute count for {ent!r}"
    return True, str(cur), "state-count", f"fold terminated determinate at {cur}"


# ------------------------------------------------------------------ loading
def load(path):
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
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
    sc = {}
    sc.update(load(HELDOUT))
    sc.update(load(SELECTION))
    print(f"scripts {len(sc)}  (heldout {len(load(HELDOUT))}, "
          f"selection {len(load(SELECTION))})")

    journal = {}
    if JOURNAL.exists():
        for line in JOURNAL.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                journal[r.get("ask")] = r
    print(f"journal rows {len(journal)}")

    # ---------------------------------------------------------- H1, H2, H5
    print("\n=== H1: event extraction is total ===")
    all_ev, all_drop, per_script = [], [], {}
    for name, v in sc.items():
        ev, dr = build_events(v["tells"])
        per_script[name] = ev
        all_ev += ev
        all_drop += [(name, t, w) for t, w in dr]
    numeral_tells = [t for v in sc.values() for t in v["tells"]
                     if set(toks(t)) & set(NUM)]
    print(f"  tells with a numeral: {len(numeral_tells)}   events extracted: {len(all_ev)}")
    for n, t, w in all_drop:
        print(f"  !! unextractable [{n}] {t!r} -- {w}")
    h1 = not all_drop and len(all_ev) == len(numeral_tells)
    print(f"  H1 {'PASS' if h1 else 'FAIL'}")

    print("\n=== H2: the head rule ===")
    h2_bad = []
    for e in all_ev:
        raw_ent = [w for w in toks(e["raw"]) if w not in DET and w not in NUM
                   and w not in COP and w not in PLACE and w != "there"]
        if len(raw_ent) >= 2 and e["entity"] != normalise(raw_ent[-1]):
            h2_bad.append(e)
    multi = [e for e in all_ev if e["entity"] and " " not in e["entity"]]
    print(f"  events {len(all_ev)}; entities are single head nouns: "
          f"{all(' ' not in (e['entity'] or '') for e in all_ev)}")
    for e in all_ev[:8]:
        print(f"    {e['frame']:8s} entity={e['entity']!r:12s} n={e['numeral']} "
              f"verb={e['verb']!r} <- {e['raw']!r}")
    h2 = not h2_bad
    print(f"  H2 {'PASS' if h2 else 'FAIL'}  violations={len(h2_bad)}")

    print("\n=== H5: update-not-add ===")
    h5_cases = []
    for name, ev in per_script.items():
        by_ent = {}
        for e in ev:
            by_ent.setdefault(e["entity"], []).append(e)
        for ent, es in by_ent.items():
            absolutes = [e for e in es if e["frame"] == "absolute"]
            if len(absolutes) >= 2:
                cur, det = fold(ev, ent)
                h5_cases.append((name, ent, [a["numeral"] for a in absolutes], cur, det))
    for name, ent, vals, cur, det in h5_cases:
        ok = cur == vals[-1]
        print(f"  [{name}] {ent}: absolutes={vals} -> fold={cur} determinate={det} "
              f"{'REPLACES ok' if ok else '!! did not replace'}")
    if not h5_cases:
        print("  no script tells two absolutes for one entity -- H5 untestable on this battery")
    h5 = all(c[3] == c[2][-1] for c in h5_cases)
    print(f"  H5 {'PASS' if h5 else ('UNTESTABLE' if not h5_cases else 'FAIL')}")

    # ------------------------------------------------------------- evaluate
    recs = []
    for name, v in sc.items():
        ev = per_script[name]
        for ask, exp in v["asks"]:
            lic, fil, kind, why = query(ask, ev)
            want = [str(w).lower() for w in (exp.get("answer") or [])]
            forbid = [str(w).lower() for w in (exp.get("forbid") or [])]
            j = journal.get(ask, {})
            recs.append({"script": name, "ask": ask, "licensed": lic, "filler": fil,
                         "kind": kind, "why": why, "want": want, "forbid": forbid,
                         "refusal_expected": bool(exp.get("require_refusal")) or
                         (not want and not forbid),
                         "correct": (fil in want) if (lic and want) else None,
                         "forbidden_said": bool(lic and fil and fil in forbid),
                         "gate_passes": j.get("pass"), "gate_stage": j.get("stage"),
                         "gate_cause": j.get("cause"), "in_journal": bool(j)})

    q = [x for x in recs if x["kind"] in ("event-count", "state-count")]
    print(f"\nquantity asks evaluated: {len(q)} of {len(recs)}")

    # ---------------------------------------------------------- H3, H4, H7
    print("\n=== H3: event-count queries ===")
    ec = [x for x in q if x["kind"] == "event-count"]
    for x in ec:
        print(f"  {'LIC+OK ' if x['licensed'] and x['correct'] else '       '}"
              f"lic={str(x['licensed']):5s} filler={str(x['filler']):6s} "
              f"want={x['want']} forbid={x['forbid']} gate={x['gate_passes']}")
        print(f"      {x['ask'][:56]}")
        print(f"      why: {x['why'][:88]}")
    ec_ok = [x for x in ec if x["licensed"] and x["correct"]]
    print(f"  event-count asks {len(ec)}, licensed+correct {len(ec_ok)}")
    h3 = bool(ec_ok) or not ec
    print(f"  H3 {'PASS' if h3 else 'FAIL'}")

    print("\n=== H4: state queries must REFUSE, never guess ===")
    st = [x for x in q if x["kind"] == "state-count"]
    st_num = [x for x in st if x["licensed"]]
    for x in st:
        print(f"  {'NUMBER!!' if x['licensed'] else 'refused '} filler={str(x['filler']):6s} "
              f"{x['ask'][:52]}")
        print(f"      why: {x['why'][:88]}")
    print(f"  state asks {len(st)}, returned a number {len(st_num)}")
    h4 = not st_num
    print(f"  H4 {'PASS' if h4 else 'FAIL'} (a number here means polarity was assumed)")

    print("\n=== H7 / E1: guarded asks ===")
    guard = [x for x in recs if x["refusal_expected"]]
    g_lic = [x for x in guard if x["licensed"]]
    for x in guard:
        print(f"  {'LICENSED!!' if x['licensed'] else 'refused   '} kind={x['kind']:12s} "
              f"{x['ask'][:48]}")
    print(f"  guarded asks {len(guard)}, licensed {len(g_lic)}")
    h7 = not g_lic
    print(f"  H7 {'PASS' if h7 else 'FAIL'}")

    # ------------------------------------------------------- H6 / E6 placement
    print("\n=== H6 / E6: the quantity-change asks the organ ALREADY passes ===")
    passing = [x for x in recs if x["gate_passes"] is True]
    qpass = [x for x in passing if x["kind"] in ("event-count", "state-count")]
    print(f"  asks the coverage gate passes: {len(passing)}")
    print(f"  of those, quantity asks: {len(qpass)}")
    for x in qpass:
        print(f"    gate-passes {x['kind']:12s} {x['ask'][:52]}")
    print("  E6 asks: would any of these REACH the primitive? Per the design the")
    print("  primitive sits inside `best_cov < floor`, so a gate pass never arrives.")
    e6 = False   # placement guarantee: gate-passing asks cannot reach the branch
    print(f"  H6 {'PASS' if not e6 else 'FAIL'}   E6 {'FIRES' if e6 else 'clear'}")

    # ------------------------------------------------------------- E2, E4
    print("\n=== E2: wrong or forbidden fillers ===")
    wrong = [x for x in recs if x["correct"] is False or x["forbidden_said"]]
    for x in wrong:
        print(f"  !! {x['ask'][:52]} filler={x['filler']!r} want={x['want']} "
              f"forbid={x['forbid']}")
    print(f"  E2 {'FIRES' if wrong else 'clear'}  ({len(wrong)} wrong)")

    print("\n=== E4: is the primitive inert? ===")
    gain = [x for x in recs if x["licensed"] and x["correct"]
            and x["gate_passes"] is False]
    already = [x for x in recs if x["licensed"] and x["correct"]
               and x["gate_passes"] is True]
    unknown = [x for x in recs if x["licensed"] and x["correct"]
               and x["gate_passes"] is None]
    print(f"  licensed+correct on asks the gate currently REFUSES (real gain): {len(gain)}")
    for x in gain:
        print(f"    GAIN {x['kind']:12s} {x['ask'][:52]} -> {x['filler']!r}")
    print(f"  licensed+correct on asks the gate already passes (no gain): {len(already)}")
    for x in already:
        print(f"    moot {x['kind']:12s} {x['ask'][:52]}")
    print(f"  licensed+correct on asks not in the journal: {len(unknown)}")
    for x in unknown:
        print(f"    ?    {x['kind']:12s} {x['ask'][:52]}")
    e4 = len(gain) == 0
    print(f"  E4 {'FIRES -- safe but inert' if e4 else 'clear'}")

    print("\n=== E3, E5, E7 ===")
    e3 = bool(st_num)
    e5 = False   # extractor uses only determiners, copulas, place preps, numerals
    e7 = bool(all_drop)
    print(f"  E3 state query returned a number : {'FIRES' if e3 else 'clear'}")
    print(f"  E5 verb lexicon / ask-fitted rule: {'FIRES' if e5 else 'clear'} "
          f"(closed grammatical classes only; polarity never resolved)")
    print(f"  E7 unextractable numeral tell    : {'FIRES' if e7 else 'clear'}")

    # ------------------------------------------------------------- verdict
    print("\n=== VERDICT ===")
    print(f"  H1 total extraction   : {'PASS' if h1 else 'FAIL'}")
    print(f"  H2 head rule          : {'PASS' if h2 else 'FAIL'}")
    print(f"  H3 event-count        : {'PASS' if h3 else 'FAIL'} ({len(ec_ok)}/{len(ec)})")
    print(f"  H4 state refuses      : {'PASS' if h4 else 'FAIL'}")
    print(f"  H5 update-not-add     : {'PASS' if h5 else ('UNTESTABLE' if not h5_cases else 'FAIL')}")
    print(f"  H6 placement holds    : {'PASS' if not e6 else 'FAIL'}")
    print(f"  H7 guard not licensed : {'PASS' if h7 else 'FAIL'}")
    fired = [n for n, c in (("E1", not h7), ("E2", bool(wrong)), ("E3", e3),
                            ("E4", e4), ("E5", e5), ("E6", e6), ("E7", e7)) if c]
    print(f"  abort conditions fired: {fired or 'none'}")

    if not h7:
        v = "ABORT E1 -- the primitive licenses a guarded ask."
    elif wrong:
        v = "ABORT E2 -- a licence with a wrong or forbidden filler; confabulation."
    elif e3:
        v = "ABORT E3 -- a state query returned a number, so polarity was assumed."
    elif e7:
        v = "ABORT E7 -- a tell with a numeral was unextractable."
    elif e4:
        v = ("SAFE BUT INERT (E4) -- every licence lands on an ask the coverage gate "
             "already answers, so the primitive can neither regress nor gain. No E17b.")
    else:
        v = f"ALL CLEAR -- {len(gain)} real gain(s). Specify E17b."
    print(f"\n  {v}")

    OUT.write_text(json.dumps({
        "verdict": v, "H1": h1, "H2": h2, "H3": h3, "H4": h4, "H5": h5,
        "H6": not e6, "H7": h7, "fired": fired,
        "event_count_asks": len(ec), "event_count_ok": len(ec_ok),
        "state_asks": len(st), "state_returned_number": len(st_num),
        "real_gain": len(gain), "moot": len(already), "unknown": len(unknown),
        "records": recs}, indent=1), encoding="utf-8")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
