import { useMemo, useState } from 'react'
import type { FluxoMensal, LinhaPrevisaoFinal, Sessao } from '../types'
import { urlDownload } from '../api'
import { money, signedMoney } from '../utils/format'
import { scoreSaude } from '../utils/scoring'
import { gerarInsights } from '../utils/insights'
import { explicarDespesa, explicarInad } from '../utils/explicacoes'
import Header from './ui/Header'
import Card from './ui/Card'
import Button from './ui/Button'
import NumberBlock from './ui/NumberBlock'
import TabBar from './ui/TabBar'
import DataTable from './ui/DataTable'

type Visao = 'anual' | 'mensal'
type AbaResultado = 'executivo' | 'previsao' | 'decisoes' | 'auditoria'

/* ─── helpers ─────────────────────────── */

function norm(s: string) {
  return s
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
}

function isTotal(label: string) {
  const n = norm(label).trim()
  return (
    n === 'total' ||
    n.includes('subtotal') ||
    n.includes('saldo') ||
    n.includes('deficit') ||
    n.includes('superavit') ||
    n.includes('inflacao')
  )
}

function isNotaFinal(label: string) {
  const n = norm(label).trim()
  return n.includes('consideracoes importantes') || n.startsWith('1) para o calculo')
}

function fallbackRows(sessao: Sessao): LinhaPrevisaoFinal[] {
  const r = sessao.resumo
  const inflacao = r.inflacao || 0
  const saldo = r.receita_anual - r.total_previsto
  return [
    { row: 9, label: 'RECEITAS', anual: 'VALOR MENSAL', rateio: null, mensal: null },
    { row: 10, label: 'Receita média do período', anual: r.receita_mensal, rateio: null, mensal: null },
    { row: 19, label: 'TOTAL', anual: r.receita_mensal, rateio: null, mensal: null },
    { row: 21, label: 'DESPESAS', anual: 'VALOR MENSAL', rateio: null, mensal: null },
    { row: 47, label: 'SUBTOTAL', anual: r.subtotal / 12, rateio: null, mensal: null },
    { row: 48, label: `PREVISÃO DE INFLAÇÃO - ${(inflacao * 100).toFixed(1)}%`, anual: (r.subtotal * inflacao) / 12, rateio: null, mensal: null },
    { row: 50, label: 'TOTAL', anual: r.total_previsto / 12, rateio: null, mensal: null },
    { row: 52, label: saldo < 0 ? 'SALDO (DÉFICIT)' : 'SALDO (SUPERÁVIT)', anual: saldo / 12, rateio: null, mensal: null },
  ]
}

function valorMensal(row: LinhaPrevisaoFinal) {
  if (typeof row.anual === 'number') return row.anual
  if (typeof row.mensal === 'number') return row.mensal
  if (typeof row.rateio === 'number') return row.rateio
  return 0
}

function valorPorVisao(row: LinhaPrevisaoFinal, visao: Visao) {
  const m = valorMensal(row)
  return visao === 'anual' ? m * 12 : m
}

function agruparLinhas(linhas: { grupo: string; final: number }[]) {
  const mapa = new Map<string, number>()
  linhas.forEach((l) => {
    mapa.set(l.grupo || 'Outros', (mapa.get(l.grupo) ?? 0) + (l.final || 0))
  })
  return [...mapa.entries()]
    .map(([label, value]) => ({ label, value }))
    .filter((i) => Math.abs(i.value) > 0.005)
    .sort((a, b) => b.value - a.value)
}

function pct(part: number, total: number) {
  return total > 0 ? Math.max(0, Math.min(100, (part / total) * 100)) : 0
}

/* ─── sub-componentes ─────────────────── */

function SectionTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <h2 className="section-title">{title}</h2>
      {subtitle && <p className="section-desc">{subtitle}</p>}
    </div>
  )
}

function MonthlyChart({ data }: { data: FluxoMensal[] }) {
  const max = Math.max(...data.map((i) => Math.max(i.receita, i.despesa)), 1)
  const piorMes = [...data].sort((a, b) => a.saldo - b.saldo)[0]
  return (
    <div>
      <div className="monthly-chart" role="img" aria-label="Receitas e despesas por mês">
        {data.map((item) => (
          <div className="month-col" key={item.mes}>
            <div className="month-bars">
              <i className="revenue" style={{ height: `${Math.max(4, (item.receita / max) * 100)}%` }} />
              <i className="expense" style={{ height: `${Math.max(4, (item.despesa / max) * 100)}%` }} />
            </div>
            <span>{item.mes}</span>
          </div>
        ))}
      </div>
      <div className="monthly-legend">
        <span>
          <i className="revenue" /> Receita
        </span>
        <span>
          <i className="expense" /> Despesa
        </span>
        {piorMes && <strong>Maior pressão: {piorMes.mes} ({signedMoney(piorMes.saldo)})</strong>}
      </div>
    </div>
  )
}

function ResultTable({
  rows,
  valueFor,
  empty,
}: {
  rows: LinhaPrevisaoFinal[]
  valueFor: (row: LinhaPrevisaoFinal) => number
  empty: string
}) {
  const visible = rows.filter((row) => Math.abs(valueFor(row)) > 0.005)
  if (visible.length === 0) return <p className="table-empty">{empty}</p>

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Conta</th>
            <th className="num">Valor</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((row) => (
            <tr key={`${row.row}-${row.label}`}>
              <td>{row.label}</td>
              <td className="num">{money(valueFor(row))}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TotalLine({ label, value, strong }: { label: string; value: number; strong?: boolean }) {
  return (
    <div className={`total-line ${strong ? 'strong' : ''}`}>
      <span>{label}</span>
      <strong>{money(value)}</strong>
    </div>
  )
}

/* ─── tela principal ──────────────────── */

export default function TelaResultado({ sessao, onVoltar }: { sessao: Sessao; onVoltar: () => void }) {
  const [visao, setVisao] = useState<Visao>('mensal')
  const [aba, setAba] = useState<AbaResultado>('executivo')
  const [mostrarDetalhes, setMostrarDetalhes] = useState(false)

  const rows = sessao.previsao_final?.length ? sessao.previsao_final : fallbackRows(sessao)
  const fluxoMensal = sessao.fluxo_mensal ?? []

  const receitas = rows.filter(
    (r) => r.row >= 10 && r.row <= 20 && r.label && !isTotal(r.label) && !isNotaFinal(r.label),
  )
  const despesas = rows.filter(
    (r) => r.row >= 22 && r.row <= 80 && r.label && !isTotal(r.label) && !isNotaFinal(r.label),
  )
  const totalReceitasMensal =
    receitas.reduce((s, r) => s + valorMensal(r), 0) || sessao.resumo.receita_mensal
  const totalDespesasMensal = sessao.resumo.total_previsto / 12

  const receitaAtual = visao === 'anual' ? totalReceitasMensal * 12 : totalReceitasMensal
  const despesaAtual = visao === 'anual' ? totalDespesasMensal * 12 : totalDespesasMensal
  const impactoInadMensal = sessao.resumo.impacto_receita_mensal ?? 0
  const impactoInadAtual = visao === 'anual' ? impactoInadMensal * 12 : impactoInadMensal
  const receitaLiquidaAtual = receitaAtual - impactoInadAtual
  const saldoAjustado = receitaAtual - impactoInadAtual - despesaAtual
  const sinalSaldo = saldoAjustado < 0 ? 'Déficit ajustado' : 'Superávit ajustado'
  const tipoResultado = saldoAjustado < 0 ? 'DÉFICIT' : 'SUPERÁVIT'

  const grupos = useMemo(
    () => agruparLinhas(sessao.linhas_contas.map((l) => ({ grupo: l.grupo, final: l.final }))),
    [sessao.linhas_contas],
  )
  const totalGrupo = grupos.reduce((s, g) => s + g.value, 0)

  const saude = scoreSaude(
    sessao.resumo.receita_anual,
    sessao.resumo.total_previsto,
    impactoInadMensal * 12,
  )

  const removido =
    sessao.extraordinarias.filter((i) => i.decisao === 'aprovada').length +
    sessao.revisar.filter((i) => i.decisao === 'aprovada').length
  const mantido =
    sessao.extraordinarias.filter((i) => i.decisao === 'reprovada').length +
    sessao.revisar.filter((i) => i.decisao === 'reprovada').length

  const decisoesDespesa = [...sessao.extraordinarias, ...sessao.revisar]
    .filter((i) => i.decisao !== 'pendente')
    .map((i) => ({
      tipo: i.decisao === 'aprovada' ? 'Removido' : 'Mantido',
      conta: i.classe,
      grupo: i.grupo,
      valor: i.valor_editado ?? i.valor,
      origem: i.origem,
      motivo: i.nota || i.motivo || 'Sem nota manual',
      explicacao: explicarDespesa(i),
    }))

  const decisoesInad = sessao.inadimplencia.map((i) => ({
    tipo: i.decisao === 'abater' ? 'Abatido' : 'Ignorado',
    conta: i.unidade,
    grupo: i.classe,
    valor: i.valor_editado ?? i.valor,
    origem: i.critica ? 'Crítica' : 'Recente',
    motivo: i.nota || `${i.meses_atraso} mês(es) em atraso`,
    explicacao: explicarInad(i),
  }))

  const trilha = [...decisoesDespesa, ...decisoesInad]

  const insights = gerarInsights({
    saldoAjustado,
    receitaAtual,
    despesaAtual,
    impactoInadMensal,
    removido,
    mantido,
    grupos,
    linhas: sessao.linhas_contas,
    fluxoMensal,
  })

  const tabs: { id: AbaResultado; label: string; count?: number }[] = [
    { id: 'executivo', label: 'Resumo' },
    { id: 'previsao', label: 'Previsão', count: despesas.length + receitas.length },
    { id: 'decisoes', label: 'Decisões', count: trilha.length },
    { id: 'auditoria', label: 'Memória', count: sessao.linhas_contas.length },
  ]

  const auditoriaColumns = [
    { key: 'grupo', header: 'Grupo', render: (r: Record<string, unknown>) => r.grupo as string },
    { key: 'classe', header: 'Conta', render: (r: Record<string, unknown>) => r.classe as string },
    { key: 'base', header: 'Base', align: 'right' as const, render: (r: Record<string, unknown>) => money(r.base as number) },
    { key: 'deducao', header: 'Dedução', align: 'right' as const, render: (r: Record<string, unknown>) => money(r.deducao as number) },
    { key: 'final', header: 'Final', align: 'right' as const, render: (r: Record<string, unknown>) => money(r.final as number) },
    { key: 'regra', header: 'Regra', render: (r: Record<string, unknown>) => r.regra as string },
  ]

  return (
    <>
      <Header onHome={onVoltar}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <div className="tab-bar" style={{ margin: 0, border: 'none', background: 'transparent', padding: 0, gap: 2 }}>
            <button
              className={`tab-btn ${visao === 'mensal' ? 'active' : ''}`}
              onClick={() => setVisao('mensal')}
              style={visao === 'mensal' ? { background: 'rgba(255,255,255,0.2)', color: '#fff' } : { color: 'rgba(255,255,255,0.7)' }}
            >
              Mensal
            </button>
            <button
              className={`tab-btn ${visao === 'anual' ? 'active' : ''}`}
              onClick={() => setVisao('anual')}
              style={visao === 'anual' ? { background: 'rgba(255,255,255,0.2)', color: '#fff' } : { color: 'rgba(255,255,255,0.7)' }}
            >
              Anual
            </button>
          </div>
          <a href={urlDownload(sessao.sessao_id)} className="btn btn-primary btn-sm" style={{ background: '#fff', color: 'var(--accent)', borderColor: '#fff' }}>
            Baixar XLSX
          </a>
          <Button variant="ghost" onClick={onVoltar} style={{ color: 'rgba(255,255,255,0.8)', borderColor: 'rgba(255,255,255,0.3)' }}>
            Voltar
          </Button>
        </div>
      </Header>

      <div className="page page-wide">
        {/* hero */}
        <section className="result-hero">
          <div>
            <p className="section-label">Documento final</p>
            <h1>
              {sessao.nome_condominio} — {sessao.ano_previsao}
            </h1>
            <p>Relatório simples: números principais primeiro, detalhes quando necessário.</p>
          </div>
        </section>

        {/* KPIs */}
        <div className="number-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
          <NumberBlock label="Total previsto" value={money(despesaAtual)} />
          <NumberBlock label="Receita" value={money(receitaAtual)} />
          <NumberBlock label="Inadimplência" value={money(impactoInadAtual)} />
          <NumberBlock
            label={sinalSaldo}
            value={money(Math.abs(saldoAjustado))}
            variant={saldoAjustado < 0 ? 'negative' : 'positive'}
          />
        </div>

        {/* saúde financeira */}
        <div className="health-bar">
          <div className={`health-dot ${saude.classe}`} />
          <div className="health-info">
            <strong>Saúde financeira: {saude.label}</strong>
            <p>Nota {saude.score}/100 — considera despesas, receita e inadimplência.</p>
          </div>
          <label className="detail-toggle">
            <input
              type="checkbox"
              checked={mostrarDetalhes}
              onChange={(e) => setMostrarDetalhes(e.target.checked)}
            />
            <span>Mostrar detalhes</span>
          </label>
        </div>

        {/* tabs */}
        <TabBar tabs={tabs} active={aba} onChange={(id) => setAba(id as AbaResultado)} />

        {/* aba: executivo */}
        {aba === 'executivo' && (
          <div className="result-grid">
            <Card>
              <SectionTitle title="Conclusão" subtitle="Leitura objetiva para apresentação." />
              <div className="conclusion">
                <strong>
                  {saldoAjustado < 0 ? 'Atenção: orçamento em déficit' : 'Cenário com superávit'}
                </strong>
                <p>
                  A previsão usa a média dos últimos 12 meses, separa eventos pontuais da rotina e
                  trata a inadimplência como redução de receita. O resultado final é{' '}
                  <b>{tipoResultado}</b>.
                </p>
              </div>
            </Card>

            <Card>
              <SectionTitle title="Insights" subtitle="Pontos que merecem atenção." />
              <ul className="insight-list">
                {insights.map((item, idx) => (
                  <li key={idx}>{item}</li>
                ))}
              </ul>
            </Card>

            <Card className="full">
              <SectionTitle title="Quadro de leitura" subtitle="Como o resultado foi formado." />
              <table className="summary-table">
                <tbody>
                  <tr>
                    <td>Receita prevista</td>
                    <td>{money(receitaAtual)}</td>
                  </tr>
                  <tr>
                    <td>(−) Inadimplência considerada</td>
                    <td>{money(impactoInadAtual)}</td>
                  </tr>
                  <tr>
                    <td>= Receita líquida estimada</td>
                    <td>{money(receitaLiquidaAtual)}</td>
                  </tr>
                  <tr>
                    <td>(−) Total previsto de despesas</td>
                    <td>{money(despesaAtual)}</td>
                  </tr>
                  <tr>
                    <td>= {tipoResultado}</td>
                    <td>{signedMoney(saldoAjustado)}</td>
                  </tr>
                </tbody>
              </table>
            </Card>

            {mostrarDetalhes && fluxoMensal.length > 0 && (
              <Card className="full">
                <SectionTitle title="Evolução mensal" subtitle="Receitas e despesas extraídas do balanço." />
                <MonthlyChart data={fluxoMensal} />
              </Card>
            )}

            {mostrarDetalhes && (
              <Card className="full">
                <SectionTitle title="Composição das despesas" subtitle="Maiores grupos considerados." />
                <div className="bar-list">
                  {grupos.slice(0, 8).map((g) => (
                    <div key={g.label}>
                      <div className="bar-item-header">
                        <strong>{g.label}</strong>
                        <span>{money(g.value / 12)}/mês</span>
                      </div>
                      <div className="bar-track">
                        <div className="bar-fill" style={{ width: `${pct(g.value, totalGrupo)}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}
          </div>
        )}

        {/* aba: previsão */}
        {aba === 'previsao' && (
          <div className="result-grid">
            <Card>
              <SectionTitle title="Receitas" />
              <ResultTable rows={receitas} valueFor={(r) => valorPorVisao(r, visao)} empty="Nenhuma receita detalhada." />
              <TotalLine label="Total receitas" value={receitaAtual} />
            </Card>
            <Card>
              <SectionTitle title="Despesas" />
              <ResultTable rows={despesas} valueFor={(r) => valorPorVisao(r, visao)} empty="Nenhuma despesa detalhada." />
              <TotalLine label="Total previsto" value={despesaAtual} strong />
            </Card>
          </div>
        )}

        {/* aba: decisões */}
        {aba === 'decisoes' && (
          <Card>
            <SectionTitle title="O que foi mexido" subtitle="Explicação de cada decisão tomada." />
            {trilha.length === 0 ? (
              <p className="table-empty">Nenhuma decisão manual registrada.</p>
            ) : (
              <div className="ledger-grid">
                {trilha.map((item, idx) => (
                  <article
                    className={`ledger-item ${norm(item.tipo)}`}
                    key={`${item.tipo}-${item.conta}-${idx}`}
                  >
                    <div className="ledger-num">{idx + 1}</div>
                    <div>
                      <div className="ledger-top">
                        <strong>{item.tipo}</strong>
                        <span>{money(item.valor)}</span>
                      </div>
                      <h3>{item.conta}</h3>
                      <p className="ledger-group">{item.grupo}</p>
                      <div className="ledger-explanation">
                        <p>{item.explicacao.resumo}</p>
                        {mostrarDetalhes &&
                          item.explicacao.evidencias.map((ev, evIdx) => (
                            <small key={evIdx}>{ev}</small>
                          ))}
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </Card>
        )}

        {/* aba: auditoria */}
        {aba === 'auditoria' && (
          <Card>
            <SectionTitle title="Memória de cálculo" subtitle="Tabela técnica para conferência." />
            {!mostrarDetalhes ? (
              <p className="table-empty">Ative "Mostrar detalhes" para ver a tabela completa.</p>
            ) : (
              <DataTable
                columns={auditoriaColumns}
                rows={sessao.linhas_contas as unknown as Record<string, unknown>[]}
              />
            )}
          </Card>
        )}
      </div>
    </>
  )
}
