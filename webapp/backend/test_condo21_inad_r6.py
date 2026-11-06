"""Feedback José 04/11/2026 (Prainha, Condo21).

- Inadimplência: dívida antiga com os meses recentes pagos (acordo) não entra.
- R6: mês sem pagamento dentro dos 3 últimos conta como zero (mensalidade paga em dobro no mês seguinte).
"""
import datetime
import unittest
from collections import defaultdict

import previsao as core


def _unidades(meses_por_unidade):
    meses, itens = defaultdict(set), defaultdict(list)
    for u, lista in meses_por_unidade.items():
        for m in lista:
            meses[u].add(m)
            itens[u].append({'mes_ref': m, 'classe': 'Tx. Condomínio', 'valor': 764.03})
    return meses, itens


def _seq(inicio_mes, inicio_ano, n):
    out, m, a = [], inicio_mes, inicio_ano
    for _ in range(n):
        out.append(f'{m:02d}/{a}')
        m, a = (m + 1, a) if m < 12 else (1, a + 1)
    return out


class InadimplenciaCondo21(unittest.TestCase):
    base = datetime.date(2026, 11, 4)

    def test_divida_antiga_com_meses_recentes_pagos_nao_entra(self):
        meses, itens = _unidades({'4-201': _seq(10, 2015, 115)})  # 10/2015 → 04/2025
        self.assertEqual(core._unidades_criticas_condo21(meses, itens, self.base), {})

    def test_devedor_atual_com_3_meses_seguidos_entra(self):
        meses, itens = _unidades({'4-101': _seq(3, 2008, 2) + _seq(8, 2026, 3)})  # ago–out/2026
        crit = core._unidades_criticas_condo21(meses, itens, self.base)
        self.assertEqual(list(crit), ['4-101'])
        self.assertEqual(crit['4-101']['meses_consecutivos'], 3)

    def test_sequencia_antiga_nao_conta_se_a_atual_tem_menos_de_3(self):
        meses, itens = _unidades({'2-303': _seq(1, 2024, 6) + ['10/2026']})
        self.assertEqual(core._unidades_criticas_condo21(meses, itens, self.base), {})

    def test_virada_de_ano(self):
        meses, itens = _unidades({'1-101': _seq(11, 2025, 3)})  # nov, dez, jan
        self.assertIn('1-101', core._unidades_criticas_condo21(meses, itens, datetime.date(2026, 2, 3)))


class R6ParcelaVigente(unittest.TestCase):
    """José 05/11/2026: parcela vigente = último pagamento ÷ meses que ele cobre."""

    def test_parcela_atrasada_paga_em_dobro(self):
        # Contrato Serasa Prainha: set 0, out 230,48 (2 parcelas) → 115,24 (conta do José)
        serie = [103.71, 113.54, 113.54, 113.54, 113.54, 0, 0, 351.25, 116.19, 113.54, 0, 230.48]
        self.assertAlmostEqual(core._media_ultimos_3_meses(serie), 115.24, places=2)

    def test_tres_parcelas_juntas(self):
        self.assertAlmostEqual(core._media_ultimos_3_meses([113.54, 0, 0, 351.25]), 117.08, places=2)

    def test_reajuste_no_ultimo_mes_vale_a_parcela_nova(self):
        # Taxa de Administração Prainha: 2.875 → 3.070 em out (média de 3 meses dava 2.940)
        self.assertAlmostEqual(core._media_ultimos_3_meses([2875.0] * 11 + [3070.0]), 3070.0)

    def test_mes_ainda_sem_pagamento_no_fim_fica_fora(self):
        self.assertAlmostEqual(core._media_ultimos_3_meses([100, 100, 120, 0]), 120)

    def test_pagamento_unico_no_ano_nao_e_dividido(self):
        self.assertAlmostEqual(core._media_ultimos_3_meses([0, 0, 0, 450]), 450)

    def test_sem_pagamento(self):
        self.assertEqual(core._media_ultimos_3_meses([0, 0]), 0.0)


class InadimplenciaCondo21FundoNaTela(unittest.TestCase):
    """José 05/11/2026: unidade inadimplente abate a taxa E o fundo de reserva do mês."""

    def test_taxa_e_fundo_do_ultimo_mes(self):
        import main
        itens = []
        for m in ('08/2026', '09/2026', '10/2026'):
            itens += [{'unidade': '4-101', 'classe': 'Tx. Condomínio', 'mes_ref': m, 'vencimento': None,
                       'valor': 764.03, 'meses_atraso': 3, 'critica': True},
                      {'unidade': '4-101', 'classe': 'Fundo Reserva', 'mes_ref': m, 'vencimento': None,
                       'valor': 76.40, 'meses_atraso': 3, 'critica': True},
                      {'unidade': '4-101', 'classe': 'Taxa Extra', 'mes_ref': m, 'vencimento': None,
                       'valor': 260.0, 'meses_atraso': 3, 'critica': True}]
        estado = {'inadimplencia': main._itens_inadimplencia_tela({'itens': itens})}
        self.assertEqual(len(estado['inadimplencia']), 1)
        item = estado['inadimplencia'][0]
        self.assertEqual(item['partes'], {'taxa': 764.03, 'fundo': 76.40})
        self.assertAlmostEqual(item['valor'], 840.43)
        self.assertEqual(main._impacto_partes(estado), {'taxa': 764.03, 'fundo': 76.4})

    def test_montar_estado_com_inadimplencia(self):
        """Reanálise da Prainha quebrou em prod (NameError 'inad', 05/11/2026)."""
        import main
        itens = [{'unidade': '4-101', 'classe': c, 'mes_ref': m, 'vencimento': None, 'valor': v,
                  'meses_atraso': 3, 'critica': True}
                 for m in ('08/2026', '09/2026', '10/2026')
                 for c, v in (('Tx. Condomínio', 764.03), ('Fundo Reserva', 76.40))]
        R = {'des': {'itens': []}, 'linhas': [], 'bal': {}, 'base_total': 0, 'desconsideracoes': 0,
             'subtotal': 0, 'total_previsto': 0,
             'inad': {'total': 1000, 'critica': 840.43, 'data_base': '2026-11-04', 'itens': itens}}
        estado = main._montar_estado('t', 'Teste', 2027, R, True)
        self.assertEqual(estado['inadimplencia'][0]['partes'], {'taxa': 764.03, 'fundo': 76.4})
        self.assertEqual(estado['inad_meta']['critica'], 840.43)


class ValorEditadoAbaVelha(unittest.TestCase):
    """Prainha 05/11/2026: aba aberta antes da reanálise gravou 764,03 por cima de 840,43."""

    def item(self):
        return {'id': 0, 'valor': 840.43, 'decisao': 'abater', 'partes': {'taxa': 764.03, 'fundo': 76.4}}

    def test_valor_de_tela_com_versao_velha_e_ignorado(self):
        import main
        item = self.item()
        main._aplicar_decisao_editavel(item, 'abater', (764.03, 764.03), None, ('abater', 'ignorar'))
        self.assertNotIn('valor_editado', item)

    def test_valor_igual_ao_original_nao_vira_edicao(self):
        import main
        item = {**self.item(), 'valor_editado': 764.03}
        main._aplicar_decisao_editavel(item, 'abater', (840.43, 840.43), None, ('abater', 'ignorar'))
        self.assertNotIn('valor_editado', item)

    def test_edicao_de_verdade_e_gravada(self):
        import main
        item = self.item()
        main._aplicar_decisao_editavel(item, 'abater', (800.0, 840.43), None, ('abater', 'ignorar'))
        self.assertEqual(item['valor_editado'], 800.0)


if __name__ == '__main__':
    unittest.main()
