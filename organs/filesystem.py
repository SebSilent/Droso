"""Filesystem organ: read/write text files, sandboxed to a root."""

from __future__ import annotations

from pathlib import Path

class FilesystemOrgan:
    """Read, write and list text files under one sandbox root.

    Safety: every path is resolved against the root and refused if it escapes
    (../, absolute paths outside, drive changes). Reads are line-capped.
    """

    def __init__(self, root: str, max_read_chars: int = 20000):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.journal: list[dict] = []
        self.max_read_chars = int(max_read_chars)

    def _resolve(self, rel_path: str) -> Path:
        p = (self.root / rel_path).resolve()
        if p != self.root and self.root not in p.parents:
            raise PermissionError(f"path escapes sandbox root: {rel_path}")
        return p

    def read(self, rel_path: str) -> dict:
        try:
            p = self._resolve(rel_path)
        except PermissionError as exc:
            return {"ok": False, "error": str(exc)}
        if not p.exists():
            return {"ok": False, "error": f"no such file: {rel_path}"}
        text = p.read_text(encoding="utf-8", errors="replace")
        return {"ok": True, "path": rel_path, "content": text[: self.max_read_chars],
                "truncated": len(text) > self.max_read_chars,
                "n_chars": len(text)}

    def write(self, rel_path: str, content: str) -> dict:
        try:
            p = self._resolve(rel_path)
        except PermissionError as exc:
            return {"ok": False, "error": str(exc)}
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        import time as _t
        self.journal.append({"path": rel_path, "n_chars": len(content),
                             "ts": _t.time(),
                             "content": content[:4000],
                             "truncated": len(content) > 4000})
        if len(self.journal) > 200:
            del self.journal[:len(self.journal) - 200]
        return {"ok": True, "path": rel_path, "n_chars": len(content)}

    def list_dir(self, rel_path: str = ".") -> dict:
        try:
            p = self._resolve(rel_path)
        except PermissionError as exc:
            return {"ok": False, "error": str(exc)}
        if not p.is_dir():
            return {"ok": False, "error": f"not a directory: {rel_path}"}
        return {"ok": True, "entries": sorted(e.name for e in p.iterdir())}