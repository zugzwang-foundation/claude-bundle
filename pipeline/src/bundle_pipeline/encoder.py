"""Sentence encoder wrapper: SentenceTransformer behind a tiny cached ``encode``.

The same class serves the base encoder (B1) and the student (B2). Vectors are
mean-pooled and L2-normalised by sentence-transformers itself
(``normalize_embeddings=True``); a per-run dict caches text -> vector so the
thousands of repeated bundle example texts in a tasks file are embedded once.
Import this module only in stages that really need torch; ``--help`` must not.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from pathlib import Path

import numpy as np

from bundle_pipeline import config


def resolve_device(choice: str = "auto") -> str:
    """'auto' -> 'mps' when PyTorch sees Apple's GPU, else 'cpu'."""
    if choice != "auto":
        return choice
    import torch  # noqa: PLC0415

    return "mps" if torch.backends.mps.is_available() else "cpu"


def dir_size_bytes(path: str | Path) -> int:
    """Bytes of the files under a path, following symlinks and counting each inode once.

    The Hub cache (with hf-xet) keeps snapshots as symlinks onto blobs stored
    elsewhere, so sizes must follow links; a plain checkout has no links at all.
    """
    p = Path(path)
    if not p.exists():
        return 0
    if p.is_file():
        return p.stat().st_size
    seen: set[tuple[int, int]] = set()
    total = 0
    for f in p.rglob("*"):
        try:
            st = f.stat()  # follows symlinks
        except OSError:
            continue
        if not f.is_file():
            continue
        key = (st.st_dev, st.st_ino)
        if key in seen:
            continue
        seen.add(key)
        total += st.st_size
    return total


def model_size_mb(model_or_path: str) -> float:
    """Size on disk in MB (10^6 bytes): a local directory, else the Hub cache snapshot."""
    p = Path(model_or_path)
    if p.exists():
        return dir_size_bytes(p) / 1e6
    cache = config.hf_cache_dir() / ("models--" + model_or_path.replace("/", "--"))
    snapshots = cache / "snapshots"
    if snapshots.is_dir():
        return dir_size_bytes(snapshots) / 1e6
    return dir_size_bytes(cache) / 1e6 if cache.exists() else 0.0


class Encoder:
    """Loads a SentenceTransformer and embeds texts with a per-instance cache."""

    def __init__(
        self,
        model_or_path: str = config.BASE_ENCODER,
        device: str = "auto",
        batch_size: int = 64,
        max_seq_length: int | None = 128,
    ) -> None:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        self.name = model_or_path
        self.device = resolve_device(device)
        self.batch_size = batch_size
        t0 = time.perf_counter()
        self.model = SentenceTransformer(model_or_path, device=self.device)
        if max_seq_length is not None:
            self.model.max_seq_length = max_seq_length
        self.load_seconds = time.perf_counter() - t0
        self._cache: dict[str, np.ndarray] = {}
        get_dim = getattr(self.model, "get_embedding_dimension", None) or (
            self.model.get_sentence_embedding_dimension
        )
        self.dim = int(get_dim() or config.EMBEDDING_DIM)

    # -- embedding ------------------------------------------------------------

    def _encode_raw(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        vecs = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(vecs, dtype=np.float32)

    def warm(self, texts: Iterable[str]) -> int:
        """Embed every text not yet cached, in large batches. Returns how many were new."""
        missing = list(dict.fromkeys(t for t in texts if t not in self._cache))
        if missing:
            for text, vec in zip(missing, self._encode_raw(missing), strict=True):
                self._cache[text] = vec
        return len(missing)

    def encode(self, texts: list[str]) -> np.ndarray:
        """(n, dim) normalised float32 vectors, from the cache where possible."""
        self.warm(texts)
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.stack([self._cache[t] for t in texts])

    def encode_uncached(self, texts: list[str]) -> np.ndarray:
        """Always run the model (used to time a single decision honestly)."""
        return self._encode_raw(texts)

    # -- facts ---------------------------------------------------------------

    @property
    def cache_size(self) -> int:
        return len(self._cache)

    def size_mb(self) -> float:
        return model_size_mb(self.name)


__all__ = ["Encoder", "dir_size_bytes", "model_size_mb", "resolve_device"]
