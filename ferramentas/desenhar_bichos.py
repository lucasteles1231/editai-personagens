"""Os olhos e as bocas dos bichos, desenhados em código (21/10/2026), no lugar medido pelo
``extrair_bichos.py`` (``bichos.json``): reduzidos à grade, os da IA viravam riscos, como as bocas
humanas.

- **Os olhos** (``olhos/<bicho>.<estado>.svg``), no estilo da folha do dono: redondos e escuros,
  com o brilho branco no alto. O de dentro é ``olho``, e a cor escolhida pinta. Os seis estados
  das poses: aberto, de lado (para a direita da tela, como o humano), para cima, arregalado,
  apertado (o "^" da risada) e meio fechado.
- **As bocas** (``boca/<bicho>.<estado>.svg``), logo abaixo do nariz: o "w" fechado do sorriso, a
  neutra, o "o", a meia e a aberta da fala, e a risada. Simétricas, de largura ímpar. No bico, a
  boca é ele abrindo no meio; na tromba do elefante e no sorriso largo do porco e do sapo, ela vem
  sem o risquinho do nariz.

    python desenhar_bichos.py BICHOS.json PARTES
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pixels  # noqa: E402

# ── os olhos ─────────────────────────────────────────────────────────────
# "#" contorno, "o" o de dentro (a cor do olho), "w" o brilho


def olho(estado: str, w: int, h: int) -> list[str]:
    """O desenho de um olho ``w`` × ``h`` (o tamanho medido no bicho) num estado."""
    if estado == "apertado":                       # o "^" da risada
        meio = w // 2
        linhas = [["."] * w for _ in range(3)]
        for x in range(w):
            linhas[min(2, abs(x - meio))][x] = "#"      # o bico no meio, em cima
        return ["".join(l) for l in linhas]
    if estado == "arregalado":
        w, h = w + 2, h + 2
    m = np.full((h, w), ".", dtype=object)
    cy, cx = (h - 1) / 2, (w - 1) / 2
    ry, rx = h / 2, w / 2
    for y in range(h):
        for x in range(w):
            d = ((y - cy) / ry) ** 2 + ((x - cx) / rx) ** 2
            if d <= 1.0:
                m[y, x] = "o"
    # o contorno: o de dentro que encosta no fora (ou na beirada)
    dentro = m == "o"
    borda = dentro & ~np.pad(dentro, 1)[2:, 1:-1] | dentro & ~np.pad(dentro, 1)[:-2, 1:-1] \
        | dentro & ~np.pad(dentro, 1)[1:-1, 2:] | dentro & ~np.pad(dentro, 1)[1:-1, :-2]
    m[borda] = "#"
    # o brilho: um quadrado de 2 no alto, para o lado de onde vem a luz (a esquerda), e um pixel
    # embaixo do outro lado; de lado e para cima, ele anda com o olhar
    # o brilho: 2 × 2 no primeiro canto de dentro, do alto (à esquerda; de lado, à direita); num
    # canto fixo ele caía no contorno do olho e sumia (o panda ficava sem olho)
    dentro_ = [(y, x) for y in range(h) for x in range(w) if m[y, x] == "o"]
    y_alto = min(y for y, _ in dentro_)
    xs_alto = [x for y, x in dentro_ if y == y_alto]
    by, bx = y_alto, (max(xs_alto) - 1 if estado == "lado" else min(xs_alto))
    for dy in (0, 1):
        for dx in (0, 1):
            if 0 <= by + dy < h and 0 <= bx + dx < w and m[by + dy, bx + dx] == "o":
                m[by + dy, bx + dx] = "w"
    if estado == "arregalado" and m[h - 3, w - 3] == "o":
        m[h - 3, w - 3] = "w"
    if estado == "meio":                           # a pálpebra cobre a metade de cima
        corte = h // 2 - 1
        m[:corte, :] = "."
        m[corte, dentro[corte]] = "#"
    return ["".join(l) for l in m]


def desenhar_olhos(estado: str, marcos: dict) -> np.ndarray:
    g = pixels.vazia()
    for o in marcos["olhos"]:
        y0, x0, y1, x1 = o["caixa"]
        w = int(np.clip(x1 - x0 + 1, 5, 7))
        h = int(np.clip(y1 - y0 + 1, 6, 8))
        mapa = olho(estado, w, h)
        alto, largo = len(mapa), len(mapa[0])
        cy, cx = (y0 + y1) / 2, (x0 + x1) / 2
        if estado == "lado":
            cx += 1
        if estado == "cima":
            cy -= 1
        top = int(round(cy - (alto - 1) / 2)) + (alto // 3 if estado == "apertado" else 0)
        esq = int(round(cx - (largo - 1) / 2))
        for i, linha in enumerate(mapa):
            for j, ch in enumerate(linha):
                if ch != ".":
                    g[top + i, esq + j] = {"#": "contorno", "o": "olho", "w": "branco"}[ch]
    return g


# ── as bocas ─────────────────────────────────────────────────────────────
# "#" contorno, "b" o de dentro, "l" a língua; a linha de cima é o risquinho do nariz à boca
BOCAS = {
    "sorriso": [
        "...#...",
        "#..#..#",
        ".##.##.",
    ],
    "neutra": [
        "...#...",
        ".#####.",
    ],
    "o": [
        "..#..",
        ".###.",
        "#bbb#",
        "#bbb#",
        ".###.",
    ],
    "meia": [
        "...#...",
        ".#####.",
        ".#bbb#.",
        "..###..",
    ],
    "aberta": [
        "...#...",
        ".#####.",
        "#bbbbb#",
        "#blllb#",
        ".#lll#.",
        "..###..",
    ],
    "rindo": [
        "....#....",
        ".#######.",
        ".#bbbbb#.",
        ".#blllb#.",
        "..#lll#..",
        "...###...",
    ],
}
CLASSE = {"#": "contorno", "b": "boca", "l": "lingua"}


def bocas_do_bico(largura: int) -> dict[str, list[str]]:
    """As bocas de um bico (o pato, a galinha, o pinguim): fechado, ele fica como veio; falando,
    abre no meio, com a largura dele (até 15). A primeira linha é a do meio do bico."""
    w = max(5, min(largura - 6, 15))
    w -= 1 - w % 2                                   # ímpar, para ficar simétrica
    meio = lambda a, b, c, n: a + b * (n - 2) + c    # noqa: E731
    aberta = lambda n: [                             # noqa: E731
        "#" * n,
        meio("#", "b", "#", n),
        "#b" + "l" * (n - 4) + "b#",
        ".#" + "l" * (n - 4) + "#.",
        ".." + "#" * (n - 4) + "..",
    ]
    return {
        "sorriso": [],
        "neutra": [],
        "o": [".###.", "#bbb#", "#bbb#", ".###."],
        "meia": ["#" * w, meio("#", "b", "#", w), meio(".", "#", ".", w)],
        "aberta": aberta(w),
        "rindo": aberta(w + 2),
    }


def desenhar_boca(nome: str, marcos: dict) -> np.ndarray:
    g = pixels.vazia()
    cx = int(round(marcos["centro_x"]))
    if marcos.get("bico"):
        mapa, y0 = bocas_do_bico(marcos["bico_largura"])[nome], marcos["boca_y"]
    else:
        mapa, y0 = BOCAS[nome], marcos["boca_y"]
        # sem o risquinho do nariz: na tromba do elefante não há nariz acima, e no sorriso de
        # bochecha a bochecha (o porco, o sapo) a boca continua a linha dele
        if marcos.get("sem_nariz") or marcos.get("sorriso_largo"):
            mapa, y0 = mapa[1:], y0 + 1
    assert all(len(l) == len(mapa[0]) and l == l[::-1] for l in mapa), nome
    for i, linha in enumerate(mapa):
        x0 = cx - len(linha) // 2
        for j, ch in enumerate(linha):
            if ch in CLASSE:
                g[y0 + i, x0 + j] = CLASSE[ch]
    if marcos.get("sorriso_largo"):
        # o meio do sorriso saiu (4 colunas de cada lado): a linha de cima da boca o religa
        for x in range(cx - 4, cx + 5):
            if g[y0, x] == "":
                g[y0, x] = "contorno"
    return g


ESTADOS_DOS_OLHOS = ("aberto", "lado", "cima", "arregalado", "apertado", "meio")


def main() -> None:
    marcos_ = json.loads(Path(sys.argv[1]).read_text())
    partes = Path(sys.argv[2])
    (partes / "olhos").mkdir(parents=True, exist_ok=True)
    (partes / "boca").mkdir(parents=True, exist_ok=True)
    for bicho, m in marcos_.items():
        for estado in ESTADOS_DOS_OLHOS:
            pixels.escrever(partes / "olhos" / f"{bicho}.{estado}.svg", [("olhos", "", desenhar_olhos(estado, m))])
        for nome in BOCAS:
            g = desenhar_boca(nome, m)
            # (o bico fechado é o próprio bico: a boca fica com a camada vazia)
            texto = pixels.svg(pixels.grupo("boca", g)) if not (g != "").any() else None
            if texto:
                (partes / "boca" / f"{bicho}.{nome}.svg").write_text(texto)
            else:
                pixels.escrever(partes / "boca" / f"{bicho}.{nome}.svg", [("boca", "", g)])
        print(bicho, "olhos", len(ESTADOS_DOS_OLHOS), "bocas", len(BOCAS))


if __name__ == "__main__":
    main()
