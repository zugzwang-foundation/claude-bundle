"""Finalise scoreboard/runs/<run-id>.json: check the contract and the extras, fix the gaps.

Usage (from pipeline/):

    uv run python scripts/w6_board_finalise.py --run-id 2026-10-16-toy-v0 [--check]

Checks: the file parses; label "toy scale"; run_id, date, exam_hash (equal to
splits/exam.sha256) and base_model; sorters B0, B1, B1b (when present) and B2
in that order, each with exactly the fourteen contract keys and the values of
the exam run it came from; people, chat and decision counts that add up; a
calibration entry for every encoder on the board; the teacher block; notes
that are all text and include the int8 parity (PyTorch vs onnxruntime, and vs
Transformers.js in Node), the follow-up toy, what the site uses and, last, the
winner line.

Fixes: an object another tool placed inside `notes` moves to a top-level key of
the same name (follow_up_toy); the Node parity (runs/parity-summary.json) is
added as `export.parity_node` and as one note; the site note is added before
the winner line; absolute paths in notes become repository-relative. Running
it twice changes nothing. With --check nothing is written; a failed check
exits 1 either way.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from bundle_pipeline import config
from bundle_pipeline.exam import METRIC_KEYS, render_table
from bundle_pipeline.store import write_json

CONTRACT_KEYS = ("id", "name", *METRIC_KEYS)
RATIO_KEYS = tuple(k for k in METRIC_KEYS if k not in ("latency_ms_per_decision", "size_mb"))
WINNER_PREFIXES = ("B2 beats B1", "B2 does not beat B1", "no student")
NODE_NOTE_PREFIX = "int8 parity in Node"
SITE_NOTE_PREFIX = "site:"
TARGET = 0.999
EXPECTED_ORDER = ("B0", "B1", "B1b", "B2")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def relative(text: str) -> str:
    return text.replace(str(config.REPO_ROOT) + "/", "")


def is_winner(note: Any) -> bool:
    return isinstance(note, str) and note.startswith(WINNER_PREFIXES)


# --- the Node parity, from scripts/w6_parity_compare.py's summary -----------------------------


def node_parity(summary: dict[str, Any]) -> dict[str, Any]:
    q8_run, fp32_run, torch = summary["node"]["q8"], summary["node"]["fp32"], summary["torch"]
    comparisons = [{k: v for k, v in c.items() if k != "per_text"} for c in summary["comparisons"]]
    by_name = {c["comparison"]: c for c in comparisons}
    q8 = by_name["Node q8 batch vs PyTorch CPU batch"]
    fp32 = by_name["Node fp32 batch vs PyTorch CPU batch"]
    pad = by_name["Node q8 batch vs Node q8 single (padding effect)"]
    v, tv = q8_run["versions"], torch["versions"]
    return {
        "runtime": (
            f"Transformers.js {v['@huggingface/transformers']} on Node {v['node']} with "
            f"onnxruntime-node {v['onnxruntime-node']}, device {q8_run['device']}"
        ),
        "reference": (
            f"PyTorch {tv['torch']} on {torch['device']}, sentence-transformers "
            f"{tv['sentence_transformers']}, transformers {tv['transformers']}, "
            f"CPython {tv['python']}"
        ),
        "texts": q8["n"],
        "texts_file": "pipeline/data/runs/" + summary["texts_sha256_source"],
        "dtype_to_file": {"fp32": fp32_run["fileLoaded"], "q8": q8_run["fileLoaded"]},
        "target_min_cos": TARGET,
        "fp32_min_cos": fp32["min"],
        "fp32_meets_target": bool(fp32[f"meets_{TARGET}"]),
        "int8_min_cos": q8["min"],
        "int8_median_cos": q8["median"],
        "int8_mean_cos": q8["mean"],
        "int8_texts_at_or_above_target": q8[f"at_or_above_{TARGET}"],
        "int8_meets_target": bool(q8[f"meets_{TARGET}"]),
        "int8_worst_text": summary.get("worst_texts", {}).get(q8["comparison"]),
        "int8_batch_vs_single_min_cos": pad["min"],
        "comparisons": comparisons,
        "token_ids_identical_texts": {
            d: summary["token_ids"][d]["identical_texts"] for d in summary["token_ids"]
        },
        "latency_ms_single_decision": {
            "node_q8": q8_run["timed40Stats"],
            "node_fp32": fp32_run["timed40Stats"],
            "pytorch_cpu_median": torch["singleMsMedian"],
        },
        "load_ms": {"q8": q8_run["loadMs"], "fp32": fp32_run["loadMs"]},
        "details": "pipeline/docs/parity.md",
    }


def node_parity_note(p: dict[str, Any], onnxruntime_int8_min: float | None) -> str:
    lat = p["latency_ms_single_decision"]
    same = (
        f" (Python onnxruntime on the same export: {onnxruntime_int8_min:.5f})"
        if onnxruntime_int8_min is not None
        else ""
    )
    return (
        f"{NODE_NOTE_PREFIX} (relay W6): {p['runtime']} against {p['reference']} on the same "
        f"{p['texts']} fixture texts: fp32 ({p['dtype_to_file']['fp32']}) min cosine "
        f"{p['fp32_min_cos']:.8f}, meets {TARGET}; int8 (dtype q8, {p['dtype_to_file']['q8']}) "
        f"min cosine {p['int8_min_cos']:.8f}, median {p['int8_median_cos']:.8f}, mean "
        f"{p['int8_mean_cos']:.8f}, {p['int8_texts_at_or_above_target']} of {p['texts']} texts "
        f"at or above {TARGET}, the same gap{same}, so the loss is the dynamic int8 "
        f"quantisation, not the JavaScript runtime; token ids identical on "
        f"{p['token_ids_identical_texts']['q8']}/{p['texts']} texts; int8 vectors depend on the "
        f"batch shape (a text alone against the same text in a padded batch of {p['texts']}: "
        f"self-cosine min {p['int8_batch_vs_single_min_cos']:.4f}; fp32 1.0); "
        f"{lat['node_q8']['n']} single decisions in Node: q8 median {lat['node_q8']['median']:.2f} "
        f"ms (p90 {lat['node_q8']['p90']:.2f}), fp32 {lat['node_fp32']['median']:.2f} ms, PyTorch "
        f"CPU {lat['pytorch_cpu_median']:.2f} ms; docs/parity.md"
    )


def site_note(board: dict[str, Any], cal_b1: dict[str, Any] | None) -> str:
    params = ""
    if cal_b1:
        params = (
            f" (temperature {cal_b1['temperature']:.4f}, none score {cal_b1['none_score']:.2f}, "
            f"file cut-off {cal_b1['file_cutoff']:.4f}, suggest cut-off "
            f"{cal_b1['suggest_cutoff']:.4f})"
        )
    lead = ""
    diff = board.get("b2_minus_b1")
    n = (board.get("examples") or {}).get("exam", {}).get("total")
    if diff and n:
        mc, acc = diff["mcnemar"], diff["accuracy_diff"]
        lead = (
            f": B2's lead is {mc['b_right_a_wrong'] - mc['a_right_b_wrong']} of {n} exam "
            f"decisions, inside the 90% bootstrap interval {acc['interval_90']} of the difference"
        )
    size = (board.get("int8_exam_effect") or {}).get("size_mb_int8")
    hosted = f" a hosted {size:.1f} MB model file" if size else " a hosted model file"
    return (
        f"{SITE_NOTE_PREFIX} the demo keeps B1, the untrained base encoder, with B1's toy "
        f"calibration from this run{params} in web/src/sorter/calibration.json; decision of "
        f"2026-10-16 in docs/DECISIONS.md{lead}, and a shipped student needs{hosted}; wiring B2 "
        "through the manifest is BDL-4's"
    )


# --- fixes --------------------------------------------------------------------------------------


def apply_fixes(board: dict[str, Any], paths: config.Paths) -> list[str]:
    done: list[str] = []
    if board.get("label") != "toy scale":
        board["label"] = "toy scale"
        done.append('label set to "toy scale"')

    notes: list[Any] = []
    for note in board.get("notes", []):
        if isinstance(note, dict) and len(note) == 1:
            key, value = next(iter(note.items()))
            if key not in board:
                board[key] = value
                done.append(f"moved the {key} object out of notes to a top-level key")
            else:
                done.append(f"dropped a {key} object from notes (top-level key already present)")
        elif isinstance(note, str):
            notes.append(relative(note))
        else:
            done.append(f"dropped a non-text note: {json.dumps(note)[:60]}")

    winner = notes.pop() if notes and is_winner(notes[-1]) else None
    notes = [n for n in notes if not n.startswith((NODE_NOTE_PREFIX, SITE_NOTE_PREFIX))]

    summary = read_json(paths.runs_dir / "parity-summary.json")
    if summary:
        parity = node_parity(summary)
        export = board.setdefault("export", {})
        if export.get("parity_node") != parity:
            export["parity_node"] = parity
            done.append("export.parity_node written from runs/parity-summary.json")
        ort_int8 = ((export.get("parity") or {}).get("int8") or {}).get("min_cos")
        note = node_parity_note(parity, ort_int8)
        anchor = next((i for i, n in enumerate(notes) if n.startswith("int8 exam effect")), None)
        notes.insert(anchor + 1 if anchor is not None else len(notes), note)
    else:
        done.append("NOT FOUND: runs/parity-summary.json, no Node parity added")

    notes.append(site_note(board, read_json(paths.models_dir / "calibration-b1.json")))
    if winner is not None:
        notes.append(winner)
    if notes != board.get("notes"):
        done.append("notes rewritten (text only, Node parity and site notes, winner last)")
    board["notes"] = notes
    return done


# --- checks -------------------------------------------------------------------------------------


def check(board: dict[str, Any], paths: config.Paths, run_id: str) -> list[str]:
    bad: list[str] = []

    def need(cond: bool, what: str) -> None:
        if not cond:
            bad.append(what)

    need(board.get("label") == "toy scale", 'label is not "toy scale"')
    need(board.get("run_id") == run_id, f"run_id is not {run_id}")
    need(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(board.get("date")))), "date is not YYYY-MM-DD")
    need(bool(board.get("base_model")), "base_model missing")
    exam_hash = str(board.get("exam_hash", ""))
    need(bool(re.fullmatch(r"[0-9a-f]{64}", exam_hash)), "exam_hash is not a sha256 hex digest")
    seal = paths.splits_dir / "exam.sha256"
    if seal.is_file():
        need(seal.read_text().split()[0] == exam_hash, "exam_hash differs from splits/exam.sha256")
    else:
        bad.append("NOT CHECKED: splits/exam.sha256 is missing")

    sorters = board.get("sorters") or []
    ids = [s.get("id") for s in sorters]
    need("B0" in ids and "B1" in ids and "B2" in ids, f"sorters must include B0, B1, B2: {ids}")
    expected = [i for i in EXPECTED_ORDER if i in ids]
    need(ids == expected, f"sorter order is {ids}, expected {expected}")
    for s in sorters:
        need(tuple(s.keys()) == CONTRACT_KEYS, f"{s.get('id')} does not carry exactly the 14 keys")
        for k in METRIC_KEYS:
            v = s.get(k)
            ok = isinstance(v, int | float) and v == v and v >= 0
            if ok and k in RATIO_KEYS:
                ok = v <= 1
            need(ok, f"{s.get('id')}.{k} = {v!r} is out of range")

    exam = read_json(paths.runs_dir / f"exam-{run_id}.json") or {}
    by_id = {r["id"]: r for r in exam.get("sorters", [])}
    b1b = read_json(paths.runs_dir / f"b1b-{run_id}.json") or {}
    b1b_rec = (b1b.get("exam") or {}).get("B1b_calibrated")  # the board entry is the calibrated run
    if b1b_rec is not None:
        by_id["B1b"] = b1b_rec
    for s in sorters:
        rec = by_id.get(s["id"])
        if rec is None:
            bad.append(f"NOT CHECKED: no exam record for {s['id']} under data/runs")
            continue
        for k in METRIC_KEYS:
            if abs(float(rec[k]) - float(s[k])) > 1e-6:
                bad.append(f"{s['id']}.{k} {s[k]} differs from the exam run's {rec[k]}")

    people, chats, examples = board.get("people"), board.get("chats"), board.get("examples")
    need(isinstance(people, dict) and isinstance(chats, dict), "people / chats counts missing")
    need(isinstance(examples, dict), "examples counts missing")
    if isinstance(people, dict) and isinstance(chats, dict) and isinstance(examples, dict):
        splits = config.SPLIT_NAMES
        need(sum(people[s] for s in splits) == people["validated"], "people per split do not sum")
        need(sum(chats[s] for s in splits) == chats["validated"], "chats per split do not sum")
        for s in splits:
            ex = examples[s]
            need(ex["total"] == chats[s], f"examples.{s}.total differs from chats.{s}")
            need(
                ex["bundle"] + ex["loose"] + ex["none"] == ex["total"],
                f"examples.{s} answer types do not sum",
            )

    cal = board.get("calibration") or {}
    need("method" in cal, "calibration.method missing")
    for sid in [i for i in ids if i != "B0"]:
        entry = cal.get(sid)
        keys = ("temperature", "none_score", "file_cutoff", "suggest_cutoff", "bootstrap")
        need(isinstance(entry, dict) and all(k in entry for k in keys), f"calibration.{sid} gaps")

    teacher = board.get("teacher") or {}
    for k in ("model", "licence", "prompt_version", "seed", "totals"):
        need(k in teacher and teacher[k] is not None, f"teacher.{k} missing")
    student = board.get("student") or {}
    need(student.get("base_model") == board.get("base_model"), "student.base_model != base_model")

    export = board.get("export") or {}
    parity = export.get("parity") or {}
    need("fp32" in parity and "int8" in parity, "export.parity (PyTorch vs onnxruntime) missing")
    if parity:
        need(parity["fp32"]["min_cos"] >= TARGET, "export.parity.fp32 is under the 0.999 bar")
        need(
            export.get("int8_meets_target") == (parity["int8"]["min_cos"] >= TARGET),
            "export.int8_meets_target disagrees with the int8 min cosine",
        )
    need("parity_node" in export, "export.parity_node (Transformers.js in Node) missing")
    need("follow_up_toy" in board, "follow_up_toy block missing")

    notes = board.get("notes") or []
    need(all(isinstance(n, str) for n in notes), "notes holds a non-text entry")
    text = [n for n in notes if isinstance(n, str)]
    need(any("onnxruntime" in n and "int8" in n for n in text), "no onnxruntime int8 parity note")
    need(any(n.startswith(NODE_NOTE_PREFIX) for n in text), "no Transformers.js (Node) note")
    need(any(n.startswith("follow-up toy") for n in text), "no follow-up toy note")
    need(any(n.startswith(SITE_NOTE_PREFIX) for n in text), "no site note")
    need(any(n.startswith("B1b") for n in text) == ("B1b" in ids), "B1b notes and sorter differ")
    need(bool(text) and is_winner(text[-1]), "the winner line is not the last note")
    need(not any(str(config.REPO_ROOT) in n for n in text), "a note holds an absolute path")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--data-root", default=None)
    ap.add_argument("--board-dir", default=str(config.SCOREBOARD_RUNS_DIR))
    ap.add_argument("--check", action="store_true", help="check only, write nothing")
    args = ap.parse_args()

    paths = config.paths_for(args.data_root)
    board_path = Path(args.board_dir) / f"{args.run_id}.json"
    try:
        board = read_json(board_path)
    except json.JSONDecodeError as exc:
        print(f"board finalise: {board_path} is not valid JSON: {exc}")
        return 1
    if board is None:
        print(f"board finalise: no board at {board_path}")
        return 2

    before = json.dumps(board, sort_keys=True)
    done = [] if args.check else apply_fixes(board, paths)
    problems = check(board, paths, args.run_id)
    changed = json.dumps(board, sort_keys=True) != before
    if changed and not args.check:
        write_json(board_path, board)

    print(render_table(board["sorters"]))
    print(
        f"\n{board_path.name}: {len(board['sorters'])} sorters, {len(board['notes'])} notes, "
        f"top-level keys {list(board)}"
    )
    for d in done:
        print(f"- fixed: {d}")
    for p in problems:
        print(f"- PROBLEM: {p}")
    status = "written" if changed and not args.check else "unchanged"
    print(f"board finalise: {status}; {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
