"""E24a -- read-only pre-test for the session-scoped absence inventory.

Design: docs/evidence/absence_inventory_design.md. This probe builds the inventory
OFFLINE from tools/scripts_heldout.json and tests the pre-registered conditions with
ZERO brain builds and ZERO organ changes. No organ behaviour, score, genome or state
is touched.

The decisive checks (design section 9):
  1. does the guarded scarf ask receive a LICENSED REFUSAL (subject present, place absent)?
  2. does any ask get licensed from a DIFFERENT subject's entry (the E15 failure)?
  3. how many asks fall through, leaving the existing path untouched (conservatism)?
  4. would any currently-PASSING ask change outcome?

Pre-registered abort: if (1) fails or (2) occurs, E24 is refuted before implementation.

Conservatism rule, and the whole difference from E15: extraction failure counts as
FALL_THROUGH, never as REFUSAL. Absence is licensed only by a positively-built
inventory, never by a failure to find something.

Usage:  python docs/evidence/e24a_absence_inventory_probe.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "tools" / "scripts_heldout.json"
JOURNAL = ROOT / "state" / "selection" / "generation_19_asks.jsonl"
OUT = ROOT / "docs" / "evidence" / "e24a_absence_inventory.json"

# Closed grammatical classes only -- no content vocabulary (design A8).
FUNCTION = {"the", "a", "an", "of", "by", "in", "on", "at", "to", "for", "and", "or",
            "but", "not", "no", "is", "are", "was", "were", "be", "been", "being",
            "do", "does", "did", "done", "it", "that", "this", "there", "i", "you",
            "me", "my", "your", "we", "they", "he", "she", "him", "her", "as", "than",
            "left", "ever", "any", "all", "both", "one", "thing", "things"}
INTERROG = {"what", "which", "who", "whom", "whose", "where", "when", "why", "how"}
QVERB = {"say", "said", "tell", "told", "mention", "mentioned", "name", "repeat"}
QMOD = {"often", "many", "much", "times", "time", "number", "about", "before",
        "after", "earlier", "last", "first", "true"}
STOP = FUNCTION | INTERROG | QVERB | QMOD

PLACE_PREP = {"on", "in", "at", "under", "beside", "near", "above", "below"}
COPULA = {"is", "are", "was", "were"}


def content(words):
    return [w for w in words if w not in STOP]


def extract_frame(tell):
    """Copula / locative / agent frames only -- the three classes E16a's extractor
    handled correctly. Quantity frames are out of scope (design section 5)."""
    t = re.sub(r"[^a-z ]", " ", str(tell).lower())
    w = [x for x in t.split() if x]
    if not w:
        return None
    # locative:  the X is on the Y
    for i, tok in enumerate(w):
        if tok in COPULA and i + 1 < len(w) and w[i + 1] in PLACE_PREP:
            subj = content(w[:i])
            obj = content(w[i + 2:])
            if len(subj) == 1 and obj:
                return ("place", subj[0], " ".join(obj))
    # property:  the X is Y
    for i, tok in enumerate(w):
        if tok in COPULA:
            subj = content(w[:i])
            obj = content(w[i + 1:])
            if len(subj) == 1 and len(obj) == 1:
                return ("property", subj[0], obj[0])
    # agent:  the X verbs the Y
    cw = content(w)
    if len(cw) >= 2:
        return ("agent", cw[0], " ".join(cw[1:]))
    return None


def build_inventory(tells):
    inv = defaultdict(dict)
    frames, failed = [], []
    for t in tells:
        f = extract_frame(t)
        if f is None:
            failed.append(t)
            continue
        rel, subj, obj = f
        inv[subj].setdefault(rel, obj)
        frames.append({"tell": t, "relation": rel, "subject": subj, "object": obj})
    return dict(inv), frames, failed


def queried_relation(ask):
    a = str(ask).lower()
    if a.startswith("where") or " where " in a:
        return "place"
    if re.search(r"\b(is|are)\s+\w+\s+(or|and)\b", a) or "what is" in a and "like" in a:
        return "property"
    if re.search(r"\bwhat does\b|\bwhat is \w+ by\b|\bwhat bites\b|\bwhat turns\b", a):
        return "agent"
    return None


def subject_of(ask, inv):
    """Bind by matching inventory subjects against the ask's content words. Never
    guesses a head noun -- E16a's head rule mis-binds multi-word subjects."""
    words = set(re.sub(r"[^a-z ]", " ", str(ask).lower()).split())
    hits = sorted(s for s in inv if s in words)
    if len(hits) == 1:
        return hits[0], False
    if len(hits) > 1:
        return None, True          # ambiguous -> fall through (conservative)
    return None, False             # subject absent -> fall through


def main():
    data = json.loads(SCRIPTS.read_text(encoding="utf-8"))
    scripts = data["scripts"]
    rows = [json.loads(l) for l in JOURNAL.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_ask = {str(r.get("ask")): r for r in rows}

    print(f"scripts {len(scripts)}; journal asks {len(rows)}")
    out = {"scripts": {}, "summary": {}}
    tot = defaultdict(int)
    scarf_result, cross_subject, changed_pass = None, [], []

    for sc in scripts:
        tells = [t["say"] for t in sc["turns"] if "say" in t]
        asks = [t for t in sc["turns"] if "ask" in t]
        inv, frames, failed = build_inventory(tells)
        print(f"\n=== script {sc['name']!r} kind={sc.get('kind')} ===")
        print(f"  tells {len(tells)} -> inventory subjects {sorted(inv)}")
        for s, rels in sorted(inv.items()):
            print(f"    {s}: {rels}")
        if failed:
            print(f"  UNEXTRACTED tells (count as fall_through, never refusal): {failed}")

        recs = []
        for t in asks:
            ask = t["ask"]
            rel = queried_relation(ask)
            subj, ambiguous = subject_of(ask, inv)
            if rel is None or subj is None:
                licence = "fall_through"
                reason = ("no queried relation" if rel is None
                          else "ambiguous subject" if ambiguous else "subject absent")
                filler = None
            elif rel in inv[subj]:
                licence, filler, reason = "answer", inv[subj][rel], "relation present"
            else:
                licence, filler, reason = "refusal", None, f"{rel} absent for {subj}"
            jr = by_ask.get(ask)
            passed = bool(jr.get("pass")) if jr else None
            rec = {"ask": ask, "queried_relation": rel, "subject": subj,
                   "licence": licence, "reason": reason, "filler": filler,
                   "journal_pass": passed,
                   "journal_cause": (jr or {}).get("cause_all"),
                   "journal_coverage": (jr or {}).get("coverage")}
            recs.append(rec)
            tot[licence] += 1
            print(f"  {licence:12s} rel={str(rel):9s} subj={str(subj):8s} "
                  f"pass={str(passed):5s} {ask[:46]!r}")
            if "scarf" in ask and ask.startswith("where"):
                scarf_result = rec
            if licence != "fall_through" and subj and any(
                    s != subj and s in str(ask).lower() for s in inv):
                cross_subject.append({"ask": ask, "bound": subj,
                                      "others_present": [s for s in inv if s != subj
                                                         and s in str(ask).lower()]})
            # Would a licence change a currently-passing ask's OUTCOME?
            # A passing ask that already refuses (cause=recall_gate, pass=True) is
            # unchanged by a refusal licence -- refusal -> refusal is the intended
            # guard preservation, not a regression. Only a passing ask that currently
            # ANSWERS would change.
            passes_by_refusal = passed and rec["journal_cause"] == "recall_gate"
            rec["passes_by_refusal"] = bool(passes_by_refusal)
            if passed and licence == "refusal" and not passes_by_refusal:
                changed_pass.append(rec)

        out["scripts"][sc["name"]] = {"inventory": inv, "frames": frames,
                                      "unextracted": failed, "asks": recs}

    print("\n=== SUMMARY ===")
    print(f"  licences: {dict(tot)}")
    out["summary"]["licences"] = dict(tot)

    print("\n=== DECISIVE CHECK 1: the guarded scarf ask ===")
    if scarf_result is None:
        print("  NOT FOUND in scripts -- cannot evaluate the guard")
        out["summary"]["scarf"] = "not_found"
    else:
        print(f"  ask      : {scarf_result['ask']!r}")
        print(f"  relation : {scarf_result['queried_relation']}")
        print(f"  subject  : {scarf_result['subject']}")
        print(f"  licence  : {scarf_result['licence']}  ({scarf_result['reason']})")
        print(f"  journal  : pass={scarf_result['journal_pass']} "
              f"cause={scarf_result['journal_cause']} cov={scarf_result['journal_coverage']}")
        ok = scarf_result["licence"] == "refusal"
        out["summary"]["scarf"] = scarf_result
        print(f"  --> licensed refusal: {'YES' if ok else 'NO'}")

    print("\n=== DECISIVE CHECK 2: cross-subject licences (the E15 failure) ===")
    print(f"  {len(cross_subject)} found")
    for c in cross_subject:
        print(f"    !! {c}")
    out["summary"]["cross_subject"] = cross_subject

    print("\n=== DECISIVE CHECK 3: currently-passing asks that would change ===")
    print(f"  {len(changed_pass)} passing ask(s) would receive a refusal licence")
    for c in changed_pass:
        print(f"    !! {c['ask']!r} bound={c['subject']} reason={c['reason']}")
    out["summary"]["changed_passing"] = changed_pass

    print("\n=== VERDICT ===")
    scarf_ok = bool(scarf_result) and scarf_result["licence"] == "refusal"
    no_cross = not cross_subject
    no_changed = not changed_pass
    print(f"  scarf licensed refusal        : {'PASS' if scarf_ok else 'FAIL'}")
    print(f"  no cross-subject licence      : {'PASS' if no_cross else 'FAIL'}")
    print(f"  no passing ask changes        : {'PASS' if no_changed else 'FAIL'}")
    viable = scarf_ok and no_cross and no_changed
    print(f"  E24a pre-registered abort     : {'NOT triggered -- proceed to review' if viable else 'TRIGGERED -- E24 refuted before implementation'}")
    out["summary"]["viable"] = viable
    out["summary"]["abort_triggered"] = not viable

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
