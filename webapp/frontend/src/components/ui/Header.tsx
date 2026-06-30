import type { ReactNode } from 'react'

interface Props {
  onHome?: () => void
  children?: ReactNode
}

export default function Header({ onHome, children }: Props) {
  return (
    <header className="app-header">
      <button className="header-logo" onClick={onHome} type="button">
        <img src="/assets/logo.png" alt="" />
        <span>Previsão Orçamentária</span>
      </button>
      <div className="header-actions">{children}</div>
    </header>
  )
}
