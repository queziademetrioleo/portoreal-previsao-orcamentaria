import { type Sessao } from './types'

export const BASE = import.meta.env.DEV ? 'http://localhost:8000' : ''

export interface DecisaoEditavel {
  decisao: string
  valor?: number
  nota?: string
}

export interface PayloadDecisoes {
  extraordinarias: Record<string, DecisaoEditavel>
  revisar: Record<string, DecisaoEditavel>
  inadimplencia: Record<string, DecisaoEditavel>
}

export async function criarSessao(form: {
  nome: string
  ano: number
  balanual: File
  desbai: File
  dessin?: File | null
  inad?: File | null
}): Promise<Sessao> {
  const fd = new FormData()
  fd.append('nome_condominio', form.nome)
  fd.append('ano_previsao', String(form.ano))
  fd.append('balanual', form.balanual)
  fd.append('desbai', form.desbai)
  if (form.dessin) fd.append('dessin', form.dessin)
  if (form.inad) fd.append('inad', form.inad)
  const r = await fetch(`${BASE}/api/sessao`, { method: 'POST', body: fd })
  if (!r.ok) throw new Error((await r.json()).detail ?? `Erro ${r.status}`)
  return r.json()
}

export async function gerarDocumento(
  sid: string,
  decisoes: PayloadDecisoes,
): Promise<{ ok: boolean; subtotal: number; total_previsto: number; impacto_receita_mensal: number; download: string }> {
  const r = await fetch(`${BASE}/api/sessao/${sid}/gerar`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(decisoes),
  })
  if (!r.ok) throw new Error((await r.json()).detail ?? `Erro ${r.status}`)
  return r.json()
}

export async function previewDocumento(
  sid: string,
  decisoes: PayloadDecisoes,
): Promise<{ subtotal: number; total_previsto: number; impacto_receita_mensal: number }> {
  const r = await fetch(`${BASE}/api/sessao/${sid}/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(decisoes),
  })
  if (!r.ok) throw new Error((await r.json()).detail ?? `Erro ${r.status}`)
  return r.json()
}

export function urlDownload(sid: string): string {
  return `${BASE}/api/sessao/${sid}/download`
}

export async function salvarDecisoes(sid: string, decisoes: PayloadDecisoes) {
  const r = await fetch(`${BASE}/api/sessao/${sid}/salvar-decisoes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(decisoes),
  });
  return r.json();
}

export interface SessaoResumida {
  sessao_id: string
  nome: string
  ano: number
  criado_em: string
  status: string
}

export async function deletarSessao(sid: string): Promise<void> {
  const r = await fetch(`${BASE}/api/sessao/${sid}`, { method: 'DELETE' })
  if (!r.ok) throw new Error(`Erro ${r.status}`)
}

export async function listarSessoes(): Promise<SessaoResumida[]> {
  const r = await fetch(`${BASE}/api/sessoes`)
  if (!r.ok) throw new Error(`Erro ${r.status}`)
  return r.json()
}
