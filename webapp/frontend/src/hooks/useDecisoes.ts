import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { BASE, previewDocumento, reanalisarSessao, salvarDecisoes, type PayloadDecisoes } from '../api'
import type { ItemInad, ItemRevisao, LancamentoConta, Sessao } from '../types'

export interface UseDecisoesReturn {
  extra: ItemRevisao[]
  setExtra: React.Dispatch<React.SetStateAction<ItemRevisao[]>>
  revisar: ItemRevisao[]
  setRevisar: React.Dispatch<React.SetStateAction<ItemRevisao[]>>
  inad: ItemInad[]
  setInad: React.Dispatch<React.SetStateAction<ItemInad[]>>
  lancamentos: LancamentoConta[]
  decisoesLancamentos: Map<number, 'deduzir' | 'manter' | 'pendente'>
  decidirLancamento: (id: number, decisao: 'deduzir' | 'manter') => void
  vivo: { subtotal: number; total: number; impacto: number }
  calculando: boolean
  aoVivo: { dedExtra: number; dedRev: number; dedLancamentos: number; impacto: number }
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
  const [lancamentos, setLancamentos] = useState<LancamentoConta[]>(sessao.lancamentos_contas ?? [])
  const [inflacao, setInflacao] = useState<number>(sessao.resumo.inflacao ?? 0.10)
  const [ultimoReajuste, setUltimoReajuste] = useState<string>(sessao.resumo.ultimo_reajuste ?? '')

  const [vivo, setVivo] = useState({
    subtotal: sessao.resumo.subtotal,
    total: sessao.resumo.total_previsto,
    impacto: sessao.resumo.impacto_receita_mensal ?? 0,
  })
  const [calculando, setCalculando] = useState(false)

  const decisoesLancamentos = useMemo(() => {
    const decisoes = new Map<number, 'deduzir' | 'manter' | 'pendente'>()
    lancamentos.forEach(item => {
      decisoes.set(item.id, item.decisao ?? (
        item.categoria_inicial === 'Extraordinaria' ? 'deduzir' :
        item.categoria_inicial === 'Revisar' ? 'pendente' : 'manter'
      ))
    })
    extra.forEach(item => decisoes.set(
      item.id,
      item.decisao === 'aprovada' ? 'deduzir' : item.decisao === 'pendente' ? 'pendente' : 'manter',
    ))
    revisar.forEach(item => decisoes.set(
      item.id,
      item.decisao === 'aprovada' ? 'deduzir' : item.decisao === 'pendente' ? 'pendente' : 'manter',
    ))
    return decisoes
  }, [lancamentos, extra, revisar])

  const decidirLancamento = useCallback((id: number, decisao: 'deduzir' | 'manter') => {
    const decisaoRevisao = decisao === 'deduzir' ? 'aprovada' : 'reprovada'
    setExtra(prev => prev.map(item => item.id === id ? { ...item, decisao: decisaoRevisao } : item))
    setRevisar(prev => prev.map(item => item.id === id ? { ...item, decisao: decisaoRevisao } : item))
    setLancamentos(prev => prev.map(item => item.id === id ? { ...item, decisao } : item))
  }, [])

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
    const idsRevisao = new Set([...extra, ...revisar].map(item => item.id))
    const dedLancamentos = lancamentos
      .filter(item => !idsRevisao.has(item.id) && decisoesLancamentos.get(item.id) === 'deduzir')
      .reduce((total, item) => total + item.valor_pago, 0)
    return { dedExtra, dedRev, dedLancamentos, impacto }
  }, [extra, revisar, inad, lancamentos, decisoesLancamentos])

  const buildPayload = useCallback((): PayloadDecisoes => {
    return {
      extraordinarias: payloadRevisao(extra),
      revisar: payloadRevisao(revisar),
      inadimplencia: payloadInad(inad),
      lancamentos: Object.fromEntries(
        [...decisoesLancamentos.entries()].map(([id, decisao]) => [String(id), { decisao }]),
      ),
      inflacao_pct: inflacao,
      ultimo_reajuste: ultimoReajuste || null,
    }
  }, [extra, revisar, inad, decisoesLancamentos, inflacao, ultimoReajuste])

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
  }, [extra, revisar, inad, lancamentos, inflacao, ultimoReajuste, sessao.sessao_id, buildPayload])

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
      setLancamentos(nova.lancamentos_contas ?? [])
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
    lancamentos,
    decisoesLancamentos,
    decidirLancamento,
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
