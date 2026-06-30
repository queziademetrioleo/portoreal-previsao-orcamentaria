interface Explicacao {
  resumo: string
  evidencias: string[]
}

interface ItemDespesa {
  decisao: 'aprovada' | 'reprovada' | 'pendente'
  origem: string
  motivo?: string
  nota?: string
  descricao?: string
  n_meses?: number | null
  explicacao?: Explicacao
}

interface ItemInad {
  decisao: 'abater' | 'ignorar'
  critica: boolean
  meses_atraso: number
  nota?: string
  explicacao?: Explicacao
}

/** Explicação legível para decisão sobre gasto (extraordinário ou ordinário). */
export function explicarDespesa(item: ItemDespesa): Explicacao {
  if (item.explicacao?.resumo) return item.explicacao

  const base =
    item.decisao === 'aprovada'
      ? 'Retirado da previsão — identificado como gasto pontual ou extraordinário.'
      : 'Mantido na previsão — considerado parte da rotina do condomínio.'

  const evidencias: string[] = []
  if (item.origem === 'IA') evidencias.push('Classificado pela IA')
  if (item.origem === 'Regra') evidencias.push('Classificado por regra do sistema')
  if (item.n_meses != null) {
    evidencias.push(`Aparece em ${item.n_meses} de 12 meses`)
  }
  if (item.nota) evidencias.push(`Anotação: ${item.nota}`)
  if (item.motivo) evidencias.push(`Motivo: ${item.motivo}`)

  return {
    resumo: base,
    evidencias: evidencias.length ? evidencias : ['Sem evidências adicionais.'],
  }
}

/** Explicação para decisão sobre inadimplente. */
export function explicarInad(item: ItemInad): Explicacao {
  if (item.explicacao?.resumo) return item.explicacao

  const resumo =
    item.decisao === 'abater'
      ? 'Abatido da receita — atraso reduz a arrecadação provável.'
      : 'Ignorado — atraso insuficiente para afetar a projeção.'

  const evidencias = [
    item.critica ? 'Inadimplência crítica (3+ meses)' : 'Inadimplência recente',
    `${item.meses_atraso} mês(es) em atraso`,
  ]
  if (item.nota) evidencias.push(`Anotação: ${item.nota}`)

  return { resumo, evidencias }
}
