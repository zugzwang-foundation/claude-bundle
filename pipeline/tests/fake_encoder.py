"""A deterministic stand-in for the sentence encoder: no network, no torch, no download.

Each word is hashed (sha256) into a fixed pseudo-random 32-dimensional vector;
a text's vector is the normalised sum of its words' vectors. Texts that share
words are close, texts with no words in common are near-orthogonal, which is
all the sorter maths needs for its tests. The interface mirrors
``bundle_pipeline.encoder.Encoder``: ``encode``, ``warm``, ``encode_uncached``,
``name``, ``device``, ``dim``, ``size_mb``.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

import numpy as np

_WORD = re.compile(r"[a-z0-9']+")


def word_vector(word: str, dim: int) -> np.ndarray:
    seed = int.from_bytes(hashlib.sha256(word.encode("utf-8")).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    return rng.standard_normal(dim).astype(np.float32)


class FakeEncoder:
    name = "fake-hash-encoder"
    device = "cpu"

    def __init__(self, dim: int = 32) -> None:
        self.dim = dim
        self._words: dict[str, np.ndarray] = {}
        self.calls = 0
        self._cache: dict[str, np.ndarray] = {}

    def _text_vector(self, text: str) -> np.ndarray:
        total = np.zeros(self.dim, dtype=np.float32)
        for w in _WORD.findall(text.lower()):
            if w not in self._words:
                self._words[w] = word_vector(w, self.dim)
            total += self._words[w]
        norm = float(np.linalg.norm(total))
        return total / norm if norm > 1e-12 else total

    def encode_uncached(self, texts: list[str]) -> np.ndarray:
        self.calls += 1
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.stack([self._text_vector(t) for t in texts])

    def warm(self, texts: Iterable[str]) -> int:
        missing = [t for t in dict.fromkeys(texts) if t not in self._cache]
        if missing:
            for t, v in zip(missing, self.encode_uncached(missing), strict=True):
                self._cache[t] = v
        return len(missing)

    def encode(self, texts: list[str]) -> np.ndarray:
        self.warm(texts)
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.stack([self._cache[t] for t in texts])

    def size_mb(self) -> float:
        return 0.0
