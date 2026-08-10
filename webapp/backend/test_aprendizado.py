import unittest

import aprendizado


class AprendizadoTest(unittest.TestCase):
    def setUp(self):
        self.item = {
            'grupo': 'Conservação',
            'classe': 'Manutenção do Portão',
            'descricao': 'NF 1234 - troca emergencial do motor do portão',
        }
        self.memoria = aprendizado.criar_registro(
            'abc123', 7, self.item, 'deduzir',
        )

    def test_ignora_numeros_variaveis_na_descricao(self):
        novo = dict(self.item, descricao='NF 9876 - troca emergencial do motor do portão')
        self.assertEqual(
            aprendizado.encontrar_decisao(novo, [self.memoria]),
            'deduzir',
        )

    def test_nao_generaliza_para_outra_classe(self):
        novo = dict(self.item, classe='Manutenção Elétrica')
        self.assertIsNone(aprendizado.encontrar_decisao(novo, [self.memoria]))

    def test_nao_generaliza_sem_descricao(self):
        novo = dict(self.item, descricao='')
        self.assertIsNone(aprendizado.encontrar_decisao(novo, [self.memoria]))

    def test_aplica_decisao_humana_e_marca_origem(self):
        novo = dict(self.item, cat='Recorrente', motivo='Regra anterior')
        quantidade = aprendizado.aplicar_memorias([novo], [self.memoria])
        self.assertEqual(quantidade, 1)
        self.assertEqual(novo['cat'], 'Extraordinaria')
        self.assertTrue(novo['aprendizado_aplicado'])
        self.assertTrue(novo['motivo'].startswith('Aprendizado humano:'))

    def test_decisao_padrao_preserva_classificacao_inicial(self):
        self.assertEqual(
            aprendizado.decisao_padrao({'categoria_inicial': 'Extraordinaria'}),
            'deduzir',
        )
        self.assertEqual(
            aprendizado.decisao_padrao({'categoria_inicial': 'Revisar'}),
            'pendente',
        )
        self.assertEqual(
            aprendizado.decisao_padrao({'categoria_inicial': 'Recorrente'}),
            'manter',
        )


if __name__ == '__main__':
    unittest.main()
