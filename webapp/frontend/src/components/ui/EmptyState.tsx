interface Props {
  message: string
  action?: { label: string; onClick: () => void }
}

export default function EmptyState({ message, action }: Props) {
  return (
    <div className="empty">
      <p>{message}</p>
      {action && (
        <button className="btn btn-primary btn-md" onClick={action.onClick}>
          {action.label}
        </button>
      )}
    </div>
  )
}
