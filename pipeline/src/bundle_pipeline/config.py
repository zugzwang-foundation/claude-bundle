"""Paths, defaults and environment for the Bundle pipeline.

Everything here is a plain constant or a tiny function; nothing imports torch.
Paths resolve relative to the pipeline/ directory (the parent of src/), which
is what `uv sync` installs in editable mode. Override with environment
variables when running elsewhere.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# --- Locations ---------------------------------------------------------------


def _find_pipeline_root() -> Path:
    """pipeline/ is two levels above this package in the src layout."""
    env = os.environ.get("BUNDLE_PIPELINE_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    here = Path(__file__).resolve()
    candidate = here.parents[2]  # src/bundle_pipeline/config.py -> pipeline/
    if (candidate / "pyproject.toml").is_file():
        return candidate
    return Path.cwd()


PIPELINE_ROOT: Path = _find_pipeline_root()
REPO_ROOT: Path = PIPELINE_ROOT.parent


def data_dir_from_env(default: Path | None = None) -> Path:
    """The data root: BUNDLE_DATA_ROOT, else BUNDLE_DATA_DIR, else pipeline/data.

    Every subcommand also takes ``--data-root``, which wins over both variables;
    a smoke run uses ``--data-root data/smoke`` so the real run is not disturbed.
    """
    env = os.environ.get("BUNDLE_DATA_ROOT") or os.environ.get("BUNDLE_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return (default or PIPELINE_ROOT / "data").resolve()


@dataclass(frozen=True)
class Paths:
    """Every file the stages read or write under one data root."""

    data_dir: Path

    @property
    def raw_people_dir(self) -> Path:
        return self.data_dir / "raw" / "people"

    @property
    def validated_people(self) -> Path:
        return self.data_dir / "validated" / "people.jsonl"

    @property
    def splits_dir(self) -> Path:
        return self.data_dir / "splits"

    @property
    def exam_sha256(self) -> Path:
        return self.splits_dir / "exam.sha256"

    @property
    def tasks_dir(self) -> Path:
        return self.data_dir / "tasks"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def generate_log(self) -> Path:
        return self.data_dir / "generate.log"

    @property
    def calibration_json(self) -> Path:
        return self.models_dir / "calibration.json"

    def split_path(self, name: str) -> Path:
        return self.splits_dir / f"{name}.jsonl"

    def tasks_path(self, name: str) -> Path:
        return self.tasks_dir / f"{name}.jsonl"

    def ensure_dirs(self) -> None:
        for d in (
            self.raw_people_dir,
            self.validated_people.parent,
            self.splits_dir,
            self.tasks_dir,
            self.models_dir,
            self.runs_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)


def paths_for(data_dir: str | Path | None = None) -> Paths:
    """Paths under ``data_dir`` (default: the environment's data root)."""
    if data_dir is None:
        return Paths(data_dir_from_env())
    return Paths(Path(data_dir).expanduser().resolve())


DATA_DIR: Path = data_dir_from_env()
RAW_PEOPLE_DIR: Path = DATA_DIR / "raw" / "people"
VALIDATED_PEOPLE: Path = DATA_DIR / "validated" / "people.jsonl"
SPLITS_DIR: Path = DATA_DIR / "splits"
EXAM_SHA256: Path = SPLITS_DIR / "exam.sha256"
TASKS_DIR: Path = DATA_DIR / "tasks"
MODELS_DIR: Path = DATA_DIR / "models"
RUNS_DIR: Path = DATA_DIR / "runs"

SPLIT_NAMES: tuple[str, str, str] = ("lessons", "practice", "exam")
SPLIT_FRACTIONS: dict[str, float] = {"lessons": 0.8, "practice": 0.1, "exam": 0.1}
DEFAULT_SEED: int = 3  # BDL-3


def split_path(name: str) -> Path:
    return SPLITS_DIR / f"{name}.jsonl"


def tasks_path(name: str) -> Path:
    return TASKS_DIR / f"{name}.jsonl"


# Outputs that live outside pipeline/ (contract with the web app and the board).
SCOREBOARD_RUNS_DIR: Path = REPO_ROOT / "scoreboard" / "runs"
WEB_CALIBRATION_JSON: Path = REPO_ROOT / "web" / "src" / "sorter" / "calibration.json"
CALIBRATION_JSON: Path = MODELS_DIR / "calibration.json"

# --- Teacher (OpenAI-compatible chat completions) ---------------------------

TEACHER_URL: str = os.environ.get("BUNDLE_TEACHER_URL", "http://127.0.0.1:8081/v1")
TEACHER_MODEL: str = os.environ.get("BUNDLE_TEACHER_MODEL", "local")
TEACHER_TIMEOUT_S: float = float(os.environ.get("BUNDLE_TEACHER_TIMEOUT", "180"))
TEACHER_MAX_RETRIES: int = 3
PROMPT_VERSION: str = "v0.2"
"""Must match prompts.PROMPT_VERSION; prompts.py is the source of truth."""

# --- Encoder -----------------------------------------------------------------

BASE_ENCODER: str = "sentence-transformers/all-MiniLM-L6-v2"
"""Licence Apache-2.0: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
(model-card licence tag read via the Hub API on 2026-10-16)."""
BROWSER_ENCODER_ID: str = "Xenova/all-MiniLM-L6-v2"
"""ONNX copy for Transformers.js; licence tag Apache-2.0 (Hub API, 2026-10-16)."""
EMBEDDING_DIM: int = 384
MAX_BUNDLE_EXAMPLES: int = 8

# --- Sorter defaults (before calibration) -----------------------------------


@dataclass(frozen=True)
class SorterParams:
    temperature: float = 0.05
    none_score: float = 0.30
    file_cutoff: float = 0.85
    suggest_cutoff: float = 0.55


DEFAULT_SORTER = SorterParams()

# --- Housekeeping -----------------------------------------------------------


def ensure_dirs(data_dir: str | Path | None = None) -> None:
    """Create the data tree (gitignored) so every stage can write."""
    paths_for(data_dir or DATA_DIR).ensure_dirs()


def hf_cache_dir() -> Path:
    """Where Hugging Face downloads land; report its size, disk is tight."""
    env = os.environ.get("HF_HUB_CACHE") or os.environ.get("HF_HOME")
    if env:
        p = Path(env).expanduser()
        return p if p.name == "hub" else p / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"
