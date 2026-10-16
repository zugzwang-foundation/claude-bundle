"""`bundle-pipeline scoreboard`: turn an exam result into scoreboard/runs/<run-id>.json.

The board file (at the repository root, outside pipeline/) follows the fixed
contract: {"run_id", "label": "toy scale", "date", "exam_hash", "base_model",
"sorters": [{id, name, accuracy, macro_f1, none_precision, none_recall, ece,
brier, file_precision, file_coverage, suggest_precision, suggest_coverage,
latency_ms_per_decision, size_mb}], "notes"}. Sorter entries carry exactly
those keys; anything else from the exam run (parameters, timings) goes into
``notes`` as text. The same module prints the markdown table.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from bundle_pipeline.exam import METRIC_KEYS, render_table
from bundle_pipeline.store import write_json

LABEL = "toy scale"


def board_sorter(record: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"id": record["id"], "name": record["name"]}
    for key in METRIC_KEYS:
        out[key] = round(float(record.get(key, 0.0)), 6)
    return out


def build_board(
    exam_result: dict[str, Any],
    run_id: str | None = None,
    notes: Sequence[str] = (),
    label: str = LABEL,
) -> dict[str, Any]:
    all_notes = list(exam_result.get("notes", []))
    for rec in exam_result.get("sorters", []):
        if rec.get("params"):
            p = rec["params"]
            all_notes.append(
                f"{rec['id']} params: temperature {p['temperature']:.4f}, none_score "
                f"{p['none_score']:.3f}, file_cutoff {p['file_cutoff']:.4f}, suggest_cutoff "
                f"{p['suggest_cutoff']:.4f}"
                + (f" (model {rec['model']})" if rec.get("model") else "")
            )
    all_notes.extend(notes)
    return {
        "run_id": run_id or exam_result["run_id"],
        "label": label,
        "date": exam_result["date"],
        "exam_hash": exam_result["exam_hash"],
        "base_model": exam_result["base_model"],
        "sorters": [board_sorter(r) for r in exam_result.get("sorters", [])],
        "notes": all_notes,
    }


def winner_note(board: dict[str, Any]) -> str:
    """One line saying whether the student (B2) beat the base encoder (B1) on accuracy."""
    by_id = {s["id"]: s for s in board["sorters"]}
    if "B2" not in by_id or "B1" not in by_id:
        return "no student on this board; the site keeps B1"
    b1, b2 = by_id["B1"], by_id["B2"]
    if b2["accuracy"] > b1["accuracy"] and b2["macro_f1"] >= b1["macro_f1"]:
        return (
            f"B2 beats B1 (accuracy {b2['accuracy']:.3f} vs {b1['accuracy']:.3f}); "
            "wire B2 into the site through the manifest"
        )
    return (
        f"B2 does not beat B1 (accuracy {b2['accuracy']:.3f} vs {b1['accuracy']:.3f}); "
        "the site keeps B1"
    )


def newest_exam_result(runs_dir: Path, run_id: str | None) -> Path | None:
    if run_id:
        p = runs_dir / f"exam-{run_id}.json"
        return p if p.is_file() else None
    candidates = sorted(runs_dir.glob("exam-*.json"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def main(args: argparse.Namespace) -> int:
    source = (
        Path(args.source) if args.source else newest_exam_result(Path(args.runs_dir), args.run_id)
    )
    if source is None or not source.is_file():
        print("scoreboard: no exam result found; run `bundle-pipeline exam` first")
        return 2
    exam_result = json.loads(source.read_text(encoding="utf-8"))
    board = build_board(exam_result, run_id=args.run_id, notes=args.notes or [])
    board["notes"].append(winner_note(board))
    out = Path(args.out_dir) / f"{board['run_id']}.json"
    write_json(out, board)
    print(render_table(board["sorters"]))
    for n in board["notes"]:
        print(f"- {n}")
    print(f"scoreboard: wrote {out}")
    return 0


__all__ = [
    "LABEL",
    "board_sorter",
    "build_board",
    "newest_exam_result",
    "render_table",
    "winner_note",
]
