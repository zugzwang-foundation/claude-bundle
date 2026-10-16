# Release drafts: Hugging Face cards

Status: DRAFT — written in BDL-3, **not published**. Nothing in this folder has been uploaded anywhere.

## What these files are

Two cards in the format the Hugging Face Hub renders from a repository's `README.md`: a YAML front matter block for the metadata the Hub indexes, then Markdown sections in the order of the Hub's own templates (model card and dataset card templates, https://github.com/huggingface/huggingface_hub/tree/main/src/huggingface_hub/templates, checked 16 Oct 2026).

| file | becomes | licence it declares |
|---|---|---|
| [MODEL_CARD.md](MODEL_CARD.md) | the `README.md` of the model repository: the student encoder, its ONNX exports and its calibration file | Apache-2.0 (D12) |
| [DATASET_CARD.md](DATASET_CARD.md) | the `README.md` of the dataset repository: the invented people and their chats, the decision examples, and the sealed exam's hash | CC BY 4.0 (D12) |

## Why they are drafts

- **The name is not settled.** "Bundle" is a working name, and D13 says nothing is deployed or published until the public name is chosen. Every place a name, an organisation or a repository id would go holds a placeholder in angle brackets, such as `<organisation>/<model-name>`.
- **The numbers are not in.** The evaluation and results sections point at `scoreboard/runs/` and say "to be filled from the latest run". A card is only filled from the run that actually ships (D7).
- **The base encoder may change.** The cards name `sentence-transformers/all-MiniLM-L6-v2` because the pipeline and the research track R2 pick it for version 0; R2 also says the pick should flip to `mixedbread-ai/mxbai-embed-xsmall-v1` if the chats run longer than 256 word pieces (docs/research/student-and-method.md, checked 16 Oct 2026). The front matter marks this NOT VERIFIED until the exam decides.
- **No Hugging Face account was used.** Relay rule 6 for BDL-3 puts Hugging Face accounts and publishing out of scope.

## How to read the placeholders

- `<angle brackets>` mark a value nobody knows yet.
- "to be filled from the latest run" marks a value that exists in `scoreboard/runs/<run-id>.json` once a run has been made and must be copied from the run that ships, never typed by hand.
- NOT VERIFIED marks a fact that was taken from a plan rather than checked against a source.

## Before publishing

1. Settle the public name (D13) and replace every placeholder.
2. Fill the results from the shipping run's JSON and the calibration values from its notes.
3. Re-check every licence named in the cards against the source on the day of publishing, and record the check in `docs/research/licences.md` (first written in BDL-3; every model and package there was checked on 16 Oct 2026).
4. Have the founder read both cards. Nothing is published without him (CLAUDE.md).

Everything in this folder is documentation and is licensed CC BY 4.0 like the rest of `docs/` (LICENSE-docs).
