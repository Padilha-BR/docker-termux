# O que este "Docker" no celular pode, não pode, e poderia

**Onde foi medido:** Galaxy S24 Ultra, Android 16, arm64, kernel 6.1.145-android14-11
(ramo GKI), **sem root**.
Todo número deste documento saiu de execução real no aparelho, não de estimativa.
Onde algo não foi testado, está escrito **"não testado"**.

---

## 1. O que PODE (verificado)

### 1.1 Motor de containers

| Recurso | Estado | Observação |
|---|---|---|
| `pull` de imagem do Docker Hub | ✅ | camadas OCI conferidas por `sha256` idênticas às do Hub |
| `run` (frente, fundo, TTY) | ✅ | container = processo real (`exe → proot`, rootfs montado) |
| `build` de Dockerfile | ✅ | builder clássico, `DOCKER_BUILDKIT=0` |
| `exec` em container vivo | ✅ | via daemon |
| `logs`, `stop`, `rm`, `ps` | ✅ | `logs` exige TTY no daemon (ver §2.4) |
| Volumes/binds do host | ✅ | `-v origem:destino`, arquivo **e** diretório |
| Rede (saída) | ✅ | DNS próprio (`8.8.8.8`) e HTTPS funcionando |
| DNS resolvido no container | ✅ | o Android não tem `/etc/resolv.conf`; é injetado |
| Imagem de **outra** arquitetura (amd64) | ✅ lento | via `qemu-user-x86-64` |
| Alpine (**musl**) e Debian/Ubuntu (**glibc**) | ✅ | `apk` e `apt` instalando |
| `pip` dentro do container | ✅ | inclusive Python 3.12 no Alpine |
| Persistência entre execuções | ✅ | imagens e containers ficam em `~/.udocker` |
| CLI oficial do Docker falando com o daemon | ✅ | API 1.41 |
| `proot-distro` (distro completa, sem daemon) | ✅ | alternativa mais direta para "quero um Linux" |

### 1.2 O que já rodou de verdade aqui (provas, não promessas)

| Tarefa | Resultado medido |
|---|---|
| **Manim** (render de vídeo) | imagem Ubuntu 24.04 + cairo/pango/ffmpeg; vídeo **h264 1280×720 30fps** gerado no aparelho em 30,9 s |
| **Markdown → PDF** tipografado | weasyprint em container, capa/A4/emoji |
| **HTTP puro** (nível 1) | baixa e extrai texto/links: **4,3 s, ~34 MB** |
| **Chromium headless** (nível 2) | **nativo** (não no container): estática **2,8 s**, SPA **4,7 s**, PNG, PDF |
| **Selenium + chromedriver** (nível 3) | clique real, espera por elemento, screenshot em **4,0-4,8 s** |
| `uname -m`, `apk add`, `apt-get install` | tudo exit 0 (os testes que pegam os defeitos de proot) |

---

## 2. O que NÃO PODE, e por quê

### 2.1 Docker de kernel: impossível sem root — e é o limite de tudo

`unshare -U true` → **`Invalid argument`**. O Android não entrega *user namespaces*
para apps comuns. Sem namespace não há:

- daemon `dockerd` de verdade
- cgroups (portanto **sem** limite de CPU/memória por container)
- overlayfs próprio, `docker network`, `docker volume` como objeto
- isolamento real: hoje **a rede do container é a rede do Termux** — um serviço
  que sobe no container já está na sua porta, e `-p` é ignorado de propósito

O que existe aqui é **execução em espaço de usuário** (`proot` + udocker): o binário
roda, mas o kernel não isola nada. Isso não é uma limitação de configuração — é o
kernel do Android.

### 2.2 Playwright não existe para Android

`pip install playwright` → `No matching distribution found` (não há wheel para
Android/aarch64). A automação de navegador aqui é **chromedriver + Selenium**
(`selenium` é Python puro e instala normal).

### 2.3 Chromium **dentro do container** não funciona

Testado exaustivamente: Chrome for Testing 156 e `chrome-headless-shell` 156 (arm64
nativos). Sintomas: `Trace/breakpoint trap` (SIGTRAP), `Target crashed`, ou loop
infinito de `crashpad ... tgkill: No such process`. `--no-sandbox`,
`--single-process`, `--no-zygote`, `--headless=old` e
`GLIBC_TUNABLES=glibc.pthread.rseq=0` — **nenhum resolve**.

**Causa (com a hipótese mais provável descartada):** o `proot` intercepta syscalls
por **ptrace**, e o crashpad do Chromium também depende de ptrace/processos filhos.
Havia uma explicação alternativa conhecida — o bug do `PartitionAlloc` em aarch64
com **page size de 64 KB** (que também dá SIGTRAP) — mas neste aparelho
`SC_PAGE_SIZE` = **4096 bytes**, então **essa hipótese está descartada aqui**.

**A cura é não usar container para isso:** o Chromium **nativo** do Termux
(`pkg install x11-repo && pkg install chromium`) roda em bionic, sem proot, e
funciona — inclusive com o JS renderizado.

### 2.4 Limites do daemon (udockerd 0.3.5)

Três lacunas confirmadas com teste controlado, todas contornadas pelo dispatcher:

| Sintoma | Causa |
|---|---|
| `pull` falha com `no image found in manifest for platform (android/arm64)` | o udocker detecta a plataforma como `android/arm64`; o Hub não publica isso |
| `docker run -v` monta **nada**, sem erro | o daemon nunca lê `HostConfig.Binds` (a string `Binds` não existe no código) |
| `docker build` → `no such image: <FROM>` | o builder do daemon não puxa a imagem base do `FROM` |
| `docker logs` de container destacado volta vazio | sem TTY, o stdout herda o do daemon |

### 2.5 O que simplesmente não existe neste modo

`docker compose`, `docker network`, `docker volume` (como objetos), `swarm`,
BuildKit, healthcheck, restart policy, `--memory`/`--cpus`, `docker push`.
Sem systemd dentro dos containers (proot não roda systemd).

### 2.6 Custos que ninguém menciona

- **`proot` intercepta cada syscall** — daí o overhead constante em tudo.
- **amd64 em arm64** passa por `qemu-user`: multiplique por ~5-20×.
- **Chromium nativo come ~1 GB de RAM** (medido: 1012-1110 MB). Dois headless ao
  mesmo tempo travam a espera por elemento.
- **Container morto à força deixa o rootfs inteiro** no disco: medido aqui, 8
  containers órfãos = **10,6 GB** parados.
- **`-v` não aceita `:ro`** no udocker: o sufixo vira parte do nome do arquivo e a
  montagem falha **em silêncio**.

---

## 3. O que é teoricamente possível (não testado aqui)

Ordenado do mais barato ao mais caro:

| Caminho | O que destrava | Custo |
|---|---|---|
| **`pkg install udocker`** (o udocker é oficial no Termux desde 2025) | dispensa o instalador por tarball deste repo | baixo — **não testado aqui**; este repo usa tarball + correções próprias |
| **`chromedriver` + `cdriv`** (cliente WebDriver em `requests` puro) | mesma automação do Selenium sem a dependência dele | baixo — não testado |
| **QEMU `system` (VM completa) dentro do Termux** | **Docker DE KERNEL de verdade**: `dockerd`, `docker compose`, systemd, cgroups | **10-25× mais lento** (sem KVM para app comum); relatos de terceiros |
| **Root (Magisk) + kernel customizado** | `pkg install root-repo && pkg install docker tini` → Docker nativo | exige desbloquear bootloader (apaga o aparelho) e compilar kernel |
| **Serviços persistentes** (Home Assistant, Jellyfin, Nextcloud) | já existem scripts prontos da comunidade rodando via udocker | depende de boot/wake-lock: o Android suspende processos em segundo plano |

**Onde provavelmente vai bater no muro mesmo assim:** qualquer coisa que exija
`systemd`, iptables, porta privilegiada (< 1024), acesso a hardware/GPU, ou
isolamento de rede de verdade.

---

## 4. O que já existia antes (crédito — nada disto é invenção nossa)

Este trabalho **não inventou** o conceito. O que ele faz é integrar, corrigir e medir:

- **[udocker](https://github.com/indigo-dc/udocker)** — o motor. Documenta o Termux
  como ambiente suportado, e hoje está no repositório oficial: `pkg install udocker`.
- **[George-Seven/Termux-Udocker](https://github.com/George-Seven/Termux-Udocker)**
  (~409 estrelas) — configuração do udocker no Termux + scripts prontos para
  serviços populares. Referência de prior art.
- **[bjia56/udockerd](https://github.com/bjia56/udockerd)** — o daemon compatível
  com a API do Docker sobre o udocker. É a camada daemon usada aqui.
- **[termux/proot](https://github.com/termux/proot)** e o `proot-distro` — o motor
  de execução em espaço de usuário.
- **Chromium/ChromeDriver do Termux** (`pkg install chromium`) e o gist
  *"Run selenium with chrome on termux"* — a via de headless/automação.
- **[Draken119/cdriv](https://github.com/Draken119/cdriv)** — cliente WebDriver em
  `requests` puro para o Termux, feito porque "Playwright/Selenium não funcionam em
  android/aarch64".
- **[OshekharO/Docker-On-Android](https://github.com/OshekharO/Docker-On-Android)** —
  o caminho com root + kernel customizado.
- **QEMU + Docker de verdade** — documentado por terceiros; a alternativa quando
  você precisa de Docker real sem root, pagando 10-25× de lentidão.

---

## 5. O que este trabalho acrescenta de original

1. **Dispatcher de duas camadas com fallback automático**: um comando `docker` que
   decide entre o daemon (completo: `build`/`exec`/`logs`/TTY) e o motor direto
   (volumes e `pull` multi-arquitetura), caindo para o direto se o daemon não subir.
2. **Conserto dos 3 defeitos do `udockerd`** (plataforma `android/arm64` no `pull`,
   `Binds` ignorado, `FROM` não puxado) — decidido e aplicado automaticamente,
   com as issues abertas no upstream ([#8](https://github.com/bjia56/udockerd/issues/8),
   [#9](https://github.com/bjia56/udockerd/issues/9)).
3. **Conserto dos 5 defeitos do proot/Android**, incluindo o shim que troca o proot
   4.8.0 que o udocker baixa pelo **proot 5.1 do Termux** (o 4.8.0 não rastreia
   processos filhos no Android: builtin roda, applet externo morre com **SIGSYS**).
4. **Headless em 3 níveis por custo**, com a medição honesta de tempo **e RAM** de
   cada nível, e o veredito de que **nenhum Chromium roda sob proot aqui**.
5. **Benchmarks medidos** (não estimados) das duas vias headless, incluindo o custo
   real de RAM do Chromium nativo (~1 GB) que a maioria dos tutoriais omite.
6. **Relato de campo das armadilhas** que custam horas: `-v ...:ro` falhando em
   silêncio, containers órfãos comendo 10,6 GB, `pkill -f udockerd` matando a própria
   shell, e o wrapper que morre deixando o Chromium pendurado como órfão.

---

## 6. Decisão rápida: use o quê?

| Preciso de… | Use |
|---|---|
| rodar uma ferramenta Linux que não existe no Termux | `docker run <imagem>` (este repo) |
| um Linux completo para trabalhar | `proot-distro login <distro>` |
| ler texto de uma página | **HTTP puro** (`webget`) — 34 MB contra ~1 GB do navegador |
| página que só existe com JavaScript | `webprint` (Chromium **nativo**) |
| clicar, preencher, esperar elemento | `webplay` (Selenium + chromedriver nativo) |
| `docker compose`, cgroups, rede isolada | **não dá** — QEMU (lento) ou root |
| automação de um sistema com cota de sessão | **HTTP puro, nunca navegador** — o navegador abre sessão de verdade e a cota é a mesma |
