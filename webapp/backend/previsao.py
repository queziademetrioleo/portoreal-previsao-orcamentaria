#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PREVISAO ORCAMENTARIA — Webapp backend (importa do modulo raiz)
Este arquivo existe para que o webapp/backend/main.py continue funcionando
com `import previsao as core`. Todos os imports sao delegados ao modulo raiz.

Usa importlib para carregar o modulo raiz por caminho absoluto, evitando
que `from previsao import *` encontre este proprio modulo (mesmo nome).
"""
import sys, os, importlib.util

_root_m = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_root_path = os.path.join(_root_m, 'previsao.py')

# Carrega o modulo raiz diretamente do arquivo (nao por nome)
_spec = importlib.util.spec_from_file_location('previsao_raiz', _root_path)
_core = importlib.util.module_from_spec(_spec)
sys.modules['previsao_raiz'] = _core
_spec.loader.exec_module(_core)

# Exporta todos os nomes publicos para o namespace deste modulo
__all__ = [a for a in dir(_core) if not a.startswith('_')]
for _attr in __all__:
    globals()[_attr] = getattr(_core, _attr)
