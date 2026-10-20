"""O brilho da careca (como no exemplo do dono): uma faixa curta e clara, inclinada, no alto à
direita do crânio, num tom mais claro da própria pele.

    python brilho.py ENTRADA SAIDA
"""
import sys
import numpy as np
from PIL import Image
ent, sai = sys.argv[1], sys.argv[2]
im = np.asarray(Image.open(ent).convert("RGB")).copy()
r, g, b = (im[..., i].astype(int) for i in range(3))
magenta = (r > 160) & (b > 160) & (g < 120)
topo = int(np.nonzero((~magenta).any(1))[0][0])
cols = np.nonzero(~magenta[topo + 60])[0]
centro, larg = (cols[0] + cols[-1]) / 2, cols[-1] - cols[0]
pele = np.median(im[topo + 90: topo + 120, int(centro) - 40: int(centro) + 40].reshape(-1, 3), axis=0)
clara = np.clip(pele + (255 - pele) * 0.45, 0, 255).astype(np.uint8)
# a faixa: de (centro + 0.18 L, topo + 34) a (centro + 0.30 L, topo + 70), com 14 px de grossura
y0, x0 = topo + 34, centro + 0.17 * larg
y1, x1 = topo + 74, centro + 0.30 * larg
for t in np.linspace(0, 1, 120):
    yc, xc = y0 + (y1 - y0) * t, x0 + (x1 - x0) * t
    meia = 7 * (1 - abs(t - 0.45) * 0.9)
    for dx in range(-int(meia), int(meia) + 1):
        y, x = int(round(yc)), int(round(xc + dx))
        if np.abs(im[y, x].astype(int) - pele).sum() < 60:      # só sobre a pele
            im[y, x] = clara
Image.fromarray(im).save(sai)
print("ok", pele.astype(int).tolist(), "->", clara.tolist())
