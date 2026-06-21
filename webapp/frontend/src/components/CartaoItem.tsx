import type { ItemInad, ItemRevisao } from '../types'

const brl = (v: number) =>
  v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })

const BADGES: Record<ItemRevisao['decisao'], { texto: string; classe: string }> = {
  aprovada: { texto: 'APROVADO — gasto extraordinário removido da base', classe: 'badge-aprovado' },
  reprovada: { texto: 'REJEITADO — recorrente, permanece na base', classe: 'badge-rejeitado' },
  pendente: { texto: 'SEM DECISÃO — permanece na base por segurança', classe: 'badge-pendente' },
}

/* ---------- CartaoRevisao (pendente ou em análise) ---------- */
interface CartaoItemProps {
  item: ItemRevisao
  onDecisao: (d: ItemRevisao['decisao']) => void
  opcoes: Array<{ valor: ItemRevisao['decisao']; rotulo: string; classe: string }>
  onEditar?: () => void
}

export function CartaoItem({ item, onDecisao, opcoes, onEditar }: CartaoItemProps) {
  const badge = BADGES[item.decisao]
  return (
    <div className={`item ${item.decisao} ${onEditar ? 'resolvido' : ''}`}>
      <div className="item-info">
        <div className="item-topo">
          <strong>{item.classe}</strong>
          <span className="valor">{brl(item.valor)}</span>
        </div>
        <div className="item-desc">{item.descricao}</div>
        <div className="item-meta">
          {item.data} · {item.grupo} ·{' '}
          <span className={`origem ${item.origem}`}>
            {item.origem === 'IA' ? 'IA' : 'Regra'}
          </span>
          <span className="motivo"> — {item.motivo}</span>
        </div>
        <div className={`badge ${badge.classe}`}>{badge.texto}</div>
      </div>
      <div className="acoes">
        {onEditar ? (
          <button className="mini neutro" onClick={onEditar}>
            Reabrir
          </button>
        ) : (
          opcoes.map(o => (
            <button
              key={o.valor}
              className={`mini ${o.classe} ${item.decisao === o.valor ? 'ativa' : ''}`}
              onClick={() => onDecisao(o.valor)}
            >
              {item.decisao === o.valor && '✓ '}
              {o.rotulo}
            </button>
          ))
        )}
      </div>
    </div>
  )
}

/* ---------- CartaoRevisado (já decidido, estilo cinza) ---------- */
interface CartaoRevisadoProps {
  item: ItemRevisao
  onReabrir: () => void
}

export function CartaoRevisado({ item, onReabrir }: CartaoRevisadoProps) {
  const removido = item.decisao === 'aprovada'
  return (
    <div className="rev-item">
      <div className="rev-main">
        <span className="rev-classe">{item.classe}</span>
        <span className="rev-meta">{item.grupo}</span>
      </div>
      <span className={`rev-tag ${removido ? 'rem' : 'man'}`}>
        {removido ? 'removido da base' : 'mantido na base'}
      </span>
      <span className="rev-valor">{brl(item.valor)}</span>
      <button className="mini neutro rev-reabrir" onClick={onReabrir}>
        Reabrir
      </button>
    </div>
  )
}

/* ---------- CartaoInadimplencia ---------- */
interface CartaoInadProps {
  item: ItemInad
  onDecisao: (d: ItemInad['decisao']) => void
}

export function CartaoInadimplencia({ item, onDecisao }: CartaoInadProps) {
  return (
    <div className={`item ${item.decisao === 'abater' ? 'aprovada' : 'reprovada'}`}>
      <div className="item-info">
        <div className="item-topo">
          <strong>{item.unidade}</strong>
          <span className="valor">{brl(item.valor)}</span>
        </div>
        <div className="item-meta">
          {item.classe} · ref. {item.mes_ref} · venc. {item.vencimento} ·{' '}
          <b className={item.critica ? 'alerta' : ''}>
            {item.meses_atraso} {item.meses_atraso === 1 ? 'mês' : 'meses'} de atraso
            {item.critica ? ' (CRÍTICA > 3 meses)' : ''}
          </b>
        </div>
        <div className={`badge ${item.decisao === 'abater' ? 'badge-aprovado' : 'badge-rejeitado'}`}>
          {item.decisao === 'abater'
            ? 'ABATE — taxa sai da receita prevista'
            : 'NAO ABATE — receita prevista permanece integral'}
        </div>
      </div>
      <div className="acoes">
        <button
          className={`mini aprovar ${item.decisao === 'abater' ? 'ativa' : ''}`}
          onClick={() => onDecisao('abater')}
        >
          {item.decisao === 'abater' ? '✓ ' : ''}Abater da receita
        </button>
        <button
          className={`mini neutro ${item.decisao === 'ignorar' ? 'ativa' : ''}`}
          onClick={() => onDecisao('ignorar')}
        >
          {item.decisao === 'ignorar' ? '✓ ' : ''}Nao abater
        </button>
      </div>
    </div>
  )
}
