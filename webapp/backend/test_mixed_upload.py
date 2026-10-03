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
            'plano_alma': ('plano.xlsx', b'chart'),
        }
        self.form = {'nome_condominio': 'Teste', 'ano_previsao': '2027',
                     'origem_sistema': 'misto', 'sem_inadimplencia_alma': 'true'}

    def test_mixed_upload_persists_and_restores_all_files_and_period(self):
        self.form.update(periodo_inicio='2026-07', periodo_fim='2026-08')
        row = {}
        def save_file(sid, field, content):
            row[main.db.COLUNAS_ARQUIVOS[field]] = content
        def save_config(sid, config):
            row['config_importacao'] = config
        with patch.object(main.db, 'criar_sessao'), \
             patch.object(main.db, 'salvar_arquivo', side_effect=save_file), \
             patch.object(main.db, 'salvar_config_importacao', side_effect=save_config):
            response = self.client.post('/api/sessao', data=self.form, files=self.files)
        self.assertEqual(response.status_code, 200, response.text)
        with tempfile.TemporaryDirectory() as folder:
            main._restaurar_arquivos(row, folder)
            self.assertEqual((Path(folder) / 'alma_fin.xlsx').read_bytes(), b'alma payments')
            self.assertEqual((Path(folder) / 'plano_alma.xlsx').read_bytes(), b'chart')
            self.assertEqual(json.loads((Path(folder) / 'importacao.json').read_text())['periodo_inicio'], '2026-07')

    def test_missing_alma_or_unconfirmed_absence_is_rejected_before_persistence(self):
        cases = [(dict(self.form), {k: v for k, v in self.files.items() if k != 'alma_fin'}),
                 ({**self.form, 'sem_inadimplencia_alma': 'false'}, self.files),
                 (self.form, {**self.files, 'alma_inad': ('inad.pdf', b'inad')}),
                 ({**self.form, 'periodo_inicio': '2026-08', 'periodo_fim': '2026-07'}, self.files)]
        with patch.object(main.db, 'criar_sessao') as create:
            for form, files in cases:
                with self.subTest(form=form, fields=list(files)):
                    self.assertEqual(self.client.post('/api/sessao', data=form, files=files).status_code, 400)
            create.assert_not_called()

    def test_condo_only_request_remains_compatible(self):
        files = {k: v for k, v in self.files.items() if not k.startswith('alma') and k != 'plano_alma'}
        with patch.object(main.db, 'criar_sessao'), patch.object(main.db, 'salvar_arquivo'), \
             patch.object(main.db, 'salvar_config_importacao'):
            response = self.client.post('/api/sessao', data={
                'nome_condominio': 'Teste', 'ano_previsao': '2027'}, files=files)
        self.assertEqual(response.status_code, 200)

    def test_health_and_empty_upload_validation(self):
        self.assertEqual(self.client.get('/api/health').status_code, 200)
        with patch.object(main.db, 'criar_sessao') as create:
            response = self.client.post('/api/sessao', data=self.form,
                files={**self.files, 'alma_fin': ('FIN.xlsx', b'')})
        self.assertEqual(response.status_code, 400)
        create.assert_not_called()

    def test_unmapped_classes_are_not_automatically_resolved_by_learning(self):
        pending = {'classificacao_pendente': True, 'cat': 'Revisar'}
        result = {'des': {'itens': [pending]}}
        with patch.object(main.db, 'listar_aprendizados', return_value=[]), \
             patch.object(main.aprendizado, 'aplicar_memorias', return_value=0) as apply:
            main._aplicar_aprendizado_resultado(result)
        apply.assert_called_once_with([], [])
