#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RELATORIO PDF PARA O CONDOMINIO

Gera um PDF limpo, para entrega ao cliente, a partir do estado ja revisado
de uma sessao (mesmos dados exibidos na tela de resultado do webapp).

Layout: logo Porto Real -> nome do condominio/ano -> Receitas -> Despesas ->
Quadro de leitura (uma caixa por opção de receita) -> Composicao das despesas
(barras) -> Conclusao -> Considerações Importantes.
"""
import base64
import math
import os
import re
import textwrap
import unicodedata
from datetime import date
from html import escape

from jinja2 import Template
from weasyprint import HTML

import previsao as core

MESES_PT = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
            'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

BARRAS_LIMITE = 5


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


def _tempo_desde_reajuste(ano, mes, hoje=None):
    """Formata o intervalo completo desde o reajuste em anos e/ou meses."""
    hoje = hoje or date.today()
    total_meses = max(0, (hoje.year - int(ano)) * 12 + hoje.month - int(mes))
    anos, meses = divmod(total_meses, 12)

    partes = []
    if anos:
        partes.append(f'{anos} {"ano" if anos == 1 else "anos"}')
    if meses or not partes:
        partes.append(f'{meses} {"mês" if meses == 1 else "meses"}')
    return ' e '.join(partes)


def _reajuste_necessario(total_previsto, receita_total):
    """Variação absoluta entre total e receita: |TOTAL / RECEITA - 1|."""
    receita_total = float(receita_total or 0)
    if receita_total <= 0:
        return 0.0
    return abs(float(total_previsto or 0) / receita_total - 1)


def _opcoes_receita(receita_anual, fundo_anual, nao_ordinarias, total_previsto):
    """Opções de receita para custear as despesas ordinárias (feedback José
    Henrique 09/2026): só taxa de condomínio; + Fundo de Reserva; + aluguel;
    + Fundo + aluguel. Cada condomínio mostra só as que tem.
    receita_anual = receita ordinária (taxas + repasses), já sem o fundo e
    sem a inadimplência considerada."""
    aluguel_anual = sum(float(i.get('mensal') or 0) for i in nao_ordinarias or []) * 12
    nome_aluguel = (nao_ordinarias[0]['classe'] if len(nao_ordinarias or []) == 1
                    else 'Aluguéis de espaço')
    tem_fundo = fundo_anual > 0.005
    tem_aluguel = aluguel_anual > 0.005
    # Nomes curtos (usuária, 23/10/2026): a receita ordinária já traz taxa, água,
    # recorrentes e receitas manuais; a tabela de receitas detalha cada uma.
    sem, com = 'Receitas sem fundo de reserva', 'Receitas com fundo de reserva'
    if not tem_fundo:  # sem fundo no relatório, só "Receitas" (usuária, 30/10/2026)
        sem = 'Receitas'
    candidatas = [
        (sem, receita_anual, True, False),
        (com, receita_anual + fundo_anual, tem_fundo, True),
        (f'{sem} + {nome_aluguel}', receita_anual + aluguel_anual, tem_aluguel, False),
        (f'{com} + {nome_aluguel}', receita_anual + fundo_anual + aluguel_anual, tem_fundo and tem_aluguel, True),
    ]
    opcoes = []
    for label, receita, aplica, usa_fundo in candidatas:
        if not aplica:
            continue
        resultado = receita - float(total_previsto or 0)
        opcoes.append({
            'label': label,
            'receita_anual': receita,
            'resultado': resultado,
            'status': core._status_resultado(resultado),
            # com sobra não há reajuste; com falta, |TOTAL / RECEITA - 1|
            'reajuste': _reajuste_necessario(total_previsto, receita) if resultado < 0 else 0.0,
            'usa_fundo': usa_fundo,
        })
    return opcoes


def _consideracao_suficiencia_receita(resultado_anual):
    """Conclusão baseada na receita ordinária, sem usar o Fundo de Reserva."""
    if resultado_anual < 0:
        return ('A receita ordinária prevista, sem utilizar o Fundo de Reserva, não será suficiente '
                'para cobrir as despesas ordinárias nos próximos 12 meses.')
    texto = ('A receita ordinária prevista será suficiente para cobrir as despesas ordinárias '
             'nos próximos 12 meses, sem utilizar o Fundo de Reserva.')
    if resultado_anual / 12 < 2000:
        texto += ' A margem mensal é inferior a R$ 2.000,00 e requer atenção.'
    return texto


USO_DO_FUNDO = ('Caso os valores arrecadados para a constituição do Fundo de Reserva sejam utilizados para o '
                'custeio de despesas ordinárias — prática não recomendada —, ')
FUNDO_PRESERVADO = (' No entanto, caso os recursos do Fundo de Reserva sejam preservados para sua finalidade '
                    'original, ')
SEM_REAJUSTE = 'não é necessário reajuste da taxa condominial'


def _consideracao_opcoes(opcoes):
    """Texto do José Henrique (28/10/2026): X = receitas com fundo, Y = receitas
    sem fundo. Sem fundo de reserva no relatório, só a frase final com Y (José
    29/10/2026). Opções com aluguel não entram no texto (continuam no quadro)."""
    sem = opcoes[0]
    if not (len(opcoes) > 1 and opcoes[1]['usa_fundo']):
        if sem['reajuste'] > 0:
            return (f'Recomendamos um reajuste de {_pct(sem["reajuste"])}% na taxa condominial '
                    'para os próximos 12 meses.')
        return SEM_REAJUSTE[0].upper() + SEM_REAJUSTE[1:] + ' para os próximos 12 meses.'
    com = opcoes[1]
    uso = (f'sugerimos um reajuste de {_pct(com["reajuste"])}% na taxa condominial.' if com['reajuste'] > 0
           else f'{SEM_REAJUSTE}.')
    preservado = (f'recomendamos um reajuste de {_pct(sem["reajuste"])}% na taxa condominial' if sem['reajuste'] > 0
                  else SEM_REAJUSTE)
    return USO_DO_FUNDO + uso + FUNDO_PRESERVADO + preservado + ' para os próximos 12 meses.'


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


def _normalizar_receitas_pdf(receitas):
    """Exibe receitas líquidas, sem repetir o desconto em linha separada."""
    descontos = sum(valor for label, valor in receitas if 'desconto' in _norm(label))
    linhas = [(label, valor) for label, valor in receitas if 'desconto' not in _norm(label)]
    if abs(descontos) > 0.005:
        pos = next((i for i, (label, _) in enumerate(linhas)
                    if _norm(label) in ('taxas de condominio', 'taxa de condominio')), None)
        if pos is None:
            linhas.append(('Receita líquida', descontos))
        else:
            label, valor = linhas[pos]
            linhas[pos] = (label, valor + descontos)
    return [(label.strip().capitalize(), valor) for label, valor in linhas]


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


# Serviço identificado pela descrição da NF — usado para abrir um contrato
# genérico ("Contrato de Manutenção") que paga mais de um fornecedor
# (feedback José Henrique 09/2026: Segurança 350 + Piscina 700 numa linha só).
_SERVICOS_CONTRATO = [
    (('seguranca', 'monitoramento', 'camera', 'cftv', 'alarme'), 'Contrato de Segurança Eletrônica'),
    (('piscina',), 'Contrato de Manutenção da Piscina'),
    (('elevador',), 'Contrato de Manutenção do Elevador'),
    (('jardim', 'jardinagem'), 'Contrato de Jardinagem'),
    (('portao', 'porta automatica'), 'Contrato de Manutenção do Portão'),
    (('interfone',), 'Contrato de Manutenção do Interfone'),
    (('dedetiza',), 'Contrato de Dedetização'),
]


def _servico_contrato(descricao):
    texto = _norm(descricao)
    for termos, label in _SERVICOS_CONTRATO:
        if any(t in texto for t in termos):
            return label
    return None


def _dividir_contrato_por_servico(linha, lancamentos):
    """Divide o valor final de um contrato entre os serviços que ele paga,
    na proporção dos pagamentos dos 3 últimos meses (mesma janela da R6).
    Devolve [(label, valor)] ou None quando não há o que dividir (um serviço
    só, ou alguma NF sem serviço reconhecível)."""
    chave = (_norm(linha.get('grupo')), _norm(linha.get('classe')))
    nfs = [l for l in (lancamentos or [])
           if (_norm(l.get('grupo')), _norm(l.get('classe'))) == chave
           and float(l.get('valor_pago') or 0) > 0.005]
    if not nfs:
        return None
    servicos = [_servico_contrato(l.get('descricao')) for l in nfs]
    if None in servicos or len(set(servicos)) < 2:
        return None
    meses = sorted({str(l.get('data') or '')[:7] for l in nfs})[-3:]
    por_servico = {}
    for nf, servico in zip(nfs, servicos):
        if str(nf.get('data') or '')[:7] in meses:
            por_servico[servico] = por_servico.get(servico, 0.0) + float(nf['valor_pago'])
    total = sum(por_servico.values())
    if total <= 0.005:
        return None
    final = float(linha.get('final') or 0)
    return [(servico, final * valor / total) for servico, valor in por_servico.items()]


def _categoria_despesa(linha):
    """Categoria de apresentação; não altera classificação nem valores da previsão.

    Contratos explícitos têm prioridade sobre grupos genéricos. Quando o grupo
    vem vazio ou incompleto, classes inequívocas continuam na categoria correta.
    A tabela e os textos de composição usam esta mesma decisão.
    """
    grupo = _norm(linha.get('grupo'))
    classe = _norm(linha.get('classe'))
    texto = re.sub(r'[^a-z0-9]+', ' ', classe).strip()
    if 'contrato' in grupo or re.search(r'\bcontrato\b', classe):
        return 'contratos'
    if any(t in grupo or t in classe for t in ('pro-labore', 'prolabore', 'pro labore')) or (
            'sindico' in grupo and 'reembolso' in grupo):
        return 'prolabore'
    if any(t in grupo for t in ('pessoal', 'funcionario', 'folha de pagamento')):
        return 'pessoal'
    if re.match(r'^(?:fgts|inss|ferias|salario|adiantamento de salario|13o? salario|decimo terceiro|'
                r'contribuicao sindical|uniformes|vale alimentacao|vale transporte|outros pessoal|'
                r'seguro de vida|rescisao|indenizacao trabalhista)\b', texto):
        return 'pessoal'
    if _eh_material_limpeza(linha):
        return 'limpeza'
    if 'tarifas publicas' in grupo or re.match(
            r'^(?:luz|agua|telefone|gas|energia eletrica) (?:do condominio|condominial)\b', texto):
        for token, categoria in (('luz', 'luz'), ('energia', 'luz'), ('agua', 'agua'),
                                 ('telefone', 'telefone'), ('gas', 'gas')):
            if token in texto.split():
                return categoria
        return 'tarifas_publicas'
    if 'tarifas bancarias' in grupo or re.search(r'\b(?:tarifas?|taxas?) bancari', classe):
        return 'bancarias'
    if 'seguro' in classe and 'vida' not in classe:
        return 'seguro'
    if any(t in grupo for t in ('obras', 'benfeitoria')):
        return 'obras'
    if any(t in grupo or t in classe for t in ('cartori', 'honorari')):
        return 'cartoriais'
    if 'administrativa' in grupo or re.match(
            r'^(?:xerox|correios?|material de expediente|impressao boleto|13.*taxa de administracao)\b', texto):
        return 'administrativas'
    if any(t in grupo for t in ('conservacao', 'manutencao', 'manutencoes', 'diversas')) or re.match(
            r'^(?:manutencao|manutencoes|outras manutencoes|reparo|reparos|conserto|pequenas reformas|'
            r'dedetizacao|descupinizacao|recarga de extintores|limpeza (?:caixa|de caixa|de fossa)|'
            r'material (?:eletrico|hidraulico|de cameras|de portao)|outros materiais(?: de)?)\b', texto):
        return 'conservacao'
    return 'outras'


def _rotulo_contrato(linha, linhas):
    """Completa nomes cortados somente quando há uma correspondência inequívoca."""
    label = ' '.join(str(linha.get('classe') or 'Contrato de serviços').split()).strip()
    key = _norm(label)
    candidatos = {
        str(l.get('classe')).strip() for l in linhas
        if _categoria_despesa(l) == 'contratos' and _norm(l.get('classe')).startswith(key + ' ')
    }
    if len(candidatos) == 1:
        label = candidatos.pop()
    texto = _norm(label)
    servicos = [
        ('elevador', 'Contrato de Manutenção do Elevador'),
        ('jardim', 'Contrato de Jardinagem'),
        ('jardinagem', 'Contrato de Jardinagem'),
        ('internet', 'Contrato de Assinatura de Internet'),
        ('administr', 'Contrato Prestação Serviço Administração'),
        ('piscina', 'Contrato de Manutenção da Piscina'),
        ('seguranca', 'Contrato de Segurança Eletrônica'),
        ('interfone', 'Contrato de Manutenção do Interfone'),
        ('portao', 'Contrato de Manutenção do Portão'),
    ]
    for termo, titulo in servicos:
        if termo in texto:
            return titulo
    # Um nome incompleto não vira uma segunda linha solta no fim da tabela.
    label = re.sub(r'\s+(?:de|do|da)\s*$', '', label, flags=re.I)
    return label.capitalize() if label.isupper() else label


def _ordem_rotulo_contrato(label):
    texto = _norm(label)
    for i, termos in enumerate((('elevador',), ('jardim', 'jardinagem'), ('tv', 'cabo'),
                                ('eta', 'piscina'), ('hidraul', 'eletric'),
                                ('interfone', 'camera', 'seguranca', 'portao', 'antena'),
                                ('vigia',), ('contab',), ('internet',), ('administr',))):
        if any(t in texto for t in termos):
            return i, texto
    return 10, texto


def _consolidar_despesas_relatorio(linhas, resumo, lancamentos=None):
    """Tabela resumida, em ordem fixa, com cada valor de origem usado uma vez."""
    ativas = [
        (idx, linha) for idx, linha in enumerate(linhas or [])
        if abs(float(linha.get('final') or 0)) > 0.005
    ]
    consumidos = {idx for idx, l in ativas if l.get('manual')}
    despesas = []

    def ng(linha):
        return _categoria_despesa(linha)

    def somar(label, predicado):
        valor = 0.0
        for idx, linha in ativas:
            if idx not in consumidos and predicado(linha):
                valor += float(linha.get('final') or 0)
                consumidos.add(idx)
        if abs(valor) > 0.005:
            despesas.append((label, valor))

    categorias = [
        ('Despesas com Pessoal', lambda l: ng(l) == 'pessoal'),
        ('Luz do Condomínio', lambda l: ng(l) == 'luz'),
        ('Água do Condomínio', lambda l: ng(l) == 'agua'),
        ('Telefone do Condomínio', lambda l: ng(l) == 'telefone'),
        ('Gás do Condomínio', lambda l: ng(l) == 'gas'),
        ('Tarifas Públicas', lambda l: ng(l) == 'tarifas_publicas'),
        ('Material de Limpeza', lambda l: ng(l) == 'limpeza'),
        ('Gastos com conservação', lambda l: ng(l) == 'conservacao'),
        ('Tarifas Bancárias', lambda l: ng(l) == 'bancarias'),
        ('Seguro de Incêndio Obrigatório', lambda l: ng(l) == 'seguro'),
    ]
    for label, predicado in categorias:
        somar(label, predicado)

    contratos = {}
    for idx, linha in ativas:
        if idx in consumidos or ng(linha) != 'contratos':
            continue
        label = _rotulo_contrato(linha, [l for _, l in ativas])
        partes = _dividir_contrato_por_servico(linha, lancamentos) or [
            (label, float(linha.get('final') or 0))]
        for titulo, valor in partes:
            key = _norm(titulo)
            anterior = contratos.get(key, (titulo, 0))
            contratos[key] = (anterior[0], anterior[1] + valor)
        consumidos.add(idx)
    despesas.extend(sorted(contratos.values(), key=lambda item: _ordem_rotulo_contrato(item[0])))
    somar('Pró-labore do Síndico', lambda l: ng(l) == 'prolabore')

    categorias_finais = [
        ('Despesas Administrativas', lambda l: ng(l) == 'administrativas'),
        ('Despesas Cartoriais e Honorários', lambda l: ng(l) == 'cartoriais'),
        ('Despesas com Obras/Benfeitorias', lambda l: ng(l) == 'obras'),
    ]
    for label, predicado in categorias_finais:
        somar(label, predicado)

    despesas.extend((l['classe'], float(l['final'])) for _, l in ativas if l.get('manual'))

    # Contas sem correspondência ficam juntas, com detalhe na revisão,
    # em vez de despejar cada classe bruta no fim do resumo público.
    # "Outras despesas" nunca aparece como linha no relatório: o resíduo sem
    # categoria é somado em Gastos com conservação, para a tabela continuar
    # fechando com o total previsto.
    outras = sum(float(linha.get('final') or 0)
                 for idx, linha in ativas if idx not in consumidos)
    if abs(outras) > 0.005:
        for pos, (label, valor) in enumerate(despesas):
            if _norm(label) == _norm('Gastos com conservação'):
                despesas[pos] = (label, valor + outras)
                break
        else:
            despesas.append(('Gastos com conservação', outras))

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

def _grupos_despesas_relatorio(despesas):
    """Gráfico com a mesma consolidação da tabela."""
    return _agrupar_por_grupo([
        {'grupo': label, 'final': mensal * 12} for label, mensal in despesas
    ])


# ---------------------------------------------------------------------------
# Grafico de barras horizontais (SVG) — composição das despesas
# Estilo editorial: barras cinza-escuro com contorno, rótulo à esquerda (até 2
# linhas), percentual na ponta, grade vertical a cada 5% (forte a cada 10%).
# A geometria (`_layout_barras`) é a mesma usada no PNG do DOCX.
# ---------------------------------------------------------------------------
BARRA_COR = '#4a4a4a'
BARRA_CONTORNO = '#14110c'
GRADE_FORTE = '#c9c8c3'
GRADE_FRACA = '#e6e5e0'


def _pct_br(frac):
    return f'{frac * 100:.1f}%'.replace('.', ',')


def _quebrar_rotulo(texto, largura=24, max_linhas=2):
    linhas = textwrap.wrap(str(texto), largura) or ['']
    if len(linhas) > max_linhas:
        resto = ' '.join(linhas[max_linhas - 1:])
        linhas = linhas[:max_linhas - 1] + [textwrap.shorten(resto, largura, placeholder='…')]
    return linhas


def _layout_barras(barras, largura=680):
    """Coordenadas do gráfico (unidades do SVG; o PNG multiplica por escala)."""
    maior = max((b['frac'] for b in barras), default=0) * 100
    eixo_max = max(10, math.ceil(maior / 10 - 1e-9) * 10)
    passo = 10 if eixo_max <= 50 else 20
    x0, x1 = 230, largura - 70
    topo, altura_barra, passo_linha = 6, 32, 46
    def x(frac):
        return x0 + (x1 - x0) * min(max(frac, 0) * 100, eixo_max) / eixo_max
    linhas = []
    for i, b in enumerate(barras):
        y = topo + i * passo_linha
        linhas.append({'y': y, 'meio': y + altura_barra / 2, 'x_fim': x(b['frac']),
                       'rotulo': _quebrar_rotulo(b['label']), 'pct': _pct_br(b['frac'])})
    base = topo + len(barras) * passo_linha - (passo_linha - altura_barra) / 2
    grade = []
    sub = passo / 2
    v = 0.0
    while v <= eixo_max + 1e-9:
        grade.append({'x': x(v / 100), 'forte': abs(v / passo - round(v / passo)) < 1e-9,
                      'rotulo': f'{v:.0f}%'})
        v += sub
    return {'linhas': linhas, 'grade': grade, 'x0': x0, 'altura_barra': altura_barra,
            'base': base, 'altura': base + 26, 'largura': largura}


def _grafico_barras_svg(grupos, total):
    if not grupos or total <= 0:
        return None
    dados = grupos
    if len(dados) > BARRAS_LIMITE + 1:
        principais = dados[:BARRAS_LIMITE]
        outros = sum(g['value'] for g in dados[BARRAS_LIMITE:])
        dados = principais + [{'label': 'Outros', 'value': outros}]
    barras = [{'label': g['label'], 'value': g['value'], 'frac': g['value'] / total} for g in dados]

    lay = _layout_barras(barras)
    partes = []
    for g in lay['grade']:
        cor = GRADE_FORTE if g['forte'] else GRADE_FRACA
        partes.append(f'<line x1="{g["x"]:.1f}" y1="0" x2="{g["x"]:.1f}" y2="{lay["base"]:.1f}" '
                      f'stroke="{cor}" stroke-width="1"/>')
        if g['forte']:
            partes.append(f'<text x="{g["x"]:.1f}" y="{lay["base"] + 18:.1f}" text-anchor="middle" '
                          f'font-size="12" fill="#14110c">{g["rotulo"]}</text>')
    for l in lay['linhas']:
        largura = max(l['x_fim'] - lay['x0'], 0)
        partes.append(f'<rect x="{lay["x0"]}" y="{l["y"]}" width="{largura:.1f}" height="{lay["altura_barra"]}" '
                      f'fill="{BARRA_COR}" stroke="{BARRA_CONTORNO}" stroke-width="1.2"/>')
        partes.append(f'<text x="{l["x_fim"] + 8:.1f}" y="{l["meio"]:.1f}" dominant-baseline="central" '
                      f'font-size="13" fill="#14110c">{l["pct"]}</text>')
        n = len(l['rotulo'])
        spans = ''.join(
            f'<tspan x="{lay["x0"] - 10}" y="{l["meio"] + (j - (n - 1) / 2) * 15:.1f}">{escape(t)}</tspan>'
            for j, t in enumerate(l['rotulo']))
        partes.append(f'<text text-anchor="end" dominant-baseline="central" font-size="12.5" '
                      f'fill="#14110c">{spans}</text>')
    svg = (f'<svg viewBox="0 0 {lay["largura"]} {lay["altura"]:.0f}" width="100%" '
           f'xmlns="http://www.w3.org/2000/svg">{"".join(partes)}</svg>')
    return {'svg': svg, 'barras': barras}


# ---------------------------------------------------------------------------
# Considerações Importantes — composição completa das categorias resumidas
# ---------------------------------------------------------------------------
def _adicionar_sem_repetir(destino, valor):
    valor = ' '.join(str(valor or '').split()).strip()
    if valor and _norm(valor) not in {_norm(item) for item in destino}:
        destino.append(valor)


def _eh_material_limpeza(linha):
    classe = _norm(linha.get('classe'))
    return 'limpeza' in classe and any(
        termo in classe for termo in ('material', 'produto', 'mat.')
    )


def _nome_na_composicao(classe):
    """Nome da classe como aparece no texto de Gastos com conservação
    (feedback José Henrique 09/2026). None = não citar."""
    nc = _norm(classe)
    if nc in ('outros materiais', 'outras despesas'):
        return None  # genéricos, não dizem nada ao síndico; o "etc." do texto os cobre
    if 'extintor' in nc:
        return 'Recarga de Extintores'
    if 'manut' in nc and re.search(r'\bgas\b', nc):
        # "Manutenção do Sistema de Gás" (Alma) e "Manutenção de Gás" (Condo21)
        # são a mesma despesa (José Henrique, 28/10/2026).
        return 'Manutenção de Gás'
    return classe


def _componentes_conservacao(linhas, resumo):
    """Classes que formam exatamente a categoria Gastos com conservação."""
    componentes = []
    for linha in linhas or []:
        if abs(float(linha.get('final') or 0)) <= 0.005 or _eh_material_limpeza(linha):
            continue
        if _categoria_despesa(linha) == 'conservacao':
            _adicionar_sem_repetir(componentes, _nome_na_composicao(linha.get('classe')))

    return componentes


def _componentes_administrativas(linhas):
    """Composição apresentada ao condomínio, sem citar a 13ª taxa de administração.

    A omissão é apenas textual: a consolidação financeira preserva essa classe.
    """
    componentes = []
    for linha in linhas or []:
        if abs(float(linha.get('final') or 0)) <= 0.005:
            continue
        classe = _norm(linha.get('classe'))
        if (re.search(r'(?:taxa|tx\.?)\s+(?:de\s+)?administrac', classe)
                and re.search(r'\b13(?:[º°ªoa])?(?!\d)|decim[oa] terceir[oa]', classe)):
            continue  # Omitir a menção, preservando os valores consolidados.
        if _categoria_despesa(linha) == 'administrativas':
            _adicionar_sem_repetir(componentes, linha.get('classe'))
    return componentes


def _texto_consideracao(texto):
    """Padroniza nomes de contas (Alma vem em CAIXA ALTA) com inicial maiúscula
    em cada frase e "R$" maiúsculo (feedback José Henrique 10/2026)."""
    texto = texto.lower()
    texto = re.sub(r'(^|[.!?]\s+)([a-zà-ÿ])', lambda m: m.group(1) + m.group(2).upper(), texto)
    texto = re.sub(r'\br\$', 'R$', texto)
    return texto.replace('Atenção/importante', 'ATENÇÃO/IMPORTANTE')


def _lista_portugues(itens):
    if len(itens) <= 1:
        return ''.join(itens)
    return ', '.join(itens[:-1]) + ' e ' + itens[-1]


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------
def montar_contexto_relatorio(estado, logo_path=None, com_fundo_override=None):
    """Contexto único do relatório, compartilhado pelos formatos PDF e DOCX."""
    resumo = estado.get('resumo') or {}
    linhas = estado.get('linhas_contas') or []
    cenarios = resumo.get('cenarios') or {}
    com_fundo = cenarios.get('com_fundo') or {}
    sem_fundo = cenarios.get('sem_fundo') or {}
    fundo_reserva_anual = cenarios.get('fundo_reserva_anual') or 0
    total_previsto = resumo.get('total_previsto') or 0
    impacto_inad_mensal = resumo.get('impacto_receita_mensal') or 0
    inflacao = float(resumo.get('inflacao') or 0)

    com_fundo_pref = com_fundo_override if com_fundo_override is not None else estado.get('com_fundo', True)
    if not com_fundo_pref:
        # "Colocar fundo de reserva no relatório? Não": o fundo some da tabela
        # de receitas, das opções de custeio e das considerações.
        fundo_reserva_anual = 0

    previsao_final = estado.get('previsao_final') or []
    receitas, _ = _extrair_receitas_despesas(previsao_final)
    if cenarios or estado.get('itens_manuais') or 'alma' in (estado.get('sistemas') or []):
        receitas = []
    receitas = [
        ('Taxas de Condomínio', valor)
        if _norm(label) == 'receita media do periodo' else (label, valor)
        for label, valor in receitas
    ]
    ordinarias = cenarios.get('receitas_ordinarias') or []
    if not receitas and cenarios:
        # Usa a composição filtrada pelo motor, também em sessões antigas;
        # o Fundo de Reserva aparece separado, nunca somado às Taxas.
        receitas = [(i['classe'], float(i['mensal'])) for i in ordinarias]
        if abs(fundo_reserva_anual) > 0.005:
            receitas.insert(1, ('Fundo de Reserva', fundo_reserva_anual / 12))
    if not receitas and not cenarios:
        receitas = [('Taxas de Condomínio', resumo.get('receita_mensal') or 0)]
    # Receitas não ordinárias (aluguel de espaço) aparecem na tabela, mas só
    # entram nas opções de cálculo — nunca na receita ordinária.
    nao_ordinarias = cenarios.get('receitas_nao_ordinarias') or []
    receitas += [(i['classe'], float(i['mensal'])) for i in nao_ordinarias
                 if _norm(i['classe']) not in {_norm(l) for l, _ in receitas}]
    if not com_fundo_pref:
        receitas = [(l, v) for l, v in receitas
                    if not ('fundo' in _norm(l) and 'reserva' in _norm(l))]
    # A inadimplência considerada sai da Taxa de Condomínio (e de toda receita
    # usada nos cenários/reajuste) — feedback José Henrique 09/2026: o texto
    # dizia "subtraímos" mas a tabela mostrava a receita cheia.
    impacto_inad_mensal = float(impacto_inad_mensal or 0)
    if impacto_inad_mensal > 0.005:
        pos_taxa = next((i for i, (l, _) in enumerate(receitas)
                         if _norm(l) == _norm('Taxas de Condomínio')), 0)
        label_taxa, valor_taxa = receitas[pos_taxa]
        receitas[pos_taxa] = (label_taxa, valor_taxa - impacto_inad_mensal)
    receitas = _normalizar_receitas_pdf(receitas)
    despesas = _consolidar_despesas_relatorio(
        linhas, resumo, estado.get('lancamentos_contas'))

    grupos = _grupos_despesas_relatorio(despesas)
    total_grupo = sum(g['value'] for g in grupos)

    receita_anual_com = (com_fundo.get('receita_anual') or 0) - impacto_inad_mensal * 12
    receita_anual_sem = (sem_fundo.get('receita_anual') or 0) - impacto_inad_mensal * 12
    resultado_com = receita_anual_com - total_previsto
    resultado_sem = receita_anual_sem - total_previsto
    opcoes = _opcoes_receita(receita_anual_sem, fundo_reserva_anual, nao_ordinarias, total_previsto)

    grafico = _grafico_barras_svg(grupos, total_grupo)

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
            f'{n_meses_balanco} meses - período disponível nos relatórios enviados.'
        )

    unidades_inad = len(set(i.get('unidade') for i in (estado.get('inadimplencia') or [])
                             if i.get('decisao') == 'abater'))
    if estado.get('inadimplencia_apurada') is False:
        consideracoes.append(
            'A inadimplência não foi apurada com os documentos disponíveis. Esta previsão não inclui '
            'abatimento da receita por débitos; isso não comprova ausência de inadimplência.'
        )
    # Avisos de importação (mês não fechado, receita fixa, diferenças entre
    # balancete e pagamentos) são conferência interna: ficam na tela de análise
    # e nunca entram no documento do condomínio (José Henrique, 22/10/2026).
    if unidades_inad > 0:
        plural = 'da' if unidades_inad == 1 else 'das'
        consideracoes.append(
            f'Consideramos para esta previsão a inadimplência de {unidades_inad} unidade(s), ou seja, '
            f'subtraímos {plural} receita mensal os valores das taxas condominiais dessa(s) unidade(s).'
        )

    conservacao_itens = _componentes_conservacao(linhas, resumo)
    if conservacao_itens:
        consideracoes.append(
            'O item "Gastos com conservação" é composto pelas seguintes despesas de manutenção: '
            + ', '.join(conservacao_itens) + ', etc.'
        )
    administrativas_itens = _componentes_administrativas(linhas)
    if administrativas_itens:
        consideracoes.append(
            'O item "Despesas Administrativas" é composto pelas seguintes despesas: '
            + _lista_portugues(administrativas_itens) + '.'
        )

    # Sem fundo de reserva no relatório a frase "sem utilizar o Fundo de
    # Reserva" não faz sentido e sai (José Henrique, 29/10/2026).
    idx_suficiencia = None
    if fundo_reserva_anual > 0.005:
        idx_suficiencia = len(consideracoes)
        consideracoes.append(_consideracao_suficiencia_receita(resultado_sem))

    ultimo_reajuste_raw = resumo.get('ultimo_reajuste')
    if ultimo_reajuste_raw:
        ano_r, mes_r = ultimo_reajuste_raw.split('-')
        mes_nome = MESES_PT[int(mes_r) - 1].upper()
        tempo_passado = _tempo_desde_reajuste(ano_r, mes_r)
        consideracoes.append(
            f'O último reajuste do valor da Taxa de Condomínio ocorreu em {mes_nome}/{ano_r}, '
            f'ou seja, há {tempo_passado} sem aumento.'
        )

    idx_opcoes = len(consideracoes)
    consideracoes.append(_consideracao_opcoes(opcoes))
    if fundo_reserva_anual > 0.005:
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
    consideracoes = [f'{i + 1}) {_texto_consideracao(texto)}' for i, texto in enumerate(consideracoes)]

    subtotal_mensal = sum(v for _, v in despesas)
    aumento_mensal = subtotal_mensal * inflacao if inflacao > 0 else 0
    total_despesas_mensal = subtotal_mensal + aumento_mensal

    # Quadro de leitura: mostra so o cenario selecionado pelo usuario.
    # Se COM FUNDO e tem FR, mostra os dois lados (informativo).
    resultado_quadro = resultado_com if com_fundo_pref else resultado_sem
    status_quadro = core._status_resultado(resultado_quadro)

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
        'opcoes': [{
            'label': o['label'],
            'receita_mensal': _money(o['receita_anual'] / 12),
            'despesa_mensal': _money(total_previsto / 12),
            'resultado_mensal': _money(o['resultado'] / 12),
            'reajuste': (f"{_pct(o['reajuste'])}%" if o['reajuste'] > 0 else 'Não é necessário'),
            'status': o['status'],
        } for o in opcoes],
        'fundo_reserva_anual': _money(fundo_reserva_anual),
        'tem_fundo_reserva': abs(fundo_reserva_anual) > 0.005,
        'grafico': grafico,
        'status_geral': status_quadro,
        'status_label': {
            'superavit': 'Cenário com superávit',
            'superavit_insuficiente': 'Superávit insuficiente — atenção',
            'deficit': 'Atenção: orçamento em déficit',
        }[status_quadro],
        # Sem a frase do resultado mensal (José Henrique, 28/10/2026).
        'conclusao_texto': (
            f'A previsão usa a média dos últimos {n_meses_balanco} meses, separa eventos pontuais da '
            'rotina. '
            + ('A inadimplência não foi apurada. Confirme a cobertura dos meses e a vigência '
               'da receita antes de adotar os valores desta previsão.'
               if estado.get('inadimplencia_apurada') is False else
               'A inadimplência é tratada como redução de receita disponível.')
        ),
        'consideracoes': consideracoes,
        # Valores numéricos para o XLSX, que refaz as somas com fórmulas.
        'valores': {
            'receitas': receitas,
            'despesas': despesas,
            'inflacao': inflacao,
            'aluguel': {_norm(i['classe']) for i in nao_ordinarias},
            'opcoes': [{'label': o['label'], 'usa_fundo': o['usa_fundo']} for o in opcoes],
            'com_fundo_pref': com_fundo_pref,
            'n_meses_balanco': n_meses_balanco,
            # Considerações que dependem dos números; o XLSX as refaz em fórmula.
            'idx_suficiencia': idx_suficiencia,
            'idx_opcoes': idx_opcoes,
        },
    }
    return ctx


def gerar_relatorio_pdf(estado, logo_path=None, com_fundo_override=None):
    ctx = montar_contexto_relatorio(estado, logo_path, com_fundo_override)
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
  .secao { margin-bottom: 14px; page-break-inside: avoid; }
  /* Considerações longas podem continuar na página seguinte, mas nunca partem um item. */
  .secao.consideracoes { page-break-inside: auto; }
  .secao.consideracoes p { page-break-inside: avoid; }
  h2 { page-break-after: avoid; }
  .secao h2 { font-size: 14px; color: #1c355e; border-bottom: 1px solid #e1e0d9; padding-bottom: 4px; margin-bottom: 8px; }
  table { width: 100%; border-collapse: collapse; font-size: 10.5px; }
  th, td { padding: 4px 6px; text-align: left; border-bottom: 1px solid #e1e0d9; }
  th { color: #52514e; font-weight: 700; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  tr.total td { font-weight: 700; border-top: 2px solid #14110c; border-bottom: none; }
  tr.subtotal td { font-weight: 700; border-top: 1px solid #898781; border-bottom: none; color: #52514e; }
  .quadros { display: flex; flex-wrap: wrap; gap: 14px; }
  .quadro { flex: 1 1 40%; border: 1px solid #e1e0d9; border-radius: 6px; padding: 10px 12px; }
  .quadro h3 { font-size: 12px; margin-bottom: 6px; color: #1c355e; }
  .quadro .linha { display: flex; justify-content: space-between; padding: 3px 0; border-bottom: 1px dashed #e1e0d9; }
  .quadro .linha:last-child { border-bottom: none; font-weight: 700; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; margin-top: 6px; }
  .badge.deficit { background: #fbe3e3; color: #a12626; }
  .badge.superavit_insuficiente { background: #fff3cd; color: #8a6300; }
  .badge.superavit { background: #dff3e3; color: #0f6b2b; }
  .grafico-barras svg { display: block; width: 100%; height: auto; }
  .conclusao-box { border-left: 3px solid #1c355e; padding-left: 10px; }
  .conclusao-box.superavit_insuficiente { border-left-color: #c98500; }
  .conclusao-box.deficit { border-left-color: #a12626; }
  .consideracoes { font-size: 10px; color: #303030; }
  .consideracoes p { margin: 0 0 6px; }
  .fecho { page-break-inside: avoid; }
  .assinatura { margin-top: 18px; text-align: center; font-size: 10.5px; }
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
      <thead><tr><th>Conta</th><th class="num">Valor mensal previsto</th></tr></thead>
      <tbody>
        {% for label, valor in receitas %}<tr><td>{{ label }}</td><td class="num">{{ valor }}</td></tr>{% endfor %}
        <tr class="total"><td>Total mensal</td><td class="num">{{ total_receitas }}</td></tr>
      </tbody>
    </table>
  </div>

  <div class="secao">
    <h2>Despesas</h2>
    <table>
      <thead><tr><th>Conta</th><th class="num">Valor mensal previsto</th></tr></thead>
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
      {% for o in opcoes %}
      <div class="quadro">
        <h3>{{ o.label }}</h3>
        <div class="linha"><span>Receita mensal</span><span>{{ o.receita_mensal }}</span></div>
        <div class="linha"><span>Despesa mensal</span><span>{{ o.despesa_mensal }}</span></div>
        <div class="linha"><span>Resultado mensal</span><span>{{ o.resultado_mensal }}</span></div>
        <div class="linha"><span>Reajuste necessário</span><span>{{ o.reajuste }}</span></div>
        <span class="badge {{ o.status }}">
          {{ {'superavit': 'Superávit', 'superavit_insuficiente': 'Superávit insuficiente', 'deficit': 'Déficit'}[o.status] }}
        </span>
      </div>
      {% endfor %}
    </div>
  </div>

  {% if grafico %}
  <div class="secao">
    <h2>Composição das despesas</h2>
    <div class="grafico-barras">{{ grafico.svg|safe }}</div>
  </div>
  {% endif %}

  <!-- Conclusão logo depois do gráfico, sem página nova (usuária, 26/10/2026: "sem espaçamentos muito
       longos"); as Considerações vêm em seguida e podem quebrar entre itens. -->
  <div class="secao">
    <h2>Conclusão</h2>
    <div class="conclusao-box {{ status_geral }}">
      <strong>{{ status_label }}</strong>
      <p>{{ conclusao_texto }}</p>
    </div>
  </div>

  <div class="secao consideracoes">
    <h2 style="text-align:center;">CONSIDERAÇÕES IMPORTANTES</h2>
    {% for c in consideracoes[:-1] %}<p>{{ c }}</p>{% endfor %}
    <!-- Assinatura presa ao último item: nunca sozinha numa página. -->
    <div class="fecho">
      {% if consideracoes %}<p>{{ consideracoes[-1] }}</p>{% endif %}
      <div class="assinatura">
        <p>Cabo Frio, {{ data_extenso }}</p>
        <p><strong>PORTO REAL IMÓVEIS</strong></p>
      </div>
    </div>
  </div>

</body>
</html>
"""
