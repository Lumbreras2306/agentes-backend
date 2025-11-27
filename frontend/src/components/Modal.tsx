import { useEffect } from 'react'
import './Modal.css'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title: string
  message: string
  type?: 'error' | 'success' | 'info' | 'warning'
  showCloseButton?: boolean
}

export default function Modal({
  isOpen,
  onClose,
  title,
  message,
  type = 'info',
  showCloseButton = true
}: ModalProps) {
  // Cerrar con ESC
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [isOpen, onClose])

  // Prevenir scroll del body cuando el modal está abierto
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = 'unset'
    }
    return () => {
      document.body.style.overflow = 'unset'
    }
  }, [isOpen])

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className={`modal-content modal-${type}`} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className={`modal-title modal-title-${type}`}>{title}</h2>
          {showCloseButton && (
            <button className="modal-close" onClick={onClose} aria-label="Cerrar">
              ×
            </button>
          )}
        </div>
        <div className="modal-body">
          <p>{message}</p>
        </div>
        <div className="modal-footer">
          <button className={`modal-button modal-button-${type}`} onClick={onClose}>
            Aceptar
          </button>
        </div>
      </div>
    </div>
  )
}
