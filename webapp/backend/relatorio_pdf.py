#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RELATORIO PDF PARA O CONDOMINIO

Gera um PDF limpo, para entrega ao cliente, a partir do estado ja revisado
de uma sessao (mesmos dados exibidos na tela de resultado do webapp).

Layout: logo Porto Real -> nome do condominio/ano -> Receitas -> Despesas ->
Quadro de leitura (com/sem fundo lado a lado) -> Insights -> Composicao das
despesas (pizza) -> Evolucao mensal -> Conclusao -> Considerações Importantes.
"""
import base64
import math
import os
import re
import unicodedata
from datetime import date

from jinja2 import Template
from weasyprint import HTML

import previsao as core

MESES_PT = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
            'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

# Mesma paleta categorica validada (6 hues, ordem fixa) usada no grafico de
# pizza da tela de resultado (TelaResultado.tsx) — nao ciclar, nao gerar cores.
PIE_COLORS = ['#2a78d6', '#1baf7a', '#eda100', '#008300', '#e34948', '#eb6834']
PIE_LIMITE_FATIAS = 5


def _norm(s):
    s = str(s or '').lower().strip()
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


def _money(v):
    v = float(v or 0)
    sinal = '-' if v < 0 else ''
    txt = f'{abs(v):,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    return f'{sinal}R$ {txt}'


def _pct(v, casas=1):
    return f'{v * 100:,.{casas}f}'.replace('.', ',')


def _data_extenso(d=None):
    d = d or date.today()
    return f'{d.day} de {MESES_PT[d.month - 1]} de {d.year}'


def _logo_base64(logo_path):
    if not logo_path or not os.path.exists(logo_path):
        return None
    with open(logo_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('ascii')


# ---------------------------------------------------------------------------
# Receitas / Despesas — a partir de previsao_final (mesmas linhas do xlsx e
# da aba "Previsão" da tela de resultado)
# ---------------------------------------------------------------------------
def _linha_e_total(label):
    n = _norm(label).strip()
    return (n == 'total' or 'subtotal' in n or 'saldo' in n or 'deficit' in n
            or 'superavit' in n or 'inflacao' in n)


def _linha_e_nota_final(label):
    n = _norm(label).strip()
    return 'consideracoes importantes' in n or n.startswith('1) para o calculo')


def _extrair_receitas_despesas(previsao_final):
    receitas, despesas = [], []
    for row in (previsao_final or []):
        label = row.get('label') or ''
        r = row.get('row') or 0
        if not label or _linha_e_total(label) or _linha_e_nota_final(label):
            continue
        valor = row.get('anual')
        if not isinstance(valor, (int, float)):
            valor = row.get('mensal') if isinstance(row.get('mensal'), (int, float)) else row.get('rateio')
        if not isinstance(valor, (int, float)) or abs(valor) <= 0.005:
            continue
        if 10 <= r <= 20:
            receitas.append((label, float(valor)))
        elif 22 <= r <= 80:
            despesas.append((label, float(valor)))
    return receitas, despesas


# ---------------------------------------------------------------------------
# Insights — espelha utils/insights.ts
# ---------------------------------------------------------------------------
def _gerar_insights(saldo_ajustado, receita_atual, despesa_atual, impacto_inad_mensal,
                     removido, mantido, grupos, linhas, fluxo_mensal):
    out = []
    if saldo_ajustado < 0:
        out.append('A previsão indica déficit: a receita líquida estimada não cobre o total de despesas previstas.')
    else:
        out.append('A receita líquida estimada cobre o total previsto de despesas no cenário atual.')

    if impacto_inad_mensal > 0:
        out.append(f'A inadimplência reduz a receita disponível em {_money(impacto_inad_mensal)} por mês.')

    margem = (saldo_ajustado / receita_atual) if receita_atual > 0 else 0
    out.append(f'Margem ajustada: {_pct(margem)}% da receita.')

    if removido > 0:
        out.append(f'{removido} gasto(s) extraordinário(s) foram retirados da previsão.')

    maior_deducao = None
    for l in linhas:
        if abs(l.get('deducao') or 0) > 0.005:
            if maior_deducao is None or abs(l['deducao']) > abs(maior_deducao['deducao']):
                maior_deducao = l
    if maior_deducao:
        out.append(f'Maior ajuste: {maior_deducao["classe"]}, com {_money(abs(maior_deducao["deducao"]))} deduzidos.')

    if grupos:
        maior_grupo = grupos[0]
        out.append(f'Maior despesa: {maior_grupo["label"]} ({_money(maior_grupo["value"] / 12)}/mês).')

    if mantido > 0:
        out.append(f'{mantido} gasto(s) foram mantidos para não subestimar despesas recorrentes.')

    return out[:7]


def _agrupar_por_grupo(linhas):
    mapa = {}
    for l in linhas:
        g = l.get('grupo') or 'Outros'
        mapa[g] = mapa.get(g, 0) + (l.get('final') or 0)
    grupos = [{'label': k, 'value': v} for k, v in mapa.items() if abs(v) > 0.005]
    grupos.sort(key=lambda g: g['value'], reverse=True)
    return grupos


# ---------------------------------------------------------------------------
# Grafico de pizza (SVG) — mesma matematica/paleta da tela de resultado
# ---------------------------------------------------------------------------
def _polar(cx, cy, r, angulo_deg):
    rad = math.radians(angulo_deg - 90)
    return cx + r * math.cos(rad), cy + r * math.sin(rad)


def _fatia_path(cx, cy, r, ini, fim):
    if fim - ini >= 359.99:
        meio_x, meio_y = _polar(cx, cy, r, ini + 180)
        ini_x, ini_y = _polar(cx, cy, r, ini)
        return (f'M {ini_x} {ini_y} A {r} {r} 0 1 1 {meio_x} {meio_y} '
                f'A {r} {r} 0 1 1 {ini_x} {ini_y} Z')
    ini_x, ini_y = _polar(cx, cy, r, fim)
    fim_x, fim_y = _polar(cx, cy, r, ini)
    large = 1 if fim - ini > 180 else 0
    return f'M {cx} {cy} L {ini_x} {ini_y} A {r} {r} 0 {large} 0 {fim_x} {fim_y} Z'


def _grafico_pizza_svg(grupos, total):
    if not grupos or total <= 0:
        return None
    dados = grupos
    if len(dados) > PIE_LIMITE_FATIAS + 1:
        principais = dados[:PIE_LIMITE_FATIAS]
        outros = sum(g['value'] for g in dados[PIE_LIMITE_FATIAS:])
        dados = principais + [{'label': 'Outros', 'value': outros}]

    cx, cy, r = 100, 100, 90
    cursor = 0.0
    fatias = []
    for i, g in enumerate(dados):
        frac = g['value'] / total
        ini, fim = cursor * 360, (cursor + frac) * 360
        cursor += frac
        meio = (ini + fim) / 2
        lx, ly = _polar(cx, cy, r * 0.66, meio)
        fatias.append({
            'label': g['label'], 'value': g['value'], 'frac': frac,
            'path': _fatia_path(cx, cy, r, ini, fim),
            'cor': PIE_COLORS[i % len(PIE_COLORS)],
            'label_x': round(lx, 1), 'label_y': round(ly, 1),
        })

    paths_svg = ''.join(
        f'<path d="{f["path"]}" fill="{f["cor"]}" stroke="#fcfcfb" stroke-width="2" stroke-linejoin="round"/>'
        for f in fatias
    )
    labels_svg = ''.join(
        f'<text x="{f["label_x"]}" y="{f["label_y"]}" text-anchor="middle" '
        f'dominant-baseline="middle" font-size="13" font-weight="700" fill="#14110c">'
        f'{round(f["frac"] * 100)}%</text>'
        for f in fatias if f['frac'] >= 0.08
    )
    svg = (f'<svg viewBox="0 0 200 200" width="220" height="220">{paths_svg}{labels_svg}</svg>')
    return {'svg': svg, 'fatias': fatias}


# ---------------------------------------------------------------------------
# Grafico de evolucao mensal (SVG, barras) — espelha MonthlyChart.tsx
# ---------------------------------------------------------------------------
def _grafico_mensal_svg(fluxo_mensal):
    if not fluxo_mensal:
        return None
    max_val = max((max(m.get('receita') or 0, m.get('despesa') or 0) for m in fluxo_mensal), default=1)
    max_val = max_val or 1
    largura_total, altura = 640, 160
    n = len(fluxo_mensal)
    col_w = largura_total / n
    barras = []
    for i, m in enumerate(fluxo_mensal):
        x0 = i * col_w
        h_rec = max(4, (m.get('receita') or 0) / max_val * altura)
        h_desp = max(4, (m.get('despesa') or 0) / max_val * altura)
        bw = col_w * 0.32
        x_rec = x0 + col_w * 0.14
        x_desp = x0 + col_w * 0.54
        barras.append({
            'x_rec': round(x_rec, 1), 'y_rec': round(altura - h_rec, 1), 'h_rec': round(h_rec, 1),
            'x_desp': round(x_desp, 1), 'y_desp': round(altura - h_desp, 1), 'h_desp': round(h_desp, 1),
            'bw': round(bw, 1), 'mes': m.get('mes') or '',
            'label_x': round(x0 + col_w / 2, 1),
        })
    pior_mes = min(fluxo_mensal, key=lambda m: m.get('saldo') or 0) if fluxo_mensal else None

    rects = ''.join(
        f'<rect x="{b["x_rec"]}" y="{b["y_rec"]}" width="{b["bw"]}" height="{b["h_rec"]}" '
        f'fill="#1c355e" rx="1.5"/>'
        f'<rect x="{b["x_desp"]}" y="{b["y_desp"]}" width="{b["bw"]}" height="{b["h_desp"]}" '
        f'fill="#c3c2b7" rx="1.5"/>'
        f'<text x="{b["label_x"]}" y="{altura + 14}" text-anchor="middle" font-size="9" fill="#52514e">{b["mes"]}</text>'
        for b in barras
    )
    svg = f'<svg viewBox="0 0 {largura_total} {altura + 20}" width="100%" height="140">{rects}</svg>'
    pior_mes_txt = None
    if pior_mes:
        pior_mes_txt = f'Maior pressão: {pior_mes.get("mes")} ({_money(pior_mes.get("saldo") or 0)})'
    return {'svg': svg, 'pior_mes_txt': pior_mes_txt}


# ---------------------------------------------------------------------------
# Considerações Importantes — itens 3 e 4 (composicao dinamica)
# ---------------------------------------------------------------------------
_CONSERVACAO_ITENS = [
    (re.compile(r'el[ée]tric', re.I), 'elétrica'),
    (re.compile(r'hidr[áa]ulic', re.I), 'hidráulica'),
    (re.compile(r'port[ãa]o', re.I), 'portão'),
    (re.compile(r'c[âa]mera', re.I), 'câmeras'),
    (re.compile(r'dedetiza', re.I), 'dedetização'),
    (re.compile(r'extintor', re.I), 'recarga de extintores'),
    (re.compile(r'fossa|caixa.{0,3}gordura', re.I), 'limpeza de fossa e caixas de gordura'),
    (re.compile(r'caixa.{0,3}[da].{0,3}gua', re.I), "limpeza de caixas d'água"),
    (re.compile(r'elevador', re.I), 'reparo no elevador'),
    (re.compile(r'\bbomba\b', re.I), 'conserto de bomba'),
    (re.compile(r'cartori|custas judicia', re.I), 'despesas cartoriais e custas judiciais'),
    (re.compile(r'reform|reparo', re.I), 'pequenas reformas e reparos'),
]
_ADMINISTRATIVAS_ITENS = [
    (re.compile(r'expediente|material de escrit', re.I), 'material de expediente'),
    (re.compile(r'xerox|c[óo]pia', re.I), 'xerox'),
    (re.compile(r'correio|sedex|correspond', re.I), 'correio'),
]


def _itens_presentes(linhas, grupo_norm_alvo, catalogo):
    presentes = []
    for l in linhas:
        if _norm(l.get('grupo')) != grupo_norm_alvo:
            continue
        if abs(l.get('final') or 0) <= 0.005:
            continue
        classe = l.get('classe') or ''
        for padrao, rotulo in catalogo:
            if padrao.search(classe) and rotulo not in presentes:
                presentes.append(rotulo)
                break
    return presentes


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------
def gerar_relatorio_pdf(estado, logo_path=None):
    resumo = estado.get('resumo') or {}
    linhas = estado.get('linhas_contas') or []
    fluxo_mensal = estado.get('fluxo_mensal') or []
    cenarios = resumo.get('cenarios') or {}
    com_fundo = cenarios.get('com_fundo') or {}
    sem_fundo = cenarios.get('sem_fundo') or {}
    fundo_reserva_anual = cenarios.get('fundo_reserva_anual') or 0
    total_previsto = resumo.get('total_previsto') or 0
    impacto_inad_mensal = resumo.get('impacto_receita_mensal') or 0

    previsao_final = estado.get('previsao_final') or []
    receitas, despesas = _extrair_receitas_despesas(previsao_final)
    if not receitas:
        receitas = [('Receita média do período', resumo.get('receita_mensal') or 0)]
    if not despesas:
        despesas = [(l['classe'], l['final']) for l in linhas if abs(l.get('final') or 0) > 0.005]

    grupos = _agrupar_por_grupo(linhas)
    total_grupo = sum(g['value'] for g in grupos)

    removido = sum(1 for i in (estado.get('extraordinarias') or []) if i.get('decisao') == 'aprovada') \
        + sum(1 for i in (estado.get('revisar') or []) if i.get('decisao') == 'aprovada')
    mantido = sum(1 for i in (estado.get('extraordinarias') or []) if i.get('decisao') == 'reprovada') \
        + sum(1 for i in (estado.get('revisar') or []) if i.get('decisao') == 'reprovada')

    receita_anual_com = com_fundo.get('receita_anual') or 0
    receita_anual_sem = sem_fundo.get('receita_anual') or 0
    resultado_com = com_fundo.get('resultado') or (receita_anual_com - total_previsto)
    resultado_sem = sem_fundo.get('resultado') or (receita_anual_sem - total_previsto)
    saldo_ajustado_anual = resultado_com - impacto_inad_mensal * 12
    status = com_fundo.get('status_resultado') or core._status_resultado(saldo_ajustado_anual)

    insights = _gerar_insights(
        saldo_ajustado_anual / 12, (resumo.get('receita_mensal') or 0), total_previsto / 12,
        impacto_inad_mensal, removido, mantido, grupos, linhas, fluxo_mensal,
    )

    pizza = _grafico_pizza_svg(grupos, total_grupo)
    grafico_mensal = _grafico_mensal_svg(fluxo_mensal)

    # --- Considerações Importantes ---
    consideracoes = []
    consideracoes.append(
        '1) Para o cálculo desta previsão, levamos em consideração a média aritmética dos últimos 12 meses.'
    )
    unidades_inad = len(set(i.get('unidade') for i in (estado.get('inadimplencia') or [])
                             if i.get('decisao') == 'abater'))
    if unidades_inad > 0:
        plural = 'da' if unidades_inad == 1 else 'das'
        consideracoes.append(
            f'2) Consideramos para esta previsão a inadimplência de {unidades_inad} unidade(s), ou seja, '
            f'subtraímos {plural} receita mensal os valores das taxas condominiais dessa(s) unidade(s).'
        )

    conservacao_itens = _itens_presentes(linhas, 'conservacao', _CONSERVACAO_ITENS)
    if conservacao_itens:
        consideracoes.append(
            '3) O item "Gastos com conservação" é composto de despesas de manutenção, tais como: '
            + ', '.join(conservacao_itens) + '.'
        )
    administrativas_itens = _itens_presentes(linhas, 'despesas administrativas', _ADMINISTRATIVAS_ITENS)
    if administrativas_itens:
        consideracoes.append(
            '4) O item "Despesas Administrativas" é composto por gastos com: '
            + ', '.join(administrativas_itens) + '.'
        )

    consideracoes.append(
        '5) A receita, provavelmente, não será suficiente para cobrir as despesas ordinárias nos próximos 12 meses.'
    )

    ultimo_reajuste_raw = resumo.get('ultimo_reajuste')
    if ultimo_reajuste_raw:
        ano_r, mes_r = ultimo_reajuste_raw.split('-')
        mes_nome = MESES_PT[int(mes_r) - 1].upper()
        anos_passados = date.today().year - int(ano_r)
        if date.today().month < int(mes_r):
            anos_passados -= 1
        anos_passados = max(anos_passados, 0)
        sufixo = 'ano' if anos_passados == 1 else 'anos'
        consideracoes.append(
            f'6) O último reajuste do valor da Taxa de Condomínio ocorreu em {mes_nome}/{ano_r}, '
            f'ou seja, há {anos_passados} {sufixo} sem aumento.'
        )

    reajuste_com = max(0.0, (total_previsto / receita_anual_com - 1)) if receita_anual_com > 0 else 0.0
    reajuste_sem = max(0.0, (total_previsto / receita_anual_sem - 1)) if receita_anual_sem > 0 else 0.0
    consideracoes.append(
        '7) Sugestão: caso os valores arrecadados para a constituição do Fundo de Reserva sejam '
        'utilizados para o custeio de despesas ordinárias — prática não recomendada —, sugerimos um '
        f'reajuste de {_pct(reajuste_com)}% na taxa condominial. No entanto, caso os recursos do Fundo '
        'de Reserva sejam preservados para sua finalidade original, recomendamos um reajuste de '
        f'{_pct(reajuste_sem)}% na taxa condominial para os próximos 12 meses.'
    )
    consideracoes.append(
        '8) Lembramos que o reajuste aplicado incidirá também sobre o valor arrecadado para o Fundo de Reserva.'
    )
    consideracoes.append(
        '9) ATENÇÃO/IMPORTANTE: Sugerimos ainda que, para os próximos 12 meses, sejam executadas as '
        'seguintes manutenções: revisão do sistema geral de combate a incêndio (mangueiras, bombas, '
        'alarme, etc), limpeza de fossa e caixas de gordura, limpeza de caixas d\'água, recarga de '
        'extintores, dedetização das áreas comuns e compra de uniforme para o(s) empregado(s), '
        'conforme determina a Convenção Coletiva de Trabalho da Categoria.'
    )

    ctx = {
        'logo_b64': _logo_base64(logo_path),
        'nome_condominio': estado.get('nome_condominio') or '',
        'ano_previsao': estado.get('ano_previsao') or '',
        'data_extenso': _data_extenso(),
        'receitas': [(l, _money(v)) for l, v in receitas],
        'total_receitas': _money(sum(v for _, v in receitas)),
        'despesas': [(l, _money(v)) for l, v in despesas],
        'total_despesas': _money(sum(v for _, v in despesas)),
        'com_fundo': {
            'receita_anual': _money(receita_anual_com),
            'despesa_anual': _money(total_previsto),
            'resultado': _money(resultado_com),
            'status': core._status_resultado(resultado_com),
        },
        'sem_fundo': {
            'receita_anual': _money(receita_anual_sem),
            'despesa_anual': _money(total_previsto),
            'resultado': _money(resultado_sem),
            'status': core._status_resultado(resultado_sem),
        },
        'fundo_reserva_anual': _money(fundo_reserva_anual),
        'tem_fundo_reserva': abs(fundo_reserva_anual) > 0.005,
        'insights': insights,
        'pizza': pizza,
        'grafico_mensal': grafico_mensal,
        'status_geral': status,
        'status_label': {
            'superavit': 'Cenário com superávit',
            'superavit_insuficiente': 'Superávit insuficiente — atenção',
            'deficit': 'Atenção: orçamento em déficit',
        }[status],
        'conclusao_texto': (
            'A previsão usa a média dos últimos 12 meses, separa eventos pontuais da rotina e trata a '
            'inadimplência como redução de receita disponível. '
            + (
                'O resultado é positivo, mas fica abaixo de R$ 2.000 por mês (R$ 24.000 no ano) — por '
                'isso não é saudável nem suficiente como margem de segurança.'
                if status == 'superavit_insuficiente' else
                f'O resultado final é {"DÉFICIT" if status == "deficit" else "SUPERÁVIT"}.'
            )
        ),
        'consideracoes': consideracoes,
    }

    template = Template(_HTML_TEMPLATE)
    html = template.render(**ctx)
    pdf_bytes = HTML(string=html, base_url=os.path.dirname(os.path.abspath(__file__))).write_pdf()
    return pdf_bytes


_HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 20mm 16mm 18mm 16mm;
    @bottom-center { content: "Página " counter(page) " de " counter(pages); font-size: 9px; color: #898781; } }
  * { box-sizing: border-box; }
  body { font-family: 'DejaVu Sans', Arial, sans-serif; color: #14110c; font-size: 11px; line-height: 1.5; }
  h1, h2, h3 { font-family: inherit; margin: 0; }
  .header { display: flex; align-items: center; gap: 16px; border-bottom: 2px solid #1c355e; padding-bottom: 12px; margin-bottom: 18px; }
  .header img { height: 56px; }
  .header .titulo h1 { font-size: 20px; color: #1c355e; }
  .header .titulo p { margin: 2px 0 0; color: #52514e; font-size: 12px; }
  .secao { margin-bottom: 20px; page-break-inside: avoid; }
  .secao h2 { font-size: 14px; color: #1c355e; border-bottom: 1px solid #e1e0d9; padding-bottom: 4px; margin-bottom: 8px; }
  table { width: 100%; border-collapse: collapse; font-size: 10.5px; }
  th, td { padding: 4px 6px; text-align: left; border-bottom: 1px solid #e1e0d9; }
  th { color: #52514e; font-weight: 700; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  tr.total td { font-weight: 700; border-top: 2px solid #14110c; border-bottom: none; }
  .quadros { display: flex; gap: 14px; }
  .quadro { flex: 1; border: 1px solid #e1e0d9; border-radius: 6px; padding: 10px 12px; }
  .quadro h3 { font-size: 12px; margin-bottom: 6px; color: #1c355e; }
  .quadro .linha { display: flex; justify-content: space-between; padding: 3px 0; border-bottom: 1px dashed #e1e0d9; }
  .quadro .linha:last-child { border-bottom: none; font-weight: 700; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; margin-top: 6px; }
  .badge.deficit { background: #fbe3e3; color: #a12626; }
  .badge.superavit_insuficiente { background: #fff3cd; color: #8a6300; }
  .badge.superavit { background: #dff3e3; color: #0f6b2b; }
  ul.insights { margin: 0; padding-left: 16px; }
  ul.insights li { margin-bottom: 4px; }
  .pizza-wrap { display: flex; align-items: center; gap: 18px; }
  .legenda { list-style: none; margin: 0; padding: 0; font-size: 10.5px; }
  .legenda li { display: flex; align-items: center; gap: 6px; margin-bottom: 5px; }
  .legenda i { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
  .mensal-legenda { display: flex; align-items: center; gap: 16px; font-size: 10px; color: #52514e; margin-top: 4px; }
  .mensal-legenda span { display: flex; align-items: center; gap: 5px; }
  .mensal-legenda i { width: 9px; height: 9px; border-radius: 2px; display: inline-block; }
  .mensal-legenda strong { color: #14110c; margin-left: auto; }
  .conclusao-box { border-left: 3px solid #1c355e; padding-left: 10px; }
  .conclusao-box.superavit_insuficiente { border-left-color: #c98500; }
  .conclusao-box.deficit { border-left-color: #a12626; }
  .consideracoes { font-size: 10px; color: #303030; }
  .consideracoes p { margin: 0 0 8px; }
  .assinatura { margin-top: 26px; text-align: center; font-size: 10.5px; }
</style>
</head>
<body>

  <div class="header">
    {% if logo_b64 %}<img src="data:image/png;base64,{{ logo_b64 }}" alt="Porto Real">{% endif %}
    <div class="titulo">
      <h1>{{ nome_condominio }} — {{ ano_previsao }}</h1>
      <p>Previsão orçamentária · {{ data_extenso }}</p>
    </div>
  </div>

  <div class="secao">
    <h2>Receitas</h2>
    <table>
      <thead><tr><th>Conta</th><th class="num">Valor médio mensal</th></tr></thead>
      <tbody>
        {% for label, valor in receitas %}<tr><td>{{ label }}</td><td class="num">{{ valor }}</td></tr>{% endfor %}
        <tr class="total"><td>Total</td><td class="num">{{ total_receitas }}</td></tr>
      </tbody>
    </table>
  </div>

  <div class="secao">
    <h2>Despesas</h2>
    <table>
      <thead><tr><th>Conta</th><th class="num">Valor médio mensal</th></tr></thead>
      <tbody>
        {% for label, valor in despesas %}<tr><td>{{ label }}</td><td class="num">{{ valor }}</td></tr>{% endfor %}
        <tr class="total"><td>Total previsto</td><td class="num">{{ total_despesas }}</td></tr>
      </tbody>
    </table>
  </div>

  <div class="secao">
    <h2>Quadro de leitura</h2>
    <div class="quadros">
      <div class="quadro">
        <h3>Com fundo de reserva</h3>
        <div class="linha"><span>Receita anual</span><span>{{ com_fundo.receita_anual }}</span></div>
        <div class="linha"><span>Despesa anual</span><span>{{ com_fundo.despesa_anual }}</span></div>
        <div class="linha"><span>Resultado</span><span>{{ com_fundo.resultado }}</span></div>
        <span class="badge {{ com_fundo.status }}">
          {{ {'superavit': 'Superávit', 'superavit_insuficiente': 'Superávit insuficiente', 'deficit': 'Déficit'}[com_fundo.status] }}
        </span>
      </div>
      <div class="quadro">
        <h3>Sem fundo de reserva</h3>
        <div class="linha"><span>Receita anual</span><span>{{ sem_fundo.receita_anual }}</span></div>
        <div class="linha"><span>Despesa anual</span><span>{{ sem_fundo.despesa_anual }}</span></div>
        <div class="linha"><span>Resultado</span><span>{{ sem_fundo.resultado }}</span></div>
        <span class="badge {{ sem_fundo.status }}">
          {{ {'superavit': 'Superávit', 'superavit_insuficiente': 'Superávit insuficiente', 'deficit': 'Déficit'}[sem_fundo.status] }}
        </span>
      </div>
    </div>
  </div>

  <div class="secao">
    <h2>Insights</h2>
    <ul class="insights">
      {% for item in insights %}<li>{{ item }}</li>{% endfor %}
    </ul>
  </div>

  {% if pizza %}
  <div class="secao">
    <h2>Composição das despesas</h2>
    <div class="pizza-wrap">
      {{ pizza.svg|safe }}
      <ul class="legenda">
        {% for f in pizza.fatias %}
        <li><i style="background:{{ f.cor }}"></i>{{ f.label }} — {{ '%.1f'|format(f.frac*100) }}%</li>
        {% endfor %}
      </ul>
    </div>
  </div>
  {% endif %}

  {% if grafico_mensal %}
  <div class="secao">
    <h2>Evolução mensal</h2>
    {{ grafico_mensal.svg|safe }}
    <div class="mensal-legenda">
      <span><i style="background:#1c355e"></i>Receita</span>
      <span><i style="background:#c3c2b7"></i>Despesa</span>
      {% if grafico_mensal.pior_mes_txt %}<strong>{{ grafico_mensal.pior_mes_txt }}</strong>{% endif %}
    </div>
  </div>
  {% endif %}

  <div class="secao">
    <h2>Conclusão</h2>
    <div class="conclusao-box {{ status_geral }}">
      <strong>{{ status_label }}</strong>
      <p>{{ conclusao_texto }}</p>
    </div>
  </div>

  <div class="secao consideracoes" style="page-break-before: always;">
    <h2 style="text-align:center;">CONSIDERAÇÕES IMPORTANTES</h2>
    {% for c in consideracoes %}<p>{{ c }}</p>{% endfor %}
    <div class="assinatura">
      <p>Cabo Frio, {{ data_extenso }}</p>
      <p><strong>PORTO REAL IMÓVEIS</strong></p>
    </div>
  </div>

</body>
</html>
"""
