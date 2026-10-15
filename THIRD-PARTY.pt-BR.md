# Componentes de terceiros

**English:** [read in English](THIRD-PARTY.md).

Este repositório **não embute nenhum binário de terceiros**. Ele instala e/ou
dirige os componentes abaixo, que mantêm as suas próprias licenças. A licença
MIT deste repositório cobre apenas os scripts e a documentação escritos aqui.

| componente | origem | licença |
|---|---|---|
| udocker | https://github.com/indigo-dc/udocker | GPL-2.0 |
| udockerd | https://pypi.org/project/udockerd/ | Apache-2.0 |
| proot | https://github.com/termux/proot | GPL-2.0 |
| proot-distro | https://github.com/termux/proot-distro | GPL-2.0 |
| qemu-user | https://www.qemu.org/ | GPL-2.0 |
| Docker CLI (binário estático) | https://download.docker.com/ | Apache-2.0 |
| Chromium do Termux | https://github.com/termux/termux-packages | BSD-3-Clause e outros |
| Selenium | https://pypi.org/project/selenium/ | Apache-2.0 |
| websockets | https://pypi.org/project/websockets/ | BSD-3-Clause |

## O que é escrito aqui

- `scripts/` — o dispatcher, o motor direto, o ciclo do daemon e o instalador
- `ferramentas/` — `pdf`, `pdfpy`, `webget`, `webprint`, `webcdp`, `webplay` e `webauto.py`
- `imagens/` — Dockerfiles **e as fontes autorais** (`md2pdf`, `webget.py`, `webprint.py`)
- `testes/`, `examples/`, `verificar.sh`, `CAPACIDADES.md`, `AUTHORS.md`

Detalhamento do que já existia antes em [`AUTHORS.md`](AUTHORS.pt-BR.md); o que o
aparelho consegue e o que não consegue, medido, em [`CAPACIDADES.md`](CAPACIDADES.pt-BR.md).
