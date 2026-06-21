import './App.css'
import { useState } from 'react'
import type { Sessao } from './types'
import ListaSessoes from './components/ListaSessoes'
import TelaUpload from './components/TelaUpload'
import TelaRevisao from './components/TelaRevisao'

type Tela = 'lista' | 'upload' | 'revisao'

export default function App() {
  const [tela, setTela] = useState<Tela>('lista')
  const [sessao, setSessao] = useState<Sessao | null>(null)

  const abrirSessao = async (id: string, status: string) => {
    if (status === 'gerado') {
      window.location.assign(`/api/sessao/${id}/download`)
      return
    }
    const r = await fetch(`/api/sessao/${id}`)
    setSessao(await r.json())
    setTela('revisao')
  }

  if (tela === 'revisao' && sessao) {
    return <TelaRevisao sessao={sessao} onVoltar={() => setTela('lista')} />
  }
  if (tela === 'upload') {
    return <TelaUpload onCriada={(s) => { setSessao(s); setTela('revisao') }} onVoltar={() => setTela('lista')} />
  }
  return <ListaSessoes onNova={() => setTela('upload')} onAbrir={abrirSessao} />
}
