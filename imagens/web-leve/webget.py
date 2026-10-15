#!/usr/bin/env python3
"""webget — baixa uma pagina e extrai o conteudo util. Roda DENTRO do container.

Nivel 1 (sem navegador): rapido e barato (~1,5 s). Se o conteudo vier por
JavaScript, o texto sai vazio e o exit e 3 — nesse caso suba para `webprint`
(Chromium nativo) ou `webcdp` (CDP puro, o mais rapido dos dois).

Uso:
    webget URL [--texto|--html|--links|--json] [-o ARQUIVO] [--seletor CSS]
                [--timeout S] [--user-agent UA]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(prog="webget")
    ap.add_argument("url")
    ap.add_argument("--texto", action="store_true", help="texto limpo (padrao)")
    ap.add_argument("--html", action="store_true", help="HTML bruto")
    ap.add_argument("--links", action="store_true", help="lista de links")
    ap.add_argument("--json", action="store_true", help="saida estruturada")
    ap.add_argument("--seletor", help="recorta por seletor CSS (ex: 'article')")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--user-agent",
                    default="Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/120 Safari/537.36")
    ap.add_argument("-o", "--saida")
    args = ap.parse_args()

    import httpx
    from bs4 import BeautifulSoup

    try:
        r = httpx.get(args.url, timeout=args.timeout, follow_redirects=True,
                      headers={"User-Agent": args.user_agent,
                               "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"})
    except Exception as e:
        print(f"webget: falha na requisicao: {e}", file=sys.stderr)
        return 1

    if r.status_code >= 400:
        print(f"webget: HTTP {r.status_code} em {args.url}", file=sys.stderr)
        return 1

    texto = r.text
    soup = BeautifulSoup(texto, "lxml")

    def limpa(s: str) -> str:
        return "\n".join(l.strip() for l in s.splitlines() if l.strip())

    if args.seletor:
        alvo = soup.select(args.seletor)
        if not alvo:
            print(f"webget: seletor '{args.seletor}' nao encontrou nada",
                  file=sys.stderr)
            return 1
        soup = BeautifulSoup("".join(str(x) for x in alvo), "lxml")

    if args.links:
        vistos, saida = set(), []
        for a in soup.find_all("a", href=True):
            u = a["href"]
            if u.startswith(("http://", "https://")) and u not in vistos:
                vistos.add(u)
                saida.append(f"{a.get_text(' ', strip=True)[:70]}\t{u}")
        conteudo = "\n".join(saida)
    elif args.html:
        conteudo = str(soup)
    else:
        for tag in soup(["script", "style", "noscript", "template", "svg"]):
            tag.decompose()
        try:
            import html2text
            h = html2text.HTML2Text()
            h.ignore_images = True
            h.body_width = 0
            conteudo = limpa(h.handle(str(soup)))
        except ImportError:
            conteudo = limpa(soup.get_text("\n"))

    if args.json:
        titulo = (soup.title.get_text(strip=True) if soup.title else "")
        print(json.dumps({
            "url": str(r.url), "status": r.status_code, "titulo": titulo,
            "bytes_html": len(texto), "chars_conteudo": len(conteudo),
            "vazio": not conteudo.strip(), "conteudo": conteudo,
        }, ensure_ascii=False))
    elif args.saida:
        Path(args.saida).write_text(conteudo, encoding="utf-8")
        print(f"{args.saida} ({len(conteudo)} chars)")
    else:
        sys.stdout.write(conteudo + ("\n" if conteudo else ""))

    # O exit 3 avisa "esta pagina so existe com JavaScript — suba de nivel". Ele
    # so vale para os modos que leem CONTEUDO: uma pagina legitimamente sem links
    # nao e isso, e mandar o chamador abrir um Chromium de ~1 GB por causa disso
    # seria falso positivo.
    if not conteudo.strip():
        if args.links:
            print("webget: nenhum link externo nesta pagina", file=sys.stderr)
            return 0
        print("webget: conteudo vazio — a pagina provavelmente renderiza via "
              "JavaScript; use `webprint` (Chromium nativo) ou `webcdp` (CDP).",
              file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
