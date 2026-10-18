"""Leitores determinísticos e consolidação do fluxo Condo21 + Almah."""
import calendar
import datetime as dt
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import openpyxl
import pdfplumber

MONEY = re.compile(r'(?<![\w/])(-?\d[\d.]*,\d{2})(?!\d)')
MONTH = re.compile(r'\b(\d{2}/\d{4})\b')
FIN_ACCOUNT_ALIASES = {
    'manutencao do sistema de gas (aquisicao de gas glp)': 'manutencao do sistema de gas',
}


def norm(value):
    text = unicodedata.normalize('NFD', str(value or '').strip().lower())
    return ' '.join(''.join(c for c in text if unicodedata.category(c) != 'Mn').split())


def number(value):
    if isinstance(value, (float, int)):
        return float(value)
    return float(str(value or '0').replace('.', '').replace(',', '.').strip())


def month_key(label):
    return dt.datetime.strptime(label, '%m/%Y').strftime('%Y-%m')


def month_label(key):
    return dt.datetime.strptime(key, '%Y-%m').strftime('%m/%Y')


def months_between(start, end):
    first = dt.datetime.strptime(start, '%Y-%m').date()
    last = dt.datetime.strptime(end, '%Y-%m').date()
    if first > last:
        raise ValueError('O início do período deve ser anterior ao fim.')
    result = []
    while first <= last:
        result.append(first.strftime('%Y-%m'))
        first = dt.date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    return result


def _merge_wrapped_balance_lines(lines):
    result = []
    previous = None
    for line in lines:
        text = line['text'].strip()
        matches = list(MONEY.finditer(result[-1])) if result else []
        if (previous and matches and not MONEY.search(text)
                and abs(line['x0'] - previous['x0']) <= 2
                and 0 < line['top'] - previous['top'] <= 12
                and result[-1][:matches[0].start()].strip()):
            offset = matches[0].start()
            result[-1] = result[-1][:offset].rstrip() + ' ' + text + ' ' + result[-1][offset:]
        else:
            result.append(text)
        previous = line
    return result


def pdf_lines(path, join_wrapped=False):
    with pdfplumber.open(path) as pdf:
        lines = []
        for page_no, page in enumerate(pdf.pages, 1):
            page = page.dedupe_chars()
            text_lines = (_merge_wrapped_balance_lines(page.extract_text_lines()) if join_wrapped
                          else (page.extract_text() or '').splitlines())
            lines.extend((page_no, line.strip()) for line in text_lines)
    if not lines:
        raise ValueError('PDF sem texto legível. Envie o relatório exportado pelo Almah.')
    return lines


def group_name(name):
    aliases = {
        'despesas com pessoal': 'Despesas com Pessoal',
        'tarifas publicas': 'Tarifas Públicas',
        'contratos': 'Contratos',
        'despesas diversas': 'Despesas Diversas',
        'despesas administrativas': 'Despesas Administrativas',
        'despesas cartoriais e honorarios': 'Despesas Cartoriais e Honorários',
        'receitas operacionais': 'Receitas Operacionais',
        'manutencoes (mao de obra / servicos)': 'Conservação',
        'materiais de manutencao': 'Conservação',
        'conservacao e limpeza': 'Conservação',
        'seguros': 'Despesas Diversas',
        'despesas com obras / benfeitorias': 'Despesas com Obras/Benfeitorias',
        'tarifas bancarias': 'Tarifas Bancárias.',
    }
    return aliases.get(norm(name), name)


def read_arrears(path):
    """Inadimplente = deve os DOIS meses anteriores ao mês do relatório.

    Ex.: relatório de outubro → deve setembro E agosto. Débito antigo com os
    meses recentes pagos indica acordo e não entra (José Henrique, 10/2026).
    Abate o boleto inteiro da unidade (taxa, fundo de reserva e água): são as
    taxas que ela deixa de pagar (José Henrique, 10/2026). Assim não depende
    do REC do sistema anterior para a taxa individual.
    """
    lines = pdf_lines(path)
    text = '\n'.join(line for _, line in lines)
    match = re.search(r'Boletos em\s+(\d{2}/\d{2}/\d{4})', text)
    if not match:
        raise ValueError('Inadimplência Almah: data-base não identificada.')
    base = dt.datetime.strptime(match[1], '%d/%m/%Y').date()
    end_day = base.replace(day=1) - dt.timedelta(days=1)
    end = end_day.strftime('%Y-%m')
    prev = (end_day.replace(day=1) - dt.timedelta(days=1)).strftime('%Y-%m')
    window = {prev, end}
    owed = defaultdict(set)
    latest = {}
    historical_count = 0
    for page, line in lines:
        # COMPTO. pode ser texto (ex.: REF. MÊS); vencimento determina o mês nesse caso.
        row = re.match(r'(.+?)\s+(BC|BL)\s+(.+?)\s+(\d{2}/\d{2}/\d{4})\s+(.+)', line)
        if not row:
            continue
        historical_count += 1
        due = dt.datetime.strptime(row[4], '%d/%m/%Y').date()
        competence = MONTH.search(row[3])
        month = month_key(competence[1]) if competence else due.strftime('%Y-%m')
        values = MONEY.findall(row[5])
        if len(values) < 2:
            raise ValueError(f'Inadimplência Almah: valores ilegíveis na página {page}.')
        original, paid = number(values[0]), number(values[1])
        if month not in window or due > base or original - paid <= 0.005:
            continue
        unit = row[1].strip()
        owed[unit].add(month)
        item = {'unidade': unit, 'classe': 'Boleto (taxa, fundo e água)', 'mes_ref': month_label(month),
                'vencimento': due, 'valor': original, 'valor_original_titulo': original,
                'proj_rec': original, 'meses_atraso': 1 if month == end else 2,
                'critica': True, 'regra_inad': 'misto_ultimos_2_meses_alma',
                'sistema': 'alma', 'arquivo': Path(path).name, 'pagina': page}
        if unit not in latest or month_key(latest[unit]['mes_ref']) < month:
            latest[unit] = item
    if not historical_count and '0 registro' not in norm(text) and '0 unidade' not in norm(text):
        raise ValueError('Inadimplência Almah: nenhum título reconhecido; confira o formato do PDF.')
    items = [item for unit, item in latest.items() if owed[unit] == window]
    total = round(sum(i['valor'] for i in items), 2)
    return {'total': total, 'critica': total, 'recente': 0.0, 'data_base': base,
            'itens': items, 'unidades_criticas': len(items),
            'unidades_criticas_detalhe': {i['unidade']: {'impacto': i['valor'],
                'tx_mensal_media': i['valor'], 'meses_consecutivos': i['meses_atraso']} for i in items},
            'impacto_mensal_receita': total, 'meses_considerados': [month_label(prev), month_label(end)],
            'regra': 'misto_ultimos_2_meses_alma'}


def read_plan(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = list(wb.active.values)
    finally:
        wb.close()
    header = {norm(v): i for i, v in enumerate(rows[0])}
    if not {'classificacao', 'descricao'} <= header.keys():
        raise ValueError('Plano de contas deve conter Classificação e Descrição.')
    accounts, groups = defaultdict(list), {}
    for row in rows[1:]:
        code = str(row[header['classificacao']] or '').strip()
        name = str(row[header['descricao']] or '').strip()
        if not code or not name:
            continue
        if code.count('.') < 4:
            groups[code] = name
        else:
            parent = groups.get(code.rsplit('.', 1)[0])
            if parent:
                accounts[norm(name)].append({'codigo': code, 'grupo': group_name(parent)})
    return accounts


def read_internal_plan():
    """Contexto de classificação versionado com a aplicação, sem upload por sessão."""
    path = Path(__file__).resolve().parent / 'data' / 'plano_contas_alma.json'
    return json.loads(path.read_text(encoding='utf-8'))['contas']


def read_balance(path):
    lines = pdf_lines(path, join_wrapped=True)
    text = '\n'.join(line for _, line in lines)
    period = re.search(r'Período\s*(\d{2}/\d{4})\s*até\s*(\d{2}/\d{4})', text, re.I)
    if not period:
        raise ValueError('Demonstrativo Almah: período não identificado.')
    keys = months_between(month_key(period[1]), month_key(period[2]))
    count = len(keys)
    result = {'receitas': [], 'despesas': [], 'meses': [month_label(m) for m in keys],
              'n_meses': count, 'saldo_inicial': None, 'saldo_final': None}
    section, group = None, None
    totals = {}
    for page, line in lines:
        n = norm(line)
        if '(+) receitas' in n:
            section, group = 'receitas', None
            continue
        if '(-) despesas' in n:
            section, group = 'despesas', None
            continue
        if '(=) saldo' in n:
            section = None
        if not section or any(s in n for s in ('emitido em', 'empreendimentos', 'rua jorge',
                                               'centro -', 'total media', 'periodo')):
            continue
        if MONTH.search(line) or re.search(r'\d{2}\.\d{3}\.\d{3}/\d{4}', line):
            continue
        matches = list(MONEY.finditer(line))
        if not matches:
            if n and not n.startswith(('por periodo', 'condominio')):
                group = group_name(line)
            continue
        label = line[:matches[0].start()].strip()
        values = [number(m[1]) for m in matches]
        if not label:  # subtotal
            continue
        if norm(label) == 'total geral':
            if len(values) != count + 2:
                raise ValueError('Demonstrativo Almah: colunas do total incompatíveis com o período.')
            totals[section] = values[count]
            continue
        if len(values) != count + 2 or not group:
            raise ValueError(f'Demonstrativo Almah: linha não reconhecida na página {page}: {label}')
        monthly = values[:count]
        if abs(sum(monthly) - values[count]) > 0.02:
            raise ValueError(f'Demonstrativo Almah: total da conta {label} não confere.')
        result[section].append({'grupo': group, 'classe': label, 'monthly': monthly,
                                'total': values[count], 'media': values[count] / count,
                                'n_meses': sum(abs(v) > 0.005 for v in monthly),
                                'sistema': 'alma', 'arquivo': Path(path).name, 'pagina': page})
    for kind in ('receitas', 'despesas'):
        computed = round(sum(r['total'] for r in result[kind]), 2)
        if kind not in totals or abs(computed - totals[kind]) > 0.02:
            raise ValueError(f'Demonstrativo Almah: total de {kind} não confere com as contas lidas.')
        result['total_' + kind] = computed
    return result


def read_fin(path, plan, pdf_accounts):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = list(wb.active.values)
    finally:
        wb.close()
    header = {norm(v): i for i, v in enumerate(rows[0])}
    needed = {'despesa', 'valor pago', 'data pagto', 'fornecedor', 'status'}
    if not needed <= header.keys():
        raise ValueError('FIN Almah: faltam colunas Despesa, Valor Pago, Data Pagto, Fornecedor ou Status.')
    items, report_total = [], None
    for index, row in enumerate(rows[1:], 2):
        def get(name):
            return row[header[name]] if name in header else None
        account = str(get('despesa') or '').strip()
        if norm(account) == 'total':
            report_total = number(get('valor pago'))
            continue
        if not account:
            continue
        date = get('data pagto')
        if not date:
            if norm(get('status')).startswith('pago'):
                raise ValueError(f'FIN Almah: pagamento sem Data Pagto na linha {index}.')
            continue
        if not norm(get('status')).startswith('pago'):
            continue
        if isinstance(date, dt.datetime):
            date = date.date()
        elif not isinstance(date, dt.date):
            date = dt.datetime.strptime(str(date).strip(), '%d/%m/%Y').date()
        candidates = plan.get(norm(account), [])
        account_key = FIN_ACCOUNT_ALIASES.get(norm(account), norm(account))
        group = pdf_accounts.get(account_key) or (candidates[0]['grupo'] if len(candidates) == 1 else None)
        group = group or 'Classes a revisar'
        supplier = str(get('fornecedor') or '').strip()
        items.append({'grupo': group, 'classe': account, 'data': date,
                      'fornecedor': supplier, 'descricao': str(get('descricao') or supplier),
                      'tipo_pgto': str(get('forma pgto.') or ''),
                      'valor_lcto': number(get('valor')), 'valor_pago': number(get('valor pago')),
                      'documento': str(get('doc') or ''), 'parcela': str(get('parcela') or ''),
                      'status': str(get('status') or ''), 'sistema': 'alma',
                      'arquivo': Path(path).name, 'linha': index,
                      'classificacao_pendente': group == 'Classes a revisar'})
    total = round(sum(i['valor_pago'] for i in items), 2)
    if report_total is not None and abs(total - report_total) > 0.02:
        raise ValueError('FIN Almah: total pago não confere com os pagamentos lidos.')
    if not items:
        raise ValueError('FIN Almah não contém pagamentos com Data Pagto.')
    return items


def read_receivables(path):
    lines = pdf_lines(path)
    text = '\n'.join(line for _, line in lines)
    period = re.search(r'Data Vencimento\s+(\d{2}/\d{2}/\d{4})\s+até\s+(\d{2}/\d{2}/\d{4})', text)
    if not period or period[1][3:] != period[2][3:]:
        raise ValueError('Contas a receber Almah: selecione um único mês de vencimento.')
    accounts, in_table = {}, False
    declared_total = None
    for _, line in lines:
        if 'CONTA DE RECEITA' in line:
            in_table = True
            continue
        if not in_table or line.startswith('Emitido em'):
            continue
        matches = list(MONEY.finditer(line))
        if len(matches) != 3:
            continue
        label = line[:matches[0].start()].strip()
        if not label:
            declared_total = number(matches[0][1])
            continue
        accounts[label] = {'lancado': number(matches[0][1]), 'liquidado': number(matches[1][1])}
    total = round(sum(v['lancado'] for v in accounts.values()), 2)
    if not accounts or declared_total is None or abs(total - declared_total) > 0.02:
        raise ValueError('Contas a receber Almah: total não confere com as contas lidas.')
    tax = sum(v['lancado'] for k, v in accounts.items() if 'condominio' in norm(k))
    reserve = sum(v['lancado'] for k, v in accounts.items() if 'fundo' in norm(k) and 'reserva' in norm(k))
    return {'mes_ref': period[1][3:], 'nome_condominio': None, 'por_classe': accounts,
            'total_lancado_mes': total, 'total_liquidado_mes': sum(v['liquidado'] for v in accounts.values()),
            'tx_condominio_mensal': round(tax, 2), 'fundo_reserva_mensal': round(reserve, 2),
            'tx_condominio_anual': round(tax * 12, 2), 'fundo_reserva_anual': round(reserve * 12, 2),
            'fixo_anual': round((tax + reserve) * 12, 2), 'sistema': 'alma'}


def consolidate_balances(condo, alma, start=None, end=None):
    condo_keys = [month_key(m) for m in condo['meses']]
    alma_keys = [month_key(m) for m in alma['meses']]
    # O balanual da migração lista meses futuros zerados: não são cobertura.
    condo_covered = {key for idx, key in enumerate(condo_keys)
                     if any(abs(r['monthly'][idx]) > 0.005
                            for kind in ('receitas', 'despesas') for r in condo[kind])}
    all_keys = sorted(condo_covered | set(alma_keys))
    keys = months_between(start or all_keys[0], end or all_keys[-1])
    overlap = set(keys) & condo_covered & set(alma_keys)
    if overlap:
        raise ValueError('Há meses com movimentação nos dois sistemas: ' + ', '.join(map(month_label, sorted(overlap))) + '. Envie exportações sem sobreposição.')
    missing = set(keys) - set(all_keys)
    if missing:
        raise ValueError('Faltam dados para os meses: ' + ', '.join(map(month_label, sorted(missing))))
    aliases = {'taxa de condominio': 'tx. condominio', 'fundo de reserva': 'fundo reserva',
               'consultoria, medicina e seg. do trabalho': 'consult., medicina e seg. do trabalho',
               'manutencao jardim': 'manutencao de jardim', 'manutencao portao / porta': 'manutencao portao'}
    def canonical(name):
        return aliases.get(norm(name), norm(name))
    original_names = {canonical(r['classe']): r['classe'] for kind in ('receitas', 'despesas') for r in condo[kind]}
    result = {'meses': [month_label(m) for m in keys], 'n_meses': len(keys),
              'saldo_inicial': None, 'saldo_final': None}
    for kind in ('receitas', 'despesas'):
        merged = {}
        for source, source_keys in ((condo, condo_keys), (alma, alma_keys)):
            for row in source[kind]:
                cls = canonical(row['classe'])
                group = group_name(row['grupo'] or 'Classes a revisar')
                identity = (norm(group), cls)
                target = merged.setdefault(identity, {'grupo': group,
                    'classe': original_names.get(cls, row['classe']), 'monthly': [0.0] * len(keys)})
                for index, key in enumerate(source_keys):
                    if key in keys:
                        target['monthly'][keys.index(key)] += row['monthly'][index]
        result[kind] = []
        for row in merged.values():
            row['monthly'] = [round(v, 2) for v in row['monthly']]
            row['total'] = round(sum(row['monthly']), 2)
            row['media'] = row['total'] / len(keys)
            row['n_meses'] = sum(abs(v) > 0.005 for v in row['monthly'])
            if row['n_meses']:
                result[kind].append(row)
        result['total_' + kind] = round(sum(r['total'] for r in result[kind]), 2)
    return result, keys, {key: 'alma' if key in alma_keys else 'condo21' for key in keys}


def balance_from_payments(items):
    """Demonstrativo de despesas (conta × mês) somado dos pagamentos detalhados.

    Com o Alma no conjunto, o sistema anterior só contribui com despesas; receita
    e inadimplência atuais vêm do Alma. O balanual/balancete repetia os mesmos
    valores (conferido centavo a centavo no Santorini e no Berlin, 10/2026).
    """
    if not items:
        raise ValueError('Despesas detalhadas do sistema anterior sem pagamentos no período.')
    keys = months_between(*(f(i['data'].strftime('%Y-%m') for i in items) for f in (min, max)))
    rows = {}
    for item in items:
        row = rows.setdefault((item['grupo'], item['classe']), {
            'grupo': item['grupo'], 'classe': item['classe'], 'monthly': [0.0] * len(keys)})
        row['monthly'][keys.index(item['data'].strftime('%Y-%m'))] += float(item['valor_pago'])
    despesas = []
    for row in rows.values():
        row['monthly'] = [round(v, 2) for v in row['monthly']]
        row['total'] = round(sum(row['monthly']), 2)
        row['media'] = row['total'] / len(keys)
        row['n_meses'] = sum(abs(v) > 0.005 for v in row['monthly'])
        despesas.append(row)
    return {'meses': [month_label(k) for k in keys], 'n_meses': len(keys), 'receitas': [],
            'despesas': despesas, 'total_receitas': 0.0,
            'total_despesas': round(sum(r['total'] for r in despesas), 2),
            'saldo_inicial': None, 'saldo_final': None}


def load_mixed(folder, core):
    root = Path(folder)
    config = json.loads((root / 'importacao.json').read_text()) if (root / 'importacao.json').exists() else {}
    condo_items = core.parse_desbai(str(root / 'desbai06.xls'))['itens']
    condo = balance_from_payments(condo_items)
    alma = read_balance(root / 'alma_bal.pdf')
    bal, keys, coverage = consolidate_balances(condo, alma, config.get('periodo_inicio'), config.get('periodo_fim'))
    plan = read_internal_plan()
    pdf_accounts = {norm(r['classe']): r['grupo'] for r in alma['despesas']}
    alma_items = read_fin(root / 'alma_fin.xlsx', plan, pdf_accounts)
    # Nomes canônicos usados no balanço também precisam ser usados nos detalhes.
    aliases = {'manutencao jardim': 'manutencao de jardim',
               'manutencao portao / porta': 'manutencao portao',
               'consultoria, medicina e seg. do trabalho': 'consult., medicina e seg. do trabalho',
               'manutencao do sistema de gas (aquisicao de gas glp)': 'manutencao do sistema de gas'}
    names = {norm(r['classe']): r['classe'] for r in bal['despesas']}
    items = []
    for source, source_items in (('condo21', condo_items), ('alma', alma_items)):
        for item in source_items:
            key = item['data'].strftime('%Y-%m')
            if key not in keys:
                continue
            item['sistema'] = source
            item.setdefault('arquivo', 'desbai06.xls')
            item['grupo'] = group_name(item['grupo'] or 'Classes a revisar')
            item['classe'] = names.get(aliases.get(norm(item['classe']), norm(item['classe'])), item['classe'])
            items.append(item)
    warnings = []
    known = {(norm(r['grupo']), norm(r['classe'])): r for r in bal['despesas']}
    for item in items:
        identity = (norm(item['grupo']), norm(item['classe']))
        if identity not in known:
            item['classificacao_pendente'] = True
            target = {'grupo': item['grupo'], 'classe': item['classe'], 'monthly': [0.0] * len(keys),
                      'total': 0.0, 'media': 0.0, 'n_meses': 0, 'somente_detalhe': True}
            known[identity] = target
            bal['despesas'].append(target)
            warnings.append(f"{item['classe']}: pagamento sem conta correspondente no demonstrativo; incluído para revisão.")
        target = known[identity]
        if target.get('somente_detalhe'):
            item['classificacao_pendente'] = True
            target['monthly'][keys.index(item['data'].strftime('%Y-%m'))] += item['valor_pago']
            target['total'] = round(sum(target['monthly']), 2)
            target['media'] = target['total'] / len(keys)
            target['n_meses'] = sum(abs(v) > 0.005 for v in target['monthly'])
    bal['total_despesas_demonstrativos'] = bal['total_despesas']
    bal['total_despesas'] = round(sum(r['total'] for r in bal['despesas']), 2)
    class_totals, group_totals = defaultdict(float), defaultdict(float)
    for item in items:
        class_totals[(item['grupo'], item['classe'])] += item['valor_pago']
        group_totals[item['grupo']] += item['valor_pago']
    first, last = dt.datetime.strptime(keys[0], '%Y-%m').date(), dt.datetime.strptime(keys[-1], '%Y-%m').date()
    last = last.replace(day=calendar.monthrange(last.year, last.month)[1])
    des = {'itens': items, 'classe_totais': dict(class_totals), 'grupo_totais': dict(group_totals),
           'grand_total': round(sum(i['valor_pago'] for i in items), 2), 'periodo': (first, last)}
    for row in bal['despesas']:
        detail = class_totals.get((row['grupo'], row['classe']), 0)
        delta = round(row['total'] - detail, 2)
        if abs(delta) > 0.02:
            warnings.append(f"{row['classe']}: demonstrativo R$ {row['total']:.2f}, pagamentos detalhados R$ {detail:.2f}, diferença R$ {delta:.2f}.")
    # Na combinação com Alma, a cobrança vigente é sempre a desse PDF.
    rec = dict(read_receivables(root / 'alma_rec.pdf'), sistema='alma')
    if (root / 'alma_inad.pdf').exists():
        ina = read_arrears(root / 'alma_inad.pdf')
    else:
        # Ausência declarada no upload misto: não recuperar inad01 do Condo21.
        ina = None
    return {'bal': bal, 'des': des, 'sin': {'grand_total': None}, 'inad': ina,
            'rec': rec, 'divergencias': warnings, 'cobertura': coverage,
            'origem_sistema': 'misto', 'config': config}
