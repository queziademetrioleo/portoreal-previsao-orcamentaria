import { useState } from 'react'
import type { Sessao } from '../types'
import { useDecisoes } from '../hooks/useDecisoes'
import { gerarDocumento } from '../api'
import { CartaoRevisao, CartaoInad } from './CartaoItem'
import BulkActions from './BulkActions'

function fmt(v: number) {
  return v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function TelaRevisao({ sessao, onVoltar, onGerado }: {
  sessao: Sessao
  onVoltar: () => void
  onGerado: (s: Sessao) => void
}) {
  const { extra, setExtra, revisar, setRevisar, inad, setInad, vivo, buildPayload } = useDecisoes(sessao)
  const [gerando, setGerando] = useState(false)
  const [erro, setErro] = useState('')

  const pendentes = (arr: any[]) => arr.filter(i => i.decisao === 'pendente')

  const handleGerar = async () => {
    setGerando(true)
    setErro('')
    try {
      await gerarDocumento(sessao.sessao_id, buildPayload())
      // Busca a sessao atualizada (status=gerado) e navega para resultado
      const r = await fetch(`/api/sessao/${sessao.sessao_id}`)
      const s = await r.json()
      onGerado(s)
    } catch (err: any) {
      setErro(err.message || 'Erro ao gerar documento.')
    } finally {
      setGerando(false)
    }
  }

  return (
    <>
      <header className="app-header">
        <a href="/" className="logo" onClick={e => { e.preventDefault(); onVoltar() }}>
          <img src="/assets/logo.png" alt="" /> Previsão Orçamentária
        </a>
        <button className="btn btn-ghost btn-sm" onClick={onVoltar}>← Voltar</button>
      </header>

      <div className="review-bar">
        <span className="bar-title">{sessao.nome_condominio} — {sessao.ano_previsao}</span>
        <span className="bar-stat">Subtotal: <strong>R$ {fmt(vivo.subtotal)}</strong></span>
        <span className="bar-stat">Total previsto: <strong>R$ {fmt(vivo.total)}</strong></span>
        {vivo.impacto > 0 && <span className="bar-stat">Impacto inad: <strong>R$ {fmt(vivo.impacto)}/mês</strong></span>}
        <div className="bar-actions">
          <button className="btn btn-primary btn-sm" onClick={handleGerar} disabled={gerando}>
            {gerando ? 'Gerando...' : 'Salvar e gerar'}
          </button>
        </div>
      </div>

      <div className="container">
        {erro && <div className="erro">{erro}</div>}

        {/* Seção: Extraordinárias */}
        {pendentes(extra).length > 0 && (
          <div className="section">
            <div className="section-header">
              <div>
                <div className="eyebrow">Despesas extraordinárias detectadas</div>
                <span className="section-count">{pendentes(extra).length} pendentes</span>
              </div>
            </div>
            <BulkActions
              count={pendentes(extra).length}
              onApproveAll={() => setExtra(prev => prev.map(i => i.decisao === 'pendente' ? {...i, decisao:'aprovada'} : i))}
              onRejectAll={() => setExtra(prev => prev.map(i => i.decisao === 'pendente' ? {...i, decisao:'reprovada'} : i))}
              approveLabel="Aprovar todos"
              rejectLabel="Manter todos"
            />
            {extra.filter(i => i.decisao === 'pendente').map(i => (
              <CartaoRevisao key={i.id} item={i}
                onApprove={() => setExtra(prev => prev.map(x => x.id === i.id ? {...x, decisao:'aprovada'} : x))}
                onReject={() => setExtra(prev => prev.map(x => x.id === i.id ? {...x, decisao:'reprovada'} : x))}
              />
            ))}
          </div>
        )}

        {/* Seção: Em Revisão */}
        {pendentes(revisar).length > 0 && (
          <div className="section">
            <div className="section-header">
              <div>
                <div className="eyebrow">Em revisão</div>
                <span className="section-count">{pendentes(revisar).length} pendentes</span>
              </div>
            </div>
            <BulkActions
              count={pendentes(revisar).length}
              onApproveAll={() => setRevisar(prev => prev.map(i => i.decisao === 'pendente' ? {...i, decisao:'aprovada'} : i))}
              onRejectAll={() => setRevisar(prev => prev.map(i => i.decisao === 'pendente' ? {...i, decisao:'reprovada'} : i))}
              approveLabel="Aprovar todos"
              rejectLabel="Manter todos"
            />
            {revisar.filter(i => i.decisao === 'pendente').map(i => (
              <CartaoRevisao key={i.id} item={i}
                onApprove={() => setRevisar(prev => prev.map(x => x.id === i.id ? {...x, decisao:'aprovada'} : x))}
                onReject={() => setRevisar(prev => prev.map(x => x.id === i.id ? {...x, decisao:'reprovada'} : x))}
              />
            ))}
          </div>
        )}

        {/* Seção: Revisados (itens já decididos) */}
        {extra.filter(i => i.decisao !== 'pendente').length + revisar.filter(i => i.decisao !== 'pendente').length > 0 && (
          <div className="section">
            <div className="section-header">
              <div>
                <div className="eyebrow">Revisados</div>
                <span className="section-count">
                  {extra.filter(i => i.decisao !== 'pendente').length + revisar.filter(i => i.decisao !== 'pendente').length} decididos
                </span>
              </div>
            </div>
            {[...extra.filter(i => i.decisao !== 'pendente'), ...revisar.filter(i => i.decisao !== 'pendente')].map(i => (
              <CartaoRevisao key={i.id} item={i}
                onApprove={() => {}}
                onReject={() => {}}
                onReset={() => {
                  setExtra(prev => prev.map(x => x.id === i.id ? {...x, decisao:'pendente'} : x))
                  setRevisar(prev => prev.map(x => x.id === i.id ? {...x, decisao:'pendente'} : x))
                }}
              />
            ))}
          </div>
        )}

        {/* Seção: Inadimplência */}
        {inad.length > 0 && (
          <div className="section">
            <div className="section-header">
              <div>
                <div className="eyebrow">Inadimplência</div>
                <span className="section-count">
                  {inad.filter(i => i.critica).length} críticas · {inad.length} total
                </span>
              </div>
            </div>
            {inad.map(i => (
              <CartaoInad key={i.id} item={i}
                onAbater={() => setInad(prev => prev.map(x => x.id === i.id ? {...x, decisao:'abater'} : x))}
                onIgnorar={() => setInad(prev => prev.map(x => x.id === i.id ? {...x, decisao:'ignorar'} : x))}
              />
            ))}
          </div>
        )}

        {/* Botão final */}
        <div style={{textAlign:'center', marginTop:'var(--s-xl)'}}>
          <button className="btn btn-primary" onClick={handleGerar} disabled={gerando} style={{padding:'12px 32px',fontSize:'15px'}}>
            {gerando ? 'Gerando documento...' : 'Salvar e gerar documento'}
          </button>
        </div>
      </div>
    </>
  )
}
