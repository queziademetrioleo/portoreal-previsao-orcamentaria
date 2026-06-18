#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GERADOR DE PREVISAO ORCAMENTARIA
Usa o modelo_previsao.xlsx como template VISUAL (layout, cores, colunas)
e preenche com os dados extraidos de cada condominio.

Template fixo = visual (cabecalhos, formatacao, abas)
Conteudo dinamico = contas preenchidas conforme os dados reais
"""

import os, re, datetime, unicodedata, warnings, shutil
warnings.filterwarnings('ignore')
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from collections import defaultdict

THIN = Side(style='thin', color='B0B7C3')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
SUB_FILL = PatternFill('solid', fgColor='D6E4F0')
MONEY = '#,##0.00'

MESES_PT = ['janeiro', 'fevereiro', 'marco', 'abril', 'maio', 'junho',
            'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']


def _norm(s):
    s = str(s or '').lower().strip()
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


def gerar_previsao_adaptativa(destino, R, nome_condominio, ano,
                               num_fracoes=None, inflacao=0.10,
                               impacto_receita_mensal=0.0,
                               inad_detalhe=None, inad_meta=None,
                               referencia=None):
    """
    Gera Previsao.xlsx:
    1. Se tem referencia, clona o layout e substitui valores
    2. Senao, gera do zero com layout padrao
    """
    if referencia and os.path.exists(referencia):
        return _gerar_via_template(referencia, destino, R, nome_condominio, ano,
                                   num_fracoes, inflacao, inad_detalhe, inad_meta)
    else:
        return _gerar_do_zero(destino, R, nome_condominio, ano,
                              num_fracoes, inflacao, inad_detalhe, inad_meta)


# ===========================================================================
# Geração via template (clona layout, substitui valores)
# ===========================================================================
def _gerar_via_template(template_path, destino, R, nome_condominio, ano,
                        num_fracoes, inflacao, inad_detalhe, inad_meta):
    """Clona o template e preenche com os dados do condominio."""
    shutil.copy2(template_path, destino)
    wb = openpyxl.load_workbook(destino)
    bal = R['bal']
    linhas = R['linhas']
    num_frac = num_fracoes or 1
    hoje = datetime.date.today()
    data_ext = f'{hoje.day} de {MESES_PT[hoje.month - 1]} de {hoje.year}'

    # Construir mapa: nome normalizado -> final calculado
    valores = {}
    for l in linhas:
        nc = _norm(l['classe'])
        valores[nc] = l['final']
        # Tambem indexa pelo grupo
        ng = _norm(l['grupo'] or '')
        valores[ng] = valores.get(ng, 0) + l['final']

    # ---------- CONTAS ----------
    if ' C O N T A S ' in wb.sheetnames:
        ws_c = wb[' C O N T A S ']

        # Atualizar Confronto Inicial
        for r in range(1, 10):
            n3 = _norm(ws_c.cell(r, 3).value)
            if 'valor transportado' in n3:
                ws_c.cell(r, 4).value = round(R['base_total'], 2)
            elif 'desconsidera' in n3:
                ws_c.cell(r, 4).value = round(R['desconsideracoes'], 2)
            elif 'subtotal inicial' in n3:
                ws_c.cell(r, 4).value = round(R['base_total'] - R['desconsideracoes'], 2)
            elif 'subtotal atual' in n3:
                ws_c.cell(r, 4).value = round(R['subtotal'], 2)

        # Receitas — procura cada conta de receita e atualiza D
        for ln in bal.get('receitas', []):
            nc = _norm(ln['classe'])
            for r in range(1, ws_c.max_row + 1):
                nn = _norm(ws_c.cell(r, 3).value)
                if nn == nc:
                    val = round(ln['total'] / 12.0, 2)
                    ws_c.cell(r, 4).value = val
                    ws_c.cell(r, 9).value = val
                    break

        # Despesas — percorre linhas do template e atualiza com valores calculados
        for r in range(1, ws_c.max_row + 1):
            code = str(ws_c.cell(r, 2).value or '').strip()
            nome = str(ws_c.cell(r, 3).value or '').strip()
            if not nome:
                continue
            nn = _norm(nome)

            # Match exato primeiro
            val = valores.get(nn)
            # Match parcial
            if val is None:
                for vn, vv in valores.items():
                    if len(nn) > 5 and len(vn) > 5 and (nn in vn or vn in nn):
                        val = vv
                        break

            if val is not None and abs(val) > 0.005:
                # Linha de conta individual (XX.YY) ou grupo (XX)
                if re.match(r'^\d{2}(\.\d{2})?$', code):
                    ws_c.cell(r, 4).value = round(val, 2)
                    ws_c.cell(r, 9).value = round(val, 2)
                elif re.match(r'^\d{2}$', code):
                    ws_c.cell(r, 4).value = round(val, 2)
                    ws_c.cell(r, 9).value = round(val, 2)

    # ---------- PREVISAO ----------
    ws_p = None
    for nome in wb.sheetnames:
        if 'REVIS' in nome.upper() and '(2)' not in nome:
            ws_p = wb[nome]
            break

    if ws_p:
        # Atualizar cabecalho
        for r in range(1, 10):
            v = ws_p.cell(r, 1).value
            if isinstance(v, str) and ('PREVIS' in v.upper() or 'ORCAMENT' in v.upper()):
                ws_p.cell(r, 1).value = f'PREVISAO ORCAMENTARIA PARA {ano}'
            if isinstance(v, str) and 'BARRAMARES' in v.upper():
                ws_p.cell(r, 1).value = nome_condominio

        # Receitas
        for ln in bal.get('receitas', []):
            nc = _norm(ln['classe'])
            for r in range(1, ws_p.max_row + 1):
                nn = _norm(ws_p.cell(r, 3).value)
                if nn == nc:
                    val = round(ln['total'] / 12.0, 2)
                    ws_p.cell(r, 4).value = val
                    ws_p.cell(r, 5).value = val
                    break

        # Despesas — atualiza linhas existentes com valores calculados
        for r in range(1, ws_p.max_row + 1):
            nome = str(ws_p.cell(r, 3).value or '').strip()
            if not nome:
                continue
            nn = _norm(nome)

            # Pular cabecalhos
            if nn in ('receitas', 'despesas', 'subtotal',
                       'previsao de inflacao', 'total'):
                continue
            if 'saldo' in nn or 'deficit' in nn or 'superavit' in nn:
                continue
            if 'infla' in nn and 'previsao' in nn:
                continue

            # Buscar valor
            val = valores.get(nn)
            if val is None:
                for vn, vv in valores.items():
                    if len(nn) > 5 and len(vn) > 5 and (nn in vn or vn in nn):
                        val = vv
                        break

            if val is not None and abs(val) > 0.005:
                ws_p.cell(r, 4).value = round(val, 2)
                ws_p.cell(r, 5).value = round(val / num_frac, 2)
                ws_p.cell(r, 6).value = round(val / 12, 2)

        # SUBTOTAL, INFLACAO, TOTAL, SALDO
        subtotal_val = R.get('subtotal', 0)
        for r in range(1, ws_p.max_row + 1):
            n3 = _norm(ws_p.cell(r, 3).value)
            if 'subtotal' in n3:
                ws_p.cell(r, 4).value = round(subtotal_val, 2)
                ws_p.cell(r, 6).value = round(subtotal_val / 12, 2)
            elif 'infla' in n3 and 'previsao' in n3:
                ws_p.cell(r, 4).value = round(subtotal_val * inflacao, 2)
            elif n3 == 'total':
                total = subtotal_val * (1 + inflacao)
                ws_p.cell(r, 4).value = round(total, 2)
                ws_p.cell(r, 5).value = round(total / num_frac, 2)
            elif 'saldo' in n3 or 'deficit' in n3 or 'superavit' in n3:
                rec_anual = sum(ln['total'] for ln in bal.get('receitas', []))
                total = subtotal_val * (1 + inflacao)
                ws_p.cell(r, 4).value = round(rec_anual - total, 2)

    # ---------- PREVISAO (2) ----------
    for nome in wb.sheetnames:
        if 'REVIS' in nome.upper() and '(2)' in nome:
            ws_p2 = wb[nome]
            ws_p2['E11'] = num_frac
            break

    # ---------- Inadimplencia ----------
    if inad_detalhe:
        _criar_aba_inad(wb, inad_detalhe, inad_meta, nome_condominio)

    wb.save(destino)
    return {'ok': True, 'modo': 'template'}


# ===========================================================================
# Geração do zero (fallback sem template)
# ===========================================================================
def _gerar_do_zero(destino, R, nome_condominio, ano, num_fracoes, inflacao,
                    inad_detalhe, inad_meta):
    """Gera Previsao do zero com layout padrao."""
    bal = R['bal']
    linhas = R['linhas']
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    num_frac = num_fracoes or 1
    hoje = datetime.date.today()
    data_ext = f'{hoje.day} de {MESES_PT[hoje.month - 1]} de {hoje.year}'

    ORDEM_GRUPOS = [
        'Despesas com Pessoal', 'Tarifas Publicas', 'Conservacao',
        'Tarifas Bancarias', 'Despesas Diversas', 'Contratos',
        'Despesas Cartoriais e Honorarios', 'Despesas Administrativas',
        'Reembolso/Pro-labore ao Sindico', 'Despesas com Obras/Benfeitorias',
    ]

    # CONTAS
    ws_c = wb.create_sheet(' C O N T A S ')
    for col, w in zip('ABCDEFGHI', [5, 12, 48, 16, 16, 14, 14, 14, 16]):
        ws_c.column_dimensions[col].width = w
    r = 1
    ws_c.cell(r, 3, 'Confronto Inicial').font = Font(bold=True, size=13)
    r += 2
    ws_c.cell(r, 3, 'Valor Transportado')
    ws_c.cell(r, 4, round(R['base_total'], 2)).number_format = MONEY
    r += 1
    ws_c.cell(r, 3, 'Desconsideracoes')
    ws_c.cell(r, 4, round(R['desconsideracoes'], 2)).number_format = MONEY
    r += 1
    ws_c.cell(r, 3, 'Subtotal Inicial').font = Font(bold=True)
    ws_c.cell(r, 4, round(R['base_total'] - R['desconsideracoes'], 2)).number_format = MONEY
    r += 2

    # Receitas no CONTAS
    r_ini = r
    cod = 1
    for ln in bal.get('receitas', []):
        ws_c.cell(r, 2, f'01.{cod:02d}')
        ws_c.cell(r, 3, ln['classe'])
        ws_c.cell(r, 4, round(ln['total'] / 12.0, 2)).number_format = MONEY
        ws_c.cell(r, 9, round(ln['total'] / 12.0, 2)).number_format = MONEY
        cod += 1
        r += 1
    r += 1

    # Despesas
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
            cod_classe += 1
            r += 1
        cod_grupo += 1

    r += 1
    ws_c.cell(r, 3, 'Subtotal Atual').font = Font(bold=True, size=12)
    ws_c.cell(r, 4, round(R['subtotal'], 2)).number_format = MONEY

    # PREVISAO
    ws_p = wb.create_sheet(' P R E V I S A O ')
    for col, w in zip('ABCDEF', [5, 8, 52, 18, 18, 18]):
        ws_p.column_dimensions[col].width = w
    r = 6
    ws_p.cell(r, 1, nome_condominio).font = Font(bold=True, size=13)
    r += 1
    ws_p.cell(r, 1, f'PREVISAO ORCAMENTARIA PARA {ano}').font = Font(bold=True, size=13)
    r += 1
    ws_p.cell(r, 1, data_ext).font = Font(italic=True)
    r = 9
    ws_p.cell(r, 3, 'RECEITAS').font = Font(bold=True)
    ws_p.cell(r, 4, 'VALOR MENSAL').font = Font(bold=True)
    r += 1
    rec_total = 0
    for ln in bal.get('receitas', []):
        val = round(ln['total'] / 12.0, 2)
        ws_p.cell(r, 3, ln['classe'])
        ws_p.cell(r, 4, val).number_format = MONEY
        ws_p.cell(r, 5, val).number_format = MONEY
        rec_total += val
        r += 1
    r += 1
    ws_p.cell(r, 3, 'TOTAL').font = Font(bold=True)
    ws_p.cell(r, 4, round(rec_total, 2)).number_format = MONEY
    r += 2
    ws_p.cell(r, 3, 'DESPESAS').font = Font(bold=True)
    ws_p.cell(r, 4, 'VALOR ANUAL').font = Font(bold=True)
    r += 1
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
        ws_p.cell(r, 2, idx)
        ws_p.cell(r, 3, grupo_nome)
        ws_p.cell(r, 4, round(final_g, 2)).number_format = MONEY
        ws_p.cell(r, 5, round(final_g / num_frac, 2)).number_format = MONEY
        ws_p.cell(r, 6, round(final_g / 12, 2)).number_format = MONEY
        despesa_total += final_g
        idx += 1
        r += 1
    r += 1
    ws_p.cell(r, 3, 'SUBTOTAL').font = Font(bold=True)
    ws_p.cell(r, 4, round(despesa_total, 2)).number_format = MONEY
    r += 1
    inflacao_val = despesa_total * inflacao
    ws_p.cell(r, 2, 99)
    ws_p.cell(r, 3, f'PREVISAO DE INFLACAO - {inflacao*100:.0f}%')
    ws_p.cell(r, 4, round(inflacao_val, 2)).number_format = MONEY
    r += 2
    total = despesa_total + inflacao_val
    ws_p.cell(r, 3, 'TOTAL').font = Font(bold=True, size=12)
    ws_p.cell(r, 4, round(total, 2)).number_format = MONEY
    r += 2
    rec_anual = rec_total * 12
    saldo = rec_anual - total
    ws_p.cell(r, 3, 'SALDO (DEFICIT)' if saldo < 0 else 'SALDO (SUPERAVIT)').font = Font(bold=True, size=12)
    ws_p.cell(r, 4, round(saldo, 2)).number_format = MONEY

    # Demais abas
    wb.create_sheet(' P R E V I S A O  (2)')
    wb.create_sheet('Cadastro')
    wb.create_sheet(' G R A F I C O')
    wb.create_sheet('Comp. Desp-Rec')

    if inad_detalhe:
        _criar_aba_inad(wb, inad_detalhe, inad_meta, nome_condominio)

    wb.save(destino)
    return {'ok': True, 'modo': 'zero'}


def _criar_aba_inad(wb, inad_detalhe, inad_meta, nome_condominio):
    """Cria aba de Inadimplencia."""
    azul = PatternFill('solid', fgColor='1F3864')
    amarelo = PatternFill('solid', fgColor='FFF2CC')
    branco_negrito = Font(bold=True, color='FFFFFF')
    wsi = wb.create_sheet('Inadimplencia')
    wsi['A1'] = f'INADIMPLENCIA - {nome_condominio}'
    wsi['A1'].font = Font(bold=True, size=13)
    if inad_meta:
        wsi['A2'] = f"Data-base: {inad_meta.get('data_base', '')} | >= 3 meses consecutivos"
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
