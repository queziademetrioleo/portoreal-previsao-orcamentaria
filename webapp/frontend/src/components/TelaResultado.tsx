import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { LinhaConta, LinhaPrevisaoFinal, Sessao } from '../types'
import { urlDownload } from '../api'

type Visao = 'anual' | 'mensal'
type AbaResultado = 'executivo' | 'previsao' | 'decisoes' | 'auditoria'

function fmt(v: number) {
  return v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function money(v: unknown) {
  return typeof v === 'number' ? `R$ ${fmt(v)}` : '—'
}

function norm(s: string) {
  return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
}

function isTotal(label: string) {
  const n = norm(label).trim()
  return n === 'total' || n.includes('subtotal') || n.includes('saldo') || n.includes('deficit') || n.includes('superavit') || n.includes('inflacao')
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
    { row: 48, label: `PREVISÃO DE INFLAÇÃO - ${(inflacao * 100).toFixed(1)} %`, anual: (r.subtotal * inflacao) / 12, rateio: null, mensal: null },
    { row: 50, label: 'TOTAL', anual: r.total_previsto / 12, rateio: null, mensal: null },
    { row: 52, label: saldo < 0 ? 'SALDO ( DÉFICIT )' : 'SALDO ( SUPERÁVIT )', anual: saldo / 12, rateio: null, mensal: null },
  ]
}

function valorMensal(row: LinhaPrevisaoFinal) {
  if (typeof row.anual === 'number') return row.anual
  if (typeof row.mensal === 'number') return row.mensal
  if (typeof row.rateio === 'number') return row.rateio
  return 0
}

function valorPorVisao(row: LinhaPrevisaoFinal, visao: Visao) {
  const mensal = valorMensal(row)
  return visao === 'anual' ? mensal * 12 : mensal
}

function agruparLinhas(linhas: LinhaConta[]) {
  const mapa = new Map<string, number>()
  linhas.forEach(l => {
    const atual = mapa.get(l.grupo) ?? 0
    mapa.set(l.grupo || 'Outros', atual + (l.final || 0))
  })
  return [...mapa.entries()]
    .map(([label, value]) => ({ label, value }))
    .filter(i => Math.abs(i.value) > 0.005)
    .sort((a, b) => b.value - a.value)
}

function pct(part: number, total: number) {
  return total > 0 ? Math.max(0, Math.min(100, (part / total) * 100)) : 0
}

function scoreSaude(saldoAjustado: number, receitaAnual: number, impactoInadAnual: number, totalPrevisto: number) {
  if (receitaAnual <= 0) return { score: 0, label: 'Sem receita', classe: 'danger' }
  const margem = saldoAjustado / receitaAnual
  const inadPct = impactoInadAnual / receitaAnual
  const pressao = totalPrevisto / receitaAnual
  let score = 72 + margem * 120 - inadPct * 160 - Math.max(0, pressao - 1) * 80
  score = Math.round(Math.max(0, Math.min(100, score)))
  if (score >= 75) return { score, label: 'Saúde confortável', classe: 'success' }
  if (score >= 50) return { score, label: 'Atenção operacional', classe: 'warn' }
  return { score, label: 'Risco de déficit', classe: 'danger' }
}

function explicarDespesa(item: {
  decisao: 'aprovada' | 'reprovada' | 'pendente'
  origem: string
  motivo?: string
  nota?: string
  descricao?: string
  n_meses?: number | null
  explicacao?: { resumo: string; evidencias: string[] }
}) {
  if (item.explicacao?.resumo) return item.explicacao
  const base = item.decisao === 'aprovada'
    ? 'Foi retirada da previsão porque a análise classificou o lançamento como não recorrente ou extraordinário.'
    : 'Foi mantida na previsão porque a revisão entendeu que o gasto compõe a rotina do condomínio.'
  const evidencias = []
  if (item.origem === 'IA') evidencias.push('classificação sugerida pela IA')
  if (item.origem === 'Regra') evidencias.push('classificação por regra do motor')
  if (item.n_meses !== null && item.n_meses !== undefined) {
    evidencias.push(`frequência observada: ${item.n_meses}/12 meses`)
  }
  const texto = `${item.descricao || ''} ${item.motivo || ''}`
  const parcela = texto.match(/parcela\s+(\d+)\s*(?:\/|de)\s*(\d+)/i)
  if (parcela) evidencias.push(`parcela ${parcela[1]} de ${parcela[2]} identificada na descrição`)
  if (item.nota) evidencias.push(`nota humana: ${item.nota}`)
  if (item.motivo) evidencias.push(`motivo técnico: ${item.motivo}`)
  return {
    resumo: base,
    evidencias: evidencias.length ? evidencias : ['sem evidência adicional registrada'],
  }
}

function explicarInad(item: {
  decisao: 'abater' | 'ignorar'
  critica: boolean
  meses_atraso: number
  nota?: string
  explicacao?: { resumo: string; evidencias: string[] }
}) {
  if (item.explicacao?.resumo) return item.explicacao
  const resumo = item.decisao === 'abater'
    ? 'Foi abatida da leitura de receita porque reduz a arrecadação provável disponível.'
    : 'Foi mantida fora do abatimento porque a revisão não considerou o atraso suficiente para reduzir a receita projetada.'
  const evidencias = [
    item.critica ? 'inadimplência crítica' : 'inadimplência recente',
    `${item.meses_atraso} mês(es) em atraso`,
  ]
  if (item.nota) evidencias.push(`nota humana: ${item.nota}`)
  return { resumo, evidencias }
}

export default function TelaResultado({ sessao, onVoltar }: {
  sessao: Sessao
  onVoltar: () => void
}) {
  const [visao, setVisao] = useState<Visao>('mensal')
  const [aba, setAba] = useState<AbaResultado>('executivo')
  const [mostrarDetalhes, setMostrarDetalhes] = useState(false)
  const rows = (sessao.previsao_final?.length ? sessao.previsao_final : fallbackRows(sessao))

  const receitas = rows.filter(r => r.row >= 10 && r.row <= 20 && r.label && !isTotal(r.label) && !isNotaFinal(r.label))
  const despesas = rows.filter(r => r.row >= 22 && r.row <= 80 && r.label && !isTotal(r.label) && !isNotaFinal(r.label))
  const totalReceitasMensal = receitas.reduce((s, r) => s + valorMensal(r), 0) || sessao.resumo.receita_mensal
  const totalDespesasMensal = sessao.resumo.total_previsto / 12
  const receitaAtual = visao === 'anual' ? totalReceitasMensal * 12 : totalReceitasMensal
  const despesaAtual = visao === 'anual' ? totalDespesasMensal * 12 : totalDespesasMensal
  const impactoInadMensal = sessao.resumo.impacto_receita_mensal ?? 0
  const impactoInadAtual = visao === 'anual' ? impactoInadMensal * 12 : impactoInadMensal
  const saldoAjustado = receitaAtual - impactoInadAtual - despesaAtual
  const sinalSaldo = saldoAjustado < 0 ? 'Déficit ajustado' : 'Superávit ajustado'
  const grupos = useMemo(() => agruparLinhas(sessao.linhas_contas), [sessao.linhas_contas])
  const totalGrupo = grupos.reduce((s, g) => s + g.value, 0)
  const saude = scoreSaude(
    sessao.resumo.receita_anual - (impactoInadMensal * 12) - sessao.resumo.total_previsto,
    sessao.resumo.receita_anual,
    impactoInadMensal * 12,
    sessao.resumo.total_previsto,
  )
  const removido = sessao.extraordinarias.filter(i => i.decisao === 'aprovada').length + sessao.revisar.filter(i => i.decisao === 'aprovada').length
  const mantido = sessao.extraordinarias.filter(i => i.decisao === 'reprovada').length + sessao.revisar.filter(i => i.decisao === 'reprovada').length
  const decisoesDespesa = [...sessao.extraordinarias, ...sessao.revisar]
    .filter(i => i.decisao !== 'pendente')
    .map(i => ({
      tipo: i.decisao === 'aprovada' ? 'Removido' : 'Mantido',
      conta: i.classe,
      grupo: i.grupo,
      valor: i.valor_editado ?? i.valor,
      origem: i.origem,
      motivo: i.nota || i.motivo || 'Sem nota manual',
      explicacao: explicarDespesa(i),
    }))
  const decisoesInad = sessao.inadimplencia.map(i => ({
    tipo: i.decisao === 'abater' ? 'Abatido' : 'Ignorado',
    conta: i.unidade,
    grupo: i.classe,
    valor: i.valor_editado ?? i.valor,
    origem: i.critica ? 'Crítica' : 'Recente',
    motivo: i.nota || `${i.meses_atraso} mês(es) em atraso`,
    explicacao: explicarInad(i),
  }))
  const trilha = [...decisoesDespesa, ...decisoesInad]

  const abas: { id: AbaResultado; label: string; count?: number }[] = [
    { id: 'executivo', label: 'Resumo Executivo' },
    { id: 'previsao', label: 'PREVISÃO (2)', count: despesas.length + receitas.length },
    { id: 'decisoes', label: 'O que foi mexido', count: trilha.length },
    { id: 'auditoria', label: 'Memória de cálculo', count: sessao.linhas_contas.length },
  ]

  return (
    <>
      <header className="app-header">
        <a href="/" className="logo" onClick={e => { e.preventDefault(); onVoltar() }}>
          <img src="/assets/logo.png" alt="" /> Previsão Orçamentária
        </a>
        <button className="btn btn-ghost btn-sm" onClick={onVoltar}>Voltar</button>
      </header>

      <main className="executive-page">
        <section className="executive-hero">
          <div>
            <div className="eyebrow">Documento final · PREVISÃO (2)</div>
            <h1>{sessao.nome_condominio} <span>{sessao.ano_previsao}</span></h1>
            <p>
              Relatório simples, com os números principais primeiro e a explicação completa disponível quando necessário.
            </p>
          </div>
          <div className="executive-actions">
            <div className="segmented">
              <button className={visao === 'mensal' ? 'active' : ''} onClick={() => setVisao('mensal')}>Mensal</button>
              <button className={visao === 'anual' ? 'active' : ''} onClick={() => setVisao('anual')}>Anual</button>
            </div>
            <a href={urlDownload(sessao.sessao_id)} className="btn btn-primary">
              Baixar XLSX
            </a>
          </div>
        </section>

        <section className="minimal-summary">
          <div className="minimal-main-number">
            <span>Total previsto</span>
            <strong>{money(despesaAtual)}</strong>
            <small>{visao === 'mensal' ? 'por mês' : 'por ano'}</small>
          </div>
          <div className="minimal-number">
            <span>Receita</span>
            <strong>{money(receitaAtual)}</strong>
          </div>
          <div className="minimal-number">
            <span>Inadimplência</span>
            <strong>{money(impactoInadAtual)}</strong>
          </div>
          <div className={`minimal-number ${saldoAjustado < 0 ? 'negative' : 'positive'}`}>
            <span>{sinalSaldo}</span>
            <strong>{money(Math.abs(saldoAjustado))}</strong>
          </div>
        </section>

        <section className="minimal-health">
          <div className={`health-dot ${saude.classe}`} />
          <div>
            <span>Saúde financeira: {saude.label}</span>
            <p>Nota {saude.score}/100, considerando despesas, receita e inadimplência.</p>
          </div>
          <label className="detail-toggle">
            <input type="checkbox" checked={mostrarDetalhes} onChange={e => setMostrarDetalhes(e.target.checked)} />
            <span>Mostrar explicações detalhadas</span>
          </label>
        </section>

        {mostrarDetalhes && (
          <section className="exec-score-grid compact">
            <div className={`health-card ${saude.classe}`}>
              <div className="health-ring" style={{ '--score': `${saude.score}%` } as React.CSSProperties}>
                <strong>{saude.score}</strong>
                <span>/100</span>
              </div>
              <div>
                <span>Saúde financeira</span>
                <h2>{saude.label}</h2>
                <p>Considera saldo, pressão das despesas e impacto de inadimplência.</p>
              </div>
            </div>
            <Kpi label={`Receita ${visao}`} value={receitaAtual} />
            <Kpi label={`Despesa ${visao}`} value={despesaAtual} tone="ink" />
            <Kpi label="Impacto inadimplência" value={impactoInadAtual} tone="warn" />
            <Kpi label={sinalSaldo} value={Math.abs(saldoAjustado)} tone={saldoAjustado < 0 ? 'danger' : 'success'} />
          </section>
        )}

        <nav className="minimal-tabs" aria-label="Abas do resultado">
          {abas.map(item => (
            <button key={item.id} className={aba === item.id ? 'active' : ''} onClick={() => setAba(item.id)}>
              {item.label}
              {typeof item.count === 'number' && <span>{item.count}</span>}
            </button>
          ))}
        </nav>

        {aba === 'executivo' && (
          <section className="minimal-grid">
            <div className="minimal-card wide">
              <SectionTitle title="O que este resultado quer dizer" subtitle="Resumo direto para apresentação." />
              <p className="executive-copy clean">
                A previsão considera a média dos últimos 12 meses, separa gastos recorrentes dos eventos pontuais
                e mostra a inadimplência fora da despesa, porque ela afeta a receita disponível. O saldo ajustado é
                a leitura mais prática para decidir se a taxa atual cobre o orçamento previsto.
              </p>
            </div>

            <div className="minimal-card">
              <SectionTitle title="Revisão feita" subtitle="Intervenções antes da geração." />
              <div className="decision-stack">
                <MetricLine label="Removidos da previsão" value={String(removido)} />
                <MetricLine label="Mantidos como despesa" value={String(mantido)} />
                <MetricLine label="Inadimplências abatidas" value={String(sessao.inadimplencia.filter(i => i.decisao === 'abater').length)} />
              </div>
            </div>

            {mostrarDetalhes && (
              <div className="minimal-card wide">
                <SectionTitle title="Composição das despesas" subtitle="Os maiores grupos considerados." />
                <div className="bar-list monochrome">
                  {grupos.slice(0, 8).map(g => (
                    <div className="bar-item" key={g.label}>
                      <div><strong>{g.label}</strong><span>{money(g.value / 12)}/mês</span></div>
                      <div className="bar-track"><i style={{ width: `${pct(g.value, totalGrupo)}%` }} /></div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}

        {aba === 'previsao' && (
          <section className="result-grid executive-table-grid minimal-table-grid">
            <ResultCard title="Receitas">
              <ResultTable rows={receitas} valueFor={r => valorPorVisao(r, visao)} empty="Nenhuma receita detalhada." />
              <TotalLine label="Total receitas" value={receitaAtual} />
            </ResultCard>
            <ResultCard title="Despesas">
              <ResultTable rows={despesas} valueFor={r => valorPorVisao(r, visao)} empty="Nenhuma despesa detalhada." />
              <TotalLine label="Total previsto" value={despesaAtual} strong />
            </ResultCard>
          </section>
        )}

        {aba === 'decisoes' && (
          <section className="minimal-card">
            <SectionTitle title="O que foi mexido" subtitle="Explicação simples de cada decisão." />
            {trilha.length === 0 ? (
              <p className="result-empty">Nenhuma decisão manual registrada.</p>
            ) : (
              <div className="decision-ledger clean">
                {trilha.map((item, idx) => (
                  <article className={`ledger-item ${norm(item.tipo)}`} key={`${item.tipo}-${item.conta}-${idx}`}>
                    <div className="ledger-marker">{idx + 1}</div>
                    <div>
                      <div className="ledger-top">
                        <strong>{item.tipo}</strong>
                        <span>{money(item.valor)}</span>
                      </div>
                      <h3>{item.conta}</h3>
                      <p>{item.grupo}</p>
                      <div className="ledger-explanation">
                        <strong>{item.explicacao.resumo}</strong>
                        {mostrarDetalhes && item.explicacao.evidencias.map((ev, evIdx) => (
                          <small key={evIdx}>{ev}</small>
                        ))}
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        )}

        {aba === 'auditoria' && (
          <section className="minimal-card">
            <SectionTitle title="Memória de cálculo" subtitle="Tabela técnica para conferência completa." />
            <div>
              {!mostrarDetalhes && (
                <p className="audit-muted">
                  Ative “Mostrar explicações detalhadas” acima para ver a tabela completa.
                </p>
              )}
              {mostrarDetalhes && (
                <div className="audit-table-wrap">
                  <table className="result-table audit-table">
                    <thead>
                      <tr>
                        <th>Grupo</th>
                        <th>Conta</th>
                        <th className="num">Base</th>
                        <th className="num">Dedução</th>
                        <th className="num">Final</th>
                        <th>Regra</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sessao.linhas_contas.map((l, idx) => (
                        <tr key={`${l.grupo}-${l.classe}-${idx}`}>
                          <td>{l.grupo}</td>
                          <td>{l.classe}</td>
                          <td className="num">{money(l.base)}</td>
                          <td className="num">{money(l.deducao)}</td>
                          <td className="num">{money(l.final)}</td>
                          <td>{l.regra}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </section>
        )}
      </main>
    </>
  )
}

function Kpi({ label, value, tone }: { label: string; value: number; tone?: 'ink' | 'warn' | 'danger' | 'success' }) {
  return (
    <div className={`exec-kpi ${tone ?? ''}`}>
      <span>{label}</span>
      <strong>{money(value)}</strong>
    </div>
  )
}

function SectionTitle({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="exec-section-title">
      <h2>{title}</h2>
      <p>{subtitle}</p>
    </div>
  )
}

function MetricLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-line">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function ResultCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="exec-card">
      <SectionTitle title={title} subtitle="Valores exibidos conforme a visão selecionada." />
      {children}
    </section>
  )
}

function ResultTable({ rows, valueFor, empty }: {
  rows: LinhaPrevisaoFinal[]
  valueFor: (row: LinhaPrevisaoFinal) => number
  empty: string
}) {
  const visible = rows.filter(row => Math.abs(valueFor(row)) > 0.005)
  if (!visible.length) return <p className="result-empty">{empty}</p>
  return (
    <div className="table-card">
      <table className="result-table">
        <thead>
          <tr>
            <th>Conta</th>
            <th className="num">Valor</th>
          </tr>
        </thead>
        <tbody>
          {visible.map(row => (
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
