import { useState } from 'react'

export interface ModalState {
  isOpen: boolean
  title: string
  message: string
  type: 'error' | 'success' | 'info' | 'warning'
}

export function useModal() {
  const [modal, setModal] = useState<ModalState>({
    isOpen: false,
    title: '',
    message: '',
    type: 'info'
  })

  const showModal = (
    title: string,
    message: string,
    type: 'error' | 'success' | 'info' | 'warning' = 'info'
  ) => {
    setModal({
      isOpen: true,
      title,
      message,
      type
    })
  }

  const showError = (message: string, title: string = 'Error') => {
    showModal(title, message, 'error')
  }

  const showSuccess = (message: string, title: string = 'Éxito') => {
    showModal(title, message, 'success')
  }

  const showInfo = (message: string, title: string = 'Información') => {
    showModal(title, message, 'info')
  }

  const showWarning = (message: string, title: string = 'Advertencia') => {
    showModal(title, message, 'warning')
  }

  const closeModal = () => {
    setModal(prev => ({ ...prev, isOpen: false }))
  }

  return {
    modal,
    showModal,
    showError,
    showSuccess,
    showInfo,
    showWarning,
    closeModal
  }
}
