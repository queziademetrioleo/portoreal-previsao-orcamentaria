interface Props {
  label: string
  value: string
  detail?: string
  variant?: 'default' | 'positive' | 'negative' | 'accent' | 'warning'
}

const variantClass: Record<string, string> = {
  default: '',
  positive: 'num-positive',
  negative: 'num-negative',
  accent: 'num-accent',
  warning: 'num-warning',
}

export default function NumberBlock({ label, value, detail, variant = 'default' }: Props) {
  return (
    <div className={`number-block ${variantClass[variant]}`}>
      <span className="number-block-label">{label}</span>
      <strong className="number-block-value">{value}</strong>
      {detail && <small className="number-block-detail">{detail}</small>}
    </div>
  )
}
