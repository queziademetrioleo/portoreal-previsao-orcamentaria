import { useState } from 'react'
import { createPortal } from 'react-dom'

export default function InfoModal({ titulo, texto }: { titulo: string; texto: string }) {
  const [aberto, setAberto] = useState(false)

  return (
    <>
      <button
        type="button"
        className="info-modal-trigger"
        onClick={() => setAberto(true)}
        aria-label={`O que é: ${titulo}`}
      >
        ?
      </button>

      {aberto && createPortal(
        <div className="info-modal-overlay" onClick={() => setAberto(false)}>
          <div
            className="info-modal-box"
            role="dialog"
            aria-modal="true"
            aria-label={titulo}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="info-modal-header">
              <strong>{titulo}</strong>
              <button
                type="button"
                className="info-modal-close"
                onClick={() => setAberto(false)}
                aria-label="Fechar"
              >
                ×
              </button>
            </div>
            <p>{texto}</p>
          </div>
        </div>,
        document.body,
      )}
    </>
  )
}
