"""Load config/hybrid_config.json."""

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_PATH = _ROOT / "config" / "hybrid_config.json"

_PATH_KEYS = (("connectome", "project_root"),
              ("sandbox", "project_root"),
              ("sandbox", "workzone"))

def load_config() -> dict:
    cfg = json.loads(_PATH.read_text(encoding="utf-8"))
    for section, key in _PATH_KEYS:
        v = cfg.get(section, {}).get(key)
        if isinstance(v, str) and v.strip():
            p = Path(v)
            if not p.is_absolute():
                p = _ROOT / p
            cfg[section][key] = str(p.resolve())
    return cfg