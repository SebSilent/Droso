"""Why does the knowledge channel lose ~half its calls? A measurement, not a guess.

`state/knowledge_ledger.jsonl` says: 33 calls, 6 accepted (~18%), 16 `empty_completion`
(~48%) -- after the channel's own 2-retry backoff already ran. `empty_completion` is set in
`api_oracle._live` when the provider returns a choice with NO content, NO `reasoning_content`
and `finish_reason != "content_filter"`. It is a *successful HTTP call with a blank answer*,
and the three candidates are separable:

  quota pressure     -> calls fail in time-clusters, or with transport/http reasons
  token budget       -> finish_reason "length", or reasoning_tokens eating max_tokens
  silent truncation  -> a field the parser discards (content in a place we do not read)

This reissues the SAME questions at two token budgets and prints, per call, the finish
reason, the reasoning-token count, the completion-token count and the raw choice keys. Run it
once and the reason is a number rather than a hypothesis.

    python tools/oracle_diagnose.py --limit 6 --budgets 320 800

It costs real provider calls: `--limit 6 --budgets 320 800` is 12.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _oracle():
    """Built from THIS project's config, the way the house builds it.

    `oracle_from_config()` with no argument runs `cfg = cfg or {}` and builds from library
    defaults -- openai/gpt-4o-mini -- which reports a real key and the wrong provider.
    """
    from organs.api_oracle import oracle_from_config
    cfg = json.loads((ROOT / "config" / "hybrid_config.json").read_text(encoding="utf-8"))
    return oracle_from_config(cfg)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--budgets", type=int, nargs="+", default=[320, 800])
    ap.add_argument("--split", default="holdout")
    a = ap.parse_args()

    from tools.make_curriculum import load
    from organs.knowledge import KnowledgeChannel

    oracle = _oracle()
    if not getattr(oracle, "has_key", False):
        print("no oracle key available; nothing to diagnose")
        return 1
    print(f"provider={oracle.provider} model={oracle.model} thinking={oracle.thinking} "
          f"reasoning_model={oracle._spec.get('reasoning_model')}")

    # Capture the RAW provider payload, because the parsed result is what discards the
    # field we are looking for.
    raw: dict = {}
    orig_post = oracle._post

    def spy(url, headers, payload):
        resp = orig_post(url, headers, payload)
        raw.clear()
        raw["sent"] = {k: v for k, v in payload.items() if k != "messages"}
        raw["resp"] = resp
        return resp

    oracle._post = spy

    ch = KnowledgeChannel(oracle=oracle, loop=None)
    rows = load(a.split)
    rows = [r for r in rows if KnowledgeChannel.target_of(r["check"])][:a.limit]
    print(f"tasks: {len(rows)}  budgets: {a.budgets}\n")

    t_start = time.time()
    tally: dict = {}
    for r in rows:
        # The per-TASK ceiling accumulates across calls; the channel resets it at the top
        # of every ask(). Without this the tool measures its own budget leak, not the
        # provider.
        try:
            oracle.budget.start_task()
        except Exception:
            pass
        target = KnowledgeChannel.target_of(r["check"])
        q = ch._question(r["task"], r["check"], target, None)
        for b in a.budgets:
            t0 = time.time()
            try:
                res = oracle.query(q, max_tokens=int(b), temperature=0.0,
                                   purpose="knowledge")
            except Exception as exc:
                res = {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
            wall = time.time()
            resp = raw.get("resp") or {}
            choice = (resp.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            usage = resp.get("usage") or {}
            row = {
                "target": target,
                "budget": int(b),
                "ok": bool(res.get("ok")),
                "text_len": len(str(res.get("text") or "")),
                "finish": choice.get("finish_reason"),
                "reasoning": int(res.get("reasoning_tokens") or 0),
                "completion": int(res.get("completion_tokens_est") or 0),
                "prompt": int(res.get("prompt_tokens_est") or 0),
                "latency": round(wall - t0, 2),
                "session_elapsed": round(wall - t_start, 1),
                "reason": str(res.get("reason") or "")[:60],
                "msg_keys": sorted(msg.keys()),
                "usage_keys": sorted(usage.keys()),
                "sent": sorted((raw.get("sent") or {}).keys()),
            }
            print(json.dumps(row))
            key = (int(b), "ok" if row["ok"] else row["finish"] or row["reason"])
            tally[key] = tally.get(key, 0) + 1

    print("\n=== tally by (budget, outcome) ===")
    for k in sorted(tally, key=str):
        print(f"  {k}: {tally[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
