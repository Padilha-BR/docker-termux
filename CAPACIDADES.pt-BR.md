# O que este "Docker" no celular pode, não pode, e poderia

**English:** [read in English](CAPACIDADES.md).

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
| **HTTP puro** (nível 1) | extrai texto/links **nativo em 1,7 s** (~34 MB); o mesmo fetch pelo container levava 16 s |
| **Chromium headless** (nível 2) | **nativo** (não no container): estática **2,8 s**, SPA **4,7 s**, PNG, PDF |
| **Selenium + chromedriver** (nível 3) | clique real, espera por elemento, screenshot em **4,0-4,8 s** |
| **CDP puro** (nível 3 mais rápido) | lê título, executa JS e tira screenshot em **1,9-2,5 s**, sem Selenium |
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

### 2.2 Playwright: sem wheel para Android em Python — mas funciona via Node

`pip install playwright` → `No matching distribution found` (não há wheel para
Android/aarch64). A automação de navegador **em Python** aqui é **chromedriver + Selenium**
(`selenium` é Python puro e instala normal).

**Em Node ele funciona** — medido, com duas chaves. Veja a §3.6.3.

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

## 3.5 E se você usar **só o udocker oficial**? (medido em 15/10/2026)

O udocker virou pacote oficial do Termux (`pkg install udocker`, 1.3.17-5,
`Depends: curl, proot, python, resolv-conf`). Rodei nele a mesma bateria que
revelou os defeitos deste repositório:

| Defeito | No udocker **oficial** |
|---|---|
| proot 4.8.0 não rastreia filhos (SIGSYS em `apk`/`pip`) | ✅ **resolvido** — o pacote depende do `proot` do Termux (5.1) |
| hardlink negado no rootfs | ✅ **resolvido** — o `link2symlink` já vem tratado |
| container sem DNS | ✅ **resolvido** — dependência `resolv-conf` injeta os nameservers |
| `LD_PRELOAD` do termux-exec quebrando o proot | ✅ **resolvido** |
| `-v origem:destino` (volume simples) | ✅ funciona igual |
| **`-v origem:destino:ro`** | ❌ **mesmo defeito**: cria um caminho literal `/destino:ro` e o mount não acontece |
| `--platform=linux/amd64` no `run` | ❌ ignora a plataforma: devolveu `aarch64` |
| `build`, `exec`, `logs` | ❌ **não existem** — o subconjunto é `pull/create/run/ps/rm/rmi/tag/import/export/save/inspect/setup/...` |

### 3.5.1 "Então o do repo faz tudo que o udocker faz?" — **não**

São **interfaces diferentes sobre o mesmo motor**, não um superconjunto. O comando
`docker` deste repositório passa quase tudo para a **CLI oficial do Docker**, que
fala a API do daemon; os dois compartilham o mesmo `~/.udocker`, então as imagens
servem para ambos (e o `udocker` oficial pode ficar instalado junto).

| Exclusivo do **udocker** | passa pelo `docker` do repo? |
|---|---|
| `verify`, `protect`, `unprotect`, `mkrepo`, `setup` | ❌ não existem na CLI do Docker |
| `name`, `rmname`, `clone` (nomeação de container) | ❌ idem |
| `create`, `run`, `pull`, `images`, `ps`, `rm`, `rmi`, `tag`, `save`, `export`, `import`, `inspect`, `login`, `logout` | ✅ cobertos (via API do Docker) |

| Exclusivo do **`docker`** (o do repo) | existe no udocker? |
|---|---|
| `build`, `exec`, `logs` | ❌ não existem no udocker |
| `cp`, `commit`, `diff`, `events`, `stats`, `top`, `wait`, `attach` | ❌ idem (dependem da API do daemon) |

Some-se que a CLI lista uns 45 comandos, mas **só os que o daemon implementa
funcionam de fato** — o resto existe na ajuda e falha na execução.

### 3.5.2 Ponho as duas para conversar? Sim — está implementado e testado

Duas pontes de uma linha cada, nas duas direções:

| você digita | vai para | por quê |
|---|---|---|
| `docker verify/protect/unprotect/mkrepo/setup/name/rmname/clone` | udocker | a API do Docker não tem esses comandos |
| `udocker build/exec/logs/compose` | `docker` do repo (daemon) | o udocker não tem esses |
| qualquer outro `docker …` | CLI oficial → daemon | comportamento normal |
| qualquer outro `udocker …` | udocker oficial | idem |

**Por que é seguro:** o daemon **não** passa pela ponte. O `udockerd` importa a lib
do udocker em Python (`from udocker.container.structure import ContainerStructure`),
nunca o binário do PATH — então sobrescrever `udocker` pelo wrapper não toca no que
já funcionava. Verificado depois de instalar as duas pontes:
`docker run --rm alpine echo ok` respondeu, `docker setup --help` chegou ao udocker
e `udocker build --help` chegou ao Docker.

**Custo honesto:** o wrapper fica no PATH **antes** do binário oficial, então
scripts de terceiros que chamam `udocker` passam por ele. É transparente (repassa
tudo o que não é `build`/`exec`/`logs`), mas é mais uma peça para dar errado — e
`UDOCKER_REAL` existe para apontar a outro binário.

**Conclusão honesta:** se você só quer **executar** imagens, `pkg install udocker`
resolve — e resolve sozinho três dos cinco defeitos que este repositório documenta
(a caçada aqui só foi necessária porque partimos de um tarball próprio). O que o
udocker puro **não** dá é `docker build`, `docker exec`, `docker logs` e a API do
Docker — é exatamente isso que a camada daemon deste repositório acrescenta, e é
ela que traz os três defeitos do `udockerd` que o dispatcher contorna.

---

## 3.6 Alternativas que existem hoje — o que **medimos** e o que não testamos

Registrado em 15/10/2026. Tudo abaixo marcado "medido" foi executado neste
aparelho; o resto é leitura de documentação de terceiros, e está marcado como tal.

| Alternativa | Estado | Números |
|---|---|---|
| `pkg install udocker` (oficial) | ✅ **medido** — resolve 4 dos 5 defeitos deste repo | ver §3.5 |
| **[Doki](https://github.com/OpceanAI/Doki)** v0.12.0 (binário Android ARM64, 14 MB) | ⚠️ **medido, com lacunas graves** | `run alpine echo` **0,79 s**, `pull alpine` 5,5 s, `doki-compose` existe; `-v x:/teste` monta certo, **mas `:ro` é ignorado** (§3.6.2) |
| **CDP puro** (Chromium nativo + `websockets`) | ✅ **medido** | página estática em **1,9 s** contra 4,3 s do Selenium, sem `chromedriver` |
| Playwright **via Node/npm** | ✅ **medido — funciona** | navegador no ar em **0,5 s**, react.dev renderizado em **1,4 s** (6583 chars), screenshot 1280×720, ~830 MB de RAM; veja a §3.6.3 |
| **[Podroid](https://github.com/ExTV/Podroid)** (APK, QEMU + kernel próprio) | 📄 **não testado** | Docker/Podman/LXC reais sem root, Android 14+ |
| **proot-distro v5** | 📄 **não testado** | traz udocker integrado, `--bind`, `--shared-home` |

### 3.6.2 O Doki aceita `:ro` e **ignora** — falha silenciosa (medido)

Melhor que o udocker em um ponto e **pior** em outro, e o detalhe importa:

    doki run --rm -v "$TMPDIR/doki-ro:/teste:ro" alpine sh -c "echo escrito > /teste/novo.txt"
    # o comando PASSOU e o novo.txt APARECEU no host

| | udocker | Doki |
|---|---|---|
| `-v x:/teste:ro` | monta em `/teste:ro` e o arquivo não aparece — **falha visível** | monta no lugar certo e **deixa escrever** — **falha silenciosa** |

O udocker erra o caminho, o que você percebe na hora. O Doki aceita a sintaxe e
**descarta a restrição de read-only**: quem escreve `:ro` achando que protegeu o
host está desprotegido. Para um mount só-leitura vindo de dado de terceiro, isso
é pior que o erro do udocker — por isso vai como bug prioritário no upstream.

### As duas lacunas do Doki (medidas, com evidência)

1. **Rede dentro do container não funciona.** O daemon roda
   `dns server started ... addr 127.0.0.11:8053` e explica que a porta 53 é
   bloqueada por SELinux — mas o `/etc/resolv.conf` que ele entrega ao container
   aponta para `nameserver 127.0.0.11` **sem porta**, ou seja, para a 53. Resultado:
   `apk add`/`curl`/`wget` de dentro do container não resolvem. `--network host`
   não mudou isso aqui.
2. **`build` recusa o contexto**: `Error: build context outside allowed directory`,
   inclusive com o contexto dentro de `$HOME`.

Isso não invalida o Doki — ele ainda é mais rápido e mais simples que a solução
deste repositório, **e o `:ro` que nos morde não existe nele**. Mas hoje ele não
substitui este stack para o caso que mais usamos (rede + `apk`/`apt` dentro do
container). São bugs a acompanhar; os dois têm reprodução mínima e merecem ser
reportados no upstream.

### 3.6.3 O Playwright **roda** no Android — via Node, com duas chaves (medido)

Este documento dizia "não testado" no dia anterior. Agora está testado, e funciona.

A pegadinha: o Playwright se recusa a subir com `Unsupported platform: android`, lançado
pelo próprio `computeDefaultCacheDirectory()` dele — ele só conhece darwin/linux/win32.
Duas coisas são necessárias:

1. **`PLAYWRIGHT_BROWSERS_PATH=0`** — com isso o Playwright para de calcular um diretório
   de cache e para de morrer no arranque.
2. **`executablePath`** apontando para o Chromium do próprio Termux
   (`$PREFIX/bin/chromium-browser`) — o Chromium que o Playwright baixaria é um build
   glibc e não roda em Android/bionic.

```js
const { chromium } = require("playwright-core");
const b = await chromium.launch({
  executablePath: "/data/data/com.termux/files/usr/bin/chromium-browser",
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
});
```

Instale com `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm i playwright-core` — não faz sentido
baixar um navegador que não roda.

Medido, três rodadas seguidas (as três concordaram):

| Etapa | Tempo | RAM |
|---|---|---|
| navegador no ar (Node) | **0,5 s** | 416-421 MB |
| `goto react.dev`, texto renderizado | **1,4 s** (6583 chars) | 829-835 MB |
| `locator(...).innerText()` com auto-wait | **0,2-0,4 s** | — |
| screenshot (PNG 1280×720, válido) | 0,1-0,5 s | — |
| **total** | **3,0-3,2 s** | ~830 MB de pico |

Auto-wait, locators, `page.evaluate`, screenshot e `page.title` funcionam normal.
Ressalva honesta: os mesmos ~830 MB de RAM do Chromium nativo, e portanto a mesma regra —
um navegador por vez. Para extrair texto puro isso é exagero; o `webget` faz em 1,7 s com
34 MB. O Playwright ganha o lugar dele quando o script precisa da *API* (auto-wait,
locators, tracing), não da velocidade bruta.

### Becos sem saída confirmados por terceiros (não perca tempo)

| Tentativa | Resultado |
|---|---|
| `podman` rootless dentro do proot | `cannot clone: Invalid argument` — mantenedor do Podman: *"proot is not powerful enough to run Podman"* ([podman#26186](https://github.com/containers/podman/issues/26186)) |
| `runsc`/gVisor | panics no Android ([gvisor#12544](https://github.com/google/gvisor/issues/12544)) |
| `pkg install docker` sem root | não existe: o pacote vive em `root-packages/` e exige root + kernel compatível |

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
| ler texto de uma página | **HTTP puro** (`webget`, nativo) — 1,7 s e 34 MB; resolve mais do que parece (SSR) |
| **imagem** da página (PNG/PDF) | `webprint` (Chromium **nativo**) — 1 GB de RAM, mas é o único que dá imagem |
| clicar, preencher, esperar elemento | `webcdp` (CDP puro, 1,9 s) ou `webplay` (Selenium) |
| página sem texto no DOM (canvas) | **nenhum** extrai texto: nem HTTP, nem Chromium |
| `docker compose`, cgroups, rede isolada | **não dá** — QEMU (lento) ou root |
| automação de um sistema com cota de sessão | **HTTP puro, nunca navegador** — o navegador abre sessão de verdade e a cota é a mesma |
