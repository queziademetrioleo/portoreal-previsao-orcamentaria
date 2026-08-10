import { useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import type { ItemInad, ItemRevisao, LancamentoConta, Sessao } from '../types'
import { useDecisoes } from '../hooks/useDecisoes'
import { gerarRelatorioPdf } from '../api'
import { money } from '../utils/format'
import Header from './ui/Header'
import Card from './ui/Card'
import Button from './ui/Button'
import Badge from './ui/Badge'
import NumberBlock from './ui/NumberBlock'
import TabBar from './ui/TabBar'

/* ─── helpers ─────────────────────────── */

type Aba = 'relatorio' | 'extraordinarios' | 'ordinarias' | 'inadimplentes' | 'contas'

type LancamentoAuditavel = LancamentoConta & {
  deduzido: boolean
  status: string
}

function parseValor(value: string) {
  const n = Number(value.replace(',', '.'))
  return Number.isFinite(n) ? n : 0
}

function valorAtual(item: { valor: number; valor_editado?: number }) {
  return Number.isFinite(item.valor_editado) ? Number(item.valor_editado) : item.valor
}

/* ─── sub-componentes ─────────────────── */

function StatusBadge({ decisao }: { decisao: string }) {
  switch (decisao) {
    case 'aprovada':
      return <Badge label="Fora da previsão — gasto pontual" variant="danger" />
    case 'reprovada':
      return <Badge label="Na previsão — gasto recorrente" variant="success" />
    case 'abater':
      return <Badge label="Vai descontar da receita" variant="danger" />
    case 'ignorar':
      return <Badge label="Não descontar" variant="neutral" />
    default:
      return <Badge label="Aguardando sua decisão" variant="warning" />
  }
}

function EditorDespesa({
  item,
  onChange,
}: {
  item: ItemRevisao
  onChange: (patch: Partial<ItemRevisao>) => void
}) {
  return (
    <article className={`editor-card ${item.decisao === 'pendente' ? 'pending' : ''}`}>
      <div>
        <h3>{item.classe}</h3>
        <p className="meta">
          <span>{item.grupo}</span>
          <span>{item.data || 'Sem data'}</span>
          <span>{item.origem === 'IA' ? 'IA' : 'Regra'}</span>
          {item.n_meses !== null && <span>{item.n_meses} meses</span>}
        </p>
        {item.descricao && <p className="desc">{item.descricao}</p>}
        {item.motivo && <p className="note">{item.motivo}</p>}
      </div>

      <div className="editor-controls">
        <StatusBadge decisao={item.decisao} />

        <label className="editor-field">
          <span>Valor</span>
          <input
            type="number"
            min="0"
            step="0.01"
            value={valorAtual(item)}
            onChange={(e) => onChange({ valor_editado: parseValor(e.target.value) })}
          />
        </label>

        <label className="editor-field">
          <span>Nota</span>
          <textarea
            value={item.nota ?? ''}
            onChange={(e) => onChange({ nota: e.target.value })}
            placeholder="Explique o motivo da decisão."
          />
        </label>

        <div className="choice-row">
          <Button
            size="sm"
            variant={item.decisao === 'aprovada' ? 'primary' : 'secondary'}
            onClick={() => onChange({ decisao: 'aprovada' })}
          >
            É gasto pontual — tirar da previsão
          </Button>
          <Button
            size="sm"
            variant={item.decisao === 'reprovada' ? 'primary' : 'secondary'}
            onClick={() => onChange({ decisao: 'reprovada' })}
          >
            É gasto recorrente — manter na previsão
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onChange({ decisao: 'pendente' })}
          >
            Decidir depois
          </Button>
        </div>
      </div>
    </article>
  )
}

function EditorInad({
  item,
  onChange,
}: {
  item: ItemInad
  onChange: (patch: Partial<ItemInad>) => void
}) {
  return (
    <article className={`editor-card ${item.critica ? 'pending' : ''}`}>
      <div>
        <h3>{item.unidade}</h3>
        <p className="meta">
          <span>{item.classe}</span>
          <span>Ref. {item.mes_ref}</span>
          <span>Venc. {item.vencimento || '—'}</span>
          <span>{item.meses_atraso} meses atraso</span>
          {item.ultima_parcela && <span>Última parcela: {item.ultima_parcela}</span>}
          {item.critica && <span>Crítica</span>}
        </p>
      </div>

      <div className="editor-controls">
        <StatusBadge decisao={item.decisao} />

        <label className="editor-field">
          <span>Valor</span>
          <input
            type="number"
            min="0"
            step="0.01"
            value={valorAtual(item)}
            onChange={(e) => onChange({ valor_editado: parseValor(e.target.value) })}
          />
        </label>

        <label className="editor-field">
          <span>Nota</span>
          <textarea
            value={item.nota ?? ''}
            onChange={(e) => onChange({ nota: e.target.value })}
            placeholder="Ex.: acordo de cobrança em andamento."
          />
        </label>

        <div className="choice-row">
          <Button
            size="sm"
            variant={item.decisao === 'abater' ? 'primary' : 'secondary'}
            onClick={() => onChange({ decisao: 'abater' })}
          >
            Descontar da receita
          </Button>
          <Button
            size="sm"
            variant={item.decisao === 'ignorar' ? 'primary' : 'secondary'}
            onClick={() => onChange({ decisao: 'ignorar' })}
          >
            Não descontar
          </Button>
        </div>
      </div>
    </article>
  )
}

/* ─── tela principal ──────────────────── */

export default function TelaRevisao({
  sessao,
  onVoltar,
}: {
  sessao: Sessao
  onVoltar: () => void
}) {
  const {
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
  } = useDecisoes(sessao)

  const [aba, setAba] = useState<Aba>('relatorio')
  const [gerando, setGerando] = useState(false)
  const [erro, setErro] = useState('')
  const [comFundo, setComFundo] = useState(true)
  const [modalGerarAberto, setModalGerarAberto] = useState(false)

  // Cenários com/sem fundo de reserva
  const cenarios = sessao.resumo.cenarios
  const cenarioAtivo = cenarios ? (comFundo ? cenarios.com_fundo : cenarios.sem_fundo) : null
  const receitaAtual = cenarioAtivo ? cenarioAtivo.receita_anual : sessao.resumo.receita_anual

  const pendentes =
    extra.filter((i) => i.decisao === 'pendente').length +
    revisar.filter((i) => i.decisao === 'pendente').length

  const removidos = [...extra, ...revisar].filter((i) => i.decisao === 'aprovada')
  const saldo = receitaAtual - vivo.total

  const updateExtra = (id: number, patch: Partial<ItemRevisao>) =>
    setExtra((prev) => prev.map((i) => (i.id === id ? { ...i, ...patch } : i)))
  const updateRevisar = (id: number, patch: Partial<ItemRevisao>) =>
    setRevisar((prev) => prev.map((i) => (i.id === id ? { ...i, ...patch } : i)))
  const updateInad = (id: number, patch: Partial<ItemInad>) =>
    setInad((prev) => prev.map((i) => (i.id === id ? { ...i, ...patch } : i)))

  const handleGerar = async () => {
    setGerando(true)
    setErro('')
    try {
      const payload = buildPayload()
      payload.com_fundo = comFundo
      const pdf = await gerarRelatorioPdf(sessao.sessao_id, payload)
      const url = URL.createObjectURL(pdf)
      const link = document.createElement('a')
      link.href = url
      link.download = `Relatorio ${sessao.ano_previsao} - ${sessao.nome_condominio}.pdf`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      setModalGerarAberto(false)
    } catch (err: unknown) {
      setErro(err instanceof Error ? err.message : 'Erro ao gerar documento.')
    } finally {
      setGerando(false)
    }
  }

  const tabs: { id: Aba; label: string; count?: number }[] = [
    { id: 'relatorio', label: 'Visão geral' },
    { id: 'extraordinarios', label: 'Gastos pontuais', count: extra.length },
    { id: 'ordinarias', label: 'Gastos a revisar', count: revisar.length },
    { id: 'inadimplentes', label: 'Inadimplência', count: inad.length },
    { id: 'contas', label: 'Contas calculadas', count: (sessao.lancamentos_contas ?? []).length },
  ]

  const lancamentosAuditaveis = useMemo<LancamentoAuditavel[]>(() => {
    const decisoes = new Map<number, string>([
      ...extra.map((item) => [item.id, item.decisao] as const),
      ...revisar.map((item) => [item.id, item.decisao] as const),
    ])
    return (sessao.lancamentos_contas ?? []).map((item) => {
      const decisao = decisoes.get(item.id)
      const deduzido = decisao === 'aprovada'
      return {
        ...item,
        deduzido,
        status: deduzido
          ? 'Deduzido da previsão'
          : decisao === 'pendente'
            ? 'Aguardando decisão'
            : 'Mantido na previsão',
      }
    })
  }, [sessao.lancamentos_contas, extra, revisar])

  const contasPorGrupo = useMemo(() => {
    const grupos = new Map<string, Map<string, LancamentoAuditavel[]>>()
    for (const item of lancamentosAuditaveis) {
      const classes = grupos.get(item.grupo) ?? new Map<string, LancamentoAuditavel[]>()
      classes.set(item.classe, [...(classes.get(item.classe) ?? []), item])
      grupos.set(item.grupo, classes)
    }
    return [...grupos.entries()]
      .map(([grupo, classes]) => ({
        grupo,
        classes: [...classes.entries()]
          .map(([classe, itens]) => ({
            classe,
            itens: itens.sort((a, b) => a.data.localeCompare(b.data)),
            pago: itens.reduce((total, item) => total + item.valor_pago, 0),
            deduzido: itens.filter((item) => item.deduzido).reduce((total, item) => total + item.valor_pago, 0),
          }))
          .sort((a, b) => a.classe.localeCompare(b.classe)),
      }))
      .sort((a, b) => a.grupo.localeCompare(b.grupo))
  }, [lancamentosAuditaveis])

  return (
    <>
      <Header onHome={onVoltar}>
        <Button variant="ghost" onClick={onVoltar}>
          Voltar
        </Button>
      </Header>

      <div className="page page-wide">
        {/* hero */}
        <section className="review-hero">
          <div>
            <p className="section-label">Revisão da previsão</p>
            <h1>
              {sessao.nome_condominio} — {sessao.ano_previsao}
            </h1>
            <p>
              Período base: {sessao.resumo.periodo?.[0]} a {sessao.resumo.periodo?.[1]}. Revise
              cada item antes de gerar o documento final.
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <Badge
              label={pendentes > 0 ? `${pendentes} pendências` : 'Tudo revisado'}
              variant={pendentes > 0 ? 'warning' : 'success'}
            />
            <Button
              variant="primary"
              onClick={() => setModalGerarAberto(true)}
              disabled={gerando || pendentes > 0}
            >
              {gerando ? 'Gerando...' : 'Gerar documento'}
            </Button>
          </div>
        </section>

        {erro && <div className="alert-error">{erro}</div>}

        {/* KPIs */}
        <div className="number-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
          <NumberBlock label="Valor transportado (anual)" value={money(sessao.resumo.base_total)} />
          <NumberBlock label="Removido na revisão" value={money(aoVivo.dedExtra + aoVivo.dedRev)} />
          <NumberBlock
            label="Total previsto (anual)"
            value={calculando ? '...' : money(vivo.total)}
          />
          <NumberBlock
            label="Saldo estimado (anual)"
            value={money(saldo)}
            variant={saldo < 0 ? 'negative' : 'positive'}
          />
        </div>

        {/* layout: sidebar + conteúdo */}
        <div className="review-layout">
          <aside className="review-sidebar">
            <Card padding="md">
              <h2 className="section-title">Cálculo</h2>
              <div className="calc-row"><span>Base 12 meses</span><strong>{money(sessao.resumo.base_total)}</strong></div>
              <div className="calc-row"><span>Itens removidos</span><strong>- {money(aoVivo.dedExtra + aoVivo.dedRev)}</strong></div>
              <div className="calc-row strong"><span>Subtotal</span><strong>{money(vivo.subtotal)}</strong></div>
              <div className="calc-row">
                <span>Aumento previsto ({(inflacao * 100).toLocaleString('pt-BR', { maximumFractionDigits: 2 })}% sobre o subtotal)</span>
                <strong>{money(vivo.total - vivo.subtotal)}</strong>
              </div>
              <div className="calc-row strong"><span>Total previsto (anual)</span><strong>{money(vivo.total)}</strong></div>
              <div className="calc-row"><span>Receita anual</span><strong>{money(receitaAtual)}</strong></div>
              <div className="calc-row"><span>Impacto inad.</span><strong>{money(vivo.impacto)}/mês</strong></div>
              <div style={{ marginTop: 10 }}>
                <Button
                  size="sm"
                  variant="primary"
                  onClick={recalcularAgora}
                  disabled={calculando}
                  full
                >
                  {calculando ? 'Reanalisando com IA...' : '🔄 Recalcular (nova análise)'}
                </Button>
              </div>
            </Card>
          </aside>

          <section style={{ minWidth: 0 }}>
            <TabBar tabs={tabs} active={aba} onChange={(id) => setAba(id as Aba)} />

            {aba === 'relatorio' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <Card>
                  <h2 className="section-title">Relatório da revisão</h2>
                  <p className="section-desc">
                    Quantidade de gastos extraordinários retirados da previsão.
                  </p>
                  <div className="number-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
                    <NumberBlock label="Itens extraordinários removidos" value={String(removidos.length)} />
                  </div>
                </Card>

              </div>
            )}

            {aba === 'extraordinarios' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
                  <div>
                    <h2 className="section-title">Gastos pontuais</h2>
                    <p className="section-desc">O sistema identificou esses gastos como fora da rotina. Se o gasto não vai se repetir no próximo ano, ele deve sair da previsão.</p>
                  </div>
                  <div className="choice-row">
                    <Button size="sm" variant="secondary" onClick={() => setExtra((prev) => prev.map((i) => ({ ...i, decisao: 'aprovada' })))}>
                      Todos são pontuais
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => setExtra((prev) => prev.map((i) => ({ ...i, decisao: 'reprovada' })))}>
                      Todos são recorrentes
                    </Button>
                  </div>
                </div>
                {extra.length === 0 ? (
                  <p className="table-empty">Nenhum extraordinário detectado.</p>
                ) : (
                  extra.map((item) => (
                    <EditorDespesa key={item.id} item={item} onChange={(p) => updateExtra(item.id, p)} />
                  ))
                )}
              </div>
            )}

            {aba === 'ordinarias' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
                  <div>
                    <h2 className="section-title">Gastos a revisar</h2>
                    <p className="section-desc">Esses itens podem ou não se repetir. Analise cada um e decida se entra na previsão do próximo ano.</p>
                  </div>
                  <div className="choice-row">
                    <Button size="sm" variant="secondary" onClick={() => setRevisar((prev) => prev.map((i) => ({ ...i, decisao: 'reprovada' })))}>
                      Todos são recorrentes
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => setRevisar((prev) => prev.map((i) => ({ ...i, decisao: 'aprovada' })))}>
                      Todos são pontuais
                    </Button>
                  </div>
                </div>
                {revisar.length === 0 ? (
                  <p className="table-empty">Nenhuma despesa ordinária pendente.</p>
                ) : (
                  revisar.map((item) => (
                    <EditorDespesa key={item.id} item={item} onChange={(p) => updateRevisar(item.id, p)} />
                  ))
                )}
              </div>
            )}

            {aba === 'inadimplentes' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
                  <div>
                    <h2 className="section-title">Inadimplência</h2>
                    <p className="section-desc">Apenas unidades com três ou mais meses consecutivos em atraso. Para cada unidade, entra somente a última taxa condominial vencida.</p>
                  </div>
                  <div className="choice-row">
                    <Button size="sm" variant="secondary" onClick={() => setInad((prev) => prev.map((i) => ({ ...i, decisao: 'abater' })))}>
                      Descontar todos da receita
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => setInad((prev) => prev.map((i) => ({ ...i, decisao: 'ignorar' })))}>
                      Não descontar nenhum
                    </Button>
                  </div>
                </div>
                {inad.length === 0 ? (
                  <div className="empty">
                    <p>✅ Nenhuma inadimplência registrada.</p>
                    <p style={{fontSize:14, color:'var(--text-secondary)', marginTop:4}}>
                      O condomínio está em dia. Esta aba pode ser ignorada.
                    </p>
                  </div>
                ) : (
                  inad.map((item) => (
                    <EditorInad key={item.id} item={item} onChange={(p) => updateInad(item.id, p)} />
                  ))
                )}
              </div>
            )}

            {aba === 'contas' && (
              <Card>
                <h2 className="section-title">Despesas por Grupo e Classe</h2>
                <p className="section-desc">
                  Veja cada lançamento que forma as contas. Apenas os itens marcados como gasto pontual são deduzidos da previsão.
                </p>
                <p className="audit-legend"><span className="audit-dot deducted" /> Deduzido da previsão <span className="audit-dot kept" /> Mantido na previsão</p>
                {contasPorGrupo.length === 0 ? (
                  <p className="table-empty">Nenhum lançamento disponível para esta sessão.</p>
                ) : (
                  <div className="audit-groups">
                    {contasPorGrupo.map(({ grupo, classes }, index) => {
                      const pagoGrupo = classes.reduce((total, classe) => total + classe.pago, 0)
                      const deduzidoGrupo = classes.reduce((total, classe) => total + classe.deduzido, 0)
                      return (
                        <details className="audit-group" key={grupo} open={index === 0}>
                          <summary>
                            <span><strong>{grupo}</strong><small>{classes.length} classe{classes.length === 1 ? '' : 's'}</small></span>
                            <span>{money(pagoGrupo)} pago · {money(deduzidoGrupo)} deduzido</span>
                          </summary>
                          <div className="audit-classes">
                            {classes.map(({ classe, itens, pago, deduzido }) => (
                              <section className="audit-class" key={classe}>
                                <div className="audit-class-header">
                                  <div><strong>{classe}</strong><small>{itens.length} lançamento{itens.length === 1 ? '' : 's'}</small></div>
                                  <div><span>Pago: {money(pago)}</span><span>Deduzido: {money(deduzido)}</span></div>
                                </div>
                                <div className="audit-table-wrap">
                                  <table className="audit-table">
                                    <thead><tr><th>Data</th><th>Descrição</th><th className="num">Valor pago</th><th>Status</th></tr></thead>
                                    <tbody>{itens.map((item) => (
                                      <tr key={item.id} className={item.deduzido ? 'is-deducted' : ''}>
                                        <td>{item.data || '—'}</td>
                                        <td><strong>{item.descricao || 'Sem descrição'}</strong>{item.motivo && <small>{item.motivo}</small>}</td>
                                        <td className="num">{money(item.valor_pago)}</td>
                                        <td><span className={`audit-status ${item.deduzido ? 'deducted' : item.status === 'Aguardando decisão' ? 'pending' : 'kept'}`}>{item.status}</span></td>
                                      </tr>
                                    ))}</tbody>
                                  </table>
                                </div>
                              </section>
                            ))}
                          </div>
                        </details>
                      )
                    })}
                  </div>
                )}
              </Card>
            )}
          </section>
        </div>
      </div>
      {modalGerarAberto && createPortal(
        <div className="info-modal-overlay" onClick={() => !gerando && setModalGerarAberto(false)}>
          <div className="info-modal-box gerar-modal" role="dialog" aria-modal="true" aria-labelledby="gerar-relatorio-titulo" onClick={(e) => e.stopPropagation()}>
            <div className="info-modal-header">
              <strong id="gerar-relatorio-titulo">Gerar relatório em PDF</strong>
              <button type="button" className="info-modal-close" onClick={() => setModalGerarAberto(false)} disabled={gerando} aria-label="Fechar">×</button>
            </div>
            <p className="gerar-modal-intro">Confirme as informações que serão usadas no relatório antes de baixar o PDF.</p>
            <label className="gerar-modal-field">
              <span>Aumento Previsto (Salários, Tarifas, Serviços)</span>
              <div><input type="number" className="inflacao-input" min={0} max={100} step={0.1} value={Number((inflacao * 100).toFixed(2))} onChange={e => { const pct = parseFloat(e.target.value); if (Number.isFinite(pct) && pct >= 0 && pct <= 100) setInflacao(pct / 100) }} aria-label="Percentual de aumento previsto" />%</div>
            </label>
            <label className="gerar-modal-field">
              <span>Último reajuste da taxa condominial</span>
              <input type="month" className="reajuste-input" value={ultimoReajuste} onChange={e => setUltimoReajuste(e.target.value)} aria-label="Mês e ano do último reajuste da taxa condominial" />
            </label>
            <fieldset className="gerar-modal-field gerar-modal-choice">
              <legend>Colocar fundo de reserva no relatório?</legend>
              <label><input type="radio" name="fundo-reserva" checked={comFundo} onChange={() => setComFundo(true)} /> Sim</label>
              <label><input type="radio" name="fundo-reserva" checked={!comFundo} onChange={() => setComFundo(false)} /> Não</label>
            </fieldset>
            <div className="gerar-modal-actions">
              <Button variant="secondary" onClick={() => setModalGerarAberto(false)} disabled={gerando}>Cancelar</Button>
              <Button variant="primary" onClick={handleGerar} disabled={gerando}>{gerando ? 'Gerando PDF...' : 'Confirmar e baixar PDF'}</Button>
            </div>
          </div>
        </div>,
        document.body,
      )}
    </>
  )
}
