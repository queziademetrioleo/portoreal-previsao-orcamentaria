export interface SaudeFinanceira {
  score: number
  label: string
  classe: 'success' | 'warn' | 'danger'
}

/**
 * Calcula nota de saúde financeira (0–100) baseada na margem entre
 * receita líquida e total previsto, penalizada por inadimplência e pressão.
 */
export function scoreSaude(
  receitaAnual: number,
  totalPrevisto: number,
  impactoInadAnual: number,
): SaudeFinanceira {
  if (receitaAnual <= 0) {
    return { score: 0, label: 'Sem receita', classe: 'danger' }
  }

  const saldoAjustado = receitaAnual - impactoInadAnual - totalPrevisto
  const margem = saldoAjustado / receitaAnual
  const inadPct = impactoInadAnual / receitaAnual
  const pressao = totalPrevisto / receitaAnual

  let score =
    72 + margem * 120 - inadPct * 160 - Math.max(0, pressao - 1) * 80
  score = Math.round(Math.max(0, Math.min(100, score)))

  if (score >= 75) return { score, label: 'Confortável', classe: 'success' }
  if (score >= 45) return { score, label: 'Atenção', classe: 'warn' }
  return { score, label: 'Risco de déficit', classe: 'danger' }
}
