"""Exam accuracy against history length, the int8 export's exam effect, and a paired bootstrap.

Usage (from pipeline/):

    uv run python scripts/w6_history_buckets.py --run-id 2026-10-16-toy-v0 \\
        --b1-calibration data/models/calibration-b1.json

* History length of a decision = how many chats the person already had at that
  moment. `tasks` writes one example per chat in day order, so the k-th example
  of a person (0-based, in file order) has k earlier chats. Buckets: fewer than
  5, 5 to 15, more than 15 (research README, recommendation 13). Accuracy is
  also broken down by answer type (bundle / loose / none) and by difficulty.
* The sorters run through the same code as `exam` (run_leave, run_encoder) with
  the same parameters, so the overall numbers match runs/exam-<run-id>.json. A
  fourth sorter, B2q, is the int8 ONNX export of the student run by onnxruntime
  on the CPU with B2's calibration: its metrics next to B2's are the "exam
  effect" of int8 quantisation (research README, recommendation 4).
* Paired bootstrap (default 1000 resamples of the exam examples) of B2 minus B1
  in accuracy and macro-F1 with the 90% interval, plus the McNemar counts.

Writes runs/exam-<run-id>-buckets.json and prints markdown tables.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from bundle_pipeline import config
from bundle_pipeline.encoder import Encoder
from bundle_pipeline.exam import (
    METRIC_KEYS,
    SorterRun,
    answer_class,
    load_params,
    macro_f1,
    render_table,
    run_encoder,
    run_leave,
)
from bundle_pipeline.export import INPUT_NAMES, mean_pool_normalise
from bundle_pipeline.schema import DecisionExample
from bundle_pipeline.sorter import argmax_including_none
from bundle_pipeline.store import read_examples, write_json

BUCKETS: tuple[tuple[str, int, int], ...] = (("<5", 0, 4), ("5-15", 5, 15), (">15", 16, 10**9))
BUCKET_ORDER = tuple(b[0] for b in BUCKETS)
CLASS_ORDER = ("bundle", "loose", "none")


def bucket(history: int) -> str:
    for name, lo, hi in BUCKETS:
        if lo <= history <= hi:
            return name
    raise ValueError(history)


def history_lengths(examples: Sequence[DecisionExample]) -> list[int]:
    """Chats the person already had before each example (file order within a person)."""
    seen: Counter[str] = Counter()
    out: list[int] = []
    for ex in examples:
        out.append(seen[ex.person_id])
        seen[ex.person_id] += 1
    return out


class OnnxEncoder:
    """The int8 export behind the same tiny interface as encoder.Encoder (CPU, onnxruntime)."""

    def __init__(self, export_dir: Path, onnx_file: str, max_seq_length: int = 128) -> None:
        import onnxruntime as ort  # noqa: PLC0415
        from transformers import AutoTokenizer  # noqa: PLC0415

        self.path = export_dir / onnx_file
        self.name = f"{export_dir.name}/{onnx_file}"
        self.device = "cpu/onnxruntime"
        self.max_seq_length = max_seq_length
        self.session = ort.InferenceSession(str(self.path), providers=["CPUExecutionProvider"])
        self.tokenizer = AutoTokenizer.from_pretrained(str(export_dir))
        self._cache: dict[str, np.ndarray] = {}

    def _encode_raw(self, texts: list[str]) -> np.ndarray:
        chunks: list[np.ndarray] = []
        for i in range(0, len(texts), 64):
            enc = self.tokenizer(
                texts[i : i + 64],
                padding=True,
                truncation=True,
                max_length=self.max_seq_length,
                return_tensors="np",
            )
            feeds = {k: np.asarray(enc[k], dtype=np.int64) for k in INPUT_NAMES if k in enc}
            if "token_type_ids" not in feeds:
                feeds["token_type_ids"] = np.zeros_like(feeds["input_ids"])
            hidden = self.session.run(["last_hidden_state"], feeds)[0]
            chunks.append(mean_pool_normalise(hidden, feeds["attention_mask"]))
        if not chunks:
            return np.zeros((0, config.EMBEDDING_DIM), dtype=np.float32)
        return np.concatenate(chunks).astype(np.float32)

    def warm(self, texts: Iterable[str]) -> int:
        missing = list(dict.fromkeys(t for t in texts if t not in self._cache))
        if missing:
            for text, vec in zip(missing, self._encode_raw(missing), strict=True):
                self._cache[text] = vec
        return len(missing)

    def encode(self, texts: list[str]) -> np.ndarray:
        self.warm(texts)
        if not texts:
            return np.zeros((0, config.EMBEDDING_DIM), dtype=np.float32)
        return np.stack([self._cache[t] for t in texts])

    def encode_uncached(self, texts: list[str]) -> np.ndarray:
        return self._encode_raw(texts)

    def size_mb(self) -> float:
        return self.path.stat().st_size / 1e6


def predictions_and_hits(
    run: SorterRun, examples: Sequence[DecisionExample]
) -> tuple[list[str], list[bool]]:
    preds = [argmax_including_none(d.probabilities) for d in run.decisions]
    return preds, [p == ex.answer for p, ex in zip(preds, examples, strict=True)]


def accuracy_by(keys: Sequence[str], hits: Sequence[bool]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[bool]] = defaultdict(list)
    for k, h in zip(keys, hits, strict=True):
        groups[k].append(h)
    return {k: {"n": len(v), "accuracy": round(sum(v) / len(v), 4)} for k, v in groups.items()}


def markdown(title: str, by_sorter: dict[str, dict[str, Any]], order: Sequence[str]) -> str:
    ids = list(by_sorter)
    lines = [
        f"| {title} | n | " + " | ".join(ids) + " |",
        "|---|---|" + "|".join("---" for _ in ids) + "|",
    ]
    for key in order:
        n = next((by_sorter[s][key]["n"] for s in ids if key in by_sorter[s]), 0)
        cells = [
            f"{by_sorter[s][key]['accuracy']:.3f}" if key in by_sorter[s] else "-" for s in ids
        ]
        lines.append(f"| {key} | {n} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def paired_bootstrap(
    answers: Sequence[str],
    preds_a: Sequence[str],
    preds_b: Sequence[str],
    resamples: int = 1000,
    seed: int = config.DEFAULT_SEED,
) -> dict[str, Any]:
    """B minus A in accuracy and macro-F1 over resamples of the same examples (90% interval)."""
    rng = np.random.default_rng(seed)
    n = len(answers)
    hits_a = np.array([p == a for p, a in zip(preds_a, answers, strict=True)])
    hits_b = np.array([p == a for p, a in zip(preds_b, answers, strict=True)])
    acc_d: list[float] = []
    f1_d: list[float] = []
    for _ in range(resamples):
        idx = rng.integers(0, n, n)
        acc_d.append(float(hits_b[idx].mean() - hits_a[idx].mean()))
        ans = [answers[i] for i in idx]
        f1_b = macro_f1(ans, [preds_b[i] for i in idx])
        f1_a = macro_f1(ans, [preds_a[i] for i in idx])
        f1_d.append(f1_b - f1_a)

    def summary(point: float, d: list[float]) -> dict[str, Any]:
        arr = np.asarray(d)
        return {
            "point": round(point, 4),
            "interval_90": [
                round(float(np.percentile(arr, 5)), 4),
                round(float(np.percentile(arr, 95)), 4),
            ],
            "share_positive": round(float((arr > 0).mean()), 3),
        }

    return {
        "resamples": resamples,
        "seed": seed,
        "accuracy_diff": summary(float(hits_b.mean() - hits_a.mean()), acc_d),
        "macro_f1_diff": summary(
            macro_f1(list(answers), list(preds_b)) - macro_f1(list(answers), list(preds_a)), f1_d
        ),
        "mcnemar": {
            "b_right_a_wrong": int((hits_b & ~hits_a).sum()),
            "a_right_b_wrong": int((hits_a & ~hits_b).sum()),
            "both_right": int((hits_a & hits_b).sum()),
            "both_wrong": int((~hits_a & ~hits_b).sum()),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--tasks", default=str(config.tasks_path("exam")))
    ap.add_argument("--encoder", default=config.BASE_ENCODER)
    ap.add_argument("--b1-calibration", default=None)
    ap.add_argument("--model", default=str(config.MODELS_DIR / "student-v0"))
    ap.add_argument("--calibration", default=str(config.CALIBRATION_JSON))
    ap.add_argument("--export", default=str(config.MODELS_DIR / "student-v0-onnx"))
    ap.add_argument("--onnx-file", default="onnx/model_quantized.onnx")
    ap.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    ap.add_argument("--resamples", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    ap.add_argument("--out", default=None, help="default runs/exam-<run-id>-buckets.json")
    args = ap.parse_args()

    examples = read_examples(Path(args.tasks))
    history = history_lengths(examples)
    buckets = [bucket(h) for h in history]
    classes = [answer_class(ex.answer) for ex in examples]
    difficulties = [ex.difficulty for ex in examples]
    answers = [ex.answer for ex in examples]

    runs: list[SorterRun] = [run_leave(examples)]
    b1 = Encoder(args.encoder, device=args.device)
    runs.append(
        run_encoder("B1", "base encoder, untrained", b1, examples, load_params(args.b1_calibration))
    )
    b2_params = load_params(args.calibration)
    student = Encoder(args.model, device=args.device)
    runs.append(run_encoder("B2", "student v0", student, examples, b2_params))
    export_dir = Path(args.export)
    if (export_dir / args.onnx_file).is_file():
        quant = OnnxEncoder(export_dir, args.onnx_file)
        runs.append(run_encoder("B2q", "student v0, int8 ONNX on CPU", quant, examples, b2_params))

    preds = {r.sorter_id: predictions_and_hits(r, examples) for r in runs}
    by_bucket = {sid: accuracy_by(buckets, h) for sid, (_, h) in preds.items()}
    by_class = {sid: accuracy_by(classes, h) for sid, (_, h) in preds.items()}
    by_difficulty = {sid: accuracy_by(difficulties, h) for sid, (_, h) in preds.items()}
    records = [r.record(examples) for r in runs]
    by_id = {rec["id"]: rec for rec in records}

    int8_effect: dict[str, Any] | None = None
    if "B2q" in by_id:
        keys = [k for k in METRIC_KEYS if k not in ("latency_ms_per_decision", "size_mb")]
        int8_effect = {
            "metrics": {
                k: {
                    "B2": round(by_id["B2"][k], 4),
                    "B2q": round(by_id["B2q"][k], 4),
                    "diff": round(by_id["B2q"][k] - by_id["B2"][k], 4),
                }
                for k in keys
            },
            "prediction_agreement": round(
                float(
                    np.mean([a == b for a, b in zip(preds["B2"][0], preds["B2q"][0], strict=True)])
                ),
                4,
            ),
            "latency_ms_per_decision_cpu_onnxruntime": by_id["B2q"]["latency_ms_per_decision"],
            "size_mb_int8": by_id["B2q"]["size_mb"],
        }

    result = {
        "run_id": args.run_id,
        "label": "toy scale",
        "tasks": args.tasks,
        "n_examples": len(examples),
        "history_definition": (
            "validated chats of the same person before this one (file order of tasks/exam.jsonl)"
        ),
        "history_bucket_sizes": dict(Counter(buckets)),
        "accuracy_by_history": by_bucket,
        "accuracy_by_answer_type": by_class,
        "accuracy_by_difficulty": by_difficulty,
        "sorters": records,
        "b2_minus_b1": paired_bootstrap(
            answers, preds["B1"][0], preds["B2"][0], args.resamples, args.seed
        ),
        "int8_exam_effect": int8_effect,
        "date": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out = Path(args.out) if args.out else config.RUNS_DIR / f"exam-{args.run_id}-buckets.json"
    write_json(out, result)

    print(render_table(records))
    print()
    print(markdown("history length", by_bucket, BUCKET_ORDER))
    print()
    print(markdown("answer type", by_class, CLASS_ORDER))
    print()
    print(markdown("difficulty", by_difficulty, sorted({d for d in difficulties})))
    print()
    d = result["b2_minus_b1"]
    print(
        f"B2 minus B1: accuracy {d['accuracy_diff']['point']:+.4f} "
        f"90% {d['accuracy_diff']['interval_90']} "
        f"(positive in {d['accuracy_diff']['share_positive']:.0%} of resamples); "
        f"macro-F1 {d['macro_f1_diff']['point']:+.4f} "
        f"90% {d['macro_f1_diff']['interval_90']}; McNemar {d['mcnemar']}"
    )
    if int8_effect:
        m = int8_effect["metrics"]
        print(
            f"int8 exam effect: accuracy {m['accuracy']['B2']:.4f} -> {m['accuracy']['B2q']:.4f}, "
            f"macro-F1 {m['macro_f1']['B2']:.4f} -> {m['macro_f1']['B2q']:.4f}, "
            f"prediction agreement {int8_effect['prediction_agreement']:.4f}, "
            f"latency {int8_effect['latency_ms_per_decision_cpu_onnxruntime']:.1f} ms on CPU"
        )
    print(f"buckets: wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
