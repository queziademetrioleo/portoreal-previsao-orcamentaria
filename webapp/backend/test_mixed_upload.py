import json
from pathlib import Path
import tempfile
import sys
import types
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
# Estes testes exercitam upload e restauração, sem renderizar PDF.
weasyprint = types.ModuleType('weasyprint')
weasyprint.HTML = object
sys.modules.setdefault('weasyprint', weasyprint)
import main
from banco_falso import BancoFalso


class MixedUploadTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.files = {
            'balanual': ('balanual.xls', b'condo'),
            'desbai': ('desbai06.xls', b'condo'),
            'rec': ('rec02.xls', b'condo'),
            'alma_bal': ('demonstrativo.pdf', b'alma balance'),
            'alma_fin': ('FIN.xlsx', b'alma payments'),
            'alma_rec': ('receber.pdf', b'alma receivables'),
        }
        self.form = {'nome_condominio': 'Teste', 'ano_previsao': '2027',
                     'origem_sistema': 'misto', 'sem_inadimplencia_alma': 'true'}

    def test_mixed_upload_persists_and_restores_all_files_and_period(self):
        self.form.update(periodo_inicio='2026-07', periodo_fim='2026-08')
        with BancoFalso().ativo() as banco:
            response = self.client.post('/api/sessao', data=self.form, files=self.files)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(banco.etapa, 'validado')
        # Com o Alma, balanual e REC do Condo21 não entram na análise.
        self.assertIsNone(banco.row['arquivo_balanual'])
        with tempfile.TemporaryDirectory() as folder:
            main._restaurar_arquivos(banco.row, folder)
            self.assertEqual((Path(folder) / 'alma_fin.xlsx').read_bytes(), b'alma payments')
            self.assertFalse((Path(folder) / 'plano_alma.xlsx').exists())
            self.assertEqual(json.loads((Path(folder) / 'importacao.json').read_text())['periodo_inicio'], '2026-07')

    def test_missing_alma_or_unconfirmed_absence_is_rejected_and_kept_for_investigation(self):
        cases = [(dict(self.form), {k: v for k, v in self.files.items() if k != 'alma_fin'}),
                 ({**self.form, 'sem_inadimplencia_alma': 'false'}, self.files),
                 (self.form, {**self.files, 'alma_inad': ('inad.pdf', b'inad')}),
                 ({**self.form, 'periodo_inicio': '2026-08', 'periodo_fim': '2026-07'}, self.files)]
        for form, files in cases:
            with self.subTest(form=form, fields=list(files)), BancoFalso().ativo() as banco:
                response = self.client.post('/api/sessao', data=form, files=files)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(banco.etapa, 'erro_validacao')
                self.assertIn(f"Protocolo {banco.row['id']}", response.json()['detail'])
                self.assertEqual(banco.row['arquivo_alma_bal'], b'alma balance')

    def test_condo_only_request_remains_compatible(self):
        files = {k: v for k, v in self.files.items() if not k.startswith('alma')}
        with BancoFalso().ativo():
            response = self.client.post('/api/sessao', data={
                'nome_condominio': 'Teste', 'ano_previsao': '2027'}, files=files)
        self.assertEqual(response.status_code, 200)

    def test_health_and_empty_upload_validation(self):
        self.assertEqual(self.client.get('/api/health').status_code, 200)
        with BancoFalso().ativo() as banco:
            response = self.client.post('/api/sessao', data=self.form,
                files={**self.files, 'alma_fin': ('FIN.xlsx', b'')})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(banco.etapa, 'erro_validacao')
        self.assertIn('vazio', banco.row['erro'])
        self.assertNotIn('arquivo_alma_fin', banco.row)

    def test_four_alma_reports_are_accepted_without_chart_upload(self):
        files = {**self.files, 'alma_inad': ('inad.pdf', b'inad')}
        form = {**self.form, 'sem_inadimplencia_alma': 'false'}
        with BancoFalso().ativo():
            response = self.client.post('/api/sessao', data=form, files=files)
        self.assertEqual(response.status_code, 200, response.text)

    def test_analysis_refuses_rejected_upload_and_logs_engine_errors(self):
        with patch.object(main.db, 'carregar_sessao', return_value={'etapa': 'erro_validacao'}):
            self.assertEqual(self.client.get('/api/sessao/abc/analisar').status_code, 409)
        row = {'nome_condominio': 'Teste', 'ano_previsao': 2027, 'etapa': 'validado'}
        with patch.object(main.db, 'carregar_sessao', return_value=row), \
             patch.object(main, '_restaurar_arquivos'), \
             patch.object(main.core, 'analisar', side_effect=ValueError('Demonstrativo Almah: período não identificado.')), \
             patch.object(main.db, 'marcar_etapa') as etapa:
            response = self.client.get('/api/sessao/abc/analisar')
        self.assertIn('período não identificado', response.text)
        self.assertEqual(etapa.call_args.args[:2], ('abc', 'erro_analise'))
        self.assertIn('período não identificado', etapa.call_args.args[2])

    def test_legacy_session_chart_is_not_restored_as_an_upload(self):
        with tempfile.TemporaryDirectory() as folder:
            main._restaurar_arquivos({'arquivo_plano_alma': b'legacy chart'}, folder)
            self.assertFalse((Path(folder) / 'plano_alma.xlsx').exists())

    def test_unmapped_classes_are_not_automatically_resolved_by_learning(self):
        pending = {'classificacao_pendente': True, 'cat': 'Revisar'}
        result = {'des': {'itens': [pending]}}
        with patch.object(main.db, 'listar_aprendizados', return_value=[]), \
             patch.object(main.aprendizado, 'aplicar_memorias', return_value=0) as apply:
            main._aplicar_aprendizado_resultado(result)
        apply.assert_called_once_with([], [])
