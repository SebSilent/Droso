import shutil
from pathlib import Path
EXO = Path("C:/Projects/HybridLLM/exocortex")
moved = []
for name in ("procedures", "speed_routing.json", "error_knowledge.json",
             "residual_cache"):
    p = EXO / name
    if p.exists():
        q = EXO / (name + ".v6bak")
        if q.exists():
            shutil.rmtree(q) if q.is_dir() else q.unlink()
        p.rename(q)
        moved.append(name)
print("hid:", moved)