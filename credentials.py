from __future__ import annotations

import getpass
import json
import os
import sys
from pathlib import Path

APP_NAME = "HybridLLM"
ROLES = ("model", "autotraining")
OFFLINE_ENV = "HYBRIDLLM_OFFLINE"

def store_dir() -> Path:
    """The per-user application-data directory for this app."""
    override = os.environ.get("HYBRIDLLM_CONFIG_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / APP_NAME
        return Path.home() / "AppData" / "Roaming" / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / APP_NAME
    return Path.home() / ".config" / APP_NAME

def store_path() -> Path:
    return store_dir() / "credentials.json"

def _locked(path: Path) -> None:
    """Best-effort owner-only permissions (POSIX; a no-op on Windows, where
    the file inherits the user profile's ACL, already private to the user)."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass

def _load() -> dict:
    p = store_path()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

def _save(data: dict) -> None:
    p = store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1), encoding="utf-8")
    _locked(p)

def get_key(role: str = "model", provider: str | None = None) -> str | None:
    """The stored key for a role, or None. `provider` is accepted for future
    per-provider entries; today one key per role is the whole model.

    Returns None when HYBRIDLLM_OFFLINE is set: an ambient credential is a
    real one, and the offline fence exists so nothing (env var or store) can
    turn a test run into a billed call. An explicitly passed key still works
    -- see organs/api_oracle.py for where that seam lives."""
    if os.environ.get(OFFLINE_ENV):
        return None
    data = _load()
    block = data.get(role)
    if isinstance(block, str):
        block = {"api_key": block}
    key = str(block.get("api_key") or "").strip() \
        if isinstance(block, dict) else ""
    if key:
        return key
    if role != "model":
        return get_key("model", provider)
    return None

def set_key(role: str, key: str) -> dict:
    key = str(key or "").strip()
    if not key:
        raise ValueError("empty key")
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}; known: {', '.join(ROLES)}")
    data = _load()
    block = data.get(role) if isinstance(data.get(role), dict) else {}
    block["api_key"] = key
    data[role] = block
    _save(data)
    return {"stored": True, "role": role, "path": str(store_path()),
            **fingerprint(key)}

def delete_key(role: str) -> dict:
    data = _load()
    existed = role in data
    data.pop(role, None)
    if data:
        _save(data)
    elif store_path().exists():
        store_path().unlink()
    return {"cleared": existed, "role": role, "path": str(store_path())}

def fingerprint(key: str | None) -> dict:
    """What may be SHOWN about a key: shape and length, never the secret.
    Enough to tell "stored" from "wrong", not enough to use."""
    if not key:
        return {"present": False}
    return {"present": True,
            "hint": f"{key[:6]}...{key[-4:]} ({len(key)} chars)",
            "length": len(key)}

def status() -> dict:
    offline = bool(os.environ.get(OFFLINE_ENV))
    out = {"store": str(store_path()),
           "exists": store_path().exists(),
           "offline_fence": offline,
           "roles": {}}
    for role in ROLES:
        key = None if offline else get_key(role)
        out["roles"][role] = {"stored": key is not None,
                              **({"fingerprint": fingerprint(key)["hint"]}
                                 if key else {})}
    return out

def _main(argv=None) -> int:
    ap_desc = "Manage HybridLLM API keys (stored outside the project)."
    import argparse
    ap = argparse.ArgumentParser(description=ap_desc)
    sub = ap.add_subparsers(dest="cmd")
    for name in ("set", "show", "clear"):
        p = sub.add_parser(name)
        p.add_argument("role", nargs="?", default="model",
                       choices=ROLES, help="which oracle the key belongs to")
    sub.add_parser("status")
    sub.add_parser("path")
    args = ap.parse_args(argv)

    if args.cmd == "path":
        print(store_path())
        return 0
    if args.cmd == "status":
        s = status()
        print(f"store      {s['store']}  ({'exists' if s['exists'] else 'not created yet'})")
        if s["offline_fence"]:
            print("fence      HYBRIDLLM_OFFLINE is set: stored keys are ignored")
        for role, r in s["roles"].items():
            fp = r.get("fingerprint", "not stored")
            print(f"{role:<11}{fp}")
        if not any(r["stored"] for r in s["roles"].values()) and not s["offline_fence"]:
            print("\nno key stored -- the oracle will raise rather than answer.")
            print(f"run: python {Path(__file__).name} set model")
        return 0
    if args.cmd == "set":
        prompt = f"API key for {args.role} (input hidden): "
        key = getpass.getpass(prompt).strip()
        if not key:
            print("nothing entered; nothing stored.")
            return 2
        print(f"stored: {set_key(args.role, key)['hint']}  ->  {store_path()}")
        return 0
    if args.cmd == "show":
        key = get_key(args.role)
        if not key:
            print(f"no key stored for {args.role}.")
            return 1
        print(f"{args.role}: {fingerprint(key)['hint']}")
        return 0
    if args.cmd == "clear":
        r = delete_key(args.role)
        print(f"cleared {args.role}: {r['cleared']}")
        return 0
    ap.print_help()
    return 0

if __name__ == "__main__":
    raise SystemExit(_main())