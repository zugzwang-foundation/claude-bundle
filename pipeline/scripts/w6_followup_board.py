"""Add the toy follow-up result to the board: a top-level "follow_up_toy" object and one note.

Reads data/runs/followup-toy.json (written by `bundle-pipeline followup-toy`)
and, when present, data/runs/followup-toy-paired.json (scripts/w6_followup_paired.py),
re-reads scoreboard/runs/<run-id>.json right before writing (another agent edits
it too), replaces any earlier follow-up entry (including one an older version
placed inside `notes`), keeps the winner line last and writes atomically after
checking the JSON parses.

    uv run python scripts/w6_followup_board.py --run-id 2026-10-16-toy-v0
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WINNER_STARTS = ("B2 beats B1", "B2 does not beat B1", "no student")


def relative(value: str) -> str:
    return value.replace(str(REPO) + "/", "")


def summary(obj: dict) -> str:
    b, s = obj["encoders"]["base"]["exam"], obj["encoders"]["student"]["exam"]
    n = obj["pairs"]["exam"]["total"]
    return (
        f"follow-up toy (is this chat a follow-up to that one? cosine of the two chats, "
        f"threshold fit on {obj['pairs']['practice']['total']} practice pairs, judged on {n} "
        f"balanced exam pairs): base AUC {b['auc']:.3f}, accuracy {b['accuracy']:.3f}, "
        f"precision {b['precision']:.3f}, recall {b['recall']:.3f}; student AUC {s['auc']:.3f}, "
        f"accuracy {s['accuracy']:.3f}, precision {s['precision']:.3f}, recall {s['recall']:.3f}; "
        f"toy scale, two people per split"
    )


def build(src: dict, paired: dict | None) -> dict:
    encoders = {}
    for name, r in src["encoders"].items():
        e = r["exam"]
        encoders[name] = {
            "model": relative(r["model"]),
            "practice_auc": round(r["practice"]["auc"], 4),
            "threshold": round(r["practice"]["threshold"], 4),
            "exam": {
                "auc": round(e["auc"], 4),
                "auc_90": [round(x, 4) for x in e["bootstrap"]["auc_90"]],
                "accuracy": round(e["accuracy"], 4),
                "accuracy_90": [round(x, 4) for x in e["bootstrap"]["accuracy_90"]],
                "precision": round(e["precision"], 4),
                "precision_90": [round(x, 4) for x in e["bootstrap"]["precision_90"]],
                "recall": round(e["recall"], 4),
                "recall_90": [round(x, 4) for x in e["bootstrap"]["recall_90"]],
                "f1": round(e["f1"], 4),
                "oracle_accuracy": round(e["oracle_accuracy"], 4),
                "positive_recall_by_gap_days": e["positive_recall_by_gap_days"],
                "negatives_rejected_by_kind": e["negatives_rejected_by_kind"],
            },
        }
    obj = {
        "label": "toy scale",
        "task": src["task"],
        "date": src["date"],
        "seed": src["seed"],
        "max_pairs": src["max_pairs"],
        "pairs": src["pairs"],
        "threshold_fit_on": "practice pairs, highest accuracy; applied unchanged to the exam pairs",
        "bootstrap": "90% intervals, percentiles 5 and 95 over 200 resamples of the exam pairs",
        "encoders": encoders,
        "source": relative(src.get("source", "pipeline/data/runs/followup-toy.json")),
        "command": "uv run bundle-pipeline followup-toy --device mps",
    }
    if paired:
        obj["student_minus_base"] = {
            "resamples": paired["resamples"],
            "accuracy_diff": round(paired["accuracy_diff"], 4),
            "accuracy_diff_90": [round(x, 4) for x in paired["accuracy_diff_90"]],
            "accuracy_diff_positive_share": round(paired["accuracy_diff_positive_share"], 3),
            "auc_diff": round(paired["auc_diff"], 4),
            "auc_diff_90": [round(x, 4) for x in paired["auc_diff_90"]],
            "auc_diff_positive_share": round(paired["auc_diff_positive_share"], 3),
            "mcnemar": paired["mcnemar"],
        }
    return obj


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--run-id", default="2026-10-16-toy-v0")
    ap.add_argument("--source", default=str(REPO / "pipeline/data/runs/followup-toy.json"))
    ap.add_argument("--paired", default=str(REPO / "pipeline/data/runs/followup-toy-paired.json"))
    ap.add_argument("--board", default=None, help="default scoreboard/runs/<run-id>.json")
    args = ap.parse_args()
    board_path = (
        Path(args.board) if args.board else REPO / "scoreboard" / "runs" / f"{args.run_id}.json"
    )
    src = json.loads(Path(args.source).read_text(encoding="utf-8"))
    src["source"] = args.source
    paired_path = Path(args.paired)
    paired = json.loads(paired_path.read_text(encoding="utf-8")) if paired_path.is_file() else None
    entry = {"follow_up_toy": build(src, paired)}

    board = json.loads(board_path.read_text(encoding="utf-8"))  # re-read right before writing
    notes = [
        n
        for n in board.get("notes", [])
        if not (isinstance(n, dict) and "follow_up_toy" in n)
        and not (isinstance(n, str) and n.startswith("follow-up toy ("))
    ]
    winner = None
    if notes and isinstance(notes[-1], str) and notes[-1].startswith(WINNER_STARTS):
        winner = notes.pop()
    notes.append(summary(entry["follow_up_toy"]))
    board["follow_up_toy"] = entry["follow_up_toy"]
    if winner is not None:
        notes.append(winner)
    board["notes"] = notes
    text = json.dumps(board, indent=2, ensure_ascii=False) + "\n"
    json.loads(text)  # must parse before it replaces the file
    tmp = board_path.with_name(board_path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, board_path)
    print(f"wrote {board_path} ({len(text)} bytes, {len(notes)} notes; follow_up_toy added)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
