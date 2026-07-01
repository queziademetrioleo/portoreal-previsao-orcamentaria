import { useState } from 'react'
import type { Sessao } from './types'
import ListaSessoes from './components/ListaSessoes'
import TelaUpload from './components/TelaUpload'
import TelaRevisao from './components/TelaRevisao'
import TelaResultado from './components/TelaResultado'
import { mockSessaoResultado } from './mockSessao'

type Tela = 'lista' | 'upload' | 'revisao' | 'resultado'

export default function App() {
  // Modo mock em dev para visualizar resultado sem backend
  const params = new URLSearchParams(window.location.search)
  if (import.meta.env.DEV && params.get('mock') === 'resultado') {
    return (
      <TelaResultado
        sessao={mockSessaoResultado}
        onVoltar={() => {
          window.location.href = '/'
        }}
      />
    )
  }

  const [tela, setTela] = useState<Tela>('lista')
  const [sessao, setSessao] = useState<Sessao | null>(null)
  const [sessaoResultado, setSessaoResultado] = useState<Sessao | null>(null)

  const abrirSessao = async (id: string, status: string) => {
    try {
      const r = await fetch(`/api/sessao/${id}`)
      if (!r.ok) throw new Error(`Erro ${r.status}`)
      if (status === 'gerado') {
        setSessaoResultado(await r.json())
        setTela('resultado')
        return
      }
      setSessao(await r.json())
      setTela('revisao')
    } catch {
      alert('Erro ao carregar sessao. Tente novamente.')
    }
  }

  if (tela === 'resultado' && sessaoResultado) {
    return <TelaResultado sessao={sessaoResultado} onVoltar={() => setTela('lista')} />
  }
  if (tela === 'revisao' && sessao) {
    return (
      <TelaRevisao
        sessao={sessao}
        onVoltar={() => setTela('lista')}
        onGerado={(s) => {
          setSessaoResultado(s)
          setTela('resultado')
        }}
      />
    )
  }
  if (tela === 'upload') {
    return (
      <TelaUpload
        onCriada={(s) => {
          setSessao(s)
          setTela('revisao')
        }}
        onVoltar={() => setTela('lista')}
      />
    )
  }
  return <ListaSessoes onNova={() => setTela('upload')} onAbrir={abrirSessao} />
}
