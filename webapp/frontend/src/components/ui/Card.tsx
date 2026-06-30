import type { ReactNode } from 'react'

interface Props {
  children: ReactNode
  className?: string
  padding?: 'md' | 'lg'
}

export default function Card({ children, className = '', padding = 'lg' }: Props) {
  const cls = `card card-${padding} ${className}`.trim()
  return <div className={cls}>{children}</div>
}
