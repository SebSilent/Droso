import sys
sys.path.insert(0, "C:/Projects/HybridLLM")
from organs.language_detector import LanguageDetector
from organs.language_paradigms import LanguageParadigms
from organs.planner import PlannerOrgan
from world.parity_benchmark import grade
from world.multilang_benchmark import TASKS

det = LanguageDetector()
for tid in ("ml_lua", "ml_html", "ml_js", "ml_cpp"):
    t = next(x for x in TASKS if x["id"] == tid)
    existing = "".join((t.get("setup") or {}).values())
    p = PlannerOrgan(None)
    plan = p.create_plan(t["text"], {"op": "ADD_VARIABLE", "name": "state_tracking"},
                         existing, language=t["true_language"])
    print("====", tid, t["true_language"])
    for s in plan:
        print("   ", s["action"], "|", s["target"], "|", repr(s["content"])[:90])