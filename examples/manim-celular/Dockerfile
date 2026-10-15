FROM ubuntu:24.04

# Isto e o que NAO da para instalar no Termux puro: cairo, pango, ffmpeg e o
# proprio Manim (que puxa pycairo/pangocairo compilados). Dentro de um container
# com root de mentira (proot -0) isso instala normalmente.
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-dev build-essential pkg-config \
        libcairo2-dev libpango1.0-dev ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# python3 -m pip em vez de `pip`: no Ubuntu 24.04 o comando `pip` nao existe
# (PEP 668 + binario chamado pip3), e isso quebra o build de forma silenciosa.
RUN python3 -m pip install --break-system-packages --no-cache-dir manim

WORKDIR /app
CMD ["manim", "--version"]
