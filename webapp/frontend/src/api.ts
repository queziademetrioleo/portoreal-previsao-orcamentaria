import { type Sessao } from './types'

const BASE = import.meta.env.DEV ? 'http://localhost:8000' : ''

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
  decisoes: {
    extraordinarias: Record<string, string>
    revisar: Record<string, string>
    inadimplencia: Record<string, string>
  },
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
  decisoes: {
    extraordinarias: Record<string, string>
    revisar: Record<string, string>
    inadimplencia: Record<string, string>
  },
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
