# Third-party components

**Português:** [leia em português](THIRD-PARTY.pt-BR.md).

This repository **bundles no third-party binary**. It installs and/or drives the
components below, which keep their own licenses. The MIT license of this repository
covers only the scripts and documentation written here.

| component | source | license |
|---|---|---|
| udocker | https://github.com/indigo-dc/udocker | GPL-2.0 |
| udockerd | https://pypi.org/project/udockerd/ | Apache-2.0 |
| proot | https://github.com/termux/proot | GPL-2.0 |
| proot-distro | https://github.com/termux/proot-distro | GPL-2.0 |
| qemu-user | https://www.qemu.org/ | GPL-2.0 |
| Docker CLI (static binary) | https://download.docker.com/ | Apache-2.0 |
| Termux Chromium | https://github.com/termux/termux-packages | BSD-3-Clause and others |
| Selenium | https://pypi.org/project/selenium/ | Apache-2.0 |
| websockets | https://pypi.org/project/websockets/ | BSD-3-Clause |

## What is written here

- `scripts/` — the dispatcher, the direct engine, the daemon lifecycle and the installer
- `ferramentas/` — `pdf`, `pdfpy`, `webget`, `webprint`, `webcdp`, `webplay` and `webauto.py`
- `imagens/` — Dockerfiles **and the original sources** (`md2pdf`, `webget.py`)
- `testes/`, `examples/`, `verificar.sh`, `CAPACIDADES.md`, `AUTHORS.md`

Details on what already existed before are in [`AUTHORS.md`](AUTHORS.md); what the device
can and cannot do, measured, is in [`CAPACIDADES.md`](CAPACIDADES.md).
