#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PREVISAO ORCAMENTARIA — Webapp backend (importa do modulo raiz)
Este arquivo existe para que o webapp/backend/main.py continue funcionando
com `import previsao as core`. Todos os imports sao delegados ao modulo raiz.

Usa importlib para carregar o modulo raiz por caminho absoluto, evitando
que `from previsao import *` encontre este proprio modulo (mesmo nome).

Caminhos tentados (em ordem):
  1. ../previsao.py (local: webapp/backend/ → raiz do projeto)
  2. /previsao.py     (Docker: COPY previsao.py /previsao.py)
"""
import sys, os, importlib.util

# Determina o caminho do modulo raiz
_here = os.path.dirname(os.path.abspath(__file__))
_candidates = [
    os.path.join(os.path.dirname(os.path.dirname(_here)), 'previsao.py'),  # ../../previsao.py
    '/previsao.py',                                                         # Docker
]

_root_path = None
for _cand in _candidates:
    if os.path.exists(_cand):
        _root_path = _cand
        break

if _root_path is None:
    raise FileNotFoundError(
        f'previsao.py (modulo raiz) nao encontrado. Tentei: {_candidates}'
    )

# Carrega o modulo raiz diretamente do arquivo (nao por nome)
_spec = importlib.util.spec_from_file_location('previsao_raiz', _root_path)
_core = importlib.util.module_from_spec(_spec)
sys.modules['previsao_raiz'] = _core
_spec.loader.exec_module(_core)

# Exporta todos os nomes publicos para o namespace deste modulo
__all__ = [a for a in dir(_core) if not a.startswith('_')]
for _attr in __all__:
    globals()[_attr] = getattr(_core, _attr)
