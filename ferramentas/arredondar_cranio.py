"""Dá ao alto da cabeça careca o perfil do exemplo do dono: uma cúpula redonda (meio círculo,
com o topo achatado em 30%). Cada linha acima da sobrancelha é encolhida, em volta do centro da
cabeça, até a largura que o perfil pede para aquela altura.

    python arredondar_cranio.py ENTRADA SAIDA
"""
import sys
import numpy as np
from PIL import Image
ent, sai = sys.argv[1], sys.argv[2]
im = np.asarray(Image.open(ent).convert("RGB")).copy()
r, g, b = (im[..., i].astype(int) for i in range(3))
magenta = (r > 160) & (b > 160) & (g < 120)
topo = int(np.nonzero((~magenta).any(1))[0][0])
meio = im[:, 380:640].astype(int)
escuro = (meio.max(-1) < 110) & (meio[..., 0] > meio[..., 2] + 10)
linhas = np.nonzero(escuro.sum(1) > 20)[0]
sobrancelha = int(linhas[linhas > topo + 150][0]) - 6


def extensao(y):
    c = np.nonzero(~magenta[y])[0]
    return (c[0], c[-1]) if len(c) else None


a0, b0 = extensao(sobrancelha)
W = b0 - a0
centro = (a0 + b0) / 2
H = sobrancelha - topo
saida = im.copy()
L = im.shape[1]
xs = np.arange(L)
for y in range(topo, sobrancelha):
    e = extensao(y)
    if not e:
        continue
    t = (sobrancelha - y) / H
    alvo = W * max(0.30, np.sqrt(max(0.0, 1 - t * t)))          # meio círculo, topo achatado
    atual = e[1] - e[0]
    s = min(1.0, alvo / atual)
    origem = np.round(centro + (xs - centro) / s).astype(int)
    linha = np.full((L, 3), (255, 0, 255), np.uint8)
    dentro = (origem >= 0) & (origem < L)
    linha[dentro] = im[y, origem[dentro]]
    saida[y] = linha
Image.fromarray(saida).save(sai)
print(f"topo {topo}, sobrancelha {sobrancelha}, largura {W}, altura {H} ({H / W:.2f} da largura)")
