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
    def test_composicao_administrativa_nunca_cita_decima_terceira_taxa(self):
        for classe in ('13º Taxa de Administração', '13o Taxa de Administracao',
                       '13. Taxa de Administração', '13ª taxa de administração',
                       'Décima terceira taxa de administração', '13° Tx. de Administração'):
            with self.subTest(classe=classe):
                linhas = [
                    {'grupo': 'Despesas Administrativas', 'classe': classe, 'final': 1200},
                    {'grupo': 'Despesas Administrativas', 'classe': 'Correios', 'final': 120},
                    {'grupo': 'Despesas Administrativas', 'classe': 'Taxa de Administração', 'final': 2400},
                ]
                self.assertEqual(relatorio_pdf._componentes_administrativas(linhas),
                                 ['Correios', 'Taxa de Administração'])
                despesas = dict(relatorio_pdf._consolidar_despesas_relatorio(linhas, {}))
                self.assertAlmostEqual(despesas['Despesas Administrativas'] * 12, 3720)

    def test_composicao_apenas_com_decima_terceira_fica_sem_mencao(self):
        linhas = [{'grupo': 'Despesas Administrativas',
                   'classe': '13º Taxa de Administração', 'final': 1200}]
        self.assertEqual(relatorio_pdf._componentes_administrativas(linhas), [])

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

    def test_opcoes_mostram_so_o_que_o_condominio_tem(self):
        aluguel = [{'classe': 'Aluguel de Espaço p/ Antena de Telefonia', 'mensal': 9268.95}]
        opcoes = relatorio_pdf._opcoes_receita(22631.19 * 12, 0, aluguel, 27408.72 * 12)
        self.assertEqual([o['label'] for o in opcoes], [
            'Só receita', 'Receita + Aluguel de Espaço p/ Antena de Telefonia',
        ])
        so_receita, com_aluguel = opcoes
        self.assertAlmostEqual(so_receita['resultado'] / 12, -4777.53, places=2)
        self.assertAlmostEqual(so_receita['reajuste'], 27408.72 / 22631.19 - 1)
        self.assertAlmostEqual(com_aluguel['resultado'] / 12, 4491.42, places=2)
        self.assertEqual(com_aluguel['reajuste'], 0.0)

    def test_quatro_opcoes_quando_tem_fundo_e_aluguel(self):
        aluguel = [{'classe': 'Aluguel de Espaço', 'mensal': 1000}]
        opcoes = relatorio_pdf._opcoes_receita(24000, 6000, aluguel, 30000)
        self.assertEqual([o['label'] for o in opcoes], [
            'Só receita', 'Receita + Fundo de Reserva', 'Receita + Aluguel de Espaço',
            'Receita + Fundo de Reserva + Aluguel de Espaço',
        ])

    def test_consideracao_lista_as_opcoes_com_falta_e_sobra(self):
        aluguel = [{'classe': 'Aluguel de Espaço p/ Antena de Telefonia', 'mensal': 9268.95}]
        opcoes = relatorio_pdf._opcoes_receita(22631.19 * 12, 0, aluguel, 27408.72 * 12)
        texto = relatorio_pdf._consideracao_opcoes(opcoes)
        self.assertIn('a) Só receita: faltam R$ 4.777,53 por mês — reajuste necessário de 21,1%', texto)
        self.assertIn('sobram R$ 4.491,42 por mês — não é necessário reajuste', texto)
        self.assertNotIn('Fundo de Reserva', texto)

    def test_consideracao_com_uma_opcao_e_curta(self):
        opcoes = relatorio_pdf._opcoes_receita(30000, 0, [], 35000)
        self.assertEqual(
            relatorio_pdf._consideracao_opcoes(opcoes),
            'Recomendamos um reajuste de 16,7% na taxa condominial para os próximos 12 meses.',
        )

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

    def test_conservacao_omite_outros_materiais_e_renomeia_extintores(self):
        linhas = [
            {'grupo': 'Conservação', 'classe': 'Outros Materiais', 'final': 100},
            {'grupo': 'Conservação', 'classe': 'Manut. Extintores e/ou Teste mangueira', 'final': 1500},
            {'grupo': 'Conservação', 'classe': 'Manutenção Portão', 'final': 900},
        ]
        self.assertEqual(
            relatorio_pdf._componentes_conservacao(linhas, {}),
            ['Recarga de Extintores', 'Manutenção Portão'],
        )

    def test_contrato_generico_e_dividido_por_servico(self):
        linhas = [{'grupo': 'Contratos', 'classe': 'Contrato de Manutenção', 'final': 12600}]
        lancamentos = []
        for mes in ('2026-06', '2026-07', '2026-08'):
            lancamentos += [
                {'grupo': 'Contratos', 'classe': 'Contrato de Manutenção', 'data': f'{mes}-03',
                 'descricao': 'Segurança Eletrônica - Prevenir Segurança', 'valor_pago': 350},
                {'grupo': 'Contratos', 'classe': 'Contrato de Manutenção', 'data': f'{mes}-05',
                 'descricao': 'da piscina do condomínio - Moises Antunes', 'valor_pago': 700},
            ]
        despesas = dict(relatorio_pdf._consolidar_despesas_relatorio(linhas, {}, lancamentos))
        self.assertAlmostEqual(despesas['Contrato de Segurança Eletrônica'], 350)
        self.assertAlmostEqual(despesas['Contrato de Manutenção da Piscina'], 700)
        self.assertNotIn('Contrato de Manutenção', despesas)

    def test_contrato_com_nf_sem_servico_reconhecido_nao_e_dividido(self):
        linhas = [{'grupo': 'Contratos', 'classe': 'Contrato de Manutenção', 'final': 1200}]
        lancamentos = [
            {'grupo': 'Contratos', 'classe': 'Contrato de Manutenção', 'data': '2026-08-03',
             'descricao': 'Segurança Eletrônica', 'valor_pago': 50},
            {'grupo': 'Contratos', 'classe': 'Contrato de Manutenção', 'data': '2026-08-05',
             'descricao': 'Serviço mensal', 'valor_pago': 50},
        ]
        despesas = dict(relatorio_pdf._consolidar_despesas_relatorio(linhas, {}, lancamentos))
        self.assertAlmostEqual(despesas['Contrato de Manutenção'], 100)


if __name__ == '__main__':
    unittest.main()
