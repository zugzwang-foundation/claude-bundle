"""Add the run's facts to scoreboard/runs/<run-id>.json after `scoreboard` has written it.

Usage (from pipeline/):

    uv run python scripts/w6_board_extras.py --run-id 2026-10-16-toy-v0

`scoreboard` writes the contract keys (run_id, label, date, exam_hash, base_model,
sorters, notes). This adds, as extra top-level keys that a strict reader can
ignore: people, chat and decision counts per split (validated/report.json,
splits/split.json, tasks/*.jsonl); the calibration of B2 and B1 with their
bootstrap intervals (models/calibration*.json, runs/bootstrap-*.json); the
teacher (model file, licence, prompt version and the totals from generate.log);
the student's training facts (models/student-v0/train_meta.json); the export and
its parity (models/student-v0-onnx/export_report.json); accuracy by history
length, answer type and difficulty, the int8 exam effect and the paired
B2-minus-B1 bootstrap (runs/exam-<run-id>-buckets.json). The same facts are
summarised into `notes` as text, and absolute paths in the notes are made
repository-relative. The winner line stays last.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from bundle_pipeline import config
from bundle_pipeline.exam import render_table
from bundle_pipeline.store import write_json

TEACHER_LICENCE = (
    "Apache-2.0 (model-card tag and LICENSE file of Qwen/Qwen3-4B-Instruct-2507, read "
    "2026-10-16; docs/toy-teacher.md)"
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def answer_counts(tasks_path: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    if tasks_path.is_file():
        with tasks_path.open(encoding="utf-8") as fh:
            for line in fh:
                ans = json.loads(line)["answer"]
                kind = "none" if ans == "none" else ("bundle" if ans.startswith("b:") else "loose")
                counts[kind] += 1
    return {"total": sum(counts.values()), **dict(sorted(counts.items()))}


def parse_generate_log(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        if cells[1] == "start":
            for tok in cells[2].split():
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    out[k] = v
        elif cells[1] == "totals":
            out["totals"] = json.loads(cells[2])
        elif cells[1] == "end":
            out["end"] = cells[2]
    return out


def relative(text: str | None) -> str | None:
    if text is None:
        return None
    return text.replace(str(config.REPO_ROOT) + "/", "")


def calibration_entry(cal: dict | None, boot: dict | None) -> dict | None:
    if not cal:
        return None
    keys = ("temperature", "none_score", "file_cutoff", "suggest_cutoff", "practice_size", "source")
    entry: dict[str, Any] = {k: cal[k] for k in keys if k in cal}
    entry["model"] = relative(cal.get("model"))
    if boot:
        entry["bootstrap"] = {
            "resamples": boot["resamples"],
            "interval": boot["interval"],
            "point_on_practice": boot["point"],
            "intervals": boot["intervals"],
            "target_reached_share": boot["target_reached_share"],
        }
    return entry


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--data-root", default=None)
    ap.add_argument("--board-dir", default=str(config.SCOREBOARD_RUNS_DIR))
    ap.add_argument("--teacher-licence", default=TEACHER_LICENCE)
    args = ap.parse_args()

    paths = config.paths_for(args.data_root)
    board_path = Path(args.board_dir) / f"{args.run_id}.json"
    board = read_json(board_path)
    if board is None:
        print(f"board extras: no board at {board_path}; run `bundle-pipeline scoreboard` first")
        return 2

    summary = (read_json(paths.validated_people.parent / "report.json") or {}).get("summary", {})
    split = read_json(paths.splits_dir / "split.json") or {}
    board["people"] = {
        "generated": summary.get("input_files"),
        "validated": summary.get("accepted"),
        **split.get("people", {}),
    }
    board["chats"] = {
        "generated": summary.get("chats_in"),
        "validated": summary.get("chats_out"),
        "dropped_exact_duplicates": summary.get("dropped_exact"),
        "dropped_near_duplicates": summary.get("dropped_near"),
        **split.get("chats", {}),
    }
    board["examples"] = {name: answer_counts(paths.tasks_path(name)) for name in config.SPLIT_NAMES}

    cal_b2 = read_json(paths.calibration_json)
    cal_b1 = read_json(paths.models_dir / "calibration-b1.json")
    boot_b2 = read_json(paths.runs_dir / "bootstrap-calibration.json")
    boot_b1 = read_json(paths.runs_dir / "bootstrap-calibration-b1.json")
    board["calibration"] = {
        "method": (
            "temperature and none score by coordinate descent on the practice NLL, then the "
            "smallest observed p_top with >= 0.95 (file) / 0.80 (suggest) precision and support "
            ">= 5; toy scale: see the bootstrap intervals"
        ),
        "B2": calibration_entry(cal_b2, boot_b2),
        "B1": calibration_entry(cal_b1, boot_b1),
    }

    gen = parse_generate_log(paths.generate_log)
    board["teacher"] = {
        "model": "Qwen3-4B-Instruct-2507",
        "file": Path(gen["model"]).name if gen.get("model") else None,
        "server": "llama-server (Metal) on this Mac, OpenAI-compatible API",
        "licence": args.teacher_licence,
        "prompt_version": gen.get("prompt", config.PROMPT_VERSION),
        "seed": gen.get("seed"),
        "people_asked": gen.get("people"),
        "chats_per_person_target": gen.get("target"),
        "workers": gen.get("workers"),
        "totals": gen.get("totals"),
        "end": gen.get("end"),
    }
    board["student"] = read_json(paths.models_dir / "student-v0" / "train_meta.json")

    export = read_json(paths.models_dir / "student-v0-onnx" / "export_report.json")
    if export:
        board["export"] = {
            "dir": relative(str(paths.models_dir / "student-v0-onnx")),
            "layout": "Transformers.js: config.json, tokenizer*.json, special_tokens_map.json, "
            "onnx/model.onnx (fp32), onnx/model_quantized.onnx (int8), manifest.json",
            **{
                k: export[k]
                for k in (
                    "exporter",
                    "quantization",
                    "files",
                    "parity_texts",
                    "parity",
                    "target_min_cos",
                    "int8_meets_target",
                    "versions",
                )
                if k in export
            },
        }

    buckets = read_json(paths.runs_dir / f"exam-{args.run_id}-buckets.json")
    if buckets:
        board["accuracy_by_history"] = {
            "definition": buckets["history_definition"],
            "bucket_sizes": buckets["history_bucket_sizes"],
            "by_sorter": buckets["accuracy_by_history"],
        }
        board["accuracy_by_answer_type"] = buckets["accuracy_by_answer_type"]
        board["accuracy_by_difficulty"] = buckets["accuracy_by_difficulty"]
        board["b2_minus_b1"] = buckets["b2_minus_b1"]
        board["int8_exam_effect"] = buckets["int8_exam_effect"]

    notes = [relative(n) for n in board.get("notes", [])]
    winner = None
    if notes and (
        notes[-1].startswith("B2 beats B1")
        or notes[-1].startswith("B2 does not beat B1")
        or notes[-1].startswith("no student")
    ):
        winner = notes.pop()
    if boot_b2:
        iv = boot_b2["intervals"]
        pt = boot_b2["point"]
        notes.append(
            f"calibration bootstrap, toy scale ({boot_b2['resamples']} resamples of the "
            f"{boot_b2['n_examples']} practice decisions, 90% intervals): B2 precision at its file "
            f"cut-off {pt['file_precision']:.3f} {iv['file_precision']}, coverage "
            f"{pt['file_coverage']:.3f} {iv['file_coverage']}; at its suggest cut-off "
            f"{pt['suggest_precision']:.3f} {iv['suggest_precision']}, coverage "
            f"{pt['suggest_coverage']:.3f} {iv['suggest_coverage']}; re-chosen file cut-off "
            f"{iv['file_cutoff']}, suggest cut-off {iv['suggest_cutoff']}, temperature "
            f"{iv['temperature']}"
        )
    if buckets:
        hist = buckets["accuracy_by_history"]
        sizes = buckets["history_bucket_sizes"]
        order = ("<5", "5-15", ">15")
        parts = []
        for sid in ("B1", "B2"):
            cells = "/".join(f"{hist[sid][b]['accuracy']:.3f}" for b in order if b in hist[sid])
            parts.append(f"{sid} {cells}")
        n_cells = "/".join(str(sizes.get(b, 0)) for b in order)
        notes.append(
            f"accuracy by history length (<5 / 5-15 / >15 earlier chats; n {n_cells}): "
            + ", ".join(parts)
        )
        d = buckets["b2_minus_b1"]
        acc, f1, mc = d["accuracy_diff"], d["macro_f1_diff"], d["mcnemar"]
        notes.append(
            f"paired bootstrap ({d['resamples']} resamples) of B2 minus B1 on the exam: accuracy "
            f"{acc['point']:+.4f}, 90% {acc['interval_90']}, positive in "
            f"{acc['share_positive']:.0%} of resamples; macro-F1 {f1['point']:+.4f}, 90% "
            f"{f1['interval_90']}; McNemar B2-only-right {mc['b_right_a_wrong']} vs B1-only-right "
            f"{mc['a_right_b_wrong']}: the lead is within noise at this size"
        )
        eff = buckets.get("int8_exam_effect")
        if eff:
            m = eff["metrics"]
            notes.append(
                f"int8 exam effect (research item 4): the int8 ONNX student via onnxruntime "
                f"makes the same prediction as the PyTorch student on "
                f"{eff['prediction_agreement']:.0%} of exam decisions; accuracy "
                f"{m['accuracy']['B2']:.3f} -> {m['accuracy']['B2q']:.3f}, "
                f"macro-F1 {m['macro_f1']['B2']:.3f} -> {m['macro_f1']['B2q']:.3f}, ECE "
                f"{m['ece']['B2']:.3f} -> {m['ece']['B2q']:.3f}, file precision "
                f"{m['file_precision']['B2']:.3f} -> {m['file_precision']['B2q']:.3f}; "
                f"{eff['latency_ms_per_decision_cpu_onnxruntime']:.1f} ms per decision on CPU, "
                f"{eff['size_mb_int8']:.1f} MB"
            )
    notes.append(
        "unusual: the exam and practice splits hold two people each (114 and 117 decisions); "
        "all people come from one 4B teacher and one prompt version, so the exam is not an "
        "out-of-distribution check; one requested person failed (p42-018, ReadTimeout)"
    )
    if winner:
        notes.append(winner)
    board["notes"] = notes
    board["label"] = "toy scale"
    write_json(board_path, board)
    print(render_table(board["sorters"]))
    for n in board["notes"]:
        print(f"- {n}")
    print(f"board extras: wrote {board_path} ({board_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
