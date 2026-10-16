"""The console script exposes every subcommand and stubs fail loudly, not silently."""

from __future__ import annotations

import pytest

from bundle_pipeline.cli import SUBCOMMANDS, build_parser, main

EXPECTED = {
    "generate",
    "validate",
    "split",
    "tasks",
    "baseline",
    "train",
    "calibrate",
    "exam",
    "export",
    "scoreboard",
    "smoke",
    "followup-toy",
}


def test_all_subcommands_are_registered() -> None:
    assert set(SUBCOMMANDS) == EXPECTED
    parser = build_parser()
    sub = next(a for a in parser._actions if a.dest == "command")
    assert set(sub.choices) == EXPECTED  # type: ignore[union-attr]


def test_help_does_not_import_torch(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    sys.modules.pop("torch", None)
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0
    assert "torch" not in sys.modules


def test_stub_returns_exit_code_3(capsys: pytest.CaptureFixture[str]) -> None:
    import importlib

    module = importlib.import_module("bundle_pipeline.train")
    if "stub" not in (module.__doc__ or ""):
        pytest.skip("train is implemented")
    assert main(["train"]) == 3
    assert "not implemented yet" in capsys.readouterr().err


def test_data_root_rebuilds_every_default(tmp_path) -> None:
    from pathlib import Path

    from bundle_pipeline.cli import prescan_data_root

    root = tmp_path / "smoke"
    assert prescan_data_root(["generate", "--data-root", str(root)]) == root.resolve()
    assert prescan_data_root(["tasks", f"--data-root={root}"]) == root.resolve()
    assert prescan_data_root(["tasks"]) is None

    parser = build_parser(root)
    g = parser.parse_args(["generate", "--data-root", str(root)])
    assert Path(g.out) == root / "raw" / "people"
    assert Path(g.log) == root / "generate.log"
    v = parser.parse_args(["validate"])
    assert Path(v.raw) == root / "raw" / "people"
    assert Path(v.out) == root / "validated" / "people.jsonl"
    s = parser.parse_args(["split"])
    assert Path(s.out_dir) == root / "splits"
    t = parser.parse_args(["tasks"])
    assert Path(t.splits_dir) == root / "splits"
    assert Path(t.out_dir) == root / "tasks"
    b = parser.parse_args(["baseline"])
    assert Path(b.out_dir) == root / "runs"
    e = parser.parse_args(["exam"])
    assert Path(e.hash_file) == root / "splits" / "exam.sha256"
    assert Path(e.tasks) == root / "tasks" / "exam.jsonl"
    x = parser.parse_args(["export"])
    assert Path(x.model) == root / "models" / "student-v0"
    c = parser.parse_args(["calibrate"])
    assert Path(c.out) == root / "models" / "calibration.json"
    f = parser.parse_args(["followup-toy"])
    assert Path(f.exam) == root / "splits" / "exam.jsonl"
    assert Path(f.out) == root / "runs" / "followup-toy.json"


def test_data_root_env_is_honoured(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from bundle_pipeline import config

    monkeypatch.setenv("BUNDLE_DATA_ROOT", str(tmp_path / "from-env"))
    assert config.paths_for().data_dir == (tmp_path / "from-env").resolve()
    monkeypatch.delenv("BUNDLE_DATA_ROOT")
    monkeypatch.setenv("BUNDLE_DATA_DIR", str(tmp_path / "legacy"))
    assert config.paths_for().data_dir == (tmp_path / "legacy").resolve()
