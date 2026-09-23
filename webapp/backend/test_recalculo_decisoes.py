import sys
import types
import unittest

# O ambiente de desenvolvimento não instala o leitor XLS legado; estes testes
# exercitam apenas o cálculo puro e não abrem arquivos.
sys.modules.setdefault('xlrd', types.ModuleType('xlrd'))

import previsao


def montar_resultado(grupo, classe, categoria='Extraordinaria'):
    return {
        'des': {'itens': [{
            'grupo': grupo,
            'classe': classe,
            'valor_pago': 300.0,
            'cat': categoria,
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
    }


class RecalculoDecisoesTest(unittest.TestCase):
    def test_x_reduz_total_em_todas_as_regras_especiais(self):
        casos = [
            ('Despesas Diversas', 'Manutenção Portal'),
            ('Despesas Diversas', 'Outras Despesas'),
            ('Despesas Diversas', 'Compra de Equipamentos'),
            ('Despesas Cartoriais', 'Custas e Honorários'),
            ('Despesas com Pessoal', 'Rescisão Trabalhista'),
            ('Contratos', 'Contrato de Elevador'),
            ('Contratos', 'Serviço Operacional'),
        ]
        for grupo, classe in casos:
            with self.subTest(grupo=grupo, classe=classe):
                resultado = previsao.recalcular(montar_resultado(grupo, classe))
                self.assertAlmostEqual(resultado['subtotal'], 900.0)
                self.assertAlmostEqual(resultado['total_previsto'], 990.0)
                self.assertAlmostEqual(resultado['linhas'][0]['deducao'], 300.0)

    def test_sem_x_preserva_valor_total(self):
        resultado = previsao.recalcular(montar_resultado(
            'Despesas Diversas', 'Compra de Equipamentos', 'Recorrente',
        ))
        self.assertAlmostEqual(resultado['subtotal'], 1200.0)
        self.assertAlmostEqual(resultado['prov_laudo'], 1200.0)

    def test_obras_ficam_fora_mesmo_mantidas_na_revisao(self):
        resultado = previsao.recalcular(montar_resultado(
            'Despesas com Obras/Benfeitorias', 'Despesas com Mão de Obra', 'Recorrente',
        ))
        self.assertAlmostEqual(resultado['subtotal'], 0.0)
        self.assertAlmostEqual(resultado['desconsideracoes'], 1200.0)

    def test_sistema_de_combate_a_incendio_fica_fora(self):
        resultado = previsao.recalcular(montar_resultado(
            'Conservação', 'Sistema de Combate a Incêndio', 'Recorrente',
        ))
        self.assertAlmostEqual(resultado['subtotal'], 0.0)

    def test_extintores_continuam_na_previsao(self):
        resultado = previsao.recalcular(montar_resultado(
            'Conservação', 'Manut. Extintores e/ou Teste mangueira', 'Recorrente',
        ))
        self.assertAlmostEqual(resultado['subtotal'], 1200.0)


if __name__ == '__main__':
    unittest.main()
