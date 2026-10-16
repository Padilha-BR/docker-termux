#!/usr/bin/env python3
"""webcdp — nível 3 de headless SEM Selenium e SEM chromedriver (CDP puro).

Fala direto com o depurador embutido do Chromium (Chrome DevTools Protocol) por
WebSocket. Medido neste aparelho: **1,9 s** numa página estática, contra 4,3 s da
via Selenium — porque não há subprocesso chromedriver esperando por um socket.

Uso:
    webcdp https://site.com --texto          # texto renderizado (JS já rodou)
    webcdp https://site.com --titulo
    webcdp https://site.com --html -o p.html
    webcdp https://site.com --screenshot p.png
    webcdp https://site.com --js "document.querySelectorAll('a').length"

Códigos de saída (mesma convenção do webget):
    0  conteúdo obtido
    2  erro de uso / ambiente / navegador que não respondeu
    3  página carregou mas o conteúdo veio vazio (provável JS que não rodou)

Só aceita URL http(s): `file:///.../.ssh/id_rsa --texto` imprimia o arquivo, e
num agente isso vira leitura local disparada por prompt injection. Cada execução
usa um perfil TEMPORÁRIO (apagado no fim): cookies não vazam entre URLs e duas
execuções em paralelo não disputam o mesmo perfil.

Pegadinha que custa tempo (documentada na skill): o `webSocketDebuggerUrl` de
`/json/version` é o endpoint do BROWSER — comandos `Page.*` nele travam sem
responder. É obrigatório conectar no alvo de uma PÁGINA (`/json/list`, type=page).
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

try:
    import websockets
    from websockets.exceptions import WebSocketException
except ImportError:  # pragma: no cover
    print("erro: falta o pacote websockets (pip install websockets)", file=sys.stderr)
    raise SystemExit(2)

CHROME = os.environ.get("CHROMIUM_BIN", "chromium-browser")
# Porta FIXA so quando quem chamou pedir (CDP_PORTA); sem isso, 0. Com 9222
# fixo uma segunda execucao (ou outro chromium ja vivo) ficava com a porta
# ocupada e o /json/list devolvia o browser DE OUTREM — e o webcdp navegava e
# executava JS la, sem perceber.
PORTA = int(os.environ["CDP_PORTA"]) if os.environ.get("CDP_PORTA") else None
TMPDIR = os.environ.get("TMPDIR", "/data/data/com.termux/files/usr/tmp")
# WEBCDP_ESPERA e o nome certo; WEBGDP_ESPERA e o typo antigo, mantido por compat
ESPERA_CARGA = float(os.environ.get("WEBCDP_ESPERA",
                                     os.environ.get("WEBGDP_ESPERA", "45")))


def esperar_alvo(porta: int, timeout: float = 30) -> dict:
    fim = time.time() + timeout
    while time.time() < fim:
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{porta}/json/version", timeout=3) as r:
                info = json.loads(r.read())
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{porta}/json/list", timeout=3) as r:
                alvos = json.loads(r.read())
            paginas = [t for t in alvos if t.get("type") == "page"]
            if paginas:
                info["pagina_ws"] = paginas[0]["webSocketDebuggerUrl"]
                return info
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)
    raise TimeoutError("o devtools do chromium nao respondeu (ou sem alvo de pagina)")


def porta_do_nosso_browser(perfil: str, timeout: float = 30) -> int:
    """Porta do Chromium que NOS lancamos, lida do proprio perfil.

    Com --remote-debugging-port=0 o Chromium escolhe a porta e grava a
    primeira linha em <user-data-dir>/DevToolsActivePort. E a unica forma de
    nao acabar dirigindo um browser que ja estava na 9222.
    """
    arq = os.path.join(perfil, "DevToolsActivePort")
    fim = time.time() + timeout
    while time.time() < fim:
        try:
            with open(arq) as f:
                porta = int(f.readline().strip())
            if porta:
                return porta
        except (OSError, ValueError):
            pass
        time.sleep(0.5)
    raise TimeoutError(f"chromium nao gravou a porta em {arq}")


async def coletar(ws_url: str, url: str, exprs: list[tuple[str, str]]) -> dict:
    resultado: dict = {}
    async with websockets.connect(ws_url, max_size=64 * 1024 * 1024) as ws:
        contador = 0

        async def cmd(metodo: str, params: dict | None = None) -> int:
            nonlocal contador
            contador += 1
            await ws.send(json.dumps({"id": contador, "method": metodo,
                                      "params": params or {}}))
            return contador

        async def esperar_id(ident: int, timeout: float = 60) -> dict:
            while True:
                resposta = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
                if resposta.get("id") == ident:
                    return resposta

        await cmd("Page.enable")
        await cmd("Runtime.enable")
        nav = await cmd("Page.navigate", {"url": url})

        fim = time.time() + ESPERA_CARGA
        while time.time() < fim:
            try:
                evento = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            except asyncio.TimeoutError:
                continue
            metodo = evento.get("method")
            if metodo == "Page.loadEventFired":
                break
            if metodo == "Page.frameStoppedLoading":
                break
            if evento.get("id") == nav and "errorText" in evento.get("result", {}):
                resultado["erro_navegacao"] = evento["result"]["errorText"]
                break

        for chave, expr in exprs:
            ident = await cmd("Runtime.evaluate",
                              {"expression": expr, "returnByValue": True})
            resposta = await esperar_id(ident)
            resultado[chave] = (resposta.get("result", {})
                                .get("result", {}).get("value"))
    return resultado


def main() -> int:
    p = argparse.ArgumentParser(prog="webcdp", add_help=True,
                                description="headless via CDP puro (sem Selenium)")
    p.add_argument("url")
    p.add_argument("--texto", action="store_true", help="texto visivel (JS ja rodou)")
    p.add_argument("--html", action="store_true", help="DOM serializado")
    p.add_argument("--titulo", action="store_true", help="somente o titulo")
    p.add_argument("--js", metavar="EXPR", help="avalia uma expressao JS e imprime")
    p.add_argument("--screenshot", metavar="ARQ", help="salva PNG no caminho dado")
    p.add_argument("-o", "--saida", help="grava a saida principal neste arquivo")
    args = p.parse_args()

    if not any([args.texto, args.html, args.titulo, args.js, args.screenshot]):
        args.texto = True
    if urllib.parse.urlsplit(args.url).scheme.lower() not in ("http", "https"):
        print(f"erro: so URL http(s) e aceita: {args.url!r}", file=sys.stderr)
        return 2

    exprs: list[tuple[str, str]] = []
    if args.titulo:
        exprs.append(("titulo", "document.title"))
    if args.html:
        exprs.append(("html", "document.documentElement.outerHTML"))
    if args.texto:
        exprs.append(("texto", "document.body ? document.body.innerText : ''"))
    if args.js:
        exprs.append(("js", args.js))

    if shutil.which(CHROME) is None:
        print(f"erro: chromium nao encontrado: {CHROME} "
              "(pkg install x11-repo && pkg install chromium)", file=sys.stderr)
        return 2

    # perfil novo a cada execucao: sem DevToolsActivePort velho de outra rodada
    # (que apontaria para OUTRO browser) e sem cookie de uma URL na seguinte
    os.makedirs(TMPDIR, exist_ok=True)
    perfil = tempfile.mkdtemp(prefix="webcdp-perfil-", dir=TMPDIR)
    porta = PORTA if PORTA is not None else 0
    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--no-sandbox", "--disable-gpu",
         "--disable-dev-shm-usage", f"--remote-debugging-port={porta}",
         f"--user-data-dir={perfil}", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        info = esperar_alvo(PORTA if PORTA is not None
                            else porta_do_nosso_browser(perfil))
        dados = asyncio.run(coletar(info["pagina_ws"], args.url, exprs))

        if args.screenshot:
            # segunda rodada só para o print (o alvo já está na página)
            async def tirar_print() -> bytes | None:
                async with websockets.connect(info["pagina_ws"],
                                              max_size=64 * 1024 * 1024) as ws:
                    await ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
                    await ws.send(json.dumps({"id": 2,
                                              "method": "Page.captureScreenshot",
                                              "params": {"format": "png"}}))
                    while True:
                        r = json.loads(await asyncio.wait_for(ws.recv(), timeout=45))
                        if r.get("id") == 2:
                            d = r.get("result", {}).get("data")
                            return base64.b64decode(d) if d else None
            dados["screenshot"] = None
            conteudo = asyncio.run(tirar_print())
            if conteudo:
                with open(args.screenshot, "wb") as fh:
                    fh.write(conteudo)
                dados["screenshot"] = args.screenshot
        return _imprimir(dados, args)
    except (TimeoutError, asyncio.TimeoutError, OSError,
            WebSocketException) as e:
        # navegador que nao subiu/nao respondeu e erro de ambiente (exit 2),
        # nao traceback
        print(f"erro: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(perfil, ignore_errors=True)


def _imprimir(dados: dict, args) -> int:
    if "titulo" in dados:
        print(dados["titulo"] or "")
    principal = dados.get("texto") or dados.get("html") or dados.get("js")
    if args.saida and principal is not None:
        with open(args.saida, "w", encoding="utf-8") as fh:
            fh.write(str(principal))
        print(f"{args.saida} ({os.path.getsize(args.saida)} bytes)")
    elif principal is not None:
        print(principal)
    if dados.get("screenshot"):
        print(f"{dados['screenshot']} "
              f"({os.path.getsize(dados['screenshot'])} bytes)")
    if dados.get("erro_navegacao"):
        print(f"aviso: {dados['erro_navegacao']}", file=sys.stderr)
    texto = (dados.get("texto") or "").strip()
    if args.texto and len(texto) < 20:
        return 3          # mesmo sinal do webget: conteudo vazio
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
