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

// Traduz o motivo tecnico (classify()/outliers/IA, vindo do backend) em
// motivos curtos e objetivos. Mesma logica de main.py:_motivos_legiveis,
// mantida em espelho para quando o backend ainda nao populou `explicacao`.
const MOTIVOS_PADROES: [RegExp, string][] = [
  [/obras?|benfeitoria/i, 'é uma obra ou reforma'],
  [/rescis|indeniza/i, 'é rescisão ou indenização de funcionário'],
  [/reparo|conserto/i, 'foi um conserto pontual, fora da rotina'],
  [/outlier|\bmad\b/i, 'o valor ficou bem acima do normal para essa conta'],
  [/valor alto/i, 'o valor ficou bem mais alto que o de costume'],
  [/capital/i, 'a descrição indica gasto de obra/capital'],
  [/sem regra explicita/i, 'não segue um padrão claro nas contas do condomínio'],
  [/periodic|ambigu/i, 'pode ou não se repetir — fica em revisão'],
  [/recorrente/i, 'é um gasto do dia a dia do condomínio'],
]

function motivosLegiveis(motivo: string | undefined, nMeses: number | null | undefined): string[] {
  const motivos: string[] = []
  const texto = motivo ?? ''
  if (texto.startsWith('IA:')) {
    const textoIa = texto.slice(3).trim()
    if (textoIa) motivos.push(textoIa.replace(/\.$/, ''))
  } else {
    const achado = MOTIVOS_PADROES.find(([padrao]) => padrao.test(texto))
    if (achado) motivos.push(achado[1])
  }
  if (nMeses != null && nMeses <= 2 && !motivos.some((m) => m.includes('rotina') || m.includes('repetir'))) {
    motivos.push(`só apareceu em ${nMeses} de 12 meses`)
  }
  if (motivos.length === 0) {
    motivos.push('identificado pela análise como fora do padrão de gasto recorrente')
  }
  return motivos
}

/** Explicação legível para decisão sobre gasto (extraordinário ou ordinário). */
export function explicarDespesa(item: ItemDespesa): Explicacao {
  if (item.explicacao?.resumo) return item.explicacao

  const motivos = motivosLegiveis(item.motivo, item.n_meses)
  const rotulo = item.decisao === 'aprovada' ? 'Removido' : 'Mantido'
  const base = `${rotulo} por motivo${motivos.length > 1 ? 's' : ''} de: ${motivos.join(', ')}.`

  const evidencias: string[] = []
  if (item.origem === 'IA') evidencias.push('Classificado pela IA')
  if (item.origem === 'Regra') evidencias.push('Classificado por regra do sistema')
  if (item.n_meses != null) {
    evidencias.push(`Aparece em ${item.n_meses} de 12 meses`)
  }
  if (item.nota) evidencias.push(`Anotação: ${item.nota}`)
  if (item.motivo) evidencias.push(`Motivo técnico: ${item.motivo}`)

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
      ? `Abatido da receita por motivo de: ${item.meses_atraso} mês(es) consecutivos em atraso, o que reduz o quanto o condomínio deve efetivamente receber.`
      : `Ignorado por motivo de: atraso de ${item.meses_atraso} mês(es), abaixo do limite considerado crítico (3 meses seguidos).`

  const evidencias = [
    item.critica ? 'Inadimplência crítica (3+ meses)' : 'Inadimplência recente',
    `${item.meses_atraso} mês(es) em atraso`,
  ]
  if (item.nota) evidencias.push(`Anotação: ${item.nota}`)

  return { resumo, evidencias }
}
