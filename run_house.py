#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

def main(argv=None) -> int:
    sys.setswitchinterval(0.0005)
    ap = argparse.ArgumentParser(description="Run the Connectome House")
    ap.add_argument("--host", default=None, help="override house.host")
    ap.add_argument("--port", type=int, default=None, help="override house.port")
    ap.add_argument("--no-heartbeat", action="store_true",
                    help="attach the heartbeat but do not start its timer")
    ap.add_argument("--no-language-training", action="store_true",
                    help="skip the first-run English lessons (each is one call)")
    ap.add_argument("--project-root", default=None,
                    help="what the fence guards (default: this repo)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    from config_loader import load_config
    from world.connectome_house import (CAPABILITIES, ConnectomeHouse,
                                        build_house_agent)

    cfg = load_config()
    h = cfg.get("house", {}) or {}
    if not h.get("enabled", True):
        print("house.enabled is false in config/hybrid_config.json; nothing to do.")
        return 2

    agent = build_house_agent(cfg, project_root=args.project_root)
    house = ConnectomeHouse(agent, cfg, host=args.host, port=args.port)
    hb = getattr(agent, "heartbeat", None)
    bar = "=" * 58
    if not args.json:
        print(bar)
        print("  THE CONNECTOME HOUSE")
        print(f"  {house.url()}")
        print(bar)

    started = time.time()
    info = house.start()
    if not info.get("success"):
        print(f"could not bind {house.host}:{house.port} -> {info.get('reason')}")
        return 1
    if info.get("took_over"):
        # The operator asked for one rule: restarting means one house, not two.
        # Say out loud what happened to the previous one.
        print(f"  single instance: {info['took_over']}")
    elif info.get("force_bound"):
        print(f"  WARNING: bound over a listener that could not be stopped -> "
              f"{info.get('note')}")
    mental = agent.start(heartbeat=not args.no_heartbeat,
                         train_language=not args.no_language_training)

    oracle = getattr(agent, "api_oracle", None)
    mode = oracle.stats().get("mode") if oracle else "absent"
    sb = getattr(agent, "sandbox", None)
    at = getattr(agent, "autotraining", None)
    lg = getattr(agent, "language", None)
    st = (at.get_state() if at else {}) or {}
    rec = {
        "url": house.url(),
        "access": house.access_mode(),
        "project_root": str(house.project_root),
        "workzone": str(sb.workzone) if sb else None,
        "network": sb.allow_network if sb else None,
        "oracle_mode": mode,
        "heartbeat": ("ticking" if (hb and getattr(hb, "_running", False))
                      else "attached, idle"),
        "autotraining": {"running": bool(st.get("running")),
                         "cycles": int(st.get("cycle_count") or 0),
                         "teacher": st.get("teacher"),
                         "start": mental.get("autotraining")},
        "language": {"vocabulary_size": (lg.vocabulary_size() if lg else None),
                     "can_speak": (lg.can_speak() if lg else None),
                     "neural_basis": "BANC_v888_KC_neurons",
                     "start": mental.get("language")},
        "organs": len(house.get_organs_state()),
        "capabilities": len(CAPABILITIES),
        "seconds_to_start": round(time.time() - started, 2),
    }
    if args.json:
        print(json.dumps(rec, indent=2))
    else:
        print(f"\n  house       {rec['url']}")
        print(f"  access      {rec['access']}")
        print(f"  guarding    {rec['project_root']}")
        print(f"  workzone    {rec['workzone']}  (free scratch space)")
        print(f"  oracle      {rec['oracle_mode']}"
              + ("   <- no credential: it raises instead of answering"
                 if mode == "blocked" else "")
              + ("   <- fenced process (HYBRIDLLM_OFFLINE): no calls are made"
                 if mode == "offline" else ""))
        print(f"  heartbeat   {rec['heartbeat']}  (thinking, no LLM)")
        print(f"  autotraining {'running' if st.get('running') else 'stopped'}"
              f"  teacher={st.get('teacher')} "
              f"cycle={st.get('cycle_count')} ({st.get('note')})")
        print(f"  language    {rec['language']['vocabulary_size']} word(s) as "
              f"KC neural patterns (can speak: "
              f"{rec['language']['can_speak']}); "
              f"{(mental.get('language') or {}).get('reason', '')}")
        print(f"  organs      {rec['organs']}")
        print(f"\n  Open {rec['url'].replace('0.0.0.0', 'localhost')} in a browser.")
        print("  The LLM has no tools. Every action below is the connectome's.\n")

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nshutting down...")
    finally:
        agent.stop()
        house.stop()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())