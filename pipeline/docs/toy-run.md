# Toy run (BDL-3, W3): the real generation on this Mac

Started 2026-10-16 18:11 IST (2026-10-16T12:41:48Z) from `pipeline/` on branch `bdl-3-pipeline`.

## Command

```
cd /Users/hrishikesh/Developer/claude-bundle/.claude/worktrees/w3-pipeline/pipeline
nohup uv run bundle-pipeline generate --people 24 --chats-per-person 60 --seed 42 \
  --out data/raw/people --workers 4 --time-budget-min 55 > data/generate.nohup.log 2>&1 &
```

- PID: 25538
- Teacher: llama-server 0.5.0 at http://127.0.0.1:8081/v1, Qwen3-4B-Instruct-2507 Q4_K_M
  (`-np 4`, Metal), see docs/toy-teacher.md.
- Prompts: v0.2 (strict JSON schemas via `response_format: json_schema`; see prompts.py).
- Logs: `data/generate.nohup.log` (stdout/stderr), `data/generate.log` (one line per person).
- Idempotent: rerunning the same command skips people already on disk.

## Why 24 people

The relay asks for about 24 people of about 60 chats within 60 minutes. The teacher report
(docs/toy-teacher.md) estimated 2 h for 24 x 60 at 4 concurrent slots and recommended 10 people
for 55 minutes; the smoke run measured 18.2 chats/min on a single stream while other agents loaded
the Mac. `--time-budget-min 55` stops starting new people after 55 minutes (+5 min grace for
people in flight), so asking for 24 costs nothing extra: the run writes whatever finishes, and
W6 runs on what exists at the deadline. The split is by person-id hash, so a partial run still
gives lessons/practice/exam.

## Smoke run before it (data/smoke, 1 person, 20 chats, seed 1)

- First attempt with prompts v0.1 failed: the 4B model returned `{"day": 3}` entries without
  `text` (3 completions, all invalid). Fix: strict JSON schemas sent as
  `response_format: {"type": "json_schema", ...}`, which llama-server compiles to a grammar
  (probed and verified 2026-10-16), plus a numbered difficulty list in the prompt.
- Second attempt (v0.2): 1 person, 3 threads, 20 chats, 5 calls, 5 completions (no retries),
  66 s, 18.2 chats/min, 11.6 tok/s, 766 completion tokens, 2131 prompt tokens.
- validate: 20 -> 20 chats, 0 exact / 0 near duplicates. split: 1 person -> lessons (practice and
  exam empty, as expected with one person). tasks: 20 examples, answers none 9 / loose 3 / bundle
  8, candidates mean 5.7 max 9.

## Throughput watch

- 18:12-18:14 IST (2 min in): 0 people written yet (a 60-chat person is 5-7 completions, so the
  first ones land after several minutes). llama-server's log shows all four slots decoding at
  3.9-4.9 tok/s each (`tg_3s` 4.9-5.1), about 19-20 tok/s aggregate, with a load average of 12-15
  from the other agents on the Mac. The smoke run cost 38 completion tokens per chat, so the
  expected rate is roughly 30 chats/min aggregate, i.e. about 1,600 chats in 55 minutes if nothing
  retries; the ~600-chat floor for W6 is far below that.
- 18:20 IST (8.6 min in): first person written, p42-003: 5 threads, 60 chats, 7 calls, 7
  completions (no JSON retries), 519 s wall, 1,979 completion tokens, 3.8 tok/s on its slot,
  6.9 chats/min per worker; 12.6 KB. llama-server's log counted 21 completions in the first 8.5
  min across the four slots (mean 865 tokens each incl. prompt). With four workers that is about
  28 chats/min aggregate: roughly 6 rounds of 4 people in 55 minutes, so expect 20-24 people and
  1,200-1,450 chats by the deadline (people still in flight at 55 min get 5 min grace, the rest
  are dropped). Above the ~600-chat floor; W6 runs on whatever exists at the deadline either way.
- Check progress with `cat data/generate.log` (one line per person) or `ls data/raw/people | wc -l`.
