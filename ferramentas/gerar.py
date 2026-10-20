"""Uma imagem do Nano Banana 2 (gemini-3.1-flash-image) a partir de imagens + texto. A chave vem
da variável GEMINI_API_KEY (precisa de faturamento: a geração de imagem não tem cota grátis) e
nunca é impressa. Cada imagem paga fica anotada em gastos.txt.

    GEMINI_API_KEY=... python gerar.py SAIDA.png "PEDIDO" IMAGEM [IMAGEM...]
"""
import base64, io, os, sys, time
from pathlib import Path
import httpx
from PIL import Image

MODELO = "gemini-3.1-flash-image"
CHAVE = os.environ.get("GEMINI_API_KEY", "").strip()
if not CHAVE:
    sys.exit("defina GEMINI_API_KEY (uma chave com faturamento)")
saida, pedido, entradas = Path(sys.argv[1]), sys.argv[2], sys.argv[3:]

def parte(caminho):
    buf = io.BytesIO(); Image.open(caminho).convert("RGB").save(buf, "PNG")
    return {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(buf.getvalue()).decode()}}

corpo = {"contents": [{"parts": [*(parte(e) for e in entradas), {"text": pedido}]}],
         "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "1:1"}}}
for tentativa in range(3):
    t0 = time.time()
    r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent",
                   headers={"x-goog-api-key": CHAVE}, json=corpo, timeout=240)
    if r.status_code != 200:
        print("erro", r.status_code, r.text[:300].replace(CHAVE, "<chave>"))
        if r.status_code in (400, 401, 402, 403, 429):
            sys.exit(2)
        time.sleep(5); continue
    partes = r.json()["candidates"][0]["content"].get("parts", [])
    for p in partes:
        dado = p.get("inlineData") or p.get("inline_data")
        if dado:
            Image.open(io.BytesIO(base64.b64decode(dado["data"]))).save(saida)
            with open(Path(__file__).parent / "gastos.txt", "a") as g:
                g.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {saida.name}\n")
            print(f"ok {saida.name} {time.time() - t0:.0f}s")
            sys.exit(0)
    print("sem imagem:", [p.get("text", "")[:200] for p in partes])
sys.exit(1)
