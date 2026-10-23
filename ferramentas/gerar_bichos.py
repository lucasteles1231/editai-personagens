"""As cabeças dos bichos: uma edição do manequim por bicho no Nano Banana 2, com uma imagem de
referência do estilo para cada um (as usadas aqui não estão no repositório). Pago: uns US$ 0,04 por
imagem, pela chave de ``gerar.py``. Um bicho que já tem a imagem não é pedido de novo.

    GEMINI_API_KEY=... python gerar_bichos.py GERADO REFERENCIAS [bicho...]

``REFERENCIAS/<bicho>.png`` é a referência de estilo; as imagens vão para ``GERADO/<bicho>.png``,
com o ``manequim.png`` ao lado (o ``extrair_bichos.py`` compara com ele).
"""
import shutil
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
MANEQUIM = AQUI.parent / "manequim" / "manequim.png"
GERADO, REFERENCIAS = Path(sys.argv[1]), Path(sys.argv[2])
BASE = ("Edit the FIRST image: replace ONLY the character's human head with {bicho}, drawn in the style of the "
        "SECOND image (the same cute chunky pixel art with a thick black outline). The new head sits on the same "
        "neck, centered, at the same height and about the same size as the original head (ears may stick out "
        "beyond it). Facing front, eyes open looking at the viewer, small closed smiling mouth. Keep EVERYTHING "
        "else exactly identical to the first image: the same light gray sweater and body, the same position, size "
        "and framing, the same pixel size, the thick black outline, the white sticker border and the flat magenta "
        "(#FF00FF) background. No hoodie, no clothes changes, no text.")
BICHOS = {
    "cachorro": "a cute puppy head: rounded head, long floppy ears hanging down on both sides, a short snout with a "
                "black nose; medium golden-brown fur with a slightly darker shade on the ears",
    "gato": "a cute tabby cat head: pointed upright ears with pink insides, whiskers, a small pink nose; medium gray "
            "fur with darker gray tabby stripes on the forehead and cheeks",
    "raposa": "a cute fox head: big pointed upright ears with white insides and dark tips, a white muzzle and white "
              "cheeks, a small black nose; bright orange fur",
    "panda": "a cute panda head: round head, round black ears, black patches around the eyes, a small black nose; "
             "white fur with black patches",
    "coelho": "a cute bunny head: two tall upright ears with pink insides, round cheeks with a light pink blush, a "
              "small pink nose; light gray fur",
    "ovelha": "a cute sheep head: a fluffy cap of round cream-white wool curls on top and around the face, a light "
              "beige face, small droopy ears with pink insides, a small dark nose; cream-white wool",
    "pato": "a cute duck head: a round white head, a wide flat orange bill, no hat; white feathers",
    "girafa": "a cute giraffe head with only a short bit of neck: a long snout, two small ossicone horns with dark round "
              "tips, small ears; golden-yellow fur with brown patches",
    "elefante": "a cute baby elephant head: big round floppy ears, a short trunk hanging down in the middle, two small "
                "white tusks; gray skin",
    "urso": "a cute brown bear head: small round ears, a lighter tan muzzle, a small black nose; medium brown fur",
    "leao": "a cute lion head: a big fluffy darker orange-brown mane all around the face, small round ears, a lighter "
            "muzzle, a small dark nose; golden fur",
    "lobo": "a cute wolf head: tall pointed ears, a white muzzle and white cheeks, a black nose; gray fur",
    "pinguim": "a cute penguin head: a round black head with a white face, a small orange beak, no hat. A penguin "
               "has NO ears: remove the human ears completely, the round black head covers where they were",
    "porco": "a cute pig head: floppy pink ears, a round snout with two dark nostrils; pink skin",
    "vaca": "a cute cow head: white with black patches, two small cream horns, ears sticking out to the sides, a pink "
            "snout with two nostrils",
    "galinha": "a cute chicken head: a red comb on top, a small yellow-orange beak, small red wattles under the beak; "
               "white feathers",
    "sapo": "a cute frog head: two big bulging eyes on top of the head, a wide smiling mouth line; green skin with a "
            "lighter yellow-green lower face",
    "cavalo": "a cute horse head: a long face, a white blaze down the middle, small pointed ears, a dark brown mane on "
              "top, two nostrils at the bottom of the muzzle; chestnut brown fur",
    "lontra": "a cute otter head: a round head, tiny round ears, a lighter muzzle with whiskers, a small dark nose; "
              "brown fur",
    "guaxinim": "a cute raccoon head: a black mask around the eyes, white around the mask and on the muzzle, round ears "
                "with white insides, a black nose; gray fur",
}
GERADO.mkdir(parents=True, exist_ok=True)
shutil.copy2(MANEQUIM, GERADO / "manequim.png")
for nome in sys.argv[3:] or BICHOS:
    destino = GERADO / f"{nome}.png"
    if destino.exists():
        continue
    r = subprocess.run([sys.executable, "-I", str(AQUI / "gerar.py"), str(destino),
                        BASE.format(bicho=BICHOS[nome]), str(MANEQUIM), str(REFERENCIAS / f"{nome}.png")],
                       capture_output=True, text=True, cwd=AQUI)
    saida = (r.stdout + r.stderr).strip().splitlines()
    print(nome, saida[-1] if saida else r.returncode, flush=True)
    if r.returncode == 2:
        break
