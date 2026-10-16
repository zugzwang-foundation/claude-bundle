# Parity: Transformers.js in Node against PyTorch (W6, toy scale)

Measured 2026-10-16, 20:57 IST (15:27Z), on this Mac (Apple silicon, 24 GiB). The relay's W6 asks:
"Check that Transformers.js in Node and PyTorch give matching embeddings on 32 fixture texts
(cosine at least 0.999), or record the gap." Every number below was measured in this run; nothing
is filled from memory. Nothing was downloaded; nothing was committed.

## Result in one paragraph

The **fp32** ONNX export (`onnx/model.onnx`, loaded by Transformers.js with `dtype: "fp32"`) gives
the same vectors as PyTorch: min cosine **1.00000000** over the 32 texts (max element difference
2.5e-7 after normalisation, min cosine 1.0000000000 at ten decimals in float64), so the fp32 bar of 0.999 is met. The **int8** export
(`onnx/model_quantized.onnx`, loaded with `dtype: "q8"`) gives min cosine **0.991530**, median
0.997830, mean 0.997523, and **0 of 32 texts reach 0.999**: the gap is recorded. It is the same
gap to five decimals that `export_report.json` measured with Python onnxruntime 1.30.0 (min
0.99153, mean 0.99752, worst text 8), so the loss is the dynamic int8 quantisation, not the
JavaScript runtime: Transformers.js and onnxruntime-node reproduce Python onnxruntime exactly.
Tokenisation is identical (32/32 texts give the same token ids in Node and PyTorch). The chain
report's finding stands as the way to judge int8 (research item 4): the int8 model changed none of
the 114 exam decisions (that was measured through Python onnxruntime, not Node).

## What was compared

- Texts: `bundle_pipeline.export.fixture_texts(32)`, the exact list `export` used: the 25 chat
  texts of `tests/fixtures/people.json` in file order, then the 6 thread descriptions, then the
  first persona (the second persona falls off at 32). Written once to
  `pipeline/data/runs/parity-texts.json` (sha256 of the JSON list
  `69f70cade460d5f2d4598863a1de3902a79b36c2d468e032e37128db520225a1`) and read by both sides.
  Token lengths 3 ("hi") to 81 (the persona); the batch is padded to 81.
- Reference: `sentence-transformers` 6.1.0 on PyTorch 2.14.1 (transformers 5.18.0, CPython 3.14.8),
  `SentenceTransformer("data/models/student-v0", device="cpu")`, `max_seq_length` 128,
  `normalize_embeddings=True` (mean pooling and L2 normalisation are the model's own modules).
  Also computed on MPS: identical to the CPU vectors at 8 decimals.
- Candidate: `@huggingface/transformers` **4.3.0** in Node **v24.21.0** with `onnxruntime-node`
  **1.30.0** (CPU execution provider; the session reports `{dtype, device: "cpu"}`), the library
  already installed in `web/node_modules` (nothing was installed). `pipeline("feature-extraction",
  "student-v0-onnx", { dtype, device: "cpu" })` then `extractor(texts, { pooling: "mean",
  normalize: true })`: the same mean pooling over the attention mask and L2 normalisation the web
  worker uses (`web/src/sorter/worker.ts`).
- Both sides embedded the 32 texts as one padded batch and again one text at a time (batch of
  one, the way the app embeds a new chat).

## Cosines (per text, 32 texts)

| comparison | min | median | mean | max | worst text | >= 0.999 | meets 0.999 |
|---|---|---|---|---|---|---|---|
| Node **fp32** batch vs PyTorch CPU batch | 1.00000000 | 1.00000000 | 1.00000000 | 1.00000000 | - | 32/32 | **yes** |
| Node fp32 single vs PyTorch CPU single | 1.00000000 | 1.00000000 | 1.00000000 | 1.00000000 | - | 32/32 | yes |
| Node **q8** batch vs PyTorch CPU batch | **0.99153044** | 0.99782964 | 0.99752311 | 0.99859867 | 8 "hi" | 0/32 | **no** |
| Node q8 single vs PyTorch CPU single | 0.99440123 | 0.99799655 | 0.99786059 | 0.99876555 | 8 "hi" | 0/32 | no |
| Node q8 vs Node fp32 (quantisation alone) | 0.99153044 | 0.99782964 | 0.99752311 | 0.99859867 | 8 | 0/32 | no |
| Node q8 batch vs Node q8 single (padding effect) | 0.99239911 | 0.99818015 | 0.99784223 | 0.99873870 | 8 | 0/32 | no |
| Node fp32 batch vs Node fp32 single | 1.00000000 | 1.00000000 | 1.00000000 | 1.00000000 | - | 32/32 | yes |
| PyTorch CPU batch vs PyTorch CPU single | 1.00000000 | 1.00000000 | 1.00000000 | 1.00000000 | - | 32/32 | yes |
| PyTorch MPS batch vs PyTorch CPU batch | 1.00000000 | 1.00000000 | 1.00000000 | 1.00000000 | - | 32/32 | yes |

Python onnxruntime 1.30.0 on the same export (`export_report.json`, written by `export` at 19:11):
fp32 min 0.99999994, int8 min 0.99153042 mean 0.99752319 worst 8. Node reproduces both.

The int8 texts furthest from PyTorch (batch, cosine, token count): 8 "hi" 0.991530 (3 tokens);
9 "is this normal" 0.995408 (5); 23 "Does that rule change in the past tense?" 0.996623 (11);
6 "knee hurts" 0.996732 (4); 31 the nurse persona 0.996792 (81); 16 the crossword clue 0.997137
(29). Closest: 20 "How do I take a screenshot of just one window..." 0.998599. One text is below
0.995, 21 of 32 are below 0.998. The shortest texts suffer most.

Two things the table shows that `export_report.json` could not:

1. **int8 is padding-sensitive.** The same int8 model gives different vectors for a text embedded
   alone and embedded in a padded batch of 32 (self-cosine min 0.9924, median 0.9982), while fp32
   gives identical vectors either way. The likely cause (NOT VERIFIED by inspecting the graph) is
   dynamic quantisation computing activation scales per tensor at run time, so padded positions
   change the scales. It matters for the site: `web/scripts/precompute-embeddings.mjs` embeds the
   library in batches of 32 while the worker embeds a new chat alone, so library vectors and live
   vectors carry this noise relative to each other; embedding the library one text at a time, or
   both sides in the same batch shape, removes it.
2. **Tokenisers agree.** `tokenizer.json` + `tokenizer_config.json` (BertTokenizer, lower-casing,
   `model_max_length` 128) produce identical token ids for all 32 texts in Transformers.js and in
   transformers 5.18.

## Latency in Node (CPU execution provider, shared Mac, one text per call)

40 single decisions (one text each, texts cycled, after 33 warm calls), `performance.now()`
around `extractor([text], { pooling: "mean", normalize: true })`, which includes tokenisation,
the ONNX run, pooling and normalisation:

| model | median | min | p90 | max | mean | load | batch of 32 | RSS after load |
|---|---|---|---|---|---|---|---|---|
| q8 `onnx/model_quantized.onnx` (22,977,287 B) | **1.64 ms** | 0.59 | 2.74 | 5.78 | 1.81 | 108 ms | 107 ms | 183 MB |
| fp32 `onnx/model.onnx` (90,382,557 B) | 1.66 ms | 1.07 | 2.78 | 3.80 | 1.87 | 72 ms | 95 ms | 443 MB |

Raw q8 values (ms): 3.77, 2.74, 2.50, 2.03, 2.00, 1.96, 0.74, 1.55, 0.61, 0.62, 1.69, 1.57, 2.05,
1.91, 2.31, 1.60, 1.52, 1.49, 1.59, 1.80, 2.08, 1.17, 2.22, 1.47, 2.89, 1.26, 1.01, 0.98, 1.13,
0.97, 1.98, 5.78, 2.95, 1.56, 1.43, 2.05, 1.81, 1.72, 0.59, 1.40. The first single call after the
batch took 2.27 ms (q8). For comparison, PyTorch on the CPU: 5.11 ms median per single text,
165 ms for the batch of 32. Load times are from disk (onnxruntime-node opens the file by path; no
copy is made). These are Node figures; the browser runs onnxruntime-web on WASM or WebGPU, which
W5 measured separately for the base model and this run does not cover (NOT VERIFIED here).

## The dtype-to-file mapping, verified in the installed 4.3.0

`node_modules/@huggingface/transformers/src/utils/dtypes.js` lines 59-72,
`DEFAULT_DTYPE_SUFFIX_MAPPING`: `fp32: ''`, `fp16: '_fp16'`, `int8: '_int8'`, `uint8: '_uint8'`,
**`q8: '_quantized'`**, `q4: '_q4'`, `q2: '_q2'`, `q1: '_q1'`, `q4f16: '_q4f16'`, `q2f16: '_q2f16'`,
`q1f16: '_q1f16'`, `bnb4: '_bnb4'`. `src/models/session.js` line 75 picks the suffix from the
resolved dtype; `src/utils/model-loader.js` lines 44-46 build `${fileName}${suffix}.onnx` under
`options.subfolder`, which defaults to `'onnx'` (`src/pipelines.js` line 111,
`src/models/modeling_utils.js` line 283). The shipped bundle `dist/transformers.node.mjs` contains
the string `"_quantized"` exactly once and `subfolder = "onnx"` five times. In Node the default
device is `cpu` (`src/utils/devices.js`: `apis.IS_NODE_ENV ? 'cpu' : 'wasm'`); a browser defaults
to `wasm`, where the default dtype is `q8` (`DEFAULT_DEVICE_DTYPE_MAPPING`).

So for this export:

| dtype string | file Transformers.js opens | present | result |
|---|---|---|---|
| `"q8"` | `student-v0-onnx/onnx/model_quantized.onnx` | yes (22,977,287 B) | loads; **this is the int8 file** |
| `"fp32"` | `student-v0-onnx/onnx/model.onnx` | yes (90,382,557 B) | loads |
| `"int8"` | `student-v0-onnx/onnx/model_int8.onnx` | no | error, below |
| `"fp16"`, `"q4"` | `.../model_fp16.onnx`, `.../model_q4.onnx` | no | same error |

The wrong string fails like this (verbatim, `dtype: "int8"`):

```
`local_files_only=true` or `env.allowRemoteModels=false` and file was not found locally at "<worktree>/pipeline/data/models/student-v0-onnx/onnx/model_int8.onnx".
```

`manifest.json`'s `"dtype": "q8"` (marked NOT VERIFIED in the README) is therefore right. The
runtime session confirmed it: `extractor.model.sessions.model.config` is
`{"dtype":"q8","device":"cpu"}` with inputs `input_ids, attention_mask, token_type_ids` and output
`last_hidden_state`.

Files Transformers.js asked for when loading the q8 pipeline (from `progress_callback`):
`config.json`, `tokenizer.json`, `tokenizer_config.json`, `onnx/model_quantized.onnx`. It did not
ask for `special_tokens_map.json` or `onnx/model.onnx`. A local file is never copied into the
library's file cache (`src/utils/hub.js`: `toCacheResponse` needs a fetch `Response`, a
`FileResponse` is not one); `node_modules/@huggingface/transformers/.cache` was 23,768 KiB before
and after (it holds `Xenova/all-MiniLM-L6-v2` from the W5 precompute).

Local loading: `env.allowLocalModels = true`, `env.allowRemoteModels = false`,
`env.localModelPath = <parent of the export directory>`, and the model id is the export
directory's name (`src/utils/hub.js` line 138: `pathJoin(env.localModelPath, <id>/<file>)`).

## What the web app needs from this export

`web/src/sorter/model-manifest.json` today points at the Hub model
(`{"id": "Xenova/all-MiniLM-L6-v2", "source": "hub", "dtype": "q8", "name": ..., "sizeMB": null}`)
and `worker.ts` sets `env.localModelPath = ${base}models/` when `source` is `"local"`. For the
student (if Hrishikesh decides to wire it; the board's three-decision lead is within noise):

| field | value | why |
|---|---|---|
| `id` | `student-v0` | the manifest id and what `web/src/sorter/calibration.json` names in `model`; copy the export to `web/public/models/student-v0/` so the directory name equals the id (the export directory on disk is `student-v0-onnx`, so rename on copy, or use `student-v0-onnx` as the id in both files) |
| `source` | `local` | `worker.ts` then disables remote loading and reads `${base}models/` |
| `dtype` | `q8` | the only string that opens `onnx/model_quantized.onnx` in 4.3.0 |
| `sizeMB` | 22.98 (22,977,287 bytes; 21.91 MiB) | the int8 file alone; `size_bytes` in `manifest.json` |
| `name` | `Bundle student-v0 (all-MiniLM-L6-v2, int8)` | from `manifest.json` |
| files to copy | `config.json` (745 B), `tokenizer.json` (711,649 B), `tokenizer_config.json` (593 B), `onnx/model_quantized.onnx` (22,977,287 B); `special_tokens_map.json` (125 B) is harmless but unused | the four files the pipeline requested; **do not** copy `onnx/model.onnx` (90 MB) into `public/` (the model budget is 40 MB) |

After the copy, `npm run precompute` must rerun (its hash keys on `manifest.id` and `dtype`), and
the padding note above applies to the library vectors.

## Commands (as run; step 1 was run as a heredoc that also stored a `source` note in the file)

```sh
# 1. the 32 texts, the way export.py built them
cd <worktree>/pipeline
uv run python -c "import json; from bundle_pipeline.export import fixture_texts; t=fixture_texts(32); json.dump({'n':len(t),'texts':t}, open('data/runs/parity-texts.json','w'), ensure_ascii=False, indent=1)"

# 2. Transformers.js in Node, from the web worktree so the library resolves; the script is fed on stdin
cd <worktree-w5>/web
PARITY_PIPELINE_DIR=<worktree>/pipeline node --input-type=module < <worktree>/pipeline/scripts/w6_parity_node.mjs
#    -> pipeline/data/runs/parity-node-q8.json, parity-node-fp32.json (vectors, token ids, 40 timings); 0.94 s wall

# 3. PyTorch reference
cd <worktree>/pipeline
uv run python scripts/w6_parity_torch.py          # -> data/runs/parity-torch.json; 2.9 s wall

# 4. per-text cosines, token check, latency summary
uv run python scripts/w6_parity_compare.py        # -> data/runs/parity-summary.json and the table above
```

Script knobs (environment variables of `w6_parity_node.mjs`): `PARITY_PIPELINE_DIR` (the
`pipeline/` directory; the run used the worktree's absolute path, which the script no longer
hardcodes), `PARITY_TEXTS`, `PARITY_MODELS_DIR` (parent of the export directory), `PARITY_MODEL_ID`
(its name), `PARITY_OUT_DIR`, `PARITY_DTYPES` (default `q8,fp32`). A dtype that fails to load is recorded verbatim in
`<out>/parity-node-errors.json` and the others still run.

## Disk and network

No downloads (`env.allowRemoteModels = false`; the model, tokenizer and library were already on
disk). Free disk 16,371,612 KiB before and 16,373,848 KiB after. Files written under
`pipeline/data/runs/` (gitignored): `parity-texts.json` 3,490 B, `parity-node-q8.json` 520,572 B,
`parity-node-fp32.json` 520,707 B, `parity-torch.json` 815,188 B, `parity-summary.json` about
15 KB. Scripts (to commit): `pipeline/scripts/w6_parity_node.mjs`, `w6_parity_torch.py`,
`w6_parity_compare.py` (ruff clean).

## Open points

1. The int8 bar (0.999) is not met by any runtime on this stack: Python onnxruntime 0.99153, Node
   0.99153044. Research item 4 says to judge int8 by the exam effect (114/114 identical decisions,
   per the chain report) and keep 0.999 as the fp32 bar, which fp32 meets. A static-quantised or
   fp16 export could be tried on the Spark; not today.
2. Browser parity (onnxruntime-web 1.31.0-dev on WASM/WebGPU) was not measured; Node used
   onnxruntime-node 1.30.0 on the CPU. The same `.onnx` bytes run in both, but the WASM kernels
   can differ in the last bits (NOT VERIFIED).
3. int8 vectors depend on the batch shape (self-cosine min 0.9924); the site embeds the library in
   batches of 32 and live chats alone.
4. The export directory is `student-v0-onnx` while the manifest id is `student-v0`; the web copy
   must make the directory name and `id` agree.
