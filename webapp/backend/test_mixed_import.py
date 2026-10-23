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

    def test_fin_without_status_column_treats_dated_rows_as_paid(self):
        """Forte Way: exportação só de pagas, sem coluna Status."""
        wb = MagicMock()
        wb.active.values = iter([
            ('Despesa', 'Valor Pago', 'Data Pagto', 'Fornecedor', 'Descrição', 'Observações'),
            ('Gás do Condomínio', '51,07', '03/08/2026', 'Naturgy', 'Cliente', ''),
        ])
        with patch.object(alma.openpyxl, 'load_workbook', return_value=wb):
            items = alma.read_fin('FIN.xlsx', {}, {})
        self.assertEqual([(i['classe'], i['valor_pago']) for i in items], [('Gás do Condomínio', 51.07)])
        # Linha sem data e sem "TOTAL" depois: recusa, para não sumir com um pagamento.
        wb.active.values = iter([
            ('Despesa', 'Valor Pago', 'Data Pagto', 'Fornecedor'),
            ('Contrato', '100,00', None, 'Fornecedor'),
        ])
        with patch.object(alma.openpyxl, 'load_workbook', return_value=wb):
            with self.assertRaisesRegex(ValueError, 'sem Data Pagto'):
                alma.read_fin('FIN.xlsx', {}, {})

    def test_unit_apportionment_xlsx_replaces_receivables_pdf(self):
        """Rateio por Unidade (XLSX, estilos inválidos p/ openpyxl) no lugar do Contas a receber."""
        import os, zipfile
        cells = [['BLOCO', 'UNIDADE', 'PROPRIETÁRIO', 'VENCIMENTO', 'COTA CONDOMINIAL', 'FUNDO DE RESERVA',
                  'CHAMADA DE CAPITAL (REF. 13º SALÁRIO)', 'TOTAL'],
                 ['UNICO', '101', 'A', '10/10/2026', '1.314,80', '131,48', '145,45', '1.591,73'],
                 ['UNICO', '405', 'B', '10/10/2026', '-', '141,13', '156,12', '297,25'],
                 ['UNICO', 'TESTE', 'C', '10/10/2026', '-', '-', '-', '0,00'],
                 [None, None, '3 UNIDADE(S)', None, '1.314,80', '272,61', '301,57', '1.888,98']]
        def row_xml(number, values):
            return f'<row r="{number}">' + ''.join(
                f'<c r="{chr(65 + i)}{number}" t="inlineStr"><is><t>{v}</t></is></c>'
                for i, v in enumerate(values) if v is not None) + '</row>'
        sheet = ('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                 + ''.join(row_xml(n, r) for n, r in enumerate(cells, 1)) + '</sheetData></worksheet>')
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'alma_rec.pdf')  # nome fixo da restauração; formato vem do conteúdo
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('xl/worksheets/sheet1.xml', sheet)
            rec = alma.read_receivables(path)
        self.assertEqual(rec['mes_ref'], '10/2026')
        self.assertEqual(rec['tx_condominio_mensal'], 1314.80)
        self.assertEqual(rec['fundo_reserva_mensal'], 272.61)
        receita = previsao._receitas_previstas_documento(rec)
        self.assertAlmostEqual(sum(l['mensal'] for l in receita), 1587.41)  # chamada de capital fica fora

    def test_fin_split_payment_takes_date_and_supplier_from_total_row(self):
        """Forte Way: duas partes sem data + linha TOTAL com data/fornecedor."""
        wb = MagicMock()
        wb.active.values = iter([
            ('Despesa', 'Valor Pago', 'Data Pagto', 'Fornecedor', 'Descrição', 'Observações'),
            ('CONTRATO DE MANUTENÇÃO (GERAL)', '267,68', '', '', '', ''),
            ('CONTRATO DE MANUTENÇÃO (GERAL)', '176,52', '', '', '', ''),
            ('TOTAL', '444,20', '18/08/2026', 'FENIX', 'MONITORAMENTO 24H', ''),
            ('GÁS DO CONDOMÍNIO', '51,07', '03/08/2026', 'NATURGY', '', ''),
            ('Total', '495,27', '', '', '', ''),
        ])
        with patch.object(alma.openpyxl, 'load_workbook', return_value=wb):
            items = alma.read_fin('FIN.xlsx', {}, {})
        self.assertEqual([(i['valor_pago'], i['data'], i['fornecedor']) for i in items[:2]],
                         [(267.68, dt.date(2026, 8, 18), 'FENIX'), (176.52, dt.date(2026, 8, 18), 'FENIX')])
        self.assertAlmostEqual(sum(i['valor_pago'] for i in items), 495.27)

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

    def test_alma_exported_for_whole_year_ignores_zero_months_before_migration(self):
        """Forte Way: Alma exportado de 06 a 08 com zeros antes da migração em 08."""
        result, keys, coverage = alma.consolidate_balances(
            balance(['06/2026', '07/2026'], [100, 150]), balance(['06/2026', '07/2026', '08/2026'], [0, 0, 200]))
        self.assertEqual(result['total_despesas'], 450)
        self.assertEqual(keys, ['2026-06', '2026-07', '2026-08'])
        self.assertEqual([coverage[k] for k in keys], ['condo21', 'condo21', 'alma'])

    def test_overlap_month_sums_both_systems(self):
        """Forte Way (José, 22/10/2026): tarifa lançada em 07 e 08 nos dois sistemas se complementa."""
        result, keys, coverage = alma.consolidate_balances(
            balance(['06/2026', '07/2026', '08/2026'], [100, 150, 30]),
            balance(['07/2026', '08/2026', '09/2026'], [20, 200, 210]))
        self.assertEqual(keys, ['2026-06', '2026-07', '2026-08', '2026-09'])
        self.assertEqual(result['total_despesas'], 710)
        self.assertEqual([coverage[k] for k in keys], ['condo21', 'condo21+alma', 'condo21+alma', 'alma'])
        self.assertEqual([o['mes'] for o in result['sobreposicao']], ['07/2026', '08/2026'])
        self.assertEqual((result['sobreposicao'][1]['condo21'], result['sobreposicao'][1]['alma']), (30, 200))

    def test_missing_month_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Faltam dados'):
            alma.consolidate_balances(balance(['05/2026'], [100]), balance(['07/2026'], [200]))

    def test_arrears_require_both_previous_months_and_abate_whole_bill(self):
        """Exemplo do José: em outubro, inadimplente é quem deve setembro E agosto."""
        lines = [(1, 'Boletos em 05/10/2026'),
                 # 01: deve agosto e setembro → inadimplente
                 (1, 'UNICO 01 BL REF. MÊS 15/08/2026 1.800,00 0,00 1.800,00'),
                 (1, 'UNICO 01 BL REF. MÊS 15/09/2026 1.900,00 0,00 1.900,00'),
                 # 02: deve só setembro → não
                 (1, 'UNICO 02 BL REF. MÊS 15/09/2026 1.800,00 0,00 1.800,00'),
                 # 03: deve março e abril, pagou de maio a setembro (acordo) → não
                 (1, 'UNICO 03 BL REF. MÊS 15/03/2026 1.800,00 0,00 1.800,00'),
                 (1, 'UNICO 03 BL REF. MÊS 15/04/2026 1.800,00 0,00 1.800,00'),
                 # 04: deve de junho a setembro → inadimplente, abate um boleto só
                 (1, 'UNICO 04 BL REF. MÊS 15/06/2026 1.700,00 0,00 1.700,00'),
                 (1, 'UNICO 04 BL REF. MÊS 15/07/2026 1.700,00 0,00 1.700,00'),
                 (1, 'UNICO 04 BL REF. MÊS 15/08/2026 1.700,00 0,00 1.700,00'),
                 (1, 'UNICO 04 BL REF. MÊS 15/09/2026 1.700,00 0,00 1.700,00'),
                 # 05: boleto de outubro ainda não entra na janela
                 (1, 'UNICO 05 BL REF. MÊS 15/09/2026 1.800,00 1.800,00 0,00')]
        with patch.object(alma, 'pdf_lines', return_value=lines):
            result = alma.read_arrears('alma_inad.pdf')
        self.assertEqual(result['meses_considerados'], ['08/2026', '09/2026'])
        self.assertEqual({i['unidade']: i['valor'] for i in result['itens']},
                         {'UNICO 01': 1900, 'UNICO 04': 1700})
        # Boleto inteiro (taxa, fundo e água), um mês por unidade.
        self.assertEqual(result['impacto_mensal_receita'], 3600)

    def test_historical_arrears_are_zero_without_recent_alma_titles(self):
        with patch.object(alma, 'pdf_lines', return_value=[
            (1, 'Boletos em 17/09/2026'),
            (1, 'UNICO 01 BL REF. MÊS 15/07/2026 1.800,00 0,00 1.800,00'),
        ]):
            result = alma.read_arrears('alma_inad.pdf')
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
        # Relatório de 17/09: os dois meses anteriores ao mês do relatório.
        self.assertEqual(result['inad']['meses_considerados'], ['07/2026', '08/2026'])
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

    def test_mixed_receipt_is_alma_even_if_condo_receipt_is_newer(self):
        (self.folder / 'alma_inad.pdf').unlink()
        expected = alma.read_receivables(self.folder / 'alma_rec.pdf')
        with patch.object(previsao, 'parse_rec', return_value={'mes_ref': '12/2030', 'fixo_anual': 999999}):
            result = alma.load_mixed(self.folder, previsao)
        self.assertEqual(result['rec']['sistema'], 'alma')
        self.assertEqual(result['rec']['fixo_anual'], expected['fixo_anual'])

if __name__ == '__main__':
    unittest.main()
