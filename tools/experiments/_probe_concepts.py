import sys
sys.path.insert(0, "C:/Projects/HybridLLM")
from config_loader import load_config
from organs.safetensors_library import SafeTensorsLibrary
from organs.tokenizer import TokenizerOrgan
from organs.exocortex import ExocortexOrgan

cfg = load_config()
lib = SafeTensorsLibrary(dict(cfg.get("safetensors_library", {})))
tok = TokenizerOrgan()
exo = ExocortexOrgan(lib, tok)
for q in ("lua", "roblox", "function", "javascript", "html", "stack",
          "vector", "coroutine", "canvas"):
    hits = exo.search_concepts(q, k=3)
    print(q, "->", [(h.get("concept"), round(float(h.get("score", 0)), 3))
                    for h in hits][:3])
import json
ff = json.loads(open("C:/Projects/HybridLLM/exocortex/ffn_expertise.json",
                     encoding="utf-8").read())
concepts = list(ff.get("concepts", {}).keys()) if isinstance(
    ff.get("concepts"), dict) else ff.get("concepts", [])
print("ffn concepts sample:", [c for c in concepts
                               if any(s in str(c).lower() for s in
                                      ("lua", "js", "html", "class",
                                       "function", "vector"))][:12])