"""E24 phase 1 -- control verification. Read-only over the generation journals."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEL = ROOT / "state" / "selection"


def load(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def key(r):
    return (r.get("script"), r.get("ask"))


a = load(SEL / "generation_19_asks.jsonl")
b = load(SEL / "generation_20_asks.jsonl")
ka = {key(r): (r.get("pass"), r.get("stage")) for r in a}
kb = {key(r): (r.get("pass"), r.get("stage")) for r in b}

print(f"gen19 asks {len(a)} passes {sum(1 for r in a if r.get('pass'))}")
print(f"gen20 asks {len(b)} passes {sum(1 for r in b if r.get('pass'))}")
diff = [k for k in ka if ka[k] != kb.get(k)]
print(f"DIFFERING (pass,stage) keys: {len(diff)}")
for k in diff[:10]:
    print("   ", k, ka[k], kb.get(k))
print(f"CONTROL IDENTICAL: {ka == kb}")

g = json.loads((SEL / "generation_20.jsonl").read_text(encoding="utf-8"))
f = g.get("fitness", {})
print("gen20 capability.passed :", f.get("capability", {}).get("passed"))
print("gen20 generalisation    :", f.get("generalisation", {}).get("passed"))
print("gen20 regression        :", f.get("regression", {}).get("frozen_guarded_and_run"))
print("gen20 code_flags        :", (g.get("provenance") or {}).get("code_flags"))
print("gen20 genome_id         :", g.get("genome_id"))
