---
name: docker-termux
description: "Use when rodando Docker no Termux/Android sem root."
version: 2.0.0
platforms: [linux, android]
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [docker, termux, android, udocker, udockerd, proot, qemu, container, oci]
---

# Docker no Termux (Android, sem root, sem daemon de kernel)

## When to Use

- Pedido de "docker no Termux/celular", container, imagem do Docker Hub, build de
  Dockerfile, ou algo que "só roda em Linux" no Android.
- Sintoma dentro de um container: **SIGSYS/signal 31**, **signal 7**,
  `failed to write database: Permission denied`, `bad address 'example.com'`,
  `qemu required but not available`.
- Reinstalar/consertar o motor: `docker doctor` e `docker-termux-setup`.

## Veredito medido (Android 16, arm64, kernel 6.1.145)

- **Docker/Podman de verdade são impossíveis sem root**: `unshare -U` devolve
  `Invalid argument` (Android bloqueia user namespaces para apps). Sem isso não
  há daemon, cgroup isolado, overlayfs nem rede própria.
- **O que funciona**: execução em userspace por `proot` 5.1 do Termux, com
  `udocker` (camada direta) e `udockerd` + CLI oficial do Docker (camada daemon).

## Arquitetura instalada (comando único: `docker`)

O comando `docker` é um **dispatcher** em `~/.hermes/bin/docker`:

| camada | quando | o que dá |
|---|---|---|
| **daemon** (`udockerd` + CLI oficial 29.x em `~/docker-termux/bin/docker`) | sempre que o daemon sobe | `run`, `build`, `exec`, `logs`, TTY, `pull`, `ps`, API do Docker em `unix://~/.udockerd/docker.sock` (0600) |
| **direto** (`~/.hermes/bin/docker-direct`, udocker + proot na hora) | fallback se o daemon não subir | `run`, volumes, `-d` com log próprio; **sem** build/exec/logs |

Ajudantes: `docker-daemon-up` (sobe desgarrado, pidfile, wake-lock),
`docker-daemon-down` (encerra o grupo de processos), `docker-termux-setup`
(instala tudo, idempotente), `docker doctor` (diagnóstico), `docker dns-fix`.

Ambas as camadas executam com o `proot` 5.1 do Termux. O daemon usa o mesmo
`~/.udocker`, então imagens baixadas numa camada aparecem na outra.

## Os 5 defeitos do Android (sintoma -> causa -> cura)

1. **proot 4.8.0 do udocker não rastreia filhos.** `run <ctr> sh -c "uname -m"`
   sai **255** com `vpid 1: terminated with signal 31` (SIGSYS), enquanto
   `run <ctr> uname -m` funciona. Regra: **builtin do shell passa, applet externo
   (fork+exec) morre** — derruba `apk`, `apt`, `pip`, qualquer script.
   Cura: shim em `~/.udocker/bin/proot-arm64-4_8_0` que faz
   `exec $PREFIX/bin/proot --link2symlink "$@"` (backup em `.udocker.orig`).
2. **Android nega hardlink no rootfs** (SELinux): `apk update` -> `Permission
   denied`; `apk add` instala e morre em `failed to write database: Permission
   denied`. Cura: `--link2symlink` (mesmo motivo que o proot-distro tem `l2s.py`).
3. **Android não tem `/etc/resolv.conf`**: container sem DNS (`bad address`).
   `--dns=` do udocker não resolve; a camada daemon configura por conta própria.
   Cura: escrever `nameserver 8.8.8.8` em
   `<repo>/containers/<ctr>/ROOT/etc/resolv.conf` (o CLI faz em todo container;
   `docker dns-fix` nos antigos).
4. **Imagem de outra arquitetura não achava o qemu**: `qemu required but not
   available` + signal 7 (SIGBUS). O udocker passava só o nome e o proot procurava
   no PATH do container. Cura: patch em `udocker/engine/proot.py`
   (`self._get_qemu(return_path=True)`) + `pkg install qemu-user-x86-64`.
5. **`LD_PRELOAD` do termux-exec quebra qualquer proot**: o loader do container
   tenta abrir `libtermux-exec-ld-preload.so`, que não existe lá
   (`execve("/bin/busybox"): No such file or directory` com o arquivo presente).
   Cura: remover `LD_PRELOAD`/`LD_LIBRARY_PATH` antes de chamar o motor.

Bônus: manter `PROOT_NO_SECCOMP=1` e `TMPDIR=$PREFIX/tmp` (sem `TMPDIR` o udocker
usa `/tmp`, inexistente no Android). Imagem amd64 imprime aviso do linker do
Android a cada processo; cura com bind `-v /linkerconfig:/linkerconfig` (o CLI
faz sozinho quando a imagem não é da arquitetura do host).

## O dispatcher conserta sozinho (não reintroduza estes bugs)

| se o usuário reclamar de... | causa real | tratamento no `~/.hermes/bin/docker` |
|---|---|---|
| `docker pull` falha: `no image found in manifest for platform (android/arm64)` | a lib do udocker vê plataforma `android/arm64`; o Hub não publica isso | `pull` vai para o motor direto (`--platform=linux/arm64`); o daemon vê a imagem depois |
| `docker run -v` não monta nada (sem erro) | udockerd ignora `HostConfig.Binds` — `grep -rn Binds` não acha nada no pacote (issue #9) | `-v`/`--volume`/`--mount` em `run`/`create` vão para o motor direto, que monta com `-b` |
| `docker build` -> `no such image: <FROM>` | o builder do daemon não puxa o `FROM` | o dispatcher lê o Dockerfile do contexto e puxa as bases antes |
| `docker logs` vazio em container destacado | sem TTY o stdout herda o do daemon (issue #8) | injeta `-t` em `run -d` com aviso |

## Utilitários que só existem via container

Ferramentas que **não** existem no Termux (e não têm pacote) e por isso rodam em
imagem Docker, chamadas como comandos normais:

| comando | o que faz | imagem |
|---|---|---|
| `pdf` | Markdown -> PDF tipografado (weasyprint; capa, A4/letter, emoji, numeração) | `pdf-tool:1` |
| `pdfpy` | roda qualquer helper da skill `pdf` (pypdf/reportlab/pdfplumber) | `pdf-tool:1` |
| `webget` | baixa página e extrai texto/HTML/links (**nível 1**, sem navegador) | nativo (`venv-web`); `web:1` se faltar o venv |
| `webprint` | Chromium headless **nativo** (fora do container): `--dom` / `--texto` / `--pdf` / `--png` (**nível 2**) | — (usa `chromium-browser`) |
| `webcdp` | CDP puro, **sem Selenium**: `--texto` / `--titulo` / `--html` / `--js` / `--screenshot` (**nível 3**, o mais rápido; só http/https) | — (usa `chromium-browser`) |
| `webplay` | roda **seu** script de automação — **Selenium + chromedriver nativo**, com o helper `webauto.py` (**nível 3b**) | — (usa o `chromium` do Termux) |

Fontes em `~/docker-termux/imagens/<nome>/`; cópia publicada em
`github.com/Padilha-BR/docker-termux`. Cada comando constrói a imagem na primeira
execução (avisa).

### Headless: escolha o nível pelo custo (medido)

| nível | ferramenta | quando | custo medido | estado |
|---|---|---|---|---|
| 1 | `webget` (httpx + bs4/lxml, **nativo**) | HTML já traz o conteúdo — **comece aqui, resolve quase tudo** | **1,7 s**, ~34 MB | **OK** |
| 2 | `webprint` (Chromium **nativo**, sem container) | página precisa de JS, ninguém precisa clicar | 2,9 s (estática) / 4,7 s (SPA) | **OK (medido)** |
| 3 | `webcdp` (CDP puro, **sem Selenium**) | leitura + JS + screenshot — mais rápido que o Selenium | 1,9-2,5 s, ~1 GB | **OK (medido)** |
| 3b | `webplay` (Selenium + chromedriver) | clique/formulário com API familiar | 4,0-4,8 s, ~1 GB | **OK (medido)** |

**Nenhum Chromium sobrevive ao `proot`** (medido: Chrome for Testing 156 e
`chrome-headless-shell` 156, arm64 nativos). Sintomas: `Trace/breakpoint trap`
(SIGTRAP), `Browser.new_page: Target crashed`, ou loop infinito de
`crashpad ... tgkill: No such process` até o timeout. Não é flag faltando —
`--no-sandbox`, `--single-process`, `--no-zygote`, `--headless=old` e
`GLIBC_TUNABLES=glibc.pthread.rseq=0` foram todos testados. Causa: o `proot`
intercepta syscalls por **ptrace**, e o crashpad do Chromium também depende de
ptrace/processos filhos — os dois brigam.

**Cura: use o Chromium NATIVO do Termux** (bionic, sem proot → sem ptrace):

    yes | pkg install x11-repo          # gtk3/libxkbcommon/libevdev vem daqui
    yes | pkg install chromium          # binario: `chromium-browser` (o real e
                                        # $PREFIX/lib/chromium/chrome, 276 MB)
    chromium-browser --headless=new --no-sandbox --disable-gpu \
        --disable-dev-shm-usage --virtual-time-budget=8000 --dump-dom URL

Medido (arm64, Android 16): estática **2,9 s**, SPA `react.dev` **4,7 s** (o JS
roda e o texto sai renderizado), `--screenshot` PNG 3,1 s, `--print-to-pdf` 88 KB.
O mesmo fetch pelo `webget` dentro do container variou de 4 a 9 s (cada chamada sobe o proot
de novo), então o headless nativo ganha em tempo — mas perde feio em RAM.
Os erros de `dbus`/`udev` no stderr são inofensivos (Android não tem bus).

**Nível 1 resolve mais do que parece — e o container cobra caro.** Medido: o
`webget` **nativo** extrai 8.097 chars de `react.dev`, 3.559 de `vercel.com` e
2.106 de `vuejs.org`; a falha que parecia "SPA precisa de JS" era **DNS dentro do
container** (`EAI_AGAIN`). O que nenhum nível resolve é página **sem texto no DOM**
(canvas: `excalidraw.com` dá 32 chars no nível 1 e 11 no Chromium). E o `proot`
cobra **por entrada do diretório montado**: container sem bind 4 s, com bind de
diretório vazio 7 s, com bind do `$HOME` (728 entradas) **13 s** — por isso o
`webget` roda nativo primeiro e o container é fallback (`WEBGET_CONTAINER=1`
força o antigo).

**Nível 3 mais rápido: CDP puro.** `webcdp URL [--texto|--titulo|--html|--js EXPR|
--screenshot ARQ]` fala Chrome DevTools Protocol por WebSocket — **sem Selenium e
sem chromedriver**, medido em 1,9-2,5 s contra 4,0-4,8 s da via Selenium. Pegadinha
que trava 70 s se você errar: o `webSocketDebuggerUrl` de `/json/version` é o
endpoint do **browser**, e comandos `Page.*` nele não respondem — é preciso o alvo
de **página** (`/json/list`, `type == "page"`). Exit 3 = página sem conteúdo.

**Nível 3b = Selenium, não Playwright**: o Playwright não tem wheel para Android
(`pip install playwright` → `No matching distribution found`). O caminho é
`chromedriver` (vem no pacote `chromium`, mesma versão) + `selenium` (Python puro,
instalado em `~/docker-termux/venv-web`). O helper `webauto.py` já traz as flags do
Android e `webplay script.py` roda seu script. Medido: clique real, espera por
elemento e screenshot OK em 4,0-4,8 s.

**Escolha pelo recurso escasso, não só pelo tempo**: em página estática o nível 1
gasta 4,3 s e ~34 MB, o nível 2 gasta 2,8 s e **~1 GB** (o Chromium nativo tem
custo alto de RAM: medido 1012-1110 MB). Prefira o nível 1 quando a memória é o
limitante; suba para o 2 quando a página precisa de JS. **Nunca rode dois
Chromiums ao mesmo tempo** no aparelho — dois headless simultâneos travam a
espera por elemento (visto na prática: 2 GB de RAM).
O wrapper `webprint` já usa essa via (`--dom|--texto|--pdf|--png`); `CHROMIUM_BIN`
troca o binário e `WEBPRINT_TIMEOUT` o timeout. Sem `pkg install chromium`, a
alternativa é **delegar para uma VM Linux** por SSH.

`webget` sai com **código 3** só quando o conteúdo vem **realmente vazio** — e
apenas nos modos que leem conteúdo: uma página **sem links** não dispara o 3 no
modo `--links` (corrigido; antes sugeria subir de nível sem motivo). Anti-bot forte (Cloudflare) e mídia (use `yt-dlp`) não
se resolvem com navegador.

### Regra para sites que consomem cota de sessão

Navegador automatizado abre sessão de verdade. Se o serviço cobra ou limita
logins concorrentes (planos com número fixo de acessos), **prefira HTTP puro**
(`requests`) em vez de navegador — a automação não muda a cota, agrava. Vale para
qualquer sistema com cota compartilhada, com ou sem container.

## Pitfall: `OCI runtime create failed: [Errno 2]` = daemon VELHO em execução (medido 16/10/2026)

Sintoma: `docker doctor` passa tudo `[OK]` (CLI, daemon, proot, qemu, DNS), o modo direto funciona
(`docker-direct run --rm alpine echo ok`), e **só o `docker run`** morre com
`OCI runtime create failed: [Errno 2] No such file or directory`. O log
`~/docker-termux/logs/udockerd.log` mostra `Error: while extracting image layer (proot retry)` e
`Error: creating container`, e o `verificar.sh` reprova exatamente 3 itens (run + fork/exec,
`apk add`, rede + DNS).

Causa medida: **o daemon estava no ar desde ANTES das atualizações**. Ele responde na API, então o
`docker-daemon-up` (idempotente) sai cedo e o processo vivo continua com o código/estado velho.
Conserto: `docker-daemon-down && docker-daemon-up` (ou `docker daemon up`). No mesmo dia:
3 FALHA → **16 OK, 0 FALHA**.

O que **não** era a causa (isolei para não repetir o diagnóstico errado): o shebang
`#!/usr/bin/env python` do `maincmd.py` — com shebang ruim **e** daemon reiniciado o `run` funciona,
porque o daemon importa a lib do udocker e não executa o binário (é a regra da seção acima); e o
`LD_PRELOAD` do `termux-exec` no daemon, que está lá e funciona. Regra geral: antes de acusar o
código, faça o daemon nascer do zero e repita o teste — em `docker`, "processo velho" é a primeira
suspeita, igual ao caso dos injetores 8890/8891.

Detalhe que confunde: o `docker-daemon-down` remove o socket, mas a chamada seguinte do `docker` já
encontra o daemon no ar outra vez (medido: <1 s) — não conte com "derrubei, então está caído" para
provar nada.

## Armadilhas que custam tempo

- **O udocker NÃO aceita sufixo `:ro`/`:rw`.** Passado cru,
  `-v /host/script.py:/ctr/script.py:ro` não monta nada e ainda cria um arquivo
  chamado **`script.py:ro`** dentro do destino — o container então falha com
  `can't open file '/ctr/script.py'`. O `docker-direct` agora remove o sufixo e
  **avisa**, mas o bind fica **gravável** (`ro` não é garantido). Prefira a forma
  pura `-v origem:destino`. (Binds de arquivo **e** de diretório
  funcionam assim: o proot cria o ponto de montagem, desde que o caminho não
  tenha opção colada.) Verificação de que o bind pegou:
  `sha256sum` do arquivo dentro e fora devem bater.

- **`docker logs` de container destacado exige `-t`** no udockerd 0.3.5: sem TTY a
  saída herda o stdout do daemon e o log volta vazio. Comprovado variando só o `-t`
  com a CLI direta (supervisor já compilado): `run -d` -> vazio, `run -dt` -> saída.
  O dispatcher insere `-t` em `run -d` e avisa. Logs de `exec` ficam em
  `~/.udockerd/logs/exec/`.
- **O supervisor do udockerd compila on first use** (`~/.udockerd/udockerd-supervisor-*`);
  precisa de `cc`/`clang`. Sem ele, `docker logs` do container principal fica vazio.
- **O daemon fala por socket Unix**, não TCP: para checar à mão use
  `curl --unix-socket ~/.udockerd/docker.sock http://localhost/_ping` (o
  `DOCKER_HOST` é `unix://...`; `DOCKER_DAEMON_TCP=1` traz o `127.0.0.1:2375`
  antigo, sem autenticação — não recomendado).
- **Uma arquitetura por tag**: `pull --platform=linux/amd64 alpine:latest`
  sobrescreve a imagem arm64 local daquela tag. Para voltar, pull sem `--platform`.
- **O builder do daemon NÃO tem cache de camadas**: mudar o `Dockerfile` refaz apt+pip
do zero (5-20 min). Por isso o código que muda com frequência (ex.: `md2pdf`,
`webget.py`) é **montado** do celular no container em vez de
copiado na imagem — editar o script não exige rebuild.
- **Nunca reconstrua imagem com containers rodando**, e não reinicie o daemon
durante um build.
- Imagens pesadas: `manim-celular:1` ~1,5 GB, `pdf-tool:1` ~718 MB, `web:1` ~86 MB.
Confira espaço antes (`df -h ~`). A antiga imagem de navegador (`navegador:1`) saiu do repo:
nenhum wrapper a usava (Chromium não roda sob proot) e ~1,5 GB só para isso não se pagava — o
headless é nativo. As
imagens não podem diferir por *tag* apenas: uma imagem por arquitetura, ver acima.
- **Nunca `pkill -f udockerd`**: a própria linha de comando casa com o padrão e
  mata a sua shell (e o daemon). Use o pidfile: `docker daemon down`.
- **Contêiner morto à força deixa o rootfs inteiro para trás.** Quando o processo
  é encerrado com SIGKILL (um `timeout` estourando, um Chromium travado), o `--rm`
  nunca roda e o diretório do contêiner fica com uma **cópia completa da imagem**.
  Medido no aparelho: 8 × `navegador:1` + 1 × `ubuntu:24.04` = **10,6 GB** parados
  sem ninguém usando. (Ctrl-C e `SIGTERM` já não causam isso: o `docker-direct`
  repassa o sinal e roda o `--rm` no fim; só SIGKILL ainda deixa sobra, e um
  `-d --rm` é limpo no `docker stop` ou no próximo `docker ps`.) Confira com
  `~/docker-termux/udocker-1.3.17/udocker/udocker ps` (`W` na coluna de estado =
  parado; PID vazio = não está rodando) e limpe com `udocker rm <id>` — nunca um
  que apareça rodando. Depois da limpeza o motor segue normal (o rootfs é
  recriado da imagem): confirme com `docker-direct run --rm alpine echo ok`.
- **Matar o wrapper não mata os filhos.** Encerrar um `benchmark.sh` (ou qualquer
  script que chame o motor) deixa o `udocker run`, o `proot` e **toda a árvore do
  Chromium** vivos, agora órfãos com `PPid 1` — ~150 MB deitados sem ninguém
  usando (medido: 152 MB). Pior: um `pkill -f udocker` os pegaria e levaria o
  daemon junto. Limpe **por PID explícito**, conferindo antes a árvore
  (`/proc/<pid>/stat` campo PPid) e preservando o `udockerd` e o `hermes
  dashboard`. Rode `docker run` sempre com `--rm` para não acumular.
- **Não reinicie o daemon com build rodando.** `docker daemon down` mata o grupo
  de processos e leva os containers junto — um `docker build` em andamento morre
  com `proot info: vpid 1: terminated with signal 15` e o Dockerfile segue com
  pacotes pela metade (ex.: `pip: not found` no passo seguinte). Termine o build
  antes de mexer no daemon.
- **`pip` não existe no Ubuntu 24.04**: use `python3 -m pip` no Dockerfile, senão
  o passo falha com `/bin/sh: 1: pip: not found`.
- **O daemon precisa ser desgarrado** (`setsid`, PPid 1) para sobreviver ao fim da
  sessão do Hermes; `docker-daemon-up` cuida disso.
- Alternativas quando o pedido é "uma distro Linux no celular": `proot-distro`
  (mantido pelo Termux: pull OCI, `build` de Dockerfile, `push`, cross-arch) —
  na prática faz mais que a camada daemon para esse caso de uso.

## Antes de dizer "isso é novo" — prior art e alternativas

No repositório docker-termux, a seção "O que já existia antes" do `README.pt-BR.md`, a §4 do
`CAPACIDADES.pt-BR.md` e o `AUTHORS.pt-BR.md` reúnem o que já existe publicado para containers no
Android (udocker empacotado no APT do Termux, `Termux-Udocker`, `udockerd`, `cdriv`, `proot-distro`,
e os caminhos QEMU/root para Docker **de kernel**) e o que cada um resolve. Leia antes de reivindicar
ineditismo, antes de escolher caminho e antes de publicar — o usuário exige a seção "o que já
existia antes", e checar prior art converte "sou o primeiro" (frágil) em "não achei publicado"
(verificável).

Para medir o custo real no aparelho (tempo + pico de RAM por amostragem de `/proc`):
`bash testes/benchmark-headless.sh [url-estatica] [url-js]` no repositório — a função `medir`
dele serve para qualquer comando. Foi o instrumento que produziu a tabela headless acima — os
~1 GB do Chromium nativo surpreendem e vale reconferir em aparelho novo.

## Antes de instalar por tarball: o pacote oficial já resolve metade

`pkg install udocker` (1.3.17-5, `Depends: curl, proot, python, resolv-conf`) já
traz **proot do Termux 5.1, o `link2symlink` e o DNS** — ou seja, os defeitos 1, 2,
3 e 5 desta skill **não existem** nessa via (medido: `sh -c "uname -m"`, `apk add`,
`wget example.com` todos OK). A caçada descrita abaixo só é necessária para quem
parte de tarball próprio, ou para quem precisa da camada daemon.

O udocker puro **não** tem `build`, `exec` nem `logs` (subconjunto real:
`pull create run images ps rm rmi tag import export save inspect verify setup login
logout`) — isso é o que a camada daemon deste repositório acrescenta. E o defeito do
sufixo `:ro` **continua** no pacote oficial (verificado: cria `/destino:ro` e não
monta), então esse é um bug legítimo a reportar upstream.

## Verificação obrigatória

    docker doctor
    docker run --rm alpine sh -c "uname -m; apk add --no-cache curl >/dev/null && echo apk-ok"
    docker run --rm debian:bookworm-slim sh -c "apt-get update -qq >/dev/null && echo apt-ok"
    docker run --rm python:3.12-alpine sh -c "pip install -q requests && echo pip-ok"
    docker run -it --rm alpine sh

O teste que pega o defeito 1 é `sh -c` com applet **externo** (`uname -m`), não
`echo` (builtin). O que pega o defeito 2 é `apk add`/`apt-get install`.

## O que NÃO existe neste modo

`docker compose`, `docker network`, `docker volume` como objetos, swarm,
BuildKit, healthcheck, restart policy, `--memory/--cpus`, `docker push`.
Rede não é isolada (porta do container = porta do Termux; `-p` é ignorado).
`docker run` sem `--rm` acumula containers parados.
