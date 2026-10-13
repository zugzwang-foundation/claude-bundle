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
