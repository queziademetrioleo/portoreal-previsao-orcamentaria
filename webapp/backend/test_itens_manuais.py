import copy
import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError
import main
import previsao
from relatorio_pdf import _consolidar_despesas_relatorio


def resultado():
    return {
        'des': {'itens': []},
        'bal': {'despesas': [{'grupo': 'Consumo', 'classe': 'Energia',
                'total': 1200, 'monthly': [100] * 12, 'n_meses': 12}],
                'receitas': [], 'total_receitas': 24000},
        'receita_anual': 24000, 'fundo_reserva_anual': 1200, 'inflacao_pct': .1,
    }


def estado():
    return {'sessao_id': 'manual', 'resumo': {}, 'extraordinarias': [],
            'revisar': [], 'inadimplencia': [], 'lancamentos_contas': []}


class ItensManuaisTest(unittest.TestCase):
    def test_receita_despesa_edicao_remocao_persistencia_e_reabertura(self):
        salvo = estado()
        def carregar(_): return copy.deepcopy(salvo)
        def persistir(_, texto): salvo.clear(); salvo.update(json.loads(texto))
        with patch.object(main, '_carregar_estado', side_effect=carregar), \
             patch.object(main, '_obter_R', side_effect=lambda _: resultado()), \
             patch.object(main, '_registrar_aprendizado_decisoes'), \
             patch.object(main.db, 'salvar_estado', side_effect=persistir):
            client = TestClient(main.app)
            itens = [{'id': 'r', 'tipo': 'receita', 'nome': 'Locação', 'valor': 50},
                     {'id': 'd', 'tipo': 'despesa', 'nome': 'Internet extra', 'valor': 100}]
            for _ in range(2):
                r = client.post('/api/sessao/manual/preview', json={'itens_manuais': itens})
                self.assertEqual(r.status_code, 200, r.text)
                self.assertEqual(r.json()['subtotal'], 2400)
                self.assertEqual(r.json()['total_previsto'], 2640)
                self.assertEqual(r.json()['cenarios']['com_fundo']['receita_anual'], 24600)
                self.assertEqual(r.json()['cenarios']['sem_fundo']['receita_anual'], 23400)
            r = client.post('/api/sessao/manual/salvar-decisoes', json={'itens_manuais': itens})
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(salvo['itens_manuais'], itens)
            self.assertEqual(salvo['resumo']['receita_mensal'], 2050)
            self.assertEqual(salvo['resumo']['total_previsto'], 2640)
            # O autosave de clientes antigos preserva inclusões manuais.
            client.post('/api/sessao/manual/salvar-decisoes', json={})
            self.assertEqual(salvo['itens_manuais'], itens)
            itens[1]['valor'] = 200
            r = client.post('/api/sessao/manual/preview', json={'itens_manuais': itens})
            self.assertEqual(r.json()['total_previsto'], 3960)
            r = client.post('/api/sessao/manual/salvar-decisoes', json={'itens_manuais': []})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(salvo['resumo']['total_previsto'], 1320)
            self.assertEqual(salvo['resumo']['receita_anual'], 24000)

    def test_pdf_recebe_itens_salvos_e_linhas_com_nome_proprio(self):
        s = estado(); s.update(nome_condominio='Teste', ano_previsao=2026)
        s['itens_manuais'] = [{'id': 'r', 'tipo': 'receita', 'nome': 'Receita extra', 'valor': 50},
                             {'id': 'd', 'tipo': 'despesa', 'nome': 'Internet extra', 'valor': 100}]
        with patch.object(main, '_carregar_estado', return_value=s), \
             patch.object(main, '_obter_R', return_value=resultado()), \
             patch.object(main, '_registrar_aprendizado_decisoes'), \
             patch.object(main.db, 'salvar_estado'), \
             patch.object(main, 'gerar_relatorio_pdf', return_value=b'%PDF-test') as render:
            r = main.relatorio_pdf('manual', main.Decisoes())
        self.assertEqual(r.body, b'%PDF-test')
        enviado = render.call_args.args[0]
        despesas = _consolidar_despesas_relatorio(enviado['linhas_contas'], enviado['resumo'])
        self.assertEqual(dict(despesas)['Internet extra'], 100)
        self.assertAlmostEqual(sum(v for _, v in despesas), 200)
        self.assertIn({'classe': 'Receita extra', 'mensal': 50}, enviado['resumo']['cenarios']['receitas_ordinarias'])

    def test_reanalise_preserva_itens_e_parcelas_informadas(self):
        import asyncio
        manual = [{'id': 'r', 'tipo': 'receita', 'nome': 'Locação', 'valor': 50}]
        row = {'nome_condominio': 'Teste', 'ano_previsao': 2027,
               'estado_json': json.dumps({'itens_manuais': manual, 'parcelas_seguro': 6})}
        with patch.object(main.db, 'carregar_sessao', return_value=row), \
             patch.object(main, '_restaurar_arquivos'), \
             patch.object(main.core, 'analisar', return_value=resultado()), \
             patch.object(main, '_aplicar_aprendizado_resultado', side_effect=lambda r: r), \
             patch.object(main.db, 'salvar_cache_analise'), \
             patch.object(main, '_montar_estado', return_value=estado()), \
             patch.object(main, '_obter_R', return_value=resultado()), \
             patch.object(main, '_salvar_estado_sync'):
            s = asyncio.run(main.reanalisar_sincrono('manual'))
        self.assertEqual(s['itens_manuais'], manual)
        self.assertEqual(s['parcelas_seguro'], 6)
        self.assertEqual(s['resumo']['receita_anual'], 24600)

    def test_pdf_pede_parcelas_quando_documento_nao_informa(self):
        R = resultado()
        R['bal']['despesas'][0].update(grupo='Diversas', classe='Seguro Incêndio')
        R['des']['itens'] = [{'grupo': 'Diversas', 'classe': 'Seguro Incêndio',
                             'data': '2026-09-10', 'valor_pago': 200, 'cat': 'Recorrente'}]
        s = estado(); s.update(nome_condominio='Teste', ano_previsao=2027)
        with patch.object(main, '_carregar_estado', return_value=s), \
             patch.object(main, '_obter_R', return_value=R), \
             patch.object(main, '_registrar_aprendizado_decisoes'), \
             patch.object(main.db, 'salvar_estado'), \
             patch.object(main, 'gerar_relatorio_pdf', return_value=b'%PDF-test') as render:
            client = TestClient(main.app)
            response = client.post('/api/sessao/manual/relatorio-pdf', json={})
            self.assertEqual(response.status_code, 400)
            render.assert_not_called()
            response = client.post('/api/sessao/manual/relatorio-pdf', json={'parcelas_seguro': 6})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(s['resumo']['subtotal'], 1200)

    def test_validacao_servidor(self):
        for campo, valor in [('nome', '  '), ('valor', 0), ('valor', -1),
                              ('valor', float('inf')), ('valor', 1.001), ('tipo', 'outro')]:
            with self.subTest(campo=campo, valor=valor), self.assertRaises(ValidationError):
                main.ItemManual(**{**{'id': '1', 'nome': 'Teste', 'tipo': 'receita', 'valor': 10}, campo: valor})
        with self.assertRaises(ValidationError):
            main.Decisoes(itens_manuais=[{'id': '1', 'nome': 'T', 'tipo': 'receita', 'valor': 1}] * 2)


class UltimoPagamentoTest(unittest.TestCase):
    def projetar(self, classe, itens, parcelas=None):
        R = resultado()
        R['bal']['despesas'][0].update(grupo='Contratos', classe=classe)
        R['des']['itens'] = [{'grupo': 'Contratos', 'classe': classe, 'cat': 'Recorrente', **i} for i in itens]
        R['parcelas_seguro'] = parcelas
        return previsao.recalcular(R)

    def test_administracao_usa_ultimo_pago_por_data_nao_media(self):
        r = self.projetar('CONTRATO PRESTAÇÃO SERVIÇO ADMINISTRAÇÃO', [
            {'data': '2026-09-10', 'valor_pago': 150},
            {'data': '2026-08-10', 'valor_pago': 100},
            {'data': '2026-09-15', 'valor_pago': 0}])
        self.assertEqual(r['subtotal'], 1800)
        self.assertAlmostEqual(r['total_previsto'], 1980)

    def test_seguro_ultima_parcela_multiplica_total_nao_numero_pago(self):
        r = self.projetar('SEGURO CONDOMINIAL OBRIGATÓRIO', [
            {'data': '2026-09-10', 'valor_pago': 846.62, 'parcela': '02/06'},
            {'data': '2025-10-10', 'valor_pago': 700, 'parcela': '06/06'}])
        self.assertEqual(r['subtotal'], 5079.72)
        self.assertAlmostEqual(r['total_previsto'], 5587.692)

    def test_seguro_legado_e_atual_nao_duplicam_projecao(self):
        r = resultado()
        antigo = {'grupo': 'Diversas', 'classe': 'Seguro Incêndio', 'total': 1200, 'monthly': [100]*12, 'n_meses': 12}
        atual = {**antigo, 'classe': 'Seguro Condominial Obrigatório'}
        r['bal']['despesas'] = [antigo, atual]
        r['des']['itens'] = [
            {'grupo': 'Diversas', 'classe': antigo['classe'], 'data': '2026-05-01', 'valor_pago': 100, 'cat': 'Recorrente'},
            {'grupo': 'Diversas', 'classe': atual['classe'], 'data': '2026-09-01', 'valor_pago': 200, 'parcela': '02/06', 'cat': 'Recorrente'}]
        r = previsao.recalcular(r)
        self.assertEqual(r['subtotal'], 1200)
        self.assertEqual(r['linhas'][0]['final'], 0)
        self.assertEqual(r['linhas'][1]['final'], 1200)

    def test_decimo_terceiro_nao_multiplica_por_doze(self):
        r = self.projetar('13º Taxa de Administração', [{'data': '2026-09-10', 'valor_pago': 200}])
        self.assertEqual(r['subtotal'], 1200)

    def test_seguro_renovado_usa_ultima_parcela_do_novo_ciclo(self):
        r = self.projetar('Seguro Incêndio', [
            {'data': '2026-02-12', 'valor_pago': 544.31, 'descricao': 'Parcela 6/6'},
            {'data': '2026-09-18', 'valor_pago': 652.90, 'descricao': 'Parcela 02/06'},
            {'data': '2026-08-20', 'valor_pago': 652.90, 'descricao': 'Parcela 01/06'}])
        self.assertEqual(r['subtotal'], 3917.40)
        self.assertEqual(r['subtotal'] / 12, 326.45)

    def test_seguro_quantidade_informada(self):
        r = self.projetar('Seguro Obrigatório', [{'data': '2026-09-10', 'valor_pago': 200}], parcelas=5)
        self.assertEqual(r['subtotal'], 1000)

    def test_seguro_parcela_na_descricao(self):
        r = self.projetar('Seguro Incêndio', [{'data': '2026-09-10', 'valor_pago': 200, 'descricao': 'Parcela 2/8'}])
        self.assertEqual(r['subtotal'], 1600)

    def test_seguro_vida_nao_muda_regra(self):
        r = self.projetar('Seguro de Vida', [{'data': '2026-09-10', 'valor_pago': 200, 'parcela': '2/8'}])
        self.assertEqual(r['subtotal'], 1200)

    def test_alma_total_inclui_todas_contas_sem_somar_legado(self):
        r = resultado()
        r['rec'] = {'sistema': 'alma', 'total_lancado_mes': 36928.38,
                    'fundo_reserva_anual': 18351.24, 'por_classe': {
                        'TAXA DE CONDOMÍNIO': {'lancado': 31410.78},
                        'FUNDO DE RESERVA': {'lancado': 1529.27},
                        'DESCONTO': {'lancado': -46.55},
                        'JUROS': {'lancado': 626.09},
                        'OUTRAS': {'lancado': 3408.79}}}
        r['bal']['receitas'] = [{'classe': 'Gás', 'total': 12000}, {'classe': 'Aluguel', 'total': 12000, 'monthly': [1000]*12}]
        r = previsao.recalcular(r)
        self.assertEqual(r['receita_anual'], 443140.56)
        self.assertEqual(r['cenarios']['receitas_nao_ordinarias'], [])
        self.assertAlmostEqual(sum(i['mensal'] for i in r['cenarios']['receitas_ordinarias']) + 1529.27, 36928.38)


if __name__ == '__main__':
    unittest.main()
