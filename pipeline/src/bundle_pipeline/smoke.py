"""`bundle-pipeline smoke`: prove the runtime works before anything heavy runs.

Prints the interpreter, the pinned packages, the torch device, the data tree
and the fixture. With --encoder it also loads the base sentence encoder and
embeds two sentences, which downloads ~90 MB on first use (disk is tight).
"""

from __future__ import annotations

import argparse
import importlib.metadata as md
import json
import platform
import sys
from pathlib import Path

from bundle_pipeline import config
from bundle_pipeline.schema import Person

PACKAGES = (
    "pydantic",
    "httpx",
    "numpy",
    "torch",
    "sentence-transformers",
    "scikit-learn",
    "onnx",
    "onnxruntime",
    "transformers",
    "tokenizers",
)


def _dir_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    # lstat: the hub cache is symlinks onto blobs, which must count once
    return sum(f.lstat().st_size for f in path.rglob("*") if f.is_file()) / 1e6


def main(args: argparse.Namespace) -> int:
    ok = True
    print(f"python      {platform.python_version()}  ({sys.executable})")
    if sys.version_info[:2] != (3, 14):
        print("  WARNING: expected CPython 3.14 from pipeline/.python-version")
        ok = False
    for name in PACKAGES:
        try:
            print(f"{name:<22} {md.version(name)}")
        except md.PackageNotFoundError:
            print(f"{name:<22} MISSING")
            ok = False

    import torch  # noqa: PLC0415 - heavy import on purpose, only in smoke

    mps = torch.backends.mps.is_available()
    print(f"torch device           {'mps' if mps else 'cpu'} (mps available: {mps})")

    import onnxruntime as ort  # noqa: PLC0415

    print(f"onnxruntime providers  {ort.get_available_providers()}")

    print(f"pipeline root          {config.PIPELINE_ROOT}")
    print(f"data dir               {config.DATA_DIR}")
    print(f"teacher url            {config.TEACHER_URL}")
    cache = config.hf_cache_dir()
    print(f"hf cache               {cache}  ({_dir_size_mb(cache):.0f} MB)")

    fixture = config.PIPELINE_ROOT / "tests" / "fixtures" / "people.json"
    if fixture.is_file():
        people = [Person.model_validate(p) for p in json.loads(fixture.read_text())]
        n_chats = sum(len(p.chats) for p in people)
        size = fixture.stat().st_size
        print(f"fixture                {len(people)} people, {n_chats} chats ({size} B)")
    else:
        print(f"fixture                MISSING at {fixture}")
        ok = False

    if args.encoder:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        model = SentenceTransformer(config.BASE_ENCODER, device="cpu")
        vecs = model.encode(
            ["how do i fix a flat on my bike", "best pasta for a long run tomorrow"],
            normalize_embeddings=True,
        )
        print(f"encoder                {config.BASE_ENCODER} dim={vecs.shape[1]}")
        print(f"hf cache after         {_dir_size_mb(config.hf_cache_dir()):.0f} MB")

    print("smoke: OK" if ok else "smoke: PROBLEMS FOUND")
    return 0 if ok else 1
