# CLAUDE.md — how Claude Code works in this repository

The first part applies to everyone. The last part applies only to the founder's own sessions, whose relays are named BDL-N.

## For everyone
1. No secret, key, credential or personal data in this repository, ever. Keys live in the services' own settings; tests use synthetic data.
2. Never fill a fact from memory: check it, or mark it NOT VERIFIED.
3. Never force-push or delete main, and never rewrite history.
4. Commit and pull-request prefixes: `chore:`, `docs:`, `feat:`, `fix:`, `test:`.
5. docs/DECISIONS.md holds one dated line per decision, newest first; mistakes are fixed in place with a dated note. STATUS.md says, in plain words, what is done, what is next and what is ready to show.

## Product rules
(Added as the product takes shape.)

## Layout and commands
Layout, decided in BDL-3; each folder lands as its workstream merges:
- `web/` — Vite + React + TypeScript static site (Node 24.21.0 via `.node-version`); Biome, Vitest, Playwright.
  - `src/config.ts` — `APP_NAME = "Bundle"` and the footer line: the only place the name lives.
  - `src/styles/tokens.css` — design tokens, light and dark.
  - `src/content/library/` — demo library JSON, one file per interest, plus `library.schema.json`; demo content only (D4).
  - `src/content/assemble.ts` — builds a visitor's nine-month history from the library.
  - `src/sorter/` — `worker.ts` (Transformers.js in a Web Worker, WebGPU then WASM), `scoring.ts`, `rules.ts`, `calibration.json`, `model-manifest.json`.
  - `src/screens/` — Welcome, Quiz, History, Chat, MonthsPass, Challenge, Reveal, Continue.
  - `src/tech/` — tech view: probability bars, model info and latency, SVG architecture diagram, scoreboard, roadmap.
  - `src/generated/` — precomputed library embeddings (gitignored; built by `web/scripts/precompute-embeddings.mjs`).
  - `public/fonts/` — self-hosted Bricolage Grotesque and Atkinson Hyperlegible (OFL).
  - `public/models/` — student model files for the browser (gitignored; the manifest points here when a student ships).
  - `scripts/` — `precompute-embeddings.mjs`, `validate-library.mjs`.
  - `e2e/` — Playwright flow at 390×844 and 1440×900.
- `pipeline/` — uv project, package `bundle_pipeline`: schema, teacher, prompts, generate, validate, split, tasks, baseline, train, calibrate, exam, export, scoreboard; `tests/fixtures/` holds the two-person fixture.
- `scoreboard/runs/` — one JSON per exam run, labelled "toy scale" today.
- `scripts/spark/` — commands and configs for the DGX Spark (written later, not run).
- `docs/` — SPEC.md, ARCHITECTURE.md, DECISIONS.md, research/, release/.
- `.github/workflows/ci.yml` — a web job and a pipeline job.

Commands (as planned in BDL-3; each set lands with its workstream):
- web (in `web/`): `npm ci`, `npm run dev`, `npm run typecheck`, `npm run lint`, `npm test`, `npm run e2e`, `npm run build`.
- pipeline (in `pipeline/`): `uv sync --frozen`, `uv run ruff check .`, `uv run pytest`, `uv run bundle-pipeline <command>`.

House rules:
1. The project's runtimes are Node 24.21.0 (`.node-version`) and the uv-managed Python in `pipeline/.python-version`, never the system ones.
2. Generated data and models are gitignored; the only exceptions are test fixtures under 200 KB, the demo library and the scoreboard JSON.
3. No file over 5 MB is ever committed.

## For the founder's sessions (BDL-N)
### Roles
- **Hrishikesh**, the founder, gives the product and its look and feel. Nothing is published, posted, bought or sent without him.
- **Web Claude**, the technical co-founder, makes the technical decisions and writes each relay. A relay's decisions stand unless Hrishikesh reopens them.
- **Claude Code** does the relay's work, merges its own pull requests and ends with a short close-out.

### Rules
1. Commit as user.name "Zugzwang/world", user.email "zugzwangworld@proton.me", set in this clone only. No Co-authored-by trailers.
2. Never post, contact anyone, spend money, or change the repository's name or visibility.
3. Never merge a pull request you didn't open: Hrishikesh decides those.
4. Use the Supabase and Vercel tools only when a relay says so.
5. Don't stop to ask mid-session: take the sensible option and list it as an open point. If a relay states something that proves wrong, take the sensible reading and say so in the close-out.

### How a change lands
Branch `bdl-<n>-<slug>` from the latest main → commit → pull request → run the work and see it work → merge it yourself (squash) → pull main. Merged branches are deleted automatically.

### Each session
- Start: `date -u`; save the relay verbatim to `~/Downloads/zz_BDL-N_relay.md`; `git fetch` and work from the latest main.
- End: bring STATUS.md up to date in your last pull request; write `~/Downloads/zz_BDL-N_close-out.md` (pull requests merged, what changed, what is live, anything skipped or blocked, open points, numbered) and show it as your last message.
- If CLAUDE.md, STATUS.md or docs/DECISIONS.md changed, copy them flat into `~/Downloads/zz_BDL_PK/`.
- "Continue BDL-N from the relay." means: re-read the relay, check git, and pick up where the work stopped.
- Session files live in `~/Downloads`, never in this repository.

### Habits (each one cost hours once)
- Push over SSH, non-interactively.
- Never leave a shell waiting for input; write each file in one command.
- Times come from `date -u`, in UTC.
- For exact searches, use `command grep` or a short script: on this Mac, `grep` is a shell function in Claude Code's shell.
- Use the project's own runtime, never the system one.
