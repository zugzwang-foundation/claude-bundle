# Status

Status: DRAFT — where the project stands, in plain words; updated at every session close-out. Last updated 2026-10-16.

## Done
- **Setup.** The repository, its working rules, licences and GitHub settings are in place (BDL-1).
- **Pinned runtime and ignore rules.** Node is pinned to 24.21.0 in `.node-version`; generated data, model files, local runtimes and build output are gitignored (BDL-3, W0).
- **Foundation documents.** The product spec (docs/SPEC.md), the architecture (docs/ARCHITECTURE.md) and decisions D1 to D13 (docs/DECISIONS.md) are written. The README and CLAUDE.md describe the layout and the commands (BDL-3, W1).

## Next
All of these are BDL-3 workstreams, in progress today:
- **Research tracks R1 to R6.** Decision models, the student and its training method, the teacher and its data, the browser and the web stack, prior art, and the DGX Spark; frank recommendations in docs/research/.
- **The Python pipeline and the toy learning loop.** Teacher, lessons, student, practice, sealed exam and scoreboard, proved end to end on the Mac at toy scale.
- **The demo library.** Twelve interests of invented chats, written for the website only.
- **Website version 1.** The quiz, the chat history, the challenge and the reveal, running locally with the real in-browser sorter.
- **Student v0 and the toy scoreboard.** The first trained student, calibrated and examined, with every result in scoreboard/runs/.
- **Continuous integration.** A web job and a pipeline job on every pull request.

## Ready to show
| item | real state |
|---|---|
| Demo website | not yet; local build in progress (BDL-3), not deployed |
