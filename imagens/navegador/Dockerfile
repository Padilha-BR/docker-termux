FROM ubuntu:24.04

# Playwright + Chromium headless. No Termux isso nao existe (nem Chromium para
# Android com automacao, nem as libs glibc que ele exige). Dentro do container
# funciona, com duas adaptacoes obrigatorias:
#   --no-sandbox            -> proot nao tem user namespace; sem isso o Chromium
#                              morre na inicializacao;
#   --disable-dev-shm-usage -> /dev/shm e minusculo no Android.
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip ca-certificates curl wget gnupg \
        fonts-dejavu-core fonts-liberation fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --break-system-packages --no-cache-dir playwright

# baixa o Chromium e TODAS as dependencias de sistema dele (usa apt por baixo)
RUN python3 -m playwright install --with-deps chromium

WORKDIR /dados
ENTRYPOINT ["python3"]
CMD ["-c", "import playwright; print('playwright pronto')"]
