
from __future__ import annotations

import re

class LLMTool:
    def __init__(self, exocortex, sparse_fn=None, max_chars: int = 900):
        self.exo = exocortex
        self.sparse_fn = sparse_fn
        self.max_chars = max_chars
        self.queries = 0

    def query(self, prompt: str, use_inference: bool = False) -> dict:
        self.queries += 1
        p = str(prompt)
        concepts: list[str] = []
        try:
            for c in self.exo.search_concepts(p, k=5):
                nm = (c.get("concept") or c.get("name") or c.get("token")
                      or "")
                if nm:
                    concepts.append(nm)
        except Exception:
            pass
        related: list[str] = []
        for seed in concepts[:2]:
            try:
                for hop in self.exo.traverse_relations(seed, max_hops=1)[:3]:
                    tgt = hop.get("to") or hop.get("target") or ""
                    if tgt:
                        related.append(f"{seed} -> {tgt}")
            except Exception:
                pass
        blocks = []
        if concepts:
            blocks.append("known concepts: " + ", ".join(concepts[:6]))
        if related:
            blocks.append("relations: " + "; ".join(related[:4]))
        try:
            for m in re.finditer(r"\b(\w{4,})\b", p.lower()):
                pass
            kws = [w for w in re.findall(r"[a-z_]{4,}", p.lower())][:6]
            for kw in kws:
                hits = self.exo.search_concepts(kw, k=1)
                for h in hits:
                    body = (h.get("snippet") or h.get("code")
                            or h.get("template") or "")
                    if body and len(blocks) < 4:
                        blocks.append(f"pattern[{h.get('concept') or h.get('token') or kw}]:\n"
                                      + str(body)[:300])
        except Exception:
            pass
        source = "atlas+vault"
        if use_inference and self.sparse_fn is not None:
            try:
                gen = str(self.sparse_fn(p[:300]))[:self.max_chars // 2]
                if gen.strip():
                    blocks.append("qwen sparse continuation:\n" + gen)
                    source = "atlas+vault+sparse_inference"
            except Exception:
                pass
        text = "\n".join(blocks)
        if not text.strip():
            text = ("no compiled knowledge matched; fall back to first-"
                    "principles decomposition")
            source = "template"
        return {"text": text[:self.max_chars], "source": source,
                "concepts": concepts[:6]}