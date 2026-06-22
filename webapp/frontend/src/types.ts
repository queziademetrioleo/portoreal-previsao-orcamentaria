export interface ItemRevisao {
  id: number
  grupo: string
  classe: string
  data: string
  descricao: string
  valor: number
  motivo: string
  n_meses: number | null
  origem: 'IA' | 'Regra'
  decisao: 'aprovada' | 'reprovada' | 'pendente'
}

export interface ItemInad {
  id: number
  unidade: string
  classe: string
  mes_ref: string
  vencimento: string
  valor: number
  meses_atraso: number
  critica: boolean
  decisao: 'abater' | 'ignorar'
}

export interface LinhaConta {
  grupo: string
  classe: string
  base: number
  deducao: number
  final: number
  regra: string
  n_meses: number
}

export interface LinhaPrevisaoFinal {
  row: number
  label: string
  anual: number | string | null
  rateio: number | string | null
  mensal: number | string | null
}

export interface Resumo {
  base_total: number
  desconsideracoes: number
  prov_laudo: number
  prov_incendio: number
  subtotal: number
  inflacao: number
  total_previsto: number
  receita_anual: number
  receita_mensal: number
  periodo: [string, string]
  impacto_receita_mensal?: number
}

export interface Sessao {
  sessao_id: string
  nome_condominio: string
  ano_previsao: number
  criado_em: string
  modelo_ia: string
  ia_ativa: boolean
  resumo: Resumo
  extraordinarias: ItemRevisao[]
  revisar: ItemRevisao[]
  inadimplencia: ItemInad[]
  inad_meta: { total: number; critica: number; data_base: string } | null
  linhas_contas: LinhaConta[]
  previsao_final?: LinhaPrevisaoFinal[]
  status: 'em_revisao' | 'gerado'
}
