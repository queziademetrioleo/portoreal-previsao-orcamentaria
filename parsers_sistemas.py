"""Consolidação das fontes selecionadas, com uma fonte por mês."""
import calendar
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

import parsers_alma as alma
import parsers_group as group

ALIASES = {'taxa de condominio': 'tx. condominio', 'fundo de reserva': 'fundo reserva',
           'manutencao jardim': 'manutencao de jardim',
           'manutencao portao / porta': 'manutencao portao',
           'consultoria, medicina e seg. do trabalho': 'consult., medicina e seg. do trabalho',
           'manutencao do sistema de gas (aquisicao de gas glp)': 'manutencao do sistema de gas'}


def canonical(value):
    return ALIASES.get(alma.norm(value), alma.norm(value))


def migration_start(sources, requested=None):
    if requested or not {'group', 'alma'} <= sources.keys():
        return requested
    balance = sources['alma']['bal']
    active = [alma.month_key(label) for index, label in enumerate(balance['meses']) if any(
        abs(row['monthly'][index]) > 0.005
        for kind in ('receitas', 'despesas') for row in balance[kind])]
    return min(active) if active else None


def consolidate(sources, start=None, end=None, alma_start=None):
    """Meses zerados de legados não são cobertura no uso de várias fontes."""
    coverage = {}
    indices = {}
    alma_start = migration_start(sources, alma_start)
    if alma_start:
        alma.months_between(alma_start, alma_start)
        if not {'group', 'alma'} <= sources.keys():
            raise ValueError('O mês de mudança para Alma exige Group e Alma selecionados.')
    for name, data in sources.items():
        bal = data['bal']
        keys = [alma.month_key(m) for m in bal['meses']]
        indices[name] = keys
        active = [key for index, key in enumerate(keys) if any(
            abs(row['monthly'][index]) > 0.005
            for kind in ('receitas', 'despesas') for row in bal[kind])]
        for index, key in enumerate(keys):
            if alma_start and ((name == 'group' and key >= alma_start) or (name == 'alma' and key < alma_start)):
                continue
            covered = len(sources) == 1 or (name == 'alma' and (
                key >= alma_start if alma_start else bool(active) and active[0] <= key <= active[-1])) or any(
                abs(row['monthly'][index]) > 0.005
                for kind in ('receitas', 'despesas') for row in bal[kind])
            if covered:
                coverage.setdefault(key, []).append(name)
    if not coverage:
        raise ValueError('Não há meses cobertos pelos relatórios selecionados.')
    all_keys = sorted(coverage)
    keys = alma.months_between(start or all_keys[0], end or all_keys[-1])
    missing = [alma.month_label(key) for key in keys if key not in coverage]
    if missing:
        raise ValueError('Faltam dados para os meses: ' + ', '.join(missing))
    overlap = [f'{alma.month_label(key)} ({", ".join(coverage[key])})'
               for key in keys if len(coverage[key]) > 1]
    if overlap:
        raise ValueError('Há meses com movimentação em mais de um sistema: ' +
                         ', '.join(overlap) + '. Informe o mês de mudança para Alma ou envie exportações sem sobreposição.')
    result = {'meses': [alma.month_label(key) for key in keys], 'n_meses': len(keys),
              'saldo_inicial': None, 'saldo_final': None}
    names = {}
    for data in sources.values():
        for kind in ('receitas', 'despesas'):
            for row in data['bal'][kind]:
                identity = (alma.norm(alma.group_name(row['grupo'] or 'Classes a revisar')), canonical(row['classe']))
                names.setdefault(identity, row['classe'])
    for kind in ('receitas', 'despesas'):
        merged = {}
        for name, data in sources.items():
            for row in data['bal'][kind]:
                grp = alma.group_name(row['grupo'] or 'Classes a revisar')
                identity = (alma.norm(grp), canonical(row['classe']))
                target = merged.setdefault(identity, {'grupo': grp, 'classe': names[identity],
                                                       'monthly': [0.0] * len(keys)})
                for index, key in enumerate(indices[name]):
                    if key in keys and coverage[key] == [name]:
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
    return result, keys, {key: coverage[key][0] for key in keys}


def load_selected(folder, core):
    root = Path(folder)
    config = json.loads((root / 'importacao.json').read_text())
    systems = config['sistemas']
    # Preservar exatamente o fluxo misto já validado contra o Santorini.
    if set(systems) == {'condo21', 'alma'}:
        data = alma.load_mixed(folder, core)
        data.update(sistemas=systems, inadimplencia_apurada=True)
        return data
    if systems == ['group']:
        data = group.load_group(folder, core)
        data.update(origem_sistema='group', sistemas=systems, inadimplencia_apurada=False)
        return data
    sources = {}
    if 'condo21' in systems:
        sources['condo21'] = {'bal': core.parse_balanual(str(root / 'balanual.xls')),
                              'des': core.parse_desbai(str(root / 'desbai06.xls')),
                              'rec': core.parse_rec(str(root / 'rec02.xls'))}
    if 'group' in systems:
        sources['group'] = group.load_group(folder, core)
    if 'alma' in systems:
        if not (root / 'alma_inad.pdf').exists() and not config.get('sem_inadimplencia_alma'):
            raise ValueError('Envie o relatório de inadimplência Alma ou declare sua ausência.')
        bal = alma.read_balance(root / 'alma_bal.pdf')
        payments = alma.read_fin(root / 'alma_fin.xlsx', alma.read_internal_plan(),
                                 {alma.norm(r['classe']): r['grupo'] for r in bal['despesas']})
        sources['alma'] = {'bal': bal, 'des': {'itens': payments},
                            'rec': alma.read_receivables(root / 'alma_rec.pdf')}
    if systems == ['condo21']:
        data = sources['condo21']
        data.update(sin=core.parse_dessin(str(root / 'dessin02.xls')) if (root / 'dessin02.xls').exists() else {'grand_total': None},
                    inad=core.parse_inad(str(root / 'inad01.xls')) if (root / 'inad01.xls').exists() else None,
                    origem_sistema='condo21', sistemas=systems, divergencias=[], cobertura={}, inadimplencia_apurada=True)
        return data
    alma_start = migration_start(sources, config.get('alma_inicio'))
    bal, keys, coverage = consolidate(sources, config.get('periodo_inicio'), config.get('periodo_fim'), alma_start)
    warnings = []
    if alma_start:
        method = 'informada' if config.get('alma_inicio') else 'detectada pelo primeiro mês com movimentação no Alma'
        warnings.append(f'Divisão {method}: Group antes de {alma.month_label(alma_start)} e Alma a partir desse mês.')
        for source in ('group', 'alma'):
            balance = sources[source]['bal']
            excluded = [i for i, label in enumerate(balance['meses'])
                        if (source == 'group' and alma.month_key(label) >= alma_start)
                        or (source == 'alma' and alma.month_key(label) < alma_start)]
            amounts = {kind: round(sum(row['monthly'][i] for row in balance[kind] for i in excluded), 2)
                       for kind in ('receitas', 'despesas')}
            if any(abs(value) > 0.005 for value in amounts.values()):
                warnings.append(f'{source.title()}: movimentos fora do período atribuído não entram na previsão: receitas R$ {amounts["receitas"]:.2f}; despesas R$ {amounts["despesas"]:.2f}. Confira a divisão entre os sistemas.')
    for data in sources.values():
        # Cobertura e receita precisam refletir a consolidação, não o Group isolado.
        warnings.extend(w for w in data.get('divergencias', []) if not any(
            token in w for token in ('inadimplência não fornecido', 'meses sem movimentação', 'receita fixa baseada')))
    if len(keys) < 12:
        warnings.append(f'Período disponível de {len(keys)} meses; confirme a cobertura para a previsão anual.')
    known = {(alma.norm(r['grupo']), canonical(r['classe'])): r for r in bal['despesas']}
    items = []
    for source, data in sources.items():
        for original in data['des']['itens']:
            item = dict(original)
            key = item['data'].strftime('%Y-%m')
            if key not in keys:
                continue
            if coverage[key] != source:
                if alma_start and ((source == 'group' and key >= alma_start) or (source == 'alma' and key < alma_start)):
                    continue
                if abs(item['valor_pago']) > 0.005:
                    raise ValueError(f'Pagamento {source} em {alma.month_label(key)} sem cobertura dessa fonte no balancete.')
                continue
            item['sistema'] = source
            item['grupo'] = alma.group_name(item['grupo'] or 'Classes a revisar')
            identity = (alma.norm(item['grupo']), canonical(item['classe']))
            if identity not in known:
                item['classificacao_pendente'] = True
                target = {'grupo': item['grupo'], 'classe': item['classe'], 'monthly': [0.0] * len(keys),
                          'total': 0, 'media': 0, 'n_meses': 0, 'somente_detalhe': True}
                known[identity] = target
                bal['despesas'].append(target)
                warnings.append(f'{item["classe"]}: pagamento sem conta no demonstrativo; incluído para revisão.')
            target = known[identity]
            item['classe'] = target['classe']
            if target.get('somente_detalhe'):
                item['classificacao_pendente'] = True
                target['monthly'][keys.index(key)] += item['valor_pago']
                target['total'] = round(sum(target['monthly']), 2)
                target['media'] = target['total'] / len(keys)
                target['n_meses'] = sum(abs(v) > 0.005 for v in target['monthly'])
            items.append(item)
    class_totals, group_totals = defaultdict(float), defaultdict(float)
    for item in items:
        class_totals[(item['grupo'], item['classe'])] += item['valor_pago']
        group_totals[item['grupo']] += item['valor_pago']
    bal['total_despesas_demonstrativos'] = bal['total_despesas']
    bal['total_despesas'] = round(sum(r['total'] for r in bal['despesas']), 2)
    for row in bal['despesas']:
        detail = class_totals.get((row['grupo'], row['classe']), 0)
        if abs(row['total'] - detail) > 0.02:
            warnings.append(f'{row["classe"]}: demonstrativo R$ {row["total"]:.2f}, pagamentos R$ {detail:.2f}; confira a diferença.')
    recs = [(name, data['rec']) for name, data in sources.items() if data.get('rec') and data['rec'].get('mes_ref')]
    if not recs:
        raise ValueError('Receita vigente não identificada nos sistemas selecionados.')
    if 'alma' in systems:
        rec_source, rec = 'alma', sources['alma']['rec']
        if not rec.get('mes_ref'):
            raise ValueError('Receita vigente não identificada no relatório de contas a receber do Alma.')
    else:
        rec_source, rec = max(recs, key=lambda pair: alma.month_key(pair[1]['mes_ref']))
    rec = dict(rec, sistema=rec_source)
    if rec.get('mes_ref') != bal['meses'][-1]:
        warnings.append(f'Receita fixa baseada em {rec["mes_ref"]}; o período termina em {bal["meses"][-1]}. Confirme a vigência da cobrança.')
    ina = None
    arrears_known = False
    if 'alma' in systems:
        if (root / 'alma_inad.pdf').exists():
            tax_sources = []
            if 'condo21' in systems:
                tax_sources.append((sources['condo21']['rec']['mes_ref'],
                                    alma.read_unit_taxes(root / 'rec02.xls')))
            if 'group' in systems:
                group_rec = sources['group']['rec']
                unit_taxes = defaultdict(float)
                for item in group_rec['itens']:
                    if item['mes_ref'] == group_rec['mes_ref'] and 'condominio' in alma.norm(item['classe']):
                        unit = str(int(item['unidade'])) if item['unidade'].isdigit() else item['unidade']
                        unit_taxes[unit] += item['lancado']
                tax_sources.append((group_rec['mes_ref'], dict(unit_taxes)))
            usable = [(ref, taxes) for ref, taxes in tax_sources if ref and taxes]
            taxes = max(usable, key=lambda pair: alma.month_key(pair[0]))[1] if usable else {}
            try:
                ina = alma.read_arrears(root / 'alma_inad.pdf', taxes)
                arrears_known = True
                if ina['itens'] and abs(sum(taxes.values()) - rec['tx_condominio_mensal']) > 0.02:
                    warnings.append('A taxa individual usada na inadimplência difere da cobrança agregada atual; confira os valores por unidade na revisão.')
            except ValueError as exc:
                if not taxes and 'identificar a taxa condominial da unidade' in str(exc):
                    warnings.append('Alma: o relatório agrega taxa, fundo e consumo. Sem taxa condominial individual por unidade, o abatimento por inadimplência não foi apurado.')
                else:
                    raise
        else:
            arrears_known = True  # ausência declarada, validada no upload
    else:
        warnings.append('Relatório de inadimplência da fonte atual não fornecido; o abatimento por débitos não foi apurado.')
    first = dt.datetime.strptime(keys[0], '%Y-%m').date()
    last = dt.datetime.strptime(keys[-1], '%Y-%m').date()
    last = last.replace(day=calendar.monthrange(last.year, last.month)[1])
    return {'bal': bal, 'des': {'itens': items, 'classe_totais': dict(class_totals),
                              'grupo_totais': dict(group_totals), 'grand_total': round(sum(i['valor_pago'] for i in items), 2),
                              'periodo': (first, last)},
            'rec': rec, 'sin': {'grand_total': None}, 'inad': ina, 'divergencias': warnings,
            'cobertura': coverage, 'sistemas': systems, 'inadimplencia_apurada': arrears_known,
            'origem_sistema': systems[0] if len(systems) == 1 else 'misto'}
