"""E25 -- user-visible capability changes only. No closure diagnostics."""
import json
from pathlib import Path

SEL = Path(__file__).resolve().parents[2] / "state" / "selection"


def load(p):
    return {(r["script"], r["ask"]): r
            for r in (json.loads(x) for x in
                      p.read_text(encoding="utf-8").splitlines() if x.strip())}


c = load(SEL / "generation_21_asks.jsonl")
t = load(SEL / "generation_22_asks.jsonl")

print("=== NEWLY ANSWERED (was silent/refusing, now gives an answer) ===")
n = 0
for k in sorted(c, key=lambda x: x[1]):
    a, b = c[k], t.get(k)
    if b is None:
        continue
    if not a.get("pass") and b.get("pass"):
        n += 1
        print(f"  {k[1]!r}")
        print(f"     before: said={str(a.get('said'))[:70]!r}")
        print(f"     after : said={str(b.get('said'))[:70]!r}")
print(f"  count: {n}")

print("\n=== NEWLY BROKEN (was answered, now silent/refusing) ===")
m = 0
for k in sorted(c, key=lambda x: x[1]):
    a, b = c[k], t.get(k)
    if b is None:
        continue
    if a.get("pass") and not b.get("pass"):
        m += 1
        print(f"  {k[1]!r}")
print(f"  count: {m}")

print("\n=== ANSWER TEXT CHANGED ON AN ASK BOTH ARMS PASS ===")
d = 0
for k in sorted(c, key=lambda x: x[1]):
    a, b = c[k], t.get(k)
    if b is None or not (a.get("pass") and b.get("pass")):
        continue
    if a.get("said") != b.get("said"):
        d += 1
        print(f"  {k[1]!r}")
        print(f"     {str(a.get('said'))[:60]!r} -> {str(b.get('said'))[:60]!r}")
print(f"  count: {d}")

pc = sum(1 for r in c.values() if r.get("pass"))
pt = sum(1 for r in t.values() if r.get("pass"))
print(f"\nTOTAL ANSWERED: {pc}/42 -> {pt}/42")
print(f"NET USER-VISIBLE GAIN: {pt - pc:+d}")
