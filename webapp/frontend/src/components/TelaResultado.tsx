import { useState } from 'react'
import type { ReactNode } from 'react'
import type { LinhaPrevisaoFinal, Sessao } from '../types'
import { urlDownload } from '../api'

type Visao = 'anual' | 'mensal'

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

function valorReceita(row: LinhaPrevisaoFinal, visao: Visao) {
  const mensal = typeof row.anual === 'number' ? row.anual : 0
  return visao === 'mensal' ? mensal : mensal * 12
}

function valorDespesa(row: LinhaPrevisaoFinal, visao: Visao) {
  if (visao === 'anual') return typeof row.anual === 'number' ? row.anual : 0
  if (typeof row.rateio === 'number') return row.rateio
  if (typeof row.mensal === 'number') return row.mensal
  return typeof row.anual === 'number' ? row.anual / 12 : 0
}

function valorTotal(row: LinhaPrevisaoFinal, visao: Visao) {
  if (visao === 'anual') return typeof row.anual === 'number' ? row.anual : 0
  if (norm(row.label).includes('inflacao')) {
    return typeof row.anual === 'number' ? row.anual / 12 : 0
  }
  if (typeof row.rateio === 'number') return row.rateio
  if (typeof row.mensal === 'number') return row.mensal
  return typeof row.anual === 'number' ? row.anual / 12 : 0
}

function fallbackRows(sessao: Sessao): LinhaPrevisaoFinal[] {
  const r = sessao.resumo
  const inflacao = r.inflacao || 0
  const saldo = r.receita_anual - r.total_previsto
  return [
    { row: 9, label: 'RECEITAS', anual: 'VALOR MENSAL', rateio: null, mensal: null },
    { row: 10, label: 'Receita média do período', anual: r.receita_mensal, rateio: null, mensal: null },
    { row: 19, label: 'TOTAL', anual: r.receita_mensal, rateio: null, mensal: null },
    { row: 21, label: 'DESPESAS', anual: 'VALOR ANUAL', rateio: null, mensal: null },
    { row: 47, label: 'SUBTOTAL', anual: r.subtotal, rateio: null, mensal: r.subtotal / 12 },
    { row: 48, label: `PREVISÃO DE INFLAÇÃO - ${(inflacao * 100).toFixed(1)} %`, anual: r.subtotal * inflacao, rateio: null, mensal: null },
    { row: 50, label: 'TOTAL', anual: r.total_previsto, rateio: r.total_previsto / 12, mensal: null },
    { row: 52, label: saldo < 0 ? 'SALDO ( DÉFICIT )' : 'SALDO ( SUPERÁVIT )', anual: saldo, rateio: saldo / 12, mensal: null },
  ]
}

export default function TelaResultado({ sessao, onVoltar }: {
  sessao: Sessao
  onVoltar: () => void
}) {
  const [visao, setVisao] = useState<Visao>('anual')
  const rows = (sessao.previsao_final?.length ? sessao.previsao_final : fallbackRows(sessao))

  const receitas = rows.filter(r => r.row >= 10 && r.row <= 18 && r.label && !isTotal(r.label))
  const totalReceitas = rows.find(r => r.row <= 20 && norm(r.label) === 'total')
  const despesas = rows.filter(r => r.row >= 22 && r.row <= 46 && r.label && !isTotal(r.label))
  const subtotal = rows.find(r => norm(r.label).includes('subtotal'))
  const inflacao = rows.find(r => norm(r.label).includes('inflacao'))
  const totalDespesas = rows.find(r => r.row > 20 && norm(r.label) === 'total')

  const totalReceitaValor = totalReceitas ? valorReceita(totalReceitas, visao) : sessao.resumo.receita_mensal * (visao === 'anual' ? 12 : 1)
  const totalDespesaValor = totalDespesas ? valorTotal(totalDespesas, visao) : sessao.resumo.total_previsto / (visao === 'mensal' ? 12 : 1)
  const saldoValor = totalReceitaValor - totalDespesaValor
  const sinalSaldo = saldoValor < 0 ? 'Déficit' : 'Superávit'

  return (
    <>
      <header className="app-header">
        <a href="/" className="logo" onClick={e => { e.preventDefault(); onVoltar() }}>
          <img src="/assets/logo.png" alt="" /> Previsão Orçamentária
        </a>
        <button className="btn btn-ghost btn-sm" onClick={onVoltar}>← Voltar</button>
      </header>

      <main className="container result-page">
        <div className="result-hero">
          <div>
            <div className="eyebrow">Documento final</div>
            <h1 className="title">{sessao.nome_condominio} — {sessao.ano_previsao}</h1>
            {sessao.resumo.periodo && (
              <p className="subtitle">Base: {sessao.resumo.periodo[0]} a {sessao.resumo.periodo[1]}</p>
            )}
          </div>
          <div className="segmented" aria-label="Alternar visão">
            <button className={visao === 'anual' ? 'active' : ''} onClick={() => setVisao('anual')}>Anual</button>
            <button className={visao === 'mensal' ? 'active' : ''} onClick={() => setVisao('mensal')}>Mensal</button>
          </div>
        </div>

        <div className="result-kpis">
          <Kpi label={`Receitas ${visao === 'anual' ? 'anuais' : 'mensais'}`} value={totalReceitaValor} />
          <Kpi label={`Despesas ${visao === 'anual' ? 'anuais' : 'mensais'}`} value={totalDespesaValor} emphasis />
          <Kpi label={sinalSaldo} value={Math.abs(saldoValor)} danger={saldoValor < 0} />
        </div>

        <section className="result-grid">
          <ResultCard title="Receitas">
            <ResultTable
              rows={receitas}
              valueFor={r => valorReceita(r, visao)}
              empty="Nenhuma receita detalhada no documento final."
            />
            {totalReceitas && <TotalLine label="Total receitas" value={totalReceitaValor} />}
          </ResultCard>

          <ResultCard title="Despesas">
            <ResultTable
              rows={despesas}
              valueFor={r => valorDespesa(r, visao)}
              empty="Nenhuma despesa detalhada no documento final."
            />
            {subtotal && <TotalLine label="Subtotal" value={valorTotal(subtotal, visao)} muted />}
            {inflacao && <TotalLine label={inflacao.label} value={valorTotal(inflacao, visao)} muted />}
            {totalDespesas && <TotalLine label="Total previsto" value={totalDespesaValor} strong />}
          </ResultCard>
        </section>

        <section className="card result-audit">
          <div>
            <div className="eyebrow">Conferência</div>
            <p>
              Esta tela usa os valores da aba final <strong>PREVISÃO</strong> do XLSX gerado.
              O saldo é sempre calculado como receitas menos despesas na visão selecionada.
            </p>
          </div>
          <div className={`audit-balance ${saldoValor < 0 ? 'negative' : 'positive'}`}>
            <span>{sinalSaldo}</span>
            <strong>{money(Math.abs(saldoValor))}</strong>
          </div>
        </section>

        {sessao.inadimplencia?.length > 0 && (
          <section className="section">
            <div className="section-header">
              <div>
                <div className="eyebrow">Inadimplência</div>
                <span className="section-count">{sessao.inadimplencia.length} lançamento(s)</span>
              </div>
            </div>
            <div className="card table-card">
              <table className="result-table">
                <thead>
                  <tr>
                    <th>Unidade</th>
                    <th>Classe</th>
                    <th>Ref.</th>
                    <th className="num">Valor</th>
                    <th className="num">Meses</th>
                  </tr>
                </thead>
                <tbody>
                  {sessao.inadimplencia.map((item, i) => (
                    <tr key={i} className={item.critica ? 'danger-row' : ''}>
                      <td>{item.unidade}</td>
                      <td>{item.classe}</td>
                      <td>{item.mes_ref}</td>
                      <td className="num">{money(item.valor)}</td>
                      <td className="num">{item.meses_atraso}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        <div className="result-actions">
          <a href={urlDownload(sessao.sessao_id)} className="btn btn-primary">
            Baixar Previsão {sessao.ano_previsao} - {sessao.nome_condominio}.xlsx
          </a>
        </div>
      </main>
    </>
  )
}

function Kpi({ label, value, emphasis, danger }: { label: string; value: number; emphasis?: boolean; danger?: boolean }) {
  return (
    <div className={`kpi-card ${emphasis ? 'emphasis' : ''} ${danger ? 'danger' : ''}`}>
      <span>{label}</span>
      <strong>{money(value)}</strong>
    </div>
  )
}

function ResultCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="card result-card">
      <div className="section-header">
        <h2 className="section-title">{title}</h2>
      </div>
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

function TotalLine({ label, value, muted, strong }: { label: string; value: number; muted?: boolean; strong?: boolean }) {
  return (
    <div className={`total-line ${muted ? 'muted' : ''} ${strong ? 'strong' : ''}`}>
      <span>{label}</span>
      <strong>{money(value)}</strong>
    </div>
  )
}
