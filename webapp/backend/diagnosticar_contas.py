#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI para diagnosticar a aba CONTAS de uma previsao manual."""
import argparse
from pathlib import Path

from diagnostico_contas import extrair_contas, gerar_markdown, salvar_diagnostico


def main():
    parser = argparse.ArgumentParser(description='Extrai formulas e memoria da aba CONTAS.')
    parser.add_argument('previsao', help='Caminho para Previsao XXXX.xlsx manual')
    parser.add_argument('--json', dest='json_path', help='Destino do JSON completo')
    parser.add_argument('--md', dest='md_path', help='Destino do relatorio Markdown')
    args = parser.parse_args()

    previsao = Path(args.previsao)
    json_path = Path(args.json_path) if args.json_path else previsao.with_suffix('.contas-diagnostico.json')
    md_path = Path(args.md_path) if args.md_path else previsao.with_suffix('.contas-diagnostico.md')

    diag = salvar_diagnostico(previsao, json_path)
    md_path.write_text(gerar_markdown(diag), encoding='utf-8')

    print(f"OK: {diag['summary']['non_empty_cells']} celulas, {diag['summary']['formulas']} formulas")
    print(f"JSON: {json_path}")
    print(f"MD:   {md_path}")


if __name__ == '__main__':
    main()
