#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GERADOR ADAPTATIVO DE PREVISAO ORCAMENTARIA
Gera o arquivo Previsao.xlsx do zero, SEM template fixo,
adaptando-se automaticamente a estrutura de cada condominio.

Formato de saida identico ao manual da Porto Real (7 abas).
"""

import os, sys, re, datetime, unicodedata, warnings
warnings.filterwarnings('ignore')
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from collections import defaultdict

MESES_PT = ['janeiro', 'fevereiro', 'marco', 'abril', 'maio', 'junho',
            'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

THIN = Side(style='thin', color='B0B7C3')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HDR_FILL = PatternFill('solid', fgColor='1F3864')
HDR_FONT = Font(bold=True, color='FFFFFF', size=10)
SUB_FILL = PatternFill('solid', fgColor='D6E4F0')
MONEY = '#,##0.00'

# Ordem padrao dos grupos na PREVISAO (como o manual)
ORDEM_GRUPOS = [
    'Despesas com Pessoal',
    'Tarifas Publicas',
    'Conservacao',
    'Tarifas Bancarias',
    'Despesas Diversas',
    'Contratos',
    'Despesas Cartoriais e Honorarios',
    'Despesas Administrativas',
    'Reembolso/Pro-labore ao Sindico',
    'Despesas com Obras/Benfeitorias',
]


def _norm(s):
    s = str(s or '').lower().strip()
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


def _num(v):
    try:
        f = float(v)
        return f if abs(f) > 1e-10 else 0.0
    except Exception:
        return 0.0


def gerar_previsao_adaptativa(destino, R, nome_condominio, ano,
                               num_fracoes=None, inflacao=0.10,
                               impacto_receita_mensal=0.0,
                               inad_detalhe=None, inad_meta=None,
                               referencia=None):
    """
    Gera Previsao.xlsx.
    Se 'referencia' for um arquivo Previsao.xlsx de referencia, COPIA o layout
    dele (abas, formulas, formatacao) e substitui os valores pelos calculados.
    Caso contrario, gera do zero.
    R = resultado de core.analisar() ou core.recalcular()
    """
    bal = R['bal']
    linhas = R['linhas']

    num_frac = num_fracoes or 1
    hoje = datetime.date.today()
    data_ext = f'{hoje.day} de {MESES_PT[hoje.month - 1]} de {hoje.year}'

    # Se tem referencia, clonar layout dela
    if referencia and os.path.exists(referencia):
        return _gerar_com_referencia(referencia, destino, R, nome_condominio, ano,
                                     num_frac, inflacao, impacto_receita_mensal,
                                     inad_detalhe, inad_meta, data_ext)

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # ===================================================================
    # ABA 1: CONTAS
    # ===================================================================
    ws_c = wb.create_sheet(' C O N T A S ')
    for col, w in zip('ABCDEFGHI', [5, 12, 48, 16, 16, 14, 14, 14, 16]):
        ws_c.column_dimensions[col].width = w

    r = 1
    ws_c.cell(r, 3, 'Confronto Inicial').font = Font(bold=True, size=13)
    r += 2

    # Valor Transportado
    ws_c.cell(r, 3, 'Valor Transportado')
    ws_c.cell(r, 4, round(R['base_total'], 2)).number_format = MONEY
    sin_total = R.get('sin', {}).get('grand_total') or R['base_total']
    ws_c.cell(r, 5, round(sin_total, 2)).number_format = MONEY
    ws_c.cell(r, 6, 'Diferenca').font = Font(italic=True)
    ws_c.cell(r, 7, round(sin_total - R['base_total'], 2)).number_format = MONEY
    r += 1

    # Desconsideracoes
    ws_c.cell(r, 3, 'Desconsideracoes')
    ws_c.cell(r, 4, round(R['desconsideracoes'], 2)).number_format = MONEY
    r += 1

    # Subtotal Inicial
    ws_c.cell(r, 3, 'Subtotal Inicial').font = Font(bold=True)
    ws_c.cell(r, 4, round(R['base_total'] - R['desconsideracoes'], 2)).number_format = MONEY
    r += 2

    # Plano Basico
    ws_c.cell(r, 2, '-').font = Font(bold=True)
    ws_c.cell(r, 3, 'Plano Basico').font = Font(bold=True)
    r += 1

    # Receitas
    ws_c.cell(r, 3, 'Receitas Operacionais (mes)').font = Font(bold=True)
    r += 1
    cod = 1
    for ln in bal.get('receitas', []):
        ws_c.cell(r, 2, f'01.{cod:02d}')
        ws_c.cell(r, 3, ln['classe'])
        ws_c.cell(r, 4, round(ln['total'] / 12.0, 2)).number_format = MONEY
        ws_c.cell(r, 9, round(ln['total'] / 12.0, 2)).number_format = MONEY
        cod += 1
        r += 1

    r += 1

    # Agrupar despesas
    por_grupo = defaultdict(list)
    for l in linhas:
        por_grupo[l['grupo'] or 'Outros'].append(l)

    cod_grupo = 2
    for grupo_nome in ORDEM_GRUPOS:
        match_key = None
        for g in por_grupo:
            if _norm(grupo_nome) in _norm(g) or _norm(g) in _norm(grupo_nome):
                match_key = g
                break
        if match_key is None:
            continue
        linhas_grupo = por_grupo.pop(match_key)
        if not linhas_grupo:
            continue

        # Linha do grupo
        base_g = sum(l['base'] for l in linhas_grupo)
        final_g = sum(l['final'] for l in linhas_grupo)
        ws_c.cell(r, 2, f'{cod_grupo:02d}')
        ws_c.cell(r, 3, grupo_nome).font = Font(bold=True)
        ws_c.cell(r, 4, round(base_g, 2)).number_format = MONEY
        ws_c.cell(r, 9, round(final_g, 2)).number_format = MONEY
        for c in range(1, 10):
            ws_c.cell(r, c).fill = SUB_FILL
        r += 1

        cod_classe = 1
        for l in linhas_grupo:
            ws_c.cell(r, 2, f'{cod_grupo:02d}.{cod_classe:02d}')
            ws_c.cell(r, 3, l['classe'])
            ws_c.cell(r, 4, round(l['base'], 2)).number_format = MONEY
            if abs(l['deducao']) > 0.005:
                ws_c.cell(r, 5, round(l['deducao'], 2)).number_format = MONEY
            ws_c.cell(r, 9, round(l['final'], 2)).number_format = MONEY
            ws_c.cell(r, 6, l['n_meses'])
            ws_c.cell(r, 7, l['regra']).font = Font(size=8, italic=True)
            cod_classe += 1
            r += 1
        cod_grupo += 1

    # Grupos restantes
    for g, linhas_grupo in por_grupo.items():
        base_g = sum(l['base'] for l in linhas_grupo)
        final_g = sum(l['final'] for l in linhas_grupo)
        if abs(final_g) < 0.005:
            continue
        ws_c.cell(r, 2, f'{cod_grupo:02d}')
        ws_c.cell(r, 3, g).font = Font(bold=True)
        ws_c.cell(r, 4, round(base_g, 2)).number_format = MONEY
        ws_c.cell(r, 9, round(final_g, 2)).number_format = MONEY
        for c in range(1, 10):
            ws_c.cell(r, c).fill = SUB_FILL
        r += 1
        cod_grupo += 1

    # Subtotal Atual
    r += 1
    ws_c.cell(r, 3, 'Subtotal Atual').font = Font(bold=True, size=12)
    ws_c.cell(r, 4, round(R['subtotal'], 2)).number_format = MONEY

    # ===================================================================
    # ABA 2: PREVISAO
    # ===================================================================
    ws_p = wb.create_sheet(' P R E V I S A O ')
    for col, w in zip('ABCDEFGH', [5, 8, 52, 18, 18, 18, 18, 18]):
        ws_p.column_dimensions[col].width = w

    r = 6
    ws_p.cell(r, 1, nome_condominio).font = Font(bold=True, size=13)
    r += 1
    ws_p.cell(r, 1, f'PREVISAO ORCAMENTARIA PARA {ano}').font = Font(bold=True, size=13)
    r += 1
    ws_p.cell(r, 1, data_ext).font = Font(italic=True)

    # RECEITAS
    r = 9
    ws_p.cell(r, 3, 'RECEITAS').font = Font(bold=True)
    ws_p.cell(r, 4, 'VALOR MENSAL').font = Font(bold=True)
    r += 1
    rec_total = 0
    for ln in bal.get('receitas', []):
        val = round(ln['total'] / 12.0, 2)
        ws_p.cell(r, 2, '')
        ws_p.cell(r, 3, ln['classe'])
        ws_p.cell(r, 4, val).number_format = MONEY
        ws_p.cell(r, 5, val).number_format = MONEY
        rec_total += val
        r += 1

    r += 1
    ws_p.cell(r, 3, 'TOTAL').font = Font(bold=True)
    ws_p.cell(r, 4, round(rec_total, 2)).number_format = MONEY
    ws_p.cell(r, 4).font = Font(bold=True)

    # DESPESAS
    r += 2
    ws_p.cell(r, 3, 'DESPESAS').font = Font(bold=True)
    ws_p.cell(r, 4, 'VALOR ANUAL').font = Font(bold=True)
    ws_p.cell(r, 5, 'VALOR POR FRACAO').font = Font(bold=True)
    ws_p.cell(r, 6, 'VALOR MENSAL').font = Font(bold=True)
    r += 1

    # Re-agrupar
    por_grupo2 = defaultdict(list)
    for l in linhas:
        por_grupo2[l['grupo'] or 'Outros'].append(l)

    despesa_total = 0
    idx = 1

    for grupo_nome in ORDEM_GRUPOS:
        match_key = None
        for g in por_grupo2:
            if _norm(grupo_nome) in _norm(g) or _norm(g) in _norm(grupo_nome):
                match_key = g
                break
        if match_key is None:
            continue
        linhas_grupo = por_grupo2.pop(match_key)
        final_g = sum(l['final'] for l in linhas_grupo)
        if abs(final_g) < 0.005:
            continue

        ws_p.cell(r, 1, '')
        ws_p.cell(r, 2, idx)
        ws_p.cell(r, 3, grupo_nome)
        ws_p.cell(r, 4, round(final_g, 2)).number_format = MONEY
        ws_p.cell(r, 5, round(final_g / num_frac, 2)).number_format = MONEY
        ws_p.cell(r, 6, round(final_g / 12, 2)).number_format = MONEY
        despesa_total += final_g
        idx += 1
        r += 1

    # Grupos restantes
    for g, linhas_grupo in por_grupo2.items():
        final_g = sum(l['final'] for l in linhas_grupo)
        if abs(final_g) < 0.005:
            continue
        ws_p.cell(r, 2, idx)
        ws_p.cell(r, 3, g)
        ws_p.cell(r, 4, round(final_g, 2)).number_format = MONEY
        ws_p.cell(r, 5, round(final_g / num_frac, 2)).number_format = MONEY
        ws_p.cell(r, 6, round(final_g / 12, 2)).number_format = MONEY
        despesa_total += final_g
        idx += 1
        r += 1

    # SUBTOTAL
    r += 1
    ws_p.cell(r, 3, 'SUBTOTAL').font = Font(bold=True)
    ws_p.cell(r, 4, round(despesa_total, 2)).number_format = MONEY
    ws_p.cell(r, 4).font = Font(bold=True)
    ws_p.cell(r, 5, 'Inflacao').font = Font(bold=True)
    ws_p.cell(r, 6, round(despesa_total / 12, 2)).number_format = MONEY
    ws_p.cell(r, 6).font = Font(bold=True)

    # INFLAcaO
    r += 1
    inflacao_val = despesa_total * inflacao
    ws_p.cell(r, 2, 99)
    ws_p.cell(r, 3, f'PREVISAO DE INFLAcaO - {inflacao*100:.0f}%')
    ws_p.cell(r, 4, round(inflacao_val, 2)).number_format = MONEY
    ws_p.cell(r, 5, inflacao).number_format = '0%'

    # TOTAL
    r += 2
    total_despesas = despesa_total + inflacao_val
    ws_p.cell(r, 3, 'TOTAL').font = Font(bold=True, size=12)
    ws_p.cell(r, 4, round(total_despesas, 2)).number_format = MONEY
    ws_p.cell(r, 4).font = Font(bold=True)
    ws_p.cell(r, 5, round(total_despesas / num_frac, 2)).number_format = MONEY
    ws_p.cell(r, 5).font = Font(bold=True)

    # SALDO
    r += 2
    rec_anual = rec_total * 12
    saldo = rec_anual - total_despesas
    if saldo < 0:
        ws_p.cell(r, 3, 'SALDO (DEFICIT)').font = Font(bold=True, size=12, color='CC0000')
    else:
        ws_p.cell(r, 3, 'SALDO (SUPERAVIT)').font = Font(bold=True, size=12, color='006600')
    ws_p.cell(r, 4, round(saldo, 2)).number_format = MONEY
    ws_p.cell(r, 4).font = Font(bold=True)

    # ===================================================================
    # ABA 3: PREVISAO (2) - por fracao
    # ===================================================================
    ws_p2 = wb.create_sheet(' P R E V I S A O  (2)')
    ws_p2['A6'] = nome_condominio
    ws_p2['A8'] = f'PREVISAO ORCAMENTARIA PARA {ano}'
    ws_p2['E11'] = num_frac

    r = 10
    ws_p2.cell(r, 3, 'RECEITAS').font = Font(bold=True)
    ws_p2.cell(r, 4, 'VALOR MEDIO MENSAL').font = Font(bold=True)
    r += 1
    for i, ln in enumerate(bal.get('receitas', []), 1):
        ws_p2.cell(r, 2, i)
        ws_p2.cell(r, 3, ln['classe'])
        ws_p2.cell(r, 4, round(ln['total'] / 12.0, 2)).number_format = MONEY
        r += 1
    r += 1
    ws_p2.cell(r, 3, 'TOTAL')
    ws_p2.cell(r, 4, round(rec_total, 2)).number_format = MONEY

    r += 2
    ws_p2.cell(r, 3, 'DESPESAS').font = Font(bold=True)
    ws_p2.cell(r, 4, 'VALOR MEDIO MENSAL').font = Font(bold=True)
    r += 1
    for i, (grupo_nome, final_g) in enumerate([
        (gn, sum(l['final'] for l in linhas if (l['grupo'] or '') == gn or
         _norm(gn) in _norm(l['grupo'] or ''))) for gn in ORDEM_GRUPOS
    ], 1):
        if abs(final_g) < 0.005:
            continue
        ws_p2.cell(r, 2, i)
        ws_p2.cell(r, 3, grupo_nome)
        ws_p2.cell(r, 4, round(final_g / 12, 2)).number_format = MONEY
        r += 1

    # ===================================================================
    # Demais abas
    # ===================================================================
    wb.create_sheet('Cadastro')
    wb.create_sheet(' G R A F I C O')
    wb.create_sheet('Comp. Desp-Rec')

    # ===================================================================
    # ABA: Inadimplencia
    # ===================================================================
    if inad_detalhe:
        wsi = wb.create_sheet('Inadimplencia')
        azul = PatternFill('solid', fgColor='1F3864')
        amarelo = PatternFill('solid', fgColor='FFF2CC')
        branco_negrito = Font(bold=True, color='FFFFFF')

        wsi['A1'] = f'INADIMPLENCIA - {nome_condominio}'
        wsi['A1'].font = Font(bold=True, size=13)
        if inad_meta:
            wsi['A2'] = f"Data-base: {inad_meta.get('data_base', '')} | Criterio: >= 3 meses consecutivos"
            wsi['A2'].font = Font(italic=True, color='5A6472')

        cab = ['Unidade / Devedor', 'Classe', 'Mes Ref.', 'Vencimento', 'Valor (R$)',
               'Meses atraso', 'Situacao', 'Decisao']
        for j, h in enumerate(cab, 1):
            c = wsi.cell(4, j, h)
            c.fill = azul; c.font = branco_negrito; c.border = BORDER
            c.alignment = Alignment(horizontal='center', wrap_text=True)
        for w, col in zip([34, 22, 10, 12, 12, 13, 18, 26], 'ABCDEFGH'):
            wsi.column_dimensions[col].width = w

        rr = 5
        for it in sorted(inad_detalhe, key=lambda x: -(x.get('meses_atraso') or 0)):
            wsi.cell(rr, 1, it.get('unidade')).border = BORDER
            wsi.cell(rr, 2, it.get('classe')).border = BORDER
            wsi.cell(rr, 3, it.get('mes_ref')).border = BORDER
            wsi.cell(rr, 4, str(it.get('vencimento') or '')).border = BORDER
            c = wsi.cell(rr, 5, it.get('valor')); c.number_format = MONEY; c.border = BORDER
            wsi.cell(rr, 6, it.get('meses_atraso')).border = BORDER
            critica = bool(it.get('critica'))
            wsi.cell(rr, 7, 'CRITICA (>= 3 meses)' if critica else 'Recente').border = BORDER
            dec = it.get('decisao')
            wsi.cell(rr, 8, 'Abatida da receita' if dec == 'abater' else 'Mantida').border = BORDER
            if critica:
                for j in range(1, 9):
                    wsi.cell(rr, j).fill = amarelo
            rr += 1

    wb.save(destino)
    return {'ok': True}


# ---------------------------------------------------------------------------
# Geracao COM referencia: clona o layout do manual e substitui valores
# ---------------------------------------------------------------------------
def _gerar_com_referencia(ref_path, destino, R, nome_condominio, ano,
                          num_frac, inflacao, impacto_receita_mensal,
                          inad_detalhe, inad_meta, data_ext):
    """Clona o arquivo de referencia, substituindo os valores pelos calculados."""
    import shutil
    shutil.copy2(ref_path, destino)
    wb = openpyxl.load_workbook(destino)
    bal = R['bal']
    linhas = R['linhas']

    # --- Construir indice: nome da conta -> final calculado ---
    valores_por_nome = {}
    for l in linhas:
        nc = _norm(l['classe'])
        valores_por_nome[nc] = l['final']
        # Tambem indexa pelo grupo
        ng = _norm(l['grupo'] or '')
        if ng not in valores_por_nome:
            valores_por_nome[ng] = 0.0
        valores_por_nome[ng] += l['final']

    # --- Atualizar CONTAS com valores calculados ---
    if ' C O N T A S ' in wb.sheetnames:
        ws_c = wb[' C O N T A S ']
        for r in range(1, ws_c.max_row + 1):
            nome = str(ws_c.cell(r, 3).value or '').strip()
            code = str(ws_c.cell(r, 2).value or '').strip()
            if not nome:
                continue

            nn = _norm(nome)
            # Buscar valor calculado
            val = None
            if nn in valores_por_nome:
                val = valores_por_nome[nn]
            else:
                # Tentar match parcial
                for vn, vv in valores_por_nome.items():
                    if len(nn) > 4 and len(vn) > 4 and (nn in vn or vn in nn):
                        val = vv
                        break

            if val is not None and abs(val) > 0.005:
                if re.match(r'^\d{2}\.\d{2}$', code):
                    # Conta individual: D = base anual, I = final
                    ws_c.cell(r, 4).value = round(val, 2)
                    ws_c.cell(r, 9).value = round(val, 2)
                elif re.match(r'^\d{2}$', code):
                    # Grupo: D e I = soma do grupo
                    ws_c.cell(r, 4).value = round(val, 2)
                    ws_c.cell(r, 9).value = round(val, 2)

        # Atualizar Confronto Inicial
        for r in range(1, 10):
            n3 = _norm(ws_c.cell(r, 3).value)
            if 'valor transportado' in n3:
                ws_c.cell(r, 4).value = round(R['base_total'], 2)
            elif 'desconsideracoes' in n3 or 'desconsiderações' in n3:
                ws_c.cell(r, 4).value = round(R['desconsideracoes'], 2)
            elif 'subtotal inicial' in n3:
                ws_c.cell(r, 4).value = round(R['base_total'] - R['desconsideracoes'], 2)
            elif 'subtotal atual' in n3:
                ws_c.cell(r, 4).value = round(R['subtotal'], 2)

        # Receitas: atualizar com media mensal
        for ln in bal.get('receitas', []):
            nc = _norm(ln['classe'])
            for r in range(1, ws_c.max_row + 1):
                if _norm(ws_c.cell(r, 3).value) == nc:
                    ws_c.cell(r, 4).value = round(ln['total'] / 12.0, 2)
                    ws_c.cell(r, 9).value = round(ln['total'] / 12.0, 2)
                    break

    # --- Atualizar PREVISAO com valores calculados ---
    if ' P R E V I S Ã O ' in wb.sheetnames:
        ws_p = wb[' P R E V I S Ã O ']
        for r in range(1, ws_p.max_row + 1):
            nome = str(ws_p.cell(r, 3).value or '').strip()
            if not nome:
                continue
            nn = _norm(nome)

            # Pular cabecalhos
            if nn in ('receitas', 'despesas', 'total', 'subtotal',
                       'previsao de inflacao'):
                continue
            if 'saldo' in nn or 'deficit' in nn or 'superavit' in nn:
                continue

            # Buscar valor
            val = None
            if nn in valores_por_nome:
                val = valores_por_nome[nn]
            else:
                for vn, vv in valores_por_nome.items():
                    if len(nn) > 4 and len(vn) > 4 and (nn in vn or vn in nn):
                        val = vv
                        break

            if val is not None and abs(val) > 0.005:
                # Coluna D = VALOR ANUAL
                ws_p.cell(r, 4).value = round(val, 2)
                # Coluna E = valor por fracao
                ws_p.cell(r, 5).value = round(val / num_frac, 2)
                # Coluna F = valor mensal
                ws_p.cell(r, 6).value = round(val / 12, 2)

        # Receitas
        for ln in bal.get('receitas', []):
            nc = _norm(ln['classe'])
            for r in range(1, ws_p.max_row + 1):
                if _norm(ws_p.cell(r, 3).value) == nc:
                    val = round(ln['total'] / 12.0, 2)
                    ws_p.cell(r, 4).value = val
                    ws_p.cell(r, 5).value = val
                    break

        # SUBTOTAL, INFLACAO, TOTAL, SALDO
        for r in range(1, ws_p.max_row + 1):
            n3 = _norm(ws_p.cell(r, 3).value)
            if 'subtotal' in n3:
                ws_p.cell(r, 4).value = round(R['subtotal'], 2)
                ws_p.cell(r, 6).value = round(R['subtotal'] / 12, 2)
            elif 'infla' in n3 and 'previsao' in n3:
                ws_p.cell(r, 4).value = round(R['subtotal'] * inflacao, 2)
            elif n3 == 'total':
                total = R['subtotal'] * (1 + inflacao)
                ws_p.cell(r, 4).value = round(total, 2)
                ws_p.cell(r, 5).value = round(total / num_frac, 2)
            elif 'saldo' in n3 or 'deficit' in n3 or 'superavit' in n3:
                rec_total = sum(ln['total'] / 12.0 for ln in bal.get('receitas', []))
                total = R['subtotal'] * (1 + inflacao)
                ws_p.cell(r, 4).value = round(rec_total * 12 - total, 2)

        # Atualizar titulo e data
        for r in range(1, 10):
            v = ws_p.cell(r, 1).value
            if isinstance(v, str) and 'PREVIS' in v.upper():
                ws_p.cell(r, 1).value = f'PREVISAO ORCAMENTARIA PARA {ano}'

    # --- Atualizar PREVISAO(2) ---
    if ' P R E V I S A O  (2)' in wb.sheetnames:
        ws_p2 = wb[' P R E V I S A O  (2)']
        ws_p2['E11'] = num_frac

    # --- Inadimplencia ---
    if inad_detalhe:
        if 'Inadimplencia' in wb.sheetnames:
            wb.remove(wb['Inadimplencia'])
        wsi = wb.create_sheet('Inadimplencia')
        azul = PatternFill('solid', fgColor='1F3864')
        amarelo = PatternFill('solid', fgColor='FFF2CC')
        branco_negrito = Font(bold=True, color='FFFFFF')

        wsi['A1'] = f'INADIMPLENCIA - {nome_condominio}'
        wsi['A1'].font = Font(bold=True, size=13)
        if inad_meta:
            wsi['A2'] = f"Data-base: {inad_meta.get('data_base', '')}"
            wsi['A2'].font = Font(italic=True, color='5A6472')

        cab = ['Unidade / Devedor', 'Classe', 'Mes Ref.', 'Vencimento', 'Valor (R$)',
               'Meses atraso', 'Situacao', 'Decisao']
        for j, h in enumerate(cab, 1):
            c = wsi.cell(4, j, h)
            c.fill = azul; c.font = branco_negrito; c.border = BORDER
            c.alignment = Alignment(horizontal='center', wrap_text=True)
        for w, col in zip([34, 22, 10, 12, 12, 13, 18, 26], 'ABCDEFGH'):
            wsi.column_dimensions[col].width = w

        rr = 5
        for it in sorted(inad_detalhe, key=lambda x: -(x.get('meses_atraso') or 0)):
            for j, (k, fmt) in enumerate([
                ('unidade', None), ('classe', None), ('mes_ref', None),
                ('vencimento', None), ('valor', MONEY), ('meses_atraso', None),
            ], 1):
                v = it.get(k)
                c = wsi.cell(rr, j, str(v) if v is not None else '')
                if fmt:
                    c.number_format = fmt
                c.border = BORDER
            critica = bool(it.get('critica'))
            wsi.cell(rr, 7, 'CRITICA (>= 3 meses)' if critica else 'Recente').border = BORDER
            dec = it.get('decisao')
            wsi.cell(rr, 8, 'Abatida da receita' if dec == 'abater' else 'Mantida').border = BORDER
            if critica:
                for j in range(1, 9):
                    wsi.cell(rr, j).fill = amarelo
            rr += 1

    wb.save(destino)
    return {'ok': True, 'layout': 'referencia'}
