# editai-personagens

As partes do avatar do [Editai](https://github.com/lucasteles1231/editai): cabelos, barbas,
óculos, acessórios, roupas, expressões e poses em pixel art, vetorizadas, cada uma com os tons
separados por "espaço de cor". É a lógica dos jogos de montar personagem: o Editai escolhe as
partes (pela foto da pessoa, com o Gemini, ou à mão), pinta cada espaço com a cor dela e monta
os quadros do avatar.

O Editai leva uma cópia destas partes, de um commit fixo daqui: o `catalogo.json` traz o hash
de cada arquivo. São uns 360 KB, e a página pede ao Editai só as partes que vai desenhar.

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

As partes fixas mudam com a pose, e ninguém as escolhe:
- os olhos (aberto, de lado, para cima, arregalado, apertado e meio fechado);
- as sobrancelhas (normal e erguida);
- as bocas (o sorriso do manequim, neutra, "o", rindo, meia e aberta);
- os braços das 12 poses.

## Como uma parte é feita

1. **O manequim:** um personagem careca, sem barba, sem óculos e com um suéter liso, no estilo
   pixel art do apresentador de um projeto anterior. O crânio foi ajustado em código
   (`encurtar_cranio.py`, `arredondar_cranio.py` e `brilho.py`).
2. **A edição:** cada parte nasce como uma edição do manequim no Nano Banana 2
   (`gemini-3.1-flash-image`): "ponha este cabelo", "esta barba", "estes braços". Os pedidos
   estão em `ferramentas/lista.json`. As poses usaram o apresentador de um projeto anterior como
   referência da pose dos braços (essas imagens não estão aqui).
3. **O recorte:** `extrair_biblioteca.py` compara a edição com o manequim e fica só com o que
   mudou, dentro da região da categoria. As regiões saem dos marcos medidos no manequim (os
   olhos, as sobrancelhas, a boca e o começo da roupa).
4. **A vetorização:** a parte vai para a grade de 150 × 150. Cada pixel vira uma classe pelo
   tom: a base, a `-sombra`, a `-sombra2` e a `-luz`, mais o `contorno` e o `branco`. Os tons
   saem dos picos de luminância do próprio desenho, e o SVG é feito de faixas de pixel.

**A boca** tem regras próprias:
- **O desenho inteiro:** ela leva tudo o que está na caixa dela, e não só o que mudou.
- **Pixel a pixel:** o contorno é escuro e sem vermelho, os dentes são claros e o de dentro é o
  vermelho escuro. A língua é o que está cercado pela boca, mesmo quando o tom dela parece pele.
- **A pele por baixo:** a pele que a boca repinta, onde estava o sorriso do manequim, vai na
  camada da cabeça, por baixo da barba.
- **A meia boca não é gerada:** ela é desenhada a partir da aberta, com a mesma largura, metade
  da altura, o contorno em cima e embaixo e uma fileira de dentes.

## As classes de cor

| Classe | Espaço |
|---|---|
| `pele`, `pele-sombra`, `pele-sombra2`, `pele-luz` | a pele |
| `cabelo-*`, `barba-*`, `sobrancelha-*` | o cabelo, a barba e as sobrancelhas |
| `olho-*` | a íris |
| `roupa-*`, `roupa2-*` | a roupa e o segundo tom dela |
| `oculos-*`, `acessorio-*` | a armação e os acessórios |
| `contorno`, `branco`, `boca`, `lingua`, `dente` | fixas |

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
uv run --with numpy --with pillow --with scipy python extrair_biblioteca.py biblioteca ../partes
python catalogo.py ../partes ../catalogo.json
```

## Licenças

- **As partes, o manequim, o padrão e o catálogo:** [CC0 1.0](LICENSE-PARTES), domínio
  público. Use como quiser, sem pedir.
- **As ferramentas:** [MIT](LICENSE).
