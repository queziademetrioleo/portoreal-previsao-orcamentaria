import json
import unittest
from unittest.mock import patch

import previsao


def item(descricao, categoria='Revisar', pendente=True):
    return {'grupo': 'Conservação', 'classe': 'Materiais', 'data': '2026-06-12',
            'descricao': descricao, 'valor_pago': 300.0, 'n_meses': 3,
            'cat': categoria, 'classificacao_pendente': pendente}


class AvaliadorDespesasTest(unittest.TestCase):
    def test_decisao_aplicada_mesmo_sem_correspondencia_no_demonstrativo(self):
        itens = [item('Compra pontual'), item('Material periódico')]
        previsao.aplicar_avaliacoes_ia(itens, {
            0: ('Extraordinaria', 'Aquisição pontual sem expectativa de repetição.'),
            1: ('Recorrente', 'Consumo regular observado no período.'),
        })
        self.assertEqual([it['cat'] for it in itens], ['Extraordinaria', 'Recorrente'])
        self.assertTrue(all(it['classificacao_pendente'] for it in itens))
        self.assertTrue(itens[0]['motivo'].startswith('IA:'))

    def test_envia_descricao_completa_e_historico_inclusive_itens_ja_classificados(self):
        descricao = 'Aquisição de objeto ' + 'contexto ' * 30
        itens = [item(descricao), item('Consumo mensal de limpeza', 'Recorrente')]
        resposta = json.dumps({'itens': [{'id': 0, 'sugestao': 'Extraordinaria',
                                         'justificativa': 'Aquisição pontual.'}]})
        with patch.object(previsao, '_ia_disponivel', return_value=True), \
                patch.object(previsao, '_claude_chat', return_value=resposta) as chat:
            sugestoes = previsao.ia_classificar_revisar(itens, 'Teste')
        prompt = chat.call_args.args[1]
        dados, _ = json.JSONDecoder().raw_decode(prompt[prompt.index('{'):])
        self.assertEqual(dados['lancamentos_a_avaliar'][0]['descricao'], descricao)
        self.assertEqual(len(dados['historico_das_contas'][0]['lancamentos']), 2)
        self.assertEqual(sugestoes[0][0], 'Extraordinaria')

    def test_compra_marcada_recorrente_por_regra_tambem_chega_ao_avaliador(self):
        itens = [item('Aquisição de objeto durável', 'Recorrente')]
        with patch.object(previsao, '_ia_disponivel', return_value=True), \
                patch.object(previsao, '_claude_chat', return_value='{"itens": []}') as chat:
            previsao.ia_classificar_revisar(itens, 'Teste')
        self.assertTrue(chat.called)

    def test_falha_da_ia_nao_inventa_classificacao(self):
        itens = [item('Descrição ambígua')]
        with patch.object(previsao, '_ia_disponivel', return_value=False):
            sugestoes = previsao.ia_classificar_revisar(itens, 'Teste')
        previsao.aplicar_avaliacoes_ia(itens, sugestoes)
        self.assertEqual(itens[0]['cat'], 'Revisar')

    def test_resposta_parcial_reavalia_ids_omitidos_sem_perder_primeira_decisao(self):
        respostas = [json.dumps({'itens': [{'id': 0, 'sugestao': 'Extraordinaria',
                                          'justificativa': 'Pontual.'}]}),
                     json.dumps({'itens': [{'id': 1, 'sugestao': 'Recorrente',
                                          'justificativa': 'Consumo periódico.'}]})]
        with patch.object(previsao, '_ia_disponivel', return_value=True), \
                patch.object(previsao, '_claude_chat', side_effect=respostas) as chat:
            sugestoes = previsao.ia_classificar_revisar([item('Compra'), item('Consumo')], 'Teste')
        self.assertEqual(len(sugestoes), 2)
        self.assertEqual(sugestoes[0][0], 'Extraordinaria')
        self.assertIn('ainda sem avaliacao: [1]', chat.call_args.args[1])


if __name__ == '__main__':
    unittest.main()
