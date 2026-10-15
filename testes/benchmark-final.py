#!/usr/bin/env python3
"""Mede tempo e PICO DE RAM dos tres niveis de fetch no celular.

Nivel 1: webget (container, proot)   -> mede tambem o custo de subir o container
Nivel 2: webprint (chromium nativo)
Nivel 3: selenium + chromedriver (nativo)

RAM = soma de VmRSS dos processos do chromium (amostrada a cada 0,3 s enquanto
o comando roda). Nao e estimativa.
"""
from __future__ import annotations

import os
import subprocess
import time

CASA = os.path.expanduser("~")
ALVOS = [("estatica", "https://example.com"),
         ("SPA (JS)", "https://react.dev")]
PY_WEB = f"{CASA}/docker-termux/venv-web/bin/python"
PY_HERMES = f"{CASA}/hermes-agent/venv/bin/python"


def rss_chromium() -> int:
    total = 0
    for p in os.listdir("/proc"):
        if not p.isdigit():
            continue
        try:
            exe = os.readlink(f"/proc/{p}/exe")
        except OSError:
            continue
        if "chromium" in exe or exe.endswith("/chrome") or "headless" in exe:
            try:
                with open(f"/proc/{p}/status") as fh:
                    for linha in fh:
                        if linha.startswith("VmRSS"):
                            total += int(linha.split()[1])
                            break
            except OSError:
                pass
    return total


def medir(rotulo: str, cmd: list[str]) -> None:
    ini = time.time()
    pico = 0
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, cwd=CASA)
    while proc.poll() is None:
        pico = max(pico, rss_chromium())
        time.sleep(0.3)
    saida = proc.stdout.read() if proc.stdout else b""
    dur = time.time() - ini
    print(f"  {rotulo:<42} {dur:6.1f}s  RAM pico ~{pico // 1024:4d} MB  "
          f"exit={proc.returncode}")
    amostra = " ".join(saida.decode("utf-8", "replace").split())[:70]
    print(f"      saida ({len(saida)} bytes): {amostra}")


SCRIPT_SEL = f"{CASA}/testes-pdf/teste-selenium.py"

for nome, url in ALVOS:
    print(f"\n### {nome}: {url}")
    medir("nivel 1: webget (container/proot)",
          [f"{CASA}/.hermes/bin/webget", url, "--texto"])
    medir("nivel 2: webprint (chromium nativo)",
          [f"{CASA}/.hermes/bin/webprint", url, "--texto"])
    if nome == "estatica":
        medir("nivel 3: selenium+chromedriver (nativo)",
              [PY_WEB, SCRIPT_SEL])
