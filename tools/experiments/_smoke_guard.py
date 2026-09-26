import sys, tempfile
sys.path.insert(0, "C:/Projects/HybridLLM")
from organs.code_assembler import CodeAssembler
from organs.planner import PlannerOrgan, _guard_test

code = ("def items_sum(items):\n    total = 0\n    for x in items:\n"
        "        total += x\n    return total\n")
a = CodeAssembler()
fn = "items_sum"
t = _guard_test(code, fn)
print("test:", repr(t))
r = a.add_condition(code, fn, t, "return None")
print("ok:", r.get("ok"), r.get("error", ""))
out = r.get("code", "")
print(out)
ns = {}
try:
    exec(out, ns)
    print("f([1,2,3]) =", ns["items_sum"]([1, 2, 3]))
    print("f(None) =", ns["items_sum"](None))
    print("f([]) =", ns["items_sum"]([]))
except Exception as e:
    print("EXEC FAIL:", type(e).__name__, e)