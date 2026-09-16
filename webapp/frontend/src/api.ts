import { type Sessao } from './types'

export const BASE = import.meta.env.DEV ? 'http://localhost:8000' : ''

type ApiErrorBody = {
  detail?: unknown
  message?: unknown
}

/**
 * Transforma respostas de erro da API em uma mensagem que uma pessoa consegue
 * entender. O FastAPI devolve erros de validação (422) como uma lista de
 * objetos; passá-los diretamente para Error fazia o navegador mostrar
 * "[object Object],[object Object]".
 */
export function mensagemErroApi(body: unknown, fallback: string): string {
  if (typeof body === 'string' && body.trim()) return body
  if (!body || typeof body !== 'object') return fallback

  const { detail, message } = body as ApiErrorBody
  const conteudo = detail ?? message
  if (typeof conteudo === 'string' && conteudo.trim()) return conteudo

  if (Array.isArray(conteudo)) {
    const mensagens = conteudo
      .map((erro) => {
        if (typeof erro === 'string') return erro
        if (!erro || typeof erro !== 'object') return null
        const item = erro as { loc?: unknown; msg?: unknown }
        const campo = Array.isArray(item.loc)
          ? item.loc.filter((parte) => parte !== 'body').join(' › ')
          : ''
        const texto = typeof item.msg === 'string' ? item.msg : null
        if (!texto) return null
        return campo ? `${campo}: ${texto}` : texto
      })
      .filter((mensagem): mensagem is string => Boolean(mensagem))
    if (mensagens.length) return mensagens.join('. ')
  }

  if (conteudo && typeof conteudo === 'object') {
    const item = conteudo as { msg?: unknown }
    if (typeof item.msg === 'string' && item.msg.trim()) return item.msg
  }

  return fallback
}

async function lancarErroResposta(r: Response): Promise<never> {
  const body = await r.json().catch(() => null)
  throw new Error(mensagemErroApi(body, `Erro ${r.status}`))
}

export interface DecisaoEditavel {
  decisao: string
  valor?: number
  nota?: string
}

export interface PayloadDecisoes {
  extraordinarias: Record<string, DecisaoEditavel>
  revisar: Record<string, DecisaoEditavel>
  inadimplencia: Record<string, DecisaoEditavel>
  lancamentos: Record<string, DecisaoEditavel>
  inflacao_pct?: number | null
  ultimo_reajuste?: string | null
  com_fundo?: boolean
}

export async function criarSessao(form: {
  nome: string
  ano: number
  balanual: File
  desbai: File
  rec: File
  dessin?: File | null
  inad?: File | null
}): Promise<Sessao> {
  const fd = new FormData()
  fd.append('nome_condominio', form.nome)
  fd.append('ano_previsao', String(form.ano))
  fd.append('balanual', form.balanual)
  fd.append('desbai', form.desbai)
  fd.append('rec', form.rec)
  if (form.dessin) fd.append('dessin', form.dessin)
  if (form.inad) fd.append('inad', form.inad)
  const r = await fetch(`${BASE}/api/sessao`, { method: 'POST', body: fd })
  if (!r.ok) await lancarErroResposta(r)
  return r.json()
}

export async function gerarRelatorioPdf(
  sid: string,
  decisoes: PayloadDecisoes,
): Promise<Blob> {
  const r = await fetch(`${BASE}/api/sessao/${sid}/relatorio-pdf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(decisoes),
  })
  if (!r.ok) await lancarErroResposta(r)
  return r.blob()
}

export async function previewDocumento(
  sid: string,
  decisoes: PayloadDecisoes,
): Promise<{ subtotal: number; total_previsto: number; impacto_receita_mensal: number; inflacao?: number }> {
  const r = await fetch(`${BASE}/api/sessao/${sid}/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(decisoes),
  })
  if (!r.ok) await lancarErroResposta(r)
  return r.json()
}

export async function salvarDecisoes(sid: string, decisoes: PayloadDecisoes) {
  const r = await fetch(`${BASE}/api/sessao/${sid}/salvar-decisoes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(decisoes),
  });
  if (!r.ok) await lancarErroResposta(r)
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

export async function reanalisarSessao(sid: string): Promise<Sessao> {
  const r = await fetch(`${BASE}/api/sessao/${sid}/reanalisar`, { method: 'POST' })
  if (!r.ok) throw new Error((await r.json()).detail ?? `Erro ${r.status}`)
  return r.json()
}

export async function listarSessoes(): Promise<SessaoResumida[]> {
  const r = await fetch(`${BASE}/api/sessoes`)
  if (!r.ok) throw new Error(`Erro ${r.status}`)
  return r.json()
}
