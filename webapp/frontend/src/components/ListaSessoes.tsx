import { useEffect, useState } from 'react'
import { type SessaoResumida, listarSessoes } from '../api'
import type { Sessao } from '../types'

const BASE = import.meta.env.DEV ? 'http://localhost:8000' : ''

interface Props {
  onNova: () => void
  onRetomar: (s: Sessao) => void
}

const STATUS_LABEL: Record<string, string> = {
  em_revisao: 'Em revisao',
  gerado: 'Documento gerado',
}

const STATUS_CLASSE: Record<string, string> = {
  em_revisao: 'status-revisao',
  gerado: 'status-gerado',
}

export default function ListaSessoes({ onNova, onRetomar }: Props) {
  const [sessoes, setSessoes] = useState<SessaoResumida[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')

  useEffect(() => {
    listarSessoes()
      .then(setSessoes)
      .catch(e => setErro(e instanceof Error ? e.message : String(e)))
      .finally(() => setCarregando(false))
  }, [])

  async function retomar(s: SessaoResumida) {
    try {
      const r = await fetch(`${BASE}/api/sessao/${s.sessao_id}`)
      if (!r.ok) throw new Error(`Erro ${r.status}`)
      const sessao: Sessao = await r.json()
      onRetomar(sessao)
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e))
    }
  }

  function download(s: SessaoResumida) {
    const url = `${BASE}/api/sessao/${s.sessao_id}/download`
    window.open(url, '_blank')
  }

  return (
    <div className="lista-sessoes fade-in">
      <div className="header-logo">
        <img src="/assets/logo.png" alt="Porto Real" className="logo" />
        <div>
          <h1>Previsao Orcamentaria</h1>
          <p className="sub">
            Sessoes de previsao orcamentaria para seu condominio.
          </p>
        </div>
      </div>

      <button className="primario" onClick={onNova}>
        + Nova previsao
      </button>

      {erro && <div className="erro">{erro}</div>}

      {carregando && (
        <div className="loading-container">
          <div className="spinner" />
          <p className="loading-texto">Carregando sessoes...</p>
        </div>
      )}

      {!carregando && sessoes.length === 0 && !erro && (
        <p className="vazio-msg">
          Nenhuma sessao encontrada. Crie uma nova previsao orcamentaria para
          comecar.
        </p>
      )}

      {sessoes.length > 0 && (
        <div className="sessoes-grid">
          {sessoes.map(s => (
            <div key={s.sessao_id} className="sessao-card">
              <div className="sessao-card-body">
                <h3 className="sessao-nome">{s.nome}</h3>
                <div className="sessao-meta">
                  <span>Ano: {s.ano}</span>
                  <span>
                    Criada em: {new Date(s.criado_em).toLocaleDateString('pt-BR')}
                  </span>
                </div>
                <span
                  className={`sessao-status ${STATUS_CLASSE[s.status] || ''}`}
                >
                  {STATUS_LABEL[s.status] || s.status}
                </span>
              </div>
              <div className="sessao-card-actions">
                <button
                  className="mini aprovar"
                  onClick={() => retomar(s)}
                >
                  {s.status === 'gerado' ? 'Visualizar' : 'Retomar revisao'}
                </button>
                {s.status === 'gerado' && (
                  <button
                    className="mini neutro"
                    onClick={() => download(s)}
                  >
                    Download
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
