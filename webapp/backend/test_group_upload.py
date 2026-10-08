import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import test_mixed_upload  # instala o stub de renderização antes de importar main
import main
import parsers_group


class GroupUploadTest(unittest.TestCase):
    def test_condo21_rejects_group_xlsx_even_when_renamed_before_persistence(self):
        for selection in ({'sistemas': '["condo21"]'}, {'origem_sistema': 'condo21'}):
            for name in ('Balancete anual Berlin.xlsx', 'balanual.xls'):
                with self.subTest(selection=selection, name=name), patch.object(main.db, 'criar_sessao') as create:
                    files = {'balanual': (name, b'PK\x03\x04xlsx'),
                             'desbai': ('desbai06.xls', b'xls'), 'rec': ('rec02.xls', b'xls')}
                    response = TestClient(main.app).post('/api/sessao',
                        data={'nome_condominio': 'Berlin', 'ano_previsao': '2026', **selection}, files=files)
                    self.assertEqual(response.status_code, 400, response.text)
                    self.assertIn('selecione Group', response.json()['detail'])
                    create.assert_not_called()

    def setUp(self):
        self.client = TestClient(main.app)
        self.form = {'nome_condominio': 'Berlin', 'ano_previsao': '2027', 'origem_sistema': 'group'}
        self.files = {field: (filename, b'group bytes') for field, filename in parsers_group.FILES.items()}

    def test_upload_and_restoration_use_group_names_and_existing_database_columns(self):
        row = {}
        def save_file(sid, field, data):
            row[main.db.COLUNAS_ARQUIVOS[field]] = data
        def save_config(sid, config):
            row['config_importacao'] = config
        with patch.object(main.db, 'criar_sessao'), \
             patch.object(main.db, 'salvar_arquivo', side_effect=save_file), \
             patch.object(main.db, 'salvar_config_importacao', side_effect=save_config), \
             patch.object(parsers_group, 'load_group', return_value={}) as validate:
            response = self.client.post('/api/sessao', data=self.form, files=self.files)
        self.assertEqual(response.status_code, 200, response.text)
        validate.assert_called_once()
        with tempfile.TemporaryDirectory() as folder:
            main._restaurar_arquivos(row, folder)
            for filename in parsers_group.FILES.values():
                self.assertEqual((Path(folder) / filename).read_bytes(), b'group bytes')
            self.assertFalse((Path(folder) / 'balanual.xls').exists())
            self.assertEqual(json.loads((Path(folder) / 'importacao.json').read_text())['origem_sistema'], 'group')

    def test_rejects_corrupt_workbooks_old_extensions_and_incompatible_reports_before_persistence(self):
        cases = [self.files,
                 {**self.files, 'balanual': ('balanual.xls', b'bad')},
                 {**self.files, 'inad': ('inad.xls', b'bad')},
                 {**self.files, 'dessin': ('dessin.xls', b'bad')}]
        with patch.object(main.db, 'criar_sessao') as create:
            for files in cases:
                with self.subTest(files=list(files)):
                    response = self.client.post('/api/sessao', data=self.form, files=files)
                    self.assertEqual(response.status_code, 400, response.text)
            create.assert_not_called()

    @unittest.skipUnless(os.environ.get('GROUP_SAMPLE_DIR'), 'GROUP_SAMPLE_DIR não definido.')
    def test_real_upload_restoration_and_engine(self):
        names = {'balanual': 'Balancete anual Berlin.xlsx',
                 'desbai': 'Despesas detalhadas por classe de conta.xlsx',
                 'rec': 'Receitas_detalhadas_por_unidade_cliente_2026_10_08_14_05_17.xlsx'}
        files = {field: (name, (Path(os.environ['GROUP_SAMPLE_DIR']) / name).read_bytes())
                 for field, name in names.items()}
        row = {}
        def save_file(sid, field, data):
            row[main.db.COLUNAS_ARQUIVOS[field]] = data
        def save_config(sid, config):
            row['config_importacao'] = config
        with patch.object(main.db, 'criar_sessao'), \
             patch.object(main.db, 'salvar_arquivo', side_effect=save_file), \
             patch.object(main.db, 'salvar_config_importacao', side_effect=save_config):
            response = self.client.post('/api/sessao', data=self.form, files=files)
        self.assertEqual(response.status_code, 200, response.text)
        with tempfile.TemporaryDirectory() as folder, patch.object(main.core, '_ia_disponivel', return_value=False):
            main._restaurar_arquivos(row, folder)
            result = main.core.analisar(folder)
            self.assertEqual(result['origem_sistema'], 'group')
            self.assertEqual(result['rec']['fixo_anual'], 399544.92)
            # Cache e estado preservam a origem, os avisos e o cálculo revisável.
            cached = main._json_loads(main._json_dumps(result))
            self.assertAlmostEqual(main.core.recalcular(cached)['total_previsto'], result['total_previsto'], places=2)
            state = main._montar_estado('group-test', 'Berlin', 2027, result, True)
            self.assertEqual(state['origem_sistema'], 'group')
            self.assertEqual(state['avisos_importacao'], result['divergencias'])
            self.assertEqual(len(state['lancamentos_contas']), 399)
            import relatorio_pdf
            with patch.object(relatorio_pdf, 'HTML') as render:
                render.return_value.write_pdf.return_value = b'%PDF-test'
                self.assertEqual(relatorio_pdf.gerar_relatorio_pdf(state), b'%PDF-test')
            html = render.call_args.kwargs['string']
            self.assertIn('não comprova ausência de inadimplência', html)
            self.assertIn('meses sem movimentação: 09/2026', html.lower())
            self.assertIn('receita fixa baseada em 06/2026', html.lower())

    @unittest.skipUnless(os.environ.get('GROUP_SAMPLE_DIR'), 'GROUP_SAMPLE_DIR não definido.')
    def test_new_system_selection_with_real_group_reports(self):
        names = {'group_bal': 'Balancete anual Berlin.xlsx',
                 'group_des': 'Despesas detalhadas por classe de conta.xlsx',
                 'group_rec': 'Receitas_detalhadas_por_unidade_cliente_2026_10_08_14_05_17.xlsx'}
        files = {field: (name, (Path(os.environ['GROUP_SAMPLE_DIR']) / name).read_bytes())
                 for field, name in names.items()}
        row = {}
        def save(sid, field, content):
            row[main.db.COLUNAS_ARQUIVOS[field]] = content
        def config(sid, content):
            row['config_importacao'] = content
        with patch.object(main.db, 'criar_sessao'), patch.object(main.db, 'salvar_arquivo', side_effect=save), \
             patch.object(main.db, 'salvar_config_importacao', side_effect=config):
            response = self.client.post('/api/sessao', data={
                'nome_condominio': 'Berlin', 'ano_previsao': '2026', 'sistemas': '["group"]'}, files=files)
        self.assertEqual(response.status_code, 200, response.text)
        with tempfile.TemporaryDirectory() as folder, patch.object(main.core, '_ia_disponivel', return_value=False):
            main._restaurar_arquivos(row, folder)
            result = main.core.analisar(folder)
        self.assertEqual(result['sistemas'], ['group'])
        self.assertFalse(result['inadimplencia_apurada'])
        self.assertEqual(result['rec']['fixo_anual'], 399544.92)


if __name__ == '__main__':
    unittest.main()
