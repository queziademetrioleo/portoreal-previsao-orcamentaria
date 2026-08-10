import { useState, useRef, useEffect } from 'react'
import { criarSessao } from '../api'
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
  const [nome, setNome] = useState('')
  const [ano, setAno] = useState(new Date().getFullYear())
  const [balanual, setBalanual] = useState<File | null>(null)
  const [desbai, setDesbai] = useState<File | null>(null)
  const [rec, setRec] = useState<File | null>(null)
  const [dessin, setDessin] = useState<File | null>(null)
  const [inad, setInad] = useState<File | null>(null)
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
    if (!ano || ano < 2020 || ano > 2035) {
      setErro('Informe um ano válido (2020–2035).')
      return
    }
    if (!balanual || !desbai || !rec) {
      setErro('Os arquivos balanual.xls, desbai06.xls e rec02.xls são obrigatórios.')
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
          setErro(data.error)
          setLoading(false)
          return
        }
        if (data.done) {
          source.close()
          fetch(`${base}/api/sessao/${sessao_id}`)
            .then((r) => {
              if (!r.ok) throw new Error(`Erro ${r.status}`)
              return r.json()
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
              Anexe os arquivos exportados do Condomínio21.
            </p>

            {erro && <div className="alert-error">{erro}</div>}

            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Condomínio (opcional — detectado automaticamente)</label>
                <input
                  className="form-input"
                  type="text"
                  value={nome}
                  onChange={(e) => setNome(e.target.value)}
                  placeholder="Será detectado do arquivo REC"
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
                <label className="form-label">Relatórios</label>
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
                  <FileZone
                    label="inad01.xls (opcional)"
                    file={inad}
                    setFile={setInad}
                  />
                </div>
                <p className="form-hint">
                  * balanual.xls, desbai06.xls e rec02.xls são obrigatórios — o REC traz a receita real e atual do condomínio. inad01.xls é opcional — só anexe se houver inadimplência.
                </p>
              </div>

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
}: {
  label: string
  file: File | null
  setFile: (f: File | null) => void
  required?: boolean
}) {
  return (
    <label className={`file-zone${file ? ' has-file' : ''}`}>
      <input
        type="file"
        accept=".xls"
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
