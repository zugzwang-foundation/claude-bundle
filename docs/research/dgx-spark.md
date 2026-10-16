# NVIDIA DGX Spark for Bundle

Status: DRAFT — research note, 2026-10-16.

## The question

The relay names an NVIDIA DGX Spark as Bundle's later compute and asks what it is,
what runs on it, how Claude Code reaches it from the Mac, how to run it overnight,
and what goes wrong. The question underneath is narrower: can one Spark serve an
open teacher model fast enough to write tens of thousands of invented chats a night,
and train the student, with nobody sitting next to it? Nothing here was run on a
Spark today (out of scope for BDL-3), and whether a unit is on hand is unknown.

## Findings

### Hardware

- GB10: Blackwell GPU with 6,144 CUDA cores plus a 20-core Arm CPU (10 Cortex-X925
  + 10 Cortex-A725). 128 GB LPDDR5x unified between CPU and GPU, 256-bit, 273 GB/s.
  1 TB or 4 TB self-encrypting NVMe. Ports: 4x USB-C (one carries power), HDMI 2.1a,
  10 GbE RJ-45, 2x QSFP (ConnectX-7), Wi-Fi 7, Bluetooth 5.4. 240 W external supply,
  140 W of it for the SoC. 150 x 150 x 50.5 mm, 1.2 kg. Marketing: 1 PFLOP FP4 with
  sparsity, models to 200B. Page dated 10 Sep 2026 (checked 16 Oct 2026) [1].
- Compute capability 12.1 (sm_121), not the RTX 5090's 12.0 or B200's 10.0
  (checked 16 Oct 2026) [2]. Generic "Blackwell" guides that build for 12.0 miss.
- A 64 GB variant "starting at $4,999" ships from six OEMs (Acer, ASUS, Dell,
  Gigabyte, HP, MSI) on 23 Oct 2026 (NVIDIA blog, 2 Oct 2026, checked 16 Oct 2026)
  [3]; NVIDIA's product page shows no 128 GB price today: unknown [4]. Bundle needs
  the 128 GB model: a 70B teacher at NVFP4 or a 30B at BF16 needs the headroom.
- Measured: about 100 TFLOPS BF16 against 273 GB/s, so a Spark "reads prompts 13 to
  41 times faster than it writes". Single-user decode 18–95 tok/s by model and task
  (Qwen3.6-35B NVFP4 95 tok/s alone and 317 tok/s total across eight users;
  Qwen3.8-27B 23–52). Idle 22–25 W, serving 60–100 W (exolabs handbook, 25 Sep
  2026, checked 16 Oct 2026) [5].
- Batched throughput, the figure that matters for synthetic data: Llama 3.1 8B FP4
  924 tok/s at 128 concurrent requests, Qwen3 Coder 30B-A3B FP8 483 tok/s at batch
  64, Mistral Small 3.1 24B FP8 320 tok/s at 128 concurrency (StorageReview, 14 Oct
  2025, launch software, checked 16 Oct 2026) [6]. A year old. The January 2026
  update is credited with up to 2.5x on prefill and batch work but only about 1.4x
  on decode [7], and the Sep 2026 handbook's 317 tok/s for eight users on a 35B MoE
  [5] sits in the same range: plan on these numbers, not on doubling them.

### OS and software stack

- DGX OS 7.5.0 is the July 2026 release (page dated 10 Sep 2026): kernel 6.17,
  driver 580.159.03, CUDA 13.0.2; releases run Nov 2025 to Jul 2026. Notable: Jan
  2026 ConnectX-7 hot-plug (18 W saving), Jul 2026 better OOM handling and a 2/4 GB
  display-memory BIOS setting (release notes, checked 16 Oct 2026) [8]. The Ubuntu
  24.04 server base is stated in the porting guide, not the release notes [9].
- Preinstalled: Docker with the NVIDIA container runtime, cuDNN, NCCL, TensorRT,
  TensorRT-LLM, Nsight, CUDA 13.0 (porting guide, 24 May 2026, checked 16 Oct 2026)
  [9]. A community guide reports Miniforge and an importable PyTorch out of the box
  [10]; not on NVIDIA's pages, so unverified.
- NVIDIA's known issues (10 Sep 2026): use the supplied adapter or risk reduced
  performance, boot failure or unexpected shutdown; `nvidia-smi` shows "Memory-Usage:
  Not Supported" on this iGPU; `cudaMemGetInfo` under-reports free memory, workaround
  `sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'` then restart the app; newest
  CUDA features arrive via NGC containers, not the base OS (checked 16 Oct 2026) [11].
- Updates: NVIDIA "strongly recommend[s]" the DGX Dashboard (localhost:11000); manual path
  `sudo apt update && sudo apt dist-upgrade`, `sudo fwupdmgr refresh`, `sudo fwupdmgr upgrade`,
  `sudo reboot`. Dashboard updates end in a reboot [12][13]. unattended-upgrades on? unknown.

### NVIDIA's own guides

- Playbooks live at build.nvidia.com/spark and github.com/NVIDIA/dgx-spark-playbooks
  (Apache-2.0) [14][15]: vllm, sglang, llama-cpp, ollama, unsloth, pytorch-fine-tune,
  nemo-fine-tune, llamafactory, connect-to-your-spark, playbook-tailscale, playbook-dgx-dashboard,
  playbook-vscode, clustering [15]. Each repeats: unified memory looks full when it is not; flush caches.

### Serving a teacher: vLLM, SGLang, llama.cpp, Ollama

- vLLM playbook: `nvcr.io/nvidia/vllm:26.05-py3` (no `.post1` tag exists in the
  playbook or in NVIDIA's vLLM release index, which lists 25.09 to 26.09 [61]), run
  as `docker run -it --gpus all -p 8000:8000 <image> vllm serve <model>`. Models
  shown: Llama-3.3-70B NVFP4, Gemma 4 31B NVFP4, Nemotron-3-Nano-30B BF16/FP8,
  Nemotron-3-Super-120B NVFP4, Qwen3-32B NVFP4; BF16, FP8, NVFP4, MXFP4, INT4 and
  AWQ supported. Most recipes use `--gpu-memory-utilization 0.8`. The Qwen3.6-35B
  recipe runs upstream `vllm/vllm-openai:latest`, not the NGC image, with
  `--gpu-memory-utilization 0.4`, `--kv-cache-dtype fp8`, `--attention-backend
  flashinfer`, `--max-num-seqs 4` and MTP speculative decoding; Gemma 4 also needs
  an upstream image. Even two Sparks give a "405B model ... insufficient memory
  headroom" (checked 16 Oct 2026) [16].
- NGC vLLM 26.09 (15 Oct 2026): vLLM 0.29.0, CUDA 13.4.1, Python 3.12. Its notes
  say vLLM "uses aggressive GPU memory allocation by default" on unified memory and
  recommend `--gpu-memory-utilization 0.7`; NVFP4 Nemotron on Spark needs
  `--max-num-seqs 4` [17]. Whether a CUDA 13.4 container runs on DGX OS 7.5.0's 580
  driver is unknown; start from the 26.05-py3 image the playbook names.
- Upstream vLLM: 0.31.0 on PyPI (5 Oct 2026), Apache-2.0, Python 3.10–3.14, with a
  "Linux glibc 2.28+ ARM64" wheel [18]; docs recommend `uv pip install vllm
  --torch-backend=auto` then `vllm download-kernels`, and warn kernel builds are slow
  "especially Blackwell"; no GB10 mention [19]. Fourteen-day pin: 0.30.0 (22 Sep) [18].
- SGLang playbook: `lmsysorg/sglang:latest-cu130`, `--attention-backend flashinfer
  --mem-fraction-static 0.75`, NVFP4 needs `--quantization modelopt_fp4` [20]. PyPI 0.5.22
  (16 Oct 2026), Apache-2.0, Python 3.11+ [21]. A second horse; nothing vLLM lacks for Bundle.
- llama.cpp playbook: build with `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=121a-real`
  (5–10 min), `llama-server -hf unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q4_K_XL`; wrong
  arch is the usual build error [22]. MIT [23]. Quick checks; batch speed unknown.
- Ollama playbook: `curl -fsSL https://ollama.com/install.sh | sh`, port 11434 over an SSH
  tunnel [24]. MIT [25]. Latest v0.40.5 is from 15 Oct 2026, too new to pin [26]. The playbook
  catalogue positions Ollama for ease and vLLM for "high-throughput and batch inference" [27].

### Fine-tuning tooling

- Official aarch64 CUDA wheels exist: `torch-2.14.1+cu130-cp312-cp312-
  manylinux_2_28_aarch64.whl` and cp310–cp315 siblings at
  download.pytorch.org/whl/cu130 [28]; 2.14.1 dates from 30 Sep 2026 [29].
- The pitfall is real: on aarch64, `pip install torch` or a plain `uv sync` resolves the
  CPU-only wheel ("2.10.0+cpu") and Unsloth dies with "cannot find any torch accelerator"
  (unsloth-cli issue 9, 26 Jun 2026) [30]. uv's fix: an explicit `[[tool.uv.index]]` named
  `pytorch-cu130` at `https://download.pytorch.org/whl/cu130` with `explicit = true`, and
  `[tool.uv.sources]` routing `torch` to it under `sys_platform == 'linux'`, PyPI on macOS [31].
- NVIDIA's answer is containers: pytorch-fine-tune uses `nvcr.io/nvidia/pytorch:25.11-py3`
  with `--ipc=host` and pip-installs transformers, peft, datasets, trl, bitsandbytes inside
  [32]. 25.11: PyTorch 2.10.0a0, CUDA 13.0.2, Python 3.12 [33]. 26.09: PyTorch 2.14.0a0,
  CUDA 13.4.1, FlashAttention 4 beta, support matrix says "x86, Arm SBSA" [34][35].
- Unsloth on the Spark is a Dockerfile, not pip: base `nvcr.io/nvidia/pytorch:25.09-py3`,
  pins `bitsandbytes==0.48.0`, `transformers==4.56.2`, `trl==0.22.2`, Triton from a pinned
  commit, xformers with `TORCH_CUDA_ARCH_LIST="12.1"`; gpt-oss-120b QLoRA about 68 GB [36].
  Unsloth's generic Blackwell page says arch "12.0" and "Do not upgrade triton on its own"
  [37]. Licence Apache-2.0 core, AGPL-3.0 Studio UI; 2026.10.6 is from 15 Oct [38]. No arm64 image [39].
- Hugging Face, all Apache-2.0: TRL 1.16.0 (15 Oct; pin 1.14.1 of 29 Sep) [40][41],
  PEFT 0.21.2 (1 Oct) [42], transformers 5.20.0 (15 Oct; pin 5.18.0 of 30 Sep) [43].
  bitsandbytes 0.50.2 (27 Aug) is MIT and ships a `manylinux_2_24_aarch64` wheel;
  whether it carries sm_121 kernels is unknown, and it only matters for QLoRA [44].
- Community wheels: flash-attn 2.8.3.post1 for cp312 aarch64 against torch 2.12.0+cu130,
  no licence stated [45]; a GB10 index with flash-attn, sageattention, flashinfer and torch
  2.13 on CUDA 13.3 [46]. Only if a profiler says attention is the bottleneck; it will not be.
- Independent reports: full fine-tune of Llama 3.1 8B used about 45 GB and 2 hours for
  10K samples x 3 epochs, Unsloth LoRA about 1 hour (1 Apr 2026) [47]; Kaitchup (17 Oct
  2025) sees the fit as "fine-tuning and small-scale training, especially for models under ~8B" [48].

### Reaching it from the Mac

- First boot can be headless: the Spark starts "immediately when power is applied",
  opens a Wi-Fi hotspot, the Quick Start sticker carries the credentials and a browser
  finishes setup; if that fails, plug in a display. Updates may reboot more than once [49].
- NVIDIA Sync is NVIDIA's macOS client (.dmg): add the device by hostname or IP with
  username and password, "not logged or stored"; it opens a terminal, the DGX Dashboard
  and a resource monitor, adds the user to the docker group, supports Tailscale [50][51].
- Plain SSH: `ssh <user>@spark-xxxx.local` over mDNS; DGX Dashboard via `ssh -L
  11000:localhost:11000` [52]. mDNS is link-local and DHCP drifts: no hardcoded IP [10].
- Tailscale: NVIDIA's playbook installs it from the Ubuntu noble repo and runs
  OpenSSH over the tailnet [53]. Tailscale SSH (`tailscale set --ssh`) replaces keys
  with identity, claims port 22 only on the Tailscale address, and leaves LAN SSH
  alone; macOS is a client, and a server only with open-source `tailscaled` [54].
  Personal plan: free, "Up to 6 users", basic Tailscale SSH on up to 5 hosts [55].
  Client BSD-3-Clause [56]; standalone Mac build recommended [57].

### Running overnight

- Sleep: NVIDIA's docs are silent on defaults (unknown). Forum threads report headless
  Sparks suspending after about 20 minutes because the GDM greeter's power profile
  applies when nobody is logged in; quoted fixes are `gsettings ... sleep-inactive-ac-type
  'nothing'` as the gdm user and `sudo systemctl mask sleep.target suspend.target
  hibernate.target hybrid-sleep.target`; another thread says newer DGX OS ships a systemd
  drop-in disallowing suspend [58]. Search snippets only (forum returns 403). Mask anyway.
- Long jobs: tmux or a systemd unit with `Restart=on-failure`, journald logs, and `sudo
  systemctl set-default multi-user.target` to drop the desktop; a community guide caps
  `user.slice` at `MemoryMax=120G` with systemd-oomd [10]. Sensible, not NVIDIA-blessed.
- Power and heat: idle 22–25 W, serving 60–100 W; stand units on their sides to run
  cooler; about $12 a month at 18 cents per kWh [5].

### Pitfalls reported by users

- Hard power-offs and freezes under sustained GPU load are the recurring forum topic:
  "hardware crashes at around 75W", "hard freeze under sustained load (RCU stall)",
  "Shutdown around 95°C during nanoChat Pretraining (20-30 min)", a unit that "now
  reliably shut off after about 20 minutes". Quoted workarounds: a clock cap `nvidia-smi
  -lgc 300,2100` (one thread: `300,2200`), cleaning dust, ambient 5–30 °C; the ~95 °C
  stop is called protective, not random [59]. Snippets only (403); eight titles confirmed.
- USB-C PD wedge: a brick firmware fault pins the GPU at 611 MHz and 13–16 W; fix is a
  cold drain (shut down, unplug wall and unit, hold power 30 s, wait 60 s), then `fwupdmgr`
  update and a second drain; affects NVIDIA and partner units alike (community doc,
  author-verified 19 May 2026) [60]. Hackernoon (26 Feb 2026) relays a 2025 report of power
  "maxing out at 100W instead of the rated 240W" and reboots in long runs before the January update [7].
- Community kernel patches in the curated list: a "2200 MHz clock cap" that ran
  "12 °C cooler at 36% less GPU-rail power", a vLLM spin-wait patch worth "24 °C
  lower average SoC temperature", DeepSpeed patched compute_121 to compute_120 [46].
- Storage: StorageReview's M.2 "would lock up and require re-imaging" under a
  synthetic heavy-IO test [6]. One report, launch firmware; back data up off the box.
- Playbooks assume `HF_TOKEN` for gated models; the Qwen3.6-35B recipe says a token is
  required [16]. Bundle skips gated models, so none is needed; any token stays off the repo.

## Options compared

| Choice | Option | Fits Bundle? | Licence | Why / why not |
|---|---|---|---|---|
| Teacher serving | vLLM in NGC container 26.05-py3 | Yes, first choice | vLLM Apache-2.0; NGC container under NVIDIA's container licence | NVIDIA's own recipe, batched OpenAI-compatible API, NVFP4/FP8, UMA-tuned flags [16][17] |
| Teacher serving | vLLM 0.30.0 from PyPI in uv venv | Maybe later | Apache-2.0 | ARM64 wheel exists [18]; slow Blackwell kernel build [19]; no GB10 recipe |
| Teacher serving | SGLang container | Works, second | Apache-2.0 | Same class as vLLM, fewer Spark notes [20] |
| Teacher serving | llama.cpp built for 121a | Quick checks only | MIT | 10-minute build, GGUF, single-user speed fine [22]; batch throughput unknown |
| Teacher serving | Ollama | No for bulk | MIT | Easiest install, positioned for ease not throughput [24][27] |
| Training stack | uv venv + torch 2.14.1+cu130 aarch64 | Yes for the student | BSD-style (PyPI expression lists Apache-2.0, BSD, MIT parts) | Official wheels [28]; needs the explicit index block [31]; same pyproject as the Mac |
| Training stack | NGC pytorch:25.11 / 26.09 container | Fallback | NVIDIA container licence | NVIDIA's path [32]; heavier; only if a wheel is missing |
| Training stack | Unsloth Dockerfile | Only if R2 fine-tunes a decoder | Apache-2.0 core | Self-built arm64 image [36]; irrelevant to an encoder student |
| Remote access | LAN SSH over mDNS | Yes, day one | n/a | Zero setup; link-local only [52][10] |
| Remote access | NVIDIA Sync (.dmg) | Optional | NVIDIA | GUI, docker group, tunnels [50][51] |
| Remote access | Tailscale + OpenSSH or Tailscale SSH | Yes, away from home | BSD-3 client; free Personal plan | NVIDIA's own playbook [53]; identity-based SSH [54][55] |
| Overnight | tmux | Minimum | n/a | Survives SSH drops, not crashes |
| Overnight | systemd unit, Restart=on-failure, resumable job | Yes | n/a | Survives the power-offs users report [59][10] |

## Recommendation

Run the teacher as a batched vLLM server in NVIDIA's NGC container
(`nvcr.io/nvidia/vllm:26.05-py3`, moving to a newer tag only once it is 14 days old
and proven on the 580 driver), with `--gpu-memory-utilization 0.7`, a high
`--max-num-seqs`, bound to localhost and reached over SSH or the tailnet, driven by
a resumable generation script under a systemd unit that restarts on failure and
appends JSONL with stable ids. Train the student in the project's own uv environment
with the official `torch 2.14.1+cu130` aarch64 wheel pinned through an explicit uv
index, skip Unsloth and NGC PyTorch containers unless R2 chooses to fine-tune a
decoder, and reach the box from the Mac with plain SSH on the LAN plus Tailscale
(free Personal plan, `tailscale set --ssh`) for everything else. Licences: vLLM
Apache-2.0, torch BSD-style, TRL/PEFT/transformers Apache-2.0, Tailscale client
BSD-3. The teacher model itself is R3's choice and must be ungated with a licence
that permits training on its outputs; the playbook's headline examples (Llama 3.3,
Gemma 4) are gated and are not recommended here.

Why: decode is memory-bound at 273 GB/s, so single-stream speed is ordinary (roughly
20–95 tok/s) and only batching makes the Spark a data factory. At the year-old 320–480
tok/s for 24–30B models, eight hours yields roughly 9–14 million output tokens, about
20,000–35,000 invented chats of 400 tokens; the Sep 2026 handbook's 317 tok/s for eight
users is in the same range, so do not bank on more until it is measured. Ollama cannot
do that. Unsloth is a decoder-LLM tool and the student is a small encoder. And the
stability reports mean "run overnight" must survive a hard power-off, not hope for a clean night.

Pins at BDL-4 (all at least 14 days old today): torch 2.14.1+cu130, transformers 5.18.0,
peft 0.21.2, trl 1.14.1, vllm container 26.05-py3 (or PyPI 0.30.0); pin uv's installer URL.

## What doesn't work, or would change the plan

1. The relay's "fine-tuning tooling (Unsloth)" points the wrong way. Unsloth is for
   decoder LLMs and on the Spark it is a self-built image [36]. The student is an
   encoder; PyTorch in uv is enough. If R2 does fine-tune a small decision model,
   NVIDIA's pytorch-fine-tune playbook with TRL and PEFT is simpler [32].
2. "vLLM, SGLang, Ollama or llama.cpp" are not four equal options. Bulk generation
   is vLLM; the rest are conveniences. R3 should size a night's output from batched
   throughput, not tokens-per-second headlines.
3. The Spark is not yet a reliable overnight appliance. Eight threads describe hard
   power-offs or thermal stops under sustained load, plus two documented
   power-delivery faults [59][60][7]. Every long job must be resumable and run under
   systemd; the first night is a stability test. If it trips, the quoted mitigations
   (clock cap, cold drain, firmware, airflow) cost 5–36% of GPU power: acceptable.
4. Plain `uv sync` on the Spark installs CPU-only torch [30]. The pyproject W3
   writes today should already carry the cu130 index block [31].
5. Unified memory lies to allocators. Expect "out of memory" with free RAM; drop
   caches, restart, keep `--gpu-memory-utilization` at or below 0.7 [11][17].
   Budget 100–110 GB for teacher plus KV cache, not 128.
6. The home network decides more than the box. mDNS fails off-LAN and DHCP drifts;
   without a Tailscale account (Hrishikesh's decision) Claude Code can only work on
   the Spark from home, with NVIDIA Sync as the GUI fallback.
7. A 64 GB Spark would change the plan: no 70B teacher, 30B at NVFP4 at best. If not
   yet bought, buy 128 GB and 4 TB; teacher checkpoints run 20–70 GB each. Unknown:
   the 128 GB price, and whether CUDA 13.4 NGC images run on the 580 driver.
8. Pin only tags seen in the NGC catalogue. This note's first draft pinned
   `26.05.post1-py3`, which does not exist [16][61]; a bad tag fails the first
   `docker pull` of the night. Confirm the tag with `docker pull` before relying on it.
9. The 2.5x story is prefill, not decode [7]. If the first measured batched run is
   under 300 tok/s on a 30B-class teacher, a night is 15,000–20,000 chats, and R3's
   data budget must shrink or the teacher must get smaller.

## BDL-4 setup checklist

### For Hrishikesh (physical, accounts, network)

1. Place the Spark where air moves, on its side as the handbook suggests, away from
   dust, in a room between 5 and 30 °C. Use only the supplied 240 W adapter. Wire it
   to the router by Ethernet; Wi-Fi is the fallback, not the plan.
2. First boot: plug in a display and keyboard, or join the Spark's hotspot from the
   Mac with the sticker credentials and finish in the browser. Create one account
   with a non-personal username (for example `bundle`) and a password kept in your
   manager. Let it update and reboot (10–20 minutes). Note the `spark-xxxx` hostname.
3. Optional: install NVIDIA Sync (.dmg) on the Mac for the GUI.
4. Create a free Tailscale Personal account, install the standalone Mac client and sign in.
   When Claude Code runs `sudo tailscale up --ssh` it prints a URL: approve it. Turn on MagicDNS.
5. Once, from the Mac: `ssh-copy-id bundle@spark-xxxx.local`; after that it is keys.
6. No Hugging Face token is needed (ungated models only). If you ever add one it
   goes in `~/.config/bundle/env` on the Spark, mode 600, never the repository.
7. Decide if the Spark may push to GitHub; safe default no: it clones over HTTPS, the Mac pushes.
8. Never click Update in the DGX Dashboard during a run (it reboots); agree a maintenance window.

### For Claude Code (commands, in order)

1. `date -u`, then over SSH: `lsb_release -a; uname -r; nvidia-smi; nvcc --version;
   docker --version; free -g; df -h /`; record OS, driver, CUDA in docs/DECISIONS.md.
2. Add a `Host spark` block to `~/.ssh/config` on the Mac with `ServerAliveInterval
   60`; verify `ssh spark true`.
3. Headless hardening, idempotent: `sudo systemctl mask sleep.target suspend.target hibernate.target
   hybrid-sleep.target`; optionally `sudo systemctl set-default multi-user.target`; `sudo apt install -y tmux`.
4. Tailscale: NVIDIA's apt steps for Ubuntu noble, then `sudo tailscale up --ssh`;
   hand the URL to Hrishikesh; verify `ssh bundle@spark-xxxx` over the tailnet.
5. Install uv pinned: `curl -LsSf https://astral.sh/uv/<version>/install.sh | sh`.
   Clone the repository over HTTPS into `~/bundle`.
6. Confirm the pyproject carries the explicit `pytorch-cu130` index; `uv sync`; then
   `uv run python -c "import torch; print(torch.__version__,
   torch.cuda.is_available(), torch.cuda.get_device_capability())"` and expect
   `2.14.1+cu130 True (12, 1)`. A `+cpu` means stop and fix the index.
7. Run BDL-3's toy loop unchanged (lessons, student, exam) and compare the
   scoreboard with the Mac run: same numbers or a logged reason.
8. `docker run --rm --gpus all nvcr.io/nvidia/vllm:26.05-py3 vllm --version`. If
   the pull demands a login, that is an NGC account: log it under Needs Hrishikesh
   and fall back to PyPI vLLM 0.30.0 in uv.
9. Serve the teacher R3 chose: `sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'`,
   then `docker run -d --name teacher --gpus all --ipc=host -p 127.0.0.1:8000:8000
   -v $HOME/.cache/huggingface:/root/.cache/huggingface nvcr.io/nvidia/vllm:26.05-py3
   vllm serve <model> --gpu-memory-utilization 0.7 --max-num-seqs 64 --max-model-len
   8192`; check `curl -s localhost:8000/v1/models`.
10. Measure, do not assume: 15-minute batched runs at concurrency 16, 32 and 64,
    logging output tok/s, `nvidia-smi -q -d TEMPERATURE,POWER,CLOCK` each minute and
    `journalctl -k`. Write the numbers into this file.
11. Install the generation driver as a systemd unit (`Restart=on-failure`,
    `RestartSec=30`, `WorkingDirectory=/home/bundle/bundle`, ExecStart via `uv run`)
    writing JSONL with stable ids so a restart resumes. Logs: `journalctl -u bundle-gen -f`.
12. First overnight is a stability test: `sudo systemctl enable --now bundle-gen`; next
    morning check `journalctl -u bundle-gen --since yesterday | tail`, `last -x reboot
    | head` and the JSONL line count. A reboot means apply the mitigations in order
    (airflow and dust; `fwupdmgr` with cold drain; `nvidia-smi -lgc 300,2100`) and rerun.
13. `rsync` generated data to the Mac daily; the data is the product.

## Sources

1. https://docs.nvidia.com/dgx/dgx-spark/hardware.html (checked 16 Oct 2026)
2. https://developer.nvidia.com/cuda-gpus (checked 16 Oct 2026)
3. https://blogs.nvidia.com/blog/local-ai-dgx-spark-64gb-sync/ (checked 16 Oct 2026)
4. https://www.nvidia.com/en-us/products/workstations/dgx-spark/ (checked 16 Oct 2026)
5. https://huggingface.co/blog/exolabs/the-dgx-spark-handbook (checked 16 Oct 2026)
6. https://www.storagereview.com/review/nvidia-dgx-spark-review-the-ai-appliance-bringing-datacenter-capabilities-to-desktops (checked 16 Oct 2026)
7. https://hackernoon.com/i-was-ready-to-return-my-dgx-spark-then-nvidias-january-update-changed-everything (checked 16 Oct 2026)
8. https://docs.nvidia.com/dgx/dgx-spark/release-notes.html (checked 16 Oct 2026)
9. https://docs.nvidia.com/dgx/dgx-spark-porting-guide/porting/software-requirements.html (checked 16 Oct 2026)
10. https://raw.githubusercontent.com/yzhao062/agent-config/main/docs/dgx-spark-setup.md (checked 16 Oct 2026)
11. https://docs.nvidia.com/dgx/dgx-spark/known-issues.html (checked 16 Oct 2026)
12. https://docs.nvidia.com/dgx/dgx-spark/os-and-component-update.html (checked 16 Oct 2026)
13. https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/playbook-dgx-dashboard/README.md (checked 16 Oct 2026)
14. https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/LICENSE (checked 16 Oct 2026)
15. https://github.com/NVIDIA/dgx-spark-playbooks/tree/main/nvidia (checked 16 Oct 2026)
16. https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/vllm/README.md (checked 16 Oct 2026)
17. https://docs.nvidia.com/deeplearning/frameworks/vllm-release-notes/rel-26-09.html (checked 16 Oct 2026)
18. https://pypi.org/project/vllm/ and https://pypi.org/project/vllm/#history (checked 16 Oct 2026)
19. https://docs.vllm.ai/en/latest/getting_started/installation/gpu.html (checked 16 Oct 2026)
20. https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/sglang/README.md (checked 16 Oct 2026)
21. https://pypi.org/project/sglang/ (checked 16 Oct 2026)
22. https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/llama-cpp/README.md (checked 16 Oct 2026)
23. https://raw.githubusercontent.com/ggml-org/llama.cpp/master/LICENSE (checked 16 Oct 2026)
24. https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/ollama/README.md (checked 16 Oct 2026)
25. https://raw.githubusercontent.com/ollama/ollama/main/LICENSE (checked 16 Oct 2026)
26. https://github.com/ollama/ollama/releases.atom (checked 16 Oct 2026)
27. https://dev.classmethod.jp/en/articles/dgx-spark-playbooks-catalog/ (search snippet, checked 16 Oct 2026)
28. https://download.pytorch.org/whl/cu130/torch/ (checked 16 Oct 2026)
29. https://pypi.org/project/torch/#history (checked 16 Oct 2026)
30. https://github.com/agentculture/unsloth-cli/issues/9 (checked 16 Oct 2026)
31. https://docs.astral.sh/uv/guides/integration/pytorch/ (checked 16 Oct 2026)
32. https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/pytorch-fine-tune/README.md (checked 16 Oct 2026)
33. https://docs.nvidia.com/deeplearning/frameworks/pytorch-release-notes/rel-25-11.html (checked 16 Oct 2026)
34. https://docs.nvidia.com/deeplearning/frameworks/pytorch-release-notes/rel-26-09.html (checked 16 Oct 2026)
35. https://docs.nvidia.com/deeplearning/frameworks/support-matrix/index.html (checked 16 Oct 2026)
36. https://unsloth.ai/docs/basics/fine-tuning-llms-with-nvidia-dgx-spark-and-unsloth (checked 16 Oct 2026)
37. https://unsloth.ai/docs/blog/fine-tuning-llms-with-blackwell-rtx-50-series-and-unsloth (checked 16 Oct 2026)
38. https://pypi.org/project/unsloth/ (checked 16 Oct 2026)
39. https://unsloth.ai/docs/get-started/install/docker (checked 16 Oct 2026)
40. https://pypi.org/project/trl/ (checked 16 Oct 2026)
41. https://pypi.org/project/trl/#history (checked 16 Oct 2026)
42. https://pypi.org/project/peft/ (checked 16 Oct 2026)
43. https://pypi.org/project/transformers/#history (checked 16 Oct 2026)
44. https://pypi.org/pypi/bitsandbytes/json (checked 16 Oct 2026)
45. https://huggingface.co/N8Programs/dgx-flash-attn-wheel (checked 16 Oct 2026)
46. https://raw.githubusercontent.com/bidual/awesome-dgx-spark/main/README.md (checked 16 Oct 2026)
47. https://spark.enverge.ai/blog/fine-tune-llm-on-dgx-spark (checked 16 Oct 2026)
48. https://kaitchup.substack.com/p/dgx-spark-use-it-for-fine-tuning (checked 16 Oct 2026)
49. https://docs.nvidia.com/dgx/dgx-spark/first-boot.html (checked 16 Oct 2026)
50. https://docs.nvidia.com/dgx/dgx-spark/nvidia-sync.html (checked 16 Oct 2026)
51. https://build.nvidia.com/spark/connect-to-your-spark/sync (checked 16 Oct 2026)
52. https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/connect-to-your-spark/README.md (checked 16 Oct 2026)
53. https://raw.githubusercontent.com/NVIDIA/dgx-spark-playbooks/main/nvidia/playbook-tailscale/README.md (checked 16 Oct 2026)
54. https://tailscale.com/kb/1193/tailscale-ssh (checked 16 Oct 2026)
55. https://tailscale.com/pricing (checked 16 Oct 2026)
56. https://raw.githubusercontent.com/tailscale/tailscale/main/LICENSE (checked 16 Oct 2026)
57. https://tailscale.com/kb/1016/install-mac (checked 16 Oct 2026)
58. https://forums.developer.nvidia.com/t/is-sleep-suspend-disabled-by-default/377582 , .../nvidia-dgx-spark-automatically-suspends-when-running-headless-despite-power-config-changes/353777 and .../configure-dgx-so-it-does-not-go-into-power-standby-mode/375767 (search snippets only; forum returned HTTP 403 to the fetch tool, 16 Oct 2026)
59. https://forums.developer.nvidia.com/t/dgx-spark-system-hardware-crashes-at-around-75w-system-reboots-repeatedly-wattage-cap-workaround-found/380669 , .../dgx-spark-shutdown-around-95-c-during-nanochat-pretraining-20-30-min/358280 , .../dgx-spark-gb10-reproducibly-hard-powers-off-under-gpu-load-fully-updated-zero-crash-capture/373251 , .../spark-abruptly-shuts-down/377478 , .../gb10-abruptly-powers-off-under-heavy-gpu-load-nvidia-smi-lgc-300-2200-prevents-it/384492 , .../dgx-spark-gb10-partnerdiag-powerstress-reproducibly-hard-powers-off-the-box-acpitz-88-97-8-c-in-5s-all-other-field-tests-pass/377365 , .../dgx-spark-stability-out-of-ram-overheating/368536 , .../warranty-claim-dgx-spark-unit-defective/361657 (titles and search snippets only; HTTP 403, 16 Oct 2026)
60. https://raw.githubusercontent.com/Sggin1/DGX-SPARK/main/GX10_PD_Throttle_Fix.md (checked 16 Oct 2026)
61. https://docs.nvidia.com/deeplearning/frameworks/vllm-release-notes/index.html (checked 16 Oct 2026)

## Verification notes (skeptic)

Opened on 16 Oct 2026: [1] [2] [3] [5] [6] [7] [8] [9] [11] [14] [16] [17] [18] [21] [23]
[25] [26] [28] [29] [30] [31] [33] [34] [35] [36] [38] [40]–[44] [46] [47] [48] [54] [55]
[56] [60] [61]; [58] and [59] confirmed as thread titles by search only (forum 403).
Fixed: (1) `26.05.post1-py3` does not exist; the playbook uses `26.05-py3` and NVIDIA's
index lists 25.09–26.09 with no post1 [16][61]; replaced throughout, added point 8.
(2) DGX OS 7.5.0 is the July 2026 release, page dated 10 Sep; Ubuntu 24.04 is from [9].
(3) exolabs single-user decode is 18–95 tok/s, not 48–95; added 317 tok/s for eight
users [5]. (4) The Qwen3.6-35B recipe runs upstream `vllm/vllm-openai:latest`; most
recipes use utilisation 0.8 [16]. (5) bitsandbytes 0.50.2 ships an aarch64 wheel [44].
(6) Hackernoon's 100 W is a relayed 2025 report; its 2.5x is prefill, decode about 1.4x
[7]; softened "floor", added point 9. (7) Tailscale Personal: basic SSH, 5 hosts [55].
Unchanged after checking: [1] [2] [3] [6] [18] [21] [26] [28] [29] [33]–[36] [38]
[40]–[43] [60] and licences [14] [23] [25] [56]. Quotes under 15 words. No gated model.
