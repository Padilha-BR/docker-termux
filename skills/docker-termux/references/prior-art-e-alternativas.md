# Prior art: o que já existe para containers no Android (e quando usar cada um)

Leia isto antes de (a) reivindicar que algo é novo, (b) escolher o caminho de execução, ou
(c) publicar. O usuário exige a seção "o que já existia antes" — crédito honesto converte
"sou o primeiro" (frágil) em "não achei publicado" (verificável).

## O que já existe

| Peça | O que é | Consequência prática |
|---|---|---|
| `udocker` no APT do Termux | o motor em userspace, hoje empacotado oficialmente (`pkg install udocker`, mesma série 1.3.17, com `proot` como dependência) | o instalador por tarball + shims deste setup **não é o único caminho**; o pacote oficial dispensa boa parte dele |
| George-Seven/Termux-Udocker | configuração do udocker para Termux + scripts prontos (Home Assistant, Jellyfin, Nextcloud, Jupyter) | a referência para "quero rodar o serviço X"; já aponta para o pacote oficial |
| bjia56/udockerd | daemon compatível com a API do Docker sobre o udocker | é a camada daemon usada aqui. Repositório pequeno e as issues de `Binds`/`logs` ficaram sem resposta: **não conte com correção upstream**, o dispatcher local contorna |
| **OpceanAI/Doki** | engine em Go/Rust, **API compatível com Docker e Podman**, 13 MB, binário Android ARM64, sem daemon de kernel | ver a seção própria abaixo: é o concorrente mais sério, com lacunas graves no Android hoje |
| **ExTV/Podroid** | APK que roda uma VM Alpine com **kernel Linux próprio** (QEMU) e traz **Podman, Docker CE e LXC** prontos, sem root (Android 14+) | o caminho "Docker de kernel sem root" empacotado. **Não testado aqui** — cite como leitura, não como recomendação medida |
| pacote `chromium` do Termux | Chromium **nativo** (bionic), com `chromedriver` no mesmo pacote | headless e automação funcionam **sem container**; é a cura para o Chromium não rodar sob proot |
| Selenium + `chromedriver` no Termux | receita conhecida em gist da comunidade | confirma que Selenium roda aqui |
| Playwright | **Python não tem wheel para Android** (`pip install playwright` → `No matching distribution found`). Em **Node/npm funciona — medido**: `playwright-core` + `PLAYWRIGHT_BROWSERS_PATH=0` + `executablePath` apontando para o Chromium nativo | não descarte o Playwright de saída: descarte só a via Python. Medido 3/3: arranque 0,5 s, `react.dev` renderizado 1,4 s, screenshot 1280×720, ~830 MB. A pegadinha é a largada — sem `PLAYWRIGHT_BROWSERS_PATH=0` ele aborta com `Unsupported platform: android` (o build de browser dele é glibc e não roda em bionic) |
| Draken119/cdriv | cliente WebDriver falando HTTP direto, dependência única `requests` | alternativa mais leve quando só se precisa navegar, clicar, ler cookie |
| **CDP puro** | falar Chrome DevTools Protocol por WebSocket direto com o Chromium nativo (`websockets`, ~1,9 s medido aqui) | mais leve que Selenium/chromedriver **e** mais rápido; é o nível 3 padrão deste setup (`webcdp`) |
| `proot-distro` | distros Linux mantidas pelo Termux (`login`, apt, build de Dockerfile); a v5 traz udocker integrado, `--bind`, `--shared-home` | muitas vezes resolve melhor que a camada daemon, sem API do Docker |
| QEMU `system` (VM completa) | Linux de verdade dentro do Termux, sem root | sem root, é o caminho para Docker **de kernel** (`dockerd`, `compose`, systemd, cgroups); custo de 10-25× (não há KVM para app comum) |
| root (Magisk) + kernel customizado | `pkg install root-repo && pkg install docker tini` | Docker nativo; exige desbloquear bootloader (apaga o aparelho) e kernel com namespaces/cgroups/overlayfs |

## Doki: o concorrente que é mais rápido e mais simples — com três bugs medidos

Testado aqui (v0.12.0, Android/arm64, sem root). O que ele faz **melhor** que este setup:

- `doki run --rm alpine echo` em **0,79 s** (aqui: 2-4 s) e `doki pull alpine` em 5,5 s.
- **`doki-compose` existe** (8 MB) — `docker compose` não existe neste setup.
- `doki-kube`/`doki-kubectl` também são publicados para Android.
- Storage driver `fuse-overlayfs` (camadas de verdade) e daemon que sobe sem root, com três runners
  disponíveis: `native`, `proot` e `legacy32`.
- O defeito do sufixo `:ro` do udocker **não existe** nele no sentido óbvio (ele não erra o caminho).

Os três bugs, com reprodução:

1. **Rede dentro do container não resolve.** O daemon loga `dns server ready ... addr 127.0.0.11:8053`
   (sabe que a 53 está bloqueada e sobe o DNS na 8053), mas entrega ao container
   `nameserver 127.0.0.11` **sem porta** → `apk add`, `curl` e `wget` de dentro do container não
   resolvem nada. `--network host` não mudou o resultado.
2. **`build` recusa o contexto**: `Error: build context outside allowed directory`, com o contexto
   em `$TMPDIR` **e** dentro de `$HOME`.
3. **`:ro` é aceito e ignorado** — monta no lugar certo e **deixa escrever**: o arquivo criado dentro
   do container apareceu no host. Falha **silenciosa**, pior que o erro visível do udocker para quem
   usa `:ro` achando que protegeu o host.

Veredito: excelente candidato a acompanhar e provável substituto quando 1 e 2 forem corrigidos; hoje
não substitui este stack para o caso que mais importa (rede + `apk`/`apt` dentro do container).

## Becos sem saída confirmados por terceiros (não perca tempo)

| Tentativa | Resultado |
|---|---|
| `podman` rootless dentro do proot | `cannot clone: Invalid argument`; mantenedor do Podman: *"proot is not powerful enough to run Podman"* (containers/podman#26186) |
| `runsc`/gVisor | panics no Android (google/gvisor#12544) |
| `pkg install docker` sem root | não existe: o pacote vive em `root-packages/` e exige root + kernel compatível |

## Chromium não rodar em container é uma classe de problema conhecida

- Relatos públicos ligam o crash do Chromium dentro de docker/bwrap/**proot** a SIGTRAP.
- **Antes de culpar o proot, descarte a outra causa.** O `PartitionAlloc` do Chromium aborta com
  SIGTRAP em aarch64 quando o **page size é 64 KiB**. Cheque primeiro:
  `python3 -c "import os; print(os.sysconf('SC_PAGE_SIZE'))"`. Com 4096 a hipótese está descartada e
  sobra o choque de ptrace (o proot intercepta syscalls por ptrace e o crashpad do Chromium também
  depende de ptrace/processos filhos).
- Consequência prática: headless no Android = Chromium **nativo**, nunca o de container.

## O que este setup acrescenta (e que não estava publicado)

1. Dispatcher de duas camadas com fallback automático (daemon completo × motor direto).
2. Contorno dos três defeitos do `udockerd` (plataforma `android/arm64` no pull, `Binds` ignorado,
   `FROM` não puxado), com as issues abertas no upstream.
3. Shim do **proot 5.1** no lugar do 4.8.0 que o udocker baixa (o 4.8.0 não rastreia filhos no
   Android: builtin roda, applet externo morre com SIGSYS).
4. Medição honesta de custo (tempo **e** RAM) das vias headless, incluindo o custo escondido do
   proot: ele cobra **por entrada do diretório montado** (bind do `$HOME` com 728 entradas = 13 s
   contra 4 s sem bind).
5. Ponte nos dois sentidos entre as duas interfaces (`docker` aceita os comandos nativos do udocker;
   `udocker` manda `build`/`exec`/`logs` para o `docker`) — mesmo motor, mesmo `~/.udocker`.
