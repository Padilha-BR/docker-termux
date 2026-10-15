FROM ubuntu:24.04

# Gerador de PDF a partir de Markdown. Nao existe nada equivalente no Termux:
# weasyprint (engine de render), pandoc com engine e LaTeX estao ausentes, e
# texlive nem tem pacote. Aqui instala em ~1 minuto: nada compila, weasyprint
# e markdown sao Python puro e as libs de texto vem prontas.
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi8 \
        shared-mime-info \
        fonts-dejavu-core fonts-liberation fonts-noto-color-emoji \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --break-system-packages --no-cache-dir \
        weasyprint markdown pymdown-extensions \
        pypdf reportlab pdfplumber pypdfium2

COPY md2pdf /usr/local/bin/md2pdf
RUN chmod +x /usr/local/bin/md2pdf

WORKDIR /dados
ENTRYPOINT ["md2pdf"]
CMD ["--help"]
