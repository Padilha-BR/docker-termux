# Utilitários de documento e web para o celular

Comandos para o Termux. Os de **documento** rodam em container, porque as
ferramentas que eles precisam **não existem** (e não têm pacote) no Android. Os de
**web** rodam **nativos**: o Chromium do Termux (bionic, sem proot) funciona, e
dentro do container ele não roda (proot e crashpad brigam por ptrace).

O `docker-termux-setup` instala todos em `~/.hermes/bin/` (ou em
`$DOCKER_TERMUX_BIN`) e eles são chamados como comandos normais.

| comando | o que faz | onde roda | por quê |
|---|---|---|---|
| `pdf` | Markdown → PDF tipografado (capa, A4/letter, tabelas, emoji, numeração) | container `pdf-tool:1` (~400 MB) | no Termux não há weasyprint, pandoc-com-engine, LaTeX nem libreoffice |
| `pdfpy` | roda qualquer helper da skill `pdf` (ler/merge/split/form/watermark) | container `pdf-tool:1` | `pypdf`, `reportlab` e `pdfplumber` não existem no Termux |
| `webget` | baixa página e extrai texto/HTML/links (nível 1, sem navegador) | nativo (`venv-web`); cai no container `web:1` se não houver o venv | é a base barata |
| `webprint` | Chromium headless: `--dom`, `--texto`, `--pdf`, `--png` (nível 2) | nativo (Chromium do Termux) | página que precisa de JS, sem clique |
| `webcdp` | CDP puro: texto, título, HTML, JS, screenshot (nível 3, o mais rápido) | nativo (Chromium + `websockets`) | interação sem Selenium |
| `webplay` | roda **seu** script Selenium (nível 3b, com o helper `webauto.py`) | nativo (Chromium + chromedriver) | API familiar de automação |

O Playwright **não existe para Android** (não há wheel no PyPI); por isso o nível 3
é CDP puro ou Selenium. A antiga imagem `navegador:1` (Playwright em container,
~1,5 GB) foi removida: o Chromium dela trava sob proot e nenhum comando a usava.

## Escolhendo o nível de "headless" (medido neste aparelho)

| nível | ferramenta | quando usar | custo |
|---|---|---|---|
| 1 | `webget` (httpx + parser) | o HTML já vem com o conteúdo: notícia, blog, doc, wiki — **a maioria dos casos** | ~1,5 s, ~30 MB de RAM |
| 2 | `webprint` (Chromium CLI) | a página precisa de JS, mas ninguém precisa clicar; é o único que dá PNG/PDF | 2,8-6 s, ~1 GB |
| 3 | `webcdp` (CDP puro) | rodar JS, ler título/texto renderizado, screenshot | 1,9-2,5 s, ~1 GB |
| 3b | `webplay` (Selenium) | login, formulário, esperar seletor, várias abas | ~4-5 s, ~1 GB |

Regra prática: **comece pelo nível 1**. Se o `webget` sair com código 3
("conteúdo vazio"), a página é JavaScript — suba para o nível 2. Só vá para o
nível 3 se precisar interagir.

O que nenhum nível resolve bem: anti-bot forte (Cloudflare Turnstile) e mídia
(para baixar vídeo/áudio, `yt-dlp` ganha de navegador).

## Exemplos

```sh
# nível 1 — barato
webget https://news.ycombinator.com --links
webget https://docs.python.org/3/library/asyncio.html --seletor "div.body" -o asyncio.md
webget https://site.com --json -o pagina.json   # --max-mb N limita o download (padrão 20)

# nível 2 — precisa de JS
webprint https://site-spa.com --dom -o pagina.html
webprint https://site.com --pdf -o site.pdf
webprint https://site.com --png -o captura.png

# nível 3 — CDP puro (só http/https; perfil temporário a cada execução)
webcdp https://site.com --titulo
webcdp https://site.com --js "document.querySelectorAll('a').length"

# nível 3b — Selenium
cat > robo.py <<'PY'
from webauto import sessao, esperar
with sessao() as d:                     # perfil temporário, apagado no fim
    d.get("https://example.com")
    esperar(d, "#busca").send_keys("termo")
    esperar(d, "button[type=submit]").click()
    print(esperar(d, ".resultado").text)
PY
webplay robo.py

# documento
pdf material.md -o Material\ 3.pdf --titulo "Unit 3" --numerar-paginas
pdfpy pdf_merge.py capa.pdf apostila.pdf -o final.pdf
```

## Notas de operação

- `pdf`/`pdfpy` (e o `webget` sem venv) constroem a imagem na primeira execução
  e avisam; depois é só iniciar container (segundos).
- **O builder do daemon não tem cache de camadas**: mexer no `Dockerfile`
  reconstrói tudo do zero (por isso o gerador `md2pdf` é montado do celular em
  vez de copiado na imagem — editar o script não exige rebuild).
- O `md2pdf` só carrega imagem/CSS de `data:` e de arquivos **dentro da pasta da
  entrada**; `file://` fora dela e http(s) são recusados (o Markdown pode vir de
  fonte não confiável). Para liberar http(s): `pdf aula.md --permitir-rede`.
- Binds: o udocker não tem `:ro`. O motor direto remove o sufixo e **avisa** que
  o bind fica gravável; não conte com somente-leitura.
- Comandos com bind (`-v`) rodam pelo motor direto; sem bind, pelo daemon.
- Não rode build com containers em andamento nem reinicie o daemon durante um
  build (`killpg` leva o build junto com `signal 15`).
