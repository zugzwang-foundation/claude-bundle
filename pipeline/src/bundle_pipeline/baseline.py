"""`bundle-pipeline baseline`: B0 (always leave) and B1 (base encoder, untrained) on a split.

Runs both sorters on tasks/<split>.jsonl (practice by default; the exam is
reserved for `bundle-pipeline exam`), prints the metrics table and writes
runs/baseline-<split>.json. B1 uses the default sorter parameters unless
``--calibration`` points at a calibration.json.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from bundle_pipeline import config
from bundle_pipeline.exam import load_params, render_table, run_encoder, run_leave
from bundle_pipeline.store import read_examples, write_json


def main(args: argparse.Namespace) -> int:
    from bundle_pipeline.encoder import Encoder  # noqa: PLC0415

    paths = config.paths_for(getattr(args, "data_root", None))
    tasks_file = Path(args.tasks) if args.tasks else paths.tasks_path(args.split)
    if not tasks_file.is_file():
        print(f"baseline: no tasks file at {tasks_file}; run `bundle-pipeline tasks` first")
        return 2
    examples = read_examples(tasks_file)
    print(f"baseline: {len(examples)} examples from {tasks_file}")
    runs = [run_leave(examples)]
    print(f"  B0 done in {runs[-1].seconds:.1f}s")
    encoder = Encoder(args.encoder, device=args.device)
    params = load_params(args.calibration)
    runs.append(run_encoder("B1", "base encoder, untrained", encoder, examples, params))
    print(f"  B1 done in {runs[-1].seconds:.1f}s ({encoder.name} on {encoder.device})")
    records = [r.record(examples) for r in runs]
    out = Path(args.out_dir) / f"baseline-{tasks_file.stem}.json"
    write_json(
        out,
        {
            "date": datetime.now(UTC).strftime("%Y-%m-%d"),
            "tasks_file": str(tasks_file),
            "base_model": args.encoder,
            "sorters": records,
        },
    )
    print(render_table(records))
    print(f"baseline: wrote {out}")
    return 0
