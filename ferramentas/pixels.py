"""As partes como grades de classes: ler um SVG de faixas de pixel (o formato do extrair.py) numa
grade de 150 × 150 por grupo, e escrever de volta no mesmo formato.

Cada grupo é ``(camada, extra, grade)``: ``extra`` são os atributos além de ``data-camada`` e
``data-pronto`` (``data-cobre="cabelo"``, por exemplo), e a grade guarda o nome da classe de cada
pixel ("" é vazio).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

GRADE = 150
GRUPO = re.compile(r'<g data-camada="([^"]+)" data-pronto="sim"([^>]*)>(.*?)</g>', re.S)
PATH = re.compile(r'<path class="([^"]+)" d="([^"]+)"/>')
FAIXA = re.compile(r"M(\d+) (\d+)h(\d+)v1h-\d+z")


def vazia() -> np.ndarray:
    return np.full((GRADE, GRADE), "", dtype=object)


def ler(caminho: Path) -> list[tuple[str, str, np.ndarray]]:
    grupos = []
    for camada, extra, corpo in GRUPO.findall(Path(caminho).read_text()):
        g = vazia()
        for cls, d in PATH.findall(corpo):
            for x, y, n in FAIXA.findall(d):
                g[int(y), int(x):int(x) + int(n)] = cls
        grupos.append((camada, extra, g))
    return grupos


def faixas(pixels: list[tuple[int, int]]) -> str:
    """Os pixels como faixas horizontais: "M x y h n v 1 h -n z"."""
    linhas: dict[int, list[int]] = {}
    for y, x in pixels:
        linhas.setdefault(y, []).append(x)
    partes = []
    for y in sorted(linhas):
        xs = sorted(linhas[y])
        ini = ant = xs[0]
        for x in [*xs[1:], None]:
            if x is not None and x == ant + 1:
                ant = x
                continue
            n = ant - ini + 1
            partes.append(f"M{ini} {y}h{n}v1h-{n}z")
            if x is not None:
                ini = ant = x
    return "".join(partes)


def grupo(camada: str, g: np.ndarray, extra: str = "", pecas: str = "") -> str:
    classes: dict[str, list[tuple[int, int]]] = {}
    for y, x in zip(*np.nonzero(g != "")):
        classes.setdefault(g[y, x], []).append((int(y), int(x)))
    corpo = "".join(f'<path class="{c}" d="{faixas(p)}"/>' for c, p in sorted(classes.items()) if p)
    return f'<g data-camada="{camada}" data-pronto="sim"{extra}>{corpo}{pecas}</g>'


def svg(*grupos: str) -> str:
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 150 150">\n  '
            + "\n  ".join(g for g in grupos if g) + "\n</svg>\n")


def escrever(caminho: Path, grupos: list[tuple[str, str, np.ndarray]]) -> None:
    Path(caminho).write_text(svg(*(grupo(c, g, extra) for c, extra, g in grupos if (g != "").any())))
