import sys
import types
import unittest

sys.modules.setdefault('xlrd', types.ModuleType('xlrd'))

jinja = types.ModuleType('jinja2')
jinja.Template = object
weasyprint = types.ModuleType('weasyprint')
weasyprint.HTML = object
sys.modules.setdefault('jinja2', jinja)
sys.modules.setdefault('weasyprint', weasyprint)

import previsao
import relatorio_pdf


class RelatorioPdfCalculosTest(unittest.TestCase):
    def test_despesas_do_pdf_fecham_com_subtotal_recalculado(self):
        grupo = 'Despesas Diversas'
        classe = 'Compra de Equipamentos'
        resultado = previsao.recalcular({
            'des': {'itens': [{
                'grupo': grupo,
                'classe': classe,
                'valor_pago': 300.0,
                'cat': 'Extraordinaria',
            }]},
            'bal': {
                'despesas': [{
                    'grupo': grupo,
                    'classe': classe,
                    'total': 1200.0,
                    'monthly': [100.0] * 12,
                    'n_meses': 12,
                }],
                'receitas': [],
                'total_receitas': 0,
            },
            'receita_anual': 24000.0,
            'fundo_reserva_anual': 0.0,
            'inflacao_pct': 0.10,
            'outliers_estatisticos': {},
            'pct_ia_por_classe': {},
        })
        resumo = {
            'subtotal': resultado['subtotal'],
            'prov_laudo': resultado['prov_laudo'],
            'prov_incendio': resultado['prov_incendio'],
        }
        despesas_mensais = relatorio_pdf._consolidar_despesas_relatorio(
            resultado['linhas'], resumo,
        )

        subtotal_pdf_anual = sum(valor for _, valor in despesas_mensais) * 12
        self.assertAlmostEqual(subtotal_pdf_anual, 900.0)
        self.assertAlmostEqual(subtotal_pdf_anual, resultado['subtotal'])


if __name__ == '__main__':
    unittest.main()
