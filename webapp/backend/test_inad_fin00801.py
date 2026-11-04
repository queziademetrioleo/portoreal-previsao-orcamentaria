"""FIN00801 do Alma (José Henrique, 04/11/2026): a inadimplência sai de cada
receita — taxa da Taxa de Condomínio, fundo do Fundo de Reserva, água da Água;
multa, juros, acordo, taxa extra e complemento ficam fora."""
import datetime as dt
import os
import sys
import tempfile
import types
import unittest

sys.modules.setdefault('xlrd', types.ModuleType('xlrd'))
weasyprint = types.ModuleType('weasyprint')
weasyprint.HTML = object
sys.modules.setdefault('weasyprint', weasyprint)

import openpyxl

import main
import parsers_alma as alma
import parsers_group as group
import relatorio_pdf

CAB = ['Bloco', 'Unidade', 'Pagador', 'Doc/Descrição', 'Status', 'Vencimento', 'Parcela',
       'Receita', 'Valor', 'Valor Pago', 'Data Pagto', 'Data Crédito', 'Emissão']


def _boleto(unidade, doc, venc, partes):
    linhas = []
    for i, (receita, valor) in enumerate(partes):
        cab = ['ÚNICO', unidade, 'FULANO', doc, 'Vencido', venc, '01/01'] if i == 0 else [None] * 7
        linhas.append(cab + [receita, valor])
    total = sum(float(v.replace('.', '').replace(',', '.')) for _, v in partes)
    linhas.append([None] * 7 + ['TOTAL', f'{total:.2f}'.replace('.', ','), None, None, None, '21/10/2026'])
    return linhas


def _fin00801(path, boletos, criado=dt.datetime(2026, 11, 4, 14, 0)):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(CAB)
    for b in boletos:
        for linha in b:
            ws.append(linha)
    wb.properties.created = criado
    wb.save(path)


class Fin00801Test(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, 'alma_inad.pdf')  # o campo grava como .pdf

    def tearDown(self):
        self.dir.cleanup()

    def test_abate_cada_receita_do_boleto_mais_recente(self):
        cheio = [('TAXA DE CONDOMÍNIO', '1.272,46'), ('FUNDO DE RESERVA', '127,25'), ('ÁGUA', '40,00'),
                 ('TAXA EXTRA - FINS RESCISÓRIOS', '30,00'), ('COMPLEMENTO TX. CONDOMÍNIO', '92,29'),
                 ('MULTA', '30,44'), ('JUROS', '15,07')]
        _fin00801(self.path, [
            _boleto('410', 'BL 1 REF. MÊS 09/2026', '05/09/2026', cheio),
            _boleto('410', 'BL 2 REF. MÊS 10/2026', '05/10/2026', cheio),
            _boleto('208', 'BL 3 REF. MÊS 09/2026', '05/09/2026', cheio),      # só setembro
            _boleto('105', 'BL 4 02/2016', '05/02/2016', cheio),               # débito antigo
        ])
        r = alma.read_arrears(self.path)
        self.assertEqual(r['meses_considerados'], ['09/2026', '10/2026'])
        self.assertEqual([i['unidade'] for i in r['itens']], ['ÚNICO 410'])
        item = r['itens'][0]
        self.assertEqual(item['mes_ref'], '10/2026')
        self.assertEqual(item['partes'], {'taxa': 1272.46, 'fundo': 127.25, 'agua': 40.0})
        self.assertAlmostEqual(item['valor'], 1439.71)
        self.assertIn('MULTA', item['fora_do_abatimento'])

    def test_boleto_so_de_acordo_nao_conta(self):
        acordo = [('ACORDO JUDICIAL', '2.500,00'), ('JUROS', '258,23')]
        _fin00801(self.path, [_boleto('301', 'BL 9 REF. 09/2026', '05/09/2026', acordo),
                              _boleto('301', 'BL 10 REF. 10/2026', '05/10/2026', acordo)])
        self.assertEqual(alma.read_arrears(self.path)['itens'], [])


class ImpactoPorReceitaTest(unittest.TestCase):
    def _estado(self, partes, com_fundo=True):
        inad = [{'id': 0, 'unidade': '410', 'valor': sum(partes.values()), 'decisao': 'abater', 'partes': partes}]
        estado = {
            'nome_condominio': 'Cidade de Cabo Frio', 'ano_previsao': 2027, 'com_fundo': com_fundo,
            'sistemas': ['group', 'alma'], 'previsao_final': [], 'inadimplencia': inad,
            'linhas_contas': [{'grupo': 'Pessoal', 'classe': 'Salários', 'final': 24000}],
            'resumo': {
                'subtotal': 24000, 'total_previsto': 26400, 'inflacao': 0.10,
                'impacto_receita_mensal': sum(partes.values()),
                'cenarios': {
                    'fundo_reserva_anual': 1200,
                    'com_fundo': {'receita_anual': 31200}, 'sem_fundo': {'receita_anual': 30000},
                    'receitas_ordinarias': [{'classe': 'Taxas de Condomínio', 'mensal': 2000},
                                            {'classe': 'Água', 'mensal': 500}],
                    'receitas_nao_ordinarias': [],
                },
            },
        }
        estado['resumo']['impacto_receita_partes'] = main._impacto_partes(estado)
        return estado

    def test_cada_parte_sai_da_sua_linha(self):
        ctx = relatorio_pdf.montar_contexto_relatorio(self._estado({'taxa': 200, 'fundo': 20, 'agua': 30}))
        self.assertEqual(dict(ctx['receitas']), {'Taxas de condomínio': 'R$ 1.800,00',
                                                  'Fundo de reserva': 'R$ 80,00', 'Água': 'R$ 470,00'})
        sem, com = ctx['opcoes']
        self.assertEqual(sem['receita_mensal'], 'R$ 2.270,00')  # 2500 - 200 - 30 (o fundo não)
        self.assertEqual(com['receita_mensal'], 'R$ 2.350,00')  # 2600 - 250
        self.assertTrue(any('taxas condominiais e do fundo de reserva' in c for c in ctx['consideracoes']))

    def test_sem_fundo_no_relatorio_fundo_inadimplente_nao_reduz_receita(self):
        ctx = relatorio_pdf.montar_contexto_relatorio(self._estado({'taxa': 200, 'fundo': 20}, com_fundo=False))
        self.assertEqual(ctx['opcoes'][0]['receita_mensal'], 'R$ 2.300,00')

    def test_valor_editado_escala_as_partes(self):
        estado = self._estado({'taxa': 200, 'fundo': 50})
        estado['inadimplencia'][0]['valor_editado'] = 125
        self.assertEqual(main._impacto_partes(estado), {'taxa': 100.0, 'fundo': 25.0})

    def test_item_sem_partes_continua_todo_na_taxa(self):
        estado = self._estado({'taxa': 1})
        estado['inadimplencia'] = [{'id': 0, 'unidade': '1', 'valor': 300, 'decisao': 'abater'}]
        self.assertEqual(main._impacto_partes(estado), {'taxa': 300.0})


class GroupNomeTest(unittest.TestCase):
    def test_aceita_cond_sem_ponto(self):
        original = group.read_rows
        group.read_rows = lambda path: [('I Porto Real - VHR',), ('COND CIDADE DE CABO FRIO',)]
        try:
            self.assertEqual(group.read('group_des.xlsx')[1], 'COND CIDADE DE CABO FRIO')
        finally:
            group.read_rows = original


if __name__ == '__main__':
    unittest.main()
