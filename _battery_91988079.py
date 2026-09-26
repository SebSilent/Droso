def match(self, task: str) -> list:
    """Every pattern hit at or above the confidence floor, best first, as
        (confidence, code, key) triples. Split out of `_from_pattern` because
        composition needs the runners-up, not just the winner."""
    if self.patterns is None:
        return []
    key = _short_key(task)
    found = []
    try:
        direct = self.patterns.query(key)
        if direct:
            found.append(direct)
        for sub in sorted(_words(task), key=len, reverse=True)[:6]:
            for hit in self.patterns.search(sub, limit=3):
                if hit not in found:
                    found.append(hit)
    except Exception:
        return []
    out = []
    for h in found:
        val = h.get('value') if isinstance(h, dict) else h
        if not val:
            continue
        conf = float((h or {}).get('confidence', 0.0) or 0.0) if isinstance(h, dict) else 0.0
        code = val if isinstance(val, str) and _looks_like_code(val) else _embedded_code(val)
        if code and conf >= self.min_confidence:
            out.append((conf, code, str(h.get('key') if isinstance(h, dict) else '')))
    out.sort(key=lambda t: -t[0])
    return out

assert match is not None
