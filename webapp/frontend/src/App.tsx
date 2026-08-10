import { useState } from 'react'
import type { Sessao } from './types'
import ListaSessoes from './components/ListaSessoes'
import TelaUpload from './components/TelaUpload'
import TelaRevisao from './components/TelaRevisao'

type Tela = 'lista' | 'upload' | 'revisao'

export default function App() {
  const [tela, setTela] = useState<Tela>('lista')
  const [sessao, setSessao] = useState<Sessao | null>(null)

  const abrirSessao = async (id: string, _status: string) => {
    try {
      const r = await fetch(`/api/sessao/${id}`)
      if (!r.ok) throw new Error(`Erro ${r.status}`)
      setSessao(await r.json())
      setTela('revisao')
    } catch {
      alert('Erro ao carregar sessao. Tente novamente.')
    }
  }

  if (tela === 'revisao' && sessao) {
    return (
      <TelaRevisao
        sessao={sessao}
        onVoltar={() => setTela('lista')}
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
