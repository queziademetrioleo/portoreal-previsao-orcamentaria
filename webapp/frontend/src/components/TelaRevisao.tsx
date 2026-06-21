import { useState } from 'react'
import { gerarDocumento, urlDownload } from '../api'
import type { Sessao } from '../types'
import { useDecisoes } from '../hooks/useDecisoes'
import BulkActions from './BulkActions'
import { CartaoInadimplencia, CartaoItem, CartaoRevisado } from './CartaoItem'

const brl = (v: number) =>
  v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })

interface Props {
  sessao: Sessao
}

export default function TelaRevisao({ sessao }: Props) {
  const {
    extra, setExtra,
    revisar, setRevisar,
    inad, setInad,
    feitos, marcarFeito, reabrir,
    vivo, calculando,
    aoVivo, buildPayload,
  } = useDecisoes(sessao)

  const [gerando, setGerando] = useState(false)
  const [resultado, setResultado] = useState<{
    subtotal: number
    total: number
    impacto: number
  } | null>(null)
  const [erro, setErro] = useState('')

  async function salvar() {
    setGerando(true)
    setErro('')
    try {
      const r = await gerarDocumento(sessao.sessao_id, buildPayload())
      setResultado({
        subtotal: r.subtotal,
        total: r.total_previsto,
        impacto: r.impacto_receita_mensal,
      })
      window.location.assign(urlDownload(sessao.sessao_id))
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e))
    } finally {
      setGerando(false)
    }
  }

  const opExtra: Array<{
    valor: 'aprovada' | 'reprovada' | 'pendente'
    rotulo: string
    classe: string
  }> = [
    { valor: 'aprovada', rotulo: 'Aprovar como gasto extraordinario', classe: 'aprovar' },
    { valor: 'reprovada', rotulo: 'Nao e extraordinario — manter na base', classe: 'reprovar' },
  ]

  const opRevisar: Array<{
    valor: 'aprovada' | 'reprovada' | 'pendente'
    rotulo: string
    classe: string
  }> = [
    { valor: 'aprovada', rotulo: 'E gasto extraordinario — remover', classe: 'aprovar' },
    { valor: 'reprovada', rotulo: 'E gasto recorrente — manter', classe: 'reprovar' },
    { valor: 'pendente', rotulo: 'Decidir depois', classe: 'neutro' },
  ]

  return (
    <div className="revisao fade-in">
      <header className="topo-fixo">
        <div>
          <h2>
            {sessao.nome_condominio} — Previsao {sessao.ano_previsao}
          </h2>
          <span className="periodo">
            Base: {sessao.resumo.periodo[0]} a {sessao.resumo.periodo[1]}
            {sessao.ia_ativa
              ? ` · IA: ${sessao.modelo_ia}`
              : ' · IA desligada'}
          </span>
        </div>
        <div className={`numeros ${calculando ? 'recalculando' : ''}`}>
          <div>
            <label>Despesa 12m</label>
            <b>{brl(sessao.resumo.base_total)}</b>
          </div>
          <div>
            <label>Subtotal previsto</label>
            <b>{brl(vivo.subtotal)}</b>
          </div>
          <div>
            <label>Total c/ inflacao</label>
            <b>{brl(vivo.total)}</b>
          </div>
          <div>
            <label>Impacto receita/mes</label>
            <b className={vivo.impacto > 0 ? 'alerta' : ''}>
              -{brl(vivo.impacto)}
            </b>
          </div>
          <button className="primario" disabled={gerando} onClick={salvar}>
            {gerando
              ? 'Gerando...'
              : `Salvar e gerar Previsao ${sessao.ano_previsao}.xlsx`}
          </button>
        </div>
      </header>

      {erro && <div className="erro">{erro}</div>}

      {resultado && (
        <div className="sucesso">
          Documento gerado — subtotal {brl(resultado.subtotal)} · total
          c/ inflacao {brl(resultado.total)}. O download comecou
          automaticamente.{' '}
          <a href={urlDownload(sessao.sessao_id)}>Baixar novamente</a>
        </div>
      )}

      {/* --- Extraordinarias --- */}
      <section>
        <h3>
          Despesas extraordinarias detectadas{' '}
          <small>
            ({extra.filter(i => !feitos.has(i.id)).length} pendentes de{' '}
            {extra.length} · {brl(aoVivo.dedExtra)} removidos da base)
          </small>
        </h3>
        <p className="dica">
          Ja marcadas como extraordinarias. Confirme cada uma — ou marque
          "Nao e extraordinario" para mante-la na base. Ao decidir, o item
          vai para <strong>Revisados</strong> (abaixo).
        </p>
        <BulkActions
          count={extra.filter(i => !feitos.has(i.id)).length}
          onApproveAll={() => {
            extra.forEach(item => marcarFeito(item.id))
            setExtra(prev => prev.map(i => ({ ...i, decisao: 'aprovada' })))
          }}
          onRejectAll={() => {
            extra.forEach(item => marcarFeito(item.id))
            setExtra(prev => prev.map(i => ({ ...i, decisao: 'reprovada' })))
          }}
        />
        {extra
          .filter(i => !feitos.has(i.id))
          .map(item => (
            <CartaoItem
              key={item.id}
              item={item}
              opcoes={opExtra}
              onDecisao={d => {
                setExtra(xs =>
                  xs.map(x =>
                    x.id === item.id ? { ...x, decisao: d } : x,
                  ),
                )
                marcarFeito(item.id)
              }}
            />
          ))}
        {extra.filter(i => !feitos.has(i.id)).length === 0 && (
          <p className="vazio">Tudo revisado nesta secao.</p>
        )}
      </section>

      {/* --- Em revisao --- */}
      <section>
        <h3>
          Em revisao — voce decide{' '}
          <small>
            ({revisar.filter(i => !feitos.has(i.id)).length} pendentes de{' '}
            {revisar.length} · {brl(aoVivo.dedRev)} removidos ate agora)
          </small>
        </h3>
        <p className="dica">
          A analise nao teve certeza nestes itens. Sem decisao, permanecem na
          base (conservador). "Decidir depois" mantem na lista.
        </p>
        <BulkActions
          count={revisar.filter(i => !feitos.has(i.id)).length}
          onApproveAll={() => {
            revisar.forEach(item => marcarFeito(item.id))
            setRevisar(prev => prev.map(i => ({ ...i, decisao: 'aprovada' })))
          }}
          onRejectAll={() => {
            revisar.forEach(item => marcarFeito(item.id))
            setRevisar(prev => prev.map(i => ({ ...i, decisao: 'reprovada' })))
          }}
        />
        {revisar
          .filter(i => !feitos.has(i.id))
          .map(item => (
            <CartaoItem
              key={item.id}
              item={item}
              opcoes={opRevisar}
              onDecisao={d => {
                setRevisar(xs =>
                  xs.map(x =>
                    x.id === item.id ? { ...x, decisao: d } : x,
                  ),
                )
                if (d === 'pendente') reabrir(item.id)
                else marcarFeito(item.id)
              }}
            />
          ))}
        {revisar.filter(i => !feitos.has(i.id)).length === 0 && (
          <p className="vazio">Tudo revisado nesta secao.</p>
        )}
      </section>

      {/* --- Revisados --- */}
      {(() => {
        const decididos = [...extra, ...revisar].filter(i =>
          feitos.has(i.id),
        )
        if (!decididos.length) return null
        return (
          <section className="secao-revisados">
            <h3>
              Revisados{' '}
              <small>
                ({decididos.length} ja tratados — "Reabrir" para mudar)
              </small>
            </h3>
            {decididos.map(item => (
              <CartaoRevisado
                key={item.id}
                item={item}
                onReabrir={() => reabrir(item.id)}
              />
            ))}
          </section>
        )
      })()}

      {/* --- Inadimplencia --- */}
      <section>
        <h3>
          Inadimplencia{' '}
          <small>
            {sessao.inad_meta
              ? `(total ${brl(sessao.inad_meta.total)} · critica ${brl(sessao.inad_meta.critica)} · data-base ${sessao.inad_meta.data_base})`
              : '(sem relatorio inad01)'}
          </small>
        </h3>
        {inad.length === 0 && (
          <p className="vazio">Nenhuma pendencia registrada.</p>
        )}
        {inad.map(item => (
          <CartaoInadimplencia
            key={item.id}
            item={item}
            onDecisao={d => {
              setInad(xs =>
                xs.map(x =>
                  x.id === item.id ? { ...x, decisao: d } : x,
                ),
              )
            }}
          />
        ))}
      </section>
    </div>
  )
}
