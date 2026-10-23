"""A cabeça em cápsula, como o exemplo do dono (20/10/2026): o alto da cabeça com a largura do rosto
na altura das orelhas, os lados retos dos olhos às orelhas, e daí para baixo o rosto de sempre (o
maxilar e o queixo, que o dono aprovou).

O manequim gerado tinha o alto da cabeça bem mais largo que o resto (52 px na grade, contra 42 no
rosto atrás das orelhas e 39 no maxilar): uma lâmpada. Na primeira tentativa, o rosto de baixo
foi alargado até o alto, e o queixo ficou quadrado ("antes estava bom já"). Aqui é o contrário: o
alto encolhe, e o queixo não muda. A largura nova é a em que os olhos ocupam a mesma fração do
rosto que no exemplo do dono (uns 77%; no manequim, eram 63%): 44 px na grade.

Na grade de 150, sobre as partes já vetorizadas, linha a linha:

- **a cabeça do manequim:** a cúpula é estreitada em volta do centro, e dela até a orelha os
  lados ficam retos, na largura nova. O contorno, a sombra de dentro dele e o brilho andam para
  dentro, e a pele que sobra sai;
- **os cabelos e os acessórios** (o boné, o gorro, o fone) andam o mesmo tanto, para continuarem
  no alto da cabeça.

Depois, os pedidos de 21/10/2026:

- **a testa mais curta** (:func:`tirar_linhas`): o alto da cabeça desce ``TESTA_MENOS`` linhas,
  mais perto da sobrancelha. A cabeça, os cabelos e o fone perdem as mesmas linhas, logo acima
  da sobrancelha (onde os lados são retos e eles continuam alinhados); os chapéus perdem linhas
  da copa, para a aba ficar inteira;
- **a cúpula lisa** (:func:`alisar_cupula`): estreitar linha a linha deixou a borda amassada.
  Ela é redesenhada por uma superelipse, um pouco menos redonda que a borda de antes, em degraus
  limpos (:func:`curva_limpa`);
- **os cabelos e os chapéus encostando nela** (:func:`encostar_no_contorno`,
  :func:`vestir_chapeu`): eles não têm contorno em cima, usam o da cabeça;
- **os furos do cabelo tapados** (:func:`tapar_buracos`): pixels que a extração achou iguais ao
  manequim caíam na sombra marrom da cabeça antiga; na nova, mostravam pele dentro do cabelo.

    python capsula.py PARTES_ENTRADA PARTES_SAIDA
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
from scipy import ndimage

import pixels

#: A fração da largura do rosto que os olhos ocupam (no exemplo do dono, uns 77%; no manequim
#: gerado, com o alto de 52 px, 63%).
OLHOS_NA_LARGURA = 0.78
#: As categorias que acompanham a cabeça nova.
ACOMPANHAM = ("cabelo", "barba", "acessorio")
#: A testa: o ponto de onde a pele do rosto é achada.
TESTA = (20, 76)
#: Os pixels de pele logo dentro do contorno que andam junto com ele (a sombra do rosto e o
#: brilho da careca, que fica perto da borda).
FAIXA_DA_CABECA = 8
#: Nas partes de cima, os pixels logo dentro da borda que andam junto (a borda do cabelo).
FAIXA = 3
#: O formato da cúpula redesenhada (o expoente da superelipse; None: o que mais se parece com a
#: borda de antes, 1,85, um ovo). O dono pediu "um pouquinho menos arredondado" em 21/10/2026.
EXPOENTE_DA_CUPULA: float | None = 2.2
#: Quantas linhas a testa perde: o alto da cabeça desce, mais perto da sobrancelha. No exemplo do
#: dono, da sobrancelha ao alto é 0,49 da largura da cabeça; aqui era 0,59 (pedido de 21/10/2026).
TESTA_MENOS = 4
#: Os chapéus (a aba não pode perder linha: eles perdem da copa).
CHAPEUS = ("bone", "gorro")


def _uniao(grupos: list[tuple[str, str, np.ndarray]]) -> np.ndarray:
    u = pixels.vazia()
    for _c, _e, g in grupos:
        u = np.where(g != "", g, u)
    return u


def eh_pele(g: np.ndarray) -> np.ndarray:
    return np.vectorize(lambda c: c.startswith("pele"))(g)


class Molde:
    """A linha do rosto antiga, linha a linha, e quanto ela anda para dentro em cada lado."""

    def __init__(self, cabeca: np.ndarray, silhueta: np.ndarray):
        pele = eh_pele(cabeca)
        rot, _n = ndimage.label(pele)
        rosto = rot == rot[TESTA]
        linhas = [int(y) for y in np.nonzero(rosto.any(axis=1))[0]]
        self.topo, self.queixo = linhas[0], linhas[-1] + 1
        contorno = cabeca == "contorno"
        pele_fora = eh_pele(silhueta) & ~rosto
        # acima da orelha, a linha do rosto é a borda da pele dele; a orelha começa na primeira linha
        # com pele fora do rosto (a esquerda é um pedaço solto: a borda dela não engana)
        self.esq, self.dir = {}, {}
        orelha_ini = self.queixo
        for y in range(self.topo, self.queixo):
            xs = np.nonzero(rosto[y])[0]
            if pele_fora[y, :xs[0]].any():
                orelha_ini = y
                break
            self.esq[y], self.dir[y] = int(xs[0]) - 1, int(xs[-1]) + 1
        # na orelha e abaixo, a linha do rosto (o contorno com a pele do rosto do lado de dentro) é
        # rastreada linha a linha, a mais perto da de cima: o lóbulo da orelha direita encosta na
        # bochecha sem contorno no meio, e pela pele ligada a orelha viraria rosto
        pe, pd = self.esq[orelha_ini - 1], self.dir[orelha_ini - 1]
        meio_x = cabeca.shape[1] // 2
        for y in range(orelha_ini, self.queixo):
            esq = [x for x in range(1, meio_x) if contorno[y, x] and rosto[y, x + 1]]
            dir_ = [x for x in range(meio_x, cabeca.shape[1] - 1) if contorno[y, x] and rosto[y, x - 1]]
            perto_e = [x for x in esq if pe - 3 <= x <= pe + 4]
            perto_d = [x for x in dir_ if pd - 4 <= x <= pd + 3]
            pe = min(perto_e, key=lambda x: abs(x - pe)) if perto_e else pe
            pd = min(perto_d, key=lambda x: abs(x - pd)) if perto_d else pd
            self.esq[y], self.dir[y] = pe, pd
        # a orelha é o primeiro trecho de linhas com pele fora do rosto (mais abaixo, a pele fora
        # dele é a do pescoço, ao lado do queixo em V)
        fim = orelha_ini
        while fim + 1 < self.queixo and pele_fora[fim + 1, :self.esq[fim + 1]].any():
            fim += 1
        self.orelha = (orelha_ini, fim)
        # o alvo: a largura em que os olhos ocupam a mesma fração do rosto que no exemplo do dono
        olhos = np.vectorize(lambda c: c == "branco" or c.startswith("olho"))(cabeca)
        xs = np.nonzero(olhos.any(axis=0))[0]
        x0, x1 = int(xs[0]) - 1, int(xs[-1]) + 1                # com o contorno do olho
        largura = round((x1 - x0 + 1) / OLHOS_NA_LARGURA)
        self.cx = (x0 + x1) / 2
        self.alvo_e = round(self.cx - largura / 2)
        self.alvo_d = self.alvo_e + largura
        acima = list(range(self.topo, self.orelha[0]))
        self.L = min(self.esq[y] for y in acima)
        self.R = max(self.dir[y] for y in acima)
        self.k = (self.alvo_d - self.alvo_e) / (self.R - self.L)
        # a cúpula até a linha mais larga dela; dali até a orelha, os lados retos
        self.largo = min(y for y in acima if self.esq[y] <= self.L + 1 and self.dir[y] >= self.R - 1)

    def novo(self, y: int) -> tuple[int, int]:
        """A linha do rosto nova: a cúpula estreitada em volta do centro, e os lados retos na
        largura nova até a orelha; dali para baixo, o rosto já é mais estreito e nada muda."""
        e, d = self.esq[y], self.dir[y]
        if y < self.largo:
            return (max(e, round(self.cx - (self.cx - e) * self.k)),
                    min(d, round(self.cx + (d - self.cx) * self.k)))
        return max(e, self.alvo_e), min(d, self.alvo_d)

    def deslocamento(self, y: int) -> tuple[int, int]:
        """Quanto a linha do rosto anda para dentro em cada lado. Acima da cabeça (o cabelo alto, o
        chapéu), vale o da primeira linha dela."""
        y_ = min(max(y, self.topo), self.queixo - 1)
        ne, nd = self.novo(y_)
        return max(0, ne - self.esq[y_]), max(0, self.dir[y_] - nd)


def para_dentro(linha: np.ndarray, ate: int, d: int, lado: int) -> np.ndarray:
    """O que vai até ``ate`` (incluído; do lado de fora) anda ``d`` para dentro: o resto fica, e o
    que estava onde ele chega sai. ``lado``: -1 esquerda, +1 direita."""
    nova = linha.copy()
    n = len(linha)
    if d <= 0:
        return nova
    if lado < 0:
        bloco = linha[:ate + 1].copy()
        nova[:ate + 1 + d] = ""
        nova[d:ate + 1 + d] = bloco
    else:
        bloco = linha[ate:].copy()
        nova[ate - d:] = ""
        nova[ate - d:n - d] = bloco
    return nova


def mover_cabeca(g: np.ndarray, m: Molde) -> np.ndarray:
    """A cabeça do manequim: a linha do rosto, a sombra e o brilho de dentro dela e o que está fora
    andam para dentro; a pele que fica entre eles e o miolo sai."""
    saida = g.copy()
    for y in range(0, m.queixo):
        de, dd = m.deslocamento(y)
        if not (de or dd):
            continue
        linha = saida[y]
        if m.topo <= y < m.queixo:
            # a faixa de dentro que anda junto: a pele "-sombra", "-luz" colada no contorno
            fim = m.esq[y] + 1
            while fim < m.esq[y] + 1 + FAIXA_DA_CABECA and str(linha[fim]).startswith("pele-"):
                fim += 1
            linha = para_dentro(linha, fim - 1, de, -1)
            ini = m.dir[y] - 1
            while ini > m.dir[y] - 1 - FAIXA_DA_CABECA and str(linha[ini]).startswith("pele-"):
                ini -= 1
            linha = para_dentro(linha, ini + 1, dd, 1)
        else:                                               # o alto, só contorno
            xs = np.nonzero(linha != "")[0]
            if len(xs):
                linha = para_dentro(linha, int(xs[0]), de, -1)
                linha = para_dentro(linha, int(np.nonzero(linha != "")[0][-1]), dd, 1)
        saida[y] = linha
    return saida


def mover_parte(g: np.ndarray, m: Molde) -> np.ndarray:
    """Uma parte de cima (o cabelo, o chapéu) andando junto com o alto da cabeça: o que está na
    borda e fora dela (mais a faixa colada na borda) anda para dentro; o que estava onde ela chega
    sai (é o mesmo cabelo, um pouco mais estreito)."""
    saida = g.copy()
    for y in range(0, m.queixo):
        de, dd = m.deslocamento(y)
        if not (de or dd):
            continue
        y_ = min(max(y, m.topo), m.queixo - 1)
        linha = para_dentro(saida[y], m.esq[y_] + FAIXA, de, -1)
        saida[y] = para_dentro(linha, m.dir[y_] - FAIXA, dd, 1)
    return saida


def curva_limpa(alvo: list[float], fim: int) -> list[int]:
    """Os recuos inteiros da borda, linha a linha (0 = o lado reto), mais perto do ``alvo`` e com
    os degraus de pixel art limpa: descendo, cada passo para fora é no máximo do tamanho do de
    cima, e os trechos retos entre passos de 1 só crescem. Arredondar linha a linha dá "2, 1, 2" e
    "1, 0, 1": é o que se vê como amassado. A última linha é o lado (recuo 0)."""
    from functools import lru_cache

    n = len(alvo)
    teto = int(np.ceil(max(alvo))) + 2

    @lru_cache(maxsize=None)
    def custo(i: int, s: int, passo: int, trecho: int, ultimo: int) -> tuple[float, tuple]:
        # na linha i com recuo s; ``passo``: o último passo maior que zero; ``trecho``: as linhas
        # desde ele; ``ultimo``: o trecho que terminou nele
        aqui = (s - alvo[i]) ** 2
        if i == n - 1:
            return (aqui, (s,)) if s == fim else (float("inf"), ())
        melhor = (float("inf"), ())
        for p in range(0, s + 1):                         # o passo para fora, até o lado
            if p == 0:
                c, r = custo(i + 1, s, passo, trecho + 1, ultimo)
            elif p > 1 and (trecho > 1 or p > passo):     # passo largo: só seguido e sem crescer
                continue
            elif p == 1 and trecho < ultimo:              # trecho reto mais curto que o de cima
                continue
            else:
                c, r = custo(i + 1, s - p, p, 1, trecho)
            if c + aqui < melhor[0]:
                melhor = (c + aqui, (s, *r))
        return melhor

    melhor = min((custo(0, s, teto, 1, 1) for s in range(teto + 1)), key=lambda t: t[0])
    return list(melhor[1])


def alisar_cupula(cab: np.ndarray, m: Molde, expoente: float | None = None) -> tuple[np.ndarray, dict]:
    """A cúpula redesenhada por uma curva, do alto da cabeça até a orelha: a superelipse que mais
    se parece com a borda de hoje (a mesma largura e altura), em degraus limpos, com o contorno de
    1 pixel, a faixa de sombra de 2 e o brilho do lado direito, como no exemplo do dono.

    Estreitar a cabeça linha a linha deixou a borda amassada: trechos retos seguidos de um pulo e
    os pixels dobrados do contorno antigo nos lados (o dono reparou em 21/10/2026).

    ``expoente``: o da superelipse (2 é a elipse; maior, o alto mais largo e os "ombros" mais
    quadrados). Sem ele, vale o que mais se parece com a borda de hoje."""
    y0 = int(np.nonzero((cab != "").any(axis=1))[0][0])
    ate = m.orelha[0] - 2                                   # a orelha tem o contorno dela
    e, d = m.alvo_e, m.alvo_d
    cx = (e + d) / 2
    a = (d - e) / 2 + 0.5
    topo = y0 - 0.5

    def meia(y: float, y_c: float, n: float) -> float:
        if y >= y_c:
            return a
        dy = (y_c - y) / (y_c - topo)
        return a * max(0.0, 1 - dy ** n) ** (1 / n) if dy <= 1 else 0.0

    hoje = {}
    for y in range(y0, ate + 1):
        xs = np.nonzero(cab[y] != "")[0]
        hoje[y] = (int(xs[-1]) - int(xs[0]) + 1) / 2
    erro, y_c, n = min((sum((meia(y, yc, nn) - h) ** 2 for y, h in hoje.items()), yc, nn)
                       for yc in np.arange(y0 + 8, ate + 1, 0.25) for nn in np.arange(1.6, 3.6, 0.05))
    if expoente is not None:                                # a mesma altura e largura, outro formato
        n = expoente
    # o recuo de cada linha (quantos pixels a borda entra, de cada lado, em relação ao lado reto)
    alvo = [(d - e) / 2 - (meia(y, y_c, n) - 0.5) for y in range(y0, ate + 1)]
    recuo = curva_limpa(alvo, 0)
    dentro = np.zeros(cab.shape, bool)
    for i, s in enumerate(recuo):
        dentro[y0 + i, e + s:d - s + 1] = True
    dentro[ate + 1:, e:d + 1] = True                        # para baixo continua: não é borda
    borda = dentro & ~ndimage.binary_erosion(dentro, structure=[[0, 1, 0], [1, 1, 1], [0, 1, 0]],
                                             border_value=0)
    dist = ndimage.distance_transform_edt(dentro)
    # acima da sobrancelha só há pele: o contorno e a sombra antigos que ficaram longe da borda nova
    # (a cúpula menos arredondada vai mais para fora que a de antes) também saem
    testa = int(np.nonzero((cab == "sobrancelha").any(axis=1))[0][0])
    saida = cab.copy()
    for y in range(0, ate + 1):
        for x in range(cab.shape[1]):
            c = saida[y, x]
            if not (c == "" or c == "contorno" or c.startswith("pele")):
                continue                                    # a sobrancelha, o olho
            if not dentro[y, x]:
                saida[y, x] = ""
            elif borda[y, x]:
                saida[y, x] = "contorno"
            elif dist[y, x] <= 3:                           # a sombra da borda, 2 pixels
                saida[y, x] = "pele-sombra"
            elif dist[y, x] <= 5 or c == "" or y < testa:   # a sombra antiga, de largura torta
                saida[y, x] = "pele"
    # o brilho: uma faixa de 2 pixels logo dentro da sombra, no alto à direita
    for y in range(y0, int(y_c)):
        for x in range(int(cx), d):
            if dentro[y, x] and 4 < dist[y, x] <= 6 and saida[y, x] == "pele":
                angulo = np.degrees(np.arctan2(x - cx, (y_c - y) * a / (y_c - topo)))
                if 22 <= angulo <= 52:
                    saida[y, x] = "pele-luz"
    return saida, {"meio": round(float(y_c), 2), "n": round(float(n), 2),
                   "erro": round(float(np.sqrt(erro / len(hoje))), 2), "recuo": recuo,
                   "_dentro": dentro & ~borda, "_dist": dist, "_testa": testa}


def encostar_no_contorno(g: np.ndarray, cupula: dict, passos: int = 3) -> np.ndarray:
    """O cabelo crescido até o contorno novo da cúpula. As partes nasceram da diferença contra o
    manequim e não têm contorno em cima: usam o da cabeça. Com a cúpula redesenhada (o contorno de
    1 pixel e a faixa de sombra), o cabelo parava antes dele, e a faixa marrom aparecia entre os
    dois. Cada pixel vazio da faixa copia o vizinho de cabelo mais para dentro, só acima da
    sobrancelha e só a partir do cabelo que já está na borda."""
    dentro, dist, testa = cupula["_dentro"], cupula["_dist"], cupula["_testa"]
    saida = g.copy()
    for _ in range(passos):
        novos = {}
        for y, x in zip(*np.nonzero(dentro & (dist <= 1 + passos) & (saida == ""))):
            if y >= testa:
                continue
            viz = [(dist[yy, xx], saida[yy, xx]) for yy in range(y - 1, y + 2) for xx in range(x - 1, x + 2)
                   if (yy, xx) != (y, x) and saida[yy, xx] != "" and dist[yy, xx] > dist[y, x]]
            if viz:
                novos[(y, x)] = min(viz, key=lambda t: t[0])[1]   # o mais perto da borda
        if not novos:
            break
        for (y, x), c in novos.items():
            saida[y, x] = c
    return saida


def tirar_linhas(g: np.ndarray, linhas: set[int]) -> np.ndarray:
    """Tira as ``linhas`` da grade: o que está acima delas desce, o que está abaixo fica."""
    saida = np.full_like(g, "")
    for y in range(g.shape[0]):
        if y not in linhas:
            saida[y + sum(1 for r in linhas if r > y)] = g[y]
    return saida


def custo_das_linhas(grades: list[np.ndarray], faixa: range) -> dict[int, int]:
    """Quanto some ao tirar cada linha: os pixels em que ela difere da de cima (uma linha igual à
    vizinha sai sem ninguém notar)."""
    custo = dict.fromkeys(faixa, 0)
    for g in grades:
        for y in faixa:
            a, b = g[y - 1], g[y]
            custo[y] += int(((a != b) & ((a != "") | (b != ""))).sum())
    return custo


def escolher_linhas(custo: dict[int, int], k: int, espaco: int = 1) -> set[int]:
    """As ``k`` linhas mais baratas, a pelo menos ``espaco`` uma da outra (no empate, a mais
    baixa)."""
    escolhidas: list[int] = []
    for y in sorted(custo, key=lambda y: (custo[y], -y)):
        if all(abs(y - r) >= espaco for r in escolhidas):
            escolhidas.append(y)
        if len(escolhidas) == k:
            break
    return set(escolhidas)


def tapar_buracos(g: np.ndarray, testa: int, maior: int = 40) -> tuple[np.ndarray, int]:
    """Os buracos pequenos do cabelo acima da sobrancelha tapados com o cabelo de volta. Eles
    são pixels que a extração achou iguais ao manequim. Na cabeça antiga, caíam na faixa de sombra
    marrom e passavam por cabelo; na cúpula nova, ali é pele, e aparecia um risco de pele dentro do
    cabelo (o chanel, 21/10/2026). Só os buracos fechados: a testa e o vão de fora não mudam."""
    vazio = g == ""
    rot, n = ndimage.label(vazio)
    saida = g.copy()
    tapados = 0
    for k in range(1, n + 1):
        ys, xs = np.nonzero(rot == k)
        if len(ys) > maior or ys.max() >= testa or ys.min() == 0 or xs.min() == 0 or xs.max() == g.shape[1] - 1:
            continue
        buraco = rot == k
        while buraco.any():
            for y, x in zip(*np.nonzero(buraco)):
                viz = [saida[yy, xx] for yy in range(y - 1, y + 2) for xx in range(x - 1, x + 2)
                       if saida[yy, xx] != "" and not buraco[yy, xx]]
                if viz:
                    cores = [c for c in viz if c != "contorno"] or viz
                    saida[y, x] = max(set(cores), key=cores.count)
                    buraco[y, x] = False
        tapados += len(ys)
    return saida, tapados


def vestir_chapeu(g: np.ndarray, cabeca: np.ndarray, cx: float, testa: int) -> np.ndarray:
    """O chapéu alargado, linha a linha, até encostar no contorno da cabeça. O gorro nasceu sem
    contorno nos lados de cima: usava o da cabeça antiga, que tinha 3 pixels de grossura ali. Com o
    contorno novo de 1 pixel e a cúpula mais cheia, sobrava pele entre os dois. Cada metade da linha
    estica a partir do meio, e a borda do chapéu vai junto (ela continua sendo a borda)."""
    saida = g.copy()
    for y in range(testa):
        xs, cs = np.nonzero(g[y] != "")[0], np.nonzero(cabeca[y] != "")[0]
        if not len(xs) or not len(cs):
            continue
        for lado, borda, alvo in ((-1, int(xs[0]), int(cs[0]) + 1), (1, int(xs[-1]), int(cs[-1]) - 1)):
            if (alvo - borda) * lado <= 0:
                continue                                    # já encosta (ou passa: o boné)
            k = (alvo - cx) / (borda - cx)
            fim = int(np.floor(cx)) if lado < 0 else int(np.ceil(cx))
            for x in range(alvo, fim, -lado):
                saida[y, x] = g[y, int(round(cx + (x - cx) / k))]
    return saida


def aplicar(entrada: Path, saida: Path, expoente: float | None = EXPOENTE_DA_CUPULA,
            testa_menos: int = TESTA_MENOS) -> Molde:
    if saida != entrada:
        shutil.copytree(entrada, saida, dirs_exist_ok=True)
    grupos = pixels.ler(entrada / "cabeca" / "manequim.svg")
    cab = next(g for c, _e, g in grupos if c == "cabeca")
    silhueta = pixels.vazia()
    for c, _e, g in grupos:
        if c != "corpo":
            silhueta = np.where(g != "", g, silhueta)
    m = Molde(cab, silhueta)
    # as partes de cima, já estreitadas junto com a cabeça
    partes = {arq: [(c, e, mover_parte(g, m)) for c, e, g in pixels.ler(arq)]
              for categoria in ACOMPANHAM for arq in sorted((entrada / categoria).glob("*.svg"))}
    # a testa mais curta: as mesmas linhas saem da cabeça, dos cabelos e do fone, logo acima da
    # sobrancelha, onde os lados da cabeça são retos (assim continuam alinhados); os chapéus perdem
    # linhas da copa, para a aba ficar inteira
    testa = int(np.nonzero((cab == "sobrancelha").any(axis=1))[0][0])
    movida = mover_cabeca(cab, m)
    alto_da_cabeca = int(np.nonzero((movida != "").any(axis=1))[0][0])
    juntas = [_uniao(gs) for arq, gs in partes.items() if arq.stem not in CHAPEUS]
    corte = escolher_linhas(custo_das_linhas(juntas, range(testa - 7, testa)), testa_menos)
    cortes = {}
    for arq, gs in partes.items():
        if arq.stem in CHAPEUS:
            u = _uniao(gs)
            alto = int(np.nonzero((u != "").any(axis=1))[0][0])
            # o chapéu mais baixo que a cabeça (o gorro) para logo abaixo do contorno de cima dela
            k = testa_menos if alto <= alto_da_cabeca else min(testa_menos, alto_da_cabeca + testa_menos + 1 - alto)
            cortes[arq] = escolher_linhas(custo_das_linhas([u], range(alto + 2, testa)), k, 2)
        else:
            cortes[arq] = corte
    nova, cupula = alisar_cupula(tirar_linhas(movida, corte), m, expoente)
    pixels.escrever(saida / "cabeca" / "manequim.svg",
                    [(c, e, nova if c == "cabeca" else g) for c, e, g in grupos])
    for arq, gs in partes.items():
        cortadas = [(c, e, tirar_linhas(g, cortes[arq])) for c, e, g in gs]
        if arq.parent.name == "cabelo":
            cortadas = [(c, e, encostar_no_contorno(g, cupula) if c == "cabelo-frente" else g)
                        for c, e, g in cortadas]
            for i, (c, e, g) in enumerate(cortadas):
                if c == "cabelo-frente":
                    g, tapados = tapar_buracos(g, testa)
                    cortadas[i] = (c, e, g)
                    if tapados:
                        print(f"  {arq.stem}: {tapados} pixels de buraco tapados")
        elif arq.stem in CHAPEUS:
            cortadas = [(c, e, vestir_chapeu(g, nova, m.cx, testa) if c == "acessorio" else g)
                        for c, e, g in cortadas]
        pixels.escrever(saida / arq.parent.name / arq.name, cortadas)
    cupula = {k: v for k, v in cupula.items() if not k.startswith("_")}
    cupula["testa_menos"] = sorted(corte)
    cupula["chapeus"] = {arq.stem: sorted(r) for arq, r in cortes.items() if arq.stem in CHAPEUS}
    info = saida / "extracao.json"
    if info.is_file():
        dados = json.loads(info.read_text())
        y = dados["marcos"]["olhos"][1]
        xs = np.nonzero(nova[y] != "")[0]
        dados["marcos"]["rosto_x"] = [int(xs[0]), int(xs[-1])]
        dados["marcos"]["topo"] = int(np.nonzero((nova != "").any(axis=1))[0][0])
        dados["capsula"] = {"cranio_antes": [m.L, m.R], "cranio": [m.alvo_e, m.alvo_d],
                            "orelha": list(m.orelha), "queixo": m.queixo,
                            "cupula": {k: v for k, v in cupula.items() if k != "recuo"}}
        info.write_text(json.dumps(dados, indent=1))
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("entrada", type=Path)
    ap.add_argument("saida", type=Path)
    a = ap.parse_args()
    m = aplicar(a.entrada, a.saida)
    print(f"crânio {m.L}-{m.R} → {m.alvo_e}-{m.alvo_d} (×{m.k:.2f}), cúpula até a linha {m.largo}, "
          f"orelha {m.orelha[0]}-{m.orelha[1]}, queixo {m.queixo} (o rosto de baixo não muda)")


if __name__ == "__main__":
    main()
