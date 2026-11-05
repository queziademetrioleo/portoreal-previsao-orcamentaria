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


class R6MediaUltimos3Meses(unittest.TestCase):
    def test_mes_zero_com_parcela_dobrada_no_seguinte(self):
        # Contrato Serasa Prainha: jul 116,19, ago 113,54, set 0, out 230,48
        media = core._media_ultimos_3_meses([113.54, 0, 115.92 + 117.10 + 118.23, 116.19, 113.54, 0, 230.48])
        self.assertAlmostEqual(media, (113.54 + 0 + 230.48) / 3, places=2)
        self.assertAlmostEqual(round(media * 12, 2), 1376.08, places=2)

    def test_mes_ainda_sem_pagamento_no_fim_fica_fora(self):
        self.assertAlmostEqual(core._media_ultimos_3_meses([100, 100, 100, 0]), 100)

    def test_sem_pagamento(self):
        self.assertEqual(core._media_ultimos_3_meses([0, 0]), 0.0)


if __name__ == '__main__':
    unittest.main()
