"""O manequim careca com o crânio mais baixo: a faixa acima das sobrancelhas é comprimida na
vertical (sem IA), e o rosto, as orelhas e o corpo ficam iguais.

    python encurtar_cranio.py ENTRADA SAIDA FATOR
"""
import sys
import numpy as np
from PIL import Image
ent, sai, fator = sys.argv[1], sys.argv[2], float(sys.argv[3])
im = np.asarray(Image.open(ent).convert("RGB")).copy()
r, g, b = (im[..., i].astype(int) for i in range(3))
magenta = (r > 160) & (b > 160) & (g < 120)
# a sobrancelha: a primeira linha (de cima) com marrom escuro no meio do rosto
meio = im[:, 380:640].astype(int)
escuro = (meio.max(-1) < 110) & (meio[..., 0] > meio[..., 2] + 10)
topo = int(np.nonzero((~magenta).any(1))[0][0])
# o contorno do alto da cabeça também é escuro: procura a sobrancelha só no rosto, bem abaixo do topo
linhas = np.nonzero(escuro.sum(1) > 20)[0]
linhas = linhas[linhas > topo + 150]
sobrancelha = int(linhas[0]) - 6
alto = sobrancelha - topo
novo_alto = round(alto * fator)
faixa = Image.fromarray(im[topo:sobrancelha]).resize((im.shape[1], novo_alto), Image.NEAREST)
saida = np.zeros_like(im); saida[...] = (255, 0, 255)
saida[sobrancelha:] = im[sobrancelha:]
saida[sobrancelha - novo_alto:sobrancelha] = np.asarray(faixa)
Image.fromarray(saida).save(sai)
print(f"topo {topo}, sobrancelha {sobrancelha}: de {alto} para {novo_alto} px")
