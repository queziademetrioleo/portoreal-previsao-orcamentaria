interface Props {
  text?: string
}

export default function Spinner({ text }: Props) {
  return (
    <div className="spinner-wrap">
      <div className="spinner" />
      {text && <p className="spinner-text">{text}</p>}
    </div>
  )
}
