interface Props {
  passo: number
  total: number
  fase: string
  detalhe?: string
}

export default function ProgressBar({ passo, total, fase, detalhe }: Props) {
  const pct = total > 0 ? (passo / total) * 100 : 0

  return (
    <div className="progress-wrap">
      <div className="progress-header">
        <span>Progresso</span>
        <span>
          {passo}/{total}
        </span>
      </div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="progress-info">
        <strong>{fase}</strong>
        {detalhe && <p>{detalhe}</p>}
      </div>
    </div>
  )
}
