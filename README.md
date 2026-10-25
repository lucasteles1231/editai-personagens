# editai-personagens

As partes do avatar do [Editai](https://github.com/lucasteles1231/editai): cabelos, barbas,
óculos, acessórios, roupas, expressões e poses em pixel art, vetorizadas, cada uma com os tons
separados por "espaço de cor". É a lógica dos jogos de montar personagem: o Editai escolhe as
partes (pela foto da pessoa, com o Gemini, ou à mão), pinta cada espaço com a cor dela e monta
os quadros do avatar.

O Editai leva uma cópia destas partes, de um commit fixo daqui: o `catalogo.json` traz o hash
de cada arquivo. São uns 900 KB, e a página pede ao Editai só as partes que vai desenhar.

**Um chapéu amassa o cabelo.** O boné e o gorro levam `data-cobre="cabelo"`. O cabelo que fica
debaixo deles não aparece, e o black power e o coque não passam por cima. O que sai pelos lados é
achatado até a aba: fica amassado, e não cortado reto.

## O que tem aqui

| Pasta | O quê |
|---|---|
| `padrao.json` | o padrão do personagem: o quadro (900 × 900, grade de 150), as camadas, as 12 poses (com a expressão e quando usar cada uma), as 3 bocas da fala, as regras da fala e da cena |
| `catalogo.json` | cada parte: a categoria, o id, a descrição (em português para a página e em inglês para o Gemini) e os espaços de cor que ela usa; as cores sugeridas; o hash de cada arquivo |
| `partes/<categoria>/<id>.svg` | as partes vetorizadas |
| `manequim/manequim.png` | o manequim de onde todas as partes nascem |
| `ferramentas/` | os scripts que geram, vetorizam e catalogam a biblioteca |

O que dá para escolher hoje:

- **15 cabelos:** curto, topete, raspado, com franja, repartido de lado, bagunçado, longo liso,
  longo ondulado, black power, cachos curtos, coque, rabo de cavalo, tranças, chanel e calvo
  (e careca, sem a parte).
- **5 barbas:** por fazer, bigode, cavanhaque, curta e cheia.
- **4 óculos:** redondos, retangulares sem aro, quadrados grossos e de sol.
- **4 acessórios:** boné, gorro, fone de ouvido e brincos.
- **4 roupas:** o suéter do manequim, moletom, camisa social e jaqueta aberta.
- **20 cabeças de bicho**, no lugar da cabeça da pessoa: cachorro, gato, raposa, panda, coelho,
  ovelha, pato, girafa, elefante, urso, leão, lobo, pinguim, porco, vaca, galinha, sapo, cavalo,
  lontra e guaxinim (veja [Os bichos](#os-bichos)).

As partes fixas mudam com a pose, e ninguém as escolhe:
- os olhos (aberto, de lado, para cima, arregalado, apertado e meio fechado);
- as sobrancelhas (normal e erguida);
- as bocas (sorriso, neutra, "o", rindo, meia e aberta);
- os braços das 12 poses.

O manequim tem três grupos:
- **a cabeça**, até o queixo;
- **o pescoço**, numa camada abaixo da roupa, para a gola de cada roupa cobrir ele;
- **o corpo**, o suéter, que sai quando outra roupa é escolhida.

## Como uma parte é feita

1. **O manequim:** um personagem careca, sem barba, sem óculos e com um suéter liso, em pixel
   art. O crânio foi ajustado em código
   (`encurtar_cranio.py`, `arredondar_cranio.py` e `brilho.py`).
2. **A edição:** cada parte nasce como uma edição do manequim no Nano Banana 2
   (`gemini-3.1-flash-image`): "ponha este cabelo", "esta barba", "estes braços". Os pedidos
   estão em `ferramentas/lista.json`. As poses usaram imagens de referência para a pose dos
   braços (essas imagens não estão aqui).
3. **O recorte:** `extrair_biblioteca.py` compara a edição com o manequim e fica só com o que
   mudou, dentro da região da categoria. As regiões saem dos marcos medidos no manequim (os
   olhos, as sobrancelhas, a boca e o começo da roupa).
4. **A vetorização:** a parte vai para a grade de 150 × 150. Cada pixel vira uma classe pelo
   tom: a base, a `-sombra`, a `-sombra2` e a `-luz`, mais o `contorno` e o `branco`. Os tons
   saem dos picos de luminância do próprio desenho, e o SVG é feito de faixas de pixel.
   - **A íris e a sobrancelha** são marrom-escuras no Nano Banana e cairiam no contorno. Por isso,
     o marrom com o branco do olho dos dois lados é `olho`, e o da sobrancelha é `sobrancelha`:
     a cor escolhida pinta os dois.
   - **O branco da roupa** (a camiseta por baixo da jaqueta, os botões) é `roupa2`, a segunda
     cor dela.
5. **A cabeça em cápsula** (`capsula.py`), como no exemplo do dono: o alto da cabeça com a
   largura do rosto. O manequim gerado tinha o alto bem mais largo que o resto, como uma
   lâmpada. A mudança é feita na grade, linha a linha:
   - **A largura nova** (44 px) é a em que os olhos ocupam a mesma fração do rosto que no
     exemplo (uns 77%).
   - **A testa** perde 4 linhas logo acima da sobrancelha (`TESTA_MENOS`): no exemplo, da
     sobrancelha ao alto é 0,49 da largura da cabeça. Os cabelos e o fone perdem as mesmas linhas;
     os chapéus perdem linhas da copa, para a aba ficar inteira.
   - **A cúpula é redesenhada** por uma superelipse (`EXPOENTE_DA_CUPULA` = 2,2, um pouco menos
     redonda que a elipse): o contorno de 1 pixel em degraus limpos, a sombra de 2 e o brilho.
     Estreitar linha a linha tinha deixado a borda amassada.
   - **Os cabelos e os chapéus** crescem até encostar no contorno novo: eles não têm contorno em
     cima, usam o da cabeça. Os furos pequenos do cabelo acima da sobrancelha são tapados: na
     cabeça antiga caíam na sombra marrom, e na nova mostravam pele.
   - **Da orelha para baixo**, inclusive o queixo, nada muda.
6. **As bocas e os óculos** são desenhados em código (`desenhar_partes.py`). Reduzidos à grade,
   os da IA viravam riscos e armações furadas.
   - **As bocas** são mapas de pixel simétricos, centrados no rosto.
   - **Os óculos** ficam em volta dos olhos medidos na cabeça, e a lente tinge o que está
     embaixo.

## Os bichos

Cada bicho é uma cabeça (`partes/cabeca/<bicho>.svg`, com o pescoço e o corpo do manequim) e os
olhos e as bocas dele (`olhos/<bicho>.<estado>.svg` e `boca/<bicho>.<estado>.svg`). No
`catalogo.json`, `bichos` traz o nome e as cores sugeridas de cada um, e `pelagem` as sugestões da
pelagem. Quem monta usa `{cabeca, olhos, boca}` = o id do bicho e deixa o cabelo, a barba, a
sobrancelha, os óculos e o acessório de fora: eles são da cabeça humana.

1. **A cabeça** nasce de uma edição do manequim no Nano Banana 2 (`gerar_bichos.py`): só a cabeça
   trocada, com uma imagem de referência do estilo para cada bicho (as usadas não estão aqui).
2. **O recorte** (`extrair_bichos.py`) separa as cores:
   - **A pelagem é o espaço `pele`**, em até quatro tons. A cor escolhida pinta o bicho, o
     pescoço e as mãos das poses. É o maior grupo da cabeça: a cor principal (a raposa, o porco),
     o cinza (o lobo, o gato rajado) ou o branco (o panda, o pato).
   - **O preto é `contorno`**, as manchas do panda e a máscara do guaxinim também.
   - **O resto que tem cor fica fixo:** o rosa da orelha, o bico, a crista, o chifre. A classe
     diz a cor, `fixa-rrggbb`, e quem monta pinta com ela, sem derivar tom.
   - **Os olhos e a boca gerados saem**, e o buraco pega a pelagem de volta. Os olhos são
     achados pelo brilho branco deles, um de cada lado; a boca, logo abaixo do nariz. No sorriso
     de bochecha a bochecha (o porco, o sapo), só o meio sai, e a boca desenhada continua a
     linha dele.
3. **Os olhos e as bocas** são desenhados em código (`desenhar_bichos.py`), no lugar medido no
   recorte (`bichos.json`): os seis olhares das poses e as seis bocas da fala. No bico (o pato, a
   galinha, o pinguim), a boca é o bico abrindo no meio; fechado, ele fica como veio.

```bash
cd ferramentas
GEMINI_API_KEY=... python gerar_bichos.py /tmp/gerado /caminho/das/referencias
uv run --with numpy --with pillow --with scipy python extrair_bichos.py /tmp/gerado ../partes /tmp/bichos
uv run --with numpy python desenhar_bichos.py /tmp/bichos/bichos.json /tmp/bichos
# copie /tmp/bichos/{cabeca,olhos,boca}/*.svg para ../partes e acrescente o bicho em BICHOS (catalogo.py)
python catalogo.py ../partes ../catalogo.json
```

## As classes de cor

| Classe | Espaço |
|---|---|
| `pele`, `pele-sombra`, `pele-sombra2`, `pele-luz` | a pele |
| `cabelo-*`, `barba-*`, `sobrancelha-*` | o cabelo, a barba e as sobrancelhas |
| `olho-*` | a íris |
| `roupa-*`, `roupa2-*` | a roupa e o segundo tom dela |
| `oculos-*`, `acessorio-*` | a armação e os acessórios |
| `contorno`, `branco`, `boca`, `lingua`, `dente` | fixas |
| `fixa-rrggbb` | fixa, com a cor no nome (os bichos: o rosa da orelha, o bico, a crista) |

Quem monta escolhe a cor base de cada espaço e deriva os tons dela (o `estilo` do
`padrao.json` diz quanto cada tom escurece ou clareia).

## Refazer a biblioteca

Gerar de novo custa imagem paga do Gemini (uns US$ 0,04 por imagem; são 52), com uma chave
que tenha faturamento:

```bash
cd ferramentas
mkdir -p biblioteca && cp ../manequim/manequim.png biblioteca/
# as poses dos braços pedem uma imagem de referência por pose em ref/<pose>.png
GEMINI_API_KEY=... python gerar_lote.py
uv run --with numpy --with pillow --with scipy python extrair_biblioteca.py biblioteca /tmp/extraidas
uv run --with numpy --with scipy python capsula.py /tmp/extraidas ../partes
uv run --with numpy --with scipy python desenhar_partes.py ../partes
python catalogo.py ../partes ../catalogo.json
```

Só o `capsula.py` e o `desenhar_partes.py` não custam nada: dá para mudar o formato da cabeça
(`OLHOS_NA_LARGURA`, `EXPOENTE_DA_CUPULA`, `TESTA_MENOS`) e o desenho das bocas e dos óculos sem
gerar imagem nenhuma.

## Licenças

- **As partes, o manequim, o padrão e o catálogo:** [CC0 1.0](LICENSE-PARTES), domínio
  público. Use como quiser, sem pedir.
- **As ferramentas:** [MIT](LICENSE).
