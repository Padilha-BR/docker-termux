"""Cena Manim que eu nao conseguia renderizar direto no Termux.

Exige cairo + pango + ffmpeg (e o Manim), que nao tem build viavel no Android.
Aqui roda dentro do container, usando a CPU do proprio celular.
"""
from manim import *


class DockerNoCelular(Scene):
    def construct(self):
        titulo = Text("Docker no celular", font_size=54, color=BLUE)
        sub = Text("Manim renderizando dentro de um container", font_size=26)
        sub.next_to(titulo, DOWN, buff=0.4)

        self.play(Write(titulo))
        self.play(FadeIn(sub, shift=UP))

        circulo = Circle(radius=1.0, color=YELLOW)
        quadrado = Square(side_length=1.7, color=GREEN)
        self.play(Create(circulo), run_time=1)
        self.play(Transform(circulo, quadrado), run_time=1)

        medido = Text("arm64 nativo, sem qemu", font_size=24, color=GRAY)
        medido.next_to(sub, DOWN, buff=0.5)
        self.play(FadeIn(medido))
        self.wait(1)
