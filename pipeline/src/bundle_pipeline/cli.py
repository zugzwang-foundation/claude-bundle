"""Command-line entry point: `bundle-pipeline <subcommand> [options]`.

Each subcommand lives in its own module and exposes
`main(args: argparse.Namespace) -> int`. Modules are imported lazily so that
`--help` never loads torch. A module that is still a stub raises
NotImplementedError with a clear message; the CLI turns that into exit code 3.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from bundle_pipeline import config

SUBCOMMANDS: dict[str, str] = {
    "generate": "ask the teacher server for people and their chats -> data/raw/people/",
    "validate": "schema, deduplication and label sanity -> data/validated/people.jsonl",
    "split": "deterministic per-person 80/10/10 split -> data/splits/, writes exam.sha256",
    "tasks": "turn each chat into a DecisionExample -> data/tasks/",
    "baseline": "B0 (always leave) and B1 (base encoder, default weights) on a split",
    "train": "train the student (B2) on the lessons split -> data/models/",
    "calibrate": "temperature scaling and cut-offs on practice -> calibration.json",
    "exam": "sit the sealed exam (checks exam.sha256) and report metrics",
    "export": "export the student to ONNX int8 and check parity with the browser runtime",
    "scoreboard": "write scoreboard/runs/<run-id>.json at the repository root",
    "followup-toy": "toy second question: is this chat a follow-up to that one? (cosine on pairs)",
    "smoke": "check the runtime: Python, packages, device, paths, fixture",
}


def _add_common(p: argparse.ArgumentParser, paths: config.Paths) -> None:
    p.add_argument("--seed", type=int, default=config.DEFAULT_SEED, help="random seed")
    p.add_argument("--verbose", "-v", action="store_true", help="more logging")
    p.add_argument(
        "--data-root",
        default=str(paths.data_dir),
        help="data tree for every default path (env BUNDLE_DATA_ROOT); e.g. data/smoke",
    )


def prescan_data_root(argv: Sequence[str]) -> Path | None:
    """Find --data-root before parsing, so the defaults below can be built from it."""
    args = list(argv)
    for i, a in enumerate(args):
        if a == "--data-root" and i + 1 < len(args):
            return Path(args[i + 1]).expanduser().resolve()
        if a.startswith("--data-root="):
            return Path(a.split("=", 1)[1]).expanduser().resolve()
    return None


def build_parser(data_root: str | Path | None = None) -> argparse.ArgumentParser:
    P = config.paths_for(data_root)  # noqa: N806 - short name, used on every line below
    parser = argparse.ArgumentParser(
        prog="bundle-pipeline",
        description="Bundle's learning loop: teacher -> tasks -> student -> exam -> board.",
    )
    sub = parser.add_subparsers(dest="command", metavar="<subcommand>")
    sub.required = True

    p = sub.add_parser("generate", help=SUBCOMMANDS["generate"])
    _add_common(p, P)
    p.add_argument("--people", type=int, default=24, help="how many people to generate")
    p.add_argument(
        "--chats-per-person",
        "--chats",
        dest="chats_per_person",
        type=int,
        default=60,
        help="target chats per person (3-5 threads of 8-15 plus 6-10 loose)",
    )
    p.add_argument("--teacher-url", default=config.TEACHER_URL)
    p.add_argument("--model", default=config.TEACHER_MODEL)
    p.add_argument("--out", default=str(P.raw_people_dir), help="one JSON per person")
    p.add_argument("--workers", type=int, default=1, help="people generated in parallel")
    p.add_argument(
        "--time-budget-min",
        type=float,
        default=60.0,
        help="stop starting new people after this many minutes",
    )
    p.add_argument(
        "--grace-min",
        type=float,
        default=5.0,
        help="minutes a person already in flight may run past the budget",
    )
    p.add_argument("--log", default=str(P.generate_log))

    p = sub.add_parser("validate", help=SUBCOMMANDS["validate"])
    _add_common(p, P)
    p.add_argument("--raw", default=str(P.raw_people_dir))
    p.add_argument("--out", default=str(P.validated_people))
    p.add_argument("--report", default=None, help="default: report.json next to --out")

    p = sub.add_parser("split", help=SUBCOMMANDS["split"])
    _add_common(p, P)
    p.add_argument("--people", default=str(P.validated_people))
    p.add_argument("--out-dir", default=str(P.splits_dir))
    p.add_argument("--salt", default="bundle-bdl3", help="mixed into sha256(person_id + salt)")
    p.add_argument("--force", action="store_true", help="allow the sealed exam to change")

    p = sub.add_parser("tasks", help=SUBCOMMANDS["tasks"])
    _add_common(p, P)
    p.add_argument("--splits-dir", default=str(P.splits_dir))
    p.add_argument("--out-dir", default=str(P.tasks_dir))

    p = sub.add_parser("baseline", help=SUBCOMMANDS["baseline"])
    _add_common(p, P)
    p.add_argument("--split", choices=config.SPLIT_NAMES, default="practice")
    p.add_argument("--tasks", default=None, help="a tasks jsonl (overrides --split)")
    p.add_argument("--encoder", default=config.BASE_ENCODER)
    p.add_argument("--calibration", default=None, help="calibration.json for B1 (default: none)")
    p.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    p.add_argument("--out-dir", default=str(P.runs_dir))

    p = sub.add_parser("train", help=SUBCOMMANDS["train"])
    _add_common(p, P)
    p.add_argument("--tasks", default=str(P.tasks_path("lessons")))
    p.add_argument("--encoder", default=config.BASE_ENCODER)
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--lr", type=float, default=2e-5)
    p.add_argument("--max-seq-length", type=int, default=128)
    p.add_argument("--max-pairs", type=int, default=None, help="cap the pairs (quick runs)")
    p.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    p.add_argument("--out", default=str(P.models_dir / "student-v0"))

    p = sub.add_parser("calibrate", help=SUBCOMMANDS["calibrate"])
    _add_common(p, P)
    p.add_argument("--model", default=str(P.models_dir / "student-v0"))
    p.add_argument("--tasks", default=str(P.tasks_path("practice")))
    p.add_argument("--min-support", type=int, default=5, help="decisions a cut-off must cover")
    p.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    p.add_argument("--out", default=str(P.calibration_json))
    p.add_argument("--web-out", default=str(config.WEB_CALIBRATION_JSON))
    p.add_argument("--no-web", action="store_true", help="do not write the web copy")

    p = sub.add_parser("exam", help=SUBCOMMANDS["exam"])
    _add_common(p, P)
    p.add_argument("--tasks", default=str(P.tasks_path("exam")))
    p.add_argument("--split-file", default=str(P.split_path("exam")))
    p.add_argument("--hash-file", default=str(P.exam_sha256))
    p.add_argument("--allow-unsealed", action="store_true", help="skip the exam.sha256 check")
    p.add_argument("--encoder", default=config.BASE_ENCODER, help="B1 base encoder")
    p.add_argument("--b1-calibration", default=None, help="calibration.json for B1 (optional)")
    p.add_argument("--model", default=str(P.models_dir / "student-v0"), help="B2 student")
    p.add_argument("--calibration", default=str(P.calibration_json), help="for B2")
    p.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    p.add_argument("--run-id", default=None, help="default <date>-toy-v0")
    p.add_argument("--out-dir", default=str(P.runs_dir))

    p = sub.add_parser("export", help=SUBCOMMANDS["export"])
    _add_common(p, P)
    p.add_argument("--model", default=str(P.models_dir / "student-v0"))
    p.add_argument("--student-id", default="student-v0")
    p.add_argument("--base-model", default=config.BASE_ENCODER)
    p.add_argument("--run-id", default=None, help="default <date>-toy-v0")
    p.add_argument("--per-tensor", action="store_true", help="per-tensor int8 (smaller, worse)")
    p.add_argument("--out", default=str(P.models_dir / "student-v0-onnx"))

    p = sub.add_parser("scoreboard", help=SUBCOMMANDS["scoreboard"])
    _add_common(p, P)
    p.add_argument("--runs-dir", default=str(P.runs_dir))
    p.add_argument("--source", default=None, help="an exam-<run-id>.json (default: newest)")
    p.add_argument("--run-id", default=None)
    p.add_argument("--notes", action="append", default=None, help="extra note (repeatable)")
    p.add_argument("--out-dir", default=str(config.SCOREBOARD_RUNS_DIR))

    p = sub.add_parser("followup-toy", help=SUBCOMMANDS["followup-toy"])
    _add_common(p, P)
    p.add_argument("--exam", default=str(P.split_path("exam")), help="people of the exam split")
    p.add_argument(
        "--practice", default=str(P.split_path("practice")), help="people the threshold is fit on"
    )
    p.add_argument("--encoder", default=config.BASE_ENCODER, help="the base encoder")
    p.add_argument(
        "--student",
        default=str(P.models_dir / "student-v0"),
        help="the trained student (skipped when the path does not exist)",
    )
    p.add_argument("--max-pairs", type=int, default=2000, help="balanced cap per split")
    p.add_argument("--resamples", type=int, default=200, help="bootstrap resamples")
    p.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    p.add_argument("--out", default=str(P.runs_dir / "followup-toy.json"))

    p = sub.add_parser("smoke", help=SUBCOMMANDS["smoke"])
    _add_common(p, P)
    p.add_argument("--encoder", action="store_true", help="also load the base encoder")

    return parser


def _resolve(command: str) -> Callable[[argparse.Namespace], int]:
    module = importlib.import_module(f"bundle_pipeline.{command.replace('-', '_')}")
    fn = getattr(module, "main", None)
    if fn is None:
        raise SystemExit(f"bundle_pipeline.{command} has no main(args) function")
    return fn


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser(prescan_data_root(raw_argv))
    args = parser.parse_args(raw_argv)
    try:
        return int(_resolve(args.command)(args) or 0)
    except NotImplementedError as e:
        print(f"bundle-pipeline {args.command}: not implemented yet: {e}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
