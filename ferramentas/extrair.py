"""As partes do personagem a partir das imagens geradas: o manequim e as edições dele.

Para cada edição (um cabelo, uma barba, os óculos, os braços de uma pose):
  1. tira o magenta e a borda branca de adesivo (a página refaz a borda);
  2. alinha com o manequim (a IA às vezes desloca a imagem uns pixels);
  3. a parte é o que mudou em relação ao manequim, dentro da região da categoria;
  4. tudo é levado ao quadro padrão pela cabeça do manequim e à grade de 150;
  5. cada pixel vira uma classe de cor (contorno, branco, pele-sombra, cabelo-luz…), para a
     página recolorir, e o SVG sai como faixas de pixel.

    uv run --with numpy --with pillow --with scipy python extrair.py GERADO PARTES
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

GERADO, PARTES = Path(sys.argv[1]), Path(sys.argv[2])
LADO, GRADE = 900, 150
CEL = LADO // GRADE
TOPO, LARGURA = 48, 312          # o alto do contorno da cabeça e a largura dela, no quadro de 900

# ── recortar ──────────────────────────────────────────────────────────────


def recortar(caminho: Path) -> np.ndarray:
    """RGBA sem o magenta e sem a borda branca de adesivo (o branco ligado ao fundo)."""
    a = np.asarray(Image.open(caminho).convert("RGB")).astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    magenta = (r > 160) & (b > 160) & (g < 120)
    # a mistura do magenta com o branco na borda (rosa claro) também é fundo
    rosa = (r > 200) & (b > 190) & (g < 225) & (np.abs(r - b) < 45) & (g < r - 25)
    # o fundo é só o que se liga à borda da imagem: um rosado dentro do rosto (o canto do olho)
    # não é fundo, e por ele o adesivo engolia o branco dos olhos
    candidato = magenta | rosa
    rot, _ = ndimage.label(candidato)
    da_borda = np.unique(np.concatenate([rot[0], rot[-1], rot[:, 0], rot[:, -1]]))
    fundo = np.isin(rot, da_borda[da_borda > 0])
    branco = (a.min(axis=-1) > 205) & ((a.max(axis=-1) - a.min(axis=-1)) < 40)
    # o adesivo: o branco que encosta no fundo, crescendo a partir dele
    adesivo = np.zeros_like(fundo)
    borda = ndimage.binary_dilation(fundo, iterations=1) & branco
    while borda.any():
        adesivo |= borda
        borda = ndimage.binary_dilation(borda, iterations=1) & branco & ~adesivo
    alfa = ~(fundo | adesivo)
    alfa = ndimage.binary_opening(alfa, iterations=1)
    return np.dstack([a.astype(np.uint8), (alfa * 255).astype(np.uint8)])


def alinhar(img: np.ndarray, ref: np.ndarray, regiao: np.ndarray) -> np.ndarray:
    """Desloca ``img`` (até 8 px) para casar com ``ref`` dentro de ``regiao``."""
    melhor, erro = (0, 0), None
    for dy in range(-8, 9):
        for dx in range(-8, 9):
            m = np.roll(img, (dy, dx), axis=(0, 1))
            e = np.abs(m[..., :3].astype(int) - ref[..., :3].astype(int)).sum(-1)[regiao].mean()
            if erro is None or e < erro:
                melhor, erro = (dy, dx), e
    return np.roll(img, melhor, axis=(0, 1))


# ── a geometria (pela cabeça do manequim) ─────────────────────────────────


def cabeca(alfa: np.ndarray) -> tuple[int, int, int]:
    linhas = np.nonzero(alfa.any(axis=1))[0]
    topo = int(linhas[0])
    altura = alfa.shape[0]
    faixa = alfa[topo + int(altura * 0.11): topo + int(altura * 0.15)]
    cols = np.nonzero(faixa.any(axis=0))[0]
    trechos, ini = [], cols[0]
    for c0, c1 in zip(cols, cols[1:]):
        if c1 != c0 + 1:
            trechos.append((ini, c0))
            ini = c1
    trechos.append((ini, cols[-1]))
    meio = alfa.shape[1] / 2
    a, b = min(trechos, key=lambda t: abs((t[0] + t[1]) / 2 - meio) - (t[1] - t[0]))
    return topo, int(b - a), int((a + b) / 2)


def para_o_quadro(img: np.ndarray, geo: tuple[int, int, int]) -> np.ndarray:
    topo, largura, centro = geo
    escala = LARGURA / largura
    im = Image.fromarray(img, "RGBA")
    novo = im.resize((round(im.width * escala), round(im.height * escala)), Image.NEAREST)
    quadro = Image.new("RGBA", (LADO, LADO), (0, 0, 0, 0))
    x, y = round(LADO / 2 - centro * escala), round(TOPO - topo * escala)
    quadro.alpha_composite(novo, (max(0, x), max(0, y)), (max(0, -x), max(0, -y)))
    return np.asarray(quadro)


def fase(img: np.ndarray) -> tuple[int, int]:
    """O deslocamento (0..5) da grade que deixa cada célula mais uniforme: o pixel da IA
    não cai certinho no da grade."""
    rgb = img[..., :3].astype(np.float32)
    melhor, menor = (0, 0), None
    for oy in range(CEL):
        for ox in range(CEL):
            r = rgb[oy:oy + (GRADE - 1) * CEL, ox:ox + (GRADE - 1) * CEL]
            cel = r.reshape(GRADE - 1, CEL, GRADE - 1, CEL, 3)
            v = cel.var(axis=(1, 3)).sum()
            if menor is None or v < menor:
                melhor, menor = (oy, ox), v
    return melhor


def na_grade(img: np.ndarray, f: tuple[int, int]) -> np.ndarray:
    """Cada célula de 6 × 6 vira um pixel: a cor mais comum, se a maior parte for cheia."""
    oy, ox = f
    pad = np.zeros((LADO + CEL, LADO + CEL, 4), np.uint8)
    pad[:LADO, :LADO] = img
    out = np.zeros((GRADE, GRADE, 4), np.uint8)
    for gy in range(GRADE):
        for gx in range(GRADE):
            c = pad[oy + gy * CEL: oy + (gy + 1) * CEL, ox + gx * CEL: ox + (gx + 1) * CEL].reshape(-1, 4)
            cheios = c[c[:, 3] > 128]
            if len(cheios) < CEL * CEL / 2:
                continue
            cores, n = np.unique(cheios[:, :3], axis=0, return_counts=True)
            out[gy, gx, :3] = cores[n.argmax()]
            out[gy, gx, 3] = 255
    return out


# ── as cores em classes ───────────────────────────────────────────────────

def lum(c: np.ndarray) -> np.ndarray:
    return c[..., 0] * 0.299 + c[..., 1] * 0.587 + c[..., 2] * 0.114


def tons_de(lums: np.ndarray) -> tuple[np.ndarray, int]:
    """Os tons que o desenho usou de verdade: os picos do histograma da luminância (no mínimo
    14 de distância entre eles). Devolve os picos e qual deles é a base (o mais comum)."""
    hist, bordas = np.histogram(lums, bins=64, range=(0, 256))
    hist = ndimage.uniform_filter1d(hist.astype(float), 3)
    centros = (bordas[:-1] + bordas[1:]) / 2
    ordem = np.argsort(hist)[::-1]
    picos: list[float] = []
    for i in ordem:
        if hist[i] < max(3.0, hist.max() * 0.04):
            break
        if all(abs(centros[i] - q) >= 14 for q in picos):
            picos.append(float(centros[i]))
    picos_arr = np.array(sorted(picos)) if picos else np.array([float(np.median(lums))])
    perto = np.abs(lums[:, None] - picos_arr[None, :]).argmin(axis=1)
    base = int(np.bincount(perto, minlength=len(picos_arr)).argmax())
    return picos_arr, base


def nome_do_tom(i: int, base: int, espaco: str) -> str:
    """O tom ``i`` (pela ordem de luminância) relativo à base: mais escuro é sombra (e sombra2
    para o segundo), mais claro é luz."""
    if i == base:
        return espaco
    if i < base:
        return f"{espaco}-sombra" if base - i == 1 else f"{espaco}-sombra2"
    return f"{espaco}-luz"


def eh_pele(c: np.ndarray, pele: np.ndarray) -> bool:
    return bool(np.min(np.abs(pele.astype(int) - c.astype(int)).sum(-1)) < 40)


#: A roupa só começa abaixo do queixo: no rosto, o cinza escuro (o canto do olho) não é roupa.
ROUPA_DESDE = 84


def classificar(grade: np.ndarray, espaco: str, pele: np.ndarray | None, roupa: np.ndarray | None,
                outro=None) -> dict[str, list[tuple[int, int]]]:
    """As classes de cada pixel cheio da grade; ``outro(y, x)`` diz o espaço do que não é
    pele nem roupa (no manequim: o olho ou a sobrancelha)."""
    cheio = grade[..., 3] > 0
    cores = grade[..., :3].astype(np.int16)
    l = lum(cores.astype(np.float32))
    preto = cheio & (l < 52)
    branco = cheio & (cores.min(-1) > 214) & ((cores.max(-1) - cores.min(-1)) < 30)
    resto = cheio & ~preto & ~branco
    tipo = np.full(grade.shape[:2], "", dtype=object)
    for y, x in zip(*np.nonzero(resto)):
        c = cores[y, x]
        if pele is not None and eh_pele(c, pele):
            tipo[y, x] = "pele"
        elif (roupa is not None and espaco != "roupa" and y >= ROUPA_DESDE
              and (int(c.max()) - int(c.min()) < 26 or np.min(np.abs(roupa.astype(int) - c).sum(-1)) < 30)):
            # abaixo do queixo, o cinza é a roupa (o suéter do manequim), em qualquer tom
            tipo[y, x] = "roupa"
        else:
            tipo[y, x] = outro(y, x) if outro else espaco
    saida: dict[str, list[tuple[int, int]]] = {}
    for nome in {t for t in tipo[resto]}:
        m = resto & (tipo == nome)
        ys, xs = np.nonzero(m)
        lums = l[ys, xs]
        picos, base = tons_de(lums)
        perto = np.abs(lums[:, None] - picos[None, :]).argmin(axis=1)
        for y, x, i in zip(ys, xs, perto):
            saida.setdefault(nome_do_tom(int(i), base, nome), []).append((y, x))
    for y, x in zip(*np.nonzero(preto)):
        saida.setdefault("contorno", []).append((y, x))
    for y, x in zip(*np.nonzero(branco)):
        saida.setdefault("branco", []).append((y, x))
    return saida


def caminho(pixels: list[tuple[int, int]]) -> str:
    """Os pixels como faixas horizontais: "M x y h n v 1 h -n z"."""
    linhas: dict[int, list[int]] = {}
    for y, x in pixels:
        linhas.setdefault(y, []).append(x)
    partes = []
    for y in sorted(linhas):
        xs = sorted(linhas[y])
        ini = ant = xs[0]
        for x in xs[1:] + [None]:
            if x is not None and x == ant + 1:
                ant = x
                continue
            n = ant - ini + 1
            partes.append(f"M{ini} {y}h{n}v1h-{n}z")
            if x is not None:
                ini = ant = x
    return "".join(partes)


def grupo(camada: str, classes: dict[str, list[tuple[int, int]]], extra: str = "") -> str:
    corpo = "".join(f'<path class="{c}" d="{caminho(p)}"/>' for c, p in sorted(classes.items()) if p)
    return f'<g data-camada="{camada}" data-pronto="sim"{extra}>{corpo}</g>'


def svg(*grupos: str) -> str:
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 150 150">\n  '
            + "\n  ".join(grupos) + "\n</svg>\n")


def gravar(categoria: str, nome: str, conteudo: str) -> None:
    pasta = PARTES / categoria
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{nome}.svg").write_text(conteudo)
    print(f"{categoria}/{nome}.svg {len(conteudo) // 1024} KB")


# ── as partes ─────────────────────────────────────────────────────────────

man = recortar(GERADO / "manequim.png")
geo = cabeca(man[..., 3] > 0)
man_q = para_o_quadro(man, geo)
f = fase(man_q)
man_g = na_grade(man_q, f)
alfa_man = man_g[..., 3] > 0
H = man.shape[0]

# as cores de referência do manequim: a pele (o meio do rosto) e a roupa (o peito)
topo_g = int(np.nonzero(alfa_man.any(axis=1))[0][0])
rosto = man_g[topo_g + 22: topo_g + 34, 66:84, :3].reshape(-1, 3)
peito = man_g[118:128, 50:100, :3].reshape(-1, 3)
pele = np.unique(rosto[lum(rosto.astype(np.float32)) > 90], axis=0)
roupa = np.unique(peito[lum(peito.astype(np.float32)) > 90], axis=0)

# o manequim em duas camadas: a cabeça (com o pescoço e o rosto) e o corpo (a roupa). No
# rosto, o que não é pele: perto do branco dos olhos é a íris, acima dela, a sobrancelha.
cores_man = man_g[..., :3].astype(np.int16)
branco_man = alfa_man & (cores_man.min(-1) > 214) & ((cores_man.max(-1) - cores_man.min(-1)) < 30)
olhos_man = np.zeros_like(branco_man)
olhos_man[topo_g + 34: topo_g + 50] = branco_man[topo_g + 34: topo_g + 50]
perto_do_olho = ndimage.binary_dilation(olhos_man, iterations=2)
c_man = classificar(man_g, "pele", pele, roupa,
                    outro=lambda y, x: "olho" if perto_do_olho[y, x] else "sobrancelha")
eh_roupa = np.zeros(alfa_man.shape, bool)
for c, px in c_man.items():
    if c.startswith("roupa"):
        for y, x in px:
            eh_roupa[y, x] = True
# o contorno que encosta na roupa (a gola, as laterais) fica com o corpo
contorno_da_roupa = ndimage.binary_dilation(eh_roupa, iterations=1)
cab, corpo = {}, {}
for c, px in c_man.items():
    for y, x in px:
        destino = corpo if (eh_roupa[y, x] or (c == "contorno" and contorno_da_roupa[y, x] and y > topo_g + 60)) else cab
        destino.setdefault(c, []).append((y, x))
gravar("cabeca", "ia-manequim", svg(grupo("cabeca", cab), grupo("corpo", corpo)))

REGIOES = {
    # o cabelo: fora do miolo do rosto (da sobrancelha para baixo)
    "cabelo": lambda g: ~((np.arange(GRADE)[:, None] > topo_g + 31)
                          & ndimage.binary_erosion(alfa_man & ~eh_roupa, iterations=3)
                          & (np.arange(GRADE)[None, :] > 56) & (np.arange(GRADE)[None, :] < 94)),
    "barba": lambda g: (np.arange(GRADE)[:, None] > topo_g + 46) & (np.arange(GRADE)[:, None] < ROUPA_DESDE + 2),
    "oculos": lambda g: (np.arange(GRADE)[:, None] > topo_g + 33) & (np.arange(GRADE)[:, None] < topo_g + 55),
    "bracos": lambda g: (np.arange(GRADE)[:, None] > topo_g + 66),
}

catalogo = []
for arquivo in sorted(GERADO.glob("*.png")):
    if arquivo.stem == "manequim":
        continue
    categoria, nome = arquivo.stem.split("-", 1)
    ed = recortar(arquivo)
    regiao_estavel = np.zeros(ed.shape[:2], bool)
    if categoria == "bracos":
        regiao_estavel[: int(H * 0.45)] = True          # a cabeça não muda
    else:
        regiao_estavel[int(H * 0.8):] = True            # o peito não muda
    ed = alinhar(ed, man, regiao_estavel & (man[..., 3] > 0))
    ed_g = na_grade(para_o_quadro(ed, geo), f)
    alfa_ed = ed_g[..., 3] > 0
    dif = np.abs(ed_g[..., :3].astype(int) - man_g[..., :3].astype(int)).sum(-1)
    mudou = alfa_ed & (~alfa_man | (dif > 70))
    mudou &= REGIOES[categoria](ed_g)
    # o fio de 1 px na borda da roupa (a IA deslocou um pixel) não é parte: abaixo do queixo,
    # o que é fino sai; o cabelo comprido e os braços são grossos e ficam
    abaixo = np.arange(GRADE)[:, None] >= ROUPA_DESDE
    if categoria in ("cabelo", "barba"):
        mudou = (mudou & ~abaixo) | ndimage.binary_opening(mudou & abaixo)
    rot, n = ndimage.label(mudou)
    if n:
        tam = ndimage.sum(mudou, rot, range(1, n + 1))
        mudou = np.isin(rot, 1 + np.nonzero(tam >= (40 if categoria == "bracos" else 6))[0])
    parte = ed_g.copy()
    parte[~mudou] = 0
    espaco = {"cabelo": "cabelo", "barba": "barba", "oculos": "oculos", "bracos": "roupa"}[categoria]
    if categoria == "bracos":
        # nos braços: o cinza (sem saturação) é a manga; o resto é a mão
        cp = parte[..., :3].astype(np.int16)
        cinza = (cp.max(-1) - cp.min(-1)) < 26
        classes = classificar(parte, "roupa", None, None,
                              outro=lambda y, x: "roupa" if cinza[y, x] else "pele")
    elif categoria in ("cabelo", "barba"):
        # o cabelo e a barba não têm pele: o reflexo claro do cabelo parece pele e não é
        classes = classificar(parte, espaco, None, None)
    else:
        classes = classificar(parte, espaco, pele, None)
    if categoria == "bracos":
        # o que a pose apaga do manequim: os braços de antes
        apaga = alfa_man & ~alfa_ed & (np.arange(GRADE)[:, None] > topo_g + 66)
        gravar("bracos", f"ia.{nome}", svg(grupo("apaga", {"vazio": list(zip(*np.nonzero(apaga)))}),
                                           grupo("braco-frente", classes)))
    else:
        camada = {"cabelo": "cabelo-frente", "barba": "barba", "oculos": "oculos"}[categoria]
        gravar(categoria, f"ia-{nome}", svg(grupo(camada, classes)))
    catalogo.append({"categoria": categoria, "id": nome, "pixels": int(mudou.sum())})

(PARTES / "piloto.json").write_text(json.dumps({"geometria": {"topo": TOPO, "largura": LARGURA, "fase": f},
                                                "pele": pele.tolist(), "roupa": roupa.tolist(),
                                                "partes": catalogo}, indent=1))
