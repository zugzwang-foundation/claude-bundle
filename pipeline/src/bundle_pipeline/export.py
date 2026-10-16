"""`bundle-pipeline export`: the student as ONNX (fp32 and int8) in the Transformers.js layout.

Why not optimum: optimum-onnx 0.1.0 pins transformers<4.58 while
sentence-transformers 6.x needs transformers>=5 (see README). So the export is
``torch.onnx.export`` (the TorchScript exporter, ``dynamo=False``, since the
dynamo path needs the unpinned ``onnxscript`` package) followed by
``onnxruntime.quantization.quantize_dynamic`` with per-channel int8 weights.
Measured on 2026-10-16 on the base encoder with the 25 fixture chats:
fp32 ONNX vs PyTorch min cosine 0.99999994; int8 per-channel 0.993 (23 MB);
int8 per-tensor 0.936 (22.9 MB). The relay's 0.999 target is not met by any
int8 variant on this stack, so the gap is recorded in export_report.json.

Output directory layout (what Transformers.js expects for a local model id):

    <out>/config.json, tokenizer.json, tokenizer_config.json, special_tokens_map.json
    <out>/onnx/model.onnx            fp32
    <out>/onnx/model_quantized.onnx  int8 (dynamic, per-channel)
    <out>/manifest.json              {id, name, dtype, size_bytes, base_model, run_id}
    <out>/export_report.json         parity numbers, sizes, versions

The model's attention is loaded as "eager" for tracing; SDPA traces fine too but
emits warnings about Python booleans. Mean pooling and normalisation are done by
the caller (the web app), exactly as ``sorter.py`` and ``compare_embeddings`` do.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from bundle_pipeline import config
from bundle_pipeline.store import write_json

OPSET = 14
INPUT_NAMES = ("input_ids", "attention_mask", "token_type_ids")
MANIFEST_KEYS = ("id", "name", "dtype", "size_bytes", "base_model", "run_id")


def mean_pool_normalise(hidden: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
    """Mean pooling over non-padding tokens, then L2 normalisation (what the app does)."""
    mask = attention_mask[..., None].astype(np.float32)
    summed = (hidden.astype(np.float32) * mask).sum(axis=1)
    counts = np.clip(mask.sum(axis=1), 1e-9, None)
    vec = summed / counts
    return vec / np.clip(np.linalg.norm(vec, axis=1, keepdims=True), 1e-12, None)


def fixture_texts(n: int = 32, fixture: Path | None = None) -> list[str]:
    """Up to n texts from the committed fixture: chats, then thread descriptions, then personas."""
    path = fixture or (config.PIPELINE_ROOT / "tests" / "fixtures" / "people.json")
    people = json.loads(path.read_text(encoding="utf-8"))
    texts: list[str] = [c["text"] for p in people for c in p["chats"]]
    texts += [t["description"] for p in people for t in p["threads"]]
    texts += [p["persona"] for p in people]
    return list(dict.fromkeys(texts))[:n]


def _load_for_export(model_dir: str) -> Any:
    from sentence_transformers import SentenceTransformer  # noqa: PLC0415

    try:
        return SentenceTransformer(
            model_dir, device="cpu", model_kwargs={"attn_implementation": "eager"}
        )
    except TypeError:  # older signature without model_kwargs
        return SentenceTransformer(model_dir, device="cpu")


def export_onnx(
    model_dir: str,
    out_dir: Path,
    run_id: str,
    student_id: str = "student-v0",
    base_model: str = config.BASE_ENCODER,
    per_channel: bool = True,
    max_seq_length: int = 128,
    log: Any = print,
) -> dict[str, Any]:
    import onnx  # noqa: PLC0415
    import onnxruntime as ort  # noqa: PLC0415
    import torch  # noqa: PLC0415
    from onnxruntime.quantization import QuantType, quantize_dynamic  # noqa: PLC0415

    out_dir.mkdir(parents=True, exist_ok=True)
    onnx_dir = out_dir / "onnx"
    onnx_dir.mkdir(exist_ok=True)

    st = _load_for_export(model_dir)
    hf_model = st[0].auto_model.eval()
    tokenizer = st.tokenizer
    hf_model.config.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    special = out_dir / "special_tokens_map.json"
    if not special.is_file():  # transformers 5 folds these into tokenizer_config.json
        write_json(special, dict(getattr(tokenizer, "special_tokens_map", {}) or {}))
    for name in (
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "config.json",
    ):
        if not (out_dir / name).is_file():
            raise FileNotFoundError(f"export did not produce {name}")

    class Wrapped(torch.nn.Module):
        def __init__(self, m: torch.nn.Module) -> None:
            super().__init__()
            self.m = m

        def forward(self, input_ids, attention_mask, token_type_ids):  # type: ignore[no-untyped-def]
            out = self.m(
                input_ids=input_ids, attention_mask=attention_mask, token_type_ids=token_type_ids
            )
            return out.last_hidden_state

    sample = tokenizer(
        ["a short sample sentence", "a second, slightly longer sample sentence for tracing"],
        padding=True,
        truncation=True,
        max_length=max_seq_length,
        return_tensors="pt",
    )
    args = tuple(sample[k] for k in INPUT_NAMES)
    dyn = {k: {0: "batch", 1: "sequence"} for k in INPUT_NAMES}
    dyn["last_hidden_state"] = {0: "batch", 1: "sequence"}
    fp32_path = onnx_dir / "model.onnx"
    t0 = time.perf_counter()
    import warnings  # noqa: PLC0415

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        torch.onnx.export(
            Wrapped(hf_model),
            args,
            str(fp32_path),
            input_names=list(INPUT_NAMES),
            output_names=["last_hidden_state"],
            dynamic_axes=dyn,
            opset_version=OPSET,
            dynamo=False,
        )
    onnx.checker.check_model(str(fp32_path))
    export_s = time.perf_counter() - t0
    log(f"export: fp32 {fp32_path.stat().st_size / 1e6:.1f} MB in {export_s:.1f}s")

    q_path = onnx_dir / "model_quantized.onnx"
    t0 = time.perf_counter()
    quantize_dynamic(
        str(fp32_path), str(q_path), weight_type=QuantType.QInt8, per_channel=per_channel
    )
    quant_s = time.perf_counter() - t0
    log(f"export: int8 {q_path.stat().st_size / 1e6:.1f} MB in {quant_s:.1f}s")

    texts = fixture_texts(32)
    parity = {
        "fp32": compare_embeddings(texts, model_dir, fp32_path, st=st),
        "int8": compare_embeddings(texts, model_dir, q_path, st=st),
    }
    fp32_cos, int8_cos = parity["fp32"]["min_cos"], parity["int8"]["min_cos"]
    log(f"export: parity min cos fp32 {fp32_cos:.6f}, int8 {int8_cos:.6f}")

    manifest = {
        "id": student_id,
        "name": f"Bundle {student_id} ({Path(base_model).name}, int8)",
        "dtype": "q8",
        "size_bytes": q_path.stat().st_size,
        "base_model": base_model,
        "run_id": run_id,
    }
    write_json(out_dir / "manifest.json", manifest)
    report = {
        "run_id": run_id,
        "date": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_model": model_dir,
        "base_model": base_model,
        "opset": OPSET,
        "exporter": "torch.onnx.export(dynamo=False)",
        "quantization": f"onnxruntime quantize_dynamic QInt8 per_channel={per_channel}",
        "files": {
            "onnx/model.onnx": fp32_path.stat().st_size,
            "onnx/model_quantized.onnx": q_path.stat().st_size,
        },
        "parity_texts": len(texts),
        "parity": parity,
        "target_min_cos": 0.999,
        "int8_meets_target": parity["int8"]["min_cos"] >= 0.999,
        "seconds": {"export": round(export_s, 1), "quantize": round(quant_s, 1)},
        "versions": {
            "torch": torch.__version__,
            "onnx": onnx.__version__,
            "onnxruntime": ort.__version__,
        },
        "browser_check": "Transformers.js in Node is W6's job; not run here",
    }
    write_json(out_dir / "export_report.json", report)
    return {"manifest": manifest, "report": report}


def compare_embeddings(
    texts: Sequence[str],
    model_dir: str,
    onnx_path: str | Path,
    st: Any = None,
    max_seq_length: int = 128,
) -> dict[str, Any]:
    """Embed with PyTorch and with onnxruntime (same tokenizer, mean pooling, normalise).

    Returns min and mean cosine between the two, and the worst text's index.
    """
    import onnxruntime as ort  # noqa: PLC0415

    if st is None:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        st = SentenceTransformer(model_dir, device="cpu")
    st.max_seq_length = max_seq_length
    texts = list(texts)
    ref = np.asarray(st.encode(texts, normalize_embeddings=True, convert_to_numpy=True))
    enc = st.tokenizer(
        texts, padding=True, truncation=True, max_length=max_seq_length, return_tensors="np"
    )
    feeds = {k: np.asarray(enc[k]) for k in INPUT_NAMES}
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    hidden = session.run(["last_hidden_state"], feeds)[0]
    got = mean_pool_normalise(hidden, feeds["attention_mask"])
    cos = (ref * got).sum(axis=1)
    return {
        "n": len(texts),
        "min_cos": float(cos.min()),
        "mean_cos": float(cos.mean()),
        "worst_index": int(cos.argmin()),
    }


def main(args: argparse.Namespace) -> int:
    model_dir = Path(args.model)
    if not model_dir.is_dir() and "/" not in args.model:
        print(f"export: no model at {model_dir}; run `bundle-pipeline train` first")
        return 2
    from bundle_pipeline.exam import default_run_id  # noqa: PLC0415

    result = export_onnx(
        str(model_dir) if model_dir.is_dir() else args.model,
        Path(args.out),
        run_id=args.run_id or default_run_id(),
        student_id=args.student_id,
        base_model=args.base_model,
        per_channel=not args.per_tensor,
    )
    m, r = result["manifest"], result["report"]
    print(
        f"export: {args.out}/manifest.json -> {m['id']} {m['dtype']} {m['size_bytes'] / 1e6:.1f} MB"
    )
    print(
        f"export: int8 parity min cos {r['parity']['int8']['min_cos']:.4f} "
        f"({'meets' if r['int8_meets_target'] else 'below'} the 0.999 target)"
    )
    return 0


__all__ = [
    "INPUT_NAMES",
    "MANIFEST_KEYS",
    "OPSET",
    "compare_embeddings",
    "export_onnx",
    "fixture_texts",
    "mean_pool_normalise",
]
