import { useState, useRef, useEffect } from 'react'
import { criarSessao, mensagemErroApi } from '../api'
import type { Sessao } from '../types'
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
  const [origemRelatorios, setOrigemRelatorios] = useState<'condo21' | 'misto'>('condo21')
  const [nome, setNome] = useState('')
  const [ano, setAno] = useState(new Date().getFullYear())
  const [balanual, setBalanual] = useState<File | null>(null)
  const [desbai, setDesbai] = useState<File | null>(null)
  const [rec, setRec] = useState<File | null>(null)
  const [dessin, setDessin] = useState<File | null>(null)
  const [inad, setInad] = useState<File | null>(null)
  const [almaBal, setAlmaBal] = useState<File | null>(null)
  const [almaFin, setAlmaFin] = useState<File | null>(null)
  const [almaRec, setAlmaRec] = useState<File | null>(null)
  const [almaInad, setAlmaInad] = useState<File | null>(null)
  const [planoAlma, setPlanoAlma] = useState<File | null>(null)
  const [semInadAlma, setSemInadAlma] = useState(false)
  const [periodoInicio, setPeriodoInicio] = useState('')
  const [periodoFim, setPeriodoFim] = useState('')
  const misto = origemRelatorios === 'misto'
  const [loading, setLoading] = useState(false)
  const [erro, setErro] = useState('')
  const [progresso, setProgresso] = useState({
    fase: 'Conectando...',
    passo: 0,
    total: 6,
    detalhe: '',
  })
  const eventSourceRef = useRef<EventSource | null>(null)

  // Cleanup EventSource on unmount
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close()
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!nome.trim()) {
      setErro('Informe o nome do condomínio.')
      return
    }
    if (!ano || ano < 2020 || ano > 2035) {
      setErro('Informe um ano válido (2020–2035).')
      return
    }
    if (!balanual || !desbai || !rec) {
      setErro('Os arquivos balanual.xls, desbai06.xls e rec02.xls são obrigatórios.')
      return
    }
    if (misto && (!almaBal || !almaFin || !almaRec || !planoAlma)) {
      setErro('Envie também o demonstrativo, FIN, contas a receber e plano de contas do Alma.')
      return
    }
    if (misto && !almaInad && !semInadAlma) {
      setErro('Envie o relatório de inadimplência do Alma ou marque que não há inadimplência.')
      return
    }
    if (misto && (Boolean(periodoInicio) !== Boolean(periodoFim) || (periodoInicio && periodoInicio > periodoFim))) {
      setErro('Informe início e fim do período em ordem, ou deixe ambos em branco.')
      return
    }
    setErro('')
    setLoading(true)

    try {
      const { sessao_id } = await criarSessao({
        nome: nome.trim(),
        ano,
        balanual,
        desbai,
        rec,
        dessin,
        inad,
        origemSistema: origemRelatorios,
        ...(misto ? {
          almaBal, almaFin, almaRec, almaInad, planoAlma,
          semInadAlma, periodoInicio, periodoFim,
        } : {}),
      })

      const base = import.meta.env.DEV ? 'http://localhost:8000' : ''
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
            .then((s) => onCriada(s))
            .catch((err) => {
              setErro(err.message || 'Erro ao carregar resultado.')
              setLoading(false)
            })
        } else {
          setProgresso(data)
        }
      }

      source.onerror = () => {
        source.close()
        setErro('Erro na conexão com o servidor. Tente novamente.')
        setLoading(false)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Erro ao enviar os arquivos.'
      setErro(msg)
      setLoading(false)
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
              <Spinner text="Analisando os relatórios..." />
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
              Selecione a origem e anexe os relatórios do condomínio.
            </p>

            {erro && <div className="alert-error">{erro}</div>}

            <form onSubmit={handleSubmit}>
              <fieldset className="form-group report-source">
                <legend className="form-label">Origem dos relatórios</legend>
                <div className="report-source-options">
                  <label className={`report-source-option${origemRelatorios === 'condo21' ? ' is-selected' : ''}`}>
                    <input
                      type="radio"
                      name="origem-relatorios"
                      value="condo21"
                      checked={origemRelatorios === 'condo21'}
                      onChange={() => setOrigemRelatorios('condo21')}
                    />
                    <span>
                      <strong>Condo21</strong>
                      <small>Padrão atual</small>
                    </span>
                  </label>
                  <label className={`report-source-option${misto ? ' is-selected' : ''}`}>
                    <input
                      type="radio"
                      name="origem-relatorios"
                      value="misto"
                      checked={misto}
                      onChange={() => setOrigemRelatorios('misto')}
                    />
                    <span>
                      <strong>Condo21 + Alma</strong>
                      <small>Meses dos dois sistemas</small>
                    </span>
                  </label>
                </div>
              </fieldset>

              <div className="form-group">
                <label className="form-label">Condomínio</label>
                <input
                  className="form-input"
                  type="text"
                  value={nome}
                  onChange={(e) => setNome(e.target.value)}
                  placeholder="Nome do condomínio"
                />
              </div>

              <div className="form-group">
                <label className="form-label">Ano da previsão</label>
                <input
                  className="form-input"
                  type="number"
                  value={ano}
                  onChange={(e) => setAno(Number(e.target.value))}
                  min={2020}
                  max={2035}
                />
              </div>

              <div className="form-group">
                <h2 className="form-label">Relatórios do Condo21</h2>
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
                  {!misto && <FileZone
                    label="inad01.xls (opcional)"
                    file={inad}
                    setFile={setInad}
                  />}
                </div>
                <p className="form-hint">
                  {misto
                    ? 'Envie os relatórios do período que ficou no Condo21. A inadimplência será consultada somente no Alma.'
                    : '* balanual.xls, desbai06.xls e rec02.xls são obrigatórios. inad01.xls é opcional — só anexe se houver inadimplência.'}
                </p>
              </div>

              {misto && (
                <>
                  <div className="form-group">
                    <h2 className="form-label">Relatórios do Alma</h2>
                    <div className="file-grid">
                      <FileZone label="Demonstrativo por período (PDF)" file={almaBal} setFile={setAlmaBal} accept=".pdf" required />
                      <FileZone label="FIN00601 — despesas detalhadas (XLSX)" file={almaFin} setFile={setAlmaFin} accept=".xlsx" required />
                      <FileZone label="Contas a receber agrupado por conta (PDF)" file={almaRec} setFile={setAlmaRec} accept=".pdf" required />
                      <FileZone label="Plano de contas Almah (XLSX)" file={planoAlma} setFile={setPlanoAlma} accept=".xlsx" required />
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
                  </div>
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
                    <p className="form-hint">Deixe em branco para usar o período completo dos documentos. Os pagamentos do FIN são selecionados pela Data Pagto.</p>
                  </div>
                </>
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

function FileZone({
  label,
  file,
  setFile,
  required,
  accept = '.xls',
}: {
  label: string
  file: File | null
  setFile: (f: File | null) => void
  required?: boolean
  accept?: string
}) {
  return (
    <label className={`file-zone${file ? ' has-file' : ''}`}>
      <input
        type="file"
        accept={accept}
        aria-label={label}
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />
      <span className="file-icon">{file ? '📄' : '📎'}</span>
      <span className="file-name">
        {file ? file.name : label}
        {required ? ' *' : ''}
      </span>
      {file && <span className="file-check">✓</span>}
    </label>
  )
}
