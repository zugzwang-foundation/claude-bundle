"""Put a second, untrained base encoder on the board as B1b (relay extra 2).

Usage (from pipeline/), after the CLI runs that this script reads:

    uv run bundle-pipeline baseline --split exam     --encoder <id> --out-dir data/runs/b1b
    uv run bundle-pipeline baseline --split practice --encoder <id> --out-dir data/runs/b1b
    uv run bundle-pipeline calibrate --model <id> --out data/models/calibration-b1b.json --no-web
    uv run bundle-pipeline baseline --split exam --encoder <id> \\
        --calibration data/models/calibration-b1b.json --out-dir data/runs/b1b-calibrated
    uv run python scripts/w6_bootstrap_cutoffs.py --model <id> \\
        --calibration data/models/calibration-b1b.json --resamples 200
    uv run python scripts/w6_second_encoder.py --run-id 2026-10-16-toy-v0 --encoder <id>

What it does:

* Re-runs B1 (base encoder, its calibration) and B1b (second encoder, its own
  calibration) on the exam through the same `exam.run_encoder` path as the CLI,
  with the default parameters as well, and checks that the re-run reproduces the
  CLI's metrics (every key but latency) before anything lands on the board.
* Per-decision analyses the CLI records do not hold: accuracy by history length,
  answer type and difficulty for B1b (research README, recommendation 13), the
  paired bootstrap of B1b minus B1 in accuracy and macro-F1 (90% interval) and
  the McNemar counts, for the calibrated pair and for the default-parameter pair.
* Two checks on the encoder itself: its weights' dtype as loaded (the CLI runs
  whatever the checkpoint stores) against a float32 copy on the CPU, as the
  min and mean cosine over the exam's distinct texts and the share of exam
  decisions on which the two agree; and how many of the exam's and practice's
  distinct texts exceed the 128 word pieces that `encoder.Encoder` keeps.
* Writes runs/b1b-<run-id>.json with everything, then inserts B1b into
  scoreboard/runs/<run-id>.json after B1 with exactly the fourteen contract keys
  (the CLI's calibrated exam record), adds B1b to accuracy_by_history,
  accuracy_by_answer_type, accuracy_by_difficulty and calibration, adds a
  `second_encoder` block and notes, and keeps the winner line last. Re-running
  replaces the earlier B1b entry rather than adding a second one.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from bundle_pipeline import config
from bundle_pipeline.encoder import Encoder
from bundle_pipeline.exam import (
    METRIC_KEYS,
    answer_class,
    load_params,
    render_table,
    run_encoder,
)
from bundle_pipeline.scoreboard import board_sorter
from bundle_pipeline.sorter import argmax_including_none, unique_texts
from bundle_pipeline.store import read_examples, write_json

sys.path.insert(0, str(Path(__file__).resolve().parent))
from w6_board_extras import calibration_entry, read_json, relative  # noqa: E402
from w6_history_buckets import (  # noqa: E402
    BUCKET_ORDER,
    CLASS_ORDER,
    accuracy_by,
    bucket,
    history_lengths,
    markdown,
    paired_bootstrap,
    predictions_and_hits,
)

COMPARED_KEYS = tuple(k for k in METRIC_KEYS if k not in ("latency_ms_per_decision", "size_mb"))
WINNER_PREFIXES = ("B2 beats B1", "B2 does not beat B1", "no student")


def cli_record(path: Path, sorter_id: str = "B1") -> dict[str, Any]:
    data = read_json(path)
    if data is None:
        raise FileNotFoundError(f"missing CLI record {path}; run `bundle-pipeline baseline` first")
    return next(s for s in data["sorters"] if s["id"] == sorter_id)


def same_metrics(
    a: dict[str, Any], b: dict[str, Any], tol: float = 1e-6
) -> tuple[list[str], float]:
    """Keys (latency and size excluded) differing by more than tol, and the largest gap."""
    gaps = {k: abs(float(a[k]) - float(b[k])) for k in COMPARED_KEYS}
    return [k for k, g in gaps.items() if g > tol], max(gaps.values())


def dtype_check(
    encoder: Encoder, examples: list[Any], params: Any
) -> tuple[dict[str, Any], list[str]]:
    """The encoder as the CLI loads it against a float32 copy on the CPU."""
    import torch  # noqa: PLC0415

    as_loaded = next(encoder.model[0].auto_model.parameters()).dtype
    ref = Encoder(encoder.name, device="cpu", max_seq_length=encoder.model.max_seq_length)
    ref_dtype = next(ref.model[0].auto_model.parameters()).dtype
    if ref_dtype != torch.float32:
        ref.model = ref.model.float()
        ref._cache.clear()
        ref_dtype = next(ref.model[0].auto_model.parameters()).dtype
    texts = unique_texts(examples)
    a = encoder.encode(texts)
    b = ref.encode(texts)
    cos = np.sum(a * b, axis=1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1))
    ref_run = run_encoder("B1b-fp32", "second encoder, float32 on CPU", ref, examples, params)
    ref_preds = [argmax_including_none(d.probabilities) for d in ref_run.decisions]
    return (
        {
            "as_loaded": {"dtype": str(as_loaded), "device": encoder.device},
            "reference": {"dtype": str(ref_dtype), "device": ref.device},
            "texts": len(texts),
            "min_cos": round(float(cos.min()), 6),
            "mean_cos": round(float(cos.mean()), 6),
            "reference_metrics": {k: round(ref_run.metrics(examples)[k], 6) for k in COMPARED_KEYS},
        },
        ref_preds,
    )


def token_lengths(encoder: Encoder, texts: list[str], keep: int) -> dict[str, Any]:
    tok = encoder.model.tokenizer
    lengths = [len(ids) for ids in tok(texts, add_special_tokens=True)["input_ids"]]
    arr = np.asarray(lengths)
    return {
        "texts": len(texts),
        "word_pieces_kept_by_encoder": keep,
        "max": int(arr.max()),
        "mean": round(float(arr.mean()), 1),
        "over_kept": int((arr > keep).sum()),
        "over_256": int((arr > 256).sum()),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--encoder", required=True, help="the second encoder's Hub id")
    ap.add_argument("--base-encoder", default=config.BASE_ENCODER)
    ap.add_argument("--data-root", default=None)
    ap.add_argument("--board-dir", default=str(config.SCOREBOARD_RUNS_DIR))
    ap.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    ap.add_argument("--resamples", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    ap.add_argument("--facts", default=None, help="JSON file of measured facts to carry")
    args = ap.parse_args()

    paths = config.paths_for(args.data_root)
    runs = paths.runs_dir
    exam_file = paths.tasks_path("exam")
    examples = read_examples(exam_file)
    practice = read_examples(paths.tasks_path("practice"))
    answers = [ex.answer for ex in examples]

    cli_default = cli_record(runs / "b1b" / "baseline-exam.json")
    cli_calibrated = cli_record(runs / "b1b-calibrated" / "baseline-exam.json")
    cli_practice = cli_record(runs / "b1b" / "baseline-practice.json")
    for rec in (cli_default, cli_calibrated, cli_practice):
        if rec["model"] != args.encoder:
            raise SystemExit(f"CLI record is for {rec['model']}, not {args.encoder}")
    b1_default = cli_record(runs / "baseline-exam.json")
    cal_b1_path = paths.models_dir / "calibration-b1.json"
    cal_b1b_path = paths.models_dir / "calibration-b1b.json"
    cal_b1, cal_b1b = load_params(cal_b1_path), load_params(cal_b1b_path)

    # -- re-run both encoders through the exam's code path ------------------
    b1 = Encoder(args.base_encoder, device=args.device)
    b1b = Encoder(args.encoder, device=args.device)
    rerun = {
        "B1": run_encoder("B1", "base encoder, untrained", b1, examples, cal_b1),
        "B1-default": run_encoder("B1-default", "B1, defaults", b1, examples),
        "B1b": run_encoder("B1b", "second encoder, untrained", b1b, examples, cal_b1b),
        "B1b-default": run_encoder("B1b-default", "B1b, defaults", b1b, examples),
    }
    metrics = {k: r.metrics(examples) for k, r in rerun.items()}
    board_path = Path(args.board_dir) / f"{args.run_id}.json"
    board = read_json(board_path)
    if board is None:
        print(f"no board at {board_path}; run `bundle-pipeline scoreboard` first")
        return 2
    board_b1 = next(s for s in board["sorters"] if s["id"] == "B1")
    checks = {
        "B1b vs CLI calibrated": same_metrics(metrics["B1b"], cli_calibrated),
        "B1b-default vs CLI default": same_metrics(metrics["B1b-default"], cli_default),
        "B1 vs board": same_metrics(metrics["B1"], board_b1, tol=1e-6),
        "B1-default vs runs/baseline-exam.json": same_metrics(metrics["B1-default"], b1_default),
    }
    for name, (diff, gap) in checks.items():
        verdict = "reproduced" if not diff else "DIFFERS on " + ", ".join(diff)
        print(f"check {name}: {verdict} (largest gap {gap:.2e})")
    if any(diff for diff, _ in checks.values()):
        print("the re-run does not reproduce the CLI; nothing written")
        return 1

    # -- per-decision analyses ------------------------------------------------
    history = history_lengths(examples)
    buckets = [bucket(h) for h in history]
    classes = [answer_class(ex.answer) for ex in examples]
    difficulties = [ex.difficulty for ex in examples]
    preds = {k: predictions_and_hits(r, examples) for k, r in rerun.items()}
    by_bucket = {k: accuracy_by(buckets, h) for k, (_, h) in preds.items()}
    by_class = {k: accuracy_by(classes, h) for k, (_, h) in preds.items()}
    by_difficulty = {k: accuracy_by(difficulties, h) for k, (_, h) in preds.items()}
    diff_cal = paired_bootstrap(answers, preds["B1"][0], preds["B1b"][0], args.resamples, args.seed)
    diff_def = paired_bootstrap(
        answers, preds["B1-default"][0], preds["B1b-default"][0], args.resamples, args.seed
    )
    pairs = zip(preds["B1"][0], preds["B1b"][0], strict=True)
    agreement = float(np.mean([a == b for a, b in pairs]))

    # -- the encoder itself -----------------------------------------------------
    dtype_facts, ref_preds = dtype_check(b1b, examples, cal_b1b)
    dtype_facts["prediction_agreement_with_reference"] = round(
        float(np.mean([a == b for a, b in zip(preds["B1b"][0], ref_preds, strict=True)])), 4
    )
    keep = int(b1b.model.max_seq_length)
    lengths = {
        "exam": token_lengths(b1b, unique_texts(examples), keep),
        "practice": token_lengths(b1b, unique_texts(practice), keep),
    }
    facts = (read_json(Path(args.facts)) or {}) if args.facts else {}

    cal_b1b_json = read_json(cal_b1b_path)
    boot_b1b = read_json(runs / "bootstrap-calibration-b1b.json")
    result = {
        "run_id": args.run_id,
        "label": "toy scale",
        "encoder": args.encoder,
        "base_encoder": args.base_encoder,
        "tasks": str(exam_file),
        "n_examples": len(examples),
        "parameters": {
            "defaults": config.DEFAULT_SORTER.__dict__,
            "B1_calibrated": cal_b1.__dict__,
            "B1b_calibrated": cal_b1b.__dict__,
        },
        "exam": {
            "B1_default": {k: round(b1_default[k], 6) for k in METRIC_KEYS},
            "B1b_default": {k: round(cli_default[k], 6) for k in METRIC_KEYS},
            "B1_calibrated": {k: round(board_b1[k], 6) for k in METRIC_KEYS},
            "B1b_calibrated": {k: round(cli_calibrated[k], 6) for k in METRIC_KEYS},
        },
        "practice_default": {"B1b": {k: round(cli_practice[k], 6) for k in METRIC_KEYS}},
        "reproduction_checks": {
            k: f"reproduced, largest gap {g:.2e}" for k, (_, g) in checks.items()
        },
        "history_bucket_sizes": dict(Counter(buckets)),
        "accuracy_by_history": by_bucket,
        "accuracy_by_answer_type": by_class,
        "accuracy_by_difficulty": by_difficulty,
        "b1b_minus_b1": {"calibrated": diff_cal, "defaults": diff_def},
        "prediction_agreement_b1_b1b_calibrated": round(agreement, 4),
        "calibration_B1b": calibration_entry(cal_b1b_json, boot_b1b),
        "dtype_check": dtype_facts,
        "token_lengths": lengths,
        "facts": facts,
        "date": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out = runs / f"b1b-{args.run_id}.json"
    write_json(out, result)

    # -- the board ------------------------------------------------------------
    short = args.encoder.split("/")[-1]
    entry = board_sorter(
        {
            **cli_calibrated,
            "id": "B1b",
            "name": f"second base encoder, untrained ({short}, calibrated on practice)",
        }
    )
    sorters = [s for s in board["sorters"] if s["id"] != "B1b"]
    i_b1 = next(i for i, s in enumerate(sorters) if s["id"] == "B1")
    sorters.insert(i_b1 + 1, entry)
    board["sorters"] = sorters
    for key, table in (
        ("accuracy_by_history", by_bucket),
        ("accuracy_by_answer_type", by_class),
        ("accuracy_by_difficulty", by_difficulty),
    ):
        target = board.get(key)
        if target is None:
            continue
        target = target["by_sorter"] if "by_sorter" in target else target
        target["B1b"] = table["B1b"]
    board.setdefault("calibration", {})["B1b"] = result["calibration_B1b"]
    board["second_encoder"] = {
        "id": args.encoder,
        "board_id": "B1b",
        "board_entry_is": "the exam run with the parameters calibrated on practice "
        "(calibration-b1b.json), the same treatment as B1 and B2",
        **{k: v for k, v in facts.items()},
        "exam_default_parameters": result["exam"]["B1b_default"],
        "practice_default_parameters": result["practice_default"]["B1b"],
        "b1b_minus_b1": result["b1b_minus_b1"],
        "prediction_agreement_b1_b1b_calibrated": result["prediction_agreement_b1_b1b_calibrated"],
        "dtype_check": dtype_facts,
        "token_lengths": lengths,
        "details": relative(str(out)),
    }

    # notes may hold non-string entries written by other tools; they are kept as they are
    notes = [n for n in board.get("notes", []) if not (isinstance(n, str) and n.startswith("B1b"))]
    winner = None
    if notes and isinstance(notes[-1], str) and notes[-1].startswith(WINNER_PREFIXES):
        winner = notes.pop()
    p = cal_b1b
    e = result["exam"]
    d = diff_cal["accuracy_diff"]
    f = diff_cal["macro_f1_diff"]
    mc = diff_cal["mcnemar"]
    dd = diff_def["accuracy_diff"]
    hist = by_bucket["B1b"]
    notes.append(
        f"B1b: second base encoder {args.encoder}, untrained, on the board as the relay's "
        f"extra 2; {facts.get('licence', 'licence NOT VERIFIED')}; "
        f"{facts.get('download', 'download NOT VERIFIED')}"
    )
    notes.append(
        f"B1b params: temperature {p.temperature:.4f}, none_score {p.none_score:.3f}, "
        f"file_cutoff {p.file_cutoff:.4f}, suggest_cutoff {p.suggest_cutoff:.4f} "
        f"(calibrated on practice like B1, data/models/calibration-b1b.json; model {args.encoder})"
    )
    notes.append(
        f"B1b with the default parameters on the exam: accuracy "
        f"{e['B1b_default']['accuracy']:.3f}, "
        f"macro-F1 {e['B1b_default']['macro_f1']:.3f}, none P/R "
        f"{e['B1b_default']['none_precision']:.3f}/{e['B1b_default']['none_recall']:.3f} "
        f"(B1 with the defaults: {e['B1_default']['accuracy']:.3f}, "
        f"{e['B1_default']['macro_f1']:.3f}, {e['B1_default']['none_precision']:.3f}/"
        f"{e['B1_default']['none_recall']:.3f}); runs/b1b/baseline-exam.json"
    )
    notes.append(
        f"B1b minus B1 on the exam, paired bootstrap ({diff_cal['resamples']} resamples): "
        f"calibrated pair accuracy {d['point']:+.4f}, 90% {d['interval_90']}, positive in "
        f"{d['share_positive']:.0%} of resamples, macro-F1 {f['point']:+.4f}, 90% "
        f"{f['interval_90']}, McNemar B1b-only-right {mc['b_right_a_wrong']} vs B1-only-right "
        f"{mc['a_right_b_wrong']}; default pair accuracy {dd['point']:+.4f}, 90% "
        f"{dd['interval_90']}; the two encoders agree on {agreement:.0%} of calibrated decisions: "
        f"neither encoder leads at this size"
    )
    notes.append(
        "B1b accuracy by history length (<5 / 5-15 / >15 earlier chats): "
        + "/".join(f"{hist[b]['accuracy']:.3f}" for b in BUCKET_ORDER if b in hist)
        + "; by answer type bundle/loose/none: "
        + "/".join(
            f"{by_class['B1b'][c]['accuracy']:.3f}" for c in CLASS_ORDER if c in by_class["B1b"]
        )
    )
    notes.append(
        f"B1b runs in {dtype_facts['as_loaded']['dtype']} as the checkpoint stores it (B1 runs in "
        f"float32): against a float32 copy on the CPU, min cosine {dtype_facts['min_cos']:.6f} "
        f"over the exam's {dtype_facts['texts']} distinct texts, same prediction on "
        f"{dtype_facts['prediction_agreement_with_reference']:.0%} of exam decisions; both "
        f"encoders see the first {keep} word pieces, which cuts {lengths['exam']['over_kept']} of "
        f"the exam's distinct texts (max {lengths['exam']['max']}), so the 4,096-token context "
        f"is unused here"
    )
    if winner:
        notes.append(winner)
    board["notes"] = notes
    board["label"] = "toy scale"
    write_json(board_path, board)

    print(render_table(board["sorters"]))
    print()
    print(markdown("history length", by_bucket, BUCKET_ORDER))
    print()
    print(markdown("answer type", by_class, CLASS_ORDER))
    print()
    print(markdown("difficulty", by_difficulty, sorted(set(difficulties))))
    print()
    print(
        f"B1b minus B1 (calibrated): accuracy {d['point']:+.4f} 90% {d['interval_90']} "
        f"(positive in {d['share_positive']:.0%}); macro-F1 {f['point']:+.4f} 90% "
        f"{f['interval_90']}; McNemar {mc}"
    )
    print(
        f"B1b minus B1 (defaults): accuracy {dd['point']:+.4f} 90% {dd['interval_90']} "
        f"(positive in {dd['share_positive']:.0%}); macro-F1 "
        f"{diff_def['macro_f1_diff']['point']:+.4f}; McNemar {diff_def['mcnemar']}"
    )
    print(f"agreement B1/B1b (calibrated predictions): {agreement:.4f}")
    print(f"dtype check: {json.dumps(dtype_facts)}")
    print(f"token lengths: {json.dumps(lengths)}")
    for n in board["notes"]:
        print(f"- {n}")
    print(f"second encoder: wrote {out} and {board_path} ({board_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
