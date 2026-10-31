"""E9 analysis: P1, P4, P5, P6 from the generation 11 (control) and 12 (scoped) journals.

P1 flag-off identity with generation 10, ask for ask.
P4 probe/frozen/guarded movement.
P5 zero erosion.
P6 every ask arm B speaks and arm A did not, by name, with its wanted answer.
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SEL = "state/selection"


def load(gen):
    p = os.path.join(SEL, "generation_%d_asks.jsonl" % gen)
    if not os.path.exists(p):
        return None
    return [json.loads(l) for l in io.open(p, encoding="utf-8") if l.strip()]


def key(r):
    return (r.get("script"), r.get("ask"))


def scores(rows):
    f = [r for r in rows if r.get("tier") == "frozen"]
    p = [r for r in rows if r.get("tier") == "probe"]
    g = [r for r in p if r.get("guarded")]
    para = [r for r in p if not r.get("guarded")]
    return {
        "frozen": "%d/%d" % (sum(1 for r in f if r.get("pass")), len(f)),
        "paraphrase": "%d/%d" % (sum(1 for r in para if r.get("pass")), len(para)),
        "guarded": "%d/%d" % (sum(1 for r in g if r.get("pass")), len(g)),
        "probe_all": "%d/%d" % (sum(1 for r in p if r.get("pass")), len(p)),
    }


def stages(rows):
    d = {}
    for r in rows:
        if not r.get("pass"):
            d[r.get("stage")] = d.get(r.get("stage"), 0) + 1
    return dict(sorted(d.items(), key=lambda kv: -kv[1]))


g10, g11, g12 = load(10), load(11), load(12)
for n, g in (("gen10", g10), ("gen11", g11), ("gen12", g12)):
    print("%s: %s" % (n, "MISSING" if g is None else "%d rows" % len(g)))
if g11 is None or g12 is None:
    sys.exit("E9 journals incomplete")

print("\n=== SCORES ===")
for n, g in (("gen10 baseline", g10), ("gen11 ARM A control", g11),
             ("gen12 ARM B scoped", g12)):
    if g:
        print("  %-22s %s" % (n, json.dumps(scores(g))))

print("\n=== STAGES (failures only) ===")
for n, g in (("gen10", g10), ("gen11 A", g11), ("gen12 B", g12)):
    if g:
        print("  %-8s %s" % (n, json.dumps(stages(g))))

# ---- P1: arm A identical to gen 10 -------------------------------------
print("\n=== P1: flag-off identity (gen11 vs gen10) ===")
if g10:
    a = {key(r): r for r in g10}
    b = {key(r): r for r in g11}
    print("  same ask set:", set(a) == set(b))
    diffs = []
    for k in sorted(set(a) & set(b), key=str):
        for f in ("pass", "stage", "cause", "source", "coverage"):
            if a[k].get(f) != b[k].get(f):
                diffs.append((k, f, a[k].get(f), b[k].get(f)))
    print("  field differences:", len(diffs))
    for d in diffs[:20]:
        print("    ", d)
    print("  P1 VERDICT:", "PASS" if not diffs and set(a) == set(b) else "FAIL")

# ---- P4 / P6: arm B vs arm A -------------------------------------------
print("\n=== P4/P6: arm B (scoped) vs arm A (control) ===")
a = {key(r): r for r in g11}
b = {key(r): r for r in g12}
print("  same ask set:", set(a) == set(b))
gained, lost, changed = [], [], []
for k in sorted(set(a) & set(b), key=str):
    pa, pb = bool(a[k].get("pass")), bool(b[k].get("pass"))
    if pb and not pa:
        gained.append(k)
    elif pa and not pb:
        lost.append(k)
    elif a[k].get("stage") != b[k].get("stage") or a[k].get("source") != b[k].get("source"):
        changed.append(k)
print("  GAINED %d:" % len(gained))
for k in gained:
    print("     +", k[0], "|", k[1], "| wanted=", b[k].get("wanted"),
          "| stage", a[k].get("stage"), "->", b[k].get("stage"))
print("  LOST %d:" % len(lost))
for k in lost:
    print("     -", k[0], "|", k[1], "| stage", a[k].get("stage"), "->", b[k].get("stage"))
print("  stage/source changed but same pass verdict: %d" % len(changed))
for k in changed:
    print("     ~", k[0], "|", k[1])
    print("        A stage=%s source=%r" % (a[k].get("stage"), a[k].get("source")))
    print("        B stage=%s source=%r" % (b[k].get("stage"), b[k].get("source")))

# ---- P5: zero erosion ---------------------------------------------------
print("\n=== P5: zero erosion ===")
ga = [r for r in g11 if r.get("guarded")]
gb = [r for r in g12 if r.get("guarded")]
print("  guarded A: %d/%d   guarded B: %d/%d" % (
    sum(1 for r in ga if r.get("pass")), len(ga),
    sum(1 for r in gb if r.get("pass")), len(gb)))
fa = [r for r in g11 if r.get("tier") == "frozen"]
fb = [r for r in g12 if r.get("tier") == "frozen"]
print("  frozen  A: %d/%d   frozen  B: %d/%d" % (
    sum(1 for r in fa if r.get("pass")), len(fa),
    sum(1 for r in fb if r.get("pass")), len(fb)))
lostf = [key(r) for r in fa if r.get("pass")]
lostf2 = {key(r) for r in fb if r.get("pass")}
print("  frozen passes lost:", [k for k in lostf if k not in lostf2])
lostg = {key(r) for r in ga if r.get("pass")}
lostg2 = {key(r) for r in gb if r.get("pass")}
print("  guarded passes lost:", [k for k in lostg if k not in lostg2])

# ---- the mouth class specifically ---------------------------------------
print("\n=== the four mouth asks ===")
for k in sorted(set(a) | set(b), key=str):
    ra, rb = a.get(k), b.get(k)
    if not ra or not rb:
        continue
    if ra.get("stage") == "mouth" or rb.get("stage") == "mouth":
        print("  ", k[0], "|", k[1])
        print("     A pass=%s stage=%s source=%r" % (
            ra.get("pass"), ra.get("stage"), ra.get("source")))
        print("     B pass=%s stage=%s source=%r" % (
            rb.get("pass"), rb.get("stage"), rb.get("source")))
