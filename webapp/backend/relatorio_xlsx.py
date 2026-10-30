#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RELATORIO XLSX PARA O CONDOMINIO

Mesmo desenho, conteúdo e ordem do PDF/DOCX (consome `montar_contexto_relatorio`),
numa aba só, pronta para imprimir/exportar em A4. A diferença: as contas são
células e tudo que depende delas é fórmula — total de receitas, SUBTOTAL,
aumento previsto, TOTAL, quadro de leitura, gráficos, conclusão e as
considerações com valores. Incluir, tirar ou alterar uma conta recalcula o
relatório no Excel / Google Sheets / LibreOffice / Numbers.

Cada fórmula é gravada junto com o resultado já calculado (XlsxWriter), para
prévias que não calculam (Finder, WhatsApp, e-mail) mostrarem os valores.
Uma linha em branco dentro de cada tabela já entra na soma; linhas inseridas
no meio da tabela também entram, porque o Excel estende o SUM sozinho.
Os dados do gráfico ficam numa aba à parte, para não entrarem na impressão
(o Numbers ignora a área de impressão e imprimiria tudo o que há na aba).
"""
import io
import math
import os

import xlsxwriter

import previsao as core
from relatorio_pdf import (FUNDO_PRESERVADO, SEM_REAJUSTE, USO_DO_FUNDO, _money, _norm, _pct,
                           montar_contexto_relatorio)

# Paleta do PDF (relatorio_pdf._HTML_TEMPLATE)
AZUL = '#1C355E'
TINTA = '#14110C'
CINZA = '#52514E'
CINZA_CLARO = '#898781'
LINHA = '#E1E0D9'
FONTE = 'Arial'
FMT_MOEDA = '"R$" #,##0.00'  # uma seção só: o Excel põe o "-" e o Numbers não duplica
FMT_PCT = '0.0%'
LINHAS_EM_BRANCO = 1
STATUS = {  # selo do quadro: texto, fundo, cor do texto (badges do PDF)
    'superavit': ('Superávit', '#DFF3E3', '#0F6B2B'),
    'superavit_insuficiente': ('Superávit insuficiente', '#FFF3CD', '#8A6300'),
    'deficit': ('Déficit', '#FBE3E3', '#A12626'),
}
CONCLUSAO = {
    'superavit': 'Cenário com superávit',
    'superavit_insuficiente': 'Superávit insuficiente — atenção',
    'deficit': 'Atenção: orçamento em déficit',
}
MINIMO = core.SUPERAVIT_MINIMO_MENSAL
ABA = 'Previsão'
ABA_DADOS = 'Dados do gráfico'
P = f"'{ABA}'!"
D = f"'{ABA_DADOS}'!"


def _status(resultado_mensal):
    if resultado_mensal >= MINIMO:
        return 'superavit'
    return 'superavit_insuficiente' if resultado_mensal >= 0 else 'deficit'


def _pct_f(ref):
    return f'FIXED({ref}*100,1)'


def _str_f(txt):
    return '"' + txt.replace('"', '""') + '"'


def _altura(texto, chars_linha=150, pt=13):
    linhas = sum(max(1, math.ceil(len(p) / chars_linha)) for p in (texto or '').split('\n'))
    return linhas * pt + 4


def _borda(**lados):
    kw = {}
    for lado, estilo in lados.items():
        kw[lado] = estilo
        kw[f'{lado}_color'] = LINHA
    return kw


class _Folha:
    """Escreve o relatório de cima para baixo nas colunas B:F (linhas 1-based)."""

    def __init__(self, wb, ws, dados):
        self.wb, self.ws, self.dados = wb, ws, dados
        self.lin = 1
        self._formatos = {}
        for i, larg in enumerate((2, 40, 17, 3, 40, 17)):
            ws.set_column(i, i, larg)
        ws.hide_gridlines(2)

    def fmt(self, **kw):
        base = {'font_name': FONTE, 'font_size': 10, 'font_color': TINTA, 'valign': 'vcenter'}
        base.update(kw)
        chave = tuple(sorted(base.items()))
        if chave not in self._formatos:
            self._formatos[chave] = self.wb.add_format(base)
        return self._formatos[chave]

    def altura(self, linha, pt):
        self.ws.set_row(linha - 1, pt)

    def escreve(self, ref, valor, formato, cache=None, ws=None):
        """Fórmula ('=...') sai com o resultado em cache; o resto é valor."""
        ws = ws or self.ws
        if isinstance(valor, str) and valor.startswith('='):
            ws.write_formula(ref, valor, formato, cache if cache is not None else 0)
        elif valor is None:
            ws.write_blank(ref, None, formato)
        else:
            ws.write(ref, valor, formato)

    def mescla(self, rng, valor, formato, cache=None):
        self.ws.merge_range(rng, '', formato)
        self.escreve(rng.split(':')[0], valor, formato, cache)

    def paragrafo(self, valor, formato, cache=None):
        r = self.lin
        self.mescla(f'B{r}:F{r}', valor, formato, cache)
        self.altura(r, _altura(cache if cache is not None else str(valor)))
        self.lin += 1
        return r

    def secao(self, txt):
        self.lin += 1
        r = self.lin
        borda = _borda(bottom=1)
        self.escreve(f'B{r}', txt, self.fmt(bold=True, font_size=13, font_color=AZUL, valign='bottom', **borda))
        for col in 'CDEF':
            self.escreve(f'{col}{r}', None, self.fmt(**borda))
        self.altura(r, 24)
        self.lin += 2

    def tabela(self, linhas):
        """Conta (B:E mesclado) | valor mensal (F). Devolve (1ª, última) linha de dados."""
        r = self.lin
        borda = _borda(bottom=1)
        self.mescla(f'B{r}:E{r}', 'Conta', self.fmt(bold=True, font_size=9, font_color=CINZA, **borda))
        self.escreve(f'F{r}', 'Valor mensal previsto', self.fmt(bold=True, font_size=9, font_color=CINZA,
                                                              align='right', **borda))
        ini = r + 1
        for i, (label, valor) in enumerate(linhas):
            r = ini + i
            self.mescla(f'B{r}:E{r}', label, self.fmt(**borda))
            self.escreve(f'F{r}', valor, self.fmt(num_format=FMT_MOEDA, align='right', **borda))
            self.altura(r, 17)
        self.lin = ini + len(linhas)
        return ini, ini + len(linhas) - 1

    def linha_total(self, label, formula, cache, estilo):
        r = self.lin
        if estilo == 'total':
            kw = {'bold': True, 'top': 2, 'top_color': TINTA}
        else:
            kw = {'bold': True, 'font_color': CINZA, 'top': 1, 'top_color': CINZA_CLARO}
        self.mescla(f'B{r}:E{r}', label, self.fmt(**kw))
        self.escreve(f'F{r}', formula, self.fmt(num_format=FMT_MOEDA, align='right', **kw), cache)
        self.altura(r, 18)
        self.lin += 1
        return r


def _cabecalho(f, ctx, logo_path):
    f.altura(1, 26)
    f.altura(2, 26)
    f.altura(3, 10)
    if logo_path and os.path.exists(logo_path):
        try:
            from PIL import Image
            with Image.open(logo_path) as im:
                escala = 52 / im.height
        except Exception:
            escala = 0.25
        f.ws.insert_image('B1', logo_path, {'x_scale': escala, 'y_scale': escala, 'x_offset': 2, 'y_offset': 8})
    f.mescla('C1:F1', f'{ctx["nome_condominio"]} — {ctx["ano_previsao"]}',
             f.fmt(bold=True, font_size=18, font_color=AZUL, valign='bottom'))
    f.mescla('C2:F2', f'Previsão orçamentária · {ctx["data_extenso"]}',
             f.fmt(font_size=11, font_color=CINZA, valign='top'))
    for col in 'BCDEF':
        f.escreve(f'{col}3', None, f.fmt(bottom=2, bottom_color=AZUL))
    f.lin = 4


def _quadro(f, opcoes, ref_total, total):
    """Cartões lado a lado (2 por linha), como o .quadro do PDF."""
    refs = []
    for i, o in enumerate(opcoes):
        c_lab, c_val = ('B', 'C') if i % 2 == 0 else ('E', 'F')
        topo = f.lin + (i // 2) * 7
        rec, desp, res, reaj, selo = (topo + k for k in range(1, 6))
        f.escreve(f'{c_lab}{topo}', o['label'], f.fmt(bold=True, font_size=11, font_color=AZUL,
                                                      **_borda(top=1, left=1)))
        f.escreve(f'{c_val}{topo}', None, f.fmt(**_borda(top=1, right=1)))
        resultado = round(o['receita'] - total, 2)
        reajuste = abs(total / o['receita'] - 1) if resultado < 0 and o['receita'] > 0 else 'Não é necessário'
        itens = (
            (rec, 'Receita mensal', f'={o["formula"]}', round(o['receita'], 2), FMT_MOEDA),
            (desp, 'Despesa mensal', f'={ref_total}', total, FMT_MOEDA),
            (res, 'Resultado mensal', f'={c_val}{rec}-{c_val}{desp}', resultado, FMT_MOEDA),
            # |TOTAL / RECEITA - 1| só quando falta dinheiro (como no PDF).
            (reaj, 'Reajuste necessário',
             f'=IF(AND({c_val}{res}<0,{c_val}{rec}>0),ABS({c_val}{desp}/{c_val}{rec}-1),"Não é necessário")',
             reajuste, FMT_PCT),
        )
        for r, txt, formula, cache, num in itens:
            tracejado = _borda(bottom=3) if r != reaj else {}
            f.escreve(f'{c_lab}{r}', txt, f.fmt(**_borda(left=1), **tracejado))
            f.escreve(f'{c_val}{r}', formula, f.fmt(num_format=num, align='right', **_borda(right=1), **tracejado),
                      cache)
        st = _status(resultado)
        f.escreve(f'{c_lab}{selo}',
                  f'=IF({c_val}{res}>={MINIMO:g},"{STATUS["superavit"][0]}",IF({c_val}{res}>=0,'
                  f'"{STATUS["superavit_insuficiente"][0]}","{STATUS["deficit"][0]}"))',
                  f.fmt(bold=True, font_color=STATUS[st][2], **_borda(left=1, bottom=1)), STATUS[st][0])
        f.escreve(f'{c_val}{selo}', None, f.fmt(**_borda(right=1, bottom=1)))
        # Se o resultado mudar, o selo troca de cor junto.
        for txt, _, cor in STATUS.values():
            f.ws.conditional_format(f'{c_lab}{selo}', {
                'type': 'cell', 'criteria': '==', 'value': _str_f(txt),
                'format': f.wb.add_format({'font_color': cor, 'bold': True})})
        for r in range(topo, selo + 1):
            f.altura(r, 17)
        refs.append({'res': f'{c_val}{res}', 'reaj': f'{c_val}{reaj}', 'resultado': resultado,
                     'reajuste': reajuste if isinstance(reajuste, float) else 0.0})
    f.lin += math.ceil(len(opcoes) / 2) * 7
    return refs


def _barras(f, ctx, linhas_despesa, ref_subtotal, subtotal):
    grafico = ctx.get('grafico')
    if not grafico:
        return
    f.secao('Composição das despesas')
    # Dados na aba à parte (A:C); cada barra aponta para a conta, C = participação.
    d = f.dados
    d.set_column('A:A', 40)
    d.set_column('B:C', 16)
    cinza = f.fmt(font_size=9)
    cinza_m = f.fmt(font_size=9, num_format=FMT_MOEDA)
    cinza_p = f.fmt(font_size=9, num_format='0.0%')
    f.escreve('A1', 'Composição das despesas', f.fmt(bold=True, font_color=AZUL), ws=d)
    barras = grafico['barras']
    ini = 2
    fim = ini + len(barras) - 1
    refs, soma = [], 0.0
    for i, barra in enumerate(barras):
        r = ini + i
        linha = linhas_despesa.get(_norm(barra['label']))
        if linha:
            num, valor = linha
            f.escreve(f'A{r}', f'={P}B{num}', cinza, barra['label'], ws=d)
            f.escreve(f'B{r}', f'={P}F{num}', cinza_m, valor, ws=d)
            refs.append(f'B{r}')
            soma += valor
        else:  # "Outros" = o que sobra do SUBTOTAL
            f.escreve(f'A{r}', barra['label'], cinza, ws=d)
            f.escreve(f'B{r}', f'={P}{ref_subtotal}' + ''.join(f'-{x}' for x in refs), cinza_m,
                      round(subtotal - soma, 2), ws=d)
        f.escreve(f'C{r}', f'=B{r}/SUM($B${ini}:$B${fim})', cinza_p, barra['frac'], ws=d)
    g = f.wb.add_chart({'type': 'bar'})
    g.add_series({
        'categories': f"={D}$A${ini}:$A${fim}",
        'values': f"={D}$C${ini}:$C${fim}",
        'fill': {'color': '#4A4A4A'},
        'border': {'color': TINTA, 'width': 1},
        'gap': 45,
        'data_labels': {'value': True, 'num_format': '0.0%',
                        'font': {'name': FONTE, 'size': 9, 'color': TINTA}},
    })
    # Em gráfico de barras o x_axis do xlsxwriter é o eixo das categorias (vertical).
    g.set_x_axis({'reverse': True, 'num_font': {'name': FONTE, 'size': 9, 'color': TINTA},
                  'line': {'color': TINTA}, 'major_tick_mark': 'none'})
    g.set_y_axis({'min': 0, 'num_format': '0%', 'major_unit': 0.1, 'minor_unit': 0.05,
                  'major_gridlines': {'visible': True, 'line': {'color': '#C9C8C3'}},
                  'minor_gridlines': {'visible': True, 'line': {'color': '#E6E5E0'}},
                  'num_font': {'name': FONTE, 'size': 9, 'color': TINTA}, 'line': {'none': True}})
    g.set_legend({'none': True})
    g.set_chartarea({'border': {'none': True}})
    g.set_size({'width': 820, 'height': 60 + 42 * len(barras)})
    f.ws.insert_chart(f'B{f.lin}', g)
    n = math.ceil((60 + 42 * len(barras)) / 15)
    for r in range(f.lin, f.lin + n):
        f.altura(r, 15)
    f.lin += n


def _texto_opcoes(opcoes, refs):
    """Mesmo texto de relatorio_pdf._consideracao_opcoes, já em minúsculas
    como sai de _texto_consideracao. Devolve (fórmula, texto atual)."""
    sem = refs[0]
    fim = ' para os próximos 12 meses.'
    if not (len(opcoes) > 1 and opcoes[1]['usa_fundo']):  # sem fundo: só a frase final (José 29/10)
        recomenda, taxa = 'Recomendamos um reajuste de ', '% na taxa condominial'
        nada = SEM_REAJUSTE[0].upper() + SEM_REAJUSTE[1:]
        formula = (f'IF({sem["res"]}<0,{_str_f(recomenda)}&{_pct_f(sem["reaj"])}&{_str_f(taxa)},'
                   f'{_str_f(nada)})&{_str_f(fim)}')
        texto = (f'{recomenda}{_pct(sem["reajuste"])}{taxa}' if sem['resultado'] < 0 else nada) + fim
        return formula, texto
    com = refs[1]
    uso = USO_DO_FUNDO.replace('Fundo de Reserva', 'fundo de reserva')
    meio = FUNDO_PRESERVADO.replace('Fundo de Reserva', 'fundo de reserva')
    sugere, recomenda, taxa = 'sugerimos um reajuste de ', 'recomendamos um reajuste de ', '% na taxa condominial'
    formula = (f'{_str_f(uso)}&IF({com["res"]}<0,{_str_f(sugere)}&{_pct_f(com["reaj"])}&{_str_f(taxa + ".")},'
               f'{_str_f(SEM_REAJUSTE + ".")})&{_str_f(meio)}&IF({sem["res"]}<0,{_str_f(recomenda)}&'
               f'{_pct_f(sem["reaj"])}&{_str_f(taxa)},{_str_f(SEM_REAJUSTE)})&{_str_f(fim)}')
    texto = (uso + (f'{sugere}{_pct(com["reajuste"])}{taxa}.' if com['resultado'] < 0 else f'{SEM_REAJUSTE}.')
             + meio + (f'{recomenda}{_pct(sem["reajuste"])}{taxa}' if sem['resultado'] < 0 else SEM_REAJUSTE) + fim)
    return formula, texto


def _texto_suficiencia(ref_res, resultado):
    neg = ('A receita ordinária prevista, sem utilizar o fundo de reserva, não será suficiente para cobrir as '
           'despesas ordinárias nos próximos 12 meses.')
    pos = ('A receita ordinária prevista será suficiente para cobrir as despesas ordinárias nos próximos 12 '
           'meses, sem utilizar o fundo de reserva.')
    margem = ' A margem mensal é inferior a R$ 2.000,00 e requer atenção.'
    formula = f'IF({ref_res}<0,{_str_f(neg)},{_str_f(pos)}&IF({ref_res}<{MINIMO:g},{_str_f(margem)},""))'
    texto = neg if resultado < 0 else pos + (margem if resultado < MINIMO else '')
    return formula, texto


def _conclusao(f, ctx, ref):
    f.secao('Conclusão')
    res, resultado = ref['res'], ref['resultado']
    st = _status(resultado)
    barra = {'left': 5, 'left_color': AZUL}
    r = f.paragrafo(f'=IF({res}>={MINIMO:g},"{CONCLUSAO["superavit"]}",IF({res}>=0,'
                    f'"{CONCLUSAO["superavit_insuficiente"]}","{CONCLUSAO["deficit"]}"))',
                    f.fmt(bold=True, font_color=STATUS[st][2], **barra), CONCLUSAO[st])
    for chave in STATUS:
        f.ws.conditional_format(f'B{r}', {'type': 'cell', 'criteria': '==', 'value': _str_f(CONCLUSAO[chave]),
                                          'format': f.wb.add_format({'font_color': STATUS[chave][2], 'bold': True})})
    f.paragrafo(ctx['conclusao_texto'], f.fmt(text_wrap=True, valign='top', **barra))


def _consideracoes(f, ctx, refs):
    v = ctx['valores']
    f.lin += 1
    f.paragrafo('CONSIDERAÇÕES IMPORTANTES', f.fmt(bold=True, font_size=13, font_color=AZUL, align='center'))
    corpo = f.fmt(font_color='#303030', text_wrap=True, valign='top')
    for i, texto in enumerate(ctx['consideracoes']):
        numero = f'{i + 1}) '
        formula = None
        if i == v['idx_suficiencia']:
            formula, atual = _texto_suficiencia(refs[0]['res'], refs[0]['resultado'])
        elif i == v['idx_opcoes']:
            formula, atual = _texto_opcoes(v['opcoes'], refs)
        if formula:
            r = f.paragrafo(f'={_str_f(numero)}&{formula}', corpo, numero + atual)
        else:
            r = f.paragrafo(texto, corpo)
        f.altura(r, _altura(texto) + 4)  # respiro entre itens, como no PDF
    f.lin += 2
    f.paragrafo(f'Cabo Frio, {ctx["data_extenso"]}', f.fmt(font_size=10.5, align='center'))
    f.paragrafo('PORTO REAL IMÓVEIS', f.fmt(bold=True, font_size=10.5, align='center'))


def _configurar_impressao(f, quebras):
    ws = f.ws
    ws.print_area(f'A1:F{f.lin}')
    ws.set_paper(9)  # A4
    ws.set_portrait()
    ws.fit_to_pages(1, 0)
    ws.set_margins(left=0.6, right=0.6, top=0.75, bottom=0.7)
    ws.center_horizontally()
    ws.set_h_pagebreaks([q - 1 for q in quebras])
    ws.set_footer('&C&9&K898781Página &P de &N')


def gerar_relatorio_xlsx(estado, logo_path=None, com_fundo_override=None):
    ctx = montar_contexto_relatorio(estado, None, com_fundo_override)
    v = ctx['valores']
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {'in_memory': True})
    ws = wb.add_worksheet(ABA)
    dados = wb.add_worksheet(ABA_DADOS)
    dados.hide_gridlines(2)
    ws.activate()
    f = _Folha(wb, ws, dados)
    _cabecalho(f, ctx, logo_path)

    # --- Receitas ---
    f.secao('Receitas')
    receitas = [(l, round(val, 2)) for l, val in v['receitas']]
    ini, fim = f.tabela(receitas + [(None, None)] * LINHAS_EM_BRANCO)
    total_rec = round(sum(val for _, val in receitas), 2)
    tot_rec = f.linha_total('Total mensal', f'=SUM(F{ini}:F{fim})', total_rec, 'total')
    rotulos, valores = f'$B${ini}:$B${fim}', f'$F${ini}:$F${fim}'
    # Fundo pelo nome (vale também para linha nova); aluguel pelos nomes do motor.
    fundo_f = f'SUMIF({rotulos},"*fundo de reserva*",{valores})'
    fundo = sum(val for l, val in receitas if 'fundo de reserva' in l.lower())
    nomes_aluguel = [l for l, _ in receitas if _norm(l) in v['aluguel']]
    aluguel_f = '+'.join(f'SUMIF({rotulos},{_str_f(l)},{valores})' for l in nomes_aluguel) or '0'
    aluguel = sum(val for l, val in receitas if l in nomes_aluguel)
    ordinaria_f = f'$F${tot_rec}-{fundo_f}-({aluguel_f})'
    ordinaria = total_rec - fundo - aluguel

    # --- Despesas ---
    f.secao('Despesas')
    despesas = [(l, round(val, 2)) for l, val in v['despesas']]
    ini, fim = f.tabela(despesas + [(None, None)] * LINHAS_EM_BRANCO)
    linhas_despesa = {_norm(l): (ini + i, val) for i, (l, val) in enumerate(despesas)}
    subtotal = round(sum(val for _, val in despesas), 2)
    sub = f.linha_total('SUBTOTAL', f'=SUM(F{ini}:F{fim})', subtotal, 'subtotal')
    aum = f.lin
    linha = _borda(bottom=1)
    f.mescla(f'B{aum}:D{aum}', 'Aumento Previsto (Salários, tarifas, serviços) =', f.fmt(**linha))
    # % editável: o aumento e o TOTAL acompanham.
    f.escreve(f'E{aum}', v['inflacao'], f.fmt(num_format='0.0%" sobre o SUBTOTAL"', align='right', **linha))
    aumento = round(subtotal * v['inflacao'], 2)
    f.escreve(f'F{aum}', f'=ROUND(F{sub}*E{aum},2)', f.fmt(num_format=FMT_MOEDA, align='right', **linha), aumento)
    f.altura(aum, 17)
    f.lin += 1
    total = round(subtotal + aumento, 2)
    tot = f.linha_total('TOTAL PREVISTO', f'=F{sub}+F{aum}', total, 'total')

    # --- Quadro de leitura ---
    f.secao('Quadro de leitura')
    opcoes = []
    for o in v['opcoes']:
        formula, receita = ordinaria_f, ordinaria
        if o['usa_fundo']:
            formula, receita = formula + f'+{fundo_f}', receita + fundo
        if '+' in o['label']:
            formula, receita = formula + f'+({aluguel_f})', receita + aluguel
        opcoes.append({'label': o['label'], 'formula': formula, 'receita': receita})
    refs = _quadro(f, opcoes, f'$F${tot}', total)

    # --- Gráfico de barras (página 2) ---
    f.lin += 1
    quebras = [f.lin]
    _barras(f, ctx, linhas_despesa, f'$F${sub}', subtotal)

    # --- Conclusão logo depois do gráfico, sem página nova, como no PDF ---
    no_quadro = 0
    if v['com_fundo_pref']:
        no_quadro = next((i for i, o in enumerate(v['opcoes']) if o['usa_fundo'] and '+' not in o['label']), 0)
    _conclusao(f, ctx, refs[no_quadro])
    _consideracoes(f, ctx, refs)

    _configurar_impressao(f, quebras)
    wb.close()
    return buf.getvalue()
