#!/usr/bin/env python3
"""Debug script to inspect R data structure."""
import sys, os, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, '/Users/Usuario/PrevisaoOrcamentaria')
sys.path.insert(0, '/Users/Usuario/PrevisaoOrcamentaria/webapp/backend')
os.chdir('/Users/Usuario/PrevisaoOrcamentaria')
import previsao as core

folder = '/Users/Usuario/Downloads/Quezia - Previsão Orçamentária 3/Sophia I/Sophia I 2024'

R = core.analisar(folder)
bal = R['bal']
linhas = R['linhas']

print('=== RECEITAS (bal) ===')
for r in bal.get('receitas', []):
    avg = r['total'] / r['n_meses'] if r.get('n_meses', 0) > 1 else None
    print(f"  {r['classe']}: total={r['total']:.2f}, n_meses={r.get('n_meses',0)}, monthly={avg}")

print()
print('=== LINHAS ===')
valores_classe = {}
valores_grupo = {}
for l in linhas:
    from gerador_previsao import _norm
    valores_classe[_norm(l['classe'])] = l['final']
    ng = _norm(l['grupo'] or '')
    valores_grupo[ng] = valores_grupo.get(ng, 0) + l['final']
    print(f"  grupo=\"{l['grupo']:40s}\" | classe=\"{l['classe']:40s}\" | final={l['final']:>9.2f}")

print()
print('=== valores_grupo ===')
for k, v in sorted(valores_grupo.items()):
    print(f"  {k}: {v:.2f}")

print()
print('=== valores_classe (non-zero) ===')
for k, v in sorted(valores_classe.items()):
    if abs(v) > 0.005:
        print(f"  {k}: {v:.2f}")

print()
print('=== subtotal from R ===')
print(f'  {R.get("subtotal", "N/A")}')
