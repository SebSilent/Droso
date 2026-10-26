# One-off: assemble the fresh-set cross-session comparison table that
# cross_session_20261026_013730.json could not carry (its ensure_baseline
# ran on the pre-fix code, so its baseline columns are None by
# construction).  Warm/cold come from the separately-run baseline
# reports, ask from the cross-session report, x-cold = ask - cold.
# All components predate the question-shape parser (commit 780c514,
# 07:15); the parser's own post-parser fresh warm/cold table lives in
# docs/speech_log.md's parser entry.
import json

CROSS = "state/fitness/cross_session_20261026_013730.json"
FIT = "state/fitness/"


def rate(path):
    d = json.load(open(path, encoding="utf-8"))
    return (d.get("benchmark") or {}).get("pass_rate")


cross = json.load(open(CROSS, encoding="utf-8"))
asks = {r["name"]: (r.get("ask") or {}).get("pass_rate") for r in cross["rows"]}

print(f"{'script':<22} {'warm':>5} {'cold':>5} {'ask':>5} {'x-cold':>7}")
ws = cs = xs = 0.0
n = 0
for name in sorted(asks):
    warm = rate(f"{FIT}conversation_script_{name}_warm.json")
    cold = rate(f"{FIT}conversation_script_{name}_cold.json")
    ask = asks[name]
    xc = ask - cold if None not in (ask, cold) else None
    print(f"{name:<22} {warm:>5} {cold:>5} {ask:>5} "
          f"{('%+.2f' % xc) if xc is not None else '-':>7}")
    ws += warm; cs += cold; xs += ask; n += 1
print(f"{'overall':<22} {ws/n:>5.3f} {cs/n:>5.3f} {xs/n:>5.3f} "
      f"{('%+.2f' % (xs/n - cs/n)):>7}")