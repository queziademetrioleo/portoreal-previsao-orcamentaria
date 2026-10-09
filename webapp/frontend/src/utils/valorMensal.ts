/** Aceita reais com vírgula decimal e ponto de milhar, ou decimal simples. */
export function parseValorMensal(texto: string): number | null {
  const limpo = texto.trim().replace(/^R\$\s*/, '').replace(/\s/g, '')
  if (!/^(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,2})?$/.test(limpo)
      && !/^\d+\.\d{1,2}$/.test(limpo)) return null
  const numero = Number(limpo.includes(',') || /^\d{1,3}(?:\.\d{3})+$/.test(limpo)
    ? limpo.replace(/\./g, '').replace(',', '.') : limpo)
  return Number.isFinite(numero) && numero > 0 && numero <= 1e9 ? Math.round(numero * 100) / 100 : null
}
