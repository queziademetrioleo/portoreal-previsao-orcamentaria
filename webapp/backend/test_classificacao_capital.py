import unittest
import previsao


class ClassificacaoCapitalTest(unittest.TestCase):
    def test_projetores_de_iluminacao_nao_sao_projeto_de_obra(self):
        for descricao in (
            'Aquisição de caixa acoplada c/acionador p/descarga, boia e led projetor.',
            'Aquisição de fita isolante, lâmpadas, botina, projetor LED, tesoura para poda.',
            'Aquisição de projetores para reposição de iluminação.',
        ):
            with self.subTest(descricao=descricao):
                cat, motivo = previsao.classify('Despesas Diversas', 'Outras Despesas',
                                                descricao, 12, 1148.01)
                self.assertEqual(cat, 'Recorrente', motivo)

    def test_projeto_de_obra_continua_identificado(self):
        for descricao in ('Elaboração de projeto estrutural', 'Projetos de engenharia'):
            with self.subTest(descricao=descricao):
                self.assertEqual(previsao.classify('Despesas Diversas', 'Outras Despesas',
                                                   descricao, 12, 1148.01)[0], 'Extraordinaria')

    def test_projetor_em_classe_desconhecida_fica_para_revisao(self):
        cat, motivo = previsao.classify('Conservação', 'Equipamento', 'Projetor LED', 1, 100)
        self.assertEqual(cat, 'Revisar')
        self.assertNotIn('obra/capital', motivo)
