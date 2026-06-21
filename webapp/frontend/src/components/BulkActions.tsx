interface Props {
  onApproveAll: () => void
  onRejectAll: () => void
  count: number
}

export default function BulkActions({ onApproveAll, onRejectAll, count }: Props) {
  if (count <= 1) return null
  return (
    <div className="bulk-actions">
      <button className="bulk-aprovar" onClick={onApproveAll}>
        Aprovar todos ({count})
      </button>
      <button className="bulk-reprovar" onClick={onRejectAll}>
        Rejeitar todos ({count})
      </button>
    </div>
  )
}
