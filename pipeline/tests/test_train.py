"""Training data plumbing (no model): pairs from examples and no-duplicate batches."""

from __future__ import annotations

import random

from bundle_pipeline.train import Pair, build_pairs, make_batches


def test_build_pairs_skips_none_and_uses_the_answer_candidate(examples) -> None:
    pairs = build_pairs(examples, seed=3)
    answered = [ex for ex in examples if ex.answer != "none"]
    assert len(pairs) == len(answered)
    by_anchor = {p.anchor: p for p in pairs}
    for ex in answered:
        p = by_anchor[ex.chat]
        cand = next(c for c in ex.candidates if c.id == ex.answer)
        if cand.kind == "bundle":
            assert p.positive in cand.examples
        else:
            assert p.positive == cand.text
        assert p.key == f"{ex.person_id}|{ex.answer}"


def test_build_pairs_is_deterministic(examples) -> None:
    assert build_pairs(examples, seed=3) == build_pairs(examples, seed=3)


def test_make_batches_never_repeats_a_key_in_a_batch() -> None:
    pairs = [Pair(f"a{i}", f"p{i}", key=f"k{i % 3}") for i in range(30)]
    batches = make_batches(pairs, batch_size=8, rng=random.Random(0))
    assert sum(len(b) for b in batches) == 30
    for b in batches:
        keys = [p.key for p in b]
        assert len(keys) == len(set(keys))
        assert 2 <= len(b) <= 8


def test_make_batches_drops_singletons() -> None:
    pairs = [Pair("a", "p", "k"), Pair("b", "q", "k"), Pair("c", "r", "k")]
    assert make_batches(pairs, batch_size=32, rng=random.Random(0)) == []
