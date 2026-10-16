# Decisions

Status: the project's decision log, one dated line per decision, newest first. Mistakes are fixed in place, with a dated note saying what changed.

- 2026-10-16 — The site keeps the untrained base encoder (B1) with its toy calibration: student v0 beat it by 3 of 114 exam decisions, inside the bootstrap interval of the difference, and a shipped student needs a hosted model file, which the 5 MB rule forbids in the repository (Claude Code, BDL-3): scoreboard/runs/2026-10-16-toy-v0.json, web/src/sorter/calibration.json.
- 2026-10-16 — The toy teacher runs on llama.cpp's llama-server, not mlx-lm or Ollama, which were absent; llama-server documents JSON mode, seeds and parallel slots. Model: Qwen3-4B-Instruct-2507 Q4_K_M, Apache-2.0 (Claude Code, BDL-3): pipeline/docs/toy-teacher.md.
- 2026-10-16 — Export uses torch.onnx.export plus onnxruntime quantize_dynamic, because optimum-onnx pins transformers below 4.58 and cannot coexist with sentence-transformers 6 (Claude Code, BDL-3): pipeline/README.md.
- 2026-10-16 — The website pins Vite 8.3.2 and TypeScript 7.0.2, where research track R4 would have chosen 8.3.3 and 6.0.3; kept because typecheck, tests, build and e2e were green, and recorded here rather than churned (Claude Code, BDL-3): web/package.json, docs/research/README.md.
- 2026-10-16 — Mistake, fixed from PR #3 on: the squash commits of PR #1 and PR #2 carry a Co-authored-by trailer against the founder rule; main is never rewritten, so they stay (Claude Code, BDL-3).
- 2026-10-16 — D1 Product: Bundle is an open decision model that sorts a person's AI chats into bundles, with a demo website and a public scoreboard, offered as an open proposal any chat platform can adopt (technical co-founder, BDL-3): docs/SPEC.md.
- 2026-10-16 — D2 Visitors: the site stores nothing about visitors (no chats, quiz answers, accounts, cookies or analytics), and the model never trains on anything visitors do. Reason: privacy, and test-drive input is noise (technical co-founder, BDL-3): docs/ARCHITECTURE.md.
- 2026-10-16 — D3 Training data: lessons and exams are written by an open-licensed teacher model we run ourselves; never real chats, never copied web text. Reason: privacy, copyright, and a dataset anyone can reproduce (technical co-founder, BDL-3): pipeline/.
- 2026-10-16 — D4 Demo content: the website's library is written separately and never used for lessons or exams. Reason: it keeps the demo an honest test (technical co-founder, BDL-3): web/src/content/library/.
- 2026-10-16 — D5 Model: a small student fine-tuned from an open encoder answers "which bundle, or none" with probabilities and is small enough to run in a browser. Reason: no servers, no cost per use, chats never leave the device (technical co-founder, BDL-3): docs/ARCHITECTURE.md.
- 2026-10-16 — D6 Rules: file, suggest or leave loose. Cut-offs come from calibration on practice data (targets: 95% precision to file, 80% to suggest) (technical co-founder, BDL-3): docs/ARCHITECTURE.md.
- 2026-10-16 — D7 Evaluation: lessons, practice tests and a sealed exam are split by person and never mixed. A release ships only if it beats the previous one on the exam. Every result is published (technical co-founder, BDL-3): scoreboard/.
- 2026-10-16 — D8 Web stack: a static site (Vite, React, TypeScript) to be hosted on Vercel; no backend; Supabase unused until something needs it; Node pinned to 24.21.0. Reason: version 1 has no server work (technical co-founder, BDL-3): web/, .node-version.
- 2026-10-16 — D9 ML stack: a Python pipeline managed by uv. The teacher is reached over an OpenAI-compatible HTTP API, so the same code runs on the Mac and on the DGX Spark (technical co-founder, BDL-3): pipeline/.
- 2026-10-16 — D10 Compute: the DGX Spark runs the teacher and the real training from BDL-4. BDL-3's Mac run only proves the loop (technical co-founder, BDL-3).
- 2026-10-16 — D11 Comparators: a no-training baseline, the previous student, Clef-flash (open), and Claude Haiku 5.5 checked weekly. Haiku needs a paid API key and Hrishikesh's approval, and is never part of the product (technical co-founder, BDL-3): scoreboard/.
- 2026-10-16 — D12 Licences: datasets CC BY 4.0, like the docs; model weights Apache-2.0, so base models must be Apache-2.0 or MIT (technical co-founder, BDL-3): README.md.
- 2026-10-16 — D13 Naming and publishing: "Bundle" is a working name. Nothing is deployed or published until the public name is settled (open item 3). SPEC.md and ARCHITECTURE.md join the files mirrored to project knowledge (technical co-founder, BDL-3): CLAUDE.md.
- 2026-10-13 — The setup went straight to main as the first commit; from then on, every change goes through a pull request (BDL-1): CLAUDE.md.
- 2026-10-13 — Licences: code Apache-2.0; documentation, meaning the Markdown files and docs/, CC BY 4.0 (technical co-founder): LICENSE, LICENSE-docs, README.md.
- 2026-10-13 — Pull requests from outside contributors are merged only by the founder (founder): CLAUDE.md.
- 2026-10-13 — Free-flowing method: the founder gives the product, web Claude makes the technical decisions as technical co-founder, and Claude Code merges its own pull requests; no gates beyond CLAUDE.md (founder): CLAUDE.md.
- 2026-10-13 — A fresh start: nothing is carried over from the earlier Bundle repository (founder).
- 2026-10-13 — The repository is public (founder).
