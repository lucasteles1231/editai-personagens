"""As bocas e os óculos, desenhados em código (20/10/2026).

Reduzidos à grade de 150, os da IA viravam ruído: uma boca tem uns 14 px de largura, e a da IA
chegava com sombras soltas e dentes em degrau; a armação dos óculos ficava furada onde caía em cima
do contorno do olho (a parte é o que mudou, e ali não mudou nada). Desenhados aqui, eles saem
simétricos, limpos e no lugar certo, medidos na própria cabeça do manequim (depois do capsula.py).

- **As bocas** (``boca/ia.<estado>.svg``): mapas de pixel à mão. O sorriso é a boca fechada das
  poses comuns; a neutra, a "o" e a risada são as das outras poses; a meia e a aberta são as da fala.
- **Os óculos** (``oculos/<id>.svg``): a armação em volta de cada olho, a ponte e as hastes até a
  lateral do rosto, na cor ``oculos``; a lente tinge o que está embaixo (``data-mistura``), e um
  brilho branco no canto.

    python desenhar_partes.py PARTES
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

import pixels

# ── as bocas ─────────────────────────────────────────────────────────────
# "#" contorno, "b" o de dentro, "d" dente, "l" língua, "s" a sombra do lábio de baixo (pele)
BOCAS = {
    "sorriso": [
        "#...............#",
        ".##...........##.",
        "...###########...",
        ".....sssssss.....",
    ],
    "neutra": [
        ".###########.",
        "...sssssss...",
    ],
    "o": [
        ".###.",
        "#bbb#",
        "#bbb#",
        "#bbb#",
        ".###.",
        ".sss.",
    ],
    "meia": [
        ".###########.",
        "#ddddddddddd#",
        "#bbbbbbbbbbb#",
        ".###########.",
        "...sssssss...",
    ],
    "aberta": [
        "..###########..",
        ".#ddddddddddd#.",
        "#bbbbbbbbbbbbb#",
        "#bbbblllllbbbb#",
        ".#blllllllllb#.",
        "..###########..",
        "....sssssss....",
    ],
    "rindo": [
        "##...............##",
        ".#################.",
        ".#ddddddddddddddd#.",
        "..#bbbbbbbbbbbbb#..",
        "..#bbblllllllbbb#..",
        "...#blllllllllb#...",
        "....###########....",
        "......sssssss......",
    ],
}
#: A linha de cima de cada boca, a partir da linha da boca do manequim (o "o" e a risada sobem).
SUBIDA = {"sorriso": -1, "neutra": 0, "o": -2, "meia": -1, "aberta": -1, "rindo": -2}
CLASSE = {"#": "contorno", "b": "boca", "d": "dente", "l": "lingua", "s": "pele-sombra"}


def desenhar_boca(nome: str, cx: int, y0: int) -> np.ndarray:
    mapa = BOCAS[nome]
    larg = len(mapa[0])
    assert all(len(linha) == larg for linha in mapa), nome
    assert all(linha == linha[::-1] for linha in mapa), f"a boca {nome} não é simétrica"
    g = pixels.vazia()
    x0 = cx - larg // 2                                       # a largura é ímpar: centrada
    for i, linha in enumerate(mapa):
        for j, ch in enumerate(linha):
            if ch in CLASSE:
                g[y0 + SUBIDA[nome] + i, x0 + j] = CLASSE[ch]
    return g


# ── os óculos ────────────────────────────────────────────────────────────


def caixa(m: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(m)
    return int(ys.min()), int(xs.min()), int(ys.max()), int(xs.max())


def retangulo(g: np.ndarray, y0: int, x0: int, y1: int, x1: int, classe: str, raio: int = 0,
              grossura: int = 1) -> np.ndarray:
    """A borda de um retângulo de cantos arredondados (``raio`` em pixels cortados do canto);
    devolve a máscara de dentro (a lente)."""
    h, w = y1 - y0 + 1, x1 - x0 + 1
    dentro = np.zeros(g.shape, bool)
    forma = np.zeros((h, w), bool)
    for i in range(h):
        for j in range(w):
            di = min(i, h - 1 - i)
            dj = min(j, w - 1 - j)
            forma[i, j] = not (di < raio and dj < raio and (raio - di) + (raio - dj) > raio + 1)
    miolo = ndimage.binary_erosion(forma, iterations=grossura)
    for i in range(h):
        for j in range(w):
            if forma[i, j] and not miolo[i, j]:
                g[y0 + i, x0 + j] = classe
            elif miolo[i, j]:
                dentro[y0 + i, x0 + j] = True
    return dentro


def desenhar_oculos(estilo: str, olhos: list[tuple[int, int, int, int]], lados: tuple[int, int]
                    ) -> tuple[np.ndarray, np.ndarray]:
    """A armação (grade) e a lente (máscara). ``olhos``: a caixa de cada olho (o branco e o
    contorno); ``lados``: as colunas do contorno do rosto, onde as hastes acabam."""
    g = pixels.vazia()
    lente = np.zeros(g.shape, bool)
    (ey0, ex0, ey1, ex1), (dy0, dx0, dy1, dx1) = sorted(olhos, key=lambda c: c[1])
    topo, base = min(ey0, dy0) - 1, max(ey1, dy1) + 2
    caixas = [(topo, ex0 - 2, base, ex1 + 2), (topo, dx0 - 2, base, dx1 + 2)]
    if estilo == "redondos":
        for y0, x0, y1, x1 in caixas:
            lente |= retangulo(g, y0, x0, y1, x1, "oculos", raio=4)
    elif estilo == "retangulares":
        for y0, x0, y1, x1 in caixas:
            lente |= retangulo(g, y0 + 1, x0, y1 - 1, x1, "oculos-luz", raio=1)
    elif estilo == "quadrados":
        for y0, x0, y1, x1 in caixas:
            lente |= retangulo(g, y0 - 1, x0 - 1, y1, x1 + 1, "oculos", raio=2, grossura=2)
            g[y0 - 1, x0 + 1:x1] = "oculos-luz"                   # o brilho em cima da armação
    elif estilo == "sol":
        for y0, x0, y1, x1 in caixas:
            dentro = retangulo(g, y0, x0, y1, x1, "oculos", raio=2)
            g[dentro] = "oculos-sombra2"                          # a lente escura
            ys, xs = np.nonzero(dentro)
            yb, xb = int(ys.min()) + 1, int(xs.min()) + 1
            g[yb, xb:xb + 3] = "branco"                           # o brilho
            g[yb + 1, xb] = "branco"
    else:
        raise ValueError(estilo)
    # a ponte, na altura do meio dos olhos, entre as duas armações
    meio = (topo + base) // 2 - 1
    esq_fim = caixas[0][3] + (1 if estilo == "quadrados" else 0)
    dir_ini = caixas[1][1] - (1 if estilo == "quadrados" else 0)
    classe = "oculos-luz" if estilo == "retangulares" else "oculos"
    g[meio, esq_fim + 1:dir_ini] = classe
    # as hastes, da armação até o contorno do rosto
    haste = topo + 2
    g[haste, lados[0] + 1:caixas[0][1] - (1 if estilo == "quadrados" else 0)] = classe
    g[haste, caixas[1][3] + (2 if estilo == "quadrados" else 1):lados[1]] = classe
    if estilo != "sol":
        for y0, x0, _y1, _x1 in caixas:                          # o brilho no canto da lente
            g[y0 + 2, x0 + 2] = "branco"
            g[y0 + 2, x0 + 3] = "branco"
            g[y0 + 3, x0 + 2] = "branco"
    return g, lente & (g == "")


def svg_dos_oculos(g: np.ndarray, lente: np.ndarray) -> str:
    """A armação e, numa peça de mistura, a lente (ela tinge o olho que está embaixo)."""
    ys, xs = np.nonzero(lente)
    peca = (f'<g data-peca="lente" data-mistura="sim"><path class="lente" fill-opacity="0.18" '
            f'd="{pixels.faixas(list(zip(ys.tolist(), xs.tolist())))}"/></g>') if len(ys) else ""
    return pixels.svg(pixels.grupo("oculos", g, pecas=peca))


def main() -> None:
    partes = Path(sys.argv[1])
    grupos = pixels.ler(partes / "cabeca" / "manequim.svg")
    cab = next(g for c, _e, g in grupos if c == "cabeca")
    # os olhos: o branco (e a íris) de cada um, com o contorno em volta
    olho = np.vectorize(lambda c: c == "branco" or c.startswith("olho"))(cab)
    rot, n = ndimage.label(ndimage.binary_dilation(olho, iterations=1))
    tamanhos = ndimage.sum(olho, rot, range(1, n + 1))
    dois = 1 + np.argsort(tamanhos)[-2:]
    olhos = []
    for k in dois:
        y0, x0, y1, x1 = caixa(rot == k)
        olhos.append((y0, x0, y1, x1))
    # a boca: no meio do rosto, uma linha abaixo de onde o nariz acaba (o fim do desenho escuro
    # do nariz, entre os olhos)
    (ey0, ex0, ey1, ex1), (dy0, dx0, dy1, dx1) = sorted(olhos, key=lambda c: c[1])
    cx = (ex0 + dx1 + 1) // 2
    escuro = np.vectorize(lambda c: c == "contorno" or c.endswith("sombra"))(cab)
    nariz = [y for y in range(ey1 + 2, ey1 + 20) if escuro[y, cx - 3:cx + 4].any()]
    boca_y = max(nariz) + 5
    linha = np.nonzero(cab[ey1] != "")[0]
    # as colunas do contorno do rosto na altura dos olhos (sem a orelha): o primeiro contorno
    # com pele do lado de dentro
    pele = np.vectorize(lambda c: c.startswith("pele"))(cab)
    contorno = cab == "contorno"
    esq = max(x for x in range(int(linha[0]), ex0) if contorno[ey0, x] and pele[ey0, x + 1])
    dir_ = min(x for x in range(dx1, int(linha[-1]) + 1) if contorno[ey0, x] and pele[ey0, x - 1])
    print(f"olhos {sorted(olhos, key=lambda c: c[1])}, centro {cx}, boca na linha {boca_y}, rosto {esq}-{dir_}")
    (partes / "boca").mkdir(exist_ok=True)
    (partes / "oculos").mkdir(exist_ok=True)
    for nome in BOCAS:
        assert len(BOCAS[nome][0]) % 2 == 1, f"a boca {nome} precisa de largura ímpar (o centro é um pixel)"
        pixels.escrever(partes / "boca" / f"ia.{nome}.svg", [("boca", "", desenhar_boca(nome, cx, boca_y))])
    for estilo in ("redondos", "retangulares", "quadrados", "sol"):
        g, lente = desenhar_oculos(estilo, olhos, (esq, dir_))
        (partes / "oculos" / f"{estilo}.svg").write_text(svg_dos_oculos(g, lente))
    print("bocas:", ", ".join(BOCAS), "| óculos: redondos, retangulares, quadrados, sol")


if __name__ == "__main__":
    main()
