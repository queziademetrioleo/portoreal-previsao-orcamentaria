interface Props {
  label: string
  variant?: 'success' | 'warning' | 'danger' | 'neutral' | 'accent'
}

const variantClass: Record<string, string> = {
  success: 'badge-success',
  warning: 'badge-warning',
  danger: 'badge-danger',
  neutral: 'badge-neutral',
  accent: 'badge-accent',
}

export default function Badge({ label, variant = 'neutral' }: Props) {
  return <span className={`badge ${variantClass[variant]}`}>{label}</span>
}
