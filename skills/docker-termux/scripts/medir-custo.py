#!/usr/bin/env python3
"""Mede tempo e PICO DE RAM de um comando no aparelho (Android/Termux).

Uso:
    python3 medir-custo.py "<rotulo>" <comando> [args...]

Por que existe: as escolhas desta skill (nivel 1 vs 2 vs 3 do headless) sao feitas por custo
MEDIDO, nao por palpite — o Chromium nativo custa ~1 GB de RAM, o que surpreende quem so olha
tempo. A RAM e amostrada de /proc (VmRSS) enquanto o comando roda; nao e estimativa.

ARMADILHAS que ja custaram tempo aqui:
  * Amostrar o PID ERRADO. O alvo e o PID do PROPRIO comando (subprocess.Popen). Observar o
    shell que chamou o comando faz o laco nunca terminar e o pico sair 0.
  * Dois Chromium ao mesmo tempo. Rode um por vez: dois headless simultaneos no aparelho
    travam a espera por elemento (esperado, porque e ~1 GB cada).
  * Comparar nivel 1 (34 MB) com nivel 2 (~1 GB) so pelo tempo esconde o recurso escasso.
"""
import os
import subprocess
import sys
import time

EXE_ALVO = ("chrome", "chromium", "headless", "proot", "node", "python")


def rss_mb(filtro=EXE_ALVO):
    """Soma VmRSS (MB) dos processos cujo executavel casa com o filtro."""
    total = 0
    for p in os.listdir("/proc"):
        if not p.isdigit():
            continue
        try:
            exe = os.readlink(f"/proc/{p}/exe")
        except OSError:
            continue
        if any(x in exe for x in filtro):
            try:
                with open(f"/proc/{p}/status") as fh:
                    for linha in fh:
                        if linha.startswith("VmRSS"):
                            total += int(linha.split()[1])
                            break
            except OSError:
                pass
    return total // 1024


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    rotulo, cmd = sys.argv[1], sys.argv[2:]
    ini = time.time()
    pico = 0
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)
    while proc.poll() is None:
        pico = max(pico, rss_mb())
        time.sleep(0.3)
    saida = proc.stdout.read() if proc.stdout else b""
    print(f"{rotulo}: {time.time() - ini:.1f}s  RAM pico ~{pico} MB  exit={proc.returncode}")
    print("saida:", " ".join(saida.decode("utf-8", "replace").split())[:160])
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
