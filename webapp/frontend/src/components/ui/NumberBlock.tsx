interface Props {
  label: string
  value: string
  variant?: 'default' | 'positive' | 'negative' | 'accent'
}

const variantClass: Record<string, string> = {
  default: '',
  positive: 'num-positive',
  negative: 'num-negative',
  accent: 'num-accent',
}

export default function NumberBlock({ label, value, variant = 'default' }: Props) {
  return (
    <div className={`number-block ${variantClass[variant]}`}>
      <span className="number-block-label">{label}</span>
      <strong className="number-block-value">{value}</strong>
    </div>
  )
}
