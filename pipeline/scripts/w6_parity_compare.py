"""W6 parity: compare Transformers.js (Node) vectors with the PyTorch reference, per text.

    cd pipeline && uv run python scripts/w6_parity_compare.py [--runs data/runs]

Reads parity-torch.json and parity-node-<dtype>.json (q8, fp32) from the runs directory, prints
a markdown table of per-text cosines (min, median, mean, worst text, how many reach 0.999) and
the Node latency figures, and writes parity-summary.json.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

PIPE = Path(__file__).resolve().parents[1]
BAR = 0.999


def cos_rows(a: list, b: list) -> np.ndarray:
    x = np.asarray(a, dtype=np.float64)
    y = np.asarray(b, dtype=np.float64)
    x /= np.linalg.norm(x, axis=1, keepdims=True)
    y /= np.linalg.norm(y, axis=1, keepdims=True)
    return (x * y).sum(axis=1)


def summary(name: str, a: list, b: list) -> dict:
    c = cos_rows(a, b)
    return {
        "comparison": name,
        "n": int(c.size),
        "min": float(c.min()),
        "median": float(np.median(c)),
        "mean": float(c.mean()),
        "max": float(c.max()),
        "worst_index": int(c.argmin()),
        "at_or_above_0.999": int((c >= BAR).sum()),
        "meets_0.999": bool(c.min() >= BAR),
        "per_text": [float(v) for v in c],
    }


def facts(d: dict) -> dict:
    """Everything but the vectors and token ids."""
    return {k: v for k, v in d.items() if not k.startswith("vectors") and k != "tokenIds"}


def row(s: dict) -> str:
    return (
        f"| {s['comparison']} | {s['n']} | {s['min']:.6f} | {s['median']:.6f} | {s['mean']:.6f} "
        f"| {s['worst_index']} | {s['at_or_above_0.999']}/{s['n']} "
        f"| {'yes' if s['meets_0.999'] else 'no'} |"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(PIPE / "data" / "runs"))
    args = ap.parse_args()
    runs = Path(args.runs)

    torch = json.loads((runs / "parity-torch.json").read_text(encoding="utf-8"))
    texts = json.loads((runs / "parity-texts.json").read_text(encoding="utf-8"))["texts"]
    nodes = {}
    for dtype in ("q8", "fp32"):
        p = runs / f"parity-node-{dtype}.json"
        if p.is_file():
            nodes[dtype] = json.loads(p.read_text(encoding="utf-8"))
    errors_path = runs / "parity-node-errors.json"
    errors = json.loads(errors_path.read_text(encoding="utf-8")) if errors_path.is_file() else []

    comps = []
    for dtype, node in nodes.items():
        comps.append(
            summary(
                f"Node {dtype} batch vs PyTorch CPU batch",
                node["vectorsBatch"],
                torch["vectorsBatch"],
            )
        )
        comps.append(
            summary(
                f"Node {dtype} single vs PyTorch CPU single",
                node["vectorsSingle"],
                torch["vectorsSingle"],
            )
        )
        comps.append(
            summary(
                f"Node {dtype} batch vs Node {dtype} single (padding effect)",
                node["vectorsBatch"],
                node["vectorsSingle"],
            )
        )
    if "q8" in nodes and "fp32" in nodes:
        comps.append(
            summary(
                "Node q8 vs Node fp32 (quantisation alone)",
                nodes["q8"]["vectorsBatch"],
                nodes["fp32"]["vectorsBatch"],
            )
        )
    comps.append(
        summary(
            "PyTorch CPU batch vs PyTorch CPU single", torch["vectorsBatch"], torch["vectorsSingle"]
        )
    )
    if torch.get("vectorsMps"):
        comps.append(
            summary(
                "PyTorch MPS batch vs PyTorch CPU batch", torch["vectorsMps"], torch["vectorsBatch"]
            )
        )

    tokens = {}
    for dtype, node in nodes.items():
        same = [a == b for a, b in zip(node["tokenIds"], torch["tokenIds"], strict=True)]
        tokens[dtype] = {
            "identical_texts": int(sum(same)),
            "n": len(same),
            "lengths_node": [len(t) for t in node["tokenIds"]],
            "lengths_torch": [len(t) for t in torch["tokenIds"]],
        }

    print(
        "| comparison | n | min cos | median cos | mean cos | worst text | >= 0.999 | meets 0.999 |"
    )
    print("|---|---|---|---|---|---|---|---|")
    for s in comps:
        print(row(s))
    print()
    for dtype, t in tokens.items():
        print(
            f"token ids identical (Node {dtype} vs PyTorch): {t['identical_texts']}/{t['n']}; "
            f"lengths min {min(t['lengths_torch'])} max {max(t['lengths_torch'])}"
        )
    for dtype, node in nodes.items():
        st = node["timed40Stats"]
        print(
            f"Node {dtype}: load {node['loadMs']} ms, batch of 32 {node['batch32Ms']} ms, "
            f"40 single decisions median {st['median']} ms (min {st['min']}, p90 {st['p90']}, "
            f"max {st['max']}, mean {st['mean']}); first single {node['singleMs'][0]} ms; "
            f"rss {node['rssMBAfterLoad']} MB; file {node['fileLoaded']}"
        )
    print(
        f"PyTorch CPU: load {torch['loadSeconds']} s, batch of 32 {torch['batch32Ms']} ms, "
        f"single decision median {torch['singleMsMedian']} ms"
    )
    for e in errors:
        print(f"LOAD ERROR dtype {e['dtype']}: {e['error']}")
    worst = {s["comparison"]: texts[s["worst_index"]] for s in comps[:2]} if comps else {}

    out = {
        "texts_sha256_source": "parity-texts.json",
        "comparisons": comps,
        "token_ids": tokens,
        "node": {d: facts(n) for d, n in nodes.items()},
        "torch": facts(torch),
        "errors": errors,
        "worst_texts": worst,
    }
    (runs / "parity-summary.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(f"\nwrote {runs / 'parity-summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
