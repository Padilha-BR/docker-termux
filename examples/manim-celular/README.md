# Exemplo: Manim renderizando dentro de um container, no celular

Manim precisa de cairo + pango + ffmpeg e compila pycairo/pangocairo — inviável
no Termux puro. Dentro do container (ubuntu:24.04 arm64, execução nativa por
proot, sem qemu) instala e renderiza normalmente.

```sh
cd examples/manim-celular
docker build -t manim-celular:1 .
docker run --rm -v "$PWD:/app" manim-celular:1 \
    manim -qm --media_dir /app/media cena.py DockerNoCelular
ls media/videos/cena/720p30/
```

Detalhes que custam tempo:
- use `python3 -m pip` no Dockerfile (o comando `pip` não existe no Ubuntu 24.04);
- `-v` só funciona pelo motor direto (o daemon descarta binds), e o comando
  `docker` já detecta e roteia sozinho;
- renderize com `--media_dir` apontando para o volume, senão o MP4 fica dentro
  do container.
