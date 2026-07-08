import { useMemo, useState } from 'react'
import type { ItemInad, ItemRevisao, LinhaConta, Sessao } from '../types'
import { useDecisoes } from '../hooks/useDecisoes'
import { gerarDocumento } from '../api'
import { money } from '../utils/format'
import Header from './ui/Header'
import Card from './ui/Card'
import Button from './ui/Button'
import Badge from './ui/Badge'
import NumberBlock from './ui/NumberBlock'
import TabBar from './ui/TabBar'
import DataTable from './ui/DataTable'
import InfoModal from './ui/InfoModal'

/* ─── helpers ─────────────────────────── */

type Aba = 'relatorio' | 'extraordinarios' | 'ordinarias' | 'inadimplentes' | 'contas'

function parseValor(value: string) {
  const n = Number(value.replace(',', '.'))
  return Number.isFinite(n) ? n : 0
}

function valorAtual(item: { valor: number; valor_editado?: number }) {
  return Number.isFinite(item.valor_editado) ? Number(item.valor_editado) : item.valor
}

function agruparPorGrupo(linhas: LinhaConta[]) {
  const grupos = new Map<string, { base: number; deducao: number; final: number; contas: number }>()
  linhas.forEach((l) => {
    const g = grupos.get(l.grupo) ?? { base: 0, deducao: 0, final: 0, contas: 0 }
    g.base += l.base
    g.deducao += l.deducao
    g.final += l.final
    g.contas += 1
    grupos.set(l.grupo, g)
  })
  return [...grupos.entries()].sort((a, b) => b[1].final - a[1].final)
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
  onGerado,
}: {
  sessao: Sessao
  onVoltar: () => void
  onGerado: (s: Sessao) => void
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
  } = useDecisoes(sessao)

  const [aba, setAba] = useState<Aba>('relatorio')
  const [gerando, setGerando] = useState(false)
  const [erro, setErro] = useState('')

  const pendentes =
    extra.filter((i) => i.decisao === 'pendente').length +
    revisar.filter((i) => i.decisao === 'pendente').length

  const removidos = [...extra, ...revisar].filter((i) => i.decisao === 'aprovada')
  const saldo = sessao.resumo.receita_anual - vivo.total
  const grupos = useMemo(() => agruparPorGrupo(sessao.linhas_contas), [sessao.linhas_contas])
  const contasComDeducao = sessao.linhas_contas.filter((l) => Math.abs(l.deducao) > 0.005)

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
      await gerarDocumento(sessao.sessao_id, buildPayload())
      const r = await fetch(`/api/sessao/${sessao.sessao_id}`)
      if (!r.ok) throw new Error(`Erro ${r.status} ao carregar sessao gerada`)
      onGerado(await r.json())
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
    { id: 'contas', label: 'Contas calculadas', count: sessao.linhas_contas.length },
  ]

  const contasColumns = [
    { key: 'grupo', header: 'Grupo', render: (r: Record<string, unknown>) => r.grupo as string },
    { key: 'classe', header: 'Conta', render: (r: Record<string, unknown>) => r.classe as string },
    { key: 'base', header: 'Base', align: 'right' as const, render: (r: Record<string, unknown>) => money(r.base as number) },
    { key: 'deducao', header: 'Dedução', align: 'right' as const, render: (r: Record<string, unknown>) => money(r.deducao as number) },
    { key: 'final', header: 'Final', align: 'right' as const, render: (r: Record<string, unknown>) => money(r.final as number) },
    { key: 'regra', header: 'Regra', render: (r: Record<string, unknown>) => r.regra as string },
  ]

  // Versao simplificada p/ o card "Gastos deduzidos ou provisionados": sem a
  // coluna Regra (texto tecnico) — a explicacao do calculo vira um (?) fixo
  // no cabecalho, em vez de uma frase tecnica por linha.
  const deducoesColumns = [
    { key: 'grupo', header: 'Grupo', render: (r: Record<string, unknown>) => r.grupo as string },
    { key: 'classe', header: 'Conta', render: (r: Record<string, unknown>) => r.classe as string },
    { key: 'base', header: 'Base', align: 'right' as const, render: (r: Record<string, unknown>) => money(r.base as number) },
    {
      key: 'deducao',
      align: 'right' as const,
      header: (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          Dedução
          <InfoModal
            titulo="Como a dedução é calculada"
            texto="Valor tirado da despesa porque identificamos um gasto fora do comum (uma obra, um conserto pontual, uma rescisão) ou porque uma parte foi separada para outra finalidade. O que sobra (Final) é o que entra na previsão do próximo ano."
          />
        </span>
      ),
      render: (r: Record<string, unknown>) => money(r.deducao as number),
    },
    { key: 'final', header: 'Final', align: 'right' as const, render: (r: Record<string, unknown>) => money(r.final as number) },
  ]

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
              onClick={handleGerar}
              disabled={gerando || pendentes > 0}
            >
              {gerando ? 'Gerando...' : 'Gerar documento'}
            </Button>
          </div>
        </section>

        {erro && <div className="alert-error">{erro}</div>}

        {/* KPIs */}
        <div className="number-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
          <NumberBlock label="Valor transportado" value={money(sessao.resumo.base_total)} />
          <NumberBlock label="Removido na revisão" value={money(aoVivo.dedExtra + aoVivo.dedRev)} />
          <NumberBlock
            label="Total previsto"
            value={calculando ? '...' : money(vivo.total)}
          />
          <NumberBlock
            label="Saldo estimado"
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
              <div className="calc-row inflacao-row">
                <span>
                  Inflação{' '}
                  <input
                    type="number"
                    className="inflacao-input"
                    min={0}
                    max={100}
                    step={0.1}
                    value={Number((inflacao * 100).toFixed(2))}
                    onChange={e => {
                      const pct = parseFloat(e.target.value)
                      if (Number.isFinite(pct) && pct >= 0 && pct <= 100) setInflacao(pct / 100)
                    }}
                    aria-label="Percentual de inflação"
                  />%
                </span>
                <strong>{money(vivo.total - vivo.subtotal)}</strong>
              </div>
              <div className="calc-row strong"><span>Total previsto</span><strong>{money(vivo.total)}</strong></div>
              <div className="calc-row"><span>Receita anual</span><strong>{money(sessao.resumo.receita_anual)}</strong></div>
              <div className="calc-row"><span>Impacto inad.</span><strong>{money(vivo.impacto)}/mês</strong></div>
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

                <Card>
                  <h2 className="section-title">Despesas por Grupo Resumidas</h2>
                  <div className="number-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
                    {grupos.map(([grupo, total]) => (
                      <div key={grupo} style={{ background: 'var(--bg)', borderRadius: 'var(--radius)', padding: 'var(--s-md)' }}>
                        <span style={{ display: 'block', fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.4px', color: 'var(--text-muted)', marginBottom: 4 }}>
                          {grupo}
                        </span>
                        <strong style={{ fontSize: 20, color: 'var(--text)' }}>{money(total.final)}</strong>
                        <small style={{ display: 'block', color: 'var(--text-secondary)', marginTop: 2 }}>
                          {total.contas} contas · dedução {money(total.deducao)}
                        </small>
                      </div>
                    ))}
                  </div>
                </Card>

                {contasComDeducao.length > 0 && (
                  <Card>
                    <h2 className="section-title">Gastos deduzidos ou provisionados</h2>
                    <DataTable
                      columns={deducoesColumns}
                      rows={contasComDeducao.slice(0, 12) as unknown as Record<string, unknown>[]}
                    />
                  </Card>
                )}
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
                    <p className="section-desc">Unidades com pagamento em atraso. Descontar da receita reduz o valor que o condomínio espera receber no próximo ano.</p>
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
                <h2 className="section-title">Contas calculadas</h2>
                <p className="section-desc">
                  Base anual por classe. Deduções e provisões vêm dos relatórios DESBAI/DESSIN.
                </p>
                <DataTable
                  columns={contasColumns}
                  rows={sessao.linhas_contas as unknown as Record<string, unknown>[]}
                />
              </Card>
            )}
          </section>
        </div>
      </div>
    </>
  )
}
