FROM python:3.12-alpine

# Nivel 1 de "headless": SEM navegador. So HTTP + parser.
# Resolve a maioria dos casos (noticia, blog, doc, wiki) em ~1 s com ~30 MB de
# RAM, contra ~2 GB de imagem e ~400 MB de RAM de um Chromium. Use isto primeiro;
# so parta para o navegador se o conteudo vier por JavaScript.
RUN apk add --no-cache ca-certificates && \
    python3 -m pip install --no-cache-dir \
        httpx beautifulsoup4 lxml html2text

WORKDIR /dados
ENTRYPOINT ["python3"]
CMD ["-c", "print('webget pronto')"]
