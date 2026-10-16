FROM ubuntu:24.04

# Gerador de PDF a partir de Markdown. Nao existe nada equivalente no Termux:
# weasyprint (engine de render), pandoc com engine e LaTeX estao ausentes, e
# texlive nem tem pacote. Aqui instala em ~1 minuto: nada compila, weasyprint
# e markdown sao Python puro e as libs de texto vem prontas.
# ARG (nao ENV): vale so durante o build. Com ENV o valor ficava gravado na
# imagem e vazava para todo processo que rodasse nela depois.
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi8 \
        shared-mime-info \
        fonts-dejavu-core fonts-liberation fonts-noto-color-emoji \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Versoes pinadas (conferidas no PyPI em 16/10/2026; todas resolvem com wheel
# manylinux aarch64 para o Python 3.12 do ubuntu:24.04). Sem pin, cada build
# pegava a ultima versao e o md2pdf podia quebrar entre dois builds iguais.
RUN python3 -m pip install --break-system-packages --no-cache-dir \
        weasyprint==70.0 markdown==3.11.1 pymdown-extensions==12.3 \
        pypdf==6.20.1 reportlab==5.0.1 pdfplumber==0.11.10 pypdfium2==5.14.0

COPY md2pdf /usr/local/bin/md2pdf
RUN chmod +x /usr/local/bin/md2pdf

WORKDIR /dados
ENTRYPOINT ["md2pdf"]
CMD ["--help"]
