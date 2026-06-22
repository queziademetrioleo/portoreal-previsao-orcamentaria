import { useState, useRef } from 'react'
import { criarSessao } from '../api'
import type { Sessao } from '../types'

export default function TelaUpload({ onCriada, onVoltar }: {
  onCriada: (s: Sessao) => void
  onVoltar: () => void
}) {
  const [nome, setNome] = useState('')
  const [ano, setAno] = useState(new Date().getFullYear())
  const [balanual, setBalanual] = useState<File | null>(null)
  const [desbai, setDesbai] = useState<File | null>(null)
  const [dessin, setDessin] = useState<File | null>(null)
  const [inad, setInad] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [erro, setErro] = useState('')
  const [progresso, setProgresso] = useState({fase:'Conectando...', passo:0, total:6, detalhe:''})
  const formRef = useRef<HTMLFormElement>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!nome.trim()) { setErro('Informe o nome do condomínio.'); return }
    if (!ano || ano < 2020 || ano > 2035) { setErro('Informe um ano válido (2020–2035).'); return }
    if (!balanual || !desbai) { setErro('Os arquivos balanual.xls e desbai06.xls são obrigatórios.'); return }
    setErro('')
    setLoading(true)
    try {
      const { sessao_id } = await criarSessao({ nome: nome.trim(), ano, balanual, desbai, dessin, inad })
      setLoading(true)

      // Connect to SSE for progress
      const base = import.meta.env.DEV ? 'http://localhost:8000' : ''
      const source = new EventSource(`${base}/api/sessao/${sessao_id}/analisar`)

      source.onmessage = (event) => {
        const data = JSON.parse(event.data)
        if (data.done) {
          source.close()
          // Fetch final session and go to review
          fetch(`${base}/api/sessao/${sessao_id}`)
            .then(r => r.json())
            .then(s => onCriada(s))
        } else {
          setProgresso(data)
        }
      }

      source.onerror = () => {
        source.close()
        setErro('Erro na conexão com o servidor. Tente novamente.')
        setLoading(false)
      }
    } catch (err: any) {
      setErro(err.message || 'Erro ao enviar os arquivos.')
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="container">
        <div className="upload-card card" style={{textAlign:'center'}}>
          <div className="spinner" />
          <div className="scan-line" />
          <p className="spinner-text" style={{fontSize:'18px',fontWeight:600,marginBottom:'24px'}}>
            Analisando os relatórios...
          </p>

          {/* Progress bar */}
          <div style={{marginBottom:'20px'}}>
            <div style={{
              display:'flex', justifyContent:'space-between',
              fontSize:'11px', color:'var(--t3)', marginBottom:'6px'
            }}>
              <span>Progresso</span>
              <span>{progresso.passo}/{progresso.total}</span>
            </div>
            <div style={{
              height:'4px', background:'var(--s2)', borderRadius:'2px', overflow:'hidden'
            }}>
              <div style={{
                height:'100%',
                width:`${(progresso.passo/progresso.total)*100}%`,
                background:'var(--extra)',
                borderRadius:'2px',
                transition:'width 0.5s ease'
              }} />
            </div>
          </div>

          {/* Current phase */}
          <div style={{
            background:'var(--s2)', borderRadius:'var(--r-card)',
            padding:'16px', marginBottom:'8px', textAlign:'left'
          }}>
            <div style={{fontSize:'11px',color:'var(--t3)',textTransform:'uppercase',letterSpacing:'0.5px',marginBottom:'4px'}}>
              Fase {progresso.passo} de {progresso.total}
            </div>
            <div style={{fontSize:'15px',fontWeight:600,color:'var(--t1)',marginBottom:'4px'}}>
              {progresso.fase}
            </div>
            {progresso.detalhe && (
              <div style={{fontSize:'13px',color:'var(--t2)'}}>
                {progresso.detalhe}
              </div>
            )}
          </div>

          <p className="spinner-text" style={{color:'var(--t3)',fontSize:'12px'}}>
            Isso pode levar até 6 minutos
          </p>
        </div>
      </div>
    )
  }

  return (
    <>
      <header className="app-header">
        <a href="/" className="logo" onClick={e => { e.preventDefault(); onVoltar() }}>
          <img src="/assets/logo.png" alt="" /> Previsão Orçamentária
        </a>
        <button className="btn btn-ghost btn-sm" onClick={onVoltar}>← Voltar</button>
      </header>
      <div className="container">
        <div className="upload-card card">
          <div className="eyebrow">Nova Análise</div>
          <h1 className="title">Envie os relatórios</h1>
          <p className="subtitle">Anexe os arquivos exportados do Condomínio21.</p>

          {erro && <div className="erro">{erro}</div>}

          <form ref={formRef} onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">Condomínio</label>
              <input className="form-input" type="text" value={nome} onChange={e => setNome(e.target.value)} placeholder="Nome do condomínio" />
            </div>
            <div className="form-group">
              <label className="form-label">Ano da previsão</label>
              <input className="form-input" type="number" value={ano} onChange={e => setAno(Number(e.target.value))} min={2020} max={2035} />
            </div>

            <div className="form-group">
              <label className="form-label">Relatórios</label>
              <div className="file-grid">
                <FileZone label="balanual.xls" file={balanual} setFile={setBalanual} required />
                <FileZone label="desbai06.xls" file={desbai} setFile={setDesbai} required />
                <FileZone label="dessin02.xls" file={dessin} setFile={setDessin} />
                <FileZone label="inad01.xls" file={inad} setFile={setInad} />
              </div>
              <p className="file-hint">* balanual.xls e desbai06.xls são obrigatórios. O sistema gera a previsão sem usar planilha manual.</p>
            </div>

            <button type="submit" className="btn btn-primary btn-full" style={{marginTop:'var(--s-lg)'}}>
              Iniciar análise
            </button>
          </form>
        </div>
      </div>
    </>
  )
}

function FileZone({ label, file, setFile, required }: {
  label: string
  file: File | null
  setFile: (f: File | null) => void
  required?: boolean
}) {
  return (
    <label className={`file-zone${file ? ' has-file' : ''}`}>
      <input type="file" accept=".xls,.xlsx" onChange={e => setFile(e.target.files?.[0] || null)} />
      <span className="file-icon">{file ? '📄' : '📎'}</span>
      <span className="file-name">{file ? file.name : label}{required ? ' *' : ''}</span>
      {file && <span className="file-check">✓</span>}
    </label>
  )
}
