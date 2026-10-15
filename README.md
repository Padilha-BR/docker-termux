# docker-termux — Docker on Android without root

> **What works and what doesn't, measured on the device:** [`CAPACIDADES.md`](CAPACIDADES.md) —
> verified capabilities, limits with root cause, what is theoretically possible, and what
> already existed before (credits).

**Português:** [leia em português](README.pt-BR.md).

## The idea

An agent running on a phone should not be half an agent. This repository is the
**field record** of how to give it what used to exist only on the desktop — with the
cost of each choice on the table, because the scarce resource here is not CPU: it is
**memory**.

Nothing below came out of a tutorial; all of it came out of measuring on the device:

| I need to… | use | measured cost |
|---|---|---|
| run a Linux tool that doesn't exist in Termux | `docker run <image>` (this repo) | 4 s `proot` floor |
| read the **text** of a page | **plain HTTP** (`webget`, native) | **1.7 s, ~34 MB** |
| get the page as an **image** (PNG/PDF) | `webprint` (Chromium **native**) | 2.8-5 s, **~1 GB** |
| click, fill, run JS | `webcdp` (raw CDP, no Selenium) | **1.9-2.5 s** |
| a full Linux to work in | `proot-distro login <distro>` | — |
| `docker compose`, cgroups, isolated networking | **impossible without root** | VM (10-25× slower) |

The rule that saves the most time: **start at level 1**. The native `webget` extracts
**8,097 characters** from `react.dev` and **3,559** from `vercel.com` — "modern page"
does not mean "needs a browser". Climb to Chromium when you need pixels or clicks: each
climb costs ~1 GB of RAM against 34 MB.

Measured on a Galaxy S24 Ultra (Android 16, arm64, kernel 6.1.145) — everything typed
and executed inside Termux, on the phone alone, without root.

## What is ready to use

| command | what it does |
|---|---|
| **`docker`** | `pull`, `run`, `build`, `exec`, `logs`, TTY, volumes, images of another architecture by emulation, and the Docker API (any client can talk to it) |
| **`webget`** | level 1 — HTTP + parser, **native**: text, links, JSON, CSS selector |
| **`webprint`** | level 2 — native Chromium: `--dom`, `--texto`, `--pdf`, `--png` |
| **`webcdp`** | level 3 — raw CDP (**no Selenium**): text, JS, screenshot |
| **`webplay`** | level 3b — Selenium + chromedriver, for those who want the familiar API |
| **`pdf` / `pdfpy`** | Markdown → typeset PDF; PDF helpers in a container |
| **`verificar.sh`** | **the proof**: 17 items, ~2 min; it changes state (daemon, images, containers) |

---

## The field report (the Docker part itself)

What follows is the record of how `docker` was made to work here — including the five
Android defects that needed fixing and the ones that **have no fix**. Credits for what
already existed are in [`AUTHORS.md`](AUTHORS.md).

## First, what this is NOT

**Real Docker is impossible without root.** Measured, not assumed:

```
$ unshare -U true
unshare: unshare failed: Invalid argument
```

Android blocks *user namespaces* for apps. Without them there is no daemon, no isolated
cgroup, no overlayfs and no network of its own. `/proc/filesystems` and `/sys/fs/cgroup`
answer `Permission denied`. Anyone promising "full Docker on Termux without root" is
selling something else.

**What this repository delivers:** two layers that together give the Docker experience
where it matters (`pull`, `run`, `build`, `exec`, `logs`, `ps`, `rm`, TTY, images of
another architecture via emulation) using userspace execution with `proot`.

---

## Prior art (credits)

This work did **not** invent rootless containers on Android. It stands on projects that
already solved parts of the problem:

| project | what it already did |
|---|---|
| [udocker](https://github.com/indigo-dc/udocker) | talks to Docker Hub, pulls OCI layers, builds a rootfs, executes via proot/fakechroot — without root |
| [udockerd](https://pypi.org/project/udockerd/) | a **Docker API**-compatible daemon on top of udocker, made for Termux; covers create/start/stop/exec/logs/TTY and `docker build`; ships `--dns` and recommends Termux's own `proot` |
| [proot-distro](https://github.com/termux/proot-distro) | already pulls OCI images from Docker Hub/GHCR/quay, builds Dockerfiles without a daemon, pushes, cross-arch via qemu — and uses `--link2symlink` plus the `/linkerconfig/com.android.art/ld.config.txt` bind |
| [termux/proot](https://github.com/termux/proot) (issues [#75](https://github.com/termux/proot/issues/75), [#149](https://github.com/termux/proot/issues/149)) | already documented `link()` denied by SELinux, `PROOT_NO_SECCOMP=1` and bionic's syscall whitelist |
| [termux/termux-app#837](https://github.com/termux/termux-app/issues/837) | explains that hardlinks are blocked by SELinux hardening and that `--link2symlink` is the way out |

All the foundation is theirs. What **this** repository adds, as far as we checked and
found unpublished:

1. The **measured diagnosis** of why the `udocker` path (which downloads its own proot
   4.8.0, `udockertools`) breaks on Android: any `fork+exec` inside the container dies
   with **SIGSYS (signal 31)**, while a direct `exec` works. That takes down `apk`,
   `apt-get`, `pip` and any script.
2. The **minimal fix**: a one-file *shim* pointing udocker at Termux's `proot` 5.1, with
   `--link2symlink`.
3. The other three environment defects and their fixes (missing `resolv.conf` on Android,
   `qemu` not found, Android linker noise on amd64 images), with symptoms and the commands
   that prove them.
4. An idempotent installer that sets up **both** layers (direct mode and daemon) and a
   `docker doctor` that checks every piece.

If you only want containers on Termux, **use `proot-distro`** — it is maintained by the
Termux team and does more. This repository exists for when you want the Docker CLI/API
(`docker build`, `docker exec`, `docker logs`) and for documenting the pitfalls with
reproducible measurements.

**And if you only want to *execute* images: `pkg install udocker`** — it is officially in
the Termux repos now. See [`CAPACIDADES.md`](CAPACIDADES.md), where the official package is
measured against these five defects.

---

## Architecture

```
                        `docker` command (yours)
                                |
                    [ dispatcher: .hermes/bin/docker ]
                       |                          |
        daemon up?     |                          | daemon won't start
                       v                          v
   LAYER 2: daemon (Docker API)           LAYER 1: direct mode
   static official CLI (arm64)            udocker + proot 5.1 on the fly
   <-> udockerd 0.3.5 (tcp 127.0.0.1:2375)  no build/exec/logs
   -> real execution: Termux proot 5.1
```

- **Layer 1 (direct mode):** `udocker` + Termux's `proot`, no daemon, no pip. Runs
  containers, has DNS, volumes, its own `-d`/`logs`. Command: `docker-direct`.
- **Layer 2 (daemon):** `udockerd` exposes the Docker API and the official Docker CLI
  (static arm64 binary) talks to it. Enables `docker build`, `docker exec`, `docker logs`,
  TTY and any API client.

Both really execute through **Termux's proot 5.1** — neither has kernel namespaces.

### Why the daemon listens on a Unix socket

The Docker API has **no authentication**: whoever reaches the endpoint controls the daemon —
runs containers, mounts a volume of your Termux home, reads your files. On a multi-user
server the loopback is already restricted; **on Android it is not**, and any app holding
the INTERNET permission can connect to `127.0.0.1:2375`.

So the daemon speaks over `unix://$HOME/.udockerd/docker.sock` in mode **0600**, inside a
`0700` directory. `udockerd` only knows TCP, so
[`scripts/udockerd-unix`](scripts/udockerd-unix) serves **its own handler and routes** over
`AF_UNIX` — nothing is reimplemented. Verified: `docker run` works through the socket, the
socket is `0600`, and `127.0.0.1:2375` stops answering. `DOCKER_DAEMON_TCP=1` brings the old
transport back (not recommended).

---

## Install

```sh
git clone https://github.com/Padilha-BR/docker-termux
cd docker-termux
bash docker-termux-setup          # idempotent; --force redoes downloads
docker doctor                     # checks every piece
bash verificar.sh                 # proves the whole stack (16 items, ~1 min)
```

The installer handles: `proot`, `qemu-user-x86-64`, the udocker runtime, the proot shim,
the qemu patch, the udockerd venv, supervisor compilation, the official CLI download,
scripts, shortcuts and `resolv.conf`.

Two things worth knowing about those downloads:

- **They are verified.** Neither udocker nor Docker publishes a `.sha256` for these
  artifacts, so the hashes live in [`checksums.txt`](checksums.txt) and the installer
  **aborts** if a downloaded file doesn't match (a version without a pin is reported with
  its hash, never silently accepted). `udockerd` is installed pinned at `==0.3.5`, the
  version the dispatcher's workarounds were tested against.
- **The daemon listens on a Unix socket**, not TCP — see "Why the daemon listens on a Unix
  socket" below.

---

## Usage

```sh
docker pull alpine                       # arm64 image (native, fast)
docker pull --platform=linux/amd64 alpine  # x86 image (emulated by qemu)
docker run --rm alpine sh -c "uname -m; apk add --no-cache curl && curl -s example.com"
docker run -it --rm debian:bookworm-slim bash

docker run -d --name=web -v $HOME/site:/site python:3.12-alpine sh /site/serve.sh
docker logs web
docker exec web cat /etc/alpine-release
docker stop web && docker rm web

printf 'FROM alpine:3.20\nRUN apk add --no-cache jq\nCMD ["jq","--version"]\n' > Dockerfile
docker build -t minha-imagem .           # a real build, no daemon
docker run --rm minha-imagem

docker doctor        # diagnostics
docker daemon up     # bring the daemon up/down explicitly
docker-direct ...    # force the daemonless mode (always available)
```

---

## The five Android defects (and the fixes)

All found by measurement (`proot -v 9`, environment-variable bisection, syscall tracing),
not by guessing.

### 1. The proot udocker downloads doesn't track child processes

```sh
$ udocker run alpine sh -c "uname -m"     # exit 255
proot info: vpid 1: terminated with signal 31
$ udocker run alpine uname -m             # works: aarch64
```

The rule that sums up the symptom: **shell builtins pass, external applets die.** `echo`
and `pwd` work; `uname`, `cat`, `apk`, `apt`, `pip` — anything doing `fork+exec` — dies
with SIGSYS. udocker's proot is `udockertools-v1.1.4` (proot 4.8.0); Termux's is 5.1.107,
with the seccomp/arm fixes.

**Fix:** a shim at `~/.udocker/bin/proot-arm64-4_8_0` (udocker executes that path) that
delegates to Termux's proot, keeping the flags udocker uses (`--kill-on-exit`, `-b`, `-0`,
`-k/--kernel-release`, `-r`, `-w`, `-v`):

```sh
exec /data/data/com.termux/files/usr/bin/proot --link2symlink "$@"
```

### 2. Android denies hardlinks inside the rootfs

```sh
$ apk update
WARNING: updating and opening https://...: Permission denied
$ apk add --no-cache curl
(9/9) Installing curl
ERROR: System state may be inconsistent: failed to write database: Permission denied
```

Packages install, but apk can't write its database — because `link()` is denied by SELinux
for ordinary apps (termux-app issue #837 documents it). **Fix:** `--link2symlink` (the same
flag proot-distro uses). After that: `OK: 28554 distinct packages available`.

### 3. Android has no `/etc/resolv.conf`

The container comes up without DNS: `wget: bad address 'example.com'`. udocker's `--dns=`
is not enough. **Fix:** write `nameserver 8.8.8.8` into
`~/.udocker/containers/<ctr>/ROOT/etc/resolv.conf` (the CLI does it automatically;
`docker dns-fix` repairs older ones). After that: `HTTP 200`.

### 4. An amd64 image can't find qemu

```
Warning: qemu required but not available
proot info: vpid 1: terminated with signal 7      # SIGBUS
```

udocker passes only the **name** of the binary (`-q qemu-x86_64`) and proot looks it up in
the *container's* `$PATH`, which has no qemu. **Fix:** a one-line patch in
`udocker/engine/proot.py` (`self._get_qemu(return_path=True)`) + `pkg install
qemu-user-x86-64`. After that: `uname -m` → `x86_64` in **1.6 s**.

### 5. termux-exec's `LD_PRELOAD` breaks any proot

```
proot error: execve("/bin/busybox"): No such file or directory
```

…with `/bin/busybox` present and executable. Termux injects `libtermux-exec-ld-preload.so`
into every command; the container's loader tries to load that library and fails. Isolated by
bisection — it is the only environment variable that kills the process. **Fix:** strip
`LD_PRELOAD` (and `LD_LIBRARY_PATH`) before calling the engine.

### Bonus: linker noise

An amd64 image prints `WARNING: linker: failed to find ... /linkerconfig/ld.config.txt` on
every process (qemu is an Android binary running under proot). **Fix:** bind
`-v /linkerconfig:/linkerconfig` — `/linkerconfig` is readable by Termux (proot-distro does
the same with the ART path).

---

## Verification (reproduce it)

```sh
bash verificar.sh          # the whole stack, 16 items
```

or individually:

```sh
docker doctor
docker run --rm alpine sh -c "uname -m; apk add --no-cache curl >/dev/null && echo apk-ok"
docker run --rm debian:bookworm-slim sh -c "apt-get update -qq >/dev/null && echo apt-ok"
docker run --rm python:3.12-alpine sh -c "pip install -q requests && echo pip-ok"
docker run -it --rm alpine sh
```

The test that catches defect 1 is `sh -c` running an **external** applet (`uname -m`), not
`echo` (a builtin). The one that catches defect 2 is `apk add` / `apt-get install`.

Measurements on this device: `docker build` of a Dockerfile with `apk add jq` in 13.8 s;
`proot-distro build` equivalent in 3.4 s (3 layers, 4.4 MiB); an amd64 image running in
1.6 s; headless level 1 (native `webget`) **1.7 s / ~34 MB**; headless level 3 (raw CDP)
**1.9 s**.

---

## What the dispatcher fixes for you (found by testing)

Three differences in the `udockerd` 0.3.5 daemon that would cost you time, all handled
automatically by the `docker` command:

| symptom | cause | what the dispatcher does |
|---|---|---|
| `docker pull` fails with `no image found in manifest for platform (android/arm64)` | the udocker lib reports the platform as **android/arm64** and Docker Hub doesn't publish that | routes `pull` to the direct engine, which pulls with `--platform=linux/arm64`; the daemon sees the image afterwards (same `~/.udocker`) |
| `docker run -v` mounts **nothing**, with no error | udockerd never reads `HostConfig.Binds` (the string `Binds` doesn't exist in its code; the udocker engine underneath supports it, but `opt["vol"]` stays empty) — [issue #9](https://github.com/bjia56/udockerd/issues/9) | detects `-v`/`--volume`/`--mount` and runs through the direct engine, which mounts via proot's `-b` |
| `docker build` fails with `no such image: <FROM base>` | the daemon's builder doesn't pull the `FROM` (real Docker does) | reads the context `Dockerfile`, finds the base images and pulls them before building |
| `docker logs` of a detached container comes back empty | without a TTY the stdout inherits the daemon's — [issue #8](https://github.com/bjia56/udockerd/issues/8) | injects `-t` into `run -d` and warns |

It also **bridges the two interfaces**: `docker` accepts the udocker-native commands
(`verify`, `protect`, `unprotect`, `mkrepo`, `setup`, `name`, `rmname`, `clone`), and a
`udocker` wrapper sends `build`/`exec`/`logs` to the `docker` command. Same engine, same
`~/.udocker`, so both commands cover both interfaces.

## Binds and browser: two measured findings

**1. `-v` does not accept `:ro`.** `-v /host/script.py:/ctr/script.py:ro` mounts nothing
and still creates a file named `script.py:ro` inside the destination — the container then
fails with `can't open file '/ctr/script.py'`. Use the plain form `-v source:dest` (works
for a file and for a directory). Proof the bind took: the `sha256sum` inside and outside
must match.

**2. No Chromium survives `proot`** — and the cure is not to use a container for this.
Measured with Chrome for Testing 156 and `chrome-headless-shell` 156 (native arm64):
`Trace/breakpoint trap` (SIGTRAP), `Target crashed`, or a loop of `crashpad ... tgkill: No
such process` until the timeout. Tried `--no-sandbox`, `--single-process`, `--no-zygote`,
`--headless=old` and `GLIBC_TUNABLES=glibc.pthread.rseq=0` — none work. Cause: `proot`
intercepts syscalls through **ptrace**, and Chromium's crashpad also relies on ptrace/child
processes.

| route | static page | SPA (JS only) | peak RAM |
|---|---|---|---|
| plain HTTP (`webget`) | **1.7 s** | fails (comes back empty) | ~34 MB |
| **native Termux Chromium** (`webprint`) | 2.8 s | 4.7-6.2 s, rendered | ~1 GB |
| raw CDP (`webcdp`) | **1.9-2.5 s** | rendered | ~1 GB |
| **Playwright via Node** (`playwright-core`) | 0.5 s (launch) | **1.4 s, rendered** | ~830 MB |
| Selenium + native `chromedriver` (`webplay`) | 4.0 s | OK | ~1 GB |

Playwright **does** run here — via Node, not Python. It refuses to start with `Unsupported
platform: android` (it only knows darwin/linux/win32) unless you set
`PLAYWRIGHT_BROWSERS_PATH=0` **and** point `executablePath` at Termux's own
`chromium-browser` (the build it would download is glibc and cannot run). Measured 3/3
runs: browser up in 0.5 s, react.dev rendered in 1.4 s, valid 1280×720 screenshot. Details
in [`CAPACIDADES.md`](CAPACIDADES.md) §3.6.3.

```sh
pkg install x11-repo && pkg install chromium   # binary: chromium-browser
chromium-browser --headless=new --no-sandbox --disable-gpu \
    --disable-dev-shm-usage --virtual-time-budget=8000 --dump-dom URL
```

`chromedriver` ships in the same package and works with `selenium` (pure Python).
Playwright **has no Python wheel for Android** — but it **does run via Node** (see the
table above). Cost, told honestly: any browser route eats ~830 MB to 1 GB of RAM — prefer
plain HTTP when the HTML already carries the content, and never run two browsers at once.

## Honest limitations

- **Don't restart the daemon while a build is running:** `docker daemon down` kills the
  process group and takes the build/containers with it (dies with `terminated with signal
  15` and the Dockerfile continues with half-installed packages).
- On Ubuntu 24.04 use `python3 -m pip` in the Dockerfile — the `pip` command doesn't exist.
- `docker compose`, `docker network`, `docker volume` (as objects), `swarm`, BuildKit,
  healthcheck, restart policy, `--memory/--cpus` and `docker push` do not exist in this mode.
- **The network is not isolated:** the container uses Termux's network stack, so the service
  listens directly on the port (`-p` is ignored on purpose).
- **`docker logs` of a detached container requires a TTY** on udockerd 0.3.5: without `-t`,
  the main process output inherits the daemon's stdout and `docker logs` comes back empty
  (real Docker doesn't need this). Proven by varying only `-t`, with the direct CLI and the
  supervisor already compiled:

  ```sh
  docker run -d  --name=c1 alpine sh -c "echo SEM-T; sleep 15"; docker logs c1   # empty
  docker run -dt --name=c2 alpine sh -c "echo COM-T; sleep 15"; docker logs c2   # COM-T
  ```

  That is why the dispatcher injects `-t` into `run -d` and warns. The supervisor
  (`~/.udockerd/udockerd-supervisor-*`, compiled by the installer) is also needed to avoid
  orphan processes.
- `docker run` without `--rm` accumulates stopped containers (same as real Docker).
- **`proot` charges per entry of the mounted directory:** a container with no bind is 4 s,
  with an empty directory 7 s, with `$HOME` (728 entries) **13 s**. That is why `webget` runs
  natively first.
- Android suspends background processes: for long-running services, exempt Termux from
  battery optimisation and keep a wake-lock.
- One architecture per tag: `pull --platform=linux/amd64 alpine:latest` replaces the local
  arm64 image for that tag.

---

## Authorship and how to cite

Made by **Gabriel Padilha** ([@Padilha-BR](https://github.com/Padilha-BR)), from field work
to fixes — everything executed inside the device, in a terminal.

- [`AUTHORS.md`](AUTHORS.md) — what already existed (credits) and what is this repository's
  original contribution.
- [`CITATION.cff`](CITATION.cff) — formal citation (GitHub shows the *Cite this repository*
  button).
- [`CAPACIDADES.md`](CAPACIDADES.md) — what it can do, what it cannot, and what is
  theoretically possible, with the measurements.

### Structure

| path | what it is |
|---|---|
| `verificar.sh` | **the battery that proves the whole stack** (17 items, ~2 min; it starts the daemon, pulls images and runs containers) |
| `scripts/` | the `docker` dispatcher, the direct engine, the daemon lifecycle, `udockerd-unix` (Unix-socket daemon) and the installer |
| `checksums.txt` | pinned sha256 of the artifacts the installer downloads |
| `ferramentas/` | `pdf`, `pdfpy`, `webget`, `webprint`, `webcdp`, `webplay` and the `webauto.py` helper |
| `imagens/` | Dockerfiles **and the original sources** (`md2pdf`, `webget.py`, `webprint.py`) |
| `testes/` | headless benchmarks (time + RAM) and the PDF test battery |
| `examples/` | worked examples: Manim (video) and web automation (Selenium) |
| `skills/` | the Hermes skill describing the procedure |

## License

MIT. The components used keep their own licenses — see [`THIRD-PARTY.md`](THIRD-PARTY.md):
udocker (GPL-2.0), udockerd (Apache-2.0), proot/proot-distro (GPL-2.0), Docker CLI
(Apache-2.0), qemu (GPL-2.0), Termux Chromium, Selenium and websockets.
