FROM python:3.12-alpine

# Nivel 1 de "headless": SEM navegador. So HTTP + parser.
# Resolve a maioria dos casos (noticia, blog, doc, wiki) em ~1 s com ~30 MB de
# RAM, contra ~2 GB de imagem e ~400 MB de RAM de um Chromium. Use isto primeiro;
# so parta para o navegador (webprint/webcdp) se o conteudo vier por JavaScript.
# Versoes pinadas (PyPI, 16/10/2026; lxml tem wheel musllinux aarch64).
RUN apk add --no-cache ca-certificates && \
    python3 -m pip install --no-cache-dir \
        httpx==0.28.1 beautifulsoup4==4.15.0 lxml==6.1.3 html2text==2025.4.15

WORKDIR /dados
ENTRYPOINT ["python3"]
CMD ["-c", "print('webget pronto')"]
