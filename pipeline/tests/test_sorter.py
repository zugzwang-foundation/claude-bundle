"""The sorter maths: softmax, rules at the cut-offs, "none" when nothing fits."""

from __future__ import annotations

import numpy as np
import pytest

from bundle_pipeline.config import SorterParams
from bundle_pipeline.schema import Candidate, DecisionExample
from bundle_pipeline.sorter import (
    NONE_ID,
    LeaveSorter,
    Sorter,
    argmax_including_none,
    bundle_vector,
    candidate_vectors,
    decide,
    decide_from_scores,
    mean_nll,
    normalise,
    probabilities,
    softmax,
    unique_texts,
)

P = SorterParams(temperature=0.05, none_score=0.30, file_cutoff=0.85, suggest_cutoff=0.55)


def test_softmax_sums_to_one_and_orders_by_score() -> None:
    probs = softmax(np.array([0.9, 0.2, 0.3]), temperature=0.05)
    assert probs.sum() == pytest.approx(1.0)
    assert probs.argmax() == 0
    assert softmax(np.array([1000.0, -1000.0]), 0.05).sum() == pytest.approx(1.0)  # no overflow


def test_softmax_rejects_non_positive_temperature() -> None:
    with pytest.raises(ValueError):
        softmax(np.array([0.1]), 0.0)


def test_probabilities_include_none_and_sum_to_one() -> None:
    probs = probabilities(["b:t1", "c:c2"], np.array([0.8, 0.4]), P)
    assert set(probs) == {"b:t1", "c:c2", NONE_ID}
    assert sum(probs.values()) == pytest.approx(1.0)
    assert probs["b:t1"] > probs["c:c2"] > probs[NONE_ID]


def test_no_candidates_means_none_with_probability_one() -> None:
    d = decide_from_scores([], np.zeros(0), P)
    assert d.probabilities == {NONE_ID: 1.0}
    assert d.action == "leave" and d.target is None


def test_rules_exactly_at_the_cutoffs() -> None:
    at_file = {"b:a": 0.85, "b:b": 0.10, NONE_ID: 0.05}
    assert decide(at_file, P).action == "file"
    just_under_file = {"b:a": 0.8499, "b:b": 0.10, NONE_ID: 0.0501}
    assert decide(just_under_file, P).action == "suggest"
    at_suggest = {"b:a": 0.55, "b:b": 0.40, NONE_ID: 0.05}
    d = decide(at_suggest, P)
    assert d.action == "suggest" and d.target == "b:a"
    under_suggest = {"b:a": 0.5499, "b:b": 0.40, NONE_ID: 0.0501}
    d = decide(under_suggest, P)
    assert d.action == "leave" and d.target is None


def test_top_ignores_none_even_when_none_is_largest() -> None:
    probs = {"b:a": 0.30, NONE_ID: 0.70}
    d = decide(probs, P)
    assert d.action == "leave" and d.target is None
    assert argmax_including_none(probs) == NONE_ID
    low = SorterParams(0.05, 0.30, file_cutoff=0.30, suggest_cutoff=0.20)
    assert decide(probs, low).action == "file"  # the rules look only at the top candidate


def test_none_wins_when_all_cosines_are_low() -> None:
    scores = np.array([0.05, -0.02, 0.10])  # unrelated texts: cosines near zero
    probs = probabilities(["b:a", "b:b", "c:c"], scores, P)
    assert argmax_including_none(probs) == NONE_ID
    assert probs[NONE_ID] > 0.9  # (0.30 - 0.10) / 0.05 = 4 nats clear of the runner-up
    assert decide(probs, P).action == "leave"


def test_bundle_vector_is_normalised_mean() -> None:
    vecs = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    v = bundle_vector(vecs)
    assert np.linalg.norm(v) == pytest.approx(1.0)
    assert v[0] == pytest.approx(v[1])
    with pytest.raises(ValueError):
        bundle_vector(np.zeros((0, 2)))


def test_normalise_leaves_zero_rows_alone() -> None:
    out = normalise(np.array([[0.0, 0.0], [3.0, 4.0]]))
    assert out[0].tolist() == [0.0, 0.0]
    assert out[1].tolist() == pytest.approx([0.6, 0.8])


def test_candidate_vectors_with_fake_encoder(fake_encoder) -> None:
    cands = [
        Candidate(id="b:t1", kind="bundle", label="Runs", examples=["long run plan", "tempo run"]),
        Candidate(id="c:c9", kind="loose", text="my sourdough starter smells odd"),
    ]
    ids, matrix = candidate_vectors(cands, fake_encoder.encode)
    assert ids == ["b:t1", "c:c9"]
    assert matrix.shape == (2, fake_encoder.dim)
    assert np.allclose(np.linalg.norm(matrix, axis=1), 1.0, atol=1e-5)


def test_sorter_files_a_chat_that_repeats_its_bundle(fake_encoder) -> None:
    cands = [
        Candidate(
            id="b:t1", kind="bundle", label="Runs", examples=["long run plan", "tempo run pace"]
        ),
        Candidate(id="c:c9", kind="loose", text="sourdough starter smells odd"),
    ]
    ex = DecisionExample(
        id="x",
        person_id="p",
        chat_id="x",
        chat="long run plan pace",
        candidates=cands,
        answer="b:t1",
        difficulty="plain",
        day=3,
    )
    d = Sorter(fake_encoder.encode, P).decide(ex)
    assert d.target == "b:t1"
    assert d.action in ("file", "suggest")
    unrelated = ex.model_copy(update={"chat": "quantum chess openings", "answer": "none"})
    d2 = Sorter(fake_encoder.encode, P).decide(unrelated)
    assert argmax_including_none(d2.probabilities) == NONE_ID


def test_leave_sorter_puts_everything_on_none() -> None:
    ex = DecisionExample(
        id="x",
        person_id="p",
        chat_id="x",
        chat="hi",
        candidates=[Candidate(id="c:c1", kind="loose", text="hello")],
        answer="c:c1",
        difficulty="very_short",
        day=1,
    )
    d = LeaveSorter().decide(ex)
    assert d.action == "leave" and d.target is None
    assert d.probabilities == {"c:c1": 0.0, NONE_ID: 1.0}


def test_mean_nll_is_lower_for_sharper_right_answers() -> None:
    from bundle_pipeline.sorter import Scored

    scored = [Scored(ids=["b:a", "b:b"], scores=np.array([0.9, 0.2]), answer="b:a")]
    assert mean_nll(scored, P) < mean_nll(scored, SorterParams(1.0, 0.30, 0.85, 0.55))


def test_unique_texts_covers_examples_loose_and_chats(examples) -> None:
    texts = unique_texts(examples)
    assert len(texts) == len(set(texts))
    assert all(ex.chat in texts for ex in examples)


def test_fixture_examples_follow_the_contract(examples) -> None:
    # 25 chats -> 25 examples; every answer is a candidate id or "none"
    assert len(examples) == 25
    for ex in examples:
        ids = {c.id for c in ex.candidates}
        assert ex.answer == NONE_ID or ex.answer in ids
        assert all(c.id.startswith(("b:", "c:")) for c in ex.candidates)
    assert any(ex.answer.startswith("b:") for ex in examples)
    assert any(ex.answer.startswith("c:") for ex in examples)
    assert any(ex.answer == NONE_ID for ex in examples)
