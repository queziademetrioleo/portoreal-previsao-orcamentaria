import type { Sessao } from '../types'
import { urlDownload } from '../api'

function fmt(v: number) {
  return v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function TelaResultado({ sessao, onVoltar }: {
  sessao: Sessao
  onVoltar: () => void
}) {
  const r = sessao.resumo
  const linhas = sessao.linhas_contas
  const receitas = linhas.filter(l => l.grupo?.toLowerCase().includes('receita') || l.classe?.toLowerCase().includes('taxa') || l.classe?.toLowerCase().includes('fundo'))

  // Group despesas by grupo
  const grupos = new Map<string, typeof linhas>()
  for (const l of linhas) {
    if (receitas.includes(l)) continue
    const g = l.grupo || 'Outros'
    if (!grupos.has(g)) grupos.set(g, [])
    grupos.get(g)!.push(l)
  }

  const saldo = r.receita_anual - r.total_previsto

  return (
    <>
      <header className="app-header">
        <a href="/" className="logo" onClick={e => { e.preventDefault(); onVoltar() }}>
          <img src="/assets/logo.png" alt="" /> Previsão Orçamentária
        </a>
        <button className="btn btn-ghost btn-sm" onClick={onVoltar}>← Voltar</button>
      </header>

      <div className="container">
        {/* Header info */}
        <div className="eyebrow">Previsão Orçamentária</div>
        <h1 className="title">{sessao.nome_condominio} — {sessao.ano_previsao}</h1>
        {r.periodo && <p className="subtitle">Período base: {r.periodo[0]} a {r.periodo[1]}</p>}

        {/* Summary cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 'var(--s-md)', marginBottom: 'var(--s-xl)' }}>
          <SummaryCard label="Base 12 meses" value={r.base_total} />
          <SummaryCard label="Desconsiderações" value={r.desconsideracoes} muted />
          <SummaryCard label="Subtotal" value={r.subtotal} />
          <SummaryCard label={`Inflação (${((r.inflacao || 0.0472)*100).toFixed(1)}%)`} value={r.subtotal * (r.inflacao || 0.0472)} muted />
          <SummaryCard label="Total Previsto" value={r.total_previsto} highlight />
          <SummaryCard label="Receita Anual" value={r.receita_anual} />
          <SummaryCard label={saldo < 0 ? 'Déficit' : 'Superávit'} value={Math.abs(saldo)} highlight={saldo < 0} />
        </div>

        {/* Receitas */}
        <div className="section">
          <div className="eyebrow">Receitas</div>
          <div className="card" style={{ overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--b1)' }}>
                  <th style={{ textAlign: 'left', padding: '8px 12px', color: 'var(--t2)', fontWeight: 500 }}>Conta</th>
                  <th style={{ textAlign: 'right', padding: '8px 12px', color: 'var(--t2)', fontWeight: 500 }}>Mensal</th>
                  <th style={{ textAlign: 'right', padding: '8px 12px', color: 'var(--t2)', fontWeight: 500 }}>Anual</th>
                </tr>
              </thead>
              <tbody>
                {receitas.map((l, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--b1)' }}>
                    <td style={{ padding: '8px 12px', color: 'var(--t1)' }}>{l.classe}</td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--t1)' }}>R$ {fmt(l.final / 12)}</td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--t1)' }}>R$ {fmt(l.final)}</td>
                  </tr>
                ))}
                <tr style={{ fontWeight: 600 }}>
                  <td style={{ padding: '8px 12px', color: 'var(--t1)' }}>TOTAL RECEITAS</td>
                  <td style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--t1)' }}>R$ {fmt(r.receita_mensal)}</td>
                  <td style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--t1)' }}>R$ {fmt(r.receita_anual)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Despesas by group */}
        <div className="section">
          <div className="eyebrow">Despesas</div>
          {[...grupos.entries()].map(([grupo, items]) => {
            const totalGrupo = items.reduce((s, l) => s + l.final, 0)
            if (totalGrupo < 0.01) return null
            return (
              <div key={grupo} className="card" style={{ marginBottom: 'var(--s-md)', overflow: 'auto' }}>
                <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--t1)', marginBottom: 'var(--s-sm)' }}>{grupo}</h3>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--b1)' }}>
                      <th style={{ textAlign: 'left', padding: '6px 12px', color: 'var(--t2)', fontWeight: 500 }}>Conta</th>
                      <th style={{ textAlign: 'right', padding: '6px 12px', color: 'var(--t2)', fontWeight: 500 }}>Base</th>
                      <th style={{ textAlign: 'right', padding: '6px 12px', color: 'var(--t2)', fontWeight: 500 }}>Dedução</th>
                      <th style={{ textAlign: 'right', padding: '6px 12px', color: 'var(--t2)', fontWeight: 500 }}>Final</th>
                      <th style={{ textAlign: 'right', padding: '6px 12px', color: 'var(--t2)', fontWeight: 500 }}>Mensal</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((l, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid var(--b1)' }}>
                        <td style={{ padding: '6px 12px', color: 'var(--t1)' }}>
                          {l.classe}
                          {l.deducao > 0 && <span style={{ fontSize: '10px', color: 'var(--t3)', marginLeft: '6px' }}>{l.regra}</span>}
                        </td>
                        <td style={{ padding: '6px 12px', textAlign: 'right', color: 'var(--t2)' }}>R$ {fmt(l.base)}</td>
                        <td style={{ padding: '6px 12px', textAlign: 'right', color: l.deducao > 0 ? 'var(--inad)' : 'var(--t2)' }}>{l.deducao > 0 ? `-R$ ${fmt(l.deducao)}` : '—'}</td>
                        <td style={{ padding: '6px 12px', textAlign: 'right', fontWeight: 500, color: 'var(--t1)' }}>R$ {fmt(l.final)}</td>
                        <td style={{ padding: '6px 12px', textAlign: 'right', color: 'var(--t2)' }}>R$ {fmt(l.final / 12)}</td>
                      </tr>
                    ))}
                    <tr style={{ fontWeight: 600, borderTop: '2px solid var(--b2)' }}>
                      <td style={{ padding: '8px 12px', color: 'var(--t1)' }}>Total {grupo}</td>
                      <td></td>
                      <td></td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--t1)' }}>R$ {fmt(totalGrupo)}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--t1)' }}>R$ {fmt(totalGrupo / 12)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            )
          })}
        </div>

        {/* Totals */}
        <div className="card" style={{ marginBottom: 'var(--s-xl)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
            <tbody>
              <TotalsRow label="Subtotal" value={r.subtotal} />
              {r.prov_laudo > 0 && <TotalsRow label="(+) Provisão Laudo Autovistoria (R4)" value={r.prov_laudo} muted />}
              {r.prov_incendio > 0 && <TotalsRow label="(+) Provisão Sist. Incêndio (R5)" value={r.prov_incendio} muted />}
              <TotalsRow label={`(+) Inflação (${((r.inflacao || 0.0472)*100).toFixed(1)}%)`} value={r.subtotal * (r.inflacao || 0.0472)} muted />
              <TotalsRow label="TOTAL PREVISTO" value={r.total_previsto} bold />
              <TotalsRow label="Receita Anual" value={r.receita_anual} />
              <TotalsRow label={saldo < 0 ? 'DÉFICIT' : 'SUPERÁVIT'} value={Math.abs(saldo)} bold={saldo < 0} negative={saldo < 0} />
            </tbody>
          </table>
        </div>

        {/* Inadimplencia */}
        {sessao.inadimplencia && sessao.inadimplencia.length > 0 && (
          <div className="section">
            <div className="eyebrow">Inadimplência</div>
            <div className="card" style={{ overflow: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--b1)' }}>
                    <th style={{ textAlign: 'left', padding: '6px 12px', color: 'var(--t2)', fontWeight: 500 }}>Unidade</th>
                    <th style={{ textAlign: 'left', padding: '6px 12px', color: 'var(--t2)', fontWeight: 500 }}>Classe</th>
                    <th style={{ textAlign: 'left', padding: '6px 12px', color: 'var(--t2)', fontWeight: 500 }}>Ref.</th>
                    <th style={{ textAlign: 'right', padding: '6px 12px', color: 'var(--t2)', fontWeight: 500 }}>Valor</th>
                    <th style={{ textAlign: 'right', padding: '6px 12px', color: 'var(--t2)', fontWeight: 500 }}>Meses</th>
                  </tr>
                </thead>
                <tbody>
                  {sessao.inadimplencia.map((item, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--b1)' }}>
                      <td style={{ padding: '6px 12px', color: item.critica ? 'var(--inad)' : 'var(--t1)', fontWeight: item.critica ? 600 : 400 }}>
                        {item.unidade}
                      </td>
                      <td style={{ padding: '6px 12px', color: 'var(--t2)' }}>{item.classe}</td>
                      <td style={{ padding: '6px 12px', color: 'var(--t2)' }}>{item.mes_ref}</td>
                      <td style={{ padding: '6px 12px', textAlign: 'right', color: 'var(--t1)' }}>R$ {fmt(item.valor)}</td>
                      <td style={{ padding: '6px 12px', textAlign: 'right', color: item.critica ? 'var(--inad)' : 'var(--t1)' }}>{item.meses_atraso}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Download button */}
        <div style={{ textAlign: 'center', margin: 'var(--s-2xl) 0' }}>
          <a href={urlDownload(sessao.sessao_id)} className="btn btn-primary" style={{ padding: '12px 32px', fontSize: '15px', textDecoration: 'none' }}>
            📥 Baixar Previsão {sessao.ano_previsao} - {sessao.nome_condominio}.xlsx
          </a>
        </div>
      </div>
    </>
  )
}

function SummaryCard({ label, value, muted, highlight }: { label: string; value: number; muted?: boolean; highlight?: boolean }) {
  return (
    <div className="card" style={{
      textAlign: 'center',
      borderLeft: highlight ? '3px solid var(--inad)' : muted ? undefined : '3px solid var(--rec)',
    }}>
      <div style={{ fontSize: '11px', color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '4px' }}>{label}</div>
      <div style={{ fontSize: '20px', fontWeight: 700, color: muted ? 'var(--t2)' : highlight ? 'var(--inad)' : 'var(--t1)' }}>
        R$ {fmt(value)}
      </div>
    </div>
  )
}

function TotalsRow({ label, value, muted, bold, negative }: { label: string; value: number; muted?: boolean; bold?: boolean; negative?: boolean }) {
  return (
    <tr style={{ borderBottom: '1px solid var(--b1)' }}>
      <td style={{
        padding: '10px 16px',
        fontWeight: bold ? 700 : 400,
        fontSize: bold ? '15px' : '14px',
        color: negative ? 'var(--inad)' : muted ? 'var(--t2)' : 'var(--t1)'
      }}>
        {label}
      </td>
      <td style={{
        padding: '10px 16px',
        textAlign: 'right',
        fontWeight: bold ? 700 : 400,
        fontSize: bold ? '15px' : '14px',
        color: negative ? 'var(--inad)' : muted ? 'var(--t2)' : 'var(--t1)'
      }}>
        R$ {fmt(value)}
      </td>
    </tr>
  )
}
