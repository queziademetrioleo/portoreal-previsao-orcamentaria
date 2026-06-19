import { useEffect, useMemo, useRef, useState } from 'react'
import { criarSessao, gerarDocumento, previewDocumento, urlDownload } from './api'
import { type ItemInad, type ItemRevisao, type Sessao } from './types'
import './App.css'

const brl = (v: number) =>
  v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })

// ---------------------------------------------------------------- Upload ---
function TelaUpload({ onPronto }: { onPronto: (s: Sessao) => void }) {
  const [nome, setNome] = useState('')
  const [ano, setAno] = useState(new Date().getFullYear() + 1)
  const [arquivos, setArquivos] = useState<Record<string, File | null>>({
    balanual: null, desbai: null, dessin: null, inad: null,
  })
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState('')

  const campos: Array<{ chave: string; rotulo: string; obrigatorio: boolean }> = [
    { chave: 'balanual', rotulo: 'balanual.xls — Demonstrativo anual', obrigatorio: true },
    { chave: 'desbai', rotulo: 'desbai06.xls — Despesas baixadas (NF a NF)', obrigatorio: true },
    { chave: 'dessin', rotulo: 'dessin02.xls — Sintético de despesas', obrigatorio: false },
    { chave: 'inad', rotulo: 'inad01.xls — Inadimplência', obrigatorio: false },
  ]

  const [progresso, setProgresso] = useState('')
  const ETAPAS = [
    'Lendo balanual.xls — demonstrativo de receitas e despesas...',
    'Lendo desbai06.xls — despesas nota fiscal por nota fiscal...',
    'Extraindo contas, grupos e valores mensais...',
    'Analisando inadimplência...',
    'IA classificando notas fiscais ambíguas...',
    'Aplicando regras de cálculo (R1 a R8)...',
    'Montando resultado final...',
  ]

  async function enviar() {
    if (!nome.trim() || !arquivos.balanual || !arquivos.desbai) {
      setErro('Preencha o nome do condomínio e os dois arquivos obrigatórios.')
      return
    }
    setErro(''); setCarregando(true)
    setProgresso(ETAPAS[0])

    // Rotaciona as mensagens a cada 3s enquanto carrega
    let i = 0
    const anim = setInterval(() => {
      i = (i + 1) % ETAPAS.length
      setProgresso(ETAPAS[i])
    }, 3000)

    try {
      const s = await criarSessao({
        nome: nome.trim(), ano,
        balanual: arquivos.balanual, desbai: arquivos.desbai,
        dessin: arquivos.dessin, inad: arquivos.inad,
      })
      clearInterval(anim)
      onPronto(s)
    } catch (e) {
      clearInterval(anim)
      setErro(e instanceof Error ? e.message : String(e))
    } finally {
      setCarregando(false)
      setProgresso('')
    }
  }

  return (
    <div className="card upload">
      <div className="header-logo">
        <img src="/assets/logo.png" alt="Porto Real" className="logo" />
        <div>
          <h1>Previsão Orçamentária</h1>
          <p className="sub">Envie os relatórios do Condomínio para que a análise seja feita e a I.A consiga gerar seu relatório. Uma revisão será feita antes de gerar o documento final.</p>
        </div>
      </div>

      <label className="campo">
        <span>Nome do condomínio</span>
        <input value={nome} onChange={e => setNome(e.target.value)}
               placeholder="COND. ED. CHATEAU LAVOISIER" />
      </label>
      <label className="campo">
        <span>Ano da previsão</span>
        <input type="number" value={ano} onChange={e => setAno(Number(e.target.value))} />
      </label>

      {campos.map(c => (
        <label key={c.chave} className={`arquivo ${arquivos[c.chave] ? 'ok' : ''}`}>
          <span>{c.rotulo} {c.obrigatorio ? '*' : '(opcional)'}</span>
          <input type="file" accept=".xls"
                 onChange={e => setArquivos(a => ({ ...a, [c.chave]: e.target.files?.[0] ?? null }))} />
          {arquivos[c.chave] && <em>✓ {arquivos[c.chave]!.name}</em>}
        </label>
      ))}

      {erro && <div className="erro">{erro}</div>}

      {carregando ? (
        <div className="loading-container">
          <div className="spinner" />
          <p className="loading-texto">{progresso}</p>
          <p className="loading-aviso">Aguarde — isso pode levar até 3 minutos</p>
        </div>
      ) : (
        <button className="primario" onClick={enviar}>
          Analisar
        </button>
      )}
    </div>
  )
}

// --------------------------------------------------------- Item de revisão ---
const BADGES: Record<ItemRevisao['decisao'], { texto: string; classe: string }> = {
  aprovada: { texto: '🔴 EXTRAORDINÁRIO — será removido da base', classe: 'badge-removido' },
  reprovada: { texto: '⚪ RECORRENTE — permanece na base (conta no total)', classe: 'badge-mantido' },
  pendente: { texto: '🟡 SEM DECISÃO — permanece na base por segurança', classe: 'badge-pendente' },
}

function CartaoItem({ item, onDecisao, opcoes, onEditar }: {
  item: ItemRevisao
  onDecisao: (d: ItemRevisao['decisao']) => void
  opcoes: Array<{ valor: ItemRevisao['decisao']; rotulo: string; classe: string }>
  onEditar?: () => void
}) {
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
          {item.data} · {item.grupo} · <span className={`origem ${item.origem}`}>{item.origem === 'IA' ? '🤖 IA' : '📐 Regra'}</span>
          <span className="motivo"> — {item.motivo}</span>
        </div>
        <div className={`badge ${badge.classe}`}>{badge.texto}</div>
      </div>
      <div className="acoes">
        {onEditar ? (
          <button className="mini neutro" onClick={onEditar}>↩ Reabrir</button>
        ) : (
          opcoes.map(o => (
            <button key={o.valor}
                    className={`mini ${o.classe} ${item.decisao === o.valor ? 'ativa' : ''}`}
                    onClick={() => onDecisao(o.valor)}>
              {item.decisao === o.valor ? '✓ ' : ''}{o.rotulo}
            </button>
          ))
        )}
      </div>
    </div>
  )
}

// ------------------------------------------------------------- Revisão ---
function TelaRevisao({ sessao }: { sessao: Sessao }) {
  const [extra, setExtra] = useState<ItemRevisao[]>(sessao.extraordinarias)
  const [revisar, setRevisar] = useState<ItemRevisao[]>(sessao.revisar)
  const [inad, setInad] = useState<ItemInad[]>(sessao.inadimplencia)
  // itens já decididos pelo humano somem da lista de pendentes (vão p/ "Resolvidos")
  const [feitos, setFeitos] = useState<Set<number>>(new Set())
  const marcarFeito = (id: number) => setFeitos(s => new Set(s).add(id))
  const reabrir = (id: number) => setFeitos(s => { const n = new Set(s); n.delete(id); return n })
  const [gerando, setGerando] = useState(false)
  const [resultado, setResultado] = useState<{ subtotal: number; total: number; impacto: number } | null>(null)
  const [erro, setErro] = useState('')

  // resumo ao vivo conforme as decisões
  const aoVivo = useMemo(() => {
    const dedExtra = extra.filter(i => i.decisao === 'aprovada').reduce((s, i) => s + i.valor, 0)
    const dedRev = revisar.filter(i => i.decisao === 'aprovada').reduce((s, i) => s + i.valor, 0)
    const unidades = new Map<string, number[]>()
    inad.filter(i => i.decisao === 'abater').forEach(i => {
      unidades.set(i.unidade, [...(unidades.get(i.unidade) ?? []), i.valor])
    })
    let impacto = 0
    unidades.forEach(vs => { impacto += vs.reduce((a, b) => a + b, 0) / vs.length })
    return { dedExtra, dedRev, impacto }
  }, [extra, revisar, inad])

  // Resultado AO VIVO: a cada decisao, recalcula no backend (debounce) o subtotal
  // e o total previsto reais — sem precisar gerar o documento.
  const [vivo, setVivo] = useState<{ subtotal: number; total: number; impacto: number }>({
    subtotal: sessao.resumo.subtotal,
    total: sessao.resumo.total_previsto,
    impacto: sessao.resumo.impacto_receita_mensal ?? 0,
  })
  const [calculando, setCalculando] = useState(false)
  const primeiraRender = useRef(true)

  useEffect(() => {
    if (primeiraRender.current) { primeiraRender.current = false; return }
    setCalculando(true)
    const t = setTimeout(async () => {
      try {
        const r = await previewDocumento(sessao.sessao_id, {
          extraordinarias: Object.fromEntries(extra.map(i => [String(i.id), i.decisao])),
          revisar: Object.fromEntries(revisar.map(i => [String(i.id), i.decisao])),
          inadimplencia: Object.fromEntries(inad.map(i => [String(i.id), i.decisao])),
        })
        setVivo({ subtotal: r.subtotal, total: r.total_previsto, impacto: r.impacto_receita_mensal })
      } catch { /* mantem ultimo valor */ }
      finally { setCalculando(false) }
    }, 350)
    return () => clearTimeout(t)
  }, [extra, revisar, inad, sessao.sessao_id])

  async function salvar() {
    setGerando(true); setErro('')
    try {
      const r = await gerarDocumento(sessao.sessao_id, {
        extraordinarias: Object.fromEntries(extra.map(i => [String(i.id), i.decisao])),
        revisar: Object.fromEntries(revisar.map(i => [String(i.id), i.decisao])),
        inadimplencia: Object.fromEntries(inad.map(i => [String(i.id), i.decisao])),
      })
      setResultado({ subtotal: r.subtotal, total: r.total_previsto, impacto: r.impacto_receita_mensal })
      window.location.assign(urlDownload(sessao.sessao_id))
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e))
    } finally {
      setGerando(false)
    }
  }

  const opExtra: Array<{ valor: ItemRevisao['decisao']; rotulo: string; classe: string }> = [
    { valor: 'aprovada', rotulo: 'Aprovar como gasto extraordinário', classe: 'aprovar' },
    { valor: 'reprovada', rotulo: 'Não é extraordinário — manter na base', classe: 'reprovar' },
  ]
  const opRevisar: Array<{ valor: ItemRevisao['decisao']; rotulo: string; classe: string }> = [
    { valor: 'aprovada', rotulo: 'É gasto extraordinário — remover', classe: 'aprovar' },
    { valor: 'reprovada', rotulo: 'É gasto recorrente — manter', classe: 'reprovar' },
    { valor: 'pendente', rotulo: 'Decidir depois', classe: 'neutro' },
  ]

  const pendentes = revisar.filter(i => i.decisao === 'pendente').length

  return (
    <div className="revisao">
      <header className="topo-fixo">
        <div>
          <h2>{sessao.nome_condominio} — Previsão {sessao.ano_previsao}</h2>
          <span className="periodo">Base: {sessao.resumo.periodo[0]} a {sessao.resumo.periodo[1]}
            {sessao.ia_ativa ? ` · 🤖 ${sessao.modelo_ia}` : ' · IA desligada'}</span>
        </div>
        <div className={`numeros ${calculando ? 'recalculando' : ''}`}>
          <div><label>Despesa 12m</label><b>{brl(sessao.resumo.base_total)}</b></div>
          <div><label>Subtotal previsto</label><b>{brl(vivo.subtotal)}</b></div>
          <div><label>Total c/ inflação</label><b>{brl(vivo.total)}</b></div>
          <div><label>Impacto receita/mês</label><b className={vivo.impacto > 0 ? 'alerta' : ''}>−{brl(vivo.impacto)}</b></div>
          <button className="primario" disabled={gerando} onClick={salvar}>
            {gerando ? 'Gerando…' : `Salvar e gerar Previsão ${sessao.ano_previsao}.xlsx`}
          </button>
        </div>
      </header>

      {erro && <div className="erro">{erro}</div>}
      {resultado && (
        <div className="sucesso">
          ✅ Documento gerado — subtotal {brl(resultado.subtotal)} · total c/ inflação {brl(resultado.total)}.
          O download começou automaticamente. <a href={urlDownload(sessao.sessao_id)}>Baixar novamente</a>
        </div>
      )}

      <section>
        <h3>🔴 Despesas extraordinárias detectadas <small>
          ({extra.filter(i => i.decisao === 'aprovada').length} de {extra.length} aprovadas como extraordinárias
          = {brl(aoVivo.dedExtra)} removidos da base)</small></h3>
        <p className="dica">A análise já marcou estes itens como extraordinários. Confirme um a um — ou clique em "Não é extraordinário" para devolver o gasto à base recorrente. Ao decidir, o item vai para "Resolvidos".</p>
        {extra.filter(i => !feitos.has(i.id)).map(item => (
          <CartaoItem key={item.id} item={item} opcoes={opExtra}
                      onDecisao={d => {
                        setExtra(xs => xs.map(x => x.id === item.id ? { ...x, decisao: d } : x))
                        // aprovar (extraordinário) some da lista; recorrente fica visível (cinza)
                        if (d === 'aprovada') marcarFeito(item.id); else reabrir(item.id)
                      }} />
        ))}
        {extra.filter(i => !feitos.has(i.id)).length === 0 && extra.length > 0 &&
          <p className="vazio">✓ Todos os {extra.length} itens revisados.</p>}
        {extra.some(i => feitos.has(i.id)) && (
          <details className="resolvidos">
            <summary>✓ {extra.filter(i => feitos.has(i.id)).length} resolvido(s) — clique para revisar/reabrir</summary>
            {extra.filter(i => feitos.has(i.id)).map(item => (
              <CartaoItem key={item.id} item={item} opcoes={opExtra}
                          onDecisao={() => {}} onEditar={() => reabrir(item.id)} />
            ))}
          </details>
        )}
      </section>

      <section>
        <h3>🟡 Em revisão — você decide <small>
          ({revisar.length} itens ambíguos · {pendentes} sem decisão · {brl(aoVivo.dedRev)} removidos até agora)</small></h3>
        <p className="dica">A análise não teve certeza nestes itens. Sem a sua decisão, eles permanecem na base (postura conservadora). Ao decidir, o item vai para "Resolvidos".</p>
        {revisar.filter(i => !feitos.has(i.id)).map(item => (
          <CartaoItem key={item.id} item={item} opcoes={opRevisar}
                      onDecisao={d => {
                        setRevisar(xs => xs.map(x => x.id === item.id ? { ...x, decisao: d } : x))
                        // "é extraordinário" (aprovada) some; recorrente fica cinza; pendente fica
                        if (d === 'aprovada') marcarFeito(item.id); else reabrir(item.id)
                      }} />
        ))}
        {revisar.filter(i => !feitos.has(i.id)).length === 0 && revisar.length > 0 &&
          <p className="vazio">✓ Todos os {revisar.length} itens revisados.</p>}
        {revisar.some(i => feitos.has(i.id)) && (
          <details className="resolvidos">
            <summary>✓ {revisar.filter(i => feitos.has(i.id)).length} resolvido(s) — clique para revisar/reabrir</summary>
            {revisar.filter(i => feitos.has(i.id)).map(item => (
              <CartaoItem key={item.id} item={item} opcoes={opRevisar}
                          onDecisao={() => {}} onEditar={() => reabrir(item.id)} />
            ))}
          </details>
        )}
      </section>

      <section>
        <h3>💸 Inadimplência <small>
          {sessao.inad_meta
            ? `(total ${brl(sessao.inad_meta.total)} · crítica ${brl(sessao.inad_meta.critica)} · data-base ${sessao.inad_meta.data_base})`
            : '(sem relatório inad01)'}
        </small></h3>
        {inad.length === 0 && <p className="vazio">Nenhuma pendência registrada.</p>}
        {inad.map(item => (
          <div key={item.id} className={`item ${item.decisao === 'abater' ? 'aprovada' : 'reprovada'}`}>
            <div className="item-info">
              <div className="item-topo">
                <strong>{item.unidade}</strong>
                <span className="valor">{brl(item.valor)}</span>
              </div>
              <div className="item-meta">
                {item.classe} · ref. {item.mes_ref} · venc. {item.vencimento} ·{' '}
                <b className={item.critica ? 'alerta' : ''}>
                  {item.meses_atraso} {item.meses_atraso === 1 ? 'mês' : 'meses'} de atraso
                  {item.critica ? ' (CRÍTICA ≥ 3 meses)' : ''}
                </b>
              </div>
              <div className={`badge ${item.decisao === 'abater' ? 'badge-removido' : 'badge-mantido'}`}>
                {item.decisao === 'abater'
                  ? '🔴 ABATE — taxa desta unidade sai da receita prevista'
                  : '🟢 NÃO ABATE — receita prevista permanece integral'}
              </div>
            </div>
            <div className="acoes">
              <button className={`mini aprovar ${item.decisao === 'abater' ? 'ativa' : ''}`}
                      onClick={() => setInad(xs => xs.map(x => x.id === item.id ? { ...x, decisao: 'abater' } : x))}>
                {item.decisao === 'abater' ? '✓ ' : ''}Abater da receita
              </button>
              <button className={`mini neutro ${item.decisao === 'ignorar' ? 'ativa' : ''}`}
                      onClick={() => setInad(xs => xs.map(x => x.id === item.id ? { ...x, decisao: 'ignorar' } : x))}>
                {item.decisao === 'ignorar' ? '✓ ' : ''}Não abater
              </button>
            </div>
          </div>
        ))}
      </section>
    </div>
  )
}

// ----------------------------------------------------------------- App ---
export default function App() {
  const [sessao, setSessao] = useState<Sessao | null>(null)
  return (
    <main className="container">
      {sessao ? <TelaRevisao sessao={sessao} /> : <TelaUpload onPronto={setSessao} />}
    </main>
  )
}
