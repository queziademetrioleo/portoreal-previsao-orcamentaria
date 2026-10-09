import unittest
from unittest.mock import patch

import test_mixed_upload
import main


class PdfExportTest(unittest.TestCase):
    def test_export_uses_reviewed_analysis_without_calling_external_ai(self):
        state = {'nome_condominio': 'Berlin', 'ano_previsao': 2026,
                 'resumo': {}, 'inadimplencia': [], 'revisar': [],
                 'extraordinarias': [{'id': 1, 'decisao': 'aprovada', 'motivo': 'IA: conserto pontual',
                                       'n_meses': 1, 'valor': 100}], 'lancamentos_contas': []}
        result = {'subtotal': 900, 'total_previsto': 990, 'desconsideracoes': 100,
                  'prov_laudo': 0, 'prov_incendio': 0, 'linhas': []}
        with patch.object(main, '_carregar_estado', return_value=state), \
             patch.object(main, '_registrar_aprendizado_decisoes'), \
             patch.object(main, '_aplicar_decisoes'), \
             patch.object(main, '_recalcular_com_decisoes', return_value=(result, 0)), \
             patch.object(main.db, 'salvar_estado'), \
             patch.object(main.core, '_ia_disponivel', return_value=True), \
             patch.object(main.core, '_claude_chat', side_effect=AssertionError('PDF não deve chamar IA')) as ai, \
             patch.object(main, 'gerar_relatorio_pdf', return_value=b'%PDF-test') as render:
            response = main.relatorio_pdf('test', main.Decisoes())
        self.assertEqual(response.body, b'%PDF-test')
        ai.assert_not_called()
        self.assertEqual(render.call_args.args[0]['resumo']['total_previsto'], 990)
        self.assertIn('conserto pontual', state['extraordinarias'][0]['explicacao']['resumo'])
