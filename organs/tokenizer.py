
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from connectome.engine import text_code

_TOKEN_RE = re.compile(r"[a-z0-9]+")

class TokenizerOrgan:
    def __init__(self, model_dir: str | Path | None = None,
                 n_kc: int = 3840, k: int = 16, seed: int = 0):
        self.model_dir = Path(model_dir) if model_dir else None
        self.n_kc = int(n_kc)
        self.k = int(k)
        self.seed = int(seed)
        self._id_to_token: list[str] | None = None

    def tokenize(self, text: str) -> list[str]:
        return _TOKEN_RE.findall(str(text).lower())

    def encode(self, text: str) -> np.ndarray:
        """Sparse k-of-n Kenyon-cell code for one text (the sensory code)."""
        return text_code(text, self.n_kc, self.k, self.seed)

    def encode_pair(self, a: str, b: str) -> np.ndarray:
        """Code for a result 'returning into' the connectome: the task text
        and the received result are hashed together, so the next perception
        carries both what was asked and what came back."""
        return self.encode(f"{a} -> {b}")

    def attach_model_dir(self, model_dir: str | Path | None) -> None:
        self.model_dir = Path(model_dir) if model_dir else None
        self._id_to_token = None

    def _load_vocab(self) -> list[str]:
        if self._id_to_token is not None:
            return self._id_to_token
        self._id_to_token = []
        if self.model_dir is None:
            return self._id_to_token
        tj = self.model_dir / "tokenizer.json"
        try:
            if tj.exists():
                vocab = json.loads(tj.read_text(encoding="utf-8"))["model"]["vocab"]
            else:
                vj = self.model_dir / "vocab.json"
                vocab = json.loads(vj.read_text(encoding="utf-8")) if vj.exists() else {}
            size = max(vocab.values()) + 1 if vocab else 0
            self._id_to_token = [""] * size
            for tok, idx in vocab.items():
                if 0 <= idx < size:
                    self._id_to_token[idx] = tok
        except (OSError, KeyError, ValueError) as exc:
            print(f"[tokenizer] vocab load failed: {exc}")
            self._id_to_token = []
        return self._id_to_token

    def decode(self, ids) -> list[str]:
        vocab = self._load_vocab()
        out = []
        for i in ids:
            i = int(i)
            out.append(vocab[i] if 0 <= i < len(vocab) else f"<id{i}>")
        return out