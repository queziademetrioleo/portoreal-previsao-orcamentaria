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
Os dados dos gráficos ficam à direita, fora da área de impressão.
"""
import io
import math
import os

import xlsxwriter

import previsao as core
from relatorio_pdf import (COR_DESPESA_ACIMA, COR_RECEITA_ACIMA, _money, _norm, _pct,
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


def _status(resultado_mensal):
    if resultado_mensal >= MINIMO:
        return 'superavit'
    return 'superavit_insuficiente' if resultado_mensal >= 0 else 'deficit'


def _money_f(ref):
    """R$ em texto dentro de fórmula; FIXED usa o separador do Excel do usuário."""
    return f'IF({ref}<0,"-R$ ","R$ ")&FIXED(ABS({ref}),2)'


def _pct_f(ref):
    return f'FIXED({ref}*100,1)'


def _str_f(txt):
    return '"' + txt.replace('"', '""') + '"'


def _altura(texto, chars_linha=135, pt=13):
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

    def __init__(self, wb, ws):
        self.wb, self.ws = wb, ws
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

    def escreve(self, ref, valor, formato, cache=None):
        """Fórmula ('=...') sai com o resultado em cache; o resto é valor."""
        if isinstance(valor, str) and valor.startswith('='):
            self.ws.write_formula(ref, valor, formato, cache if cache is not None else 0)
        elif valor is None:
            self.ws.write_blank(ref, None, formato)
        else:
            self.ws.write(ref, valor, formato)

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


def _pizza(f, ctx, linhas_despesa, ref_subtotal, subtotal):
    pizza = ctx.get('pizza')
    if not pizza:
        return
    f.secao('Composição das despesas')
    # Dados à direita (H:I), fora da área de impressão; cada fatia aponta para a conta.
    ini = f.lin
    f.ws.set_column('H:H', 34)
    f.ws.set_column('I:I', 16)
    cinza = f.fmt(font_size=9, font_color=CINZA_CLARO)
    cinza_m = f.fmt(font_size=9, font_color=CINZA_CLARO, num_format=FMT_MOEDA)
    f.escreve(f'H{ini - 1}', 'Dados do gráfico (não imprime)', f.fmt(bold=True, font_size=9, font_color=CINZA_CLARO))
    refs, soma = [], 0.0
    for i, fatia in enumerate(pizza['fatias']):
        r = ini + i
        linha = linhas_despesa.get(_norm(fatia['label']))
        if linha:
            num, valor = linha
            f.escreve(f'H{r}', f'=B{num}', cinza, fatia['label'])
            f.escreve(f'I{r}', f'=F{num}', cinza_m, valor)
            refs.append(f'I{r}')
            soma += valor
        else:  # "Outros" = o que sobra do SUBTOTAL
            f.escreve(f'H{r}', fatia['label'], cinza)
            f.escreve(f'I{r}', f'={ref_subtotal}' + ''.join(f'-{x}' for x in refs), cinza_m,
                      round(subtotal - soma, 2))
    fim = ini + len(pizza['fatias']) - 1
    g = f.wb.add_chart({'type': 'pie'})
    g.add_series({
        'categories': f"='Previsão'!$H${ini}:$H${fim}",
        'values': f"='Previsão'!$I${ini}:$I${fim}",
        'points': [{'fill': {'color': fat['cor']}, 'border': {'color': '#FCFCFB', 'width': 1.5}}
                   for fat in pizza['fatias']],
        'data_labels': {'percentage': True, 'font': {'name': FONTE, 'size': 9, 'bold': True, 'color': TINTA}},
    })
    g.set_legend({'position': 'right', 'font': {'name': FONTE, 'size': 9}})
    g.set_chartarea({'border': {'none': True}})
    g.set_size({'width': 820, 'height': 300})
    f.ws.insert_chart(f'B{f.lin}', g)
    for r in range(f.lin, f.lin + 15):
        f.altura(r, 15)
    f.lin += 15


def _mensal(f, ctx, ref_receita, receita):
    fluxo = ctx.get('fluxo_mensal') or []
    if not fluxo:
        return
    f.secao('Evolução mensal')
    # Dados à direita (K:O), fora da área de impressão.
    for col, larg in zip('KLMNO', (10, 15, 15, 15, 15)):
        f.ws.set_column(f'{col}:{col}', larg)
    cinza = f.fmt(font_size=9, font_color=CINZA_CLARO)
    cinza_m = f.fmt(font_size=9, font_color=CINZA_CLARO, num_format=FMT_MOEDA)
    cab = f.lin
    f.escreve(f'K{cab - 1}', 'Dados do gráfico (não imprime) — a despesa de cada mês pode ser corrigida aqui',
              f.fmt(bold=True, font_size=9, font_color=CINZA_CLARO))
    for col, txt in zip('KLMNO', ('Mês', 'Receita', 'Despesa', 'Receita acima', 'Despesa acima')):
        f.escreve(f'{col}{cab}', txt, f.fmt(bold=True, font_size=9, font_color=CINZA_CLARO))
    ini = cab + 1
    difs = []
    for i, m in enumerate(fluxo):
        r = ini + i
        despesa = round(float(m.get('despesa') or 0), 2)
        dif = round(receita - despesa, 2)
        difs.append((m.get('mes'), dif))
        f.escreve(f'K{r}', m.get('mes'), cinza)
        f.escreve(f'L{r}', f'={ref_receita}', cinza_m, receita)
        f.escreve(f'M{r}', despesa, cinza_m)
        f.escreve(f'N{r}', f'=MAX(L{r}-M{r},0)', cinza_m, max(dif, 0))
        f.escreve(f'O{r}', f'=MIN(L{r}-M{r},0)', cinza_m, min(dif, 0))
    fim = ini + len(fluxo) - 1

    r = f.lin
    n_abaixo = sum(1 for _, d in difs if d < 0)
    n_acima = len(difs) - n_abaixo  # empate conta como acima, como no PDF
    abaixo = f'COUNTIF(O{ini}:O{fim},"<0")'
    acima = f'(ROWS(K{ini}:K{fim})-{abaixo})'
    plural = lambda n: 'mês' if n == 1 else 'meses'
    meses = lambda n: f'IF({n}=1," mês"," meses")'
    f.escreve(f'B{r}', f'="▲ "&{acima}&{meses(acima)}&" com receita acima da despesa"',
              f.fmt(bold=True, font_color=COR_RECEITA_ACIMA),
              f'▲ {n_acima} {plural(n_acima)} com receita acima da despesa')
    f.mescla(f'E{r}:F{r}', f'="▼ "&{abaixo}&{meses(abaixo)}&" com despesa acima da receita"',
             f.fmt(bold=True, font_color=COR_DESPESA_ACIMA),
             f'▼ {n_abaixo} {plural(n_abaixo)} com despesa acima da receita')
    f.altura(r, 18)
    f.lin += 1

    g = f.wb.add_chart({'type': 'column'})
    for col, cor in (('N', COR_RECEITA_ACIMA), ('O', COR_DESPESA_ACIMA)):
        g.add_series({
            'name': f"='Previsão'!${col}${cab}",
            'categories': f"='Previsão'!$K${ini}:$K${fim}",
            'values': f"='Previsão'!${col}${ini}:${col}${fim}",
            'fill': {'color': cor}, 'border': {'none': True},
            'overlap': 100, 'gap': 70,
            # ≈ e sinal como no PDF; o zero (a outra série do mês) fica sem rótulo.
            'data_labels': {'value': True, 'position': 'outside_end',
                            'num_format': '"≈ +R$ "#,##0;"≈ −R$ "#,##0;""',
                            'font': {'name': FONTE, 'size': 8, 'bold': True, 'color': TINTA}},
        })
    g.set_legend({'none': True})
    # Folga embaixo/em cima para o rótulo da maior barra não encostar nos meses.
    menor, maior = min(min(d for _, d in difs), 0), max(max(d for _, d in difs), 0)
    folga = (maior - menor) * 0.18 or 1
    g.set_y_axis({'visible': False, 'major_gridlines': {'visible': False},
                  'min': menor - folga if menor < 0 else 0, 'max': maior + folga})
    g.set_x_axis({'label_position': 'low', 'num_font': {'name': FONTE, 'size': 8, 'color': CINZA},
                  'line': {'color': CINZA_CLARO}})
    g.set_chartarea({'border': {'none': True}})
    g.set_size({'width': 820, 'height': 250})
    f.ws.insert_chart(f'B{f.lin}', g)
    for rr in range(f.lin, f.lin + 13):
        f.altura(rr, 15)
    f.lin += 13

    r = f.lin
    f.mescla(f'B{r}:C{r}', f'="Diferença entre a receita atual ("&{_money_f(ref_receita)}&" por mês) e a despesa '
             f'de cada mês. Valores aproximados, arredondados ao real."',
             f.fmt(font_size=9, font_color=CINZA, text_wrap=True, valign='top'),
             f'Diferença entre a receita atual ({_money(receita)} por mês) e a despesa de cada mês. '
             'Valores aproximados, arredondados ao real.')
    pior = f'MIN(O{ini}:O{fim})'
    mes_pior, val_pior = min(difs, key=lambda x: x[1])
    f.mescla(f'E{r}:F{r}', f'=IF({pior}<0,"Maior diferença negativa: "&INDEX(K{ini}:K{fim},'
             f'MATCH({pior},O{ini}:O{fim},0))&" ("&{_money_f(pior)}&")","")',
             f.fmt(bold=True, font_size=9, text_wrap=True, valign='top', align='right'),
             f'Maior diferença negativa: {mes_pior} ({_money(val_pior)})' if val_pior < 0 else '')
    f.altura(r, 28)
    f.lin += 1


def _texto_opcoes(opcoes, refs):
    """Mesmo texto de relatorio_pdf._consideracao_opcoes, já em minúsculas
    como sai de _texto_consideracao. Devolve (fórmula, texto atual)."""
    if len(opcoes) == 1:
        r = refs[0]
        return (f'IF(ISNUMBER({r["reaj"]}),"Recomendamos um reajuste de "&{_pct_f(r["reaj"])}&"% na taxa '
                f'condominial para os próximos 12 meses.","A receita atual cobre as despesas previstas; não é '
                f'necessário reajuste da taxa condominial.")',
                f'Recomendamos um reajuste de {_pct(r["reajuste"])}% na taxa condominial para os próximos 12 meses.'
                if r['reajuste'] > 0 else
                'A receita atual cobre as despesas previstas; não é necessário reajuste da taxa condominial.')
    partes, textos = [], []
    for letra, o, r in zip('abcd', opcoes, refs):
        frase = (f'IF({r["res"]}<0,"faltam "&{_money_f("-" + r["res"])}&" por mês — reajuste necessário de "'
                 f'&{_pct_f(r["reaj"])}&"% na taxa condominial","sobram "&{_money_f(r["res"])}'
                 f'&" por mês — não é necessário reajuste")')
        prefixo = f'{letra}) {o["label"].lower()}: '
        partes.append(f'{_str_f(prefixo)}&{frase}')
        res = r['resultado']
        textos.append(prefixo + (f'faltam {_money(-res)} por mês — reajuste necessário de {_pct(r["reajuste"])}% '
                                 'na taxa condominial' if res < 0 else
                                 f'sobram {_money(res)} por mês — não é necessário reajuste'))
    abre = 'Opções para o custeio das despesas ordinárias nos próximos 12 meses: '
    formula = _str_f(abre) + '&' + '&"; "&'.join(partes) + '&"."'
    texto = abre + '; '.join(textos) + '.'
    if any(o['usa_fundo'] for o in opcoes):
        nota = (' A utilização dos valores arrecadados para o fundo de reserva no custeio das despesas '
                'ordinárias não é recomendada.')
        formula += '&' + _str_f(nota)
        texto += nota
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
    prefixo = ctx['conclusao_texto'].split('O resultado mensal é de')[0]
    insuf = (' — positivo, mas abaixo dos R$ 2.000 por mês (R$ 24.000 no ano) considerados margem de '
             'segurança suficiente.')
    formula = (f'={_str_f(prefixo)}&"O resultado mensal é de "&{_money_f(res)}&IF(AND({res}>=0,{res}<{MINIMO:g}),'
               f'{_str_f(insuf)}," ("&IF({res}<0,"DÉFICIT","SUPERÁVIT")&").")')
    f.paragrafo(formula, f.fmt(text_wrap=True, valign='top', **barra), ctx['conclusao_texto'])


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
        f.altura(r, _altura(texto) + 6)  # respiro entre itens, como no PDF
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
    ws = wb.add_worksheet('Previsão')
    f = _Folha(wb, ws)
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

    # --- Gráficos (página 2) ---
    f.lin += 1
    quebras = [f.lin]
    _pizza(f, ctx, linhas_despesa, f'$F${sub}', subtotal)
    _mensal(f, ctx, f'$F${tot_rec}', total_rec)

    # --- Conclusão + Considerações juntas numa página nova, como no PDF ---
    f.lin += 1
    quebras.append(f.lin)
    no_quadro = 0
    if v['com_fundo_pref']:
        no_quadro = next((i for i, o in enumerate(v['opcoes']) if o['usa_fundo'] and '+' not in o['label']), 0)
    _conclusao(f, ctx, refs[no_quadro])
    _consideracoes(f, ctx, refs)

    _configurar_impressao(f, quebras)
    wb.close()
    return buf.getvalue()
