"""Read and write the pipeline's JSON and JSONL files.

Every stage after `generate` passes people and examples around as JSONL (one
pydantic model per line). Keeping the helpers here means every module writes
files the same way: UTF-8, one `model_dump_json()` per line, written to a
temporary file and renamed so a half-written file never looks finished.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable, Iterator
from pathlib import Path

from pydantic import BaseModel

from bundle_pipeline.schema import DecisionExample, Person


def read_jsonl[T: BaseModel](path: Path, model: type[T]) -> list[T]:
    """Load every non-empty line of `path` as `model`."""
    items: list[T] = []
    with path.open("r", encoding="utf-8") as fh:
        for n, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(model.model_validate_json(line))
            except ValueError as e:
                raise ValueError(f"{path}:{n}: {e}") from e
    return items


def iter_jsonl[T: BaseModel](path: Path, model: type[T]) -> Iterator[T]:
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield model.model_validate_json(line)


def jsonl_text(items: Iterable[BaseModel]) -> str:
    """The exact bytes a JSONL file of these items will hold (used for hashing)."""
    return "".join(item.model_dump_json() + "\n" for item in items)


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_jsonl(path: Path, items: Iterable[BaseModel]) -> int:
    """Write items as JSONL; returns how many lines were written."""
    lines = [item.model_dump_json() for item in items]
    write_text_atomic(path, "".join(line + "\n" for line in lines))
    return len(lines)


def write_json(path: Path, data: object, indent: int = 2) -> None:
    write_text_atomic(path, json.dumps(data, indent=indent, ensure_ascii=False) + "\n")


def read_people(path: Path) -> list[Person]:
    return read_jsonl(path, Person)


def write_people(path: Path, people: Iterable[Person]) -> int:
    return write_jsonl(path, people)


def read_examples(path: Path) -> list[DecisionExample]:
    return read_jsonl(path, DecisionExample)


def write_examples(path: Path, examples: Iterable[DecisionExample]) -> int:
    return write_jsonl(path, examples)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


__all__ = [
    "iter_jsonl",
    "jsonl_text",
    "read_examples",
    "read_jsonl",
    "read_people",
    "sha256_file",
    "sha256_text",
    "write_examples",
    "write_json",
    "write_jsonl",
    "write_people",
    "write_text_atomic",
]
