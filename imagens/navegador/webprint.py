#!/usr/bin/env python3
"""webprint — usa o Chromium SEM biblioteca de automacao (NIVEL 2).

Tres modos, todos pela linha de comando do proprio navegador:
    --dom     HTML final depois do JavaScript (o "curl" que funciona em SPA)
    --pdf     imprime a pagina em PDF
    --png     screenshot da pagina inteira

Diferente do Playwright: nao ha driver, nao ha script de interacao — so o
Chromium headless fazendo o trabalho. Use quando a pagina precisa de JS mas
ninguem precisa clicar em nada.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ARGS_BASE = [
    "--headless=new",
    "--no-sandbox",              # proot nao tem user namespace
    "--disable-dev-shm-usage",   # /dev/shm pequeno no Android
    "--disable-gpu",
    "--hide-scrollbars",
    "--no-first-run",
    "--no-default-browser-check",
]


def caminho_chromium() -> str:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        return p.chromium.executable_path


def main() -> int:
    ap = argparse.ArgumentParser(prog="webprint")
    ap.add_argument("url")
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument("--dom", action="store_true", help="HTML apos o JS")
    modo.add_argument("--pdf", action="store_true", help="imprime em PDF")
    modo.add_argument("--png", action="store_true", help="screenshot inteiro")
    ap.add_argument("-o", "--saida")
    ap.add_argument("--espera", type=float, default=2.0,
                    help="segundos de espera extra para o JS rodar")
    ap.add_argument("--largura", type=int, default=1280)
    ap.add_argument("--altura", type=int, default=1600)
    args = ap.parse_args()

    chrome = caminho_chromium()
    pasta = Path("/dados")
    if not pasta.is_dir():
        print("webprint: /dados nao esta montado", file=sys.stderr)
        return 2

    if args.dom:
        destino = Path(args.saida) if args.saida else pasta / "pagina.html"
        cmd = [chrome, *ARGS_BASE, "--virtual-time-budget=8000",
               "--dump-dom", args.url]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 and not r.stdout:
            print(f"webprint: chromium falhou ({r.returncode}): "
                  f"{r.stderr[-400:]}", file=sys.stderr)
            return 1
        destino.write_text(r.stdout, encoding="utf-8")
        print(f"{destino} ({len(r.stdout)} chars)")
        return 0

    if args.pdf:
        destino = Path(args.saida) if args.saida else pasta / "pagina.pdf"
        cmd = [chrome, *ARGS_BASE, "--virtual-time-budget=8000",
               "--print-to-pdf-no-header", f"--print-to-pdf={destino}", args.url]
        r = subprocess.run(cmd, capture_output=True, text=True)
    else:  # --png (padrao)
        destino = Path(args.saida) if args.saida else pasta / "pagina.png"
        cmd = [chrome, *ARGS_BASE, f"--window-size={args.largura},{args.altura}",
               "--virtual-time-budget=8000", f"--screenshot={destino}", args.url]
        r = subprocess.run(cmd, capture_output=True, text=True)

    if not destino.exists() or destino.stat().st_size == 0:
        print(f"webprint: nada foi gerado. stderr do chromium:\n{r.stderr[-500:]}",
              file=sys.stderr)
        return 1
    print(f"{destino} ({destino.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
