"""As cabeças dos bichos viram partes (o pedido do dono de 21/10/2026: "criação dos personagens para
animais também").

Cada bicho nasceu de uma edição do manequim no Nano Banana 2 (só a cabeça trocada, com a folha do
dono como referência de estilo). Daqui sai ``cabeca/<bicho>.svg``: a cabeça do bicho no grupo
``cabeca``, e o pescoço e o corpo do manequim de sempre (a roupa escolhida continua cobrindo o
corpo).

- **A pelagem** é o espaço "pele", em até quatro tons: a cor escolhida pinta o bicho, o pescoço e as
  mãos das poses (nada de mão de gente num cachorro). No panda, a pelagem é o branco.
- **O preto** é contorno (as manchas do panda também); **o branco** (o focinho da raposa) e **o
  rosa** (a orelha por dentro, o nariz do coelho) ficam fixos.
- **Os olhos e a boca saem**: o ``desenhar_bichos.py`` desenha os seis olhares e as seis bocas no
  lugar medido aqui, que vai para ``bichos.json``. Os olhos são achados pelo brilho branco deles; a
  boca, logo abaixo do nariz.

    uv run --with numpy --with pillow --with scipy python extrair_bichos.py GERADO ../partes SAIDA [bicho...]

``GERADO`` tem as imagens do ``gerar_bichos.py`` e o ``manequim.png`` (que ele copia para lá);
``../partes`` dá o pescoço e o corpo do manequim e o queixo dele (``extracao.json``).
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

PILOTO = Path(__file__).resolve().parent
sys.path.insert(0, str(PILOTO))
import pixels  # noqa: E402

_fonte = (PILOTO / "extrair.py").read_text()
exec(_fonte[_fonte.index("GERADO, PARTES"):_fonte.index("# ── as partes")].replace(
    "GERADO, PARTES = Path(sys.argv[1]), Path(sys.argv[2])", ""))

GERADO, PARTES_V7, SAIDA = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
ROWS = np.arange(GRADE)[:, None]
COLS = np.arange(GRADE)[None, :]

man = recortar(GERADO / "manequim.png")
geo = cabeca(man[..., 3] > 0)
f = fase(para_o_quadro(man, geo))
man_g = na_grade(para_o_quadro(man, geo), f)
alfa_man = man_g[..., 3] > 0
H = man.shape[0]
# o pescoço e o corpo do manequim de hoje (depois do capsula.py), e o queixo dele
grupos_man = {c: (e, g) for c, e, g in pixels.ler(PARTES_V7 / "cabeca" / "manequim.svg")}
QUEIXO = json.loads((PARTES_V7 / "extracao.json").read_text())["marcos"]["queixo"]
CENTRO_X = 75
#: Os bichos de bico: o bico é a boca (abre no meio), e não há boca abaixo dele.
BICO = {"pato", "galinha", "pinguim"}
#: Sem nariz para achar: a boca do elefante fica no alto das presas, ao lado da tromba.
SEM_NARIZ = {"elefante"}
DEPURAR_OLHO = False


def vizinhos_de(m: np.ndarray) -> np.ndarray:
    return ndimage.binary_dilation(m, iterations=1) & ~m


def tapar(g: np.ndarray, buraco: np.ndarray, contorno_vale: bool, so_pelo: bool = False) -> None:
    """Cada pixel do buraco pega a classe do pixel de fora mais perto dele: a pelagem continua a
    de volta, com os tons dela, em regiões de borda limpa (o preenchimento pela maioria dos
    vizinhos, de fora para dentro, deixava riscos em xadrez na diagonal: o branco da máscara do
    lobo, o âmbar do olho do gato). O contorno só vale quando ``contorno_vale`` (a mancha preta do
    panda). Com ``so_pelo``, só a pelagem vale, quando há (o rosa em volta do olho do gato descia
    em riscos pelo buraco inteiro)."""
    fonte = ~buraco & (g != "")
    if not contorno_vale:
        fonte &= g != "contorno"
    if so_pelo:
        pelo_ = fonte & np.vectorize(lambda c: c.startswith("pele"))(g)
        if pelo_.any():
            fonte = pelo_
    if not fonte.any():
        return
    _d, (iy, ix) = ndimage.distance_transform_edt(~fonte, return_indices=True)
    ys, xs = np.nonzero(buraco)
    g[ys, xs] = g[iy[ys, xs], ix[ys, xs]]


def extrair(nome: str) -> dict:
    ed = recortar(GERADO / f"{nome}.png")
    estavel = np.zeros(ed.shape[:2], bool)
    estavel[int(H * 0.82):] = True                   # a barra do suéter não muda
    ed = alinhar(ed, man, estavel & (man[..., 3] > 0))
    ed_g = na_grade(para_o_quadro(ed, geo), f)
    rgb = ed_g[..., :3].astype(np.int16)
    # o fundo preso entre a orelha comprida e o pescoço não encosta na borda da imagem, e o
    # recortar não tira: o magenta (e o rosado da mistura) sai, e com ele o branco do adesivo
    # que cresce a partir dele
    r_, g_, b_ = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    preso = ((r_ > 160) & (b_ > 160) & (g_ < 120)) | ((r_ > 200) & (b_ > 190) & (g_ < r_ - 25) & (np.abs(r_ - b_) < 45))
    branco_ = (rgb.min(-1) > 205) & ((rgb.max(-1) - rgb.min(-1)) < 40)
    borda_ = ndimage.binary_dilation(preso) & branco_
    while borda_.any():
        preso |= borda_
        borda_ = ndimage.binary_dilation(borda_) & branco_ & ~preso
    ed_g[preso, 3] = 0
    alfa = ed_g[..., 3] > 0
    dif = np.abs(rgb - man_g[..., :3].astype(np.int16)).sum(-1)
    mudou = alfa & (~alfa_man | (dif > 70))
    # a cabeça: tudo até o queixo do manequim, e o que mudou abaixo dele ligado a isso (as
    # orelhas compridas do cachorro)
    candidato = alfa & ((ROWS <= QUEIXO) | mudou)
    rot, n = ndimage.label(candidato)
    cab = np.isin(rot, [k for k in range(1, n + 1) if (rot[:QUEIXO + 1] == k).any()])
    cab &= (ROWS <= QUEIXO) | ndimage.binary_opening(mudou)
    l = lum(rgb.astype(np.float32))
    sat = rgb.max(-1) - rgb.min(-1)
    preto = cab & (l < 52)
    branco = cab & (rgb.min(-1) > 214) & (sat < 30)
    cor = cab & ~preto & ~branco
    cinza = cor & (sat < 48)                          # quase sem cor: o cinza, o creme, a sombra
    matiz = np.degrees(np.arctan2(np.sqrt(3) * (rgb[..., 1] - rgb[..., 2]),
                                  2 * rgb[..., 0] - rgb[..., 1] - rgb[..., 2])) % 360
    colorido = cor & ~cinza
    # a pelagem é o maior dos grupos: o branco (o panda, o pato), o cinza (o lobo, a ovelha) ou a
    # cor principal com a vizinhança dela (a raposa, o porco, o sapo)
    if colorido.any():
        hist = np.bincount((matiz[colorido] // 10).astype(int) % 36, minlength=36)
        pico = (int(np.argmax(np.convolve(np.r_[hist[-1], hist, hist[0]], [1, 1, 1], "valid"))) * 10 + 5) % 360
        perto_do_pico = colorido & (np.minimum(np.abs(matiz - pico), 360 - np.abs(matiz - pico)) <= 35)
    else:
        perto_do_pico = colorido
    grupos_ = {"branco": branco.sum(), "cinza": cinza.sum(), "cor": perto_do_pico.sum()}
    qual = max(grupos_, key=grupos_.get)
    if qual == "branco":
        pelo = branco | cinza
        branco = np.zeros_like(branco)
    elif qual == "cinza":
        pelo = cinza
        # um cinza puxado para a cor principal (o gato rajado, marrom-acinzentado) leva os tons
        # claros dela: o focinho creme é pelagem, o rosa forte da orelha não; num cinza frio (o
        # lobo), o rosa claro da orelha é rosa mesmo
        # (puxado mesmo: no gato, 85% do cinza tem um pouco de cor; na vaca preta e branca, 2%, e o
        # rosa do focinho dela ia virar pelagem)
        tinto = cinza & (sat >= 15)
        if tinto.sum() >= 0.5 * cinza.sum() and colorido.any():
            rad = np.radians(matiz[tinto])
            tom = np.degrees(np.arctan2(np.sin(rad).mean(), np.cos(rad).mean())) % 360
            if min(abs(tom - pico), 360 - abs(tom - pico)) <= 35:
                pelo = cinza | perto_do_pico & (sat <= 80)

    else:
        pelo = perto_do_pico | cinza
    # o resto que tem cor (o bico, a crista, o chifre, o rosa da orelha) é cor fixa: até quatro
    fixa = cor & ~pelo
    g = np.full((GRADE, GRADE), "", dtype=object)
    ys, xs = np.nonzero(pelo)
    picos, base = tons_de(l[ys, xs])
    perto = np.abs(l[ys, xs][:, None] - picos[None, :]).argmin(axis=1)
    for y, x, i in zip(ys, xs, perto):
        d = int(i) - base
        g[y, x] = "pele" if d == 0 else "pele-luz" if d > 0 else "pele-sombra" if d == -1 else "pele-sombra2"
    g[preto] = "contorno"
    g[branco] = "branco"
    if fixa.any():
        px = rgb[fixa].astype(float)
        k = min(4, len(np.unique(px // 24, axis=0)))
        centros = [px[0]]
        while len(centros) < k:                     # os mais longe uns dos outros, para começar
            d = np.min([((px - c) ** 2).sum(-1) for c in centros], axis=0)
            centros.append(px[int(np.argmax(d))])
        centros = np.array(centros)
        for _ in range(12):
            perto_c = np.argmin(((px[:, None] - centros[None]) ** 2).sum(-1), axis=1)
            centros = np.array([px[perto_c == j].mean(0) if (perto_c == j).any() else centros[j] for j in range(k)])
        for (y, x), j in zip(zip(*np.nonzero(fixa)), perto_c):
            g[y, x] = "fixa-{:02x}{:02x}{:02x}".format(*[int(round(v)) for v in centros[j]])
    eh_fixa = np.vectorize(lambda c: c.startswith("fixa-"))(g)
    # o pescoço de gente que a IA deixou logo acima do queixo do manequim (o rosa do gato, do lobo,
    # da vaca): é pelagem, senão, com outra cor, sobrava uma faixa de pele humana sob a cabeça
    _e, pesc = grupos_man["pescoco"]
    cols_pesc = np.nonzero((pesc != "").any(axis=0))[0]
    quente = (rgb[..., 0] >= rgb[..., 1]) & (rgb[..., 0] - rgb[..., 2] >= 40)
    humano = eh_fixa & quente & (ROWS >= QUEIXO - 4) & (COLS >= cols_pesc.min() - 2) & (COLS <= cols_pesc.max() + 2)
    for y, x in zip(*np.nonzero(humano)):
        d = int(np.abs(picos - l[y, x]).argmin()) - base
        g[y, x] = "pele" if d == 0 else "pele-luz" if d > 0 else "pele-sombra" if d == -1 else "pele-sombra2"
    eh_fixa &= ~humano

    # ── os olhos: o brilho branco, um em cada lado, na mesma altura ─────────
    claro = cab & (rgb.min(-1) > 200) & (sat < 45)
    rot, n = ndimage.label(claro)
    brilhos = []
    for k in range(1, n + 1):
        py, px = np.nonzero(rot == k)
        if len(py) > 8:
            continue
        cy, cx = py.mean(), px.mean()
        anel = vizinhos_de(rot == k)
        escuro_em_volta = (l[anel] < 110).mean()
        if escuro_em_volta >= 0.5:                   # um brilho dentro de algo escuro: o olho
            brilhos.append((cy, cx, len(py)))
    # um de cada lado, a 6 a 20 colunas do meio (no meio é o nariz; mais longe, a orelha por
    # dentro, que também é branco em volta de escuro), na mesma altura
    def par(pontos, longe: int):
        lado = lambda b: 6 <= abs(b[1] - CENTRO_X) <= longe  # noqa: E731
        return [(a, b) for a in pontos for b in pontos
                if a[1] < CENTRO_X < b[1] and lado(a) and lado(b) and abs(a[0] - b[0]) <= 2
                and abs((CENTRO_X - a[1]) - (b[1] - CENTRO_X)) <= 4]

    # o sapo tem os olhos saltados para os lados: até 24 colunas, se até 20 não deu
    pares = par(brilhos, 20) or par(brilhos, 24)
    if DEPURAR_OLHO:
        print(f"  {nome}: brilhos {[(round(a), round(b), t) for a, b, t in brilhos]}")
    if not pares:
        # sem o brilho nos dois (o leão, o pinguim): os pedaços escuros do tamanho de um olho,
        # um de cada lado, na mesma altura; o "brilho" fica no alto à esquerda de cada um
        rot_e, n_e = ndimage.label(cab & (l < 90) & (g == "contorno") | cab & (l < 70))
        manchas = []
        for k in range(1, n_e + 1):
            py, px = np.nonzero(rot_e == k)
            alto_, largo_ = py.max() - py.min() + 1, px.max() - px.min() + 1
            if 6 <= len(py) <= 70 and 3 <= alto_ <= 11 and 3 <= largo_ <= 11:
                manchas.append((float(py.mean()), float(px.mean()), len(py)))   # o centro do pedaço
        pares = par(manchas, 22)
    if not pares:
        raise SystemExit(f"{nome}: não achei os dois olhos (brilhos {[(round(a), round(b)) for a, b, _ in brilhos]})")
    esq, dir_ = min(pares, key=lambda p: abs(p[0][0] - p[1][0]) + abs((CENTRO_X - p[0][1]) - (p[1][1] - CENTRO_X)))
    olhos = []
    for cy, cx, _ in (esq, dir_):
        # o olho: o escuro ligado ao brilho, numa caixa de até 13 × 11 em volta dele (com 9 × 9, o
        # canto de fora do olho do cachorro, um traço de delineador, ficava ao lado do "^")
        # (desce mais do que sobe: o brilho fica no alto do olho, e com a caixa no meio dele a borda
        # de baixo do olho do porco, da galinha e do elefante ficava como um risco)
        caixa = (ROWS - cy >= -5.5) & (ROWS - cy <= 7.5) & (np.abs(COLS - cx) <= 6.5)
        # só o escuro e o brilho dele: com o claro todo, o olho do pato era a caixa inteira (a
        # plumagem branca), e o tapa-buraco apagava o que estava em volta
        # (os brilhos pequenos da caixa toda: a ovelha tem um segundo, embaixo)
        rot_cl, _n = ndimage.label(claro)
        pequenos = [j for j in np.unique(rot_cl[claro & caixa])
                    if j and (rot_cl == j).sum() <= 8]
        brilho_aqui = np.isin(rot_cl, pequenos) | claro & (np.abs(ROWS - cy) <= 2) & (np.abs(COLS - cx) <= 2)
        escuro = cab & caixa & ((l < 110) | brilho_aqui)
        rot, _n = ndimage.label(escuro)
        k = rot[int(round(cy)), int(round(cx))] or np.bincount(rot[caixa & (rot > 0)]).argmax()
        olho = rot == k
        # (com a íris colorida ligada a ele, na caixa: o âmbar do olho do gato ficava em volta)
        rot_i, _n = ndimage.label(olho | eh_fixa & caixa & cab, structure=np.ones((3, 3)))
        olho |= np.isin(rot_i, np.unique(rot_i[olho])) & eh_fixa
        # o olho dentro de uma mancha (o panda): o escuro em volta é bem maior que um olho, e é
        # a mancha. Só o brilho sai (vira a mancha), e o olho desenhado vai por cima dela
        # (só o preto de verdade: com o claro junto, o branco do pato inteiro se ligava ao olho, e o
        # cinza-escuro das listras do gato também)
        # (sem os traços finos: o contorno da cabeça encosta no olho da girafa e contava como mancha)
        inteiro, _n = ndimage.label(ndimage.binary_opening(cab & (l < 60)))
        pretos = inteiro[olho & (l < 60)]
        k_ = int(np.bincount(pretos).argmax()) if len(pretos) else 0
        # a mancha passa da caixa do olho (o panda, a máscara do guaxinim); o olho, não
        fora_da_caixa = int(((inteiro == k_) & ~caixa).sum()) if k_ else 0
        if DEPURAR_OLHO:
            print(f"  {nome}: olho {int(olho.sum())} px, preto fora da caixa {fora_da_caixa} px")
        # (80: o olho grande da girafa passa uns 45 da caixa; a mancha do panda, mais de 130)
        if fora_da_caixa >= 80:
            brilho = olho & claro
            g[brilho] = "contorno"
            oy, ox = np.nonzero(olho)
            olhos.append({"caixa": [int(oy.min()), int(ox.min()), int(oy.max()), int(ox.max())],
                          "brilho": [round(float(cy), 1), round(float(cx), 1)], "em_volta": "contorno"})
            continue
        oy, ox = np.nonzero(olho)
        y0, y1, x0, x1 = int(oy.min()), int(oy.max()), int(ox.min()), int(ox.max())
        # a cor de volta do olho (a pelagem; no panda, a mancha preta)
        anel = vizinhos_de(olho) & cab & ~olho
        em_volta = [g[y, x] for y, x in zip(*np.nonzero(anel))]
        sem_contorno = [c for c in em_volta if c != "contorno"]
        # o contorno grosso do olho do gato não é o fundo dele: só no panda (a mancha preta) o
        # preto em volta é a cor de fundo
        fundo = "contorno" if len(sem_contorno) < 0.25 * len(em_volta) else max(set(sem_contorno), key=sem_contorno.count)
        if fundo != "contorno":
            # a órbita mais escura em volta do olho gerado ficava como um fantasma quando o olho
            # fecha (o "^" da risada): sai um pixel a mais
            olho = ndimage.binary_dilation(olho) & cab & (g != "contorno") | olho
        tapar(g, olho, fundo == "contorno", so_pelo=fundo.startswith("pele"))
        olhos.append({"caixa": [y0, x0, y1, x1], "brilho": [round(float(cy), 1), round(float(cx), 1)], "em_volta": fundo})

    # ── o nariz e a boca ──────────────────────────────────────────────────
    baixo_dos_olhos = max(o["caixa"][2] for o in olhos)
    em_volta_da_boca = "pele"
    if nome in BICO:
        # o bico é a boca: ele abre no meio (desenhar_bichos.py), e nada sai daqui (a crista e a
        # barbela da galinha também são cor fixa, logo abaixo dele)
        meio = (np.abs(COLS - CENTRO_X) <= 8) & (ROWS > baixo_dos_olhos) & (ROWS <= baixo_dos_olhos + 16)
        rot, n = ndimage.label(cab & meio & eh_fixa)
        if not n:
            raise SystemExit(f"{nome}: não achei o bico")
        k = int(np.argmax(ndimage.sum(np.ones_like(rot), rot, range(1, n + 1)))) + 1
        semente = rot == k
        # a cor do bico é a do alto da semente (a barbela vermelha da galinha fica embaixo dele), e
        # as cores perto dela (a sombra do bico) vêm junto
        sy = np.nonzero(semente)[0]
        alto_ = semente & (ROWS <= sy.min() + 1)
        cores_ = [g[y, x] for y, x in zip(*np.nonzero(alto_))]
        cor_do_bico = max(set(cores_), key=cores_.count)
        ref = np.array([int(cor_do_bico[5 + i:7 + i], 16) for i in (0, 2, 4)])
        parecidas = {c for c in set(g[cab & eh_fixa])
                     if np.abs(np.array([int(c[5 + i:7 + i], 16) for i in (0, 2, 4)]) - ref).sum() < 90}
        rot_, _n = ndimage.label(cab & np.isin(g, list(parecidas)))
        bico = np.isin(rot_, np.unique(rot_[semente & np.isin(g, list(parecidas))]))
        by, bx = np.nonzero(bico)
        nariz_caixa = [int(by.min()), int(bx.min()), int(by.max()), int(bx.max())]
        boca_y = int(by.min() + (by.max() - by.min()) // 2)
        cx_nariz = float((bx.min() + bx.max()) / 2)
        extra_ = {"bico": True, "bico_largura": int(bx.max() - bx.min() + 1)}
    else:
        nariz_cand = None
        meio_ = lambda alcance: ((np.abs(COLS - CENTRO_X) <= 6) & (ROWS > baixo_dos_olhos)  # noqa: E731
                                 & (ROWS <= baixo_dos_olhos + alcance))
        rosado = (rgb[..., 0] > rgb[..., 1] + 35) & (rgb[..., 2] >= rgb[..., 1] - 12) & (l > 90)
        # o escuro (pela luminância: o nariz da ovelha é marrom); longe (o cavalo); o rosa (o coelho);
        # a cor fixa (o focinho da vaca)
        for cand in (meio_(16) & (l < 90), meio_(26) & (l < 90), meio_(16) & rosado, meio_(16) & eh_fixa):
            # o nariz não é a pelagem (a mancha preta da vaca É a pelagem dela; o tom mais escuro
            # vale, que o nariz marrom da ovelha cai nele)
            rot_c, n_c = ndimage.label(cab & cand & ~np.isin(g, ["pele", "pele-luz", "pele-sombra"]))
            # um pixel solto (o fim do olho da lontra) não é nariz, nem uma linha que atravessa a
            # janela (a borda de cima do focinho da vaca)
            def serve(k):
                ys_, xs_ = np.nonzero(rot_c == k)
                linha = xs_.max() - xs_.min() >= 11 and ys_.max() - ys_.min() <= 1
                return len(ys_) >= 3 and not linha
            cand = np.isin(rot_c, [k for k in range(1, n_c + 1) if serve(k)])
            if cand.any():
                nariz_cand = cand
                break
        if nariz_cand is None and nome not in SEM_NARIZ:
            raise SystemExit(f"{nome}: não achei o nariz")
    if nome in SEM_NARIZ:
        # a boca no alto das presas (o branco dos lados da tromba), no meio
        presas = cab & (l > 190) & (np.abs(COLS - CENTRO_X) <= 16) & (ROWS > baixo_dos_olhos + 4)
        if not presas.any():
            raise SystemExit(f"{nome}: não achei as presas")
        boca_y = int(np.nonzero(presas)[0].min()) + 1
        cx_nariz = float(CENTRO_X)
        nariz_caixa = [boca_y - 1, CENTRO_X - 1, boca_y - 1, CENTRO_X + 1]
        extra_ = {"sem_nariz": True}
    elif nome not in BICO:
        rot, n = ndimage.label(nariz_cand)
        # o do meio primeiro (no leão, um fio escuro da juba ficava mais acima), depois o mais alto;
        # "do meio" conta com os vizinhos da mesma altura: as narinas do porco e do sapo, cada uma
        # de um lado, têm o meio entre elas
        def centro_da_faixa(k):
            ys_ = np.nonzero(rot == k)[0]
            junto = np.isin(rot, [j for j in range(1, n + 1)
                                  if ((rot == j) & (ROWS >= ys_.min()) & (ROWS <= ys_.max())).any()])
            return abs(np.nonzero(junto)[1].mean() - CENTRO_X)
        k = min(range(1, n + 1), key=lambda k: (centro_da_faixa(k) > 3, np.nonzero(rot == k)[0].min()))
        ny, nx = np.nonzero(rot == k)
        # o nariz vai de cima até a primeira linha que afina (1 ou 2 pixels): dali para baixo é o
        # risco que desce até a boca (no panda, ligado ao "w" dela)
        larguras = [int((ny == y).sum()) for y in range(int(ny.min()), int(ny.max()) + 1)]
        fim_do_nariz = int(ny.min())
        for i, w in enumerate(larguras):
            if w <= 2 and i >= 2:
                break
            fim_do_nariz = int(ny.min()) + i
        nariz = (rot == k) & (ROWS <= fim_do_nariz)
        # as narinas (a vaca, o porco): os pedaços na mesma faixa de linhas do primeiro
        faixa = (ROWS >= ny.min()) & (ROWS <= fim_do_nariz)
        for j in range(1, n + 1):
            if j != k and ((rot == j) & faixa).any():
                nariz |= (rot == j) & faixa
        cx_nariz = float(np.nonzero(nariz)[1].mean())
        # a boca de verdade: o risco escuro abaixo do nariz (até 12 linhas, a até 12 colunas do
        # meio), inteiro (o sorriso largo do sapo), que não fecha uma área (a borda do focinho
        # do porco fecha) nem encosta na borda da cabeça (o queixo da lontra)
        # (até 9 linhas: a boca larga do sapo fica a 7; o risco do pescoço do coelho, a 11)
        zona = (ROWS > fim_do_nariz) & (ROWS <= fim_do_nariz + 9) & (np.abs(COLS - cx_nariz) <= 12)
        fora = ndimage.binary_dilation(~cab)
        boca = np.zeros_like(cab)
        largo = False
        # o escuro e o rosa (a boca do coelho é rosa, o "w" do gato é marrom); sem nada, só o preto
        # (no porco, o marrom do focinho liga o sorriso ao contorno da cabeça inteira)
        for escuro_todo in (cab & ((l < 95) | rosado) & ~nariz, cab & (l < 60) & ~nariz):
            rot_b, n_b = ndimage.label(escuro_todo, structure=np.ones((3, 3)))
            pedacos = []
            for j in np.unique(rot_b[zona & escuro_todo]):
                pedaco = rot_b == j
                fecha = ndimage.binary_fill_holes(pedaco).sum() - pedaco.sum() >= 4
                if DEPURAR_OLHO:
                    ys_, xs_ = np.nonzero(pedaco)
                    print(f"  {nome} boca? {int(pedaco.sum())} px linhas {ys_.min()}-{ys_.max()} "
                          f"colunas {xs_.min()}-{xs_.max()} fecha {fecha} fora {bool((pedaco & fora).any())}")
                if not fecha and not (pedaco & fora).any() and pedaco.sum() <= 160:
                    boca |= pedaco
            if boca.any():
                break
        if boca.any():
            by_, bx_ = np.nonzero(boca)
            # um sorriso de bochecha a bochecha (o sapo, o porco): fica, e só o meio dele vira a
            # boca desenhada, que continua a linha dele (a linha de cima da boca é o risquinho)
            # (de 30 colunas: o porco e o sapo têm 35; o cachorro, 26, e a boca dele sai inteira)
            largo = bx_.max() - bx_.min() + 1 >= 30
            if largo:
                no_meio = boca & (np.abs(COLS - cx_nariz) <= 2)
                linha = int(np.nonzero(no_meio)[0].min()) if no_meio.any() else int(by_.min())
                # (da linha para baixo: as pontas das narinas do sapo, logo acima, ficam)
                boca &= (np.abs(COLS - cx_nariz) <= 4) & (ROWS >= linha - 2)
                boca_y = linha - 1
            else:
                boca &= ROWS <= by_.min() + 5                # só a boca, não o risco do queixo abaixo
                boca_y = int(np.nonzero(boca)[0].min())
                bx_ = np.nonzero(boca)[1]
                if abs((bx_.min() + bx_.max()) / 2 - cx_nariz) <= 2:
                    cx_nariz = float((bx_.min() + bx_.max()) / 2)
        else:
            boca_y = fim_do_nariz + 1
        anel = vizinhos_de(boca) & cab & ~boca & (g != "contorno")
        em_volta = [g[y, x] for y, x in zip(*np.nonzero(anel))] or ["pele"]
        em_volta_da_boca = max(set(em_volta), key=em_volta.count)
        tapar(g, boca, False)
        nz = np.nonzero(nariz)
        nariz_caixa = [int(nz[0].min()), int(nz[1].min()), fim_do_nariz, int(nz[1].max())]
        extra_ = {"sorriso_largo": True} if largo else {}

    cabeca_g = g.copy()
    cabeca_g[~cab] = ""
    grupos_ = [("cabeca", "", cabeca_g)]
    for c in ("pescoco", "corpo"):
        extra, gg = grupos_man[c]
        grupos_.append((c, extra, gg))
    (SAIDA / "cabeca").mkdir(parents=True, exist_ok=True)
    pixels.escrever(SAIDA / "cabeca" / f"{nome}.svg", grupos_)
    return {"olhos": olhos, "nariz": nariz_caixa, "boca_y": boca_y, "centro_x": round(cx_nariz, 1),
            "focinho": em_volta_da_boca, "pelagem": qual, **extra_,
            "cor": "#{:02x}{:02x}{:02x}".format(*[int(v) for v in np.median(rgb[pelo & (g == "pele")], axis=0)]),
            "pixels": int(cab.sum())}


CORES_DEPURAR = {"contorno": (20, 20, 20), "branco": (255, 255, 255), "lingua": (230, 120, 150),
                 "pele": (210, 160, 90), "pele-luz": (240, 210, 150), "pele-sombra": (170, 120, 60),
                 "pele-sombra2": (120, 80, 40)}


def depurar(nome: str, m: dict) -> Image.Image:
    """A cabeça em classes, com os olhos (azul), o nariz (verde) e a linha da boca (vermelho)."""
    g = next(gg for c, _e, gg in pixels.ler(SAIDA / "cabeca" / f"{nome}.svg") if c == "cabeca")
    im = np.full((GRADE, GRADE, 3), 200, np.uint8)
    for (y, x), c in np.ndenumerate(g):
        if c:
            im[y, x] = CORES_DEPURAR.get(c) or (tuple(int(c[5 + i:7 + i], 16) for i in (0, 2, 4))
                                                 if c.startswith("fixa-") else (255, 0, 255))
    for o in m["olhos"]:
        y0, x0, y1, x1 = o["caixa"]
        im[y0:y1 + 1, [x0, x1]] = (40, 90, 255)
        im[[y0, y1], x0:x1 + 1] = (40, 90, 255)
    y0, x0, y1, x1 = m["nariz"]
    im[y0:y1 + 1, [x0, x1]] = (0, 200, 0)
    im[m["boca_y"], int(m["centro_x"]) - 6:int(m["centro_x"]) + 7] = (255, 0, 0)
    return Image.fromarray(im[0:100, 25:125]).resize((400, 400), Image.NEAREST)


TODOS = ("cachorro", "gato", "raposa", "panda", "coelho", "ovelha", "pato", "girafa", "elefante", "urso", "leao",
         "lobo", "pinguim", "porco", "vaca", "galinha", "sapo", "cavalo", "lontra", "guaxinim")
marcos = {}
for nome in sys.argv[4:] or TODOS:
    try:
        marcos[nome] = extrair(nome)
    except SystemExit as erro:
        print("FALHOU", erro)
colunas = min(5, len(marcos))
folha = Image.new("RGB", (410 * colunas, 410 * ((len(marcos) + colunas - 1) // colunas)), "white")
for i, (nome, m) in enumerate(marcos.items()):
    folha.paste(depurar(nome, m), ((i % colunas) * 410, (i // colunas) * 410))
folha.save(SAIDA / "depurar.png")
(SAIDA / "bichos.json").write_text(json.dumps(marcos, indent=1, ensure_ascii=False))
for nome, m in marcos.items():
    print(nome, "olhos", [o["caixa"] for o in m["olhos"]], "nariz", m["nariz"], "boca", m["boca_y"],
          "pelagem", m["cor"], "focinho", m["focinho"])
