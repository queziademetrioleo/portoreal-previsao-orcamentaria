import type { ReactNode, ButtonHTMLAttributes } from 'react'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
  full?: boolean
  children: ReactNode
}

const variantClass: Record<string, string> = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  ghost: 'btn-ghost',
  danger: 'btn-danger',
}

export default function Button({
  variant = 'secondary',
  size = 'md',
  full = false,
  className = '',
  children,
  ...rest
}: Props) {
  const cls = `btn ${variantClass[variant]} btn-${size} ${full ? 'btn-full' : ''} ${className}`.trim()
  return (
    <button className={cls} {...rest}>
      {children}
    </button>
  )
}
