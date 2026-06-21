export default function BulkActions({ count, onApproveAll, onRejectAll, approveLabel, rejectLabel }: {
  count: number
  onApproveAll: () => void
  onRejectAll: () => void
  approveLabel?: string
  rejectLabel?: string
}) {
  if (count <= 1) return null
  return (
    <div className="bulk-actions">
      <button className="btn btn-approve btn-sm" onClick={onApproveAll}>
        ✓ {approveLabel || 'Aprovar todos'} ({count})
      </button>
      <button className="btn btn-reject btn-sm" onClick={onRejectAll}>
        ✗ {rejectLabel || 'Rejeitar todos'} ({count})
      </button>
    </div>
  )
}
