import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from organs.api_oracle import oracle_from_config
from organs.language_organ import LanguageOrgan

cfg = json.loads((ROOT / "config" / "hybrid_config.json").read_text("utf-8"))
oracle = oracle_from_config(cfg)
print(f"oracle: {oracle.provider}/{oracle.model} @ {oracle.base_url} "
      f"mode={oracle.mode} thinking={oracle.thinking}")
tmp = Path(tempfile.mkdtemp(prefix="lang_probe_")) / "language_state.json"
organ = LanguageOrgan(config=cfg, state_path=tmp)
print(f"before: {organ!r}  readiness={organ.readiness()}")

r = organ.initial_training(oracle, max_tokens=1600)
print("\nteacher reply summary:", json.dumps(
    {k: v for k, v in r.items() if k != "raw_head"}, indent=1)[:900])
if not r.get("ok"):
    print("raw head:", r.get("raw_head", "")[:600])
    print("VERDICT: language acquisition failed")
    sys.exit(1)

print(f"\nafter: {organ!r}")
print("readiness:", json.dumps(organ.readiness(), indent=1))
sample = organ.list_vocabulary(limit=6)["vocabulary"]
print("sample entries:", json.dumps(sample, indent=1)[:1200])
print("rules:", json.dumps(organ.list_grammar_rules(limit=3), indent=1)[:600])
print("patterns:", json.dumps(organ.list_communication_patterns(limit=3),
                              indent=1)[:700])
print("gloss():", organ.gloss("the connectome verified procedure and reported failure"))
print("utter(greeting):", json.dumps(organ.utter("greeting"), indent=1))
print(f"\ncalls={oracle.calls} "
      f"tokens={oracle.tokens_prompt}+{oracle.tokens_completion}")
print("state file:", tmp, tmp.stat().st_size, "bytes")
print("VERDICT: language acquisition works against the live teacher")