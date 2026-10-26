# One-off: summarize speech-suite reports (turns with pass flags).
import json
import glob
import sys

paths = sorted(glob.glob("state/fitness/conversation_shape*.json"))
if len(sys.argv) > 1:
    paths = [p for p in paths if sys.argv[1] in p]
for p in paths:
    if "arbiter" in p:
        continue
    d = json.load(open(p, encoding="utf-8"))
    b = d.get("benchmark", {})
    turns = b.get("turns", [])
    graded = [t for t in turns if t.get("pass") is not None]
    npass = sum(1 for t in graded if t["pass"])
    fails = [t.get("ask") or t.get("say") for t in graded if not t["pass"]]
    print(f"{p.split('conversation_')[1].replace('.json',''):28} "
          f"{npass}/{len(graded)}  fails={fails}")