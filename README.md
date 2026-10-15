# docker-termux — Docker num Android sem root

> **O que dá e o que não dá, medido no aparelho:** [`CAPACIDADES.md`](CAPACIDADES.md) —
> capacidades verificadas, limites com causa raiz, o que é teoricamente possível e o
> que já existia antes (créditos).

> **English version below (scroll down).**

Relato de campo: como fazer `docker` funcionar num celular Android sem root, sem
daemon de kernel, sem cgroups e sem user namespaces — medido num Galaxy S24 Ultra
(Android 16, arm64, kernel 6.1.145), tudo digitado e executado dentro do Termux.

---

## Primeiro, o que isto NÃO é

**Docker de verdade é impossível sem root.** Medido, não suposto:

```
$ unshare -U true
unshare: unshare failed: Invalid argument
```

O Android bloqueia *user namespaces* para aplicativos. Sem isso não existe
daemon, cgroup isolado, overlayfs nem rede própria. `/proc/filesystems` e
`/sys/fs/cgroup` respondem `Permission denied`. Quem promete "Docker completo no
Termux sem root" está vendendo outra coisa.

**O que este repositório entrega:** duas camadas que, juntas, dão a experiência
do Docker na parte que importa (`pull`, `run`, `build`, `exec`, `logs`, `ps`,
`rm`, TTY, imagens de outra arquitetura por emulação) usando execução em
userspace com `proot`.

---

## O que já existia antes (créditos)

Este trabalho **não** inventou containers rootless no Android. Apoia-se em
projetos que já resolviam partes do problema:

| Projeto | O que já fazia |
|---|---|
| [udocker](https://github.com/indigo-dc/udocker) | Fala com o Docker Hub, baixa camadas OCI, monta rootfs, executa com proot/fakechroot — sem root |
| [udockerd](https://pypi.org/project/udockerd/) | Daemon compatível com a **API do Docker** sobre udocker, feito para Termux; cobre create/start/stop/exec/logs/TTY e `docker build`; já traz `--dns` e recomenda o `proot` oficial do Termux |
| [proot-distro](https://github.com/termux/proot-distro) | Já puxa imagens OCI do Docker Hub/GHCR/quay, faz `build` de Dockerfile sem daemon, `push`, cross-arch por qemu — e usa `--link2symlink` e o bind de `/linkerconfig/com.android.art/ld.config.txt` |
| [termux/proot](https://github.com/termux/proot) (issues [#75](https://github.com/termux/proot/issues/75), [#149](https://github.com/termux/proot/issues/149)) | Já documentavam `link()` negado por SELinux, `PROOT_NO_SECCOMP=1` e a whitelist de syscalls do bionic |
| [termux/termux-app#837](https://github.com/termux/termux-app/issues/837) | Explica que hardlink é bloqueado por hardening do SELinux e que `--link2symlink` é a saída |

Toda a base é deles. O que **este** repositório acrescenta, até onde
verificamos e não encontramos publicado:

1. O **diagnóstico medido** de por que o caminho `udocker` (que baixa seu
   próprio proot 4.8.0, o `udockertools`) quebra no Android: qualquer
   `fork+exec` dentro do container morre com **SIGSYS (signal 31)**, enquanto
   `exec` direto funciona. Isso derruba `apk`, `apt-get`, `pip` e qualquer script.
2. A **correção mínima** para isso: um *shim* de um arquivo que aponta o udocker
   para o `proot` 5.1 do Termux, com `--link2symlink`.
3. Os outros três defeitos de ambiente e suas correções (`resolv.conf`
   inexistente no Android, `qemu` não encontrado, ruído do linker do Android em
   imagens amd64), com os sintomas e os comandos que os comprovam.
4. Um instalador idempotente que monta as **duas** camadas (modo direto e
   daemon) e um `docker doctor` que confere cada peça.

Se você só quer containers no Termux, **use o `proot-distro`** — é mantido pelo
time do Termux e faz mais. Este repositório existe para o caso de você querer a
API/CLI do Docker (`docker build`, `docker exec`, `docker logs`) e para
documentar as armadilhas com medições reproduzíveis.

---

## Arquitetura

```
                        comando `docker` (seu)
                                |
                    [ dispatcher: .hermes/bin/docker ]
                       |                          |
        daemon no ar?  |                          | daemon não sobe
                       v                          v
   CAMADA 2: daemon (API do Docker)        CAMADA 1: modo direto
   CLI oficial estatica (arm64)            udocker + proot 5.1 na hora
   <-> udockerd 0.3.5 (tcp 127.0.0.1:2375) sem build/exec/logs
   -> execucao real: proot 5.1 do Termux
```

- **Camada 1 (modo direto):** `udocker` + `proot` do Termux, sem daemon, sem pip.
  Roda container, tem DNS, volumes, `-d`/`logs` próprios. `docker-direct`.
- **Camada 2 (daemon):** `udockerd` expõe a API do Docker e a CLI oficial do
  Docker (binário estático arm64) fala com ele. Habilita `docker build`,
  `docker exec`, `docker logs`, TTY e qualquer cliente de API.

Ambas executam de verdade via **proot 5.1 do Termux** — nenhuma tem namespaces
de kernel.

---

## Instalação

```sh
git clone https://github.com/Padilha-BR/docker-termux
cd docker-termux
bash docker-termux-setup          # idempotente; --force refaz downloads
docker doctor                     # confere cada peça
```

O instalador cuida de: `proot`, `qemu-user-x86-64`, runtime udocker, shim do
proot, patch do qemu, venv do udockerd, compilação do supervisor, download da CLI
oficial, scripts, atalhos e `resolv.conf`.

---

## Uso

```sh
docker pull alpine                       # imagem arm64 (nativa, rápida)
docker pull --platform=linux/amd64 alpine  # imagem x86 (emulada por qemu)
docker run --rm alpine sh -c "uname -m; apk add --no-cache curl && curl -s example.com"
docker run -it --rm debian:bookworm-slim bash

docker run -d --name=web -v $HOME/site:/site python:3.12-alpine sh /site/serve.sh
docker logs web
docker exec web cat /etc/alpine-release
docker stop web && docker rm web

printf 'FROM alpine:3.20\nRUN apk add --no-cache jq\nCMD ["jq","--version"]\n' > Dockerfile
docker build -t minha-imagem .           # build de verdade, sem daemon
docker run --rm minha-imagem

docker doctor        # diagnóstico
docker daemon up     # sobe/derruba o daemon explicitamente
docker-direct ...    # força o modo sem daemon (sempre disponível)
```

---

## Os cinco defeitos do Android (e as correções)

Todos encontrados por medição (`proot -v 9`, bisseção de variáveis de ambiente,
trace de syscall), não por chute.

### 1. O proot que o udocker baixa não rastreia processos filhos

```sh
$ udocker run alpine sh -c "uname -m"     # exit 255
proot info: vpid 1: terminated with signal 31
$ udocker run alpine uname -m             # funciona: aarch64
```

Regra que resume o sintoma: **builtin do shell passa, applet externo morre.**
`echo` e `pwd` funcionam; `uname`, `cat`, `apk`, `apt`, `pip` — qualquer coisa que
faça `fork+exec` — morre com SIGSYS. O proot do udocker é o `udockertools-v1.1.4`
(proot 4.8.0); o do Termux é 5.1.107, com as correções de seccomp/arm.

**Correção:** um shim em `~/.udocker/bin/proot-arm64-4_8_0` (o udocker executa
esse caminho) que delega ao proot do Termux, mantendo as flags que o udocker usa
(`--kill-on-exit`, `-b`, `-0`, `-k/--kernel-release`, `-r`, `-w`, `-v`):

```sh
exec /data/data/com.termux/files/usr/bin/proot --link2symlink "$@"
```

### 2. O Android nega hardlink dentro do rootfs

```sh
$ apk update
WARNING: updating and opening https://...: Permission denied
$ apk add --no-cache curl
(9/9) Installing curl
ERROR: System state may be inconsistent: failed to write database: Permission denied
```

Os pacotes instalam, mas o apk não consegue gravar o banco — porque `link()` é
negado pelo SELinux para aplicativos comuns (a issue #837 do termux-app documenta
isso). **Correção:** `--link2symlink` (a mesma flag que o proot-distro usa).
Depois: `OK: 28554 distinct packages available`.

### 3. O Android não tem `/etc/resolv.conf`

O container sobe sem DNS: `wget: bad address 'example.com'`. A opção `--dns=`
do udocker não basta. **Correção:** escrever
`nameserver 8.8.8.8` em `~/.udocker/containers/<ctr>/ROOT/etc/resolv.conf`
(o CLI faz isso automaticamente; `docker dns-fix` conserta os antigos).
Depois: `HTTP 200`.

### 4. Imagem amd64 não encontra o qemu

```
Warning: qemu required but not available
proot info: vpid 1: terminated with signal 7      # SIGBUS
```

O udocker passa apenas o **nome** do binário (`-q qemu-x86_64`) e o proot procura
no `$PATH` do *container*, que não tem qemu. **Correção:** patch de uma linha em
`udocker/engine/proot.py` (`self._get_qemu(return_path=True)`) + `pkg install
qemu-user-x86-64`. Depois: `uname -m` → `x86_64` em **1,6 s**.

### 5. O `LD_PRELOAD` do termux-exec quebra qualquer proot

```
proot error: execve("/bin/busybox"): No such file or directory
```

…com o `/bin/busybox` presente e executável. O Termux injeta
`libtermux-exec-ld-preload.so` em todo comando; o loader do container tenta
carregar essa biblioteca e falha. Foi isolado por bisseção — é a única variável
do ambiente que mata o processo. **Correção:** remover `LD_PRELOAD` (e
`LD_LIBRARY_PATH`) antes de chamar o motor.

### Bônus: ruído do linker

Imagem amd64 imprime `WARNING: linker: failed to find ... /linkerconfig/ld.config.txt`
a cada processo (o qemu é um binário Android rodando sob o proot).
**Correção:** bind `-v /linkerconfig:/linkerconfig` — `/linkerconfig` é legível
pelo Termux (o proot-distro faz o mesmo com o caminho do ART).

---

## Verificação (reproduza)

```sh
docker doctor
docker run --rm alpine sh -c "uname -m; apk add --no-cache curl >/dev/null && echo apk-ok"
docker run --rm debian:bookworm-slim sh -c "apt-get update -qq >/dev/null && echo apt-ok"
docker run --rm python:3.12-alpine sh -c "pip install -q requests && echo pip-ok"
docker run -it --rm alpine sh
```

O teste que pega o defeito 1 é `sh -c` executando applet **externo** (`uname -m`),
não `echo` (builtin). O que pega o defeito 2 é `apk add`/`apt-get install`.

Medições desta máquina: `docker build` de um Dockerfile com `apk add jq` em
**13,8 s**; `proot-distro build` equivalente em 3,4 s (3 layers, 4,4 MiB);
imagem amd64 executando em **1,6 s**; ~370 MB de imagens em disco após os testes.

---

## O que o dispatcher conserta por você (achado testando)

Três diferenças do daemon `udockerd` 0.3.5 que custariam tempo, todas já
tratadas automaticamente pelo comando `docker`:

| sintoma | causa | o que o dispatcher faz |
|---|---|---|
| `docker pull` falha com `no image found in manifest for platform (android/arm64)` | a lib do udocker detecta a plataforma como **android/arm64** e o Docker Hub não publica isso | roteia `pull` para o motor direto, que puxa com `--platform=linux/arm64`; o daemon enxerga a imagem depois (mesmo `~/.udocker`) |
| `docker run -v` monta **nada**, sem erro | o udockerd nunca lê `HostConfig.Binds` (a string `Binds` não existe no código dele; o motor udocker por baixo tem o suporte, mas `opt["vol"]` fica vazio) — [issue #9](https://github.com/bjia56/udockerd/issues/9) | detecta `-v`/`--volume`/`--mount` e roda pelo motor direto, que monta via `-b` do proot |
| `docker build` falha com `no such image: <base do FROM>` | o builder do daemon não puxa o `FROM` (o Docker real puxa) | lê o `Dockerfile` do contexto, acha as imagens base e puxa antes de construir |
| `docker logs` de container destacado volta vazio | sem TTY o stdout herda o do daemon — [issue #8](https://github.com/bjia56/udockerd/issues/8) | insere `-t` em `run -d` e avisa |

## Binds e navegador: dois achados medidos

**1. `-v` não aceita `:ro`.** `-v /host/script.py:/ctr/script.py:ro` não monta nada
e ainda cria um arquivo chamado `script.py:ro` dentro do destino — o container
falha com `can't open file '/ctr/script.py'`. Use a forma pura `-v origem:destino`
(vale para arquivo e para diretório). Prova de que o bind pegou: `sha256sum` do
arquivo dentro e fora devem bater.

**2. Nenhum Chromium sobrevive ao `proot`** — e a cura é não usar container para
isso. Medido com Chrome for Testing 156 e `chrome-headless-shell` 156 (arm64
nativos): `Trace/breakpoint trap` (SIGTRAP), `Target crashed`, ou loop de
`crashpad ... tgkill: No such process` até estourar o timeout. Testado
`--no-sandbox`, `--single-process`, `--no-zygote`, `--headless=old` e
`GLIBC_TUNABLES=glibc.pthread.rseq=0` — nenhum resolve. Causa: o `proot`
intercepta syscalls por **ptrace**, e o crashpad do Chromium também depende de
ptrace/processos filhos.

| via | página estática | SPA (só JS) | RAM pico |
|---|---|---|---|
| HTTP puro (`webget`, dentro do container) | 4,3 s | falha (volta vazio) | ~34 MB |
| **Chromium NATIVO do Termux** (`webprint`) | 2,8 s | **6,2 s, renderizado** | ~1 GB |
| Selenium + `chromedriver` nativo (`webplay`) | 4,0 s | OK | ~1 GB |

```sh
pkg install x11-repo && pkg install chromium   # binário: chromium-browser
chromium-browser --headless=new --no-sandbox --disable-gpu \
    --disable-dev-shm-usage --virtual-time-budget=8000 --dump-dom URL
```

O `chromedriver` vem no mesmo pacote e roda com `selenium` (Python puro) — o
Playwright **não existe para Android** (nenhum wheel no PyPI). Os wrappers
`webprint` (nível 2) e `webplay` (nível 3, com o helper `webauto.py`) usam essa
via. Custo honesto: o Chromium nativo come ~1 GB de RAM — prefira HTTP puro
quando o HTML já traz o conteúdo, e nunca rode dois Chromiums em paralelo.

## Limitações honestas

- **Não reinicie o daemon com um build rodando:** `docker daemon down` mata o
  grupo de processos e leva o build/containers junto (morre com
  `terminated with signal 15` e o Dockerfile continua com pacotes pela metade).
- No Ubuntu 24.04 use `python3 -m pip` no Dockerfile — o comando `pip` não existe.
- `docker compose`, `docker network`, `docker volume` (como objetos), `swarm`,
  BuildKit, healthcheck, restart policy, `--memory/--cpus` e `docker push` não
  existem neste modo.
- **Rede não é isolada:** o container usa a pilha de rede do Termux, então o
  serviço já escuta direto na porta (o `-p` é ignorado de propósito).
- **`docker logs` de container destacado exige TTY** no udockerd 0.3.5: sem
  `-t`, a saída do processo principal herda o stdout do daemon e `docker logs`
  volta vazio (o Docker real não precisa disso). Comprovado variando só o `-t`,
  com a CLI direta e o supervisor já compilado:

  ```sh
  docker run -d  --name=c1 alpine sh -c "echo SEM-T; sleep 15"; docker logs c1   # vazio
  docker run -dt --name=c2 alpine sh -c "echo COM-T; sleep 15"; docker logs c2   # COM-T
  ```

  Por isso o dispatcher insere `-t` em `run -d` e avisa. O supervisor
  (`~/.udockerd/udockerd-supervisor-*`, compilado pelo instalador) também é
  necessário para não deixar processos órfãos.
- `docker run` sem `--rm` acumula containers parados (igual ao Docker real).
- O Android suspende processos em segundo plano: para serviços longos, garanta a
  bateria sem restrições para o Termux e mantenha wake-lock.
- Uma arquitetura por tag: `pull --platform=linux/amd64 alpine:latest` substitui
  a imagem arm64 local daquela tag.

---

## Autoria e como citar

Feito por **Gabriel Padilha** ([@Padilha-BR](https://github.com/Padilha-BR)), do
trabalho de campo às correções — tudo executado dentro do aparelho, por terminal.

- [`AUTHORS.md`](AUTHORS.md) — o que já existia antes (créditos) e o que é
  contribuição original deste repositório.
- [`CITATION.cff`](CITATION.cff) — citação formal (o GitHub mostra o botão
  *Cite this repository*).
- [`CAPACIDADES.md`](CAPACIDADES.md) — o que pode, o que não pode e o que é
  teoricamente possível, com as medições.

### Estrutura

| caminho | o que é |
|---|---|
| `scripts/` | o dispatcher `docker`, o motor direto, o ciclo do daemon e o instalador |
| `ferramentas/` | `pdf`, `pdfpy`, `webget`, `webprint`, `webplay` e o helper `webauto.py` |
| `imagens/` | Dockerfiles **e as fontes autorais** (`md2pdf`, `webget.py`, `webprint.py`) |
| `testes/` | benchmarks de headless (tempo + RAM) e a bateria de testes do PDF |
| `examples/` | exemplos rodando: Manim (vídeo) e automação web (Selenium) |
| `skills/` | a skill do Hermes que descreve o procedimento |

## Licença

MIT. Os componentes usados mantêm suas licenças: udocker (GPL-2.0),
udockerd (Apache-2.0), proot/proot-distro (GPL-2.0), Docker CLI (Apache-2.0),
qemu (GPL-2.0).

---
---

# docker-termux — Docker on Android without root

> Field report: getting `docker` to work on an Android phone without root, no
> kernel daemon, no cgroups, no user namespaces — measured on a Galaxy S24 Ultra
> (Android 16, arm64, kernel 6.1.145), all typed and executed inside Termux.

## What this is NOT

**Real Docker is impossible without root.** Measured, not assumed:

```
$ unshare -U true
unshare: unshare failed: Invalid argument
```

Android blocks user namespaces for apps. No user namespaces means no daemon, no
isolated cgroups, no overlayfs, no private network. `/proc/filesystems` and
`/sys/fs/cgroup` are `Permission denied`. Anyone promising "full Docker on Termux
without root" is selling something else.

**What you get here:** two layers that together deliver the Docker experience
where it matters (`pull`, `run`, `build`, `exec`, `logs`, `ps`, `rm`, TTY,
cross-architecture images through emulation) using userspace execution with
`proot`.

## Prior art (credit)

This work did **not** invent rootless containers on Android. It stands on
projects that had already solved parts of it: **udocker** (OCI pull + rootfs),
**udockerd** (a Docker-Engine-API-compatible daemon over udocker, built for
Termux, with `docker build`, `--dns`, and a recommendation to use Termux's own
`proot`), **proot-distro** (OCI pulls, Dockerfile builds without a daemon, qemu,
`--link2symlink`, and the `/linkerconfig` bind), and the **termux/proot** and
**termux-app** issues documenting SELinux blocking `link()` and the bionic
syscall whitelist.

Until we found otherwise unpublished, what this repository adds is:

1. The **measured diagnosis** of why the `udocker` path (which downloads its own
   proot 4.8.0) breaks on Android: every `fork+exec` inside the container dies
   with **SIGSYS (signal 31)** while a direct `exec` works — which kills `apk`,
   `apt-get`, `pip` and any script.
2. The **one-file fix**: a shim pointing udocker at Termux's `proot` 5.1 with
   `--link2symlink`.
3. Three further environment defects and their fixes (`/etc/resolv.conf` missing
   on Android, qemu not found for amd64 images, Android linker noise), each with
   the symptom and the command that proves it.
4. An idempotent installer for **both** layers plus a `docker doctor`.

If you just want Linux containers on Termux, **use `proot-distro`** — it is
maintained by the Termux team and does more. This repository exists for the case
where you want the Docker CLI/API (`docker build`, `exec`, `logs`) and for the
reproducible write-up of the pitfalls.

## Install / usage

```sh
git clone https://github.com/Padilha-BR/docker-termux && cd docker-termux
bash docker-termux-setup
docker doctor
docker run --rm alpine sh -c "uname -m; apk add --no-cache curl && curl -s example.com"
docker build -t minha-imagem .     # real build, no daemon
```

See the Portuguese section above for the full defect list, verification commands
and limitations — the two sections describe the same thing.

Two measured findings worth highlighting: `-v` does **not** accept a `:ro`
suffix (it becomes part of the filename), and **no Chromium survives `proot`**
(SIGTRAP / crashpad loop — the `proot` ptrace interception and Chromium's
crashpad collide). The fix for headless browsing is the **native Termux
Chromium** (`pkg install x11-repo && pkg install chromium`), driven by
`webprint` or by `selenium` + the bundled `chromedriver` (`webplay`).
