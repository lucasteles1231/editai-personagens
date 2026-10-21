"""A biblioteca de partes a partir das edições do manequim (biblioteca/<categoria>-<id>.png).

As regiões de cada categoria saem dos marcos medidos no próprio manequim (os olhos, as
sobrancelhas, a boca, o começo da roupa), e não de distâncias fixas: o manequim pode mudar.

Depois desta extração vêm o ``capsula.py`` (a cabeça com o maxilar largo do exemplo do dono) e o
``desenhar_partes.py`` (as bocas e os óculos, desenhados em código: reduzidos à grade de 150, os da
IA viravam riscos e armações furadas).

    uv run --with numpy --with pillow --with scipy python extrair_biblioteca.py BIBLIOTECA SAIDA
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

AQUI = Path(__file__).parent
# as funções de base (recortar, alinhar, geometria, grade, tons, SVG) vêm do extrair.py do piloto
_fonte = (AQUI / "extrair.py").read_text()
exec(_fonte[_fonte.index("GERADO, PARTES"):_fonte.index("# ── as partes")].replace(
    "GERADO, PARTES = Path(sys.argv[1]), Path(sys.argv[2])", ""))

GERADO, PARTES = Path(sys.argv[1]), Path(sys.argv[2])
# só algumas categorias (para conferir uma mudança sem refazer tudo): "cabelo,barba"
SO = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None
COLS = np.arange(GRADE)[None, :]
ROWS = np.arange(GRADE)[:, None]
#: As bocas e os óculos são desenhados em código (desenhar_partes.py).
EM_CODIGO = {"boca", "oculos"}
#: Os chapéus: o cabelo só aparece abaixo deles (o desenhista lê ``data-cobre``).
CHAPEUS = {"bone", "gorro"}

man = recortar(GERADO / "manequim.png")
geo = cabeca(man[..., 3] > 0)
man_q = para_o_quadro(man, geo)
f = fase(man_q)
man_g = na_grade(man_q, f)
alfa_man = man_g[..., 3] > 0
H = man.shape[0]
cores = man_g[..., :3].astype(np.int16)
lum_man = lum(cores.astype(np.float32))
sat = cores.max(-1) - cores.min(-1)
topo_g = int(np.nonzero(alfa_man.any(axis=1))[0][0])

# ── os marcos do rosto, medidos no manequim ──────────────────────────────
centro = slice(50, 100)
branco_man = alfa_man & (cores.min(-1) > 214) & (sat < 30)
linhas_olho = np.nonzero(branco_man[:, centro].any(axis=1))[0]
linhas_olho = linhas_olho[(linhas_olho > topo_g + 15) & (linhas_olho < topo_g + 75)]
olho_ini, olho_fim = int(linhas_olho.min()), int(linhas_olho.max())
# a sobrancelha: o marrom escuro (não preto) logo acima dos olhos
marrom = alfa_man & (lum_man < 110) & (lum_man > 30) & (cores[..., 0] > cores[..., 2] + 12)
linhas_sob = np.nonzero(marrom[olho_ini - 14: olho_ini, centro].sum(axis=1) > 3)[0] + olho_ini - 14
sob_ini, sob_fim = int(linhas_sob.min()), int(linhas_sob.max())
# a roupa: a primeira linha com cinza (o suéter) no meio do quadro, abaixo dos olhos
cinza = alfa_man & (sat < 22) & (lum_man > 100) & (lum_man < 225)
linhas_roupa = np.nonzero(cinza[:, 60:90].sum(axis=1) > 6)[0]
ROUPA_DESDE = int(linhas_roupa[linhas_roupa > olho_fim + 10].min())
# a boca: no meio do rosto, as linhas pretas formam grupos (o nariz, a boca, o queixo); a boca
# é o grupo logo antes do queixo (o último), na linha mais cheia dele
preto = alfa_man & (lum_man < 52)
cheias = preto[:, 66:84].sum(axis=1)
linhas_boca = np.nonzero(cheias >= 6)[0]
linhas_boca = linhas_boca[(linhas_boca > olho_fim + 6) & (linhas_boca < ROUPA_DESDE - 4)]
grupos_boca = np.split(linhas_boca, np.nonzero(np.diff(linhas_boca) > 2)[0] + 1)
if len(grupos_boca) < 2:
    raise SystemExit(f"não achei a boca e o queixo do manequim: linhas {linhas_boca.tolist()}")
boca_y = int(grupos_boca[-2][np.argmax(cheias[grupos_boca[-2]])])
# a largura do rosto na altura dos olhos
cols_rosto = np.nonzero(alfa_man[olho_fim])[0]
rosto_x0, rosto_x1 = int(cols_rosto.min()), int(cols_rosto.max())

caixa_olhos = (ROWS >= olho_ini - 3) & (ROWS <= olho_fim + 3) & (COLS > rosto_x0 + 4) & (COLS < rosto_x1 - 4)
caixa_sob = (ROWS >= sob_ini - 5) & (ROWS <= sob_fim + 2) & (COLS > rosto_x0 + 4) & (COLS < rosto_x1 - 4)
caixa_boca = (ROWS >= boca_y - 5) & (ROWS <= boca_y + 9) & (COLS > 58) & (COLS < 92)
# o contorno da silhueta (o maior pedaço preto ligado: a cabeça, as orelhas, o queixo) não é da
# boca: a caixa larga alcança o queixo dos lados
_rot, _n = ndimage.label(alfa_man & (lum_man < 52), structure=np.ones((3, 3)))
SILHUETA = ndimage.binary_dilation(_rot == 1 + int(np.argmax(ndimage.sum(_rot > 0, _rot, range(1, _n + 1)))))
caixa_boca &= ~SILHUETA

# a pele e a roupa de referência
rosto = man_g[olho_fim + 3: boca_y - 3, 62:88, :3].reshape(-1, 3)
pele = np.unique(rosto[lum(rosto.astype(np.float32)) > 90], axis=0)
peito = man_g[ROUPA_DESDE + 10: ROUPA_DESDE + 25, 50:100, :3].reshape(-1, 3)
roupa = np.unique(peito[lum(peito.astype(np.float32)) > 90], axis=0)
# a classificação da roupa (no classificar do piloto) usa ROUPA_DESDE: o valor medido vale
globals()["ROUPA_DESDE"] = ROUPA_DESDE


# ── as classes como grade ────────────────────────────────────────────────


def para_grade(classes: dict) -> np.ndarray:
    g = np.full((GRADE, GRADE), "", dtype=object)
    for c, px in classes.items():
        for y, x in px:
            g[y, x] = c
    return g


def para_classes(g: np.ndarray, onde: np.ndarray | None = None) -> dict:
    saida: dict = {}
    m = g != ""
    if onde is not None:
        m &= onde
    for y, x in zip(*np.nonzero(m)):
        saida.setdefault(g[y, x], []).append((int(y), int(x)))
    return saida


def marrom_escuro(c: np.ndarray) -> bool:
    """A íris e a sobrancelha do Nano Banana: marrom bem escuro, que o corte do contorno pegava
    (luminância uns 41). O contorno é preto de verdade."""
    l_ = float(lum(c.astype(np.float32)))
    return int(c[0]) - int(c[2]) > 18 and 22 < l_ < 95


def entre_brancos(grade_rgb: np.ndarray, alcance: int = 4) -> np.ndarray:
    """O que tem o branco do olho dos dois lados, na mesma linha (a até ``alcance`` px): a íris.
    O canto do olho e a sobrancelha não têm."""
    rgb = grade_rgb[..., :3].astype(np.int16)
    branco = (grade_rgb[..., 3] > 0) & (rgb.min(-1) > 214) & ((rgb.max(-1) - rgb.min(-1)) < 30)
    esq = np.zeros_like(branco)
    dir_ = np.zeros_like(branco)
    for k in range(1, alcance + 1):
        esq[:, k:] |= branco[:, :-k]
        dir_[:, :-k] |= branco[:, k:]
    return esq & dir_


def so_entre_brancos(g: np.ndarray, grade_rgb: np.ndarray) -> None:
    """"olho" fora do branco do olho (o canto, um cílio) era engano: volta a ser contorno, para a
    cor escolhida não pintar o canto do olho."""
    fora_ = caixa_olhos & ~entre_brancos(grade_rgb) & np.vectorize(lambda c: c.startswith("olho"))(g)
    g[fora_] = "contorno"


def colorir(g: np.ndarray, grade_rgb: np.ndarray, onde: np.ndarray, espaco: str) -> None:
    """O contorno marrom-escuro dentro de ``onde`` vira o espaço de cor (a íris, a sobrancelha),
    em dois tons pela luminância: assim a cor escolhida pinta o olho e a sobrancelha."""
    for y, x in zip(*np.nonzero(onde & (g == "contorno"))):
        c = grade_rgb[y, x, :3].astype(np.int16)
        if marrom_escuro(c):
            g[y, x] = espaco if lum(c.astype(np.float32)) >= 34 else f"{espaco}-sombra"


# ── o manequim: a cabeça, o pescoço e o corpo ─────────────────────────────
olhos_man = branco_man & caixa_olhos
perto_do_olho = ndimage.binary_dilation(olhos_man, iterations=2)
c_man = classificar(man_g, "pele", pele, roupa,
                    outro=lambda y, x: "olho" if perto_do_olho[y, x] else "sobrancelha")
gm = para_grade(c_man)
# a sobrancelha e a íris (a linha do olho continua preta)
colorir(gm, man_g, caixa_sob & (ROWS <= sob_fim + 1), "sobrancelha")
colorir(gm, man_g, caixa_olhos & entre_brancos(man_g), "olho")
so_entre_brancos(gm, man_g)
# "sobrancelha" fora da sobrancelha é engano do classificar (o brilho da careca, o desenho de
# dentro da orelha, o canelado da gola): o claro vira luz da pele, o escuro, sombra
for y, x in zip(*np.nonzero(np.vectorize(lambda c: c.startswith("sobrancelha"))(gm) & ~caixa_sob)):
    gm[y, x] = "pele-luz" if lum_man[y, x] > 150 else "pele-sombra2"
for y, x in zip(*np.nonzero(np.vectorize(lambda c: c.startswith("olho"))(gm) & ~ndimage.binary_dilation(caixa_olhos))):
    gm[y, x] = "pele-sombra2"
# a sobrancelha são os dois pedaços grandes; um pixel solto na caixa dela (a sombra da têmpora)
# vira sombra da pele, e anda junto com o contorno no capsula.py
_sob = np.vectorize(lambda c: c.startswith("sobrancelha"))(gm)
_rot, _n = ndimage.label(_sob, structure=np.ones((3, 3)))
if _n > 2:
    _tam = ndimage.sum(_sob, _rot, range(1, _n + 1))
    _soltos = _sob & ~np.isin(_rot, 1 + np.argsort(_tam)[-2:])
    gm[_soltos] = "pele-sombra2"

eh_pele_g = np.vectorize(lambda c: c.startswith("pele"))(gm)
eh_roupa_g = np.vectorize(lambda c: c.startswith("roupa"))(gm)
_rot, _n = ndimage.label(eh_pele_g)
rosto_pele = _rot == _rot[20, int(np.mean(np.nonzero(alfa_man[20])[0]))]
QUEIXO = int(np.nonzero(rosto_pele.any(axis=1))[0][-1]) + 1      # a linha de baixo do queixo
# o pescoço: a pele abaixo do queixo ligada a ele, e as linhas dele (o contorno que encosta nessa
# pele e não na roupa: a linha da gola é da roupa)
abaixo = ROWS > QUEIXO
_rot, _n = ndimage.label(eh_pele_g & abaixo)
meio_x = int(round(np.mean(np.nonzero(rosto_pele[QUEIXO - 1])[0])))
pescoco_pele = _rot == _rot[QUEIXO + 2, meio_x]
vizinho = lambda m: ndimage.binary_dilation(m, structure=ndimage.generate_binary_structure(2, 1))  # noqa: E731
linhas_do_pescoco = (gm == "contorno") & abaixo & vizinho(pescoco_pele) & ~vizinho(eh_roupa_g)
pescoco = pescoco_pele | linhas_do_pescoco
corpo_m = (gm != "") & abaixo & ~pescoco
cabeca_m = (gm != "") & ~abaixo
# a boca do manequim sai: toda boca vem de uma parte (desenhar_partes.py), até o sorriso
boca_m = (ROWS >= boca_y - 2) & (ROWS <= boca_y + 5) & (COLS >= 64) & (COLS <= 87) & rosto_pele.any(axis=0)[None, :]
boca_m &= ndimage.binary_erosion(ndimage.binary_fill_holes(rosto_pele | (gm == "contorno") & cabeca_m), iterations=2)
gm[boca_m & cabeca_m] = "pele"
# no corpo, o que não é roupa nem contorno (o canelado da gola) vira o tom mais escuro dela
for y, x in zip(*np.nonzero(corpo_m & ~eh_roupa_g & (gm != "contorno"))):
    gm[y, x] = "roupa-sombra2"
CORPO_DO_MANEQUIM = corpo_m
print(f"marcos: topo {topo_g}, sobrancelha {sob_ini}-{sob_fim}, olhos {olho_ini}-{olho_fim}, boca {boca_y}, "
      f"queixo {QUEIXO}, roupa desde {ROUPA_DESDE}, rosto x {rosto_x0}-{rosto_x1}")
if not SO or "cabeca" in SO:
    gravar("cabeca", "manequim", svg(grupo("cabeca", para_classes(gm, cabeca_m)),
                                     grupo("pescoco", para_classes(gm, pescoco)),
                                     grupo("corpo", para_classes(gm, corpo_m))))
# a boca antiga do manequim, para limpar o risco dela de dentro das barbas
BOCA_ANTIGA = boca_m & (para_grade(c_man) == "contorno")

miolo_do_rosto = (ROWS > sob_ini - 1) & ndimage.binary_erosion(alfa_man & ~corpo_m, iterations=3) & \
    (COLS > rosto_x0 + 6) & (COLS < rosto_x1 - 6) & (ROWS < ROUPA_DESDE)
REGIOES = {
    "cabelo": ~miolo_do_rosto,
    "barba": (ROWS > olho_fim + 2) & (ROWS < ROUPA_DESDE + 2),
    "acessorio": ROWS < ROUPA_DESDE,
    # perto do branco do olho do manequim: a IA mexia na borda do rosto também, e esse ruído
    # ficava solto no rosto novo do capsula.py (os olhos não andam com o contorno)
    "olhos": caixa_olhos & ndimage.binary_dilation(branco_man & caixa_olhos, iterations=3),
    "sobrancelhas": caixa_sob,
    # a boca só até o queixo: a mão do "pensando" fica logo abaixo dela
    "bracos": ~(caixa_olhos | caixa_sob | (caixa_boca & (ROWS < boca_y + 4))),
    "roupa": ROWS >= ROUPA_DESDE - 6,
}
CAMADA = {"cabelo": "cabelo-frente", "barba": "barba", "acessorio": "acessorio", "olhos": "olhos",
          "sobrancelhas": "sobrancelhas", "bracos": "braco-frente", "roupa": "corpo"}

catalogo = []
for arquivo in sorted(GERADO.glob("*.png")):
    if arquivo.stem == "manequim":
        continue
    categoria, nome = arquivo.stem.split("-", 1)
    if categoria in EM_CODIGO or (SO and categoria not in SO):
        continue
    ed = recortar(arquivo)
    estavel = np.zeros(ed.shape[:2], bool)
    if categoria in ("bracos", "roupa"):
        estavel[: int(H * 0.40)] = True          # a cabeça não muda
    else:
        estavel[int(H * 0.82):] = True           # a barra da roupa não muda
    ed = alinhar(ed, man, estavel & (man[..., 3] > 0))
    ed_g = na_grade(para_o_quadro(ed, geo), f)
    alfa_ed = ed_g[..., 3] > 0
    dif = np.abs(ed_g[..., :3].astype(int) - man_g[..., :3].astype(int)).sum(-1)
    # a barba rala são pontinhos claros: o corte de "mudou" é mais baixo só para ela
    corte = 34 if (categoria, nome) == ("barba", "rala") else 70
    mudou = alfa_ed & (~alfa_man | (dif > corte))
    if categoria == "roupa":
        # a roupa nova substitui o corpo inteiro do manequim (o suéter, a gola e as linhas dos
        # ombros): o que é corpo no manequim também entra, mudado ou não
        mudou = alfa_ed & (mudou | CORPO_DO_MANEQUIM)
    mudou &= REGIOES[categoria]
    if categoria in ("cabelo", "barba"):
        abaixo_ = ROWS >= ROUPA_DESDE
        mudou = (mudou & ~abaixo_) | ndimage.binary_opening(mudou & abaixo_)
    rot, n = ndimage.label(mudou)
    if n:
        minimo = {"bracos": 40, "roupa": 40, "olhos": 2, "sobrancelhas": 2}.get(categoria, 6)
        tam = ndimage.sum(mudou, rot, range(1, n + 1))
        mudou = np.isin(rot, 1 + np.nonzero(tam >= minimo)[0])
    parte = ed_g.copy()
    parte[~mudou] = 0
    cp = parte[..., :3].astype(np.int16)
    extra = ""
    if categoria == "bracos":
        cinza_p = (cp.max(-1) - cp.min(-1)) < 26
        classes = classificar(parte, "roupa", None, None, outro=lambda y, x: "roupa" if cinza_p[y, x] else "pele")
    elif categoria == "roupa":
        claro = lum(cp.astype(np.float32)) > 228
        cinza_p = (cp.max(-1) - cp.min(-1)) < 26
        classes = classificar(parte, "roupa", None, None,
                              outro=lambda y, x: ("roupa2" if claro[y, x] else "roupa") if cinza_p[y, x] else "pele")
        # o branco da roupa (a camiseta por baixo da jaqueta, os cordões, os botões) é o segundo
        # tom dela, "roupa2", e a sombra cinza ligada a ele é a sombra desse tom: como "roupa",
        # ela pegava a cor da jaqueta em tracinhos na gola da camiseta
        gr = para_grade(classes)
        branco_ = gr == "branco"
        rot, _n = ndimage.label(branco_ | (gr == "roupa-sombra"))
        for k in set(np.unique(rot[branco_])) - {0}:
            pedaco = rot == k
            if branco_[pedaco].mean() >= 0.4:                  # é um pedaço claro, com a sombra dele
                gr[pedaco & (gr == "roupa-sombra")] = "roupa2-sombra"
        gr[branco_] = "roupa2"
        classes = para_classes(gr)
    elif categoria in ("cabelo", "barba"):
        classes = classificar(parte, categoria, None, None)
        if categoria == "barba":
            # o risco do sorriso antigo que a IA redesenhou junto com o bigode: no meio da barba
            # vira o tom dela; fora, sai (a boca nova é desenhada por cima)
            gb = para_grade(classes)
            for y, x in zip(*np.nonzero(BOCA_ANTIGA & (gb == "contorno"))):
                viz = [gb[y, v] for v in (x - 1, x + 1) if gb[y, v] not in ("", "contorno")]
                gb[y, x] = max(set(viz), key=viz.count) if len(viz) == 2 else ""
            classes = para_classes(gb)
    elif categoria == "olhos":
        perto = ndimage.binary_dilation(ed_g[..., :3].min(-1) > 214, iterations=2)
        classes = classificar(parte, "olho", pele, None, outro=lambda y, x: "olho" if perto[y, x] else "sobrancelha")
        go = para_grade(classes)
        colorir(go, ed_g, caixa_olhos & entre_brancos(ed_g), "olho")
        so_entre_brancos(go, ed_g)
        classes = para_classes(go)
    elif categoria == "sobrancelhas":
        classes = classificar(parte, "sobrancelha", pele, None)
        gs_ = para_grade(classes)
        colorir(gs_, ed_g, caixa_sob & (ROWS <= sob_fim + 1), "sobrancelha")
        classes = para_classes(gs_)
    elif categoria == "acessorio":
        classes = classificar(parte, "acessorio", pele, None)
    else:
        classes = classificar(parte, categoria, pele, None)
    if categoria == "acessorio" and nome in CHAPEUS:
        # a pele que a edição mexeu (a testa sob a aba) vai na camada da cabeça; o chapéu marca
        # que o cabelo só aparece abaixo dele
        pele_ = {c: px for c, px in classes.items() if c.startswith("pele")}
        resto = {c: px for c, px in classes.items() if not c.startswith("pele")}
        grupos_ = [grupo("cabeca", pele_) if pele_ else "", grupo("acessorio", resto, ' data-cobre="cabelo"')]
        grupos_ = [g for g in grupos_ if g]
    else:
        grupos_ = [grupo(CAMADA[categoria], classes, extra)]
    if categoria == "bracos":
        apaga = alfa_man & ~alfa_ed & (ROWS > ROUPA_DESDE - 4)
        grupos_.insert(0, grupo("apaga", {"vazio": list(zip(*np.nonzero(apaga)))}))
    estado = categoria in ("olhos", "sobrancelhas", "bracos")
    gravar(categoria, f"ia.{nome}" if estado else nome, svg(*grupos_))
    catalogo.append({"categoria": categoria, "id": nome, "pixels": int(mudou.sum())})

if not SO:
    (PARTES / "extracao.json").write_text(json.dumps({
        "geometria": {"topo": TOPO, "largura": LARGURA, "fase": f},
        "marcos": {"topo": topo_g, "sobrancelha": [sob_ini, sob_fim], "olhos": [olho_ini, olho_fim],
                   "boca": boca_y, "queixo": QUEIXO, "roupa_desde": ROUPA_DESDE, "rosto_x": [rosto_x0, rosto_x1]},
        "partes": catalogo}, indent=1))
