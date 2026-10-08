import datetime as dt
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import xlrd  # Importar o leitor real antes dos testes que usam um stub.
import parsers_alma as alma
import previsao


def balance(months, values):
    return {'meses': months, 'receitas': [], 'despesas': [{
        'grupo': 'Contratos', 'classe': 'Contrato', 'monthly': values,
    }]}


class MixedImportTest(unittest.TestCase):
    def test_wrapped_balance_names_do_not_replace_group_headers(self):
        lines = [
            {'text': 'DESPESAS COM PESSOAL', 'x0': 54, 'top': 100},
            {'text': 'CONSULTORIA, MEDICINA E 10,00 10,00 10,00', 'x0': 65, 'top': 115},
            {'text': 'SEG. DO TRABALHO', 'x0': 65, 'top': 123},
            {'text': 'FGTS 20,00 20,00 20,00', 'x0': 65, 'top': 138},
            {'text': 'CONTRATOS', 'x0': 54, 'top': 146},
            {'text': 'CONTRATO DE MANUTENÇÃO DO 30,00 30,00 30,00', 'x0': 65, 'top': 160},
            {'text': 'ELEVADOR', 'x0': 65, 'top': 168},
        ]
        merged = alma._merge_wrapped_balance_lines(lines)
        self.assertEqual(len(merged), 5)
        self.assertIn('CONSULTORIA, MEDICINA E SEG. DO TRABALHO 10,00', merged[1])
        self.assertEqual(merged[3], 'CONTRATOS')
        self.assertIn('CONTRATO DE MANUTENÇÃO DO ELEVADOR 30,00', merged[4])

    @unittest.skipUnless(Path('tmp/berlin-db-audit/alma_bal.pdf').exists(), 'Documentos privados de Berlin indisponíveis')
    def test_berlin_real_wrapped_accounts_reconcile_without_duplicate_expenses(self):
        import parsers_sistemas
        with tempfile.TemporaryDirectory() as folder:
            for name in ('alma_bal.pdf', 'alma_fin.xlsx', 'alma_rec.pdf'):
                shutil.copyfile(Path('tmp/berlin-db-audit') / name, Path(folder) / name)
            (Path(folder) / 'importacao.json').write_text(json.dumps({'sistemas': ['alma'], 'sem_inadimplencia_alma': True}))
            result = parsers_sistemas.load_selected(folder, previsao)
        account_warnings = [w for w in result['divergencias'] if 'demonstrativo' in w or 'pagamento sem conta' in w]
        self.assertEqual(len(account_warnings), 1)
        self.assertIn('TARIFAS BANCÁRIAS', account_warnings[0])
        self.assertAlmostEqual(result['bal']['total_despesas'], 110850.08, places=2)
        self.assertAlmostEqual(result['bal']['total_despesas'], result['bal']['total_despesas_demonstrativos'], places=2)
        rows = result['bal']['despesas']
        self.assertEqual(next(r for r in rows if r['classe'] == 'FGTS')['grupo'], 'Despesas com Pessoal')
        self.assertFalse(any(r.get('somente_detalhe') for r in rows))

    @unittest.skipUnless(Path('tmp/berlin-db-audit/balanual.xls').exists(), 'Documentos privados de Berlin indisponíveis')
    def test_group_legacy_xls_is_rejected_by_condo_reader(self):
        with self.assertRaisesRegex(ValueError, 'selecione Group'):
            previsao.parse_balanual('tmp/berlin-db-audit/balanual.xls')

    def test_internal_chart_maps_pool_guardian_without_uploaded_workbook(self):
        plan = alma.read_internal_plan()
        self.assertEqual(plan[alma.norm('CONTRATO DE GUARDIÃO DE PISCINA')][0]['grupo'], 'Contratos')

    def test_fin_uses_payment_date_even_when_due_date_is_in_another_month(self):
        wb = MagicMock()
        wb.active.values = iter([
            ('Despesa', 'Valor Pago', 'Data Pagto', 'Fornecedor', 'Status', 'Vencimento'),
            ('Guardião', '1.200,00', '02/08/2026', 'Fornecedor', 'Pago', '15/07/2026'),
        ])
        with patch.object(alma.openpyxl, 'load_workbook', return_value=wb):
            items = alma.read_fin('FIN.xlsx', {alma.norm('Guardião'): [{'grupo': 'Contratos'}]}, {})
        self.assertEqual(items[0]['data'], dt.date(2026, 8, 2))
        self.assertEqual(items[0]['grupo'], 'Contratos')

    def test_paid_fin_row_without_payment_date_is_rejected(self):
        wb = MagicMock()
        wb.active.values = iter([
            ('Despesa', 'Valor Pago', 'Data Pagto', 'Fornecedor', 'Status'),
            ('Contrato', '1.200,00', None, 'Fornecedor', 'Pago'),
        ])
        with patch.object(alma.openpyxl, 'load_workbook', return_value=wb):
            with self.assertRaisesRegex(ValueError, 'sem Data Pagto'):
                alma.read_fin('FIN.xlsx', {}, {})

    def test_zero_future_month_is_replaced_by_alma_without_double_counting(self):
        result, keys, coverage = alma.consolidate_balances(
            balance(['06/2026', '07/2026'], [100, 0]), balance(['07/2026'], [200]))
        self.assertEqual(result['total_despesas'], 300)
        self.assertEqual(keys, ['2026-06', '2026-07'])
        self.assertEqual(coverage['2026-07'], 'alma')

    def test_overlap_and_missing_month_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'dois sistemas'):
            alma.consolidate_balances(balance(['07/2026'], [100]), balance(['07/2026'], [200]))
        with self.assertRaisesRegex(ValueError, 'Faltam dados'):
            alma.consolidate_balances(balance(['05/2026'], [100]), balance(['07/2026'], [200]))

    def test_arrears_use_report_months_and_latest_tax_per_unit(self):
        lines = [(1, 'Boletos em 17/09/2026'),
                 (1, 'UNICO 01 BL REF. MÊS 15/07/2026 1.800,00 0,00 1.800,00'),
                 (1, 'UNICO 01 BL REF. MÊS 15/08/2026 1.800,00 0,00 1.800,00'),
                 (1, 'UNICO 01 BL REF. MÊS 15/09/2026 1.800,00 0,00 1.800,00'),
                 (1, 'UNICO 02 BL REF. MÊS 15/08/2026 1.800,00 1.800,00 0,00'),
                 (1, 'UNICO 03 BL REF. MÊS 30/09/2026 1.800,00 0,00 1.800,00')]
        with patch.object(alma, 'pdf_lines', return_value=lines):
            result = alma.read_arrears('alma_inad.pdf', {'1': 1632})
        self.assertEqual(result['meses_considerados'], ['08/2026', '09/2026'])
        self.assertEqual(len(result['itens']), 1)
        self.assertEqual(result['itens'][0]['mes_ref'], '09/2026')
        self.assertEqual(result['impacto_mensal_receita'], 1632)

    def test_historical_arrears_are_zero_without_recent_alma_titles(self):
        with patch.object(alma, 'pdf_lines', return_value=[
            (1, 'Boletos em 17/09/2026'),
            (1, 'UNICO 01 BL REF. MÊS 15/07/2026 1.800,00 0,00 1.800,00'),
        ]):
            result = alma.read_arrears('alma_inad.pdf', {})
        self.assertEqual(result['impacto_mensal_receita'], 0)


SANTORINI = Path('/Users/Usuario/Downloads/Santorini')


@unittest.skipUnless(SANTORINI.exists(), 'Documentos locais de validação indisponíveis')
class SantoriniIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        mapping = {
            'balanual.xls': 'balanual.xls', 'desbai06.xls': 'desbai06.xls',
            'rec02.xls': 'rec02.xls', 'inad01.xls': 'inad01.xls',
            'alma_fin.xlsx': 'FIN00601 - despesas detalhadas almah.xlsx',
            'alma_bal.pdf': 'Por Período Agrupado Por Contas.pdf',
            'alma_rec.pdf': 'Relatório Contas a receber agrupado por conta.pdf',
            'alma_inad.pdf': 'Relatório Inadimplência (1).pdf',
        }
        import unicodedata
        actual = {unicodedata.normalize('NFC', p.name): p for p in SANTORINI.iterdir()}
        for target, source in mapping.items():
            shutil.copyfile(actual[source], self.folder / target)

    def test_full_analysis_reconciles_sources_and_ignores_old_arrears(self):
        self.assertFalse((self.folder / 'plano_alma.xlsx').exists())
        with patch.object(previsao, '_ia_disponivel', return_value=False):
            result = previsao.analisar(str(self.folder))
        self.assertEqual(len(result['des']['itens']), 249)
        self.assertAlmostEqual(result['des']['grand_total'], 247103.24)
        self.assertAlmostEqual(result['bal']['total_despesas'], 247158.62)
        self.assertEqual(result['inad']['meses_considerados'], ['08/2026', '09/2026'])
        self.assertEqual(result['inad']['impacto_mensal_receita'], 0)
        self.assertTrue(any('55.38' in warning for warning in result['divergencias']))
        self.assertEqual(result['origem_sistema'], 'misto')

    def test_selected_fin_period_and_absent_alma_arrears_do_not_use_condo(self):
        (self.folder / 'alma_inad.pdf').unlink()
        (self.folder / 'importacao.json').write_text(json.dumps({
            'periodo_inicio': '2026-07', 'periodo_fim': '2026-08',
        }))
        result = alma.load_mixed(self.folder, previsao)
        self.assertEqual(len(result['des']['itens']), 37)
        self.assertAlmostEqual(result['des']['grand_total'], 33668.19)
        self.assertIsNone(result['inad'])
        self.assertEqual(result['des']['periodo'], (dt.date(2026, 7, 1), dt.date(2026, 8, 31)))

if __name__ == '__main__':
    unittest.main()
