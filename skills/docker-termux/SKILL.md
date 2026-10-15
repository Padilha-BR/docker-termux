---
name: docker-termux
description: "Use when rodando Docker no Termux/Android sem root."
version: 2.0.0
platforms: [linux]
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
| **daemon** (`udockerd` + CLI oficial 29.x em `~/docker-termux/bin/docker`) | sempre que o daemon sobe | `run`, `build`, `exec`, `logs`, TTY, `pull`, `ps`, API do Docker em `tcp://127.0.0.1:2375` |
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

## Armadilhas que custam tempo

- **`docker logs` precisa de TTY** no daemon 0.3.5: sem `-t` a saída do container
  principal vai para o log do daemon. O dispatcher insere `-t` em `run -d` e avisa.
  Logs de `exec` são capturados normalmente (`~/.udockerd/logs/exec/`).
- **O supervisor do udockerd compila on first use** (`~/.udockerd/udockerd-supervisor-*`);
  precisa de `cc`/`clang`. Sem ele, `docker logs` do container principal fica vazio.
- **`curl` não entende `tcp://`**: para checar o daemon use
  `http://127.0.0.1:2375/_ping` (o `DOCKER_HOST` é que é `tcp://`).
- **Uma arquitetura por tag**: `pull --platform=linux/amd64 alpine:latest`
  sobrescreve a imagem arm64 local daquela tag. Para voltar, pull sem `--platform`.
- **Nunca `pkill -f udockerd`**: a própria linha de comando casa com o padrão e
  mata a sua shell (e o daemon). Use o pidfile: `docker daemon down`.
- **O daemon precisa ser desgarrado** (`setsid`, PPid 1) para sobreviver ao fim da
  sessão do Hermes; `docker-daemon-up` cuida disso.
- Alternativas quando o pedido é "uma distro Linux no celular": `proot-distro`
  (mantido pelo Termux: pull OCI, `build` de Dockerfile, `push`, cross-arch) —
  na prática faz mais que a camada daemon para esse caso de uso.

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
