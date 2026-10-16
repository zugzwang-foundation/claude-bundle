# Status

Status: DRAFT — where the project stands, in plain words; updated at every session close-out. Last updated 2026-10-16 (BDL-3 close-out).

## Done
- **Setup.** The repository, its working rules, licences and GitHub settings are in place (BDL-1).
- **Foundation day (BDL-3, 16 October 2026).** Node pinned and ignore rules (W0). The spec, the architecture and decisions D1 to D13 (W1). Six research tracks with a licences table and a frank synthesis in docs/research/ (W2). The Python pipeline with 130 tests: teacher client, prompts, generate, validate, split, tasks, baseline, train, calibrate, exam, export, scoreboard (W3). The demo library: twelve interests, 360 invented chats (W4). Website version 1 running locally with the real in-browser sorter, 107 unit tests and 10 Playwright runs (W5). Student v0, the sealed exam and the first scoreboard run, all at toy scale (W6). Continuous integration (W7). Spark scripts written but not run, and release-card drafts, unpublished.

## Next
- **BDL-4 on the DGX Spark.** Serve the teacher research track R3 recommends, generate at scale, train and calibrate the student properly, sit the sealed exam and publish the run. Day-one list: docs/research/dgx-spark.md and scripts/spark/README.md.
- **Apply the research.** WASM as the browser default, a two-number JavaScript budget, a second open comparator beside Clef-flash, a learned "none" logit, a deliberately written out-of-scope set (docs/research/README.md, "Recommended changes").
- **Ship the student.** Host the exported model so the site can load it through the manifest; today the site keeps the untrained base encoder.
- **Settle the public name** (D13) before anything is deployed or published.

## Ready to show
| item | real state |
|---|---|
| Demo website | local demo only, not deployed: `cd web && npm ci && npm run build && npm run preview`; the sorter downloads a 22.6 MB model from huggingface.co; 48 screenshots were taken on 16 October |
| Scoreboard | one toy-scale run, scoreboard/runs/2026-10-16-toy-v0.json: on 114 exam decisions the untrained base encoder scores 0.632 and student v0 0.658, a difference inside the bootstrap interval |
| Research | docs/research/README.md: ten findings, 21 corrections to the plan, 19 recommended changes |
