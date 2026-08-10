import sys
import types
import unittest
from datetime import date

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
    def test_consideracoes_listam_todas_as_classes_das_categorias(self):
        linhas = [
            {'grupo': 'Conservação', 'classe': 'Manutenção Elétrica', 'final': 100},
            {'grupo': 'Conservação', 'classe': 'Manutenção Hidráulica', 'final': 200},
            {'grupo': 'Despesas Diversas', 'classe': 'Dedetização', 'final': 50},
            {'grupo': 'Conservação', 'classe': 'Item totalmente deduzido', 'final': 0},
            {'grupo': 'Despesas Diversas', 'classe': 'Seguro Predial', 'final': 80},
            {'grupo': 'Conservação', 'classe': 'Material de Limpeza', 'final': 90},
            {'grupo': 'Despesas Administrativas', 'classe': 'Xerox', 'final': 20},
            {'grupo': 'Despesas Administrativas', 'classe': 'Correios', 'final': 30},
            {'grupo': 'Despesas Administrativas', 'classe': 'Material de Expediente', 'final': 40},
        ]
        conservacao = relatorio_pdf._componentes_conservacao(
            linhas, {'prov_laudo': 120, 'prov_incendio': 60},
        )
        administrativas = relatorio_pdf._componentes_administrativas(linhas)

        self.assertEqual(conservacao, [
            'Manutenção Elétrica',
            'Manutenção Hidráulica',
            'Dedetização',
            'Provisão para Laudo de Autovistoria',
            'Provisão para Sistema de Incêndio/Registro',
        ])
        self.assertEqual(administrativas, [
            'Xerox', 'Correios', 'Material de Expediente',
        ])

    def test_reajuste_usa_total_dividido_pela_receita_menos_um(self):
        self.assertAlmostEqual(
            relatorio_pdf._reajuste_necessario(35000, 32000),
            35000 / 32000 - 1,
        )

    def test_reajuste_usa_valor_absoluto_quando_receita_supera_total(self):
        self.assertAlmostEqual(
            relatorio_pdf._reajuste_necessario(29034.47, 32594.70),
            abs(29034.47 / 32594.70 - 1),
        )

    def test_consideracao_sem_fundo_e_curta_e_usa_receita_sem_fundo(self):
        texto = relatorio_pdf._consideracao_fundo_reserva(
            False, 35000, 32000, 30000,
        )
        self.assertEqual(
            texto,
            'Recomendamos um reajuste de 16,7% na taxa condominial para os próximos 12 meses.',
        )

    def test_consideracao_aparece_com_formula_quando_fundo_e_utilizado(self):
        texto = relatorio_pdf._consideracao_fundo_reserva(
            True, 35000, 32000, 30000,
        )
        self.assertIn('9,4%', texto)
        self.assertIn('prática não recomendada', texto)
        self.assertIn('|Total Previsto ÷ Receita Total − 1|', texto)

    def test_tempo_desde_reajuste_usa_meses_antes_de_um_ano(self):
        self.assertEqual(
            relatorio_pdf._tempo_desde_reajuste(2025, 10, date(2026, 8, 10)),
            '10 meses',
        )

    def test_tempo_desde_reajuste_combina_anos_e_meses(self):
        self.assertEqual(
            relatorio_pdf._tempo_desde_reajuste(2024, 6, date(2026, 8, 10)),
            '2 anos e 2 meses',
        )

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
