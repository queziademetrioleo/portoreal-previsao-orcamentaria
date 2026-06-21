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
  const formRef = useRef<HTMLFormElement>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!nome.trim()) { setErro('Informe o nome do condomínio.'); return }
    if (!ano || ano < 2020 || ano > 2035) { setErro('Informe um ano válido (2020–2035).'); return }
    if (!balanual || !desbai) { setErro('Os arquivos balanual.xls e desbai06.xls são obrigatórios.'); return }
    setErro('')
    setLoading(true)
    try {
      const s = await criarSessao({ nome: nome.trim(), ano, balanual, desbai, dessin, inad })
      onCriada(s)
    } catch (err: any) {
      setErro(err.message || 'Erro ao enviar os arquivos.')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="container">
        <div className="upload-card card" style={{textAlign:'center'}}>
          <div className="spinner" />
          <p className="spinner-text">Analisando os relatórios... Isso pode levar até 6 minutos.</p>
          <p className="spinner-text" style={{color:'var(--t3)',fontSize:'12px'}}>A IA está classificando as despesas.</p>
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
              <p className="file-hint">* balanual.xls e desbai06.xls são obrigatórios</p>
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
