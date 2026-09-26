import sys, json
sys.path.insert(0, "C:/Projects/HybridLLM")
from world.reasoning_benchmark import TASKS, build_agent
from world.parity_benchmark import grade

which = sys.argv[1] if len(sys.argv) > 1 else "rt_api"
task = next(t for t in TASKS if t["id"] == which)
ag = build_agent()
r = ag.solve_task(task, grade_fn=grade)
print(json.dumps({k: v for k, v in r.items() if k != "results"},
                 indent=1, default=str)[:1500])
for e in ag.reasoning_log[-14:]:
    print(json.dumps(e, default=str)[:180])