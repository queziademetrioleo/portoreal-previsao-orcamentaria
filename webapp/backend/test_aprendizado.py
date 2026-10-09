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

    def test_salary_is_not_excluded_by_old_or_conflicting_memories(self):
        item = {'grupo': 'Despesas com Pessoal', 'classe': 'Salário Empregado(s)',
                'descricao': 'JONATAS ALVES DE ANDRADE DE SÁ', 'cat': 'Recorrente'}
        old = aprendizado.criar_registro('antiga', 1, item, 'deduzir')
        self.assertIsNone(aprendizado.encontrar_decisao(item, [old]))
        aprendizado.aplicar_memorias([item], [old])
        self.assertEqual(item['cat'], 'Recorrente')
        self.assertNotIn('aprendizado_aplicado', item)

    def test_cached_salary_misclassification_is_repaired(self):
        item = {'classe': 'Salário Empregado(s)', 'descricao': 'Jonatas',
                'cat': 'Extraordinaria', 'aprendizado_aplicado': True}
        aprendizado.aplicar_memorias([item], [])
        self.assertEqual(item['cat'], 'Recorrente')
        self.assertNotIn('aprendizado_aplicado', item)

    def test_salary_guard_does_not_apply_to_severance_or_repairs(self):
        for classe in ('Rescisão Trabalhista', 'Reparo no Elevador'):
            item = {'grupo': 'Despesas com Pessoal', 'classe': classe,
                    'descricao': 'Jonatas', 'cat': 'Recorrente'}
            memory = aprendizado.criar_registro('antiga', 1, item, 'deduzir')
            aprendizado.aplicar_memorias([item], [memory])
            self.assertEqual(item['cat'], 'Extraordinaria')


if __name__ == '__main__':
    unittest.main()
