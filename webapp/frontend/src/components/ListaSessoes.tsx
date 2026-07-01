import { useEffect, useState } from 'react'
import { listarSessoes, deletarSessao } from '../api'
import type { SessaoResumida } from '../api'
import Header from './ui/Header'
import Badge from './ui/Badge'
import Button from './ui/Button'
import Spinner from './ui/Spinner'
import EmptyState from './ui/EmptyState'

interface Props {
  onNova: () => void
  onAbrir: (id: string, status: string) => void
}

export default function ListaSessoes({ onNova, onAbrir }: Props) {
  const [sessoes, setSessoes] = useState<SessaoResumida[]>([])
  const [loading, setLoading] = useState(true)
  const [erro, setErro] = useState('')

  useEffect(() => {
    listarSessoes()
      .then(setSessoes)
      .catch((err) => setErro(err instanceof Error ? err.message : 'Erro ao carregar'))
      .finally(() => setLoading(false))
  }, [])

  async function handleDelete(e: React.MouseEvent, sid: string) {
    e.stopPropagation()
    if (!confirm('Excluir esta previsão?')) return
    try {
      await deletarSessao(sid)
      setSessoes((prev) => prev.filter((s) => s.sessao_id !== sid))
    } catch {
      alert('Erro ao excluir.')
    }
  }

  const statusBadge = (status: string) =>
    status === 'gerado' ? (
      <Badge label="Gerado" variant="success" />
    ) : (
      <Badge label="Em revisão" variant="warning" />
    )

  return (
    <>
      <Header>
        <Button variant="primary" onClick={onNova}>
          + Nova Previsão
        </Button>
      </Header>

      <div className="page">
        <p className="section-label">Previsão Orçamentária</p>
        <h1 className="page-title">Condomínios</h1>

        {loading && <Spinner text="Carregando..." />}

        {erro && <div className="alert-error">{erro}</div>}

        {!loading && !erro && sessoes.length === 0 && (
          <EmptyState
            message="Nenhuma previsão salva ainda."
            action={{ label: 'Criar primeira previsão', onClick: onNova }}
          />
        )}

        {!loading && sessoes.length > 0 && (
          <div className="sessions-grid">
            {sessoes.map((s) => (
              <div
                key={s.sessao_id}
                className="session-card"
                onClick={() => onAbrir(s.sessao_id, s.status)}
              >
                <button
                  className="btn btn-ghost btn-xs"
                  onClick={(e) => handleDelete(e, s.sessao_id)}
                  style={{
                    position: 'absolute',
                    top: 'var(--s-sm)',
                    right: 'var(--s-sm)',
                    padding: '2px 8px',
                    zIndex: 1,
                  }}
                  title="Excluir"
                >
                  ✕
                </button>
                <h3>{s.nome}</h3>
                <p>Previsão {s.ano}</p>
                {statusBadge(s.status)}
                <time>
                  {new Date(s.criado_em).toLocaleDateString('pt-BR')}
                </time>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  )
}
