#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

CANDIDATE_BASES = [
    "https://api.z.ai/api/coding/paas/v4",
    "https://api.z.ai/api/paas/v4",
]

def post(url: str, key: str, payload: dict, timeout: float = 45.0):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"},
        method="POST")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace")), \
                time.perf_counter() - t0
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            body = json.loads(body)
        except Exception:
            pass
        return e.code, body, time.perf_counter() - t0
    except Exception as e:
        return None, f"{type(e).__name__}: {e}", time.perf_counter() - t0

def list_models(key: str):
    out = {}
    for base in CANDIDATE_BASES:
        url = base.rstrip("/") + "/models"
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {key}"}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=20.0) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            out[base] = sorted(m.get("id", "?") for m in
                               (data.get("data") or data.get("model_list") or []))
        except Exception as e:
            out[base] = f"{type(e).__name__}: {str(e)[:160]}"
    return out

def build_payload(model: str, max_tokens: int, prompt: str, thinking, system):
    payload = {"model": model, "max_tokens": max_tokens, "temperature": 0.6,
               "messages": [{"role": "user", "content": prompt}]}
    if system:
        payload["messages"].insert(0, {"role": "system", "content": system})
    if thinking:
        payload["thinking"] = {"type": thinking}
    return payload

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-tokens", type=int, default=16)
    ap.add_argument("--prompt", default="Reply with exactly one word: what color is the sky?")
    ap.add_argument("--provider-key", default="model")
    ap.add_argument("--thinking", default=None,
                    help="enabled|disabled -> payload thinking.type")
    ap.add_argument("--system", default=None)
    ap.add_argument("--only", default=None, help="substring filter on base urls")
    ap.add_argument("--skip-models", action="store_true")
    args = ap.parse_args()

    cfg = json.loads((ROOT / "config" / "hybrid_config.json").read_text("utf-8"))
    block = cfg.get(args.provider_key, {}) or {}
    import sys as _sys
    _sys.path.insert(0, str(ROOT))
    from credentials import get_key
    key = get_key(args.provider_key, provider=block.get("provider"))
    model = block.get("model") or block.get("name")
    cfg_base = block.get("base_url")
    if not key:
        print(f"NO KEY for role '{args.provider_key}' in the credential store "
              f"(python credentials.py set {args.provider_key}) - nothing to probe.")
        return 2
    bases = [cfg_base] + [b for b in CANDIDATE_BASES if b != cfg_base] if cfg_base \
        else CANDIDATE_BASES

    print(f"model from config: {model!r}   provider: {block.get('provider')!r}")
    print(f"key: {key[:6]}...{key[-4:]}  (len {len(key)})")
    if args.only:
        bases = [b for b in bases if args.only in b]
    if not args.skip_models:
        print("\n-- GET /models --")
        for base, names in list_models(key).items():
            if isinstance(names, list):
                print(f"{base}\n   {len(names)} models: {names}")
            else:
                print(f"{base}\n   {names}")

    print("\n-- POST /chat/completions --")
    any_ok = False
    for base in bases:
        url = base.rstrip("/") + "/chat/completions"
        payload = build_payload(model, args.max_tokens, args.prompt,
                                args.thinking, args.system)
        status, body, dt = post(url, key, payload)
        if isinstance(body, dict):
            choice = (body.get("choices") or [{}])[0]
            text = ((choice.get("message") or {}).get("content") or "")[:200]
            err = body.get("error") or body.get("msg") or body.get("message")
            usage = body.get("usage") or {}
        else:
            text, err, usage = "", str(body)[:300], {}
        ok = bool(text)
        any_ok = any_ok or ok
        print(f"{'PASS' if ok else 'FAIL'}  {base}  [{status}] {dt:.2f}s")
        if not ok:
            print(f"      raw  : {json.dumps(body, ensure_ascii=False)[:1200]}")
        else:
            msg = (body.get("choices") or [{}])[0].get("message") or {}
            if msg.get("reasoning_content"):
                print(f"      think: {str(msg['reasoning_content'])[:120]!r}")
        if text:
            print(f"      text : {text!r}")
            print(f"      usage: {usage}")
            print(f"      model: {body.get('model')}")
        if err:
            print(f"      error: {json.dumps(err)[:400] if isinstance(err, dict) else err}")
    print(f"\nVERDICT: {'a real answer came back' if any_ok else 'no endpoint answered'}")
    return 0 if any_ok else 1

if __name__ == "__main__":
    raise SystemExit(main())