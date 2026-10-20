"""Contratos Group e conferência opcional contra os XLSX privados locais."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import previsao as core
import parsers_group as group


class GroupImportTest(unittest.TestCase):
    def setUp(self):
        self.months = ['10/2025', '11/2025', '12/2025'] + [f'{m:02}/2026' for m in range(1, 10)]
        self.balance = [
            ['COND. TESTE'], ['Classe de conta', *self.months, 'Total'],
            ['Receitas'], ['1.1 - Receitas Operacionais'],
            ['1.1.2 - .Tx. Condomínio', *([100] * 12), 1200],
            ['Total de receitas', *([100] * 12), 1200],
            ['Despesas'], ['2.8 - Contratos'],
            ['2.8.1 - Elevador', *([20] * 12), 240],
            ['Total de despesas', *([20] * 12), 240],
        ]
        self.expenses = [['COND. TESTE'], [
            'Classe de conta', 'Fornecedor', 'Competência', 'Vencimento',
            'Pagamento', 'Valor lançado (R$)', 'Valor pago (R$)', 'Descrição'],
            ['2.8 - Contratos']]
        for month in self.months:
            self.expenses.append(['2.8.1 - Elevador', 'Empresa', month,
                                  f'10/{month}', f'10/{month}', 20, 20, 'Contrato'])
        self.expenses.append(['Total de despesas', None, None, None, None, 240, 240, None])
        self.receipts = [['COND. TESTE'], [
            'Unidade', 'NN', 'Classe de Conta', 'Competência',
            'Recebimento', 'Valor (R$)', 'Valor recebido (R$)'],
            ['101', '123- Excluída', '1.1.2 - .Tx. Condomínio', '06/2026', '-', 100, '-'],
            ['101', '456', '1.1.2 - .Tx. Condomínio', '06/2026', '10/06/2026', 100, 100],
            ['101', '456', '1.1.3 - .Fundo Reserva', '06/2026', '10/06/2026', 5, 5],
            ['Total de receitas das unidades', None, None, None, None, 205, 105],
            ['Fornecedor', 'NN', 'Classe de Conta', 'Competência',
             'Recebimento', 'Valor (R$)', 'Valor recebido (R$)'],
            ['Banco', '-', '1.1.2 - .Tx. Condomínio', '06/2026', '10/06/2026', 999, 999]]

    def reader(self, path):
        name = Path(path).name
        rows = {'group_bal.xlsx': self.balance, 'group_des.xlsx': self.expenses,
                'group_rec.xlsx': self.receipts}[name]
        return rows, 'COND. TESTE'

    def load(self):
        with patch.object(group, 'read', side_effect=self.reader):
            return group.load_group('/unused', core)

    def test_matches_accounts_and_months_excludes_cancelled_and_supplier_receipts(self):
        data = self.load()
        self.assertEqual(data['bal']['total_despesas'], 240)
        self.assertEqual(data['des']['grand_total'], 240)
        self.assertEqual(data['rec']['fixo_anual'], 1260)
        self.assertEqual(data['rec']['tx_condominio_mensal'], 100)
        self.assertEqual(len(data['rec']['excluidas']), 1)
        self.assertFalse(any('diferenças entre' in v for v in data['divergencias']))
        self.assertTrue(any('inadimplência não fornecido' in v for v in data['divergencias']))

    def test_total_documento_inclui_juros_e_nao_so_taxa_e_fundo(self):
        self.receipts.insert(5, ['101', '456', '1.1.4 - Juros', '06/2026', '10/06/2026', 5, 5])
        self.receipts[6][5] += 5
        self.receipts[6][6] += 5
        rec = self.load()['rec']
        self.assertEqual(rec['total_lancado_mes'], 110)
        self.assertEqual(rec['total_liquidado_mes'], 110)

    def test_reordered_columns_are_read_by_header(self):
        self.expenses = [[r[i] for i in reversed(range(len(r)))] if len(r) == 8 else r for r in self.expenses]
        # Group heading must follow its header column too.
        self.expenses[2] = [None] * 7 + ['2.8 - Contratos']
        self.assertEqual(self.load()['des']['grand_total'], 240)

    def test_month_names_money_and_zero_payment(self):
        self.assertEqual(group.month('out./2025'), '10/2025')
        self.assertEqual(group.month('09/2026'), '09/2026')
        self.assertIsNone(group.month('13/2026'))
        self.assertEqual(float(group.money('1.234,56')), 1234.56)
        with self.assertRaises(ValueError):
            group.money('valor inválido')
        self.expenses[3][6] = 0
        self.expenses[-1][6] = 220
        result = self.load()
        self.assertEqual(result['des']['itens'][0]['valor_pago'], 0)
        self.assertTrue(any('diferenças entre' in v for v in result['divergencias']))

    def test_payment_date_drives_reconciliation_not_competence(self):
        self.expenses[3][2] = '09/2025'
        self.assertFalse(any('diferenças entre' in v for v in self.load()['divergencias']))
        self.expenses[3][4] = '10/09/2025'
        with self.assertRaisesRegex(ValueError, 'fora do período'):
            self.load()

    def test_rejects_bad_totals_duplicate_active_bill_and_missing_receipt_subtotal(self):
        for target in ('balance', 'expenses', 'receipts'):
            with self.subTest(target=target):
                saved = copy.deepcopy(getattr(self, target))
                if target == 'balance':
                    self.balance[4][-1] = 999
                elif target == 'expenses':
                    self.expenses[-1][6] = 999
                else:
                    self.receipts[5][5] = 999
                with self.assertRaises(ValueError):
                    self.load()
                setattr(self, target, saved)
        self.receipts.insert(4, list(self.receipts[3]))
        self.receipts[6][5] += 100
        self.receipts[6][6] += 100
        with self.assertRaisesRegex(ValueError, 'cobrança repetida'):
            self.load()
        self.receipts = self.receipts[:5]
        with self.assertRaises(ValueError):
            self.load()

    def test_account_on_two_balance_lines_is_summed_when_section_total_matches(self):
        """Aldeia das Asas: 1.1.6 Taxa Extra em duas linhas do balancete Group."""
        self.balance[4:4] = [['1.1.6 - Taxa Extra', *([10] * 12), 120],
                             ['1.1.6 - Taxa Extra Obra', 30, *([0] * 11), 30]]
        self.balance[7] = ['Total de receitas', 140, *([110] * 11), 1350]
        with patch.object(group, 'read', side_effect=self.reader):
            bal = group.parse_balance('group_bal.xlsx')
        extra = [r for r in bal['receitas'] if r['codigo'] == '1.1.6']
        self.assertEqual(len(extra), 1)
        self.assertEqual(extra[0]['total'], 150)
        self.assertEqual(extra[0]['monthly'][0], 40)
        self.assertTrue(any('1.1.6' in w and 'somados' in w for w in bal['avisos']))
        # Linha copiada por engano não entra no total da seção e continua barrada.
        self.balance[7] = ['Total de receitas', 110, *([110] * 11), 1320]
        with patch.object(group, 'read', side_effect=self.reader):
            with self.assertRaisesRegex(ValueError, 'soma das classes de receitas'):
                group.parse_balance('group_bal.xlsx')

    def arrears(self):
        head = ['Unidade', 'Sacado', 'NN', 'Classe de conta', 'Competência', 'Vencimento', 'Atraso',
                'Valor (R$)', 'Juros (R$)', 'Total (R$)', 'Informações do acordo', 'Recebimento']
        rows = [['I Porto Real - VHR'], ['INADIMPLÊNCIA DETALHADA'], ['Número de unidades: 4'], [], head]
        def bill(unit, nn, m, received='-', water=50):
            for cls, value in (('1.1.2 - .Tx. Condomínio', 100), ('1.1.3 - .Fundo Reserva', 10), ('1.1.36 - Água', water)):
                rows.append([unit, 'Fulano', nn, cls, m, f'10/{m}', '20', value, 1, value + 1, '-', received])
        bill('Águia - 201', '1', '08/2026'); bill('Águia - 201', '2', '09/2026', water=60)  # deve 08 e 09
        rows.append(['Águia - 201', 'Fulano', '3', '1.7.8 - Acordo Extrajudicial', '09/2026', '20/09/2026', '10', 900, 0, 900, 'Acordo 7', '-'])
        bill('Lince - 102', '4', '09/2026')                                                # só 09
        bill('Pegasus - 310', '5', '08/2026', received='05/10/2026'); bill('Pegasus - 310', '6', '09/2026')  # 08 pago depois
        bill('Pegasus - 505', '7', '02/2026'); bill('Pegasus - 505', '8', '03/2026')     # débito antigo
        total = sum(r[7] for r in rows[5:])
        rows += [['Total inadimplência das unidades', None, None, None, None, None, None, total],
                 ['Filtros:  Inadimplência até:30/09/2026; Competência: Todas'], ['Emissão: 19/10/2026 20:40']]
        return rows

    def test_group_arrears_use_two_months_before_report_like_alma(self):
        """Emissão em outubro: inadimplente é quem deve setembro E agosto (José, 10/2026)."""
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / group.ARREARS_FILE).write_bytes(b'')
            with patch.object(group, 'read', side_effect=self.reader), \
                 patch.object(group, 'read_rows', return_value=self.arrears()):
                data = group.load_group(folder, core)
        ina = data['inad']
        self.assertEqual(ina['meses_considerados'], ['08/2026', '09/2026'])
        self.assertEqual([i['unidade'] for i in ina['itens']], ['Águia - 201'])
        # Boleto inteiro de 09 (taxa + fundo + água), sem juros e sem a parcela do acordo.
        self.assertEqual(ina['itens'][0]['valor'], 170)
        self.assertEqual(ina['impacto_mensal_receita'], 170)
        self.assertFalse(any('inadimplência não fornecido' in v for v in data['divergencias']))

    def test_group_arrears_report_is_checked_against_its_totals(self):
        rows = self.arrears()
        rows[-3][7] += 1
        with patch.object(group, 'read_rows', return_value=rows):
            with self.assertRaisesRegex(ValueError, 'difere do total'):
                group.parse_arrears('inad.xlsx')
        rows = self.arrears()
        rows[2] = ['Número de unidades: 3']
        with patch.object(group, 'read_rows', return_value=rows):
            with self.assertRaisesRegex(ValueError, 'número de unidades'):
                group.parse_arrears('inad.xlsx')
        with patch.object(group, 'read_rows', return_value=self.balance):
            with self.assertRaisesRegex(ValueError, 'Inadimplência detalhada'):
                group.parse_arrears('inad.xlsx')

    def test_rejects_mixed_condominiums_and_short_periods(self):
        def wrong(path):
            rows, name = self.reader(path)
            return rows, 'COND. OUTRO' if str(path).endswith('group_rec.xlsx') else name
        with patch.object(group, 'read', side_effect=wrong), self.assertRaisesRegex(ValueError, 'mesmo condomínio'):
            group.load_group('/unused', core)
        self.balance[1][1] = '09/2025'
        with self.assertRaisesRegex(ValueError, 'consecutivos'):
            self.load()


SAMPLES = os.environ.get('GROUP_SAMPLE_DIR')


@unittest.skipUnless(SAMPLES, 'Defina GROUP_SAMPLE_DIR para conferir os arquivos privados Berlin.')
class BerlinGroupTest(unittest.TestCase):
    def test_real_documents_and_full_engine_without_external_ai(self):
        import shutil
        names = {'balanual': 'Balancete anual Berlin.xlsx',
                 'desbai': 'Despesas detalhadas por classe de conta.xlsx',
                 'rec': 'Receitas_detalhadas_por_unidade_cliente_2026_10_08_14_05_17.xlsx'}
        with tempfile.TemporaryDirectory() as folder:
            for field, name in names.items():
                shutil.copyfile(Path(SAMPLES) / name, Path(folder) / group.FILES[field])
            with patch.object(core, '_ia_disponivel', return_value=False), \
                 patch('ia_parser.ia_parse_pasta', side_effect=AssertionError('Group não usa parser IA')):
                result = core.analisar(folder)
            self.assertEqual(result['origem_sistema'], 'group')
            self.assertEqual(len(result['des']['itens']), 399)
            self.assertEqual(len(result['des']['classe_totais']), 46)
            self.assertAlmostEqual(result['base_total'], 292073.03, places=2)
            self.assertEqual(result['rec']['tx_condominio_mensal'], 31816.28)
            self.assertEqual(result['rec']['fundo_reserva_mensal'], 1479.13)
            self.assertEqual(result['rec']['total_lancado_mes'], 37660.26)
            self.assertEqual(result['receita_anual'], 451923.12)
            self.assertIsNone(result['inad'])
            self.assertFalse(any('diferenças entre' in w for w in result['divergencias']))
            self.assertTrue(any('não fechado' in w for w in result['divergencias']))
            self.assertTrue(any('09/2026' in w and 'sem movimentação' in w for w in result['divergencias']))
            before = result['total_previsto']
            recalculated = core.recalcular(copy.deepcopy(result))
            self.assertAlmostEqual(recalculated['total_previsto'], before, places=2)


if __name__ == '__main__':
    unittest.main()
