#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RELATORIO PDF PARA O CONDOMINIO

Gera um PDF limpo, para entrega ao cliente, a partir do estado ja revisado
de uma sessao (mesmos dados exibidos na tela de resultado do webapp).

Layout: logo Porto Real -> nome do condominio/ano -> Receitas -> Despesas ->
Quadro de leitura (com/sem fundo lado a lado) -> Composicao das despesas
(pizza) -> Evolucao mensal -> Conclusao -> Considerações Importantes.
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
# pizza do relatório — não ciclar, não gerar cores.
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
    return (n.startswith('total') or 'subtotal' in n or 'saldo' in n or 'deficit' in n
            or 'superavit' in n or 'inflacao' in n or 'aumento' in n)


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


def _consolidar_despesas_relatorio(linhas, resumo):
    """Replica o agrupamento da seção Despesas do XLSX antigo no PDF."""
    ativas = [
        (idx, linha) for idx, linha in enumerate(linhas or [])
        if abs(float(linha.get('final') or 0)) > 0.005
    ]
    consumidos = set()
    despesas = []

    def ng(linha):
        return _norm(linha.get('grupo'))

    def nc(linha):
        return _norm(linha.get('classe'))

    def somar(label, predicado):
        valor = 0.0
        for idx, linha in ativas:
            if idx not in consumidos and predicado(linha):
                valor += float(linha.get('final') or 0)
                consumidos.add(idx)
        if abs(valor) > 0.005:
            despesas.append((label, valor))

    categorias = [
        ('Despesas com Pessoal', lambda l: 'pessoal' in ng(l)),
        ('Luz do Condomínio', lambda l: 'tarifas publicas' in ng(l) and 'luz' in nc(l)),
        ('Água do Condomínio', lambda l: 'tarifas publicas' in ng(l) and 'agua' in nc(l)),
        ('Telefone do Condomínio', lambda l: 'tarifas publicas' in ng(l) and 'telefone' in nc(l)),
        ('Gás do Condomínio', lambda l: 'tarifas publicas' in ng(l) and 'gas' in nc(l)),
        ('Material de Limpeza', lambda l: 'limpeza' in nc(l)
         and any(t in nc(l) for t in ('material', 'produto', 'mat.'))),
        ('Gastos com conservação', lambda l: 'conservacao' in ng(l)
         or ('diversas' in ng(l) and 'seguro' not in nc(l))),
        ('Tarifas Bancárias', lambda l: 'tarifas bancarias' in ng(l)
         or 'tarifas bancarias' in nc(l)),
        ('Seguro de Incêndio Obrigatório', lambda l: 'seguro' in nc(l) and 'vida' not in nc(l)),
    ]
    for label, predicado in categorias:
        somar(label, predicado)

    # Mesma seleção e ordem de contratos/pro-labore de _linhas_contratuais,
    # usada pelo XLSX antes da retirada da etapa de documento intermediário.
    def ordem_contrato(item):
        idx, linha = item
        classe = nc(linha)
        tokens = set(re.findall(r'[a-z0-9]+', classe))
        if 'elevador' in classe:
            prioridade = 0
        elif 'jardim' in classe:
            prioridade = 1
        elif 'tv' in tokens or 'cabo' in tokens:
            prioridade = 2
        elif 'eta' in tokens or 'piscina' in tokens:
            prioridade = 3
        elif 'hidraul' in classe or 'eletric' in classe:
            prioridade = 4
        elif any(k in classe for k in ('interf', 'camera', 'portao', 'antena')):
            prioridade = 5
        elif 'vigia' in classe:
            prioridade = 6
        elif 'contab' in classe:
            prioridade = 7
        elif 'internet' in classe or tokens & {'net', 'oi', 'vivo', 'claro', 'fibra'}:
            prioridade = 8
        elif 'administr' in classe:
            prioridade = 9
        elif any(k in classe for k in ('sindico', 'pro-labore', 'prolabore', 'ajuda de custo')):
            prioridade = 10
        else:
            prioridade = 11
        return prioridade, idx

    contratuais = [
        item for item in ativas
        if ('contrato' in ng(item[1]) or 'pro-labore' in ng(item[1])
            or 'prolabore' in ng(item[1])
            or ('sindico' in ng(item[1]) and 'reembolso' in ng(item[1])))
    ]
    labels_contratos = set()
    for idx, linha in sorted(contratuais, key=ordem_contrato):
        if idx in consumidos:
            continue
        label = str(linha.get('classe') or '').strip()
        if _norm(label) in labels_contratos:
            continue
        despesas.append((label, float(linha.get('final') or 0)))
        labels_contratos.add(_norm(label))
        consumidos.add(idx)

    categorias_finais = [
        ('Despesas Administrativas', lambda l: 'administrativa' in ng(l)),
        ('Despesas Cartoriais e Honorários', lambda l: any(
            t in ng(l) or t in nc(l) for t in ('cartori', 'honorari'))),
        ('Despesas com Obras/Benfeitorias', lambda l: any(
            t in ng(l) for t in ('obras', 'benfeitoria'))),
    ]
    for label, predicado in categorias_finais:
        somar(label, predicado)

    # As provisões fazem parte de conservação e não aparecem como linha solta.
    provisoes = (float(resumo.get('prov_laudo') or 0)
                 + float(resumo.get('prov_incendio') or 0))
    if abs(provisoes) > 0.005:
        for pos, (label, valor) in enumerate(despesas):
            if _norm(label) == _norm('Gastos com conservação'):
                despesas[pos] = (label, valor + provisoes)
                break
        else:
            despesas.append(('Gastos com conservação', provisoes))

    # O XLSX preservava somente as classes que não pertenciam a nenhuma das
    # categorias conhecidas, inclusive desambiguando rótulos repetidos.
    labels_existentes = {_norm(label) for label, _ in despesas}
    for idx, linha in ativas:
        if idx in consumidos:
            continue
        label = str(linha.get('classe') or linha.get('grupo')
                    or 'Despesa sem classificação').strip()
        if _norm(label) in labels_existentes:
            label = f"{linha.get('grupo') or 'Outros'} - {label}"
        despesas.append((label, float(linha.get('final') or 0)))
        labels_existentes.add(_norm(label))

    # Mantém também a salvaguarda de fechamento usada no documento antigo.
    subtotal_alvo = float(resumo.get('subtotal') or 0)
    diferenca = round(subtotal_alvo - sum(valor for _, valor in despesas), 2)
    if subtotal_alvo and abs(diferenca) > 0.05:
        despesas.append(('Ajustes de previsão', diferenca))

    return [(label, valor / 12) for label, valor in despesas]


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
def gerar_relatorio_pdf(estado, logo_path=None, com_fundo_override=None):
    resumo = estado.get('resumo') or {}
    linhas = estado.get('linhas_contas') or []
    fluxo_mensal = estado.get('fluxo_mensal') or []
    cenarios = resumo.get('cenarios') or {}
    com_fundo = cenarios.get('com_fundo') or {}
    sem_fundo = cenarios.get('sem_fundo') or {}
    fundo_reserva_anual = cenarios.get('fundo_reserva_anual') or 0
    total_previsto = resumo.get('total_previsto') or 0
    impacto_inad_mensal = resumo.get('impacto_receita_mensal') or 0
    inflacao = float(resumo.get('inflacao') or 0)

    com_fundo_pref = com_fundo_override if com_fundo_override is not None else estado.get('com_fundo', True)

    previsao_final = estado.get('previsao_final') or []
    receitas, _ = _extrair_receitas_despesas(previsao_final)
    receitas = [
        ('Taxas de Condomínio', valor)
        if _norm(label) == 'receita media do periodo' else (label, valor)
        for label, valor in receitas
    ]
    # Filtra Fundo de Reserva das receitas quando o usuario escolheu SEM FUNDO
    if not com_fundo_pref:
        receitas = [(l, v) for l, v in receitas
                     if not ('fundo' in _norm(l) and 'reserva' in _norm(l))]
    if not receitas:
        receitas = [('Taxas de Condomínio', resumo.get('receita_mensal') or 0)]
    despesas = _consolidar_despesas_relatorio(linhas, resumo)

    grupos = _agrupar_por_grupo(linhas)
    total_grupo = sum(g['value'] for g in grupos)

    receita_anual_com = com_fundo.get('receita_anual') or 0
    receita_anual_sem = sem_fundo.get('receita_anual') or 0
    resultado_com = com_fundo.get('resultado') or (receita_anual_com - total_previsto)
    resultado_sem = sem_fundo.get('resultado') or (receita_anual_sem - total_previsto)
    saldo_ajustado_anual = resultado_com - impacto_inad_mensal * 12
    status = com_fundo.get('status_resultado') or core._status_resultado(saldo_ajustado_anual)

    # Meta do reajuste NAO e zerar o resultado (ponto de equilibrio) — e atingir a
    # mesma margem de seguranca (SUPERAVIT_MINIMO, R$2.000/mes) usada no restante
    # do relatorio. Sem isso, o reajuste ficava 0,0% mesmo quando o Quadro de
    # leitura classificava o resultado como "Superavit insuficiente" logo acima.
    meta_receita = total_previsto + core.SUPERAVIT_MINIMO
    reajuste_com = max(0.0, (meta_receita / receita_anual_com - 1)) if receita_anual_com > 0 else 0.0
    reajuste_sem = max(0.0, (meta_receita / receita_anual_sem - 1)) if receita_anual_sem > 0 else 0.0

    pizza = _grafico_pizza_svg(grupos, total_grupo)
    grafico_mensal = _grafico_mensal_svg(fluxo_mensal)

    # --- Considerações Importantes (numeradas sequencialmente ao final —
    # itens condicionais ausentes nao deixam buraco na numeracao) ---
    consideracoes = []

    n_meses_balanco = resumo.get('n_meses_balanco') or 12
    if n_meses_balanco >= 12:
        consideracoes.append(
            'Para o cálculo desta previsão, levamos em consideração a média aritmética dos últimos 12 meses.'
        )
    else:
        consideracoes.append(
            f'Para o cálculo desta previsão, levamos em consideração a média aritmética dos últimos '
            f'{n_meses_balanco} meses — período disponível, já que o condomínio iniciou a administração '
            'com a Porto Real recentemente.'
        )

    unidades_inad = len(set(i.get('unidade') for i in (estado.get('inadimplencia') or [])
                             if i.get('decisao') == 'abater'))
    if unidades_inad > 0:
        plural = 'da' if unidades_inad == 1 else 'das'
        consideracoes.append(
            f'Consideramos para esta previsão a inadimplência de {unidades_inad} unidade(s), ou seja, '
            f'subtraímos {plural} receita mensal os valores das taxas condominiais dessa(s) unidade(s).'
        )

    conservacao_itens = _itens_presentes(linhas, 'conservacao', _CONSERVACAO_ITENS)
    if conservacao_itens:
        consideracoes.append(
            'O item "Gastos com conservação" é composto de despesas de manutenção, tais como: '
            + ', '.join(conservacao_itens) + '.'
        )
    administrativas_itens = _itens_presentes(linhas, 'despesas administrativas', _ADMINISTRATIVAS_ITENS)
    if administrativas_itens:
        consideracoes.append(
            'O item "Despesas Administrativas" é composto por gastos com: '
            + ', '.join(administrativas_itens) + '.'
        )

    consideracoes.append(
        'A receita, provavelmente, não será suficiente para cobrir as despesas ordinárias nos próximos 12 meses.'
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
            f'O último reajuste do valor da Taxa de Condomínio ocorreu em {mes_nome}/{ano_r}, '
            f'ou seja, há {anos_passados} {sufixo} sem aumento.'
        )

    consideracoes.append(
        'Sugestão: caso os valores arrecadados para a constituição do Fundo de Reserva sejam '
        'utilizados para o custeio de despesas ordinárias — prática não recomendada —, sugerimos um '
        f'reajuste de {_pct(reajuste_com)}% na taxa condominial. No entanto, caso os recursos do Fundo '
        'de Reserva sejam preservados para sua finalidade original, recomendamos um reajuste de '
        f'{_pct(reajuste_sem)}% na taxa condominial para os próximos 12 meses.'
    )
    consideracoes.append(
        'Lembramos que o reajuste aplicado incidirá também sobre o valor arrecadado para o Fundo de Reserva.'
    )
    consideracoes.append(
        'ATENÇÃO/IMPORTANTE: Sugerimos ainda que, para os próximos 12 meses, sejam executadas as '
        'seguintes manutenções: revisão do sistema geral de combate a incêndio (mangueiras, bombas, '
        'alarme, etc), limpeza de fossa e caixas de gordura, limpeza de caixas d\'água, recarga de '
        'extintores, dedetização das áreas comuns e compra de uniforme para o(s) empregado(s), '
        'conforme determina a Convenção Coletiva de Trabalho da Categoria.'
    )
    consideracoes = [f'{i + 1}) {texto}' for i, texto in enumerate(consideracoes)]

    subtotal_mensal = sum(v for _, v in despesas)
    aumento_mensal = subtotal_mensal * inflacao if inflacao > 0 else 0
    total_despesas_mensal = subtotal_mensal + aumento_mensal

    # Quadro de leitura: mostra so o cenario selecionado pelo usuario.
    # Se COM FUNDO e tem FR, mostra os dois lados (informativo).
    cenario_quadro = sem_fundo if not com_fundo_pref else com_fundo
    status_quadro = cenario_quadro.get('status_resultado') or (
        core._status_resultado(cenario_quadro.get('resultado') or 0))
    resultado_quadro = cenario_quadro.get('resultado') or (
        (receita_anual_sem if not com_fundo_pref else receita_anual_com) - total_previsto)

    ctx = {
        'logo_b64': _logo_base64(logo_path),
        'nome_condominio': estado.get('nome_condominio') or '',
        'ano_previsao': estado.get('ano_previsao') or '',
        'data_extenso': _data_extenso(),
        'receitas': [(l, _money(v)) for l, v in receitas],
        'total_receitas': _money(sum(v for _, v in receitas)),
        'despesas': [(l, _money(v)) for l, v in despesas],
        'subtotal_mensal': _money(subtotal_mensal),
        'inflacao_pct': f'{inflacao * 100:.1f}'.replace('.', ','),
        'aumento_mensal': _money(aumento_mensal),
        'total_despesas': _money(total_despesas_mensal),
        'com_fundo_pref': com_fundo_pref,
        'com_fundo': {
            'receita_mensal': _money(receita_anual_com / 12),
            'despesa_mensal': _money(total_previsto / 12),
            'resultado_mensal': _money(resultado_com / 12),
            'status': core._status_resultado(resultado_com),
        },
        'sem_fundo': {
            'receita_mensal': _money(receita_anual_sem / 12),
            'despesa_mensal': _money(total_previsto / 12),
            'resultado_mensal': _money(resultado_sem / 12),
            'status': core._status_resultado(resultado_sem),
        },
        'quadro': {
            'receita_mensal': _money((receita_anual_sem if not com_fundo_pref else receita_anual_com) / 12),
            'despesa_mensal': _money(total_previsto / 12),
            'resultado_mensal': _money(resultado_quadro / 12),
            'status': status_quadro,
            'label': 'Sem fundo de reserva' if not com_fundo_pref else 'Com fundo de reserva',
        },
        'fundo_reserva_anual': _money(fundo_reserva_anual),
        'tem_fundo_reserva': abs(fundo_reserva_anual) > 0.005,
        'pizza': pizza,
        'grafico_mensal': grafico_mensal,
        'status_geral': status_quadro,
        'status_label': {
            'superavit': 'Cenário com superávit',
            'superavit_insuficiente': 'Superávit insuficiente — atenção',
            'deficit': 'Atenção: orçamento em déficit',
        }[status_quadro],
        'conclusao_texto': (
            f'A previsão usa a média dos últimos {n_meses_balanco} meses, separa eventos pontuais da '
            'rotina e trata a inadimplência como redução de receita disponível. '
            + (
                f'O resultado mensal é de {_money(resultado_quadro / 12)} — '
                'positivo, mas abaixo dos R$ 2.000 por mês (R$ 24.000 no ano) considerados margem de '
                'segurança suficiente.'
                if status_quadro == 'superavit_insuficiente' else
                f'O resultado mensal é de {_money(resultado_quadro / 12)} '
                f'({"DÉFICIT" if status_quadro == "deficit" else "SUPERÁVIT"}).'
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
  tr.subtotal td { font-weight: 700; border-top: 1px solid #898781; border-bottom: none; color: #52514e; }
  .quadros { display: flex; gap: 14px; }
  .quadro { flex: 1; border: 1px solid #e1e0d9; border-radius: 6px; padding: 10px 12px; }
  .quadro h3 { font-size: 12px; margin-bottom: 6px; color: #1c355e; }
  .quadro .linha { display: flex; justify-content: space-between; padding: 3px 0; border-bottom: 1px dashed #e1e0d9; }
  .quadro .linha:last-child { border-bottom: none; font-weight: 700; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; margin-top: 6px; }
  .badge.deficit { background: #fbe3e3; color: #a12626; }
  .badge.superavit_insuficiente { background: #fff3cd; color: #8a6300; }
  .badge.superavit { background: #dff3e3; color: #0f6b2b; }
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
        <tr class="total"><td>Total mensal</td><td class="num">{{ total_receitas }}</td></tr>
      </tbody>
    </table>
  </div>

  <div class="secao">
    <h2>Despesas</h2>
    <table>
      <thead><tr><th>Conta</th><th class="num">Valor médio mensal</th></tr></thead>
      <tbody>
        {% for label, valor in despesas %}<tr><td>{{ label }}</td><td class="num">{{ valor }}</td></tr>{% endfor %}
        <tr class="subtotal"><td>SUBTOTAL</td><td class="num">{{ subtotal_mensal }}</td></tr>
        <tr><td>Aumento Previsto (Salários, tarifas, serviços) = {{ inflacao_pct }}% sobre o SUBTOTAL</td><td class="num">{{ aumento_mensal }}</td></tr>
        <tr class="total"><td>TOTAL PREVISTO</td><td class="num">{{ total_despesas }}</td></tr>
      </tbody>
    </table>
  </div>

  <div class="secao">
    <h2>Quadro de leitura</h2>
    <div class="quadros">
      {% if com_fundo_pref and tem_fundo_reserva %}
      <div class="quadro">
        <h3>Com fundo de reserva</h3>
        <div class="linha"><span>Receita mensal</span><span>{{ com_fundo.receita_mensal }}</span></div>
        <div class="linha"><span>Despesa mensal</span><span>{{ com_fundo.despesa_mensal }}</span></div>
        <div class="linha"><span>Resultado mensal</span><span>{{ com_fundo.resultado_mensal }}</span></div>
        <span class="badge {{ com_fundo.status }}">
          {{ {'superavit': 'Superávit', 'superavit_insuficiente': 'Superávit insuficiente', 'deficit': 'Déficit'}[com_fundo.status] }}
        </span>
      </div>
      <div class="quadro">
        <h3>Sem fundo de reserva</h3>
        <div class="linha"><span>Receita mensal</span><span>{{ sem_fundo.receita_mensal }}</span></div>
        <div class="linha"><span>Despesa mensal</span><span>{{ sem_fundo.despesa_mensal }}</span></div>
        <div class="linha"><span>Resultado mensal</span><span>{{ sem_fundo.resultado_mensal }}</span></div>
        <span class="badge {{ sem_fundo.status }}">
          {{ {'superavit': 'Superávit', 'superavit_insuficiente': 'Superávit insuficiente', 'deficit': 'Déficit'}[sem_fundo.status] }}
        </span>
      </div>
      {% else %}
      <div class="quadro">
        <h3>{{ quadro.label }}</h3>
        <div class="linha"><span>Receita mensal</span><span>{{ quadro.receita_mensal }}</span></div>
        <div class="linha"><span>Despesa mensal</span><span>{{ quadro.despesa_mensal }}</span></div>
        <div class="linha"><span>Resultado mensal</span><span>{{ quadro.resultado_mensal }}</span></div>
        <span class="badge {{ quadro.status }}">
          {{ {'superavit': 'Superávit', 'superavit_insuficiente': 'Superávit insuficiente', 'deficit': 'Déficit'}[quadro.status] }}
        </span>
      </div>
      {% endif %}
    </div>
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
