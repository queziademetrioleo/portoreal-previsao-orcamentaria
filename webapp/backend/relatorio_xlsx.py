#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RELATORIO XLSX PARA O CONDOMINIO

Mesmos números do PDF/DOCX (consome `montar_contexto_relatorio`), mas com as
somas em fórmulas: incluir, tirar ou alterar uma conta recalcula total de
receitas, subtotal, aumento previsto, total, opções de custeio, reajuste e o
gráfico mensal ao abrir no Excel / Google Sheets / LibreOffice.

Cada tabela traz linhas em branco dentro do intervalo somado; linhas inseridas
no meio da tabela também entram, porque o Excel estende o SUM sozinho.
"""
import io

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

import previsao as core
from relatorio_pdf import COR_DESPESA_ACIMA, COR_RECEITA_ACIMA, _norm, montar_contexto_relatorio

AZUL = '1C355E'
CINZA = '52514E'
FMT_MOEDA = '"R$" #,##0.00;[Red]-"R$" #,##0.00'
FMT_PCT = '0.0%'
LINHAS_EM_BRANCO = 3
TIPO_ORDINARIA, TIPO_FUNDO, TIPO_ALUGUEL = 'Ordinária', 'Fundo de reserva', 'Aluguel de espaço'

_fino = Side(style='thin', color='C9CED6')
BORDA = Border(top=_fino, bottom=_fino, left=_fino, right=_fino)
F_CAB = PatternFill('solid', fgColor=AZUL)
F_TOTAL = PatternFill('solid', fgColor='E8EDF5')
F_EDITAVEL = PatternFill('solid', fgColor='FFF8E1')


def _tipo_receita(label, aluguel):
    n = _norm(label)
    if 'fundo' in n and 'reserva' in n:
        return TIPO_FUNDO
    if n in aluguel:
        return TIPO_ALUGUEL
    return TIPO_ORDINARIA


def _celula(ws, ref, valor=None, negrito=False, fmt=None, cor=None, fundo=None, borda=True, tamanho=10):
    c = ws[ref]
    if valor is not None:
        c.value = valor
    c.font = Font(name='Arial', size=tamanho, bold=negrito, color=cor)
    if fmt:
        c.number_format = fmt
    if fundo:
        c.fill = fundo
    if borda:
        c.border = BORDA
    return c


def _cabecalho(ws, linha, titulos):
    for col, txt in zip('ABCDEF', titulos):
        c = _celula(ws, f'{col}{linha}', txt, True, cor='FFFFFF', fundo=F_CAB)
        c.alignment = Alignment(horizontal='left' if col == 'A' else 'center', vertical='center', wrap_text=True)


def _secao(ws, linha, txt):
    _celula(ws, f'A{linha}', txt, True, cor=AZUL, borda=False, tamanho=12)


def _aba_previsao(ws, ctx):
    v = ctx['valores']
    ws.title = 'Previsão'
    for col, larg in zip('ABCDEF', (54, 20, 18, 18, 20, 30)):
        ws.column_dimensions[col].width = larg
    _celula(ws, 'A1', f'{ctx["nome_condominio"]} — {ctx["ano_previsao"]}', True, cor=AZUL, borda=False, tamanho=16)
    _celula(ws, 'A2', f'Previsão orçamentária · {ctx["data_extenso"]}', cor=CINZA, borda=False, tamanho=11)
    _celula(ws, 'A3', 'Altere os valores nas células amarelas ou insira linhas dentro das tabelas: '
            'totais, opções de custeio e gráfico se recalculam sozinhos.', cor=CINZA, borda=False, tamanho=9)

    # --- Receitas ---
    lin = 5
    _secao(ws, lin, 'Receitas')
    _cabecalho(ws, lin + 1, ('Conta', 'Tipo', 'Valor mensal', 'Valor anual'))
    tipos = DataValidation(type='list', formula1=f'"{TIPO_ORDINARIA},{TIPO_FUNDO},{TIPO_ALUGUEL}"',
                           allow_blank=True)
    ws.add_data_validation(tipos)
    ini = lin + 2
    linhas = [(l, val, _tipo_receita(l, v['aluguel'])) for l, val in v['receitas']]
    linhas += [(None, None, None)] * LINHAS_EM_BRANCO
    for i, (label, valor, tipo) in enumerate(linhas):
        r = ini + i
        _celula(ws, f'A{r}', label, fundo=F_EDITAVEL)
        _celula(ws, f'B{r}', tipo, fundo=F_EDITAVEL).alignment = Alignment(horizontal='center')
        tipos.add(f'B{r}')
        _celula(ws, f'C{r}', round(valor, 2) if valor is not None else None, fmt=FMT_MOEDA, fundo=F_EDITAVEL)
        _celula(ws, f'D{r}', f'=C{r}*12', fmt=FMT_MOEDA)
    fim = ini + len(linhas) - 1
    tot_rec = fim + 1
    _celula(ws, f'A{tot_rec}', 'Total mensal', True, fundo=F_TOTAL)
    _celula(ws, f'B{tot_rec}', fundo=F_TOTAL)
    _celula(ws, f'C{tot_rec}', f'=SUM(C{ini}:C{fim})', True, FMT_MOEDA, fundo=F_TOTAL)
    _celula(ws, f'D{tot_rec}', f'=SUM(D{ini}:D{fim})', True, FMT_MOEDA, fundo=F_TOTAL)
    soma_tipo = lambda tipo: f'SUMIF($B${ini}:$B${fim},"{tipo}",$C${ini}:$C${fim})'
    fundo = soma_tipo(TIPO_FUNDO)
    aluguel = soma_tipo(TIPO_ALUGUEL)
    # Linha sem tipo conta como ordinária: só fundo e aluguel ficam de fora.
    ordinaria = f'($C${tot_rec}-{fundo}-{aluguel})'

    # --- Despesas ---
    lin = tot_rec + 2
    _secao(ws, lin, 'Despesas')
    _cabecalho(ws, lin + 1, ('Conta', '', 'Valor mensal', 'Valor anual'))
    ini = lin + 2
    linhas = list(v['despesas']) + [(None, None)] * LINHAS_EM_BRANCO
    for i, (label, valor) in enumerate(linhas):
        r = ini + i
        _celula(ws, f'A{r}', label, fundo=F_EDITAVEL)
        _celula(ws, f'B{r}')
        _celula(ws, f'C{r}', round(valor, 2) if valor is not None else None, fmt=FMT_MOEDA, fundo=F_EDITAVEL)
        _celula(ws, f'D{r}', f'=C{r}*12', fmt=FMT_MOEDA)
    fim = ini + len(linhas) - 1
    sub, aum, tot = fim + 1, fim + 2, fim + 3
    _celula(ws, f'A{sub}', 'SUBTOTAL', True, fundo=F_TOTAL)
    _celula(ws, f'B{sub}', fundo=F_TOTAL)
    _celula(ws, f'C{sub}', f'=SUM(C{ini}:C{fim})', True, FMT_MOEDA, fundo=F_TOTAL)
    _celula(ws, f'D{sub}', f'=C{sub}*12', True, FMT_MOEDA, fundo=F_TOTAL)
    _celula(ws, f'A{aum}', 'Aumento previsto (salários, tarifas, serviços) sobre o SUBTOTAL')
    _celula(ws, f'B{aum}', v['inflacao'], fmt=FMT_PCT, fundo=F_EDITAVEL).alignment = Alignment(horizontal='center')
    _celula(ws, f'C{aum}', f'=C{sub}*B{aum}', fmt=FMT_MOEDA)
    _celula(ws, f'D{aum}', f'=C{aum}*12', fmt=FMT_MOEDA)
    _celula(ws, f'A{tot}', 'TOTAL PREVISTO', True, fundo=F_TOTAL)
    _celula(ws, f'B{tot}', fundo=F_TOTAL)
    _celula(ws, f'C{tot}', f'=C{sub}+C{aum}', True, FMT_MOEDA, fundo=F_TOTAL)
    _celula(ws, f'D{tot}', f'=C{tot}*12', True, FMT_MOEDA, fundo=F_TOTAL)

    # --- Quadro de leitura: mesmas opções do PDF, em fórmula ---
    lin = tot + 2
    _secao(ws, lin, 'Quadro de leitura')
    _cabecalho(ws, lin + 1, ('Opção', 'Receita mensal', 'Despesa mensal', 'Resultado mensal',
                             'Reajuste necessário', 'Situação'))
    minimo = core.SUPERAVIT_MINIMO_MENSAL
    for i, label in enumerate(v['opcoes']):
        r = lin + 2 + i
        receita = ordinaria
        if 'com fundo' in _norm(label):
            receita += f'+{fundo}'
        if '+' in label:
            receita += f'+{aluguel}'
        _celula(ws, f'A{r}', label, True)
        _celula(ws, f'B{r}', f'={receita}', fmt=FMT_MOEDA)
        _celula(ws, f'C{r}', f'=$C${tot}', fmt=FMT_MOEDA)
        _celula(ws, f'D{r}', f'=B{r}-C{r}', True, FMT_MOEDA)
        # |TOTAL / RECEITA - 1| só quando falta dinheiro (como no PDF).
        _celula(ws, f'E{r}', f'=IF(AND(D{r}<0,B{r}>0),ABS(C{r}/B{r}-1),"Não é necessário")',
                fmt=FMT_PCT).alignment = Alignment(horizontal='center')
        _celula(ws, f'F{r}', f'=IF(D{r}>={minimo:g},"Superávit",IF(D{r}>=0,'
                f'"Superávit insuficiente — atenção","Déficit"))', True)
    ws.freeze_panes = 'A5'
    return f"'Previsão'!$C${tot_rec}"


def _aba_mensal(wb, ctx, ref_receita):
    fluxo = ctx.get('fluxo_mensal') or []
    if not fluxo:
        return
    ws = wb.create_sheet('Evolução mensal')
    for col, larg in zip('ABCDEF', (12, 18, 18, 18, 16, 16)):
        ws.column_dimensions[col].width = larg
    _celula(ws, 'A1', 'Evolução mensal', True, cor=AZUL, borda=False, tamanho=14)
    _celula(ws, 'A2', 'Receita = total mensal da aba Previsão. A despesa de cada mês vem dos relatórios '
            'contábeis e pode ser corrigida nas células amarelas.', cor=CINZA, borda=False, tamanho=9)
    _cabecalho(ws, 4, ('Mês', 'Receita', 'Despesa', 'Diferença', 'Receita acima', 'Despesa acima'))
    ini = 5
    for i, m in enumerate(fluxo):
        r = ini + i
        _celula(ws, f'A{r}', m.get('mes')).alignment = Alignment(horizontal='center')
        _celula(ws, f'B{r}', f'={ref_receita}', fmt=FMT_MOEDA)
        _celula(ws, f'C{r}', round(float(m.get('despesa') or 0), 2), fmt=FMT_MOEDA, fundo=F_EDITAVEL)
        _celula(ws, f'D{r}', f'=B{r}-C{r}', True, FMT_MOEDA)
        _celula(ws, f'E{r}', f'=MAX(D{r},0)', fmt=FMT_MOEDA)
        _celula(ws, f'F{r}', f'=MIN(D{r},0)', fmt=FMT_MOEDA)
    fim = ini + len(fluxo) - 1
    _celula(ws, f'A{fim + 2}', f'=COUNTIF(D{ini}:D{fim},">=0")&" mês(es) com receita acima da despesa · "'
            f'&COUNTIF(D{ini}:D{fim},"<0")&" mês(es) com despesa acima da receita"', True, borda=False)

    # Duas séries (acima / abaixo) para cada lado ter a sua cor.
    g = BarChart()
    g.type = 'col'
    g.grouping = 'clustered'
    g.overlap = 100
    g.gapWidth = 60
    g.title = 'Diferença entre receita e despesa de cada mês'
    g.y_axis.title = 'R$'
    g.y_axis.numFmt = '"R$" #,##0'
    g.y_axis.majorGridlines = None
    g.x_axis.delete = False
    g.y_axis.delete = False
    g.x_axis.tickLblPos = 'low'
    g.add_data(Reference(ws, min_col=5, max_col=6, min_row=4, max_row=fim), titles_from_data=True)
    g.set_categories(Reference(ws, min_col=1, min_row=ini, max_row=fim))
    for serie, cor in zip(g.series, (COR_RECEITA_ACIMA, COR_DESPESA_ACIMA)):
        serie.graphicalProperties.solidFill = cor.lstrip('#')
        serie.graphicalProperties.line.noFill = True
    g.legend.position = 'b'
    g.width, g.height = 24, 10
    ws.add_chart(g, f'H4')


def gerar_relatorio_xlsx(estado, com_fundo_override=None):
    ctx = montar_contexto_relatorio(estado, None, com_fundo_override)
    wb = Workbook()
    ref_receita = _aba_previsao(wb.active, ctx)
    _aba_mensal(wb, ctx, ref_receita)
    # Sem valores em cache: o Excel calcula tudo ao abrir.
    wb.calculation.fullCalcOnLoad = True
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
