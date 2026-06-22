import type { ItemRevisao, ItemInad } from '../types'

function fmt(v: number) {
  return v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function OrigemBadge({ origem }: { origem: string }) {
  if (origem === 'IA') return <span className="badge badge-ia">🤖 IA</span>
  if (origem === 'Regra') return <span className="badge badge-rec">📐 Regra</span>
  return null
}

export function CartaoRevisao({ item, onApprove, onReject, onReset }: {
  item: ItemRevisao
  onApprove: () => void
  onReject: () => void
  onReset?: () => void
}) {
  const isResolvido = item.decisao !== 'pendente'
  const extraCls = item.decisao === 'aprovada' ? 'extra' : item.decisao === 'reprovada' ? 'recorrente' : 'revisar'

  return (
    <div className={`item ${extraCls}${isResolvido ? ' resolvido' : ''}`}>
      <div className="item-body">
        <div className="item-top">
          <div className="item-class">
            {item.grupo} <span>&gt; {item.classe}</span>
          </div>
          <div className="item-valor">R$ {fmt(item.valor)}</div>
        </div>
        {item.descricao && <div className="item-desc">{item.descricao}</div>}
        <div className="item-meta">
          {item.data && <span className="item-data">{item.data}</span>}
          <OrigemBadge origem={item.origem} />
          {item.motivo && <span className="item-motivo" title={item.motivo}>{item.motivo}</span>}
        </div>
      </div>
      <div className="item-actions">
        {isResolvido ? (
          onReset && <button className="btn btn-ghost btn-xs" onClick={onReset}>↩ Reabrir</button>
        ) : (
          <>
            <button className="btn btn-approve btn-xs" onClick={onApprove}>✓ Remover da previsão</button>
            <button className="btn btn-reject btn-xs" onClick={onReject}>↺ Manter na previsão</button>
          </>
        )}
      </div>
    </div>
  )
}

export function CartaoInad({ item, onAbater, onIgnorar }: {
  item: ItemInad
  onAbater: () => void
  onIgnorar: () => void
}) {
  const crit = item.critica ? ' (crítico)' : ''

  return (
    <div className="item inad">
      <div className="item-body">
        <div className="item-top">
          <div className="item-class">{item.unidade}{crit}</div>
          <div className="item-valor">R$ {fmt(item.valor)}</div>
        </div>
        <div className="item-meta">
          <span className="item-data">{item.classe} — ref. {item.mes_ref}</span>
          {item.meses_atraso > 0 && (
            <span className={`badge ${item.critica ? 'badge-inad' : 'badge-rev'}`}>
              {item.meses_atraso} {item.meses_atraso === 1 ? 'mês' : 'meses'}
            </span>
          )}
        </div>
      </div>
      <div className="item-actions">
        <button className="btn btn-abater btn-xs" onClick={onAbater}>Abater</button>
        <button className="btn btn-ghost btn-xs" onClick={onIgnorar}>Ignorar</button>
      </div>
    </div>
  )
}
