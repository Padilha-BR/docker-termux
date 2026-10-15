# Autoria e créditos

**English:** [read in English](AUTHORS.md).

## Autor deste trabalho

**Gabriel Padilha** — [@Padilha-BR](https://github.com/Padilha-BR)

Responsável pelo trabalho de campo, pela engenharia das correções e por todas as
medições publicadas aqui. Tudo foi executado **dentro do próprio aparelho**, por
terminal (Termux), sem root e sem computador auxiliar.

Se este repositório te economizou tempo, o reconhecimento justo é a citação
(veja `CITATION.cff`) ou o crédito na origem.

## Antes de tudo: o que já existia (créditos)

O conceito **não** é original deste repositório. Estas são as peças de terceiros
em que este trabalho se apoia:

| Projeto | O que é |
|---|---|
| [udocker](https://github.com/indigo-dc/udocker) | o motor de containers sem privilégios; documenta o Termux como ambiente suportado e hoje tem pacote oficial no Termux |
| [George-Seven/Termux-Udocker](https://github.com/George-Seven/Termux-Udocker) | configuração do udocker no Termux e scripts prontos para serviços populares |
| [bjia56/udockerd](https://github.com/bjia56/udockerd) | daemon compatível com a API do Docker, apoiado no udocker (é a camada daemon usada aqui) |
| [termux/proot](https://github.com/termux/proot) e `proot-distro` | execução em espaço de usuário (o motor de tudo) |
| [termux/termux-packages](https://github.com/termux/termux-packages) | o proot 5.1, o Chromium nativo, o `chromedriver` e o `qemu-user` |
| gist *"Run selenium with chrome on termux"* | a via de headless por `chromedriver` + Selenium no Termux |
| [Draken119/cdriv](https://github.com/Draken119/cdriv) | cliente WebDriver em `requests` puro para o Termux |
| [OshekharO/Docker-On-Android](https://github.com/OshekharO/Docker-On-Android) | o caminho do Docker de kernel com root + kernel customizado |

## Revisão de código externa

A revisão estática de [@pablo-afterlife](https://github.com/pablo-afterlife)
([PR #1](https://github.com/Padilha-BR/docker-termux/pull/1), mergeado) achou defeitos
reais nos scripts deste repositório — entre eles um backtick sem escape que fazia o
**shell executar `docker logs` a cada `docker run -d`**, uma busca de container que podia
acertar o container errado, um `stop` que matava por PID reciclado e um wake-lock que
nunca era devolvido (o aparelho parava de dormir). Ele não tinha Android; cada correção
foi revalidada no aparelho depois.

## O que é contribuição deste repositório

1. **Dispatcher de duas camadas** com fallback automático entre daemon e motor
   direto (`scripts/docker`).
2. **Conserto dos três defeitos do `udockerd`**: plataforma `android/arm64` no
   `pull`, `HostConfig.Binds` ignorado e o `FROM` não puxado no `build` — com as
   issues abertas no upstream.
3. **Conserto dos defeitos do proot no Android**, incluindo o shim que substitui
   o proot 4.8.0 (que não rastreia processos filhos: builtin roda, applet externo
   morre com SIGSYS) pelo proot 5.1 do Termux com `--link2symlink`.
4. **Veredito medido do headless**: nenhum Chromium roda sob `proot` aqui, e a
   cura é o Chromium **nativo**; nível 1/2/3 escolhido por custo, com tempo **e**
   RAM medidos.
5. **Relato de armadilhas** que custam horas e não estão documentadas em lugar
   nenhum: `-v ...:ro` falhando em silêncio, o wrapper que morre deixando o
   Chromium órfão, containers mortos à força acumulando 10,6 GB, `pkill -f
   udockerd` matando a própria shell.
6. **Transporte em socket Unix para o daemon**: a API do Docker não autentica ninguém, e no
   Android o loopback é alcançável por qualquer app com permissão de rede — então o daemon
   saiu do TCP e foi para trás de um socket `0600`.
7. **Hashes pinados dos artefatos**: o instalador aborta num download que não bate com o
   [`checksums.txt`](checksums.txt), já que nenhum upstream publica `.sha256`.

Detalhamento em [`CAPACIDADES.md`](CAPACIDADES.pt-BR.md).
