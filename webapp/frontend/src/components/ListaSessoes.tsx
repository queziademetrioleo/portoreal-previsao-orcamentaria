import { useEffect, useState } from 'react'
import { listarSessoes, deletarSessao } from '../api'
import type { SessaoResumida } from '../api'

export default function ListaSessoes({ onNova, onAbrir }: {
  onNova: () => void
  onAbrir: (id: string, status: string) => void
}) {
  const [sessoes, setSessoes] = useState<SessaoResumida[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listarSessoes().then(setSessoes).catch(() => {}).finally(() => setLoading(false))
  }, [])

  async function handleDelete(e: React.MouseEvent, sid: string) {
    e.stopPropagation()
    if (!confirm('Excluir esta previsão?')) return
    try {
      await deletarSessao(sid)
      setSessoes(prev => prev.filter(s => s.sessao_id !== sid))
    } catch {
      alert('Erro ao excluir')
    }
  }

  return (
    <>
      <header className="app-header">
        <a href="/" className="logo">
          <img src="/assets/logo.png" alt="" /> Previsão Orçamentária
        </a>
      </header>
      <div className="container">
        <div className="eyebrow">Previsão Orçamentária</div>
        <h1 className="title">Condomínios</h1>
        <button className="btn btn-primary" onClick={onNova}>+ Nova Previsão</button>

        {loading && <div className="spinner" />}

        {!loading && sessoes.length === 0 && (
          <div className="empty">
            <p>Nenhuma previsão salva ainda.</p>
            <button className="btn btn-primary" onClick={onNova}>Criar primeira previsão</button>
          </div>
        )}

        {!loading && sessoes.length > 0 && (
          <div className="sessions-grid" style={{marginTop:'var(--s-xl)'}}>
            {sessoes.map(s => (
              <div key={s.sessao_id} className="session-card" onClick={() => onAbrir(s.sessao_id, s.status)} style={{position:'relative'}}>
                <button
                  className="btn btn-ghost btn-xs"
                  onClick={e => handleDelete(e, s.sessao_id)}
                  style={{position:'absolute',top:'var(--s-sm)',right:'var(--s-sm)',padding:'2px 6px',lineHeight:1,zIndex:1}}
                  title="Excluir"
                >
                  ✕
                </button>
                <h3>{s.nome}</h3>
                <p>Previsão {s.ano}</p>
                <span className={`badge ${s.status === 'gerado' ? 'badge-gerado' : 'badge-pendente'}`}>
                  {s.status === 'gerado' ? '✓ Gerado' : '📝 Em revisão'}
                </span>
                <time>{new Date(s.criado_em).toLocaleDateString('pt-BR')}</time>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  )
}
