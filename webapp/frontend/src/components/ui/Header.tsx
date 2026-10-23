import type { ReactNode } from 'react'

interface Props {
  onHome?: () => void
  children?: ReactNode
}

export default function Header({ onHome, children }: Props) {
  return (
    <header className="app-header">
      <button className="header-logo" onClick={onHome} type="button">
        <img src="/assets/logo-branca.png" alt="Porto Real Imóveis" />
        <span>Previsão Orçamentária</span>
      </button>
      <div className="header-actions">
        {children}
        {onHome && (
          <button className="btn btn-md btn-header" onClick={onHome} type="button">
            ← Menu principal
          </button>
        )}
      </div>
    </header>
  )
}
