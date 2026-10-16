"""W6 parity: embed the 32 parity texts with PyTorch (sentence-transformers) as the reference.

    cd pipeline && uv run python scripts/w6_parity_torch.py \
        [--model data/models/student-v0] [--texts data/runs/parity-texts.json] \
        [--out data/runs/parity-torch.json]

Writes the CPU vectors (batch of 32 and one text at a time), the MPS vectors when available,
the tokenizer's ids per text and the versions, so scripts/w6_parity_compare.py can compare them
with the Transformers.js vectors from scripts/w6_parity_node.mjs.
"""

from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path

import numpy as np

PIPE = Path(__file__).resolve().parents[1]


def encode(st, texts: list[str], batch_size: int) -> np.ndarray:
    return np.asarray(
        st.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ),
        dtype=np.float32,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=str(PIPE / "data" / "models" / "student-v0"))
    ap.add_argument("--texts", default=str(PIPE / "data" / "runs" / "parity-texts.json"))
    ap.add_argument("--out", default=str(PIPE / "data" / "runs" / "parity-torch.json"))
    ap.add_argument("--max-seq-length", type=int, default=128)
    args = ap.parse_args()

    import sentence_transformers
    import torch
    import transformers
    from sentence_transformers import SentenceTransformer

    texts = json.loads(Path(args.texts).read_text(encoding="utf-8"))["texts"]
    t0 = time.perf_counter()
    st = SentenceTransformer(args.model, device="cpu")
    st.max_seq_length = args.max_seq_length
    load_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    batch = encode(st, texts, batch_size=32)
    batch_s = time.perf_counter() - t0
    single_ms: list[float] = []
    singles = []
    for t in texts:
        t1 = time.perf_counter()
        singles.append(encode(st, [t], batch_size=1)[0])
        single_ms.append((time.perf_counter() - t1) * 1000)
    single = np.stack(singles)

    enc = st.tokenizer(texts, truncation=True, max_length=args.max_seq_length)
    token_ids = [list(map(int, ids)) for ids in enc["input_ids"]]

    mps = None
    mps_note = "torch.backends.mps.is_available() is False"
    if torch.backends.mps.is_available():
        st_mps = SentenceTransformer(args.model, device="mps")
        st_mps.max_seq_length = args.max_seq_length
        mps = encode(st_mps, texts, batch_size=32)
        mps_note = "batch of 32 on MPS"

    out = {
        "model": args.model,
        "device": "cpu",
        "max_seq_length": args.max_seq_length,
        "versions": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "sentence_transformers": sentence_transformers.__version__,
            "transformers": transformers.__version__,
        },
        "n": len(texts),
        "dim": int(batch.shape[1]),
        "tokenIds": token_ids,
        "loadSeconds": round(load_s, 2),
        "batch32Ms": round(batch_s * 1000, 1),
        "singleMs": [round(x, 2) for x in single_ms],
        "singleMsMedian": round(float(np.median(single_ms)), 2),
        "vectorsBatch": batch.tolist(),
        "vectorsSingle": single.tolist(),
        "vectorsMps": mps.tolist() if mps is not None else None,
        "mpsNote": mps_note,
    }
    Path(args.out).write_text(json.dumps(out) + "\n", encoding="utf-8")
    print(f"torch: {args.model} loaded in {load_s:.1f}s; {len(texts)} texts, dim {batch.shape[1]}")
    print(
        f"torch: batch of 32 {batch_s * 1000:.0f} ms; single decision median "
        f"{np.median(single_ms):.1f} ms on CPU; {mps_note}"
    )
    print(f"torch: versions {out['versions']}")
    print(f"torch: wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
