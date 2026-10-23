"""O catálogo das partes (catalogo.json): o que cada parte é, em português (para a página) e em
inglês (para o Gemini escolher pela foto), os espaços de cor que ela usa e o hash de cada arquivo.

Os espaços de cor saem das próprias SVGs (as classes ``cabelo``, ``cabelo-sombra``… viram
``cabelo``); as descrições ficam aqui, à mão.

    python ferramentas/catalogo.py PARTES SAIDA.json
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ESPACOS = ["pele", "cabelo", "sobrancelha", "barba", "olho", "roupa", "roupa2", "oculos", "acessorio"]

# as categorias que a pessoa (ou o Gemini) escolhe; "nenhum" é sem a parte
ESCOLHAS = {
    "cabelo": {
        "rotulo": "Cabelo",
        "nenhum": ["careca", "bald, no hair at all"],
        "opcoes": {
            "curto": ["curto", "short neat hair, tapered sides, a little volume on top"],
            "topete": ["topete", "short quiff: tapered sides, volume on top swept up and back"],
            "raspado": ["raspado", "very short buzz cut, an even thin layer of shaved hair"],
            "franja": ["com franja", "short hair with straight bangs covering the forehead"],
            "lateral": ["repartido de lado", "medium-short hair with a side part, combed to one side"],
            "baguncado": ["bagunçado", "messy, tousled medium-length hair with loose spiky locks"],
            "longo": ["longo liso", "long straight hair with a center part, falling onto the shoulders"],
            "ondulado": ["longo ondulado", "long wavy hair with a side part, falling onto the shoulders"],
            "afro": ["black power", "big round afro of tight curls"],
            "cachos-curtos": ["cachos curtos", "short tight curls close to the head"],
            "coque": ["coque", "hair pulled back tight into a round bun on top of the head"],
            "rabo": ["rabo de cavalo", "long hair slicked back into a ponytail"],
            "trancas": ["tranças", "long box braids falling onto the shoulders"],
            "chanel": ["chanel", "chin-length bob haircut with a side part"],
            "calvo": ["calvo", "male pattern baldness: bald on top, short hair only on the sides and back"],
        },
    },
    "barba": {
        "rotulo": "Barba",
        "nenhum": ["sem barba", "clean-shaven, no facial hair"],
        "opcoes": {
            "rala": ["por fazer", "light stubble, a few days of growth"],
            "bigode": ["bigode", "mustache only, no beard"],
            "cavanhaque": ["cavanhaque", "thin mustache and a small goatee on the chin"],
            "curta": ["curta", "short well-trimmed beard with mustache, close to the jaw"],
            "cheia": ["cheia", "full beard with mustache covering the jaw and the chin"],
        },
    },
    "oculos": {
        "rotulo": "Óculos",
        "nenhum": ["sem óculos", "no glasses"],
        "opcoes": {
            "redondos": ["redondos", "thin round metal-frame glasses"],
            "retangulares": ["retangulares sem aro", "thin rectangular rimless glasses"],
            "quadrados": ["quadrados grossos", "thick square plastic-frame glasses"],
            "sol": ["de sol", "dark sunglasses"],
        },
    },
    "acessorio": {
        "rotulo": "Acessório",
        "nenhum": ["nenhum", "no hat, no headphones, no earrings"],
        "opcoes": {
            "bone": ["boné", "baseball cap facing forward"],
            "gorro": ["gorro", "knitted beanie"],
            "fone": ["fone de ouvido", "big over-ear headphones on the head"],
            "brincos": ["brincos", "small round earrings"],
        },
    },
    "roupa": {
        "rotulo": "Roupa",
        "nenhum": ["suéter", "plain crew-neck sweater or T-shirt"],
        "opcoes": {
            "moletom": ["moletom", "hoodie with the hood down and two drawstrings"],
            "camisa": ["camisa social", "button-up shirt with a collar"],
            "jaqueta": ["jaqueta aberta", "open jacket over a crew-neck T-shirt"],
        },
    },
}

# os bichos (21/10/2026): a cabeça no lugar da do manequim, com os olhos e as bocas desenhados em
# código para ela (desenhar_bichos.py). A pelagem é o espaço "pele": a cor escolhida pinta o bicho, o
# pescoço e as mãos. Sem cabelo, barba, sobrancelha, óculos nem acessório (eles são da cabeça humana).
BICHOS = {
    "cachorro": {"pt": "cachorro", "pelagem": "#e69d4e", "olho": "#2a1d14"},
    "gato": {"pt": "gato", "pelagem": "#8a736c", "olho": "#c8902a"},
    "raposa": {"pt": "raposa", "pelagem": "#f77e25", "olho": "#2a1d14"},
    "panda": {"pt": "panda", "pelagem": "#ffffff", "olho": "#2a1d14"},
    "coelho": {"pt": "coelho", "pelagem": "#ddc3b8", "olho": "#2a1d14"},
    "ovelha": {"pt": "ovelha", "pelagem": "#f6dbbe", "olho": "#2a1d14"},
    "pato": {"pt": "pato", "pelagem": "#ffffff", "olho": "#2a1d14"},
    "girafa": {"pt": "girafa", "pelagem": "#eca927", "olho": "#2a1d14"},
    "elefante": {"pt": "elefante", "pelagem": "#a08b8d", "olho": "#2a1d14"},
    "urso": {"pt": "urso", "pelagem": "#8f5031", "olho": "#2a1d14"},
    "leao": {"pt": "leão", "pelagem": "#cd6420", "olho": "#2a1d14"},
    "lobo": {"pt": "lobo", "pelagem": "#808a8e", "olho": "#2a1d14"},
    "pinguim": {"pt": "pinguim", "pelagem": "#ffffff", "olho": "#2a1d14"},
    "porco": {"pt": "porco", "pelagem": "#faa597", "olho": "#2a1d14"},
    "vaca": {"pt": "vaca", "pelagem": "#424242", "olho": "#2a1d14"},
    "galinha": {"pt": "galinha", "pelagem": "#ffffff", "olho": "#2a1d14"},
    "sapo": {"pt": "sapo", "pelagem": "#719c42", "olho": "#2a1d14"},
    "cavalo": {"pt": "cavalo", "pelagem": "#bb6032", "olho": "#2a1d14"},
    "lontra": {"pt": "lontra", "pelagem": "#9d664c", "olho": "#2a1d14"},
    "guaxinim": {"pt": "guaxinim", "pelagem": "#8a8a89", "olho": "#2a1d14"},
}
ESTADOS_DOS_OLHOS = ("aberto", "lado", "cima", "arregalado", "apertado", "meio")
ESTADOS_DAS_BOCAS = ("sorriso", "neutra", "o", "meia", "aberta", "rindo")
PELAGEM = {
    "rotulo": "Pelagem",
    "sugestoes": {"#e69d4e": "caramelo", "#f77e25": "laranja", "#a0663a": "marrom", "#3a2a20": "preta",
                  "#8a736c": "cinza", "#c9c4bf": "cinza claro", "#ddc3b8": "bege", "#ffffff": "branca",
                  "#eca927": "amarela", "#faa597": "rosa", "#719c42": "verde"},
}

# as partes fixas: vêm do manequim ou mudam com a pose, ninguém escolhe
FIXAS = {"cabeca": "manequim", "olhos": "ia", "sobrancelhas": "ia", "nariz": "nenhum", "boca": "ia", "bracos": "ia"}

CORES = {
    "pele": {
        "rotulo": "Pele",
        "sugestoes": {"#f7d2b6": "muito clara", "#f4bf96": "clara", "#e2a57c": "média clara", "#c68642": "média",
                      "#a26a42": "morena", "#8a5636": "escura", "#5c3a24": "muito escura"},
    },
    "cabelo": {
        "rotulo": "Cabelo",
        "sugestoes": {"#1f1611": "preto", "#3b2a1e": "castanho escuro", "#6b4a2b": "castanho", "#b5562c": "ruivo",
                      "#d9b26a": "loiro", "#ecd59a": "loiro claro", "#9a9a9a": "grisalho", "#e6e2da": "branco"},
    },
    "sobrancelha": {"rotulo": "Sobrancelha", "vazia": "o cabelo, mais escuro", "sugestoes": {}},
    "barba": {"rotulo": "Barba", "vazia": "o cabelo", "sugestoes": {}},
    "olho": {
        "rotulo": "Olhos",
        "sugestoes": {"#2a1d14": "preto", "#5a3a22": "castanho", "#9a6b2f": "mel", "#4c8a52": "verde",
                      "#3d6fa8": "azul", "#7d8a91": "cinza"},
    },
    "roupa": {
        "rotulo": "Roupa",
        "sugestoes": {"#3c7542": "verde", "#2b4c7e": "azul", "#1f2430": "preta", "#c2185b": "rosa",
                      "#f0a500": "amarela", "#9aa0a6": "cinza", "#5b3b8a": "roxa", "#b23a2e": "vermelha"},
    },
    "roupa2": {"rotulo": "Detalhe da roupa", "sugestoes": {"#e8e4da": "branco", "#1f2430": "preto"}},
    "oculos": {"rotulo": "Óculos", "sugestoes": {"#2f2f2f": "preto", "#8a6a3b": "tartaruga", "#b8b8b8": "prata"}},
    "acessorio": {"rotulo": "Acessório", "sugestoes": {"#2b4c7e": "azul", "#1f2430": "preto", "#d4a017": "dourado",
                                                       "#b23a2e": "vermelho"}},
}

PADRAO = {"cabelo": "curto", "barba": "nenhum", "oculos": "nenhum", "acessorio": "nenhum", "roupa": "moletom",
          "cores": {"pele": "#f4bf96", "cabelo": "#3b2a1e", "sobrancelha": "", "barba": "", "olho": "#5a3a22",
                    "roupa": "#3c7542", "roupa2": "#e8e4da", "oculos": "#2f2f2f", "acessorio": "#2b4c7e"}}


def espacos_da(svg: str) -> list[str]:
    classes = {c for m in re.findall(r'class="([^"]+)"', svg) for c in m.split()}
    bases = {re.sub(r"^t-", "", c).split("-")[0] for c in classes}
    return [e for e in ESPACOS if e in bases]


def main() -> None:
    partes, saida = Path(sys.argv[1]), Path(sys.argv[2])
    arquivos = {}
    for svg in sorted(partes.rglob("*.svg")):
        rel = svg.relative_to(partes).as_posix()
        dados = svg.read_bytes()
        arquivos[rel] = {"bytes": len(dados), "sha256": hashlib.sha256(dados).hexdigest()}
    categorias = {}
    for cat, info in ESCOLHAS.items():
        opcoes = []
        for id_, (pt, en) in info["opcoes"].items():
            rel = f"{cat}/{id_}.svg"
            if rel not in arquivos:
                raise SystemExit(f"falta a parte {rel}")
            opcoes.append({"id": id_, "pt": pt, "en": en, "cores": espacos_da((partes / rel).read_text())})
        sobra = {p.stem for p in (partes / cat).glob("*.svg")} - set(info["opcoes"])
        if sobra:
            raise SystemExit(f"partes sem descrição em {cat}: {sorted(sobra)}")
        categorias[cat] = {"rotulo": info["rotulo"], "nenhum": {"pt": info["nenhum"][0], "en": info["nenhum"][1]},
                           "opcoes": opcoes}
    for cat, id_ in FIXAS.items():
        if id_ != "nenhum" and not any(r.startswith(f"{cat}/{id_}") for r in arquivos):
            raise SystemExit(f"falta a parte fixa {cat}/{id_}")
    bichos = []
    for id_, info in BICHOS.items():
        precisa = [f"cabeca/{id_}.svg", *(f"olhos/{id_}.{e}.svg" for e in ESTADOS_DOS_OLHOS),
                   *(f"boca/{id_}.{e}.svg" for e in ESTADOS_DAS_BOCAS)]
        falta = [r for r in precisa if r not in arquivos]
        if falta:
            raise SystemExit(f"falta do bicho {id_}: {falta}")
        bichos.append({"id": id_, **info})
    saida.write_text(json.dumps({
        "editai": "catalogo-do-personagem",
        "versao": 1,
        "categorias": categorias,
        "fixas": FIXAS,
        "cores": CORES,
        "padrao": PADRAO,
        "bichos": bichos,
        "pelagem": PELAGEM,
        "arquivos": arquivos,
    }, ensure_ascii=False, indent=1) + "\n")
    print(f"{saida}: {sum(len(c['opcoes']) for c in categorias.values())} opções, {len(bichos)} bichos, "
          f"{len(arquivos)} arquivos, "
          f"{sum(a['bytes'] for a in arquivos.values()) // 1024} KB")


if __name__ == "__main__":
    main()
