import io
import sys
import types
import unittest

sys.modules.setdefault('xlrd', types.ModuleType('xlrd'))
weasyprint = types.ModuleType('weasyprint')
weasyprint.HTML = object
sys.modules.setdefault('weasyprint', weasyprint)

from openpyxl import load_workbook

import relatorio_xlsx
from test_relatorio_docx import _estado


def _linha(ws, texto):
    return next(r for r in range(1, ws.max_row + 1) if ws[f'A{r}'].value == texto)


class RelatorioXlsxTest(unittest.TestCase):
    def setUp(self):
        self.wb = load_workbook(io.BytesIO(relatorio_xlsx.gerar_relatorio_xlsx(_estado())))
        self.ws = self.wb['Previsão']

    def test_totais_sao_formulas_com_linhas_livres(self):
        ws = self.ws
        tot_rec = _linha(ws, 'Total mensal')
        self.assertTrue(ws[f'C{tot_rec}'].value.startswith('=SUM(C'))
        # Linhas em branco dentro do intervalo somado, para incluir contas novas.
        self.assertIsNone(ws[f'A{tot_rec - 1}'].value)
        sub = _linha(ws, 'SUBTOTAL')
        self.assertIsNone(ws[f'A{sub - 1}'].value)
        self.assertEqual(ws[f'C{sub + 1}'].value, f'=C{sub}*B{sub + 1}')
        self.assertAlmostEqual(ws[f'B{sub + 1}'].value, 0.10)
        self.assertEqual(_linha(ws, 'TOTAL PREVISTO'), sub + 2)

    def test_fundo_separado_nas_opcoes(self):
        ws = self.ws
        fundo = _linha(ws, 'Fundo de reserva')
        self.assertEqual(ws[f'B{fundo}'].value, 'Fundo de reserva')
        sem = _linha(ws, 'Receitas sem fundo de reserva')
        com = _linha(ws, 'Receitas com fundo de reserva')
        self.assertNotIn('"Fundo de reserva"', ws[f'B{sem}'].value.split('-', 1)[0])
        self.assertTrue(ws[f'B{com}'].value.count('"Fundo de reserva"') == 2)

    def test_grafico_mensal_ligado_a_receita(self):
        ws = self.wb['Evolução mensal']
        self.assertEqual(ws['B5'].value, "='Previsão'!$C$" + str(_linha(self.ws, 'Total mensal')))
        self.assertEqual(len(ws._charts), 1)
