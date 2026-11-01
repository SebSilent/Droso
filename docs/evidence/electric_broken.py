import json
from pathlib import Path

SEL = Path("state/selection")


def load(p):
    return {(r["script"], r["ask"]): r
            for r in (json.loads(x) for x in
                      (SEL / p).read_text(encoding="utf-8").splitlines() if x.strip())}


c = load("generation_21_asks.jsonl")
t = load("generation_24_asks.jsonl")
for k in sorted(c, key=lambda x: x[1]):
    a, b = c[k], t.get(k)
    if b and a.get("pass") and not b.get("pass"):
        print("=== BROKEN:", repr(k[1]), "  script", k[0])
        print("  ctl pass", a.get("pass"), "ctl said ", repr(a.get("said")))
        print("  trt pass", b.get("pass"), "trt said ", repr(b.get("said")))
        print("  trt stage", b.get("stage"), " reason", repr(b.get("reason"))[:120])
        print("  trt keys", sorted(x for x in b if x not in
                                   ("script", "ask", "said", "pass", "stage")))
        print("  gold/expected:", repr(a.get("gold")), repr(a.get("expected")),
              repr(a.get("answer")), repr(b.get("gold")), repr(b.get("expected")))
