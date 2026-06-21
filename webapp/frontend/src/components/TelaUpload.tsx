import { useState } from 'react'
import { criarSessao } from '../api'
import type { Sessao } from '../types'

interface Props {
  onSessaoCriada: (s: Sessao) => void
  onVoltar: () => void
}

const ETAPAS = [
  'Lendo balanual.xls — demonstrativo de receitas e despesas...',
  'Lendo desbai06.xls — despesas nota fiscal por nota fiscal...',
  'Extraindo contas, grupos e valores mensais...',
  'Analisando inadimplencia...',
  'IA classificando notas fiscais ambiguas...',
  'Aplicando regras de calculo (R1 a R8)...',
  'Montando resultado final...',
]

const CAMPOS: Array<{ chave: string; rotulo: string; obrigatorio: boolean }> = [
  { chave: 'balanual', rotulo: 'balanual.xls — Demonstrativo anual', obrigatorio: true },
  { chave: 'desbai', rotulo: 'desbai06.xls — Despesas baixadas (NF a NF)', obrigatorio: true },
  { chave: 'dessin', rotulo: 'dessin02.xls — Sintetico de despesas', obrigatorio: false },
  { chave: 'inad', rotulo: 'inad01.xls — Inadimplencia', obrigatorio: false },
]

export default function TelaUpload({ onSessaoCriada, onVoltar }: Props) {
  const [nome, setNome] = useState('')
  const [ano, setAno] = useState(new Date().getFullYear() + 1)
  const [arquivos, setArquivos] = useState<Record<string, File | null>>({
    balanual: null, desbai: null, dessin: null, inad: null,
  })
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState('')
  const [progresso, setProgresso] = useState('')

  async function enviar() {
    if (!nome.trim() || !arquivos.balanual || !arquivos.desbai) {
      setErro('Preencha o nome do condominio e os dois arquivos obrigatorios.')
      return
    }
    setErro('')
    setCarregando(true)
    setProgresso(ETAPAS[0])

    let i = 0
    const anim = setInterval(() => {
      i = (i + 1) % ETAPAS.length
      setProgresso(ETAPAS[i])
    }, 3000)

    try {
      const s = await criarSessao({
        nome: nome.trim(), ano,
        balanual: arquivos.balanual, desbai: arquivos.desbai,
        dessin: arquivos.dessin, inad: arquivos.inad,
      })
      clearInterval(anim)
      onSessaoCriada(s)
    } catch (e) {
      clearInterval(anim)
      setErro(e instanceof Error ? e.message : String(e))
    } finally {
      setCarregando(false)
      setProgresso('')
    }
  }

  return (
    <div className="card upload fade-in">
      <div className="upload-header">
        <button className="btn-voltar" onClick={onVoltar}>
          &larr; Voltar
        </button>
        <div className="header-logo">
          <img src="/assets/logo.png" alt="Porto Real" className="logo" />
          <div>
            <h1>Previsao Orcamentaria</h1>
            <p className="sub">
              Envie os relatorios do Condominio para que a analise seja feita
              e a IA consiga gerar seu relatorio. Uma revisao sera feita antes
              de gerar o documento final.
            </p>
          </div>
        </div>
      </div>

      <label className="campo">
        <span>Nome do condominio</span>
        <input
          value={nome}
          onChange={e => setNome(e.target.value)}
          placeholder="COND. ED. CHATEAU LAVOISIER"
        />
      </label>

      <label className="campo">
        <span>Ano da previsao</span>
        <input
          type="number"
          value={ano}
          onChange={e => setAno(Number(e.target.value))}
        />
      </label>

      {CAMPOS.map(c => (
        <label key={c.chave} className={`arquivo ${arquivos[c.chave] ? 'ok' : ''}`}>
          <span>
            {c.rotulo} {c.obrigatorio ? '*' : '(opcional)'}
          </span>
          <input
            type="file"
            accept=".xls"
            onChange={e =>
              setArquivos(a => ({ ...a, [c.chave]: e.target.files?.[0] ?? null }))
            }
          />
          {arquivos[c.chave] && <em>{arquivos[c.chave]!.name}</em>}
        </label>
      ))}

      {erro && <div className="erro">{erro}</div>}

      {carregando ? (
        <div className="loading-container">
          <div className="spinner" />
          <p className="loading-texto">{progresso}</p>
          <p className="loading-aviso">Aguarde — isso pode levar ate 3 minutos</p>
        </div>
      ) : (
        <button className="primario" onClick={enviar}>
          Analisar
        </button>
      )}
    </div>
  )
}
