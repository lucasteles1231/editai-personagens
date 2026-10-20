"""Gera a lista inteira (lista.json) em biblioteca/, pulando o que já existe e parando se o total
de imagens pagas (gastos.txt) passar do teto."""
import json, subprocess, sys
from pathlib import Path
O = Path(__file__).parent
TETO = 100
itens = json.loads((O / "lista.json").read_text())
for it in itens:
    destino = O / "biblioteca" / f"{it['categoria']}-{it['id']}.png"
    if destino.exists():
        continue
    gastas = len((O / "gastos.txt").read_text().splitlines()) if (O / "gastos.txt").exists() else 0
    if gastas >= TETO:
        print("teto de imagens atingido:", gastas); sys.exit(3)
    r = subprocess.run([sys.executable, "-I", str(O / "gerar.py"), str(destino), it["pedido"], *it["imagens"]],
                       cwd=O, capture_output=True, text=True)
    print(destino.name, (r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout + r.stderr).strip() else r.returncode, flush=True)
    if r.returncode == 2:
        print("a API recusou: parando"); sys.exit(2)
print("fim; imagens pagas no total:",
      len((O / "gastos.txt").read_text().splitlines()) if (O / "gastos.txt").exists() else 0)
