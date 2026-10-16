"""The sorter's maths, in pure numpy (no torch, no network).

This is the decision model's whole arithmetic, shared by the B1 baseline, the
student (B2) and the tests. The web app re-implements exactly these steps in
TypeScript, so keep it small and literal:

* every text is embedded by a sentence encoder with mean pooling, L2-normalised;
* a bundle's vector is the normalised mean of its example vectors;
* a loose chat's vector is its own text's vector;
* score(candidate) = cosine(chat, candidate);
* "none" gets the constant ``none_score``;
* probabilities = softmax(scores / temperature) over candidates + "none";
* top = argmax over the candidates (never "none");
  action = "file" if p_top >= file_cutoff, "suggest" if p_top >= suggest_cutoff, else "leave";
  target = top id unless the action is "leave".

Defaults before calibration live in ``config.SorterParams``: temperature 0.05,
none_score 0.30, file_cutoff 0.85, suggest_cutoff 0.55.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from bundle_pipeline.config import DEFAULT_SORTER, SorterParams
from bundle_pipeline.schema import Candidate, Decision, DecisionExample

NONE_ID = "none"

EmbedFn = Callable[[list[str]], np.ndarray]
"""Maps a list of texts to an (n, dim) float32 array of L2-normalised vectors."""


# --- Vectors -----------------------------------------------------------------


def normalise(vectors: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """L2-normalise each row; an all-zero row stays zero instead of becoming NaN."""
    arr = np.asarray(vectors, dtype=np.float32)
    if arr.ndim == 1:
        norm = float(np.linalg.norm(arr))
        return arr / norm if norm > eps else arr
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    return np.where(norms > eps, arr / np.maximum(norms, eps), arr)


def bundle_vector(example_vectors: np.ndarray) -> np.ndarray:
    """Normalised mean of the example vectors (shape (k, dim) -> (dim,))."""
    arr = np.asarray(example_vectors, dtype=np.float32)
    if arr.size == 0:
        raise ValueError("a bundle needs at least one example vector")
    return normalise(arr.mean(axis=0))


def candidate_vectors(
    candidates: Sequence[Candidate], embed: EmbedFn, dim: int | None = None
) -> tuple[list[str], np.ndarray]:
    """Return the candidate ids and a (n, dim) matrix of their vectors, in order."""
    ids: list[str] = []
    rows: list[np.ndarray] = []
    for cand in candidates:
        ids.append(cand.id)
        if cand.kind == "bundle":
            texts = list(cand.examples)
            if not texts and cand.label:
                texts = [cand.label]  # degenerate bundle: fall back to its label
            rows.append(bundle_vector(embed(texts)) if texts else None)  # type: ignore[arg-type]
        else:
            rows.append(embed([cand.text or ""])[0])
    if not rows:
        return ids, np.zeros((0, dim or 0), dtype=np.float32)
    width = next((r.shape[0] for r in rows if r is not None), dim or 0)
    matrix = np.stack([r if r is not None else np.zeros(width, np.float32) for r in rows])
    return ids, matrix.astype(np.float32)


def cosine_scores(chat_vector: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Cosine of the chat against each row; inputs are already normalised."""
    if matrix.shape[0] == 0:
        return np.zeros(0, dtype=np.float32)
    return (matrix @ np.asarray(chat_vector, dtype=np.float32)).astype(np.float32)


# --- Probabilities and rules -------------------------------------------------


def softmax(scores: np.ndarray, temperature: float) -> np.ndarray:
    """Numerically stable softmax of scores / temperature."""
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    z = np.asarray(scores, dtype=np.float64) / temperature
    z = z - z.max()
    e = np.exp(z)
    return (e / e.sum()).astype(np.float64)


def probabilities(
    ids: Sequence[str], scores: np.ndarray, params: SorterParams = DEFAULT_SORTER
) -> dict[str, float]:
    """Softmax over the candidates plus "none" (at ``none_score``), keyed by id."""
    all_scores = np.append(np.asarray(scores, dtype=np.float64), params.none_score)
    probs = softmax(all_scores, params.temperature)
    out = {cid: float(p) for cid, p in zip(ids, probs[:-1], strict=True)}
    out[NONE_ID] = float(probs[-1])
    return out


def top_candidate(probs: dict[str, float]) -> tuple[str | None, float]:
    """The best candidate that is not "none" and its probability (None, 0.0 if no candidates)."""
    best_id, best_p = None, 0.0
    for cid, p in probs.items():
        if cid != NONE_ID and (best_id is None or p > best_p):
            best_id, best_p = cid, p
    return best_id, best_p


def argmax_including_none(probs: dict[str, float]) -> str:
    """The most probable key, "none" included (ties go to the first key seen)."""
    return max(probs.items(), key=lambda kv: kv[1])[0]


def decide(probs: dict[str, float], params: SorterParams = DEFAULT_SORTER) -> Decision:
    """Apply the file / suggest / leave rules to a probability table."""
    top_id, p_top = top_candidate(probs)
    if top_id is None:
        return Decision(probabilities=probs, action="leave", target=None)
    if p_top >= params.file_cutoff:
        return Decision(probabilities=probs, action="file", target=top_id)
    if p_top >= params.suggest_cutoff:
        return Decision(probabilities=probs, action="suggest", target=top_id)
    return Decision(probabilities=probs, action="leave", target=None)


def decide_from_scores(
    ids: Sequence[str], scores: np.ndarray, params: SorterParams = DEFAULT_SORTER
) -> Decision:
    return decide(probabilities(ids, scores, params), params)


# --- A whole decision, from texts --------------------------------------------


@dataclass
class Scored:
    """A decision example reduced to candidate ids and cosine scores (params-free)."""

    ids: list[str]
    scores: np.ndarray
    answer: str

    def probabilities(self, params: SorterParams) -> dict[str, float]:
        return probabilities(self.ids, self.scores, params)

    def answer_probability(self, params: SorterParams) -> float:
        probs = self.probabilities(params)
        return probs.get(self.answer, 0.0)


class Sorter:
    """Embeds with ``embed`` and decides with the maths above."""

    def __init__(self, embed: EmbedFn, params: SorterParams = DEFAULT_SORTER) -> None:
        self.embed = embed
        self.params = params

    def score(self, example: DecisionExample) -> Scored:
        ids, matrix = candidate_vectors(example.candidates, self.embed)
        chat_vec = self.embed([example.chat])[0]
        return Scored(ids=ids, scores=cosine_scores(chat_vec, matrix), answer=example.answer)

    def decide(self, example: DecisionExample, params: SorterParams | None = None) -> Decision:
        scored = self.score(example)
        return decide_from_scores(scored.ids, scored.scores, params or self.params)


class LeaveSorter:
    """B0: always leave the chat loose. Puts all its probability on "none"."""

    def score(self, example: DecisionExample) -> Scored:
        ids = [c.id for c in example.candidates]
        return Scored(ids=ids, scores=np.full(len(ids), -np.inf), answer=example.answer)

    def decide(self, example: DecisionExample, params: SorterParams | None = None) -> Decision:
        probs = dict.fromkeys((c.id for c in example.candidates), 0.0)
        probs[NONE_ID] = 1.0
        return Decision(probabilities=probs, action="leave", target=None)


def mean_nll(scored: Sequence[Scored], params: SorterParams, eps: float = 1e-12) -> float:
    """Mean negative log-likelihood of the answers (the calibration objective)."""
    if not scored:
        return 0.0
    total = 0.0
    for s in scored:
        total -= float(np.log(max(s.answer_probability(params), eps)))
    return total / len(scored)


def unique_texts(examples: Sequence[DecisionExample], chats: bool = True) -> list[str]:
    """Every distinct text a run will embed: candidate examples, loose texts and chats."""
    seen: dict[str, None] = {}
    for ex in examples:
        for cand in ex.candidates:
            for t in cand.examples:
                seen.setdefault(t)
            if cand.text is not None:
                seen.setdefault(cand.text)
            elif not cand.examples and cand.label:
                seen.setdefault(cand.label)
        if chats:
            seen.setdefault(ex.chat)
    return list(seen)


__all__ = [
    "NONE_ID",
    "EmbedFn",
    "LeaveSorter",
    "Scored",
    "Sorter",
    "SorterParams",
    "argmax_including_none",
    "bundle_vector",
    "candidate_vectors",
    "cosine_scores",
    "decide",
    "decide_from_scores",
    "mean_nll",
    "normalise",
    "probabilities",
    "softmax",
    "top_candidate",
    "unique_texts",
]
