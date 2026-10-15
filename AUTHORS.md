# Authorship and credits

**Português:** [leia em português](AUTHORS.pt-BR.md).

## Author of this work

**Gabriel Padilha** — [@Padilha-BR](https://github.com/Padilha-BR)

Responsible for the field work, for engineering the fixes and for every measurement
published here. Everything was executed **inside the device itself**, in a terminal
(Termux), without root and without a helper computer.

If this repository saved you time, fair recognition is the citation (see
[`CITATION.cff`](CITATION.cff)) or credit at the source.

## Before anything: what already existed (credits)

The concept is **not** original to this repository. These are the third-party pieces
this work stands on:

| project | what it is |
|---|---|
| [udocker](https://github.com/indigo-dc/udocker) | the unprivileged container engine; documents Termux as a supported environment and now ships as an official Termux package |
| [George-Seven/Termux-Udocker](https://github.com/George-Seven/Termux-Udocker) | udocker configuration on Termux and ready-made scripts for popular services |
| [bjia56/udockerd](https://github.com/bjia56/udockerd) | Docker API-compatible daemon backed by udocker (the daemon layer used here) |
| [termux/proot](https://github.com/termux/proot) and `proot-distro` | userspace execution (the engine behind everything) |
| [termux/termux-packages](https://github.com/termux/termux-packages) | proot 5.1, native Chromium, `chromedriver` and `qemu-user` |
| gist *"Run selenium with chrome on termux"* | the headless route via `chromedriver` + Selenium on Termux |
| [Draken119/cdriv](https://github.com/Draken119/cdriv) | WebDriver client in pure `requests` for Termux |
| [OshekharO/Docker-On-Android](https://github.com/OshekharO/Docker-On-Android) | the kernel-Docker path with root + a custom kernel |

## What this repository contributes

1. A **two-layer dispatcher** with automatic fallback between the daemon and the direct
   engine ([`scripts/docker`](scripts/docker)).
2. **Fixes for the three `udockerd` defects**: the `android/arm64` platform on `pull`,
   the ignored `HostConfig.Binds`, and the `FROM` not being pulled on `build` — with the
   issues opened upstream.
3. **Fixes for the proot defects on Android**, including the shim that replaces proot
   4.8.0 (which does not track child processes: builtins run, external applets die with
   SIGSYS) with Termux's proot 5.1 plus `--link2symlink`.
4. A **measured verdict on headless**: no Chromium runs under `proot` here, and the cure
   is the **native** Chromium; levels 1/2/3 chosen by cost, with time **and** RAM measured.
5. A **write-up of pitfalls** that cost hours and are not documented anywhere: `-v ...:ro`
   failing silently, the wrapper that dies leaving Chromium orphaned, force-killed
   containers piling up 10.6 GB, and `pkill -f udockerd` killing its own shell.

Details in [`CAPACIDADES.md`](CAPACIDADES.md).
