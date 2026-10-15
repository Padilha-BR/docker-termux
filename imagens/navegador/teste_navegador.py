"""Teste de navegador real dentro do container (usa o diretorio montado em /dados).

Abre uma pagina, imprime titulo e texto, tira screenshot e salva o HTML.
Flags obrigatorias no Android: --no-sandbox e --disable-dev-shm-usage.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
SAIDA = Path("/dados")

ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--no-zygote",
]

with sync_playwright() as p:
    print("chromium:", p.chromium.executable_path)
    navegador = p.chromium.launch(args=ARGS)
    pagina = navegador.new_page(viewport={"width": 900, "height": 1200})
    pagina.goto(URL, timeout=45000, wait_until="domcontentloaded")
    print("titulo:", pagina.title())
    texto = pagina.inner_text("body")
    print("texto (200 chars):", " ".join(texto.split())[:200])
    pagina.screenshot(path=str(SAIDA / "screenshot.png"), full_page=True)
    (SAIDA / "pagina.html").write_text(pagina.content(), encoding="utf-8")
    print("screenshot:", (SAIDA / "screenshot.png").stat().st_size, "bytes")
    navegador.close()
print("OK")
