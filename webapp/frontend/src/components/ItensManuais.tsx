import { useState, type FormEvent } from 'react'
import type { ItemManual } from '../types'
import { money } from '../utils/format'
import { formatarValorMensal, parseValorMensal } from '../utils/valorMensal'
import Card from './ui/Card'
import Button from './ui/Button'
import './ItensManuais.css'

export default function ItensManuais({ itens, salvar }: {
  itens: ItemManual[]; salvar: (itens: ItemManual[]) => Promise<void>
}) {
  const [tipo, setTipo] = useState<ItemManual['tipo']>('receita')
  const [nome, setNome] = useState('')
  const [valor, setValor] = useState('')
  const [editando, setEditando] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const [erro, setErro] = useState('')
  const [status, setStatus] = useState('')
  function limpar() { setNome(''); setValor(''); setEditando(null) }
  async function persistir(proximos: ItemManual[], mensagem: string) {
    setOcupado(true); setErro(''); setStatus('')
    try { await salvar(proximos); limpar(); setStatus(mensagem) }
    catch (e) { setErro(e instanceof Error ? e.message : 'Não foi possível salvar. Tente novamente.') }
    finally { setOcupado(false) }
  }
  async function adicionar(e: FormEvent) {
    e.preventDefault()
    const numero = parseValorMensal(valor)
    if (!nome.trim() || numero === null) {
      setErro('Informe um nome e um valor mensal válido, maior que zero.'); return
    }
    const item: ItemManual = { id: editando ?? crypto.randomUUID(), tipo, nome: nome.trim(), valor: Math.round(numero * 100) / 100 }
    await persistir(editando ? itens.map(i => i.id === editando ? item : i) : [...itens, item], 'Lançamento salvo na previsão.')
  }
  return <Card className="manual-items">
    <details>
      <summary className="manual-toggle">Adicionar receita ou despesa
        {itens.length > 0 && <span className="manual-count">{itens.length} {itens.length === 1 ? 'lançamento salvo' : 'lançamentos salvos'}</span>}
      </summary>
      <div className="manual-content">
    <form onSubmit={adicionar}>
      <fieldset disabled={ocupado}>
        <legend>Tipo de lançamento</legend>
        <div className="manual-types">
          <label><input type="radio" name="tipo-manual" checked={tipo === 'receita'} onChange={() => setTipo('receita')} /> Receita</label>
          <label><input type="radio" name="tipo-manual" checked={tipo === 'despesa'} onChange={() => setTipo('despesa')} /> Despesa</label>
        </div>
        <div className="manual-fields">
          <label>Nome<input value={nome} onChange={e => setNome(e.target.value)} required maxLength={120} placeholder="Ex.: locação do salão" /></label>
          <label>Valor mensal (R$)<input value={valor} onChange={e => setValor(formatarValorMensal(e.target.value))} required inputMode="decimal" placeholder="0,00" /></label>
          <Button type="submit" variant="primary">{ocupado ? 'Salvando…' : editando ? 'Salvar alteração' : 'Salvar lançamento'}</Button>
          {editando && <Button type="button" onClick={limpar}>Cancelar</Button>}
        </div>
      </fieldset>
    </form>
    {erro && <p role="alert" className="manual-error">{erro}</p>}
    <p role="status">{status}</p>
    {itens.length > 0 && <ul className="manual-list">{itens.map(i => <li key={i.id}>
      <div><strong>{i.nome}</strong><span>{i.tipo === 'receita' ? 'Receita' : 'Despesa'} · {money(i.valor)} por mês</span></div>
      <div><Button size="sm" disabled={ocupado} onClick={() => { setEditando(i.id); setTipo(i.tipo); setNome(i.nome); setValor(formatarValorMensal(i.valor.toFixed(2))); setErro(''); setStatus('') }}>Editar</Button>
      <Button size="sm" variant="danger" disabled={ocupado} onClick={() => persistir(itens.filter(x => x.id !== i.id), 'Lançamento removido.')}>Remover</Button></div>
    </li>)}</ul>}
      </div>
    </details>
  </Card>
}
