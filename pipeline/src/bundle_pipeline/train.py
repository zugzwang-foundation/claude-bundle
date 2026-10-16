"""`bundle-pipeline train`: fine-tune the base encoder on the lessons split -> student v0.

Pairs: every DecisionExample whose answer is not "none" becomes one
(anchor, positive) pair: the chat text and one text from the answer candidate,
a random example of the answer bundle or the answer loose chat's text (seeded).
Loss: MultipleNegativesRankingLoss with in-batch negatives (scale 20, cosine).
Batches are built so no two pairs in a batch share the same (person, answer):
a sibling chat of the same thread would otherwise be punished as a negative.

The loop is plain PyTorch (AdamW, linear warm-up then decay) around the
sentence-transformers model and loss, so no `datasets`/`accelerate` are needed.
Batch 32, 1 epoch, lr 2e-5 by default; a toy run on ~1000 examples takes a
minute or two on this Mac. The student is saved with ``SentenceTransformer.save``
to data/models/student-v0/ together with train_meta.json.
"""

from __future__ import annotations

import argparse
import random
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bundle_pipeline import config
from bundle_pipeline.schema import DecisionExample
from bundle_pipeline.store import read_examples, write_json


@dataclass(frozen=True)
class Pair:
    anchor: str
    positive: str
    key: str
    """person_id + answer id: pairs sharing a key never sit in the same batch."""


def build_pairs(examples: Sequence[DecisionExample], seed: int = config.DEFAULT_SEED) -> list[Pair]:
    """One (chat, positive) pair per example whose answer names a candidate."""
    rng = random.Random(seed)
    pairs: list[Pair] = []
    for ex in examples:
        if ex.answer == "none":
            continue
        cand = next((c for c in ex.candidates if c.id == ex.answer), None)
        if cand is None:
            continue
        if cand.kind == "bundle":
            texts = [t for t in cand.examples if t.strip()]
            positive = rng.choice(texts) if texts else (cand.label or "")
        else:
            positive = cand.text or ""
        if not positive.strip() or not ex.chat.strip() or positive == ex.chat:
            continue
        pairs.append(Pair(anchor=ex.chat, positive=positive, key=f"{ex.person_id}|{ex.answer}"))
    return pairs


def make_batches(pairs: Sequence[Pair], batch_size: int, rng: random.Random) -> list[list[Pair]]:
    """Shuffle, then fill batches greedily so each key appears at most once per batch.

    Pairs that cannot be placed start a new batch. Batches with fewer than two
    pairs are dropped (a batch of one has no negatives).
    """
    pool = list(pairs)
    rng.shuffle(pool)
    batches: list[list[Pair]] = []
    while pool:
        batch: list[Pair] = []
        keys: set[str] = set()
        rest: list[Pair] = []
        for p in pool:
            if len(batch) < batch_size and p.key not in keys:
                batch.append(p)
                keys.add(p.key)
            else:
                rest.append(p)
        batches.append(batch)
        pool = rest
    return [b for b in batches if len(b) >= 2]


def _features(model: Any, texts: list[str], device: str) -> dict[str, Any]:
    import torch  # noqa: PLC0415

    preprocess = getattr(model, "preprocess", None) or model.tokenize
    feats = preprocess(texts)
    return {k: (v.to(device) if torch.is_tensor(v) else v) for k, v in feats.items()}


def train(
    examples: Sequence[DecisionExample],
    out_dir: Path,
    base_model: str = config.BASE_ENCODER,
    epochs: int = 1,
    batch_size: int = 32,
    lr: float = 2e-5,
    seed: int = config.DEFAULT_SEED,
    device: str = "auto",
    max_seq_length: int = 128,
    warmup_ratio: float = 0.1,
    max_pairs: int | None = None,
    log: Any = print,
) -> dict[str, Any]:
    import torch  # noqa: PLC0415
    from sentence_transformers import SentenceTransformer  # noqa: PLC0415
    from sentence_transformers.sentence_transformer.losses import (  # noqa: PLC0415
        MultipleNegativesRankingLoss,
    )

    from bundle_pipeline.encoder import resolve_device  # noqa: PLC0415

    dev = resolve_device(device)
    torch.manual_seed(seed)
    random.seed(seed)
    rng = random.Random(seed)

    pairs = build_pairs(examples, seed)
    if max_pairs is not None:
        pairs = pairs[:max_pairs]
    if len(pairs) < 2:
        raise ValueError(f"only {len(pairs)} training pairs; nothing to learn from")
    batches_per_epoch = make_batches(pairs, batch_size, rng)
    total_steps = epochs * len(batches_per_epoch)
    warmup = max(1, int(total_steps * warmup_ratio))

    model = SentenceTransformer(base_model, device=dev)
    model.max_seq_length = max_seq_length
    loss_fn = MultipleNegativesRankingLoss(model)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)

    def lr_lambda(step: int) -> float:
        if step < warmup:
            return (step + 1) / warmup
        return max(0.0, (total_steps - step) / max(1, total_steps - warmup))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)
    log(
        f"train: {len(pairs)} pairs, {len(batches_per_epoch)} batches/epoch, {epochs} epoch(s), "
        f"lr {lr}, device {dev}, base {base_model}"
    )

    losses: list[float] = []
    t0 = time.perf_counter()
    step = 0
    model.train()
    for epoch in range(epochs):
        batches = batches_per_epoch if epoch == 0 else make_batches(pairs, batch_size, rng)
        for batch in batches:
            anchors = _features(model, [p.anchor for p in batch], dev)
            positives = _features(model, [p.positive for p in batch], dev)
            emb_a = model(anchors)["sentence_embedding"]
            emb_p = model(positives)["sentence_embedding"]
            loss = loss_fn.compute_loss_from_embeddings([emb_a, emb_p], labels=None)  # type: ignore[arg-type]
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            losses.append(float(loss.detach().cpu()))
            step += 1
            if step % 10 == 0 or step == total_steps:
                recent = sum(losses[-10:]) / len(losses[-10:])
                elapsed = time.perf_counter() - t0
                log(f"  step {step}/{total_steps}  loss {recent:.4f}  {elapsed:.0f}s")
    seconds = time.perf_counter() - t0
    model.eval()

    out_dir.mkdir(parents=True, exist_ok=True)
    model.save(str(out_dir), create_model_card=False)
    meta = {
        "student": out_dir.name,
        "base_model": base_model,
        "pairs": len(pairs),
        "examples": len(examples),
        "batches_per_epoch": len(batches_per_epoch),
        "epochs": epochs,
        "batch_size": batch_size,
        "lr": lr,
        "warmup_steps": warmup,
        "seed": seed,
        "device": dev,
        "max_seq_length": max_seq_length,
        "loss": "MultipleNegativesRankingLoss(scale=20, cos_sim), in-batch negatives",
        "loss_first": losses[0] if losses else None,
        "loss_last": losses[-1] if losses else None,
        "loss_mean": sum(losses) / len(losses) if losses else None,
        "seconds": round(seconds, 1),
        "date": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "torch": torch.__version__,
    }
    write_json(out_dir / "train_meta.json", meta)
    first, last = meta["loss_first"], meta["loss_last"]
    log(f"train: saved {out_dir} in {seconds:.0f}s; loss {first:.3f} -> {last:.3f}")
    return meta


def main(args: argparse.Namespace) -> int:
    tasks_file = Path(args.tasks)
    if not tasks_file.is_file():
        print(f"train: no tasks file at {tasks_file}; run `bundle-pipeline tasks` first")
        return 2
    examples = read_examples(tasks_file)
    train(
        examples,
        Path(args.out),
        base_model=args.encoder,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        seed=args.seed,
        device=args.device,
        max_seq_length=args.max_seq_length,
        max_pairs=args.max_pairs,
    )
    return 0


__all__ = ["Pair", "build_pairs", "make_batches", "train"]
