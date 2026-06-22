import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { BASE, previewDocumento, salvarDecisoes, type PayloadDecisoes } from '../api'
import type { ItemInad, ItemRevisao, Sessao } from '../types'

export interface UseDecisoesReturn {
  extra: ItemRevisao[]
  setExtra: React.Dispatch<React.SetStateAction<ItemRevisao[]>>
  revisar: ItemRevisao[]
  setRevisar: React.Dispatch<React.SetStateAction<ItemRevisao[]>>
  inad: ItemInad[]
  setInad: React.Dispatch<React.SetStateAction<ItemInad[]>>
  feitos: Set<number>
  marcarFeito: (id: number) => void
  reabrir: (id: number) => void
  vivo: { subtotal: number; total: number; impacto: number }
  calculando: boolean
  aoVivo: { dedExtra: number; dedRev: number; impacto: number }
  buildPayload: () => PayloadDecisoes
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
  const [feitos, setFeitos] = useState<Set<number>>(new Set())

  const marcarFeito = useCallback((id: number) => {
    setFeitos(s => new Set(s).add(id))
  }, [])

  const reabrir = useCallback((id: number) => {
    setFeitos(s => {
      const n = new Set(s)
      n.delete(id)
      return n
    })
  }, [])

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
    }
  }, [extra, revisar, inad])

  // Preview debounced (backend recalcula subtotal/total)
  const primeiraRender = useRef(true)

  useEffect(() => {
    if (primeiraRender.current) {
      primeiraRender.current = false
      return
    }
    setCalculando(true)
    const t = setTimeout(async () => {
      try {
        const payload = buildPayload()
        const r = await previewDocumento(sessao.sessao_id, payload)
        setVivo({
          subtotal: r.subtotal,
          total: r.total_previsto,
          impacto: r.impacto_receita_mensal,
        })
        await salvarDecisoes(sessao.sessao_id, payload)
      } catch {
        /* mantem ultimo valor */
      } finally {
        setCalculando(false)
      }
    }, 350)
    return () => clearTimeout(t)
  }, [extra, revisar, inad, sessao.sessao_id, buildPayload])

  // Salvar decisoes ao fechar/recarregar (beforeunload)
  useEffect(() => {
    const handleBeforeUnload = () => {
      const payload = buildPayload()
      navigator.sendBeacon(
        `${BASE}/api/sessao/${sessao.sessao_id}/salvar-decisoes`,
        JSON.stringify(payload),
      )
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [buildPayload, sessao.sessao_id])

  return {
    extra,
    setExtra,
    revisar,
    setRevisar,
    inad,
    setInad,
    feitos,
    marcarFeito,
    reabrir,
    vivo,
    calculando,
    aoVivo,
    buildPayload,
  }
}
