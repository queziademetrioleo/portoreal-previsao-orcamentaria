import { useState } from 'react'
import type { Sessao } from './types'
import ListaSessoes from './components/ListaSessoes'
import TelaUpload from './components/TelaUpload'
import TelaRevisao from './components/TelaRevisao'
import './App.css'

type Tela = 'lista' | 'upload' | 'revisao'

export default function App() {
  const [tela, setTela] = useState<Tela>('lista')
  const [sessao, setSessao] = useState<Sessao | null>(null)

  return (
    <main className="container">
      {tela === 'lista' && (
        <ListaSessoes
          onNova={() => setTela('upload')}
          onRetomar={(s) => { setSessao(s); setTela('revisao') }}
        />
      )}
      {tela === 'upload' && (
        <TelaUpload
          onSessaoCriada={(s) => { setSessao(s); setTela('revisao') }}
          onVoltar={() => setTela('lista')}
        />
      )}
      {tela === 'revisao' && sessao && (
        <TelaRevisao sessao={sessao} />
      )}
    </main>
  )
}
