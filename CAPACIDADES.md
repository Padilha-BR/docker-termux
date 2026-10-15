# What this "Docker" on a phone can do, cannot do, and could do

**Português:** [leia em português](CAPACIDADES.pt-BR.md).

**Where it was measured:** Galaxy S24 Ultra, Android 16, arm64, kernel 6.1.145-android14-11
(GKI branch), **without root**.
Every number in this document came out of real execution on the device, not an estimate.
Where something was not tested, it says **"not tested"**.

---

## 1. What it CAN do (verified)

### 1.1 Container engine

| Feature | State | Note |
|---|---|---|
| `pull` an image from Docker Hub | ✅ | OCI layers checked by `sha256`, identical to the Hub's |
| `run` (foreground, background, TTY) | ✅ | container = a real process (`exe → proot`, rootfs mounted) |
| `build` a Dockerfile | ✅ | classic builder, `DOCKER_BUILDKIT=0` |
| `exec` into a live container | ✅ | through the daemon |
| `logs`, `stop`, `rm`, `ps` | ✅ | `logs` requires a TTY on the daemon (see §2.4) |
| Host volumes/binds | ✅ | `-v source:dest`, file **and** directory |
| Network (outbound) | ✅ | its own DNS (`8.8.8.8`) and working HTTPS |
| DNS resolved inside the container | ✅ | Android has no `/etc/resolv.conf`; it is injected |
| Image of **another** architecture (amd64) | ✅ slow | via `qemu-user-x86-64` |
| Alpine (**musl**) and Debian/Ubuntu (**glibc**) | ✅ | `apk` and `apt` installing |
| `pip` inside the container | ✅ | including Python 3.12 on Alpine |
| Persistence between runs | ✅ | images and containers live in `~/.udocker` |
| Official Docker CLI talking to the daemon | ✅ | API 1.41 |
| `proot-distro` (full distro, no daemon) | ✅ | the more direct alternative for "I want a Linux" |

### 1.2 What actually ran here (proof, not promises)

| Task | Measured result |
|---|---|
| **Manim** (video render) | Ubuntu 24.04 image + cairo/pango/ffmpeg; **h264 1280×720 30fps** video generated on the device in 30.9 s |
| **Markdown → PDF**, typeset | weasyprint in a container, cover/A4/emoji |
| **Plain HTTP** (level 1) | extracts text/links **natively in 1.7 s** (~34 MB); the same fetch through the container took 16 s |
| **Chromium headless** (level 2) | **native** (not in the container): static page **2.8 s**, SPA **4.7 s**, PNG, PDF |
| **Selenium + chromedriver** (level 3) | real click, wait for element, screenshot in **4.0-4.8 s** |
| **Raw CDP** (faster level 3) | reads the title, runs JS and takes a screenshot in **1.9-2.5 s**, no Selenium |
| `uname -m`, `apk add`, `apt-get install` | all exit 0 (the tests that catch the proot defects) |

---

## 2. What it CANNOT do, and why

### 2.1 Kernel Docker: impossible without root — and that is the limit of everything

`unshare -U true` → **`Invalid argument`**. Android does not hand *user namespaces* to
ordinary apps. Without a namespace there is no:

- real `dockerd` daemon
- cgroups (therefore **no** per-container CPU/memory limit)
- its own overlayfs, `docker network`, `docker volume` as objects
- real isolation: today **the container's network is Termux's network** — a service that
  comes up in the container is already on your port, and `-p` is ignored on purpose

What exists here is **userspace execution** (`proot` + udocker): the binary runs, but the
kernel isolates nothing. This is not a configuration limitation — it is the Android kernel.

### 2.2 Playwright: no Python wheel for Android — but it does work via Node

`pip install playwright` → `No matching distribution found` (there is no wheel for
Android/aarch64). For browser automation **in Python**, the route here is
**chromedriver + Selenium** (`selenium` is pure Python and installs normally).

**In Node it works** — measured, with two keys. See §3.6.3.

### 2.3 Chromium **inside the container** does not work

Tested exhaustively: Chrome for Testing 156 and `chrome-headless-shell` 156 (native arm64).
Symptoms: `Trace/breakpoint trap` (SIGTRAP), `Target crashed`, or an endless loop of
`crashpad ... tgkill: No such process`. `--no-sandbox`, `--single-process`, `--no-zygote`,
`--headless=old` and `GLIBC_TUNABLES=glibc.pthread.rseq=0` — **none of them work**.

**Cause (with the most likely hypothesis ruled out):** `proot` intercepts syscalls through
**ptrace**, and Chromium's crashpad also depends on ptrace/child processes. There was a
known alternative explanation — the `PartitionAlloc` bug on aarch64 with a **64 KB page
size** (which also gives SIGTRAP) — but on this device `SC_PAGE_SIZE` = **4096 bytes**, so
**that hypothesis is ruled out here**.

**The cure is not to use a container for this:** Termux's **native** Chromium
(`pkg install x11-repo && pkg install chromium`) runs on bionic, without proot, and
works — including with the JS rendered.

### 2.4 Daemon limits (udockerd 0.3.5)

Three gaps confirmed with controlled tests, all worked around by the dispatcher:

| Symptom | Cause |
|---|---|
| `pull` fails with `no image found in manifest for platform (android/arm64)` | udocker reports the platform as `android/arm64`; the Hub doesn't publish that |
| `docker run -v` mounts **nothing**, with no error | the daemon never reads `HostConfig.Binds` (the string `Binds` does not exist in its code) |
| `docker build` → `no such image: <FROM>` | the daemon's builder doesn't pull the `FROM` base image |
| `docker logs` of a detached container comes back empty | without a TTY, the stdout inherits the daemon's |

### 2.5 What simply does not exist in this mode

`docker compose`, `docker network`, `docker volume` (as objects), `swarm`, BuildKit,
healthcheck, restart policy, `--memory`/`--cpus`, `docker push`. No systemd inside the
containers (proot does not run systemd).

### 2.6 Costs nobody mentions

- **`proot` intercepts every syscall** — hence the constant overhead on everything.
- **amd64 on arm64** goes through `qemu-user`: multiply by ~5-20×.
- **Native Chromium eats ~1 GB of RAM** (measured: 1012-1110 MB). Two headless at once
  deadlock waiting for an element.
- **A force-killed container leaves the whole rootfs** on disk: measured here, 8 orphan
  containers = **10.6 GB** sitting there.
- **`-v` does not accept `:ro`** in udocker: the suffix becomes part of the filename and
  the mount fails **silently**.

---

## 3. What is theoretically possible (not tested here)

Ordered from cheapest to most expensive:

| Path | What it unlocks | Cost |
|---|---|---|
| **`pkg install udocker`** (udocker has been official in Termux since 2025) | removes the need for this repo's tarball installer | low — **not tested here**; this repo uses a tarball + its own fixes |
| **`chromedriver` + `cdriv`** (WebDriver client in pure `requests`) | the same Selenium automation without the Selenium dependency | low — not tested |
| **QEMU `system` (full VM) inside Termux** | **real KERNEL Docker**: `dockerd`, `docker compose`, systemd, cgroups | **10-25× slower** (no KVM for an ordinary app); third-party reports |
| **Root (Magisk) + custom kernel** | `pkg install root-repo && pkg install docker tini` → native Docker | requires unlocking the bootloader (wipes the device) and building a kernel |
| **Persistent services** (Home Assistant, Jellyfin, Nextcloud) | community scripts already exist running through udocker | depends on boot/wake-lock: Android suspends background processes |

**Where it will probably hit the wall anyway:** anything requiring `systemd`, iptables, a
privileged port (< 1024), hardware/GPU access, or real network isolation.

---

## 3.5 What if you use **only the official udocker**? (measured 2026-10-15)

udocker became an official Termux package (`pkg install udocker`, 1.3.17-5, `Depends: curl,
proot, python, resolv-conf`). I ran on it the same battery that revealed this repository's
defects:

| Defect | On the **official** udocker |
|---|---|
| proot 4.8.0 doesn't track children (SIGSYS on `apk`/`pip`) | ✅ **solved** — the package depends on Termux's `proot` (5.1) |
| hardlink denied inside the rootfs | ✅ **solved** — `link2symlink` is already handled |
| container without DNS | ✅ **solved** — the `resolv-conf` dependency injects the nameservers |
| termux-exec's `LD_PRELOAD` breaking proot | ✅ **solved** |
| `-v source:dest` (simple volume) | ✅ works the same |
| **`-v source:dest:ro`** | ❌ **same defect**: creates a literal `/dest:ro` path and the mount never happens |
| `--platform=linux/amd64` on `run` | ❌ ignores the platform: returned `aarch64` |
| `build`, `exec`, `logs` | ❌ **do not exist** — the subset is `pull/create/run/ps/rm/rmi/tag/import/export/save/inspect/setup/...` |

### 3.5.1 "So does the repo's version do everything udocker does?" — **no**

They are **different interfaces over the same engine**, not a superset. This repository's
`docker` command passes almost everything to the **official Docker CLI**, which talks to
the daemon's API; both share the same `~/.udocker`, so images serve both (and the official
`udocker` can stay installed alongside).

| Exclusive to **udocker** | does it go through the repo's `docker`? |
|---|---|
| `verify`, `protect`, `unprotect`, `mkrepo`, `setup` | ❌ they don't exist in the Docker CLI |
| `name`, `rmname`, `clone` (container naming) | ❌ likewise |
| `create`, `run`, `pull`, `images`, `ps`, `rm`, `rmi`, `tag`, `save`, `export`, `import`, `inspect`, `login`, `logout` | ✅ covered (via the Docker API) |

| Exclusive to **`docker`** (the repo's) | does it exist in udocker? |
|---|---|
| `build`, `exec`, `logs` | ❌ they don't exist in udocker |
| `cp`, `commit`, `diff`, `events`, `stats`, `top`, `wait`, `attach` | ❌ likewise (they depend on the daemon API) |

Add to that: the CLI lists about 45 commands, but **only the ones the daemon implements
actually work** — the rest exist in the help and fail at execution.

### 3.5.2 Can I make the two talk? Yes — implemented and tested

Two one-line bridges, in both directions:

| you type | it goes to | why |
|---|---|---|
| `docker verify/protect/unprotect/mkrepo/setup/name/rmname/clone` | udocker | the Docker API has no such commands |
| `udocker build/exec/logs/compose` | the repo's `docker` (daemon) | udocker has no such commands |
| any other `docker …` | official CLI → daemon | normal behaviour |
| any other `udocker …` | official udocker | same |

**Why it is safe:** the daemon does **not** go through the bridge. `udockerd` imports the
udocker Python library (`from udocker.container.structure import ContainerStructure`),
never the binary on `PATH` — so replacing `udocker` with the wrapper does not touch what
already worked. Verified after installing both bridges: `docker run --rm alpine echo ok`
answered, `docker setup --help` reached udocker, and `udocker build --help` reached Docker.

**Honest cost:** the wrapper sits on `PATH` **before** the official binary, so third-party
scripts calling `udocker` go through it. It is transparent (it forwards everything that
isn't `build`/`exec`/`logs`), but it is one more piece that can break — and `UDOCKER_REAL`
exists to point at another binary.

**Honest conclusion:** if you only want to **execute** images, `pkg install udocker` does
it — and it solves on its own three of the five defects this repository documents (the hunt
here was only necessary because we started from our own tarball). What plain udocker does
**not** give you is `docker build`, `docker exec`, `docker logs` and the Docker API — that
is exactly what this repository's daemon layer adds, and it is the layer that brings the
three `udockerd` defects the dispatcher works around.

---

## 3.6 Alternatives that exist today — what **we measured** and what we did not test

Recorded on 2026-10-15. Everything marked "measured" below was executed on this device;
the rest is reading third-party documentation, and is marked as such.

| Alternative | State | Numbers |
|---|---|---|
| `pkg install udocker` (official) | ✅ **measured** — solves 4 of this repo's 5 defects | see §3.5 |
| **[Doki](https://github.com/OpceanAI/Doki)** v0.12.0 (Android ARM64 binary, 14 MB) | ⚠️ **measured, with serious gaps** | `run alpine echo` **0.79 s**, `pull alpine` 5.5 s, `doki-compose` exists; `-v x:/teste` mounts correctly, **but `:ro` is ignored** (§3.6.2) |
| **Raw CDP** (native Chromium + `websockets`) | ✅ **measured** | static page in **1.9 s** against Selenium's 4.3 s, no `chromedriver` |
| Playwright **via Node/npm** | ✅ **measured — it works** | browser up in **0.5 s**, react.dev rendered in **1.4 s** (6583 chars), 1280×720 screenshot, ~830 MB RAM; see §3.6.3 |
| **[Podroid](https://github.com/ExTV/Podroid)** (APK, QEMU + its own kernel) | 📄 **not tested** | real Docker/Podman/LXC without root, Android 14+ |
| **proot-distro v5** | 📄 **not tested** | ships udocker integrated, `--bind`, `--shared-home` |

### 3.6.2 Doki accepts `:ro` and **ignores** it — silent failure (measured)

Better than udocker on one point and **worse** on another, and the detail matters:

    doki run --rm -v "$TMPDIR/doki-ro:/teste:ro" alpine sh -c "echo escrito > /teste/novo.txt"
    # the command SUCCEEDED and novo.txt APPEARED on the host

| | udocker | Doki |
|---|---|---|
| `-v x:/teste:ro` | mounts at `/teste:ro` and the file does not appear — **visible failure** | mounts in the right place and **lets you write** — **silent failure** |

udocker gets the path wrong, which you notice immediately. Doki accepts the syntax and
**discards the read-only restriction**: anyone writing `:ro` believing they protected the
host is unprotected. For a read-only mount coming from third-party data, that is worse than
udocker's error — which is why it went upstream as a priority bug.

### The two Doki gaps (measured, with evidence)

1. **Networking inside the container does not work.** The daemon runs `dns server started
   ... addr 127.0.0.11:8053` and explains that port 53 is blocked by SELinux — but the
   `/etc/resolv.conf` it hands the container points to `nameserver 127.0.0.11` **with no
   port**, that is, to 53. Result: `apk add`/`curl`/`wget` from inside the container don't
   resolve. `--network host` did not change that here.
2. **`build` refuses the context**: `Error: build context outside allowed directory`, even
   with the context inside `$HOME`.

This does not invalidate Doki — it is still faster and simpler than this repository's
solution, **and the `:ro` that bites us does not exist in it**. But today it does not
replace this stack for the case we use most (networking + `apk`/`apt` inside the container).
They are bugs to track; both have a minimal reproduction and deserve an upstream report.

### 3.6.3 Playwright **does** run on Android — via Node, with two keys (measured)

This document said "not tested" the day before. Now it is tested, and it works.

The trap: Playwright refuses to start with `Unsupported platform: android`, thrown from its
own `computeDefaultCacheDirectory()` — it only knows darwin/linux/win32. Two things are
needed:

1. **`PLAYWRIGHT_BROWSERS_PATH=0`** — with it, Playwright stops computing a cache directory
   and stops dying at startup.
2. **`executablePath`** pointing at Termux's own Chromium
   (`$PREFIX/bin/chromium-browser`) — the Chromium Playwright would download is a glibc
   build and does not run on Android/bionic.

```js
const { chromium } = require("playwright-core");
const b = await chromium.launch({
  executablePath: "/data/data/com.termux/files/usr/bin/chromium-browser",
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
});
```

Install with `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm i playwright-core` — there is no point
downloading a browser that cannot run.

Measured, three runs in a row (all three agreed):

| Step | Time | RAM |
|---|---|---|
| browser up (Node) | **0.5 s** | 416-421 MB |
| `goto react.dev`, text rendered | **1.4 s** (6583 chars) | 829-835 MB |
| `locator(...).innerText()` with auto-wait | **0.2-0.4 s** | — |
| screenshot (1280×720 PNG, valid) | 0.1-0.5 s | — |
| **total** | **3.0-3.2 s** | ~830 MB peak |

Auto-wait, locators, `page.evaluate`, screenshots and `page.title` all behave normally.
Honest caveat: the same ~830 MB of RAM as native Chromium, and therefore the same rule —
one browser at a time. For plain text extraction this is overkill; `webget` does it in 1.7 s
with 34 MB. Playwright earns its place when the script needs the *API* (auto-wait, locators,
tracing), not the raw speed.

### Dead ends confirmed by others (don't waste your time)

| Attempt | Result |
|---|---|
| rootless `podman` inside proot | `cannot clone: Invalid argument` — a Podman maintainer: *"proot is not powerful enough to run Podman"* ([podman#26186](https://github.com/containers/podman/issues/26186)) |
| `runsc`/gVisor | panics on Android ([gvisor#12544](https://github.com/google/gvisor/issues/12544)) |
| `pkg install docker` without root | does not exist: the package lives in `root-packages/` and requires root + a compatible kernel |

---

## 4. What already existed before (credit — none of this is our invention)

This work did **not invent** the concept. What it does is integrate, fix and measure:

- **[udocker](https://github.com/indigo-dc/udocker)** — the engine. It documents Termux as a
  supported environment, and today it is in the official repository: `pkg install udocker`.
- **[George-Seven/Termux-Udocker](https://github.com/George-Seven/Termux-Udocker)** (~409
  stars) — udocker setup on Termux plus ready-made scripts for popular services. Prior art
  reference.
- **[bjia56/udockerd](https://github.com/bjia56/udockerd)** — the Docker API-compatible
  daemon over udocker. It is the daemon layer used here.
- **[termux/proot](https://github.com/termux/proot)** and `proot-distro` — the userspace
  execution engine.
- **Termux Chromium/ChromeDriver** (`pkg install chromium`) and the gist *"Run selenium with
  chrome on termux"* — the headless/automation route.
- **[Draken119/cdriv](https://github.com/Draken119/cdriv)** — WebDriver client in pure
  `requests` for Termux, made because "Playwright/Selenium don't work on android/aarch64".
- **[OshekharO/Docker-On-Android](https://github.com/OshekharO/Docker-On-Android)** — the
  root + custom kernel path.
- **QEMU + real Docker** — documented by third parties; the alternative when you need real
  Docker without root, paying 10-25× in slowness.

---

## 5. What this work adds that is original

1. **A two-layer dispatcher with automatic fallback**: one `docker` command that decides
   between the daemon (complete: `build`/`exec`/`logs`/TTY) and the direct engine (volumes
   and multi-architecture `pull`), falling back to direct if the daemon won't start.
2. **Fixes for the 3 `udockerd` defects** (`android/arm64` platform on `pull`, ignored
   `Binds`, `FROM` not pulled) — decided and applied automatically, with the issues opened
   upstream ([#8](https://github.com/bjia56/udockerd/issues/8),
   [#9](https://github.com/bjia56/udockerd/issues/9)).
3. **Fixes for the 5 proot/Android defects**, including the shim that swaps the proot 4.8.0
   udocker downloads for **Termux's proot 5.1** (4.8.0 does not track child processes on
   Android: builtins run, external applets die with **SIGSYS**).
4. **Headless in 3 levels by cost**, with honest measurement of time **and RAM** for each
   level, and the verdict that **no Chromium runs under proot here**.
5. **Measured benchmarks** (not estimated) of both headless routes, including the real RAM
   cost of native Chromium (~1 GB) that most tutorials omit.
6. **A field report of the traps** that cost hours: `-v ...:ro` failing silently, orphan
   containers eating 10.6 GB, `pkill -f udockerd` killing your own shell, and the wrapper
   that dies leaving Chromium hanging as an orphan.

---

## 6. Quick decision: what to use?

| I need to… | Use |
|---|---|
| run a Linux tool that doesn't exist in Termux | `docker run <image>` (this repo) |
| a full Linux to work in | `proot-distro login <distro>` |
| read the text of a page | **plain HTTP** (`webget`, native) — 1.7 s and 34 MB; solves more than it seems (SSR) |
| an **image** of the page (PNG/PDF) | `webprint` (Chromium **native**) — 1 GB of RAM, but it is the only one that gives an image |
| click, fill, wait for an element | `webcdp` (raw CDP, 1.9 s) or `webplay` (Selenium) |
| a page with no text in the DOM (canvas) | **none** extracts text: neither HTTP nor Chromium |
| `docker compose`, cgroups, isolated networking | **not possible** — QEMU (slow) or root |
| automating a system with a session quota | **plain HTTP, never a browser** — a browser opens a real session and the quota is the same |
