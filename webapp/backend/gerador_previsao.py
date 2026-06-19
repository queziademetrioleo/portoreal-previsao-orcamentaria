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


# Similaridade minima (Jaccard de tokens) para aceitar um match aproximado.
# Substring por comprimento e cego: ou e frouxo (o generico "contrato" vira
# substring de "Contrato de Manutencao do Jardim" -> contas fantasma) ou e
# estrito demais (descarta "Manut. Extintores e/ou Teste" x "Manut. Extintores").
# Jaccard de tokens distingue os dois casos.
_SIM_MIN_MATCH = 0.5

# Conectores ignorados na tokenizacao (nao carregam significado de conta).
_STOPWORDS = {'de', 'do', 'da', 'dos', 'das', 'e', 'ou', 'com', 'para', 'p',
              'no', 'na', 'a', 'o', 'as', 'os', 'em', 'ao', 'eou'}

# Palavras-CATEGORIA genericas: aparecem em muitas linhas e NAO distinguem a
# conta (ex.: "Contrato de Manutencao do Jardim" x "... da E.T.A." compartilham
# {contrato, manutencao}). O match exige pelo menos um token ESPECIFICO em comum
# (jardim/eta/elevador/...), nunca so as categoricas — senao o generico
# "Contrato de Manutencao" cairia em "...do Jardim" (a 1a linha que aparece).
_GENERICAS = {'contrato', 'manutencao', 'manut', 'despesas', 'taxa', 'geral'}


def _tokens(nome):
    brutos = re.split(r'[^a-z0-9]+', nome)
    return {t for t in brutos if len(t) >= 3 and t not in _STOPWORDS}


def _achar_valor(nn, valores, usados):
    """Encontra o melhor valor para a conta normalizada 'nn'.

    1) match exato; 2) similaridade de tokens (Jaccard) >= _SIM_MIN_MATCH E pelo
    menos um token ESPECIFICO (nao-categorico) em comum. Cada chave de 'valores'
    so e consumida uma vez (registrada em 'usados'). Retorna (chave, valor) ou
    (None, None).
    """
    if nn in valores and nn not in usados:
        return nn, valores[nn]
    tn = _tokens(nn)
    espec_n = tn - _GENERICAS
    if not tn or not espec_n:
        return None, None
    melhor_chave = None
    melhor_sim = 0.0
    for vn, vv in valores.items():
        if vn in usados:
            continue
        tv = _tokens(vn)
        if not tv:
            continue
        # Exige token especifico em comum (alem de eventuais categoricas).
        if not (espec_n & (tv - _GENERICAS)):
            continue
        sim = len(tn & tv) / len(tn | tv)
        if sim > melhor_sim:
            melhor_sim = sim
            melhor_chave = vn
    if melhor_chave is not None and melhor_sim >= _SIM_MIN_MATCH:
        return melhor_chave, valores[melhor_chave]
    return None, None


def _receita_mensal(ln):
    """Valor mensal de uma receita = media dos meses ATIVOS (total / n_meses).

    Receitas pontuais (1 mes) nao sao recorrentes e nao entram na previsao
    mensal — retorna None para que a conta seja ignorada.
    """
    nm = ln.get('n_meses') or 0
    if nm <= 1:
        return None
    return round(ln['total'] / nm, 2)


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

    # Mapas separados: por CLASSE e por GRUPO. Manter separados evita que uma
    # chave de grupo (ex.: "despesas diversas") seja substring de uma linha de
    # classe (ex.: "Estorno de Despesas Diversas") e contamine o valor dela.
    valores_classe = {}
    valores_grupo = {}
    classes_por_grupo = {}   # grupo_norm -> {classe_norm: final}
    for l in linhas:
        valores_classe[_norm(l['classe'])] = l['final']
        ng = _norm(l['grupo'] or '')
        valores_grupo[ng] = valores_grupo.get(ng, 0) + l['final']
        classes_por_grupo.setdefault(ng, {})[_norm(l['classe'])] = l['final']
    # Para a PREVISAO (que mistura linhas de classe e de grupo) usamos o
    # combinado, com a classe tendo prioridade.
    valores = {**valores_grupo, **valores_classe}

    def _classes_do_grupo(grupo_tmpl):
        """Classes parseadas dos grupos que casam com o grupo do template.
        Restringir ao mesmo grupo evita que uma conta homonima de outro grupo
        (ex.: '13o Taxa de Administracao' existe em Diversas E Administrativas)
        seja roteada para a linha errada."""
        gt = _tokens(grupo_tmpl)
        if not gt:
            return valores_classe
        out = {}
        for g, classes in classes_por_grupo.items():
            tg = _tokens(g)
            if tg and len(gt & tg) / len(gt | tg) >= 0.5:
                out.update(classes)
        # Sem fallback para "todas as classes": se nenhum grupo parseado casa com
        # o grupo do template, as linhas ficam vazias (evita contaminacao entre
        # grupos). Os nomes de grupo do Condominio21 sao padronizados e casam.
        return out

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

        # Limpar dados RESIDUAIS (lixo de preenchimentos anteriores) que o template
        # carrega: ajustes manuais em E:H (ex.: "Outros Materiais" E=1000) e valores
        # literais em D/I de linhas de classe que ficaram de um condominio anterior
        # (ex.: "Contrato" D=5234.52). Sem isso, linhas nao preenchidas nesta
        # geracao mantem numeros antigos e inflam o subtotal. Preserva FORMULAS do
        # template (VLOOKUP, =SUM, =D-SUM(E:H), =+D205).
        for r in range(11, ws_c.max_row + 1):
            for col in (5, 6, 7, 8):
                if isinstance(ws_c.cell(r, col).value, (int, float)):
                    ws_c.cell(r, col).value = None
            code_b = str(ws_c.cell(r, 2).value or '').strip()
            if re.match(r'^\d{2}\.\d{2}$', code_b):  # linha de classe
                for col in (4, 9):
                    if isinstance(ws_c.cell(r, col).value, (int, float)):
                        ws_c.cell(r, col).value = None

        # Receitas — procura cada conta de receita e atualiza D
        for ln in bal.get('receitas', []):
            val = _receita_mensal(ln)
            if val is None:
                continue
            nc = _norm(ln['classe'])
            for r in range(1, ws_c.max_row + 1):
                nn = _norm(ws_c.cell(r, 3).value)
                if nn == nc:
                    ws_c.cell(r, 4).value = val
                    ws_c.cell(r, 9).value = val
                    break

        # Despesas — percorre linhas do template e atualiza com valores calculados.
        # 'usados' garante que cada valor parseado preencha no maximo uma linha.
        # 'grupo_atual' guarda o ultimo cabecalho de grupo (XX) para restringir o
        # match as classes do mesmo grupo.
        usados_c = set()
        grupo_atual = ''
        for r in range(1, ws_c.max_row + 1):
            code_a = str(ws_c.cell(r, 1).value or '').strip()  # col A
            code_b = str(ws_c.cell(r, 2).value or '').strip()  # col B
            nome = str(ws_c.cell(r, 3).value or '').strip()
            if not nome:
                continue
            # Cabecalho de grupo (codigo XX). O template e inconsistente: grupos
            # 02-10 trazem o codigo na col A, mas 14-17 (Admin, Montagem, Fundo
            # Reserva, Pro-labore) trazem na col B. Aceitar ambas, senao o
            # 'grupo_atual' trava e contas desses grupos nao sao preenchidas.
            grp = code_a if re.match(r'^\d{2}$', code_a) else (
                  code_b if re.match(r'^\d{2}$', code_b) else None)
            if grp:
                if not grp.startswith('01'):
                    grupo_atual = _norm(nome)
                continue
            # So linhas de CLASSE de despesa (codigo XX.YY na col B). Cabecalhos de
            # grupo mantem suas formulas =SUM(...). 01.xx sao receitas.
            if not re.match(r'^\d{2}\.\d{2}$', code_b) or code_b.startswith('01'):
                continue
            nn = _norm(nome)
            candidatos = _classes_do_grupo(grupo_atual)
            chave, val = _achar_valor(nn, candidatos, usados_c)
            if val is not None and abs(val) > 0.005:
                ws_c.cell(r, 4).value = round(val, 2)
                ws_c.cell(r, 9).value = round(val, 2)
                usados_c.add(chave)

        # Provisoes R4 (Laudo de Autovistoria) e R5 (Sistema de Incendio).
        # Sao gravadas como ajuste NEGATIVO na coluna E: como a coluna I do
        # template e =D-SUM(E:H), um E negativo soma a provisao ao valor final,
        # que entao flui para a PREVISAO via formula. Sem isso o "Subtotal Atual"
        # da CONTAS nao bate com a soma da PREVISAO.
        def _acha_linha(*termos):
            for rr in range(1, ws_c.max_row + 1):
                n = _norm(ws_c.cell(rr, 3).value)
                if n and all(t in n for t in termos):
                    return rr
            return None

        r_laudo = _acha_linha('laudo', 'autovistoria') or _acha_linha('autovistoria')
        if r_laudo and R.get('prov_laudo', 0) > 0.005:
            if not ws_c.cell(r_laudo, 4).value:
                ws_c.cell(r_laudo, 4).value = 0
            ws_c.cell(r_laudo, 5).value = -round(R['prov_laudo'], 2)

        r_inc = (_acha_linha('sistema', 'combate', 'incendio')
                 or _acha_linha('registro', 'convencao'))
        if r_inc and R.get('prov_incendio', 0) > 0.005:
            if not ws_c.cell(r_inc, 4).value:
                ws_c.cell(r_inc, 4).value = 0
            ws_c.cell(r_inc, 5).value = -round(R['prov_incendio'], 2)

    # ---------- PREVISAO ----------
    ws_p = None
    for nome in wb.sheetnames:
        # nome da aba vem espacado: ' P R E V I S Ã O ' -> remover espacos p/ casar
        if 'REVIS' in nome.upper().replace(' ', '') and '(2)' not in nome:
            ws_p = wb[nome]
            break

    if ws_p:
        # Atualizar cabecalho: titulo com o ano (preserva acentos) e nome do
        # condominio onde houver placeholder (BARRAMARES / COND. ...).
        for r in range(1, 10):
            v = ws_p.cell(r, 1).value
            if isinstance(v, str) and ('PREVIS' in v.upper() or 'ORCAMENT' in v.upper()):
                ws_p.cell(r, 1).value = f'PREVISÃO ORÇAMENTÁRIA PARA {ano}'
            elif isinstance(v, str) and ('BARRAMARES' in v.upper()
                                         or v.upper().startswith('COND')):
                ws_p.cell(r, 1).value = nome_condominio

        # Linha de Obras/Benfeitorias MANTIDAS na revisão (R1 reprovado). O
        # template não tem linha de Obras na PREVISÃO; usamos uma linha livre
        # (dentro do range do SUBTOTAL) referenciando o grupo Obras da CONTAS.
        # Fica 0 quando nada é mantido.
        if ' C O N T A S ' in wb.sheetnames:
            ws_c2 = wb[' C O N T A S ']
            r_obras = None
            for rr in range(1, ws_c2.max_row + 1):
                nrc = _norm(ws_c2.cell(rr, 3).value)
                code_a = str(ws_c2.cell(rr, 1).value or '').strip()
                if 'obras' in nrc and re.match(r'^\d{2}$', code_a):
                    r_obras = rr
                    break
            if r_obras:
                # achar primeira linha de despesa livre (C vazio) antes do SUBTOTAL
                for rr in range(22, 48):
                    nome_l = _norm(ws_p.cell(rr, 3).value)
                    if not nome_l:
                        ws_p.cell(rr, 3).value = 'Despesas com Obras/Benfeitorias'
                        ws_p.cell(rr, 4).value = f"=' C O N T A S '!$I${r_obras}"
                        break

        # IMPORTANTE: nesta planilha a PREVISAO e inteiramente movida por
        # formulas que apontam para a CONTAS (ex.: D22 = CONTAS!I64,
        # contratos D33..D42 = CONTAS!I194..I203). Preencher a CONTAS
        # corretamente ja resolve a PREVISAO. So escrevemos um valor estatico
        # quando a celula NAO for formula (templates sem formula / do-zero),
        # nunca sobrescrevendo as formulas do modelo.
        def _set_se_nao_formula(r, c, valor):
            atual = ws_p.cell(r, c).value
            if isinstance(atual, str) and atual.startswith('='):
                return
            ws_p.cell(r, c).value = valor

        # Receitas
        for ln in bal.get('receitas', []):
            val = _receita_mensal(ln)
            if val is None:
                continue
            nc = _norm(ln['classe'])
            for r in range(1, ws_p.max_row + 1):
                nn = _norm(ws_p.cell(r, 3).value)
                if nn == nc:
                    _set_se_nao_formula(r, 4, val)
                    _set_se_nao_formula(r, 5, val)
                    break

        # Despesas — atualiza linhas existentes com valores calculados
        usados_p = set()
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

            chave, val = _achar_valor(nn, valores, usados_p)
            if val is not None and abs(val) > 0.005:
                _set_se_nao_formula(r, 4, round(val, 2))
                _set_se_nao_formula(r, 5, round(val / num_frac, 2))
                _set_se_nao_formula(r, 6, round(val / 12, 2))
                usados_p.add(chave)

        # SUBTOTAL, INFLACAO, TOTAL, SALDO (so para templates sem formula)
        subtotal_val = R.get('subtotal', 0)
        for r in range(1, ws_p.max_row + 1):
            n3 = _norm(ws_p.cell(r, 3).value)
            if 'subtotal' in n3:
                _set_se_nao_formula(r, 4, round(subtotal_val, 2))
                _set_se_nao_formula(r, 6, round(subtotal_val / 12, 2))
            elif 'infla' in n3 and 'previsao' in n3:
                _set_se_nao_formula(r, 4, round(subtotal_val * inflacao, 2))
            elif n3 == 'total':
                total = subtotal_val * (1 + inflacao)
                _set_se_nao_formula(r, 4, round(total, 2))
                _set_se_nao_formula(r, 5, round(total / num_frac, 2))
            elif 'saldo' in n3 or 'deficit' in n3 or 'superavit' in n3:
                rec_anual = sum(ln['total'] for ln in bal.get('receitas', []))
                total = subtotal_val * (1 + inflacao)
                _set_se_nao_formula(r, 4, round(rec_anual - total, 2))

    # ---------- PREVISAO (2) ----------
    for nome in wb.sheetnames:
        if 'REVIS' in nome.upper().replace(' ', '') and '(2)' in nome:
            ws_p2 = wb[nome]
            ws_p2['E11'] = num_frac
            # A6 do template = VLOOKUP(Cadastro!A4,...) que resolvia para o nome
            # do condominio do template (BARRAMARES XX). Sobrescreve com o nome
            # real desta previsao. A8 = titulo com o ano correto.
            cab = str(ws_p2['A6'].value or '')
            if cab.startswith('=') or 'BARRAMARES' in cab.upper() or cab.upper().startswith('COND'):
                ws_p2['A6'] = nome_condominio
            if isinstance(ws_p2['A8'].value, str) and 'PREVIS' in ws_p2['A8'].value.upper():
                ws_p2['A8'] = f'PREVISÃO ORÇAMENTÁRIA PARA {ano}'
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
        val = _receita_mensal(ln)
        if val is None:
            continue
        ws_c.cell(r, 2, f'01.{cod:02d}')
        ws_c.cell(r, 3, ln['classe'])
        ws_c.cell(r, 4, val).number_format = MONEY
        ws_c.cell(r, 9, val).number_format = MONEY
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
        val = _receita_mensal(ln)
        if val is None:
            continue
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
