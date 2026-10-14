"""Gera uma proposta de transcrição das marcas das fotos. NÃO importa automaticamente."""
import csv
from pathlib import Path
from database import PHOTO_NAMES

marked = {
  1: list(range(1,12)), 2: list(range(1,8)), 5: list(range(1,5)), 6: list(range(1,5)),
  8: list(range(1,7)), 9: list(range(1,4)), 11: list(range(1,8)), 12: list(range(1,12)),
  13: list(range(1,6)), 14: [7], 15: list(range(1,5)), 16: list(range(1,6)),
  17: list(range(1,4)), 18: list(range(1,4)), 19: [7], 20: [7,8],
  22: list(range(1,5)), 23: list(range(1,4)), 24: list(range(1,8)),
  25: list(range(1,5)), 26: list(range(1,4)), 28: list(range(1,5)),
  29: list(range(1,8)), 30: list(range(1,4)), 32: list(range(1,8)), 33: list(range(1,12))
}
p = Path(__file__).parent/'historico_foto_2026_para_validar.csv'
with p.open('w', encoding='utf-8-sig', newline='') as file:
    writer = csv.DictWriter(file, fieldnames=['nome','mes','valor','rever_nome'])
    writer.writeheader()
    for index, (name, uncertain) in enumerate(PHOTO_NAMES, 1):
        for month in marked.get(index, []):
            writer.writerow({'nome': name, 'mes': month, 'valor': 3500, 'rever_nome': 'SIM' if uncertain else ''})
print(p, 'com', sum(map(len, marked.values())), 'marcas provisórias')
