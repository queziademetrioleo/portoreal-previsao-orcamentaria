import { useState, useRef, useEffect } from 'react'
import { BASE, criarSessao, mensagemErroApi } from '../api'
import FileZone from './FileZone'
import type { Sessao, Sistema } from '../types'
import Header from './ui/Header'
import Card from './ui/Card'
import Button from './ui/Button'
import ProgressBar from './ui/ProgressBar'
import Spinner from './ui/Spinner'

interface Props {
  onCriada: (s: Sessao) => void
  onVoltar: () => void
}

export default function TelaUpload({ onCriada, onVoltar }: Props) {
  const [sistemas, setSistemas] = useState<Sistema[]>(['condo21'])
  const [nome, setNome] = useState('')
  const [ano, setAno] = useState(new Date().getFullYear())
  const [balanual, setBalanual] = useState<File | null>(null)
  const [desbai, setDesbai] = useState<File | null>(null)
  const [rec, setRec] = useState<File | null>(null)
  const [dessin, setDessin] = useState<File | null>(null)
  const [inad, setInad] = useState<File | null>(null)
  const [groupBal, setGroupBal] = useState<File | null>(null)
  const [groupDes, setGroupDes] = useState<File | null>(null)
  const [groupRec, setGroupRec] = useState<File | null>(null)
  const [almaBal, setAlmaBal] = useState<File | null>(null)
  const [almaFin, setAlmaFin] = useState<File | null>(null)
  const [almaRec, setAlmaRec] = useState<File | null>(null)
  const [almaInad, setAlmaInad] = useState<File | null>(null)
  const [semInadAlma, setSemInadAlma] = useState(false)
  const [almaInicio, setAlmaInicio] = useState('')
  const [periodoInicio, setPeriodoInicio] = useState('')
  const [periodoFim, setPeriodoFim] = useState('')
  const condo = sistemas.includes('condo21')
  const alma = sistemas.includes('alma')
  const group = sistemas.includes('group')
  const multiplos = sistemas.length > 1
  const escolherSistema = (sistema: Sistema) => {
    setSistemas((prev) => prev.includes(sistema) ? prev.filter((s) => s !== sistema) : [...prev, sistema])
    setErro('')
  }
  const [loading, setLoading] = useState(false)
  const [erro, setErro] = useState('')
  const [progresso, setProgresso] = useState({
    fase: 'Conectando...',
    passo: 0,
    total: 6,
    detalhe: '',
  })
  const eventSourceRef = useRef<EventSource | null>(null)
  const envioEmCursoRef = useRef(false)
  const mountedRef = useRef(true)

  // Cleanup EventSource on unmount
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      eventSourceRef.current?.close()
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (envioEmCursoRef.current) return
    if (!nome.trim()) {
      setErro('Informe o nome do condomínio.')
      return
    }
    if (!ano || ano < 2020 || ano > 2035) {
      setErro('Informe um ano válido (2020–2035).')
      return
    }
    if (!sistemas.length) {
      setErro('Selecione pelo menos um sistema.')
      return
    }
    if (condo && (!balanual || !desbai || !rec)) {
      setErro('Envie balanual.xls, desbai06.xls e rec02.xls do Condo21.')
      return
    }
    if (group && (!groupBal || !groupDes || !groupRec)) {
      setErro('Envie o balancete anual, as despesas detalhadas e as receitas por unidade da Group em XLS ou XLSX.')
      return
    }
    if (alma && (!almaBal || !almaFin || !almaRec)) {
      setErro('Envie também o demonstrativo por período, FIN e contas a receber do Alma.')
      return
    }
    if (alma && !almaInad && !semInadAlma) {
      setErro('Envie o relatório de inadimplência do Alma ou marque que não há inadimplência.')
      return
    }
    if ((alma || multiplos) && (Boolean(periodoInicio) !== Boolean(periodoFim) || (periodoInicio && periodoInicio > periodoFim))) {
      setErro('Informe início e fim do período em ordem, ou deixe ambos em branco.')
      return
    }
    setErro('')
    envioEmCursoRef.current = true
    setProgresso({ fase: 'Enviando documentos...', passo: 0, total: 6, detalhe: '' })
    setLoading(true)

    try {
      const { sessao_id } = await criarSessao({
        nome: nome.trim(),
        ano,
        sistemas,
        ...(condo ? { balanual, desbai, rec, dessin, inad: multiplos ? null : inad } : {}),
        ...(group ? { groupBal, groupDes, groupRec } : {}),
        ...(alma ? { almaBal, almaFin, almaRec, almaInad, semInadAlma } : {}),
        ...((alma || multiplos) ? { periodoInicio, periodoFim } : {}),
        ...(group && alma ? { almaInicio } : {}),
      })
      if (!mountedRef.current) return

      const base = BASE
      const source = new EventSource(
        `${base}/api/sessao/${sessao_id}/analisar`,
      )
      eventSourceRef.current = source

      source.onmessage = (event) => {
        const data = JSON.parse(event.data)
        if (data.error) {
          source.close()
          setErro(mensagemErroApi(data.error, 'Erro ao analisar os relatórios.'))
          setLoading(false)
          envioEmCursoRef.current = false
          return
        }
        if (data.done) {
          source.close()
          fetch(`${base}/api/sessao/${sessao_id}`)
            .then(async (r) => {
              if (!r.ok) {
                const body = await r.json().catch(() => null)
                throw new Error(mensagemErroApi(body, `Erro ${r.status}`))
              }
              return r.json() as Promise<Sessao>
            })
            .then((s) => { if (mountedRef.current) onCriada(s) })
            .catch((err) => {
              setErro(err.message || 'Erro ao carregar resultado.')
              setLoading(false)
              envioEmCursoRef.current = false
            })
        } else {
          setProgresso(data)
        }
      }

      source.onerror = () => {
        source.close()
        setErro('Erro na conexão com o servidor. Tente novamente.')
        setLoading(false)
        envioEmCursoRef.current = false
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Erro ao enviar os arquivos.'
      setErro(msg)
      setLoading(false)
      envioEmCursoRef.current = false
    }
  }

  if (loading) {
    return (
      <>
        <Header onHome={onVoltar}>
          <Button variant="ghost" onClick={onVoltar}>
            ← Voltar
          </Button>
        </Header>
        <div className="page">
          <div className="upload-card">
            <Card>
              <Spinner text={progresso.fase === 'Enviando documentos...' ? 'Enviando documentos...' : 'Analisando os relatórios...'} />
              <ProgressBar
                passo={progresso.passo}
                total={progresso.total}
                fase={progresso.fase}
                detalhe={progresso.detalhe}
              />
              <p className="spinner-text" style={{ fontSize: 14 }}>
                Isso pode levar alguns minutos.
              </p>
            </Card>
          </div>
        </div>
      </>
    )
  }

  return (
    <>
      <Header onHome={onVoltar}>
        <Button variant="ghost" onClick={onVoltar}>
          ← Voltar
        </Button>
      </Header>

      <div className="page">
        <div className="upload-card">
          <Card>
            <p className="section-label">Nova Análise</p>
            <h1 className="page-title">Enviar relatórios</h1>
            <p className="page-subtitle">
              Selecione um ou mais sistemas e anexe os relatórios do condomínio.
            </p>

            {erro && <div className="alert-error" role="alert">{erro}</div>}

            <form onSubmit={handleSubmit}>
              <section className="upload-identity" aria-labelledby="condominio-heading">
                <h2 id="condominio-heading" className="upload-section-title">Dados do condomínio</h2>
                <p className="upload-section-description">Esta análise e todos os documentos abaixo pertencem ao mesmo condomínio.</p>
                <div className="upload-identity-fields">
                  <div className="form-group">
                    <label className="form-label" htmlFor="condominio-nome">Condomínio</label>
                    <input
                      className="form-input"
                      id="condominio-nome"
                      type="text"
                      value={nome}
                      onChange={(e) => setNome(e.target.value)}
                      placeholder="Nome do condomínio"
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label" htmlFor="previsao-ano">Ano da previsão</label>
                    <input
                      className="form-input"
                      id="previsao-ano"
                      type="number"
                      value={ano}
                      onChange={(e) => setAno(Number(e.target.value))}
                      min={2020}
                      max={2035}
                    />
                  </div>
                </div>
              </section>

              <div className="upload-documents-heading">
                <h2 className="upload-section-title">Documentos do condomínio</h2>
                <p className="upload-section-description">Selecione os sistemas e envie os arquivos na caixa correspondente.</p>
              </div>

              <fieldset className="form-group report-source">
                <legend className="form-label">Sistemas dos relatórios</legend>
                <div className="report-source-options">
                  <label className={`report-source-option${condo ? ' is-selected' : ''}`}>
                    <input
                      type="checkbox"
                      name="origem-relatorios"
                      value="condo21"
                      checked={condo}
                      onChange={() => escolherSistema('condo21')}
                    />
                    <span>
                      <strong>Condo21</strong>
                      <small>Relatórios em XLS</small>
                    </span>
                  </label>
                  <label className={`report-source-option${alma ? ' is-selected' : ''}`}>
                    <input
                      type="checkbox"
                      name="origem-relatorios"
                      value="alma"
                      checked={alma}
                      onChange={() => escolherSistema('alma')}
                    />
                    <span>
                      <strong>Alma</strong>
                      <small>Relatórios em PDF e XLSX</small>
                    </span>
                  </label>
                  <label className={`report-source-option${group ? ' is-selected' : ''}`}>
                    <input type="checkbox" name="origem-relatorios" value="group" checked={group}
                      onChange={() => escolherSistema('group')} />
                    <span><strong>Group</strong><small>Relatórios em XLS ou XLSX</small></span>
                  </label>
                </div>
                <p className="form-hint">Marque todos os sistemas usados no período. Cada seleção abre seus próprios campos abaixo.</p>
              </fieldset>

              {condo && <section className="upload-document-block" aria-labelledby="condo21-documentos">
                <div className="upload-document-header"><h3 id="condo21-documentos">Condo21</h3><span>Documentos · XLS</span></div>
                <div className="file-grid">
                  <FileZone
                    label="balanual.xls"
                    file={balanual}
                    setFile={setBalanual}
                    required
                  />
                  <FileZone
                    label="desbai06.xls"
                    file={desbai}
                    setFile={setDesbai}
                    required
                  />
                  <FileZone
                    label="rec02.xls"
                    file={rec}
                    setFile={setRec}
                    required
                  />
                  <FileZone
                    label="dessin02.xls"
                    file={dessin}
                    setFile={setDessin}
                  />
                  {!multiplos && <FileZone
                    label="inad01.xls (opcional)"
                    file={inad}
                    setFile={setInad}
                  />}
                </div>
                <p className="form-hint">
                  {multiplos
                    ? 'Envie os relatórios do período que ficou no Condo21. Os meses não podem sobrepor os dos outros sistemas.'
                    : '* balanual.xls, desbai06.xls e rec02.xls são obrigatórios. inad01.xls é opcional — só anexe se houver inadimplência.'}
                </p>
              </section>}

              {group && <section className="upload-document-block" aria-labelledby="group-documentos">
                <div className="upload-document-header"><h3 id="group-documentos">Group</h3><span>Documentos · XLS ou XLSX</span></div>
                <div className="file-grid">
                  <FileZone label="Balancete anual (XLS ou XLSX)" file={groupBal} setFile={setGroupBal} accept=".xls,.xlsx" required />
                  <FileZone label="Despesas detalhadas por classe de conta (XLS ou XLSX)" file={groupDes} setFile={setGroupDes} accept=".xls,.xlsx" required />
                  <FileZone label="Receitas detalhadas por unidade/cliente (XLS ou XLSX)" file={groupRec} setFile={setGroupRec} accept=".xls,.xlsx" required />
                </div>
                <p className="form-hint">Envie o balancete com 12 meses e pagamentos do mesmo período. Cobranças excluídas serão desconsideradas. A inadimplência Group ainda não é apurada por estes três relatórios.</p>
              </section>}

              {alma && (
                  <section className="upload-document-block" aria-labelledby="alma-documentos">
                    <div className="upload-document-header"><h3 id="alma-documentos">Alma</h3><span>Documentos · PDF e XLSX</span></div>
                    <div className="file-grid">
                      <FileZone label="Por período agrupado por contas (PDF)" file={almaBal} setFile={setAlmaBal} accept=".pdf" required />
                      <FileZone label="FIN00601 — despesas detalhadas (XLSX)" file={almaFin} setFile={setAlmaFin} accept=".xlsx" required />
                      <FileZone label="Contas a receber agrupado por conta (PDF)" file={almaRec} setFile={setAlmaRec} accept=".pdf" required />
                      {!semInadAlma && <FileZone label="Inadimplência Alma (PDF)" file={almaInad} setFile={setAlmaInad} accept=".pdf" required />}
                    </div>
                    <label className="form-hint" style={{ display: 'flex', gap: 'var(--s-sm)', alignItems: 'center', marginTop: 'var(--s-md)' }}>
                      <input type="checkbox" checked={semInadAlma} onChange={(e) => {
                        setSemInadAlma(e.target.checked)
                        if (e.target.checked) setAlmaInad(null)
                      }} />
                      Não há inadimplência no Alma
                    </label>
                    <p className="form-hint">Consideramos apenas os dois últimos meses da referência do relatório de inadimplência do Alma.</p>
                  </section>
              )}
              {group && alma && (
                <section className="upload-identity" aria-labelledby="migracao-heading">
                  <h2 id="migracao-heading" className="upload-section-title">Mudança da Group para Alma</h2>
                  <label className="form-label" htmlFor="alma-inicio">Primeiro mês que deve usar os dados do Alma (opcional)</label>
                  <input id="alma-inicio" className="form-input" type="month" value={almaInicio} onChange={(e) => setAlmaInicio(e.target.value)} />
                  <p className="upload-section-description">A Group será usada antes desse mês e o Alma a partir dele. Movimentos da Group após a mudança ficarão fora da previsão e serão indicados na conferência. Deixe vazio para detectar a mudança pelo primeiro mês com movimentação no Alma.</p>
                </section>
              )}
              {(multiplos || alma) && (
                  <div className="form-group">
                    <h2 className="form-label">Período das receitas e despesas</h2>
                    <div className="file-grid">
                      <label className="form-hint">Mês inicial
                        <input className="form-input" type="month" value={periodoInicio} onChange={(e) => setPeriodoInicio(e.target.value)} />
                      </label>
                      <label className="form-hint">Mês final
                        <input className="form-input" type="month" value={periodoFim} onChange={(e) => setPeriodoFim(e.target.value)} />
                      </label>
                    </div>
                    <p className="form-hint">Deixe em branco para usar o período completo dos documentos. Cada mês deve pertencer a um único sistema, sem lacunas. Na mudança da Group para Alma, usamos a divisão detectada ou informada acima.</p>
                  </div>
              )}

              <Button
                type="submit"
                variant="primary"
                full
                style={{ marginTop: 'var(--s-lg)' }}
              >
                Iniciar análise
              </Button>
            </form>
          </Card>
        </div>
      </div>
    </>
  )
}
