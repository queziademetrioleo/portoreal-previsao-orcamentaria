import { useMemo, useState } from 'react'
import type { ItemInad, ItemRevisao, LinhaConta, Sessao } from '../types'
import { useDecisoes } from '../hooks/useDecisoes'
import { gerarDocumento } from '../api'

type Aba = 'relatorio' | 'extraordinarios' | 'ordinarias' | 'inadimplentes' | 'contas'

function fmt(v: number) {
  return v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function brl(v: number) {
  return `R$ ${fmt(v)}`
}

function valorAtual(item: { valor: number; valor_editado?: number }) {
  return Number.isFinite(item.valor_editado) ? Number(item.valor_editado) : item.valor
}

function agruparPorGrupo(linhas: LinhaConta[]) {
  const grupos = new Map<string, { base: number; deducao: number; final: number; contas: number }>()
  linhas.forEach(l => {
    const atual = grupos.get(l.grupo) ?? { base: 0, deducao: 0, final: 0, contas: 0 }
    atual.base += l.base
    atual.deducao += l.deducao
    atual.final += l.final
    atual.contas += 1
    grupos.set(l.grupo, atual)
  })
  return [...grupos.entries()].sort((a, b) => b[1].final - a[1].final)
}

function parseValor(value: string) {
  const n = Number(value.replace(',', '.'))
  return Number.isFinite(n) ? n : 0
}

function StatusDecisao({ decisao }: { decisao: string }) {
  if (decisao === 'aprovada') return <span className="audit-pill danger">Removido da previsão</span>
  if (decisao === 'reprovada') return <span className="audit-pill ok">Mantido na previsão</span>
  if (decisao === 'abater') return <span className="audit-pill danger">Abater da receita</span>
  if (decisao === 'ignorar') return <span className="audit-pill neutral">Ignorar</span>
  return <span className="audit-pill warn">Pendente</span>
}

function EditorDespesa({ item, onChange, origem }: {
  item: ItemRevisao
  origem: 'extraordinaria' | 'ordinaria'
  onChange: (patch: Partial<ItemRevisao>) => void
}) {
  const ehPendente = item.decisao === 'pendente'
  return (
    <article className={`audit-editor-card ${ehPendente ? 'pending' : ''}`}>
      <div className="audit-editor-main">
        <div className="audit-editor-title">
          <strong>{item.classe}</strong>
          <span>{item.grupo}</span>
        </div>
        {item.descricao && <p className="audit-editor-desc">{item.descricao}</p>}
        <div className="audit-editor-meta">
          <span>{item.data || 'Sem data'}</span>
          <span>{item.origem === 'IA' ? 'Classificado por IA' : 'Classificado por regra'}</span>
          {item.n_meses !== null && <span>{item.n_meses} meses com movimento</span>}
        </div>
        {item.motivo && <p className="audit-note-line">{item.motivo}</p>}
      </div>

      <div className="audit-editor-controls">
        <StatusDecisao decisao={item.decisao} />
        <label className="audit-field">
          <span>Valor considerado</span>
          <input
            type="number"
            min="0"
            step="0.01"
            value={valorAtual(item)}
            onChange={e => onChange({ valor_editado: parseValor(e.target.value) })}
          />
        </label>
        <label className="audit-field wide">
          <span>Nota da revisão</span>
          <textarea
            value={item.nota ?? ''}
            onChange={e => onChange({ nota: e.target.value })}
            placeholder="Explique o motivo da decisão para auditoria futura."
          />
        </label>
        <div className="audit-choice-row">
          <button
            className={`btn ${item.decisao === 'aprovada' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            onClick={() => onChange({ decisao: 'aprovada' })}
          >
            Remover da previsão
          </button>
          <button
            className={`btn ${item.decisao === 'reprovada' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            onClick={() => onChange({ decisao: 'reprovada' })}
          >
            Manter como despesa
          </button>
          {origem === 'ordinaria' && (
            <button className="btn btn-ghost btn-sm" onClick={() => onChange({ decisao: 'pendente' })}>
              Marcar pendente
            </button>
          )}
        </div>
      </div>
    </article>
  )
}

function EditorInadimplente({ item, onChange }: {
  item: ItemInad
  onChange: (patch: Partial<ItemInad>) => void
}) {
  return (
    <article className={`audit-editor-card ${item.critica ? 'pending' : ''}`}>
      <div className="audit-editor-main">
        <div className="audit-editor-title">
          <strong>{item.unidade}</strong>
          <span>{item.classe}</span>
        </div>
        <div className="audit-editor-meta">
          <span>Ref. {item.mes_ref}</span>
          <span>Venc. {item.vencimento || 'sem vencimento'}</span>
          <span>{item.meses_atraso} meses em atraso</span>
          {item.critica && <span>Crítica</span>}
        </div>
      </div>

      <div className="audit-editor-controls">
        <StatusDecisao decisao={item.decisao} />
        <label className="audit-field">
          <span>Valor considerado</span>
          <input
            type="number"
            min="0"
            step="0.01"
            value={valorAtual(item)}
            onChange={e => onChange({ valor_editado: parseValor(e.target.value) })}
          />
        </label>
        <label className="audit-field wide">
          <span>Nota da revisão</span>
          <textarea
            value={item.nota ?? ''}
            onChange={e => onChange({ nota: e.target.value })}
            placeholder="Ex.: inadimplência recorrente, acordo, cobrança em aberto."
          />
        </label>
        <div className="audit-choice-row">
          <button
            className={`btn ${item.decisao === 'abater' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            onClick={() => onChange({ decisao: 'abater' })}
          >
            Abater da receita
          </button>
          <button
            className={`btn ${item.decisao === 'ignorar' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            onClick={() => onChange({ decisao: 'ignorar' })}
          >
            Ignorar no cálculo
          </button>
        </div>
      </div>
    </article>
  )
}

function TabelaLinhas({ linhas }: { linhas: LinhaConta[] }) {
  return (
    <div className="audit-table-wrap">
      <table className="result-table audit-table">
        <thead>
          <tr>
            <th>Grupo</th>
            <th>Conta</th>
            <th className="num">Base</th>
            <th className="num">Dedução</th>
            <th className="num">Final</th>
            <th>Regra aplicada</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((l, idx) => (
            <tr key={`${l.grupo}-${l.classe}-${idx}`}>
              <td>{l.grupo}</td>
              <td>{l.classe}</td>
              <td className="num">{brl(l.base)}</td>
              <td className="num">{brl(l.deducao)}</td>
              <td className="num">{brl(l.final)}</td>
              <td>{l.regra}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function TelaRevisao({ sessao, onVoltar, onGerado }: {
  sessao: Sessao
  onVoltar: () => void
  onGerado: (s: Sessao) => void
}) {
  const { extra, setExtra, revisar, setRevisar, inad, setInad, vivo, calculando, aoVivo, buildPayload } = useDecisoes(sessao)
  const [aba, setAba] = useState<Aba>('relatorio')
  const [gerando, setGerando] = useState(false)
  const [erro, setErro] = useState('')

  const pendentes = extra.filter(i => i.decisao === 'pendente').length + revisar.filter(i => i.decisao === 'pendente').length
  const removidos = [...extra, ...revisar].filter(i => i.decisao === 'aprovada')
  const mantidos = [...extra, ...revisar].filter(i => i.decisao === 'reprovada')
  const abatidos = inad.filter(i => i.decisao === 'abater')
  const saldo = sessao.resumo.receita_anual - vivo.total
  const grupos = useMemo(() => agruparPorGrupo(sessao.linhas_contas), [sessao.linhas_contas])
  const contasComDeducao = sessao.linhas_contas.filter(l => Math.abs(l.deducao) > 0.005)

  const atualizarExtra = (id: number, patch: Partial<ItemRevisao>) => {
    setExtra(prev => prev.map(i => i.id === id ? { ...i, ...patch } : i))
  }
  const atualizarRevisar = (id: number, patch: Partial<ItemRevisao>) => {
    setRevisar(prev => prev.map(i => i.id === id ? { ...i, ...patch } : i))
  }
  const atualizarInad = (id: number, patch: Partial<ItemInad>) => {
    setInad(prev => prev.map(i => i.id === id ? { ...i, ...patch } : i))
  }

  const handleGerar = async () => {
    setGerando(true)
    setErro('')
    try {
      await gerarDocumento(sessao.sessao_id, buildPayload())
      const r = await fetch(`/api/sessao/${sessao.sessao_id}`)
      const s = await r.json()
      onGerado(s)
    } catch (err: any) {
      setErro(err.message || 'Erro ao gerar documento.')
    } finally {
      setGerando(false)
    }
  }

  const abas: { id: Aba; label: string; count?: number }[] = [
    { id: 'relatorio', label: 'Relatório' },
    { id: 'extraordinarios', label: 'Editar Extraordinários', count: extra.length },
    { id: 'ordinarias', label: 'Editar Despesas Ordinárias', count: revisar.length },
    { id: 'inadimplentes', label: 'Editar Inadimplentes', count: inad.length },
    { id: 'contas', label: 'Contas Calculadas', count: sessao.linhas_contas.length },
  ]

  return (
    <>
      <header className="app-header">
        <a href="/" className="logo" onClick={e => { e.preventDefault(); onVoltar() }}>
          <img src="/assets/logo.png" alt="" /> Previsão Orçamentária
        </a>
        <button className="btn btn-ghost btn-sm" onClick={onVoltar}>Voltar</button>
      </header>

      <main className="audit-page">
        <section className="audit-hero">
          <div>
            <div className="eyebrow">Revisão auditável</div>
            <h1>{sessao.nome_condominio} <span>{sessao.ano_previsao}</span></h1>
            <p>
              Período base: {sessao.resumo.periodo?.[0]} a {sessao.resumo.periodo?.[1]}.
              As edições abaixo recalculam o preview pelo backend antes da geração.
            </p>
          </div>
          <div className="audit-hero-actions">
            <span className={`audit-pill ${pendentes > 0 ? 'warn' : 'ok'}`}>
              {pendentes > 0 ? `${pendentes} pendências` : 'Sem pendências'}
            </span>
            <button className="btn btn-primary" onClick={handleGerar} disabled={gerando || pendentes > 0}>
              {gerando ? 'Gerando...' : 'Salvar e gerar documento'}
            </button>
          </div>
        </section>

        {erro && <div className="erro">{erro}</div>}

        <section className="audit-kpis">
          <div className="audit-kpi">
            <span>Valor transportado</span>
            <strong>{brl(sessao.resumo.base_total)}</strong>
          </div>
          <div className="audit-kpi">
            <span>Removido na revisão</span>
            <strong>{brl(aoVivo.dedExtra + aoVivo.dedRev)}</strong>
          </div>
          <div className="audit-kpi">
            <span>Total previsto</span>
            <strong>{brl(vivo.total)}</strong>
            {calculando && <small>Recalculando...</small>}
          </div>
          <div className={`audit-kpi ${saldo < 0 ? 'danger' : 'success'}`}>
            <span>Saldo estimado</span>
            <strong>{brl(saldo)}</strong>
          </div>
        </section>

        <div className="audit-layout">
          <aside className="audit-sidebar">
            <div className="audit-panel">
              <h2>Trilha do cálculo</h2>
              <div className="audit-calc-row"><span>Base 12 meses</span><strong>{brl(sessao.resumo.base_total)}</strong></div>
              <div className="audit-calc-row"><span>Itens removidos</span><strong>- {brl(aoVivo.dedExtra + aoVivo.dedRev)}</strong></div>
              <div className="audit-calc-row"><span>Provisão laudo</span><strong>{brl(sessao.resumo.prov_laudo)}</strong></div>
              <div className="audit-calc-row"><span>Provisão incêndio</span><strong>{brl(sessao.resumo.prov_incendio)}</strong></div>
              <div className="audit-calc-row strong"><span>Subtotal</span><strong>{brl(vivo.subtotal)}</strong></div>
              <div className="audit-calc-row"><span>Inflação</span><strong>{brl(vivo.total - vivo.subtotal)}</strong></div>
              <div className="audit-calc-row strong"><span>Total previsto</span><strong>{brl(vivo.total)}</strong></div>
              <div className="audit-calc-row"><span>Receita anual</span><strong>{brl(sessao.resumo.receita_anual)}</strong></div>
              <div className="audit-calc-row"><span>Impacto inad.</span><strong>{brl(vivo.impacto)}/mês</strong></div>
            </div>
          </aside>

          <section className="audit-workspace">
            <nav className="audit-tabs" aria-label="Abas da revisão">
              {abas.map(item => (
                <button
                  key={item.id}
                  className={aba === item.id ? 'active' : ''}
                  onClick={() => setAba(item.id)}
                >
                  {item.label}
                  {typeof item.count === 'number' && <span>{item.count}</span>}
                </button>
              ))}
            </nav>

            {aba === 'relatorio' && (
              <div className="audit-section-stack">
                <section className="audit-card">
                  <div className="audit-section-head">
                    <div>
                      <h2>Relatório completo da revisão</h2>
                      <p>Mostra o que entrou, o que saiu e qual regra levou ao número final.</p>
                    </div>
                  </div>
                  <div className="audit-summary-grid">
                    <div><span>Análise inteligente</span><strong>{sessao.ia_ativa ? 'Ativa' : 'Regras locais'}</strong></div>
                    <div><span>Extraordinários removidos</span><strong>{removidos.length}</strong></div>
                    <div><span>Itens mantidos</span><strong>{mantidos.length}</strong></div>
                    <div><span>Inadimplências abatidas</span><strong>{abatidos.length}</strong></div>
                    <div><span>Notas manuais</span><strong>{[...extra, ...revisar, ...inad].filter(i => i.nota).length}</strong></div>
                  </div>
                </section>

                <section className="audit-card">
                  <h2>Despesas ordinárias consideradas</h2>
                  <p className="audit-muted">
                    Estas são as classes que permanecem compondo a previsão após as regras e decisões humanas.
                  </p>
                  <div className="audit-group-grid">
                    {grupos.map(([grupo, total]) => (
                      <div className="audit-group-card" key={grupo}>
                        <span>{grupo}</span>
                        <strong>{brl(total.final)}</strong>
                        <small>{total.contas} contas · dedução {brl(total.deducao)}</small>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="audit-card">
                  <h2>Gastos não considerados ou provisionados</h2>
                  {removidos.length === 0 && contasComDeducao.length === 0 ? (
                    <p className="audit-muted">Nenhum item removido ou deduzido até o momento.</p>
                  ) : (
                    <TabelaLinhas linhas={contasComDeducao.slice(0, 12)} />
                  )}
                </section>
              </div>
            )}

            {aba === 'extraordinarios' && (
              <div className="audit-section-stack">
                <div className="audit-section-head">
                  <div>
                    <h2>Editar Extraordinários</h2>
                    <p>Itens classificados como fora da rotina. “Remover” reduz a base da previsão; “manter” volta para o cálculo.</p>
                  </div>
                  <div className="audit-choice-row">
                    <button className="btn btn-secondary btn-sm" onClick={() => setExtra(prev => prev.map(i => ({ ...i, decisao: 'aprovada' })))}>
                      Remover todos
                    </button>
                    <button className="btn btn-secondary btn-sm" onClick={() => setExtra(prev => prev.map(i => ({ ...i, decisao: 'reprovada' })))}>
                      Manter todos
                    </button>
                  </div>
                </div>
                {extra.length === 0 ? <div className="result-empty">Nenhum extraordinário detectado.</div> : extra.map(item => (
                  <EditorDespesa key={item.id} item={item} origem="extraordinaria" onChange={patch => atualizarExtra(item.id, patch)} />
                ))}
              </div>
            )}

            {aba === 'ordinarias' && (
              <div className="audit-section-stack">
                <div className="audit-section-head">
                  <div>
                    <h2>Editar Despesas Ordinárias</h2>
                    <p>Itens em revisão. Use esta aba para decidir se entram como gasto normal ou se devem ser removidos.</p>
                  </div>
                  <div className="audit-choice-row">
                    <button className="btn btn-secondary btn-sm" onClick={() => setRevisar(prev => prev.map(i => ({ ...i, decisao: 'reprovada' })))}>
                      Manter todos
                    </button>
                    <button className="btn btn-secondary btn-sm" onClick={() => setRevisar(prev => prev.map(i => ({ ...i, decisao: 'aprovada' })))}>
                      Remover todos
                    </button>
                  </div>
                </div>
                {revisar.length === 0 ? <div className="result-empty">Nenhuma despesa ordinária pendente de revisão.</div> : revisar.map(item => (
                  <EditorDespesa key={item.id} item={item} origem="ordinaria" onChange={patch => atualizarRevisar(item.id, patch)} />
                ))}
              </div>
            )}

            {aba === 'inadimplentes' && (
              <div className="audit-section-stack">
                <div className="audit-section-head">
                  <div>
                    <h2>Editar Inadimplentes</h2>
                    <p>O abatimento calcula o impacto médio mensal por unidade e reduz a percepção de receita disponível.</p>
                  </div>
                  <div className="audit-choice-row">
                    <button className="btn btn-secondary btn-sm" onClick={() => setInad(prev => prev.map(i => ({ ...i, decisao: 'abater' })))}>
                      Abater todos
                    </button>
                    <button className="btn btn-secondary btn-sm" onClick={() => setInad(prev => prev.map(i => ({ ...i, decisao: 'ignorar' })))}>
                      Ignorar todos
                    </button>
                  </div>
                </div>
                {inad.length === 0 ? <div className="result-empty">Nenhuma inadimplência carregada.</div> : inad.map(item => (
                  <EditorInadimplente key={item.id} item={item} onChange={patch => atualizarInad(item.id, patch)} />
                ))}
              </div>
            )}

            {aba === 'contas' && (
              <div className="audit-section-stack">
                <section className="audit-card">
                  <h2>Contas calculadas pelo backend</h2>
                  <p className="audit-muted">
                    O “Valor Transportado” vem do balanço anual por classe. As NFs do DESBAI/DESSIN explicam deduções,
                    revisões e provisões, mas nem toda edição altera a base anual de uma classe.
                  </p>
                  <TabelaLinhas linhas={sessao.linhas_contas} />
                </section>
              </div>
            )}
          </section>
        </div>
      </main>
    </>
  )
}
