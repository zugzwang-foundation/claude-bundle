# Reaching the DGX Spark from the Mac

> **WRITTEN IN BDL-3, NEVER RUN YET. VERIFY ON THE SPARK IN BDL-4.**

Status: DRAFT (BDL-3). Everything here comes from docs/research/dgx-spark.md (R6),
sections "Reaching it from the Mac", "Running overnight" and the BDL-4 checklist,
checked 16 Oct 2026. Placeholders in angle brackets; no real addresses anywhere.
`<user>` is the Spark's one account (R6 suggests a non-personal name such as `bundle`);
`<spark-host>` is the name the Spark gets at first boot, of the form `spark-xxxx.local`
on the LAN (R6). Never write an IP address into a file: DHCP drifts (R6).

## 1. On the LAN, day one: plain SSH over mDNS

The Spark announces itself over mDNS as `<spark-host>` (R6, NVIDIA's connect playbook).
This works only on the same network; see section 3 for everywhere else.

Once, from the Mac, copy a key (R6 checklist item 5; the Mac's key pair is assumed to exist):

```sh
ssh-copy-id <user>@<spark-host>      # the one time a password is typed; after this it is keys
```

Then add a `Host` block to `~/.ssh/config` on the Mac (R6, Claude Code step 2), so that
`ssh spark` is enough and idle tunnels do not drop. R6 names only `ServerAliveInterval 60`;
the other two lines are ordinary OpenSSH options added here:

```
Host spark
  HostName <spark-host>
  User <user>
  ServerAliveInterval 60
  ServerAliveCountMax 3
  IdentitiesOnly yes
```

Verify, non-interactively: `ssh -o BatchMode=yes spark true && echo ok`.

## 2. Make the Spark safe to leave alone (once, over SSH)

From R6's hardening step (idempotent):

```sh
ssh spark 'sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target'
ssh spark 'sudo apt install -y tmux'
# optional, drops the desktop (R6):
ssh spark 'sudo systemctl set-default multi-user.target'
```

Headless Sparks have suspended after about twenty minutes when nobody is logged in
(forum reports via R6); masking the targets is the fix R6 quotes. `00-check.sh` checks
this. The `sudo` lines need a password unless passwordless sudo is set up on the Spark;
run them from an interactive terminal, not from a script.

## 3. Away from home: Tailscale (optional, Hrishikesh's account)

R6's recommendation for everything off the LAN. It needs a free Tailscale Personal
account (R6: "Up to 6 users", basic Tailscale SSH on up to 5 hosts), created by
Hrishikesh, with MagicDNS turned on (R6 checklist item 4). Nothing here spends money.

1. Mac: install the standalone Tailscale client (R6 recommends the standalone build over
   the App Store one) and sign in.
2. Spark: NVIDIA's `playbook-tailscale` installs Tailscale from the Ubuntu noble
   repository and runs OpenSSH over the tailnet. The exact apt lines are in that
   playbook (R6, source 53: github.com/NVIDIA/dgx-spark-playbooks, `nvidia/playbook-tailscale`);
   they are not copied here. NOT VERIFIED beyond R6's summary.
3. Spark: `sudo tailscale up --ssh`. It prints a URL; Hrishikesh approves it in the browser
   (R6). `--ssh` turns on Tailscale SSH, which replaces keys with the tailnet identity,
   claims port 22 only on the Tailscale address and leaves LAN SSH alone (R6).
4. Mac: a second `Host` block, so the LAN block keeps working at home:

```
Host spark-ts
  HostName <spark-host>        # the MagicDNS name; the same short name usually resolves
  User <user>
  ServerAliveInterval 60
```

Verify: `ssh -o BatchMode=yes spark-ts true`. Without a Tailscale account, Claude Code can
work on the Spark only from home (R6, point 6).

NVIDIA Sync (a macOS `.dmg`) is R6's GUI fallback: it adds the device by hostname with the
account password ("not logged or stored"), opens a terminal and the DGX Dashboard, adds the
user to the docker group and supports Tailscale. Optional.

## 4. Long runs: tmux

SSH sessions drop; tmux keeps the shell. It does not survive a reboot, which is why the
nightly loop belongs under systemd (`30-nightly.*`) once it has worked by hand (R6).

```sh
ssh spark
tmux new -s bundle                  # first time
  ~/bundle/scripts/spark/00-check.sh
  ~/bundle/scripts/spark/10-serve-teacher.sh
  PEOPLE=20 GEN_TIME_BUDGET_MIN=30 ~/bundle/scripts/spark/20-run-loop.sh
# detach: Ctrl-b then d.   Later:
ssh spark -t tmux attach -t bundle
```

## 5. Tunnels

The teacher is bound to `127.0.0.1:8081` on the Spark and never exposed (R6, `10-serve-teacher.sh`).
To drive it from the Mac, so that the same pipeline code runs against the Spark's teacher (D9):

```sh
ssh -N -L 8081:127.0.0.1:8081 spark &      # background tunnel; kill it when done
cd pipeline && BUNDLE_TEACHER_URL=http://127.0.0.1:8081/v1 BUNDLE_TEACHER_MODEL=nvidia/Qwen3.6-35B-A3B-NVFP4 uv run bundle-pipeline generate --people 1 --time-budget-min 5
```

The DGX Dashboard, the same way (R6): `ssh -L 11000:localhost:11000 spark`, then
`http://localhost:11000` on the Mac. Never click *Update* there during a run: it reboots
the box (R6).

## 6. Getting the data back

R6, step 13: rsync the generated data to the Mac daily; the data is the product. The Spark
clones the repository over HTTPS and does not push (R6's safe default, Hrishikesh's call);
the Mac commits what should be committed (scoreboard JSON, nothing generated).

`<clone>` is the Mac's checkout of this repository.

```sh
rsync -az --info=progress2 spark:bundle/pipeline/data/ <clone>/pipeline/data/spark/
rsync -az spark:bundle/scoreboard/runs/ <clone>/scoreboard/runs/
rsync -az spark:bundle/runs/ ~/Downloads/zz_spark_runs/        # logs, outside the repository
```

The copy lands inside `pipeline/data/`, which the repository's `data/` rule ignores (a
sibling such as `data-spark/` would not be); on the Mac, point the pipeline at it with
`--data-root data/spark`. Check with `git status` before committing: only the scoreboard
JSON is meant to be committed. The sealed exam file is never read, only copied and hashed
(R3's exam rules, D7).

## 7. The morning after a night run (R6, step 12)

```sh
ssh spark 'journalctl --user -u 30-nightly --since yesterday | tail -40'
ssh spark 'last -x reboot | head'                       # a reboot in the night = apply R6's mitigations in order
ssh spark 'journalctl -k --since yesterday | tail -20'  # kernel messages: RCU stalls, thermal stops
ssh spark 'cat ~/bundle/runs/*/status.tsv | tail -12'
ssh spark 'wc -l ~/bundle/pipeline/data/validated/people.jsonl'
ssh spark 'docker logs --tail 20 bundle-teacher'
```

## 8. Rules that apply here

- No secret in the repository (CLAUDE.md). No token is needed for the ungated models used;
  if one is ever added it goes in `~/.config/bundle/env` on the Spark, mode 600 (R6).
- No real hostnames or addresses in any committed file; `Host` blocks live in `~/.ssh/config`
  on the Mac, not here.
- The Spark does not push to GitHub (R6 safe default) unless Hrishikesh decides otherwise.
- Nothing is published from the Spark: scoreboard runs are copied to the Mac and go through a
  pull request like everything else (D7, D13).
