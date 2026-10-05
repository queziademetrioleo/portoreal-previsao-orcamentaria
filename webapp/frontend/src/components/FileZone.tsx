import { useId, useRef, useState } from 'react'
import { validarArquivo } from '../utils/upload'

interface Props {
  label: string
  file: File | null
  setFile: (file: File | null) => void
  required?: boolean
  accept?: string
}

export default function FileZone({ label, file, setFile, required, accept = '.xls' }: Props) {
  const id = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [erro, setErro] = useState('')
  const [dragging, setDragging] = useState(false)

  function selecionar(files: FileList | null) {
    if (!files?.length) return
    if (files.length !== 1) {
      setErro('Selecione apenas um arquivo para este relatório.')
      return
    }
    const selected = files[0]
    const error = validarArquivo(selected, accept)
    setErro(error ?? '')
    if (!error) setFile(selected)
  }

  return (
    <div className="file-field">
      <span id={`${id}-label`} className="file-label">
        {label} {required && <span aria-label="obrigatório">*</span>}
      </span>
      <div
        className={`file-zone${file ? ' has-file' : ''}${dragging ? ' is-dragging' : ''}${erro ? ' has-error' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDragging(false)
        }}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          selecionar(e.dataTransfer.files)
        }}
      >
        <input
          ref={inputRef}
          className="file-input"
          type="file"
          accept={accept}
          aria-labelledby={`${id}-label`}
          tabIndex={-1}
          onChange={(e) => {
            selecionar(e.target.files)
            e.target.value = ''
          }}
        />
        <button
          className="file-select"
          type="button"
          aria-labelledby={`${id}-label ${id}-name`}
          aria-describedby={`${id}-hint${erro ? ` ${id}-error` : ''}`}
          aria-invalid={Boolean(erro)}
          onClick={() => inputRef.current?.click()}
        >
          <span className="file-icon" aria-hidden="true">{file ? '📄' : '📎'}</span>
          <span className="file-name" id={`${id}-name`}>
            {file ? file.name : 'Selecionar ou arrastar arquivo'}
          </span>
          {file && <span className="file-check" aria-hidden="true">✓</span>}
        </button>
        {file && <button
          className="file-remove"
          type="button"
          aria-label={`Remover arquivo de ${label}`}
          onClick={() => { setFile(null); setErro('') }}
        >Remover</button>}
      </div>
      <span className="file-format" id={`${id}-hint`}>{accept.toUpperCase()} · até 20 MB</span>
      {erro && <p className="file-error" id={`${id}-error`} role="alert">{erro}</p>}
    </div>
  )
}
