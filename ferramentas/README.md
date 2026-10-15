# Utilitários que só existem no celular via Docker

Estes comandos rodam no Termux usando containers, porque as ferramentas que eles
precisam **não existem** (e não têm pacote) no Android. Todos entram em
`~/.hermes/bin/` e são chamados como comandos normais.

| comando | o que faz | imagem | por que precisa do Docker |
|---|---|---|---|
| `pdf` | Markdown → PDF tipografado (capa, A4/letter, tabelas, emoji, numeração) | `pdf-tool:1` (~400 MB) | no Termux não há weasyprint, pandoc-com-engine, LaTeX nem libreoffice |
| `pdfpy` | roda qualquer helper da skill `pdf` (ler/merge/split/form/watermark) | `pdf-tool:1` | `pypdf`, `reportlab` e `pdfplumber` não existem no Termux |
| `webget` | baixa página e extrai texto/HTML/links (nível 1, sem navegador) | `web:1` (~200 MB) | — roda igual em qualquer lugar, mas é a base barata |
| `webprint` | Chromium headless: `--dom`, `--pdf`, `--png` (nível 2) | `navegador:1` (~2 GB) | não há Chromium automatizável no Termux |
| `webplay` | roda **seu** script Playwright (nível 3, com interação) | `navegador:1` | idem |

## Escolhendo o nível de "headless" (medido neste aparelho)

| nível | ferramenta | quando usar | custo |
|---|---|---|---|
| 1 | `webget` (httpx + parser) | o HTML já vem com o conteúdo: notícia, blog, doc, wiki — **a maioria dos casos** | ~1 s, ~30 MB de RAM |
| 2 | `webprint` (Chromium CLI) | a página precisa de JS, mas ninguém precisa clicar | ~8-15 s, ~400 MB |
| 3 | `webplay` (Playwright) | login, formulário, esperar seletor, várias abas, interceptar rede | ~15-40 s, ~500 MB |

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

# nível 2 — precisa de JS
webprint https://site-spa.com --dom -o pagina.html
webprint https://site.com --pdf -o site.pdf
webprint https://site.com --png -o captura.png

# nível 3 — interação
cat > robo.py <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
    pg = b.new_page()
    pg.goto("https://example.com")
    pg.fill("#busca", "termo")          # interage de verdade
    pg.click("button[type=submit]")
    pg.wait_for_selector(".resultado")
    print(pg.inner_text(".resultado"))
    b.close()
PY
webplay robo.py

# documento
pdf material.md -o Material\ 3.pdf --titulo "Unit 3" --numerar-paginas
pdfpy pdf_merge.py capa.pdf apostila.pdf -o final.pdf
```

## Notas de operação

- Cada comando constrói a imagem na primeira execução e avisa; depois é só
  iniciar container (segundos).
- **O builder do daemon não tem cache de camadas**: mexer no `Dockerfile`
  reconstrói tudo do zero (por isso o gerador `md2pdf` é montado do celular em
  vez de copiado na imagem — editar o script não exige rebuild).
- Comandos com bind (`-v`) rodam pelo motor direto; sem bind, pelo daemon.
- Não rode build com containers em andamento nem reinicie o daemon durante um
  build (`killpg` leva o build junto com `signal 15`).
