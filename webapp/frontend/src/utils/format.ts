/**
 * Formatação de valores monetários — unificada para todo o frontend.
 */

/** Número com 2 casas decimais, separador de milhar pt-BR */
export function fmt(v: number): string {
  return v.toLocaleString('pt-BR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

/** Valor como string monetária: "R$ 1.234,56" */
export function money(v: unknown): string {
  return typeof v === 'number' ? `R$ ${fmt(v)}` : '—'
}

/** Valor com sinal explícito: "-R$ 500,00" */
export function signedMoney(v: number): string {
  return `${v < 0 ? '-' : ''}R$ ${fmt(Math.abs(v))}`
}

/** Apelido curto — mesmo que money */
export const brl = money

/** Porcentagem (0–100) a partir de parte/total */
export function pct(part: number, total: number): number {
  return total > 0 ? Math.max(0, Math.min(100, (part / total) * 100)) : 0
}
