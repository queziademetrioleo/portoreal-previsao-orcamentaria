interface Tab {
  id: string
  label: string
  count?: number
  attention?: boolean
}

interface Props {
  tabs: Tab[]
  active: string
  onChange: (id: string) => void
}

export default function TabBar({ tabs, active, onChange }: Props) {
  return (
    <nav className="tab-bar" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          role="tab"
          aria-selected={active === tab.id}
          className={`tab-btn ${active === tab.id ? 'active' : ''}${tab.attention ? ' attention' : ''}`}
          onClick={() => onChange(tab.id)}
          aria-label={tab.attention ? `${tab.label}: há itens pendentes de revisão` : tab.label}
        >
          {tab.label}
          {typeof tab.count === 'number' && <span className="tab-count">{tab.count}</span>}
        </button>
      ))}
    </nav>
  )
}
