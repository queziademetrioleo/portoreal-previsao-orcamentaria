import type { FluxoMensal, LinhaConta } from '../types'
import { money } from './format'

interface ParamsInsights {
  saldoAjustado: number
  receitaAtual: number
  despesaAtual: number
  impactoInadMensal: number
  removido: number
  mantido: number
  grupos: { label: string; value: number }[]
  linhas: LinhaConta[]
  fluxoMensal: FluxoMensal[]
}

/** Gera até 7 frases curtas explicando o resultado para leigos. */
export function gerarInsights(p: ParamsInsights): string[] {
  const out: string[] = []

  if (p.saldoAjustado < 0) {
    out.push(
      'A previsão indica déficit: a receita líquida estimada não cobre o total de despesas previstas.',
    )
  } else {
    out.push(
      'A receita líquida estimada cobre o total previsto de despesas no cenário atual.',
    )
  }

  if (p.impactoInadMensal > 0) {
    out.push(
      `A inadimplência reduz a receita disponível em ${money(p.impactoInadMensal)} por mês.`,
    )
  }

  const margem =
    p.receitaAtual > 0 ? p.saldoAjustado / p.receitaAtual : 0
  out.push(
    `Margem ajustada: ${(margem * 100).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}% da receita.`,
  )

  if (p.removido > 0) {
    out.push(
      `${p.removido} gasto(s) extraordinário(s) foram retirados da previsão.`,
    )
  }

  const maiorDeducao = [...p.linhas]
    .filter((l) => Math.abs(l.deducao) > 0.005)
    .sort((a, b) => Math.abs(b.deducao) - Math.abs(a.deducao))[0]
  if (maiorDeducao) {
    out.push(
      `Maior ajuste: ${maiorDeducao.classe}, com ${money(Math.abs(maiorDeducao.deducao))} deduzidos.`,
    )
  }

  const maiorGrupo = p.grupos[0]
  if (maiorGrupo) {
    out.push(
      `Maior despesa: ${maiorGrupo.label} (${money(maiorGrupo.value / 12)}/mês).`,
    )
  }

  if (p.mantido > 0) {
    out.push(
      `${p.mantido} gasto(s) foram mantidos para não subestimar despesas recorrentes.`,
    )
  }

  return out.slice(0, 7)
}
