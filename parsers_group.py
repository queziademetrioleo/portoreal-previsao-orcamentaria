"""Importação determinística dos XLS e XLSX exportados pela Group.

Cabeçalhos identificam colunas; códigos ligam contas entre relatórios.
Valores cobrados excluídos permanecem na auditoria, nunca na projeção.
"""
import datetime as dt
import re
import unicodedata
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

import openpyxl
import xlrd

FILES = {'balanual': 'group_bal.xlsx', 'desbai': 'group_des.xlsx',
         'rec': 'group_rec.xlsx'}
MONTHS = {name: i for i, name in enumerate(
    ('jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'), 1)}


def norm(value):
    text = unicodedata.normalize('NFD', str(value or '').strip().lower())
    return ' '.join(''.join(c for c in text if unicodedata.category(c) != 'Mn').split())


def money(value):
    if value is None or str(value).strip() in ('', '-', '–'):
        return Decimal(0)
    text = str(value).strip().replace('R$', '').strip()
    if ',' in text:
        text = text.replace('.', '').replace(',', '.')
    try:
        result = Decimal(text)
        if not result.is_finite():
            raise InvalidOperation
        return result.quantize(Decimal('0.01'))
    except InvalidOperation as exc:
        raise ValueError(f'Group: valor monetário inválido: {value!r}.') from exc


def account(value):
    match = re.fullmatch(r'\s*(\d+(?:\.\d+)+)\s*-\s*(.+?)\s*', str(value or ''))
    return (match[1], match[2].lstrip('.').strip()) if match else (None, None)


def date(value):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.datetime.strptime(str(value).strip(), '%d/%m/%Y').date()
    except ValueError as exc:
        raise ValueError(f'Group: data inválida: {value!r}.') from exc


def month(value):
    if isinstance(value, (dt.date, dt.datetime)):
        return value.strftime('%m/%Y')
    text = norm(value)
    numeric = re.fullmatch(r'(\d{2})/(\d{4})', text)
    named = re.fullmatch(r'([a-z]{3})\.?/(\d{4})', text)
    if numeric:
        m, year = int(numeric[1]), int(numeric[2])
    elif named and named[1] in MONTHS:
        m, year = MONTHS[named[1]], int(named[2])
    else:
        return None
    try:
        return dt.date(year, m, 1).strftime('%m/%Y')
    except ValueError:
        return None


def read(path):
    try:
        with open(path, 'rb') as source:
            signature = source.read(8)
        if signature == bytes.fromhex('d0cf11e0a1b11ae1'):
            wb = xlrd.open_workbook(path)
            sheet = wb.sheet_by_index(0)
            rows = [tuple(xlrd.xldate_as_datetime(cell.value, wb.datemode)
                          if cell.ctype == xlrd.XL_CELL_DATE else cell.value
                          for cell in sheet.row(index)) for index in range(sheet.nrows)]
        else:
            with open(path, 'rb') as source:
                wb = openpyxl.load_workbook(source, read_only=True, data_only=True)
                try:
                    rows = [tuple(row) for row in wb.worksheets[0].iter_rows(values_only=True)]
                finally:
                    wb.close()
    except Exception as exc:
        raise ValueError(f'Group: não foi possível ler {Path(path).name} como XLS ou XLSX.') from exc
    names = [str(row[0]).strip() for row in rows if row and
             norm(row[0]).startswith(('cond.', 'condominio '))]
    if not names:
        raise ValueError(f'Group: condomínio não identificado em {Path(path).name}.')
    return rows, names[0]


def header(rows, required):
    for i, row in enumerate(rows):
        cols = {norm(v): c for c, v in enumerate(row) if v is not None}
        if all(label in cols for label in required):
            return i, cols
    raise ValueError('Group: cabeçalho não encontrado: ' + ', '.join(required) + '.')


def parse_balance(path):
    rows, name = read(path)
    start, cols = header(rows, ('classe de conta', 'total'))
    month_cols = [(i, month(v)) for i, v in enumerate(rows[start]) if month(v)]
    labels = [label for _, label in month_cols]
    if len(labels) != 12 or len(set(labels)) != 12:
        raise ValueError('Group: o balancete anual deve conter 12 meses distintos.')
    indices = [int(label[3:]) * 12 + int(label[:2]) for label in labels]
    if any(b - a != 1 for a, b in zip(indices, indices[1:])):
        raise ValueError('Group: os meses do balancete devem ser consecutivos e estar em ordem.')
    sections = {'receitas': [], 'despesas': []}
    totals = {}
    section = group = group_code = None
    seen = set()
    warnings = []
    for row_no, row in enumerate(rows[start + 1:], start + 2):
        label = row[cols['classe de conta']]
        normalized = norm(label)
        if normalized in sections:
            section, group, group_code = normalized, None, None
            continue
        if normalized in ('total de receitas', 'total de despesas'):
            kind = normalized.removeprefix('total de ')
            totals[kind] = money(row[cols['total']])
            section = None
            continue
        if not section:
            continue
        code, title = account(label)
        if not code:
            continue
        if code.count('.') == 1:
            group_code, group = code, title
            continue
        if not group_code or not code.startswith(group_code + '.'):
            raise ValueError(f'Group: conta {code} sem grupo correspondente na linha {row_no}.')
        if code in seen:
            raise ValueError(f'Group: conta {code} repetida no balancete.')
        seen.add(code)
        values = [money(row[c]) for c, _ in month_cols]
        total = money(row[cols['total']])
        if abs(sum(values) - total) > Decimal('0.01'):
            raise ValueError(f'Group: soma mensal da conta {code} difere do total informado.')
        sections[section].append({'grupo': group, 'classe': title, 'codigo': code,
                                  'codigo_grupo': group_code, 'monthly': list(map(float, values)),
                                  'total': float(total), 'media': float(total / 12),
                                  'n_meses': sum(v != 0 for v in values), 'linha_origem': row_no})
    for kind, accounts in sections.items():
        if not accounts or kind not in totals:
            raise ValueError(f'Group: seção de {kind} incompleta no balancete.')
        if abs(sum(money(r['total']) for r in accounts) - totals[kind]) > Decimal('0.01'):
            raise ValueError(f'Group: soma das classes de {kind} difere do total do balancete.')
    if any('mes nao fechado' in norm(v) for r in rows for v in r if v):
        warnings.append('Group: o balancete contém pelo menos um mês não fechado; confira a cobertura antes de gerar a previsão.')
    empty = [label for i, label in enumerate(labels) if not any(
        abs(r['monthly'][i]) > 0.005 for section_rows in sections.values() for r in section_rows)]
    if empty:
        warnings.append('Group: meses sem movimentação: ' + ', '.join(empty) +
                        '. O relatório não comprova se são meses completos ou ausência de dados.')
    previous = [r for r in rows if norm(r[0]) == 'saldo anterior']
    final = [r for r in rows if norm(r[0]) == 'saldo total']
    return {**sections, 'total_receitas': float(totals['receitas']),
            'total_despesas': float(totals['despesas']), 'meses': labels, 'n_meses': 12,
            'saldo_inicial': float(money(previous[0][month_cols[0][0]])) if previous else None,
            'saldo_final': float(money(final[-1][month_cols[-1][0]])) if final else None,
            'nome_condominio': name, 'avisos': warnings}


def parse_expenses(path):
    rows, name = read(path)
    start, cols = header(rows, ('classe de conta', 'fornecedor', 'competencia',
                               'vencimento', 'pagamento', 'valor lancado (r$)', 'valor pago (r$)', 'descricao'))
    items, class_totals, group_totals = [], defaultdict(Decimal), defaultdict(Decimal)
    group = group_code = None
    total = None
    for row_no, row in enumerate(rows[start + 1:], start + 2):
        label = row[cols['classe de conta']]
        if norm(label) == 'total de despesas':
            total = money(row[cols['valor pago (r$)']])
            break
        code, title = account(label)
        if not code:
            continue
        if code.count('.') == 1:
            group_code, group = code, title
            continue
        if not group_code or not code.startswith(group_code + '.'):
            raise ValueError(f'Group: despesa {code} sem grupo correspondente na linha {row_no}.')
        paid = money(row[cols['valor pago (r$)']])
        payment = row[cols['pagamento']]
        if payment is None or str(payment).strip() in ('', '-'):
            if paid:
                raise ValueError(f'Group: despesa paga sem data de pagamento na linha {row_no}.')
            continue  # Conta não paga não integra o histórico de caixa.
        description = str(row[cols['descricao']] or '').strip()
        supplier = str(row[cols['fornecedor']] or '').strip().lstrip('.')
        item = {'grupo': group, 'classe': title, 'codigo': code, 'codigo_grupo': group_code,
                'fornecedor': supplier, 'data': date(payment),
                'competencia': month(row[cols['competencia']]),
                'vencimento': date(row[cols['vencimento']]),
                'documento': str(row[cols['numero do documento']] or '') if 'numero do documento' in cols else '',
                'tipo_pgto': '', 'valor_lcto': float(money(row[cols['valor lancado (r$)']])),
                'valor_pago': float(paid), 'descricao': description if description not in ('', '-') else supplier,
                'sistema': 'group', 'linha_origem': row_no}
        items.append(item)
        class_totals[(group, title)] += paid
        group_totals[group] += paid
    if total is None or not items:
        raise ValueError('Group: relatório de despesas sem lançamentos pagos ou total geral.')
    if abs(sum(money(i['valor_pago']) for i in items) - total) > Decimal('0.01'):
        raise ValueError('Group: soma dos pagamentos difere do total das despesas detalhadas.')
    return {'itens': items, 'classe_totais': {k: float(v) for k, v in class_totals.items()},
            'grupo_totais': {k: float(v) for k, v in group_totals.items()},
            'grand_total': float(total), 'nome_condominio': name,
            'periodo': (min(i['data'] for i in items), max(i['data'] for i in items))}


def parse_receipts(path, core):
    rows, name = read(path)
    start, cols = header(rows, ('unidade', 'nn', 'classe de conta', 'competencia',
                               'recebimento', 'valor (r$)', 'valor recebido (r$)'))
    items, excluded = [], []
    reported = None
    # As receitas de fornecedores e o resumo abaixo não são cobranças das unidades.
    for row_no, row in enumerate(rows[start + 1:], start + 2):
        if norm(row[cols['unidade']]).startswith('total de receitas das unidades'):
            reported = (money(row[cols['valor (r$)']]), money(row[cols['valor recebido (r$)']]))
            break
        code, title = account(row[cols['classe de conta']])
        if not code:
            continue
        competence = month(row[cols['competencia']])
        if not competence:
            raise ValueError(f'Group: competência inválida na receita da linha {row_no}.')
        item = {'unidade': str(row[cols['unidade']]).strip(), 'codigo': code,
                'classe': title, 'mes_ref': competence,
                'identificador': str(row[cols['nn']] or '').strip(),
                'lancado': float(money(row[cols['valor (r$)']])),
                'liquidado': float(money(row[cols['valor recebido (r$)']])), 'linha_origem': row_no}
        (excluded if 'exclu' in norm(item['identificador']) else items).append(item)
    if not items:
        raise ValueError('Group: receitas sem cobranças válidas por unidade.')
    if reported is None:
        raise ValueError('Group: subtotal das receitas das unidades não encontrado.')
    for field, expected in zip(('lancado', 'liquidado'), reported):
        if abs(sum(money(i[field]) for i in items + excluded) - expected) > Decimal('0.01'):
            raise ValueError(f'Group: soma das receitas das unidades ({field}) difere do subtotal informado.')
    reference = max((i['mes_ref'] for i in items), key=lambda s: (s[3:], s[:2]))
    current = [i for i in items if i['mes_ref'] == reference]
    seen = set()
    classes = defaultdict(lambda: {'lancado': Decimal(0), 'liquidado': Decimal(0)})
    for item in current:
        # NN identifica o boleto, com uma linha por classe. Não deduplicar por valor.
        if item['identificador'] not in ('', '-'):
            key = (item['unidade'], item['identificador'], item['codigo'], reference)
            if key in seen:
                raise ValueError(f'Group: cobrança repetida da unidade {item["unidade"]}, conta {item["codigo"]}.')
            seen.add(key)
        for field in ('lancado', 'liquidado'):
            classes[item['classe']][field] += money(item[field])
    taxes = sum(v['lancado'] for k, v in classes.items() if
                'condominio' in norm(k) or norm(k).startswith('tx'))
    fund = sum(v['lancado'] for k, v in classes.items() if core._eh_fundo_reserva(k))
    if taxes <= 0:
        raise ValueError('Group: taxa condominial vigente não identificada nas receitas por unidade.')
    return {'nome_condominio': name, 'mes_ref': reference,
            'por_classe': {k: {f: float(v) for f, v in values.items()} for k, values in classes.items()},
            'total_lancado_mes': float(sum(v['lancado'] for k, v in classes.items() if core._rec_classe_entra(k))),
            'total_liquidado_mes': float(sum(v['liquidado'] for k, v in classes.items() if core._rec_classe_entra(k))),
            'tx_condominio_mensal': float(taxes), 'fundo_reserva_mensal': float(fund),
            'tx_condominio_anual': float(taxes * 12), 'fundo_reserva_anual': float(fund * 12),
            'fixo_anual': float((taxes + fund) * 12), 'itens': items, 'excluidas': excluded}


def load_group(folder, core):
    folder = Path(folder)
    bal = parse_balance(folder / FILES['balanual'])
    des = parse_expenses(folder / FILES['desbai'])
    rec = parse_receipts(folder / FILES['rec'], core)
    if len({norm(report['nome_condominio']) for report in (bal, des, rec)}) != 1:
        raise ValueError('Group: os três relatórios devem pertencer ao mesmo condomínio.')
    warnings = list(bal['avisos'])
    warnings.append('Group: relatório de inadimplência não fornecido. O abatimento por inadimplência não foi calculado; isso não comprova ausência de débitos.')
    if rec['excluidas']:
        warnings.append(f'Group: {len(rec["excluidas"])} linhas de cobranças excluídas das unidades foram retiradas da base da receita.')
    if rec['mes_ref'] != bal['meses'][-1]:
        warnings.append(f'Group: receita fixa baseada em {rec["mes_ref"]}; o balancete termina em {bal["meses"][-1]}. Confirme se a cobrança ainda é vigente.')
    labels = bal['meses']
    detail = defaultdict(Decimal)
    for item in des['itens']:
        label = item['data'].strftime('%m/%Y')
        if label not in labels:
            raise ValueError(f'Group: pagamento em {label} fora do período do balancete.')
        detail[(item['codigo'], label)] += money(item['valor_pago'])
    codes = {r['codigo'] for r in bal['despesas']}
    for item in des['itens']:
        if item['codigo'] not in codes:
            item['classificacao_pendente'] = True
    differences = []
    for row in bal['despesas']:
        for label, value in zip(labels, row['monthly']):
            delta = detail.pop((row['codigo'], label), Decimal(0)) - money(value)
            if abs(delta) > Decimal('0.01'):
                differences.append(f'{row["codigo"]} ({label}): diferença R$ {delta:.2f}')
    differences.extend(f'{code} ({label}): pagamento R$ {value:.2f} sem conta no balancete'
                       for (code, label), value in detail.items() if abs(value) > Decimal('0.01'))
    if differences:
        warnings.append('Group: diferenças entre balancete e pagamentos por conta/mês: ' + '; '.join(differences))
    return {'bal': bal, 'des': des, 'rec': rec, 'sin': {'grand_total': None}, 'inad': None,
            'divergencias': warnings, 'cobertura': {label: 'group' for label in labels}}
