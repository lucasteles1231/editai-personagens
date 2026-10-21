"""A cabeça em cápsula, como o exemplo do dono (20/10/2026): o alto da cabeça com a largura do rosto
na altura das orelhas, os lados retos dos olhos às orelhas, e daí para baixo o rosto de sempre (o
maxilar e o queixo, que o dono aprovou).

O manequim gerado tinha o alto da cabeça bem mais largo que o resto (52 px na grade, contra 42 no
rosto atrás das orelhas e 39 no maxilar): uma lâmpada. Na primeira tentativa, o rosto de baixo
foi alargado até o alto, e o queixo ficou quadrado ("antes estava bom já"). Aqui é o contrário: o
alto encolhe, e o queixo não muda. A largura nova é a em que os olhos ocupam a mesma fração do
rosto que no exemplo do dono (uns 77%; no manequim, eram 63%): 44 px na grade.

Na grade de 150, sobre as partes já vetorizadas, linha a linha:

- **a cabeça do manequim:** a cúpula é estreitada em volta do centro (a mesma curva, mais
  estreita), e dela até a orelha os lados ficam retos, na largura nova. O
  contorno, a sombra de dentro dele e o brilho andam para dentro, e a pele que sobra sai;
- **os cabelos e os acessórios** (o boné, o gorro, o fone) andam o mesmo tanto, para continuarem
  no alto da cabeça.

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


def aplicar(entrada: Path, saida: Path) -> Molde:
    if saida != entrada:
        shutil.copytree(entrada, saida, dirs_exist_ok=True)
    grupos = pixels.ler(entrada / "cabeca" / "manequim.svg")
    cab = next(g for c, _e, g in grupos if c == "cabeca")
    silhueta = pixels.vazia()
    for c, _e, g in grupos:
        if c != "corpo":
            silhueta = np.where(g != "", g, silhueta)
    m = Molde(cab, silhueta)
    pixels.escrever(saida / "cabeca" / "manequim.svg",
                    [(c, e, mover_cabeca(g, m) if c == "cabeca" else g) for c, e, g in grupos])
    for categoria in ACOMPANHAM:
        for arq in sorted((entrada / categoria).glob("*.svg")):
            gs = pixels.ler(arq)
            pixels.escrever(saida / categoria / arq.name, [(c, e, mover_parte(g, m)) for c, e, g in gs])
    info = saida / "extracao.json"
    if info.is_file():
        dados = json.loads(info.read_text())
        nova = mover_cabeca(cab, m)
        y = dados["marcos"]["olhos"][1]
        xs = np.nonzero(nova[y] != "")[0]
        dados["marcos"]["rosto_x"] = [int(xs[0]), int(xs[-1])]
        dados["capsula"] = {"cranio_antes": [m.L, m.R], "cranio": [m.alvo_e, m.alvo_d],
                            "orelha": list(m.orelha), "queixo": m.queixo}
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
