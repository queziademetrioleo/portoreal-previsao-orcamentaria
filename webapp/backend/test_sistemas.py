import itertools
import json
import tempfile
from datetime import date
from pathlib import Path
import unittest
from unittest.mock import patch

import test_mixed_upload
import main
import parsers_sistemas as selected


def source(month):
    year, number = map(int, month.split('-'))
    label = f'{number:02}/{year}'
    bal = {'meses': [label], 'n_meses': 1, 'total_receitas': 100, 'total_despesas': 60,
           'receitas': [{'grupo': 'Receitas Operacionais', 'classe': 'Tx. Condomínio',
                         'monthly': [100], 'total': 100, 'n_meses': 1}],
           'despesas': [{'grupo': 'Conservação', 'classe': 'Manutenção Elétrica',
                         'monthly': [60], 'total': 60, 'n_meses': 1}]}
    item = {'grupo': 'Conservação', 'classe': 'Manutenção Elétrica', 'data': date(year, number, 5),
            'valor_pago': 60, 'valor_lcto': 60, 'descricao': 'Manutenção', 'fornecedor': 'Empresa'}
    rec = {'mes_ref': label, 'fixo_anual': 1200, 'tx_condominio_mensal': 100,
           'fundo_reserva_mensal': 0, 'fundo_reserva_anual': 0, 'por_classe': {}, 'itens': []}
    return {'bal': bal, 'des': {'itens': [item]}, 'rec': rec, 'divergencias': [], 'inad': None}


class SystemsConsolidationTest(unittest.TestCase):
    def test_all_seven_combinations_cover_each_month_once(self):
        systems = ('condo21', 'group', 'alma')
        for size in range(1, 4):
            for combination in itertools.combinations(systems, size):
                with self.subTest(combination=combination):
                    data = {name: source(f'2026-{index:02}') for index, name in enumerate(combination, 1)}
                    balance, keys, coverage = selected.consolidate(data)
                    self.assertEqual(balance['total_despesas'], 60 * size)
                    self.assertEqual(balance['n_meses'], size)
                    self.assertEqual(list(coverage.values()), list(combination))

    def test_overlap_gaps_and_requested_period_are_checked(self):
        with self.assertRaisesRegex(ValueError, 'mais de um sistema'):
            selected.consolidate({'group': source('2026-01'), 'alma': source('2026-01')})
        with self.assertRaisesRegex(ValueError, 'Faltam dados'):
            selected.consolidate({'group': source('2026-01'), 'alma': source('2026-03')})
        balance, _, coverage = selected.consolidate({'group': source('2026-01'), 'alma': source('2026-02')}, '2026-02', '2026-02')
        self.assertEqual(balance['total_despesas'], 60)
        self.assertEqual(coverage, {'2026-02': 'alma'})

    def test_group_and_alma_and_alma_alone_use_latest_receipt_and_keep_details(self):
        for systems in (['alma'], ['group', 'alma'], ['condo21', 'group', 'alma'], ['condo21', 'group']):
            with self.subTest(systems=systems), tempfile.TemporaryDirectory() as folder:
                (Path(folder) / 'importacao.json').write_text(json.dumps({'sistemas': systems, 'sem_inadimplencia_alma': True}))
                data = {name: source(f'2026-{i:02}') for i, name in enumerate(systems, 1)}
                fallback = source('2026-01')
                with patch.object(selected.group, 'load_group', return_value=data.get('group', fallback)), \
                     patch.object(main.core, 'parse_balanual', return_value=data.get('condo21', fallback)['bal']), \
                     patch.object(main.core, 'parse_desbai', return_value=data.get('condo21', fallback)['des']), \
                     patch.object(main.core, 'parse_rec', return_value=data.get('condo21', fallback)['rec']), \
                     patch.object(selected.alma, 'read_balance', return_value=data.get('alma', fallback)['bal']), \
                     patch.object(selected.alma, 'read_fin', return_value=data.get('alma', fallback)['des']['itens']), \
                     patch.object(selected.alma, 'read_receivables', return_value=data.get('alma', fallback)['rec']), \
                     patch.object(selected.alma, 'read_internal_plan', return_value={}):
                    result = selected.load_selected(folder, main.core)
                self.assertEqual(len(result['des']['itens']), len(systems))
                self.assertEqual(result['rec']['sistema'], systems[-1])
                self.assertEqual(result['bal']['total_despesas'], 60 * len(systems))
                self.assertEqual(result['sistemas'], systems)

    def test_alma_arrears_without_individual_taxes_is_explicitly_uncomputed(self):
        data = source('2026-01')
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'importacao.json').write_text(json.dumps({'sistemas': ['alma']}))
            (Path(folder) / 'alma_inad.pdf').write_bytes(b'pdf')
            with patch.object(selected.alma, 'read_balance', return_value=data['bal']), \
                 patch.object(selected.alma, 'read_fin', return_value=data['des']['itens']), \
                 patch.object(selected.alma, 'read_receivables', return_value=data['rec']), \
                 patch.object(selected.alma, 'read_internal_plan', return_value={}), \
                 patch.object(selected.alma, 'read_arrears', side_effect=ValueError('Não foi possível identificar a taxa condominial da unidade 101.')):
                result = selected.load_selected(folder, main.core)
        self.assertFalse(result['inadimplencia_apurada'])
        self.assertIsNone(result['inad'])
        self.assertTrue(any('individual por unidade' in warning for warning in result['divergencias']))

    def test_group_receipts_supply_individual_tax_for_alma_arrears(self):
        legacy, current = source('2026-01'), source('2026-02')
        legacy['rec']['itens'] = [{'unidade': '101', 'classe': 'Tx. Condomínio',
                                  'mes_ref': '01/2026', 'lancado': 100}]
        arrears = {'regra': 'misto_ultimos_2_meses_alma', 'itens': [{'valor': 100}]}
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'importacao.json').write_text(json.dumps({'sistemas': ['group', 'alma']}))
            (Path(folder) / 'alma_inad.pdf').write_bytes(b'pdf')
            with patch.object(selected.group, 'load_group', return_value=legacy), \
                 patch.object(selected.alma, 'read_balance', return_value=current['bal']), \
                 patch.object(selected.alma, 'read_fin', return_value=current['des']['itens']), \
                 patch.object(selected.alma, 'read_receivables', return_value=current['rec']), \
                 patch.object(selected.alma, 'read_internal_plan', return_value={}), \
                 patch.object(selected.alma, 'read_arrears', return_value=arrears) as read:
                result = selected.load_selected(folder, main.core)
        self.assertEqual(read.call_args.args[1], {'101': 100})
        self.assertTrue(result['inadimplencia_apurada'])
        self.assertEqual(result['inad'], arrears)


class SystemsUploadTest(unittest.TestCase):
    def setUp(self):
        self.client = test_mixed_upload.TestClient(main.app)
        self.form = {'nome_condominio': 'Teste', 'ano_previsao': '2027', 'sem_inadimplencia_alma': 'true'}

    def files(self, systems):
        fields = {'condo21': ('balanual', 'desbai', 'rec'),
                  'alma': ('alma_bal', 'alma_fin', 'alma_rec'),
                  'group': ('group_bal', 'group_des', 'group_rec')}
        return {field: (main.ARQUIVOS_ESPERADOS[field], b'dados')
                for system in systems for field in fields[system]}

    def test_all_combinations_persist_and_restore_distinct_files(self):
        for count in range(1, 4):
            for systems in itertools.combinations(('condo21', 'alma', 'group'), count):
                row = {}
                def save(sid, field, content):
                    row[main.db.COLUNAS_ARQUIVOS[field]] = content
                def config(sid, content):
                    row['config_importacao'] = content
                with self.subTest(systems=systems), patch.object(main.db, 'criar_sessao'), \
                     patch.object(main.db, 'salvar_arquivo', side_effect=save), \
                     patch.object(main.db, 'salvar_config_importacao', side_effect=config), \
                     patch.object(selected, 'load_selected', return_value={}):
                    response = self.client.post('/api/sessao', data={**self.form, 'sistemas': json.dumps(systems)}, files=self.files(systems))
                self.assertEqual(response.status_code, 200, response.text)
                with tempfile.TemporaryDirectory() as folder:
                    main._restaurar_arquivos(row, folder)
                    for field in self.files(systems):
                        self.assertEqual((Path(folder) / main.ARQUIVOS_ESPERADOS[field]).read_bytes(), b'dados')

    def test_bad_selection_missing_selected_files_and_period_fail_before_persistence(self):
        for systems in ([], ['group', 'group'], ['outro'], 'group', ['alma', 1]):
            with patch.object(main.db, 'criar_sessao') as create:
                response = self.client.post('/api/sessao', data={**self.form, 'sistemas': json.dumps(systems)}, files=self.files(['group']))
                self.assertEqual(response.status_code, 400, response.text)
                create.assert_not_called()
        with patch.object(main.db, 'criar_sessao') as create:
            response = self.client.post('/api/sessao', data={**self.form, 'sistemas': '["alma","group"]'}, files=self.files(['group']))
            self.assertEqual(response.status_code, 400)
            create.assert_not_called()

    def test_consolidation_failure_is_returned_to_user_before_saving(self):
        with patch.object(selected, 'load_selected', side_effect=ValueError('Há meses com movimentação em mais de um sistema.')), \
             patch.object(main.db, 'criar_sessao') as create:
            response = self.client.post('/api/sessao', data={**self.form, 'sistemas': '["alma","group"]'}, files=self.files(['alma', 'group']))
        self.assertEqual(response.status_code, 400)
        self.assertIn('mais de um sistema', response.json()['detail'])
        create.assert_not_called()


if __name__ == '__main__':
    unittest.main()
