import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { BASE, previewDocumento, reanalisarSessao, salvarDecisoes, type PayloadDecisoes } from '../api'
import type { ItemInad, ItemRevisao, Sessao } from '../types'

export interface UseDecisoesReturn {
  extra: ItemRevisao[]
  setExtra: React.Dispatch<React.SetStateAction<ItemRevisao[]>>
  revisar: ItemRevisao[]
  setRevisar: React.Dispatch<React.SetStateAction<ItemRevisao[]>>
  inad: ItemInad[]
  setInad: React.Dispatch<React.SetStateAction<ItemInad[]>>
  vivo: { subtotal: number; total: number; impacto: number }
  calculando: boolean
  aoVivo: { dedExtra: number; dedRev: number; impacto: number }
  buildPayload: () => PayloadDecisoes
  inflacao: number
  setInflacao: (v: number) => void
  ultimoReajuste: string
  setUltimoReajuste: (v: string) => void
  recalcularAgora: () => Promise<void>
}

function valorAtual(i: { valor: number; valor_editado?: number }) {
  return Number.isFinite(i.valor_editado) ? Number(i.valor_editado) : i.valor
}

function payloadRevisao(items: ItemRevisao[]) {
  return Object.fromEntries(
    items.map(i => [String(i.id), {
      decisao: i.decisao,
      valor: valorAtual(i),
      nota: i.nota ?? '',
    }]),
  )
}

function payloadInad(items: ItemInad[]) {
  return Object.fromEntries(
    items.map(i => [String(i.id), {
      decisao: i.decisao,
      valor: valorAtual(i),
      nota: i.nota ?? '',
    }]),
  )
}

export function useDecisoes(sessao: Sessao): UseDecisoesReturn {
  const [extra, setExtra] = useState<ItemRevisao[]>(sessao.extraordinarias)
  const [revisar, setRevisar] = useState<ItemRevisao[]>(sessao.revisar)
  const [inad, setInad] = useState<ItemInad[]>(sessao.inadimplencia)
  const [inflacao, setInflacao] = useState<number>(sessao.resumo.inflacao ?? 0.10)
  const [ultimoReajuste, setUltimoReajuste] = useState<string>(sessao.resumo.ultimo_reajuste ?? '')

  const [vivo, setVivo] = useState({
    subtotal: sessao.resumo.subtotal,
    total: sessao.resumo.total_previsto,
    impacto: sessao.resumo.impacto_receita_mensal ?? 0,
  })
  const [calculando, setCalculando] = useState(false)

  // Resumo ao vivo sem backend (apenas deducoes locais)
  const aoVivo = useMemo(() => {
    const dedExtra = extra
      .filter(i => i.decisao === 'aprovada')
      .reduce((s, i) => s + valorAtual(i), 0)
    const dedRev = revisar
      .filter(i => i.decisao === 'aprovada')
      .reduce((s, i) => s + valorAtual(i), 0)
    const unidades = new Map<string, number[]>()
    inad
      .filter(i => i.decisao === 'abater')
      .forEach(i => {
        unidades.set(i.unidade, [...(unidades.get(i.unidade) ?? []), valorAtual(i)])
      })
    let impacto = 0
    unidades.forEach(vs => {
      impacto += vs.reduce((a, b) => a + b, 0) / vs.length
    })
    return { dedExtra, dedRev, impacto }
  }, [extra, revisar, inad])

  const buildPayload = useCallback((): PayloadDecisoes => {
    return {
      extraordinarias: payloadRevisao(extra),
      revisar: payloadRevisao(revisar),
      inadimplencia: payloadInad(inad),
      inflacao_pct: inflacao,
      ultimo_reajuste: ultimoReajuste || null,
    }
  }, [extra, revisar, inad, inflacao, ultimoReajuste])

  // Preview debounced (backend recalcula subtotal/total)
  const primeiraRender = useRef(true)
  const previewSeq = useRef(0)

  useEffect(() => {
    if (primeiraRender.current) {
      primeiraRender.current = false
      return
    }
    setCalculando(true)
    const seq = ++previewSeq.current
    const t = setTimeout(async () => {
      try {
        const payload = buildPayload()
        const r = await previewDocumento(sessao.sessao_id, payload)
        // So aplica se esta for a requisicao mais recente
        if (seq !== previewSeq.current) return
        setVivo({
          subtotal: r.subtotal,
          total: r.total_previsto,
          impacto: r.impacto_receita_mensal,
        })
        await salvarDecisoes(sessao.sessao_id, payload)
      } catch {
        /* mantem ultimo valor */
      } finally {
        if (seq === previewSeq.current) {
          setCalculando(false)
        }
      }
    }, 350)
    return () => clearTimeout(t)
  }, [extra, revisar, inad, inflacao, ultimoReajuste, sessao.sessao_id, buildPayload])

  // Salvar decisoes ao fechar/recarregar (beforeunload)
  useEffect(() => {
    const handleBeforeUnload = () => {
      const payload = buildPayload()
      const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' })
      navigator.sendBeacon(
        `${BASE}/api/sessao/${sessao.sessao_id}/salvar-decisoes`,
        blob,
      )
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [buildPayload, sessao.sessao_id])

  // Recalculo manual imediato (botao "Recalcular" na interface)
  // Re-executa a analise COMPLETA (IA + regras) — equivale a fazer upload novamente
  const recalcularAgora = useCallback(async () => {
    setCalculando(true)
    try {
      const nova = await reanalisarSessao(sessao.sessao_id)
      // Reseta todo o estado interno com os resultados frescos da reanalise
      setExtra(nova.extraordinarias)
      setRevisar(nova.revisar)
      setInad(nova.inadimplencia)
      setVivo({
        subtotal: nova.resumo.subtotal,
        total: nova.resumo.total_previsto,
        impacto: nova.resumo.impacto_receita_mensal ?? 0,
      })
      setInflacao(nova.resumo.inflacao ?? 0.10)
      setUltimoReajuste(nova.resumo.ultimo_reajuste ?? '')
      // Pula o proximo preview debounced — os numeros ja estao atualizados
      primeiraRender.current = true
    } catch (err) {
      /* mantem ultimo valor */
      console.error('Erro ao recalcular:', err)
    } finally {
      setCalculando(false)
    }
  }, [sessao.sessao_id])

  return {
    extra,
    setExtra,
    revisar,
    setRevisar,
    inad,
    setInad,
    vivo,
    calculando,
    aoVivo,
    buildPayload,
    inflacao,
    setInflacao,
    ultimoReajuste,
    setUltimoReajuste,
    recalcularAgora,
  }
}
