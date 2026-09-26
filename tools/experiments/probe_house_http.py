#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

def http(port, path, payload=None, timeout=60):
    url = f"http://127.0.0.1:{port}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"_raw": raw[:200]}
    except Exception as e:
        return -1, {"_error": f"{type(e).__name__}: {e}"}

GETS = ["/api/state", "/api/full_state", "/api/organs", "/api/consciousness",
        "/api/autotraining/state", "/api/autotraining/log",
        "/api/language/state", "/api/language/store", "/api/config",
        "/api/progress", "/api/thoughts", "/api/guarantee", "/api/neural/state"]

SHAPE = {
    "/api/state": ["house", "stats", "mental"],
    "/api/organs": ["autotraining", "language", "heartbeat", "api_oracle"],
    "/api/autotraining/state": ["enabled", "running", "cycle_count", "teacher",
                                "teacher_mode", "teacher_has_key", "note"],
    "/api/autotraining/log": ["entries"],
    "/api/language/state": ["present", "vocabulary_size", "word_patterns",
                            "can_speak", "min_vocabulary", "neural_basis",
                            "recent_words"],
    "/api/language/store": ["present", "vocabulary", "total"],
    "/api/config": ["model", "autotraining", "provider_choices"],
    "/api/guarantee": ["guarantees", "limits", "verdict"],
    "/api/neural/state": ["graph_loaded", "neuron_count", "synapse_count",
                          "plastic_synapses", "recent_activity", "lived_time"],
}

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=7799)
    ap.add_argument("--live", action="store_true",
                    help="allow real provider calls (one chat turn)")
    args = ap.parse_args(argv)

    env = dict(os.environ)
    if not args.live:
        env["HYBRIDLLM_OFFLINE"] = "1"
    else:
        env.pop("HYBRIDLLM_OFFLINE", None)
    child = subprocess.Popen(
        [sys.executable, str(ROOT / "run_house.py"), "--json", "--port",
         str(args.port), "--no-language-training"],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, env=env)
    ok = True
    try:
        deadline = time.time() + 90
        while time.time() < deadline:
            st, _ = http(args.port, "/api/state", timeout=2)
            if st == 200:
                break
            if child.poll() is not None:
                print("FATAL: the house process exited before serving")
                print((child.stdout.read() or "")[-2500:])
                return 1
            time.sleep(0.5)
        else:
            print("FATAL: the house never answered /api/state within 90s")
            print((child.stdout.read() or "")[-2500:])
            return 1

        print(f"--- startup record ---")
        st, boot = http(args.port, "/api/state")
        print(f"    url={boot['house'].get('url')} access={boot['house'].get('access')}"
              f" guarding={boot['house'].get('project_root')}")

        print(f"--- GET sweep (port {args.port}, "
              f"{'LIVE' if args.live else 'OFFLINE fence on'}) ---")
        bodies = {}
        for path in GETS:
            st, body = http(args.port, path)
            bodies[path] = body
            miss = [k for k in SHAPE.get(path, [])
                    if not isinstance(body, dict) or k not in body]
            good = st == 200 and not miss
            ok &= good
            keys = sorted(body)[:6] if isinstance(body, dict) else type(body)
            print(f"  [{'ok ' if good else 'BAD'}] {path:28s} {st} keys={keys}"
                  + (f"  MISSING={miss}" if miss else ""))

        for asset in ("autotraining.js", "language.js", "app.js", "style.css"):
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{args.port}/static/{asset}",
                        timeout=15) as r:
                    n = len(r.read())
                print(f"  [ok ] static/{asset:20s} {n} bytes")
            except Exception as e:
                ok = False
                print(f"  [BAD] static/{asset}: {e}")

        with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/",
                                    timeout=15) as r:
            html = r.read().decode("utf-8", "replace")
        for tab in ("training-panel", "language-panel", "neural-panel", "toggle-llm",
                    "toggle-autotraining", "lang-train", "train-now",
                    "at-state", "at-log", "at-cycle", "lang-vocab",
                    "lang-grammar", "lang-patterns"):
            found = f'id="{tab}"' in html
            ok &= found
            print(f"  [{'ok ' if found else 'BAD'}] #{tab} in the served page")
        for view in ("training", "language"):
            found = f'data-view="{view}"' in html
            ok &= found
            print(f"  [{'ok ' if found else 'BAD'}] tab data-view={view} "
                  f"(app.js binds .tab[data-view])")

        from credentials import get_key
        real = get_key("model")
        shown = ((bodies["/api/config"].get("model") or {}).get("api_key"))
        leaked = bool(real) and str(real) in json.dumps(bodies["/api/config"])
        ok &= not leaked
        print(f"  [{'ok ' if not leaked else 'BAD'}] /api/config redacts the stored "
              f"key (shown as {str(shown)[:38]!r})")

        st, chat = http(args.port, "/api/chat", {"message": "What is a cache?"},
                        timeout=120)
        resp = str(chat.get("response", ""))
        good = st == 200 and bool(chat.get("path"))
        ok &= good
        print(f"  [{'ok ' if good else 'BAD'}] POST /api/chat {st} "
              f"path={chat.get('path')} oracle_mode={chat.get('oracle_mode')} "
              f"ms={chat.get('ms')}")
        print(f"        reply[:170] {resp[:170]!r}")
        if args.live:
            print(f"        served: mode={chat.get('oracle_mode')} "
                  f"tokens={chat.get('tokens')}")
        else:
            notes = json.dumps((chat.get("notes") or []) +
                               [chat.get("response", "")]).lower()
            refuses = ("no api key" in notes or "offline" in notes or
                       "fenced" in notes or chat.get("response", "") == "")
            ok &= refuses and "mock" not in notes
            print(f"  [{'ok ' if refuses else 'BAD'}] the fenced turn produced "
                  f"no invented text (notes: "
                  f"{(chat.get('notes') or ['none'])[:1]})")

        _, tog = http(args.port, "/api/llm/toggle", {"enabled": False})
        _, mid = http(args.port, "/api/chat", {"message": "hello?"}, timeout=60)
        _, back = http(args.port, "/api/llm/toggle", {"enabled": True})
        good = (tog.get("llm_enabled") is False and back.get("llm_enabled")
                is True)
        ok &= good
        print(f"  [{'ok ' if good else 'BAD'}] llm switch round-trips "
              f"({tog.get('llm_enabled')} -> {back.get('llm_enabled')}); "
              f"switch-off reply: {str(mid.get('response'))[:80]!r}")

        _, run = http(args.port, "/api/autotraining/run", {})
        rec = run.get("cycle") or {}
        if args.live:
            good = rec.get("status") == "success" and rec.get("lesson")
            ok &= bool(good)
            print(f"  [{'ok ' if good else 'BAD'}] LIVE teacher cycle: "
                  f"{str((rec.get('lesson') or {}).get('title'))[:60]!r} -> "
                  f"{str(rec.get('applied', {}).get('summary'))[:60]!r}")
            print(f"        analysis from the teacher: "
                  f"{str(rec.get('analysis'))[:120]!r}")
            print(f"        spent {rec.get('tokens')} tokens")
        else:
            good = (run.get("success") is False and rec.get("reason") in
                    ("no_api_key", "offline_mode", "no_teacher_configured",
                     "disabled"))
            ok &= good
            print(f"  [{'ok ' if good else 'BAD'}] a cycle with no usable teacher "
                  f"refuses ({rec.get('reason')}) and learns nothing")

        _, lt = http(args.port, "/api/language/train", {})
        if args.live:
            rep = lt.get("report") or {}
            good = "calls" in rep or rep.get("words_added") is not None
            ok &= bool(good)
            print(f"  [{'ok ' if good else 'BAD'}] LIVE language encoding: "
                  f"{rep.get('calls')} call(s), {rep.get('words_added')} words "
                  f"as KC patterns "
                  f"(stopped: {rep.get('stopped_reason')})")
            _, lst = http(args.port, "/api/language/state")
            print(f"        can_speak={lst.get('can_speak')} "
                  f"vocabulary={lst.get('vocabulary_size')} "
                  f"(neural basis: {lst.get('neural_basis')})")
        else:
            good = lt.get("success") is False and str(lt.get("reason")) in (
                "no_api_key", "offline_mode")
            ok &= good
            print(f"  [{'ok ' if good else 'BAD'}] training without a key "
                  f"refuses ({lt.get('reason')})")

        _, stt = http(args.port, "/api/state")
        m = stt.get("mental") or {}
        print(f"        mind: activity={m.get('activity')} "
              f"heartbeat={m.get('heartbeat', {}).get('state')} "
              f"teacher={m.get('autotraining', {}).get('teacher')} "
              f"language level={m.get('language', {}).get('level')}")
        print("verdict:", "HOUSE OK" if ok else "HOUSE PROBLEMS")
        return 0 if ok else 1
    finally:
        child.terminate()
        try:
            child.wait(timeout=15)
        except Exception:
            child.kill()

if __name__ == "__main__":
    raise SystemExit(main())