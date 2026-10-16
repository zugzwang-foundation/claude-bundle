"""Export helpers that need no model: pooling maths, fixture texts, manifest keys."""

from __future__ import annotations

import numpy as np

from bundle_pipeline.export import MANIFEST_KEYS, fixture_texts, mean_pool_normalise


def test_mean_pool_normalise_ignores_padding() -> None:
    hidden = np.array([[[1.0, 0.0], [3.0, 0.0], [100.0, 100.0]]], dtype=np.float32)
    mask = np.array([[1, 1, 0]])
    out = mean_pool_normalise(hidden, mask)
    assert out.shape == (1, 2)
    assert out[0].tolist() == [1.0, 0.0]  # mean of (1,0) and (3,0), normalised


def test_fixture_texts_are_32_distinct(fixture_path) -> None:
    texts = fixture_texts(32, fixture_path)
    assert len(texts) == 32 and len(set(texts)) == 32


def test_manifest_keys_match_contract() -> None:
    assert MANIFEST_KEYS == ("id", "name", "dtype", "size_bytes", "base_model", "run_id")
