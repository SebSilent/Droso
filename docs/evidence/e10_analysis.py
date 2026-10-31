"""E10 analysis: arm A (gen 13, both flags off) vs arm B (gen 14, scope+content),
with gen 11 as the pre-E10 control reference.

Reports P1 (flag-off identity), P4/P6 (gained/lost/stage movement), P5 (zero
erosion) and the failure-stage census. Guarded counts come from the harness's own
summary column, not from a journal key -- e9_analysis.py looked for a `guarded`
field the ask journal does not carry and reported 0/0.
"""
from __future__ import annotations

import collections
import io
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SEL = os.path.join(ROOT, "state", "selection")
FIELDS = ("pass", "stage", "cause", "source", "coverage")


def asks(gen):
    p = os.path.join(SEL, "generation_%d_asks.jsonl" % gen)
    if not os.path.exists(p):
        return None
    rows = [json.loads(l) for l in io.open(p, encoding="utf-8") if l.strip()]
    return {(r.get("script"), r.get("ask")): r for r in rows}


def summary(gen):
    """The harness's own per-line summary: frozen, probes, guard."""
    p = os.path.join(SEL, "generation_%d.jsonl" % gen)
    if not os.path.exists(p):
        return None
    out = []
    for l in io.open(p, encoding="utf-8"):
        if not l.strip():
            continue
        r = json.loads(l)
        sc = r.get("scores") or r
        out.append({k: sc.get(k) for k in
                    ("frozen", "paraphrase", "guarded", "probe_all", "frozen_passed",
                     "probe_passed", "guard_passed") if k in sc})
    return out


def stages(d):
    c = collections.Counter()
    for r in d.values():
        if not r.get("pass"):
            c[r.get("stage") or "-"] += 1
    return dict(sorted(c.items(), key=lambda kv: -kv[1]))


def passes(d):
    return {k for k, r in d.items() if r.get("pass")}


def diff(a, b, label_a, label_b):
    ka, kb = set(a), set(b)
    print("  same ask set: %s  (%d vs %d)" % (ka == kb, len(ka), len(kb)))
    if ka != kb:
        print("    only in %s: %s" % (label_a, sorted(ka - kb)[:6]))
        print("    only in %s: %s" % (label_b, sorted(kb - ka)[:6]))
    nd = 0
    for k in sorted(ka & kb):
        for f in FIELDS:
            if a[k].get(f) != b[k].get(f):
                nd += 1
                if nd <= 14:
                    print("     ~ %s | %s\n        %s %s=%r\n        %s %s=%r"
                          % (k[0], k[1], label_a, f, a[k].get(f), label_b, f,
                             b[k].get(f)))
    print("  field differences: %d" % nd)
    return nd


def main():
    g11, g13, g14 = asks(11), asks(13), asks(14)
    for n, g in (("gen11", g11), ("gen13", g13), ("gen14", g14)):
        print("%s: %s" % (n, "%d rows" % len(g) if g else "MISSING"))
    if not (g13 and g14):
        print("\nbattery incomplete; nothing to compare")
        return

    print("\n=== HARNESS SUMMARY (authoritative for guarded) ===")
    for n, g in (("gen11 pre-E10", 11), ("gen13 ARM A control", 13),
                 ("gen14 ARM B scope+content", 14)):
        print("  %-28s %s" % (n, summary(g)))

    print("\n=== STAGES (failures only) ===")
    if g11:
        print("  gen11 / expected A  %s" % stages(g11))
    print("  gen13 ARM A         %s" % stages(g13))
    print("  gen14 ARM B         %s" % stages(g14))

    print("\n=== P1: flag-off identity (gen13 vs gen11) ===")
    if g11:
        nd = diff(g11, g13, "gen11", "gen13")
        print("  P1 VERDICT: %s" % ("PASS" if nd == 0 else "FAIL"))
    else:
        print("  gen11 missing; P1 not measurable")

    print("\n=== P4/P6: arm B vs arm A ===")
    pa, pb = passes(g13), passes(g14)
    gained, lost = sorted(pb - pa), sorted(pa - pb)
    print("  GAINED %d:" % len(gained))
    for k in gained:
        print("     + %s | %s  stage=%s" % (k[0], k[1], g14[k].get("stage")))
    print("  LOST %d:" % len(lost))
    for k in lost:
        print("     - %s | %s  stage=%s" % (k[0], k[1], g14[k].get("stage")))
    moved = [k for k in set(g13) & set(g14)
             if g13[k].get("stage") != g14[k].get("stage")
             or g13[k].get("source") != g14[k].get("source")]
    print("  stage/source changed, same verdict: %d" % len(moved))
    for k in sorted(moved)[:14]:
        print("     ~ %s | %s\n        A stage=%s source=%r\n        B stage=%s source=%r"
              % (k[0], k[1], g13[k].get("stage"), g13[k].get("source"),
                 g14[k].get("stage"), g14[k].get("source")))

    print("\n=== P5: zero erosion ===")
    print("  frozen passes lost : %s" % (sorted(lost) or "[]"))
    frz = {k for k in g13 if "sel-" not in str(k[0])}
    print("  frozen-tier lost   : %s" % (sorted(k for k in lost if k in frz) or "[]"))
    print("  P5 VERDICT: %s" % ("PASS" if not lost else "FAIL"))

    print("\n=== P6: new babble ===")
    spoke_a = {k for k, r in g13.items() if r.get("source")}
    spoke_b = {k for k, r in g14.items() if r.get("source")}
    print("  asks with a source, A=%d B=%d" % (len(spoke_a), len(spoke_b)))
    print("  newly speaking: %s" % (sorted(spoke_b - spoke_a) or "none"))
    print("  went silent   : %s" % (sorted(spoke_a - spoke_b) or "none"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
