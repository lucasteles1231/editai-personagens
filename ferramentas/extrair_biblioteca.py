"""A biblioteca de partes a partir das edições do manequim (biblioteca/<categoria>-<id>.png).

As regiões de cada categoria saem dos marcos medidos no próprio manequim (os olhos, as
sobrancelhas, a boca, o começo da roupa), e não de distâncias fixas: o manequim pode mudar.

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
# só algumas categorias (para conferir uma mudança sem refazer tudo): "boca,olhos"
SO = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None
COLS = np.arange(GRADE)[None, :]
ROWS = np.arange(GRADE)[:, None]

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
print(f"marcos: topo {topo_g}, sobrancelha {sob_ini}-{sob_fim}, olhos {olho_ini}-{olho_fim}, boca {boca_y}, "
      f"roupa desde {ROUPA_DESDE}, rosto x {rosto_x0}-{rosto_x1}")

caixa_olhos = (ROWS >= olho_ini - 3) & (ROWS <= olho_fim + 3) & (COLS > rosto_x0 + 4) & (COLS < rosto_x1 - 4)
caixa_sob = (ROWS >= sob_ini - 5) & (ROWS <= sob_fim + 2) & (COLS > rosto_x0 + 4) & (COLS < rosto_x1 - 4)
caixa_boca = (ROWS >= boca_y - 5) & (ROWS <= boca_y + 9) & (COLS > 58) & (COLS < 92)
# o contorno da silhueta (o maior pedaço preto ligado: a cabeça, as orelhas, o queixo) não é da
# boca: a caixa larga da risada alcança o queixo dos lados
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

# ── o manequim: a cabeça e o corpo (o suéter) ─────────────────────────────
olhos_man = branco_man & caixa_olhos
perto_do_olho = ndimage.binary_dilation(olhos_man, iterations=2)
c_man = classificar(man_g, "pele", pele, roupa,
                    outro=lambda y, x: "olho" if perto_do_olho[y, x] else "sobrancelha")
eh_roupa = np.zeros(alfa_man.shape, bool)
for c, px in c_man.items():
    if c.startswith("roupa"):
        for y, x in px:
            eh_roupa[y, x] = True
contorno_da_roupa = ndimage.binary_dilation(eh_roupa, iterations=1)
cab, corpo = {}, {}
for c, px in c_man.items():
    for y, x in px:
        vai = corpo if (eh_roupa[y, x] or (c == "contorno" and contorno_da_roupa[y, x] and y > ROUPA_DESDE - 4)) else cab
        vai.setdefault(c, []).append((y, x))
gravar("cabeca", "manequim", svg(grupo("cabeca", cab), grupo("corpo", corpo)))

miolo_do_rosto = (ROWS > sob_ini - 1) & ndimage.binary_erosion(alfa_man & ~eh_roupa, iterations=3) & \
    (COLS > rosto_x0 + 6) & (COLS < rosto_x1 - 6) & (ROWS < ROUPA_DESDE)
REGIOES = {
    "cabelo": ~miolo_do_rosto,
    "barba": (ROWS > olho_fim + 2) & (ROWS < ROUPA_DESDE + 2),
    "oculos": (ROWS >= sob_fim - 1) & (ROWS <= olho_fim + 7),
    "acessorio": ROWS < ROUPA_DESDE,
    "olhos": caixa_olhos,
    "sobrancelhas": caixa_sob,
    "boca": caixa_boca,
    # a boca só até o queixo: a mão do "pensando" fica logo abaixo dela
    "bracos": ~(caixa_olhos | caixa_sob | (caixa_boca & (ROWS < boca_y + 4))),
    "roupa": ROWS >= ROUPA_DESDE - 6,
}
CAMADA = {"cabelo": "cabelo-frente", "barba": "barba", "oculos": "oculos", "acessorio": "acessorio",
          "olhos": "olhos", "sobrancelhas": "sobrancelhas", "boca": "boca", "bracos": "braco-frente",
          "roupa": "corpo"}


# os tons da pele do manequim (a luminância média de cada um): a pele que a boca repinta (onde
# estava o sorriso) usa o tom do manequim mais perto, e não os tons medidos só na boca
TONS_DA_PELE = {c: float(np.mean([lum_man[y, x] for y, x in px])) for c, px in c_man.items() if c.startswith("pele")}


def classes_da_boca(parte):
    """A boca, pixel a pixel, por regras: no Nano Banana o de dentro é um vermelho tão escuro
    (#4c231d) que o corte do contorno pegava, e o dente da risada é cinza-azulado (#d0d5d9).

    - contorno: escuro e sem vermelho (o R abaixo de 48);
    - pele: perto da pele do manequim, no tom do manequim mais perto;
    - dente: claro e quase sem cor;
    - o resto é o vermelho: escuro é o de dentro (boca), claro é a língua."""
    cp = parte[..., :3].astype(np.int16)
    l = lum(cp.astype(np.float32))
    saida = {}
    for y, x in zip(*np.nonzero(parte[..., 3] > 0)):
        c = cp[y, x]
        r, g = int(c[0]), int(c[1])
        if l[y, x] < 52 and (r < 48 or r - g < 25):
            nome = "contorno"
        elif eh_pele(c, pele):
            nome = min(TONS_DA_PELE, key=lambda t: abs(TONS_DA_PELE[t] - l[y, x]))
        elif int(c.min()) > 180 and int(c.max()) - int(c.min()) < 40:
            nome = "dente"
        elif r - g >= 25:
            nome = "boca" if l[y, x] < 80 else "lingua"
        else:
            nome = min(TONS_DA_PELE, key=lambda t: abs(TONS_DA_PELE[t] - l[y, x]))
        saida.setdefault(nome, []).append((int(y), int(x)))
    return _arrumar_boca(saida, cp, l)


def _do_lado_de_dentro(c, l_):
    if int(c.min()) > 170 and int(c.max()) - int(c.min()) < 50:
        return "dente"
    return "boca" if l_ < 80 else "lingua"


def _arrumar_boca(saida, cp, l):
    """Dois consertos que só a forma resolve: a língua rosada (#da7a6e) passa no teste da pele
    (é perto da sombra do nariz), mas está cercada pela boca, então é boca; e um pixel colorido
    solto fora da boca (o brilho rosado do lábio de baixo) é pele."""
    forma = np.zeros(cp.shape[:2], bool)
    for nome in ("contorno", "boca", "lingua", "dente"):
        for y, x in saida.get(nome, []):
            forma[y, x] = True
    cercado = ndimage.binary_fill_holes(forma) & ~forma
    colorido = np.zeros_like(forma)
    for nome in ("boca", "lingua", "dente"):
        for y, x in saida.get(nome, []):
            colorido[y, x] = True
    rot, n = ndimage.label(forma, structure=np.ones((3, 3)))
    maior = 1 + int(np.argmax(ndimage.sum(forma, rot, range(1, n + 1)))) if n else 0
    nova = {}
    for nome, px in saida.items():
        for y, x in px:
            if nome.startswith("pele") and cercado[y, x]:
                nome_ = _do_lado_de_dentro(cp[y, x], l[y, x])
            elif colorido[y, x] and rot[y, x] != maior:
                nome_ = min(TONS_DA_PELE, key=lambda t: abs(TONS_DA_PELE[t] - l[y, x]))
            else:
                nome_ = nome
            nova.setdefault(nome_, []).append((y, x))
    return nova


def grupos_da_boca(classes):
    """A pele que a boca repinta (onde estava o sorriso do manequim) vai na camada da cabeça, por
    baixo da barba; o resto (o contorno, o de dentro, os dentes, a língua) na camada da boca, por
    cima. Assim a boca aberta aparece no meio do bigode, e a pele não pinta por cima dele."""
    pele_ = {c: px for c, px in classes.items() if c.startswith("pele")}
    resto = {c: px for c, px in classes.items() if not c.startswith("pele")}
    return [g for g in (grupo("cabeca", pele_) if pele_ else "", grupo("boca", resto)) if g]


catalogo = []
boca_aberta = None
for arquivo in sorted(GERADO.glob("*.png")):
    if arquivo.stem == "manequim":
        continue
    categoria, nome = arquivo.stem.split("-", 1)
    if SO and categoria not in SO:
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
        # a roupa nova substitui o suéter inteiro: o que é roupa no manequim também entra
        mudou = alfa_ed & (mudou | eh_roupa)
    if categoria == "boca":
        # a boca leva o desenho inteiro dela na caixa, não só o que mudou: a linha da boca
        # neutra que coincide com o sorriso do manequim também é da boca
        cp_ed = ed_g[..., :3].astype(np.int16)
        nao_pele = np.zeros(mudou.shape, bool)
        for y, x in zip(*np.nonzero(caixa_boca & alfa_ed)):
            nao_pele[y, x] = not eh_pele(cp_ed[y, x], pele)
        mudou |= nao_pele
        mudou = ndimage.binary_fill_holes(mudou)
    mudou &= REGIOES[categoria]
    if categoria in ("cabelo", "barba"):
        abaixo = ROWS >= ROUPA_DESDE
        mudou = (mudou & ~abaixo) | ndimage.binary_opening(mudou & abaixo)
    rot, n = ndimage.label(mudou)
    if n:
        minimo = {"bracos": 40, "roupa": 40, "olhos": 2, "boca": 2, "sobrancelhas": 2}.get(categoria, 6)
        tam = ndimage.sum(mudou, rot, range(1, n + 1))
        mudou = np.isin(rot, 1 + np.nonzero(tam >= minimo)[0])
    parte = ed_g.copy()
    parte[~mudou] = 0
    cp = parte[..., :3].astype(np.int16)
    if categoria == "bracos":
        cinza_p = (cp.max(-1) - cp.min(-1)) < 26
        classes = classificar(parte, "roupa", None, None, outro=lambda y, x: "roupa" if cinza_p[y, x] else "pele")
    elif categoria == "roupa":
        claro = lum(cp.astype(np.float32)) > 228
        cinza_p = (cp.max(-1) - cp.min(-1)) < 26
        classes = classificar(parte, "roupa", None, None,
                              outro=lambda y, x: ("roupa2" if claro[y, x] else "roupa") if cinza_p[y, x] else "pele")
    elif categoria in ("cabelo", "barba"):
        classes = classificar(parte, categoria, None, None)
    elif categoria == "boca":
        classes = classes_da_boca(parte)
        if nome == "aberta":
            boca_aberta = classes
    elif categoria == "olhos":
        perto = ndimage.binary_dilation(ed_g[..., :3].min(-1) > 214, iterations=2)
        classes = classificar(parte, "olho", pele, None, outro=lambda y, x: "olho" if perto[y, x] else "sobrancelha")
    elif categoria == "sobrancelhas":
        classes = classificar(parte, "sobrancelha", pele, None)
    elif categoria == "acessorio":
        classes = classificar(parte, "acessorio", pele, None)
    else:
        classes = classificar(parte, categoria, pele, None)
    grupos_ = [grupo(CAMADA[categoria], classes)]
    if categoria == "boca":
        grupos_ = grupos_da_boca(classes)
    if categoria == "bracos":
        apaga = alfa_man & ~alfa_ed & (ROWS > ROUPA_DESDE - 4)
        grupos_.insert(0, grupo("apaga", {"vazio": list(zip(*np.nonzero(apaga)))}))
    estado = categoria in ("olhos", "sobrancelhas", "boca", "bracos")
    gravar(categoria, f"ia.{nome}" if estado else nome, svg(*grupos_))
    catalogo.append({"categoria": categoria, "id": nome, "pixels": int(mudou.sum())})

# a meia boca (sem IA): a aberta com metade da altura, a partir da borda de cima, coluna por
# coluna. Amostrar a aberta achatada deixava a meia ruidosa (cada coluna pegava uma mistura
# diferente de dente, língua e escuro); desenhada, ela é o que um pixel artist faria: o contorno
# em cima e embaixo, uma fileira de dente onde a aberta mostra dente e o escuro no meio. Onde a
# aberta tinha boca e a meia não tem, fica pele, para o sorriso do manequim não aparecer.
if boca_aberta:
    classe = {p: c for c, px in boca_aberta.items() for p in px}
    dentro = {p for p, c in classe.items() if not c.startswith("pele")}
    meia = {}
    colunas = sorted({x for _, x in dentro})
    topos = {x: min(y for y, xx in dentro if xx == x) for x in colunas}
    fins = {x: max(y for y, xx in dentro if xx == x) for x in colunas}
    # uma altura só no miolo (a mediana): a aberta tem o fundo irregular, e a meia achatada dela
    # saía com o contorno de baixo em degraus; só os cantos, mais baixos, ficam com a deles
    alturas = {x: max(2, int(np.ceil((fins[x] - topos[x] + 1) * 0.5))) for x in colunas}
    altura_do_miolo = int(np.median([alturas[x] for x in colunas[2:-2]] or list(alturas.values())))
    for x in colunas:
        topo = topos[x]
        nova = min(alturas[x], altura_do_miolo)
        # o contorno de cima desce até o topo das vizinhas: a linha não fica furada
        ate = max([topo] + [topos[v] for v in (x - 1, x + 1) if v in topos])
        miolo = colunas[0] + 1 < x < colunas[-1] - 1
        for y in range(topo, topo + nova):
            if y <= ate or y == topo + nova - 1:
                nome = "contorno"
            elif y == ate + 1 and miolo and y < topo + nova - 2:
                nome = "dente"
            else:
                nome = "boca"
            meia.setdefault(nome, []).append((y, x))
    tem = {p for px in meia.values() for p in px}
    for p_, c in classe.items():
        if c.startswith("pele"):
            meia.setdefault("pele", []).append(p_)
        elif p_ not in tem:
            meia.setdefault("pele", []).append(p_)
    gravar("boca", "ia.meia", svg(*grupos_da_boca(meia)))

if not SO:
  (PARTES / "extracao.json").write_text(json.dumps({
    "geometria": {"topo": TOPO, "largura": LARGURA, "fase": f},
    "marcos": {"topo": topo_g, "sobrancelha": [sob_ini, sob_fim], "olhos": [olho_ini, olho_fim], "boca": boca_y,
               "roupa_desde": ROUPA_DESDE, "rosto_x": [rosto_x0, rosto_x1]},
    "partes": catalogo}, indent=1))
