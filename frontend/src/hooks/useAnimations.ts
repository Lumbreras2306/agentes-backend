import { useState, useCallback } from 'react'

export interface ActiveAnimation {
  id: string
  type: 'move' | 'fumigate' | 'analyze' | 'refill'
  agentId: string
  startTime: number
  duration: number
  from?: [number, number]
  to?: [number, number]
  position?: [number, number]
  data?: any
}

export function useAnimations() {
  const [activeAnimations, setActiveAnimations] = useState<Map<string, ActiveAnimation>>(new Map())

  const startAnimation = useCallback((animation: ActiveAnimation) => {
    setActiveAnimations(prev => {
      const newMap = new Map(prev)
      newMap.set(animation.id, animation)
      return newMap
    })

    // Limpiar animación después de su duración
    setTimeout(() => {
      setActiveAnimations(prev => {
        const newMap = new Map(prev)
        newMap.delete(animation.id)
        return newMap
      })
    }, animation.duration)
  }, [])

  const clearAnimation = useCallback((id: string) => {
    setActiveAnimations(prev => {
      const newMap = new Map(prev)
      newMap.delete(id)
      return newMap
    })
  }, [])

  const clearAllAnimations = useCallback(() => {
    setActiveAnimations(new Map())
  }, [])

  return {
    activeAnimations,
    startAnimation,
    clearAnimation,
    clearAllAnimations,
  }
}

