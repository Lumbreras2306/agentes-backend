import { useEffect, useRef, useState, useCallback } from 'react'
import './DijkstraAnimation.css'

interface DijkstraAnimationProps {
  grid: number[][]
  width: number
  height: number
  barnPos: number[]
  tractorPaths: number[][][]
  destinations: number[][]
  simulationSteps: Array<Array<{
    position: number[]
    path_index: number
    waiting: boolean
    arrived: boolean
    path_recalculated?: boolean
    color: string
  }>>
  tractorColors: string[]
  infestationGrid?: number[][]
  tileColors: {
    IMPASSABLE: string
    ROAD: string
    FIELD: string
    BARN: string
  }
  speed?: number
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

function lerp(start: number, end: number, t: number): number {
  return start + (end - start) * t
}

export default function DijkstraAnimation({
  grid,
  width,
  height,
  barnPos,
  tractorPaths,
  destinations,
  simulationSteps,
  tractorColors,
  infestationGrid,
  tileColors,
  speed = 300,
}: DijkstraAnimationProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [currentStep, setCurrentStep] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const pathsTakenRef = useRef<Array<Set<string>>>([])
  
  const animationFrameRef = useRef<number>()
  const lastStepTimeRef = useRef<number>(0)
  const interpolationRef = useRef<number>(1)
  const currentStepRef = useRef<number>(0)

  useEffect(() => {
    pathsTakenRef.current = tractorPaths.map(() => new Set())
  }, [tractorPaths])

  useEffect(() => {
    currentStepRef.current = currentStep
    interpolationRef.current = 0
    lastStepTimeRef.current = performance.now()
  }, [currentStep])

  const maxSteps = simulationSteps.length

  const renderCanvas = useCallback((interpolation: number) => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const step = currentStepRef.current

    const cellSize = Math.min(
      Math.floor(canvas.width / width),
      Math.floor(canvas.height / height)
    )

    const offsetX = (canvas.width - width * cellSize) / 2
    const offsetZ = (canvas.height - height * cellSize) / 2

    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)

    // Dibujar grid base
    for (let z = 0; z < height; z++) {
      for (let x = 0; x < width; x++) {
        const tileType = grid[z][x]
        let color = tileColors.IMPASSABLE

        if (tileType === 1) color = tileColors.ROAD
        else if (tileType === 2) color = tileColors.FIELD
        else if (tileType === 3) color = tileColors.BARN

        const xPos = offsetX + x * cellSize
        const zPos = offsetZ + z * cellSize

        ctx.fillStyle = color
        ctx.fillRect(xPos, zPos, cellSize, cellSize)

        // Mostrar toda la infestación desde el inicio
        if (infestationGrid && infestationGrid[z] && infestationGrid[z][x] !== undefined) {
          const infestationLevel = infestationGrid[z][x]
          if (infestationLevel > 0) {
            const intensity = infestationLevel / 100
            const r = Math.floor(255 * intensity)
            const g = Math.floor(255 * (1 - intensity * 0.5))
            const b = 0
            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.6)`
            ctx.fillRect(xPos, zPos, cellSize, cellSize)
          }
        }

        ctx.strokeStyle = 'rgba(0, 0, 0, 0.1)'
        ctx.strokeRect(xPos, zPos, cellSize, cellSize)
      }
    }

    // Dibujar caminos recorridos de tractores
    if (step < simulationSteps.length) {
      const stepData = simulationSteps[step]

      stepData.forEach((tractorState, tractorId) => {
        const pathIndex = tractorState.path_index
        const path = tractorPaths[tractorId]
        if (path) {
          for (let i = 0; i <= Math.min(pathIndex, path.length - 1); i++) {
            const pos = path[i]
            if (pos && pos.length >= 2) {
              const px = clamp(pos[0], 0, width - 1)
              const pz = clamp(pos[1], 0, height - 1)
              pathsTakenRef.current[tractorId].add(`${px},${pz}`)
            }
          }
        }
      })

      pathsTakenRef.current.forEach((pathSet, tractorId) => {
        const color = tractorColors[tractorId]
        ctx.fillStyle = color
        ctx.globalAlpha = 0.3

        pathSet.forEach((posStr) => {
          const [px, pz] = posStr.split(',').map(Number)
          if (px < 0 || px >= width || pz < 0 || pz >= height) return

          const [bx, bz] = barnPos
          const isDest = destinations.some((dest) => dest[0] === px && dest[1] === pz)

          if (!(px === bx && pz === bz) && !isDest) {
            const currentTractorPos = stepData[tractorId]?.position
            if (!currentTractorPos || currentTractorPos[0] !== px || currentTractorPos[1] !== pz) {
              const xPos = offsetX + px * cellSize
              const zPos = offsetZ + pz * cellSize
              ctx.fillRect(xPos, zPos, cellSize, cellSize)
            }
          }
        })

        ctx.globalAlpha = 1.0
      })
    }

    // Dibujar destinos
    destinations.forEach((dest, idx) => {
      if (dest && dest.length >= 2) {
        const dx = clamp(dest[0], 0, width - 1)
        const dz = clamp(dest[1], 0, height - 1)
        const color = tractorColors[idx]
        const xPos = offsetX + dx * cellSize
        const zPos = offsetZ + dz * cellSize

        ctx.fillStyle = color
        ctx.globalAlpha = 0.8
        ctx.fillRect(xPos, zPos, cellSize, cellSize)
        ctx.globalAlpha = 1.0

        ctx.strokeStyle = color
        ctx.lineWidth = 3
        ctx.strokeRect(xPos, zPos, cellSize, cellSize)
      }
    })

    // Dibujar tractores CON INTERPOLACIÓN
    if (step < simulationSteps.length) {
      const currentStepData = simulationSteps[step]
      const prevStep = step > 0 ? step - 1 : 0
      const prevStepData = simulationSteps[prevStep]

      currentStepData.forEach((tractorState, tractorId) => {
        if (tractorState.position && tractorState.position.length >= 2) {
          const targetX = clamp(tractorState.position[0], 0, width - 1)
          const targetZ = clamp(tractorState.position[1], 0, height - 1)

          let startX = targetX
          let startZ = targetZ
          if (prevStepData && prevStepData[tractorId]?.position) {
            startX = clamp(prevStepData[tractorId].position[0], 0, width - 1)
            startZ = clamp(prevStepData[tractorId].position[1], 0, height - 1)
          }

          const displayX = lerp(startX, targetX, interpolation)
          const displayZ = lerp(startZ, targetZ, interpolation)

          const xPos = offsetX + displayX * cellSize + cellSize / 2
          const zPos = offsetZ + displayZ * cellSize + cellSize / 2
          const radius = cellSize * 0.35

          let fillColor = tractorState.color
          if (tractorState.arrived) {
            fillColor = adjustBrightness(tractorState.color, 0.1)
          } else if (tractorState.path_recalculated) {
            fillColor = '#ffaa00'
          } else if (tractorState.waiting) {
            fillColor = adjustBrightness(tractorState.color, -0.3)
          }

          ctx.fillStyle = fillColor
          ctx.beginPath()
          ctx.arc(xPos, zPos, radius, 0, Math.PI * 2)
          ctx.fill()

          ctx.strokeStyle = tractorState.path_recalculated ? '#ff6600' : '#000000'
          ctx.lineWidth = tractorState.path_recalculated ? 3 : 2
          ctx.stroke()
        }
      })
    }

    // Granero
    for (let z = 0; z < height; z++) {
      for (let x = 0; x < width; x++) {
        if (grid[z][x] === 3) {
          const barnX = offsetX + x * cellSize
          const barnZ = offsetZ + z * cellSize
          ctx.fillStyle = tileColors.BARN
          ctx.fillRect(barnX, barnZ, cellSize, cellSize)
          ctx.strokeStyle = '#000000'
          ctx.lineWidth = 3
          ctx.strokeRect(barnX, barnZ, cellSize, cellSize)
        }
      }
    }
  }, [grid, width, height, barnPos, tractorPaths, destinations, simulationSteps, tractorColors, infestationGrid, tileColors])

  // Loop de animación
  useEffect(() => {
    let isActive = true

    const animate = (currentTime: number) => {
      if (!isActive) return

      const elapsed = currentTime - lastStepTimeRef.current
      interpolationRef.current = Math.min(1, elapsed / speed)

      renderCanvas(interpolationRef.current)

      if (isPlaying && interpolationRef.current >= 1 && currentStepRef.current < maxSteps - 1) {
        setCurrentStep(prev => {
          if (prev < maxSteps - 1) {
            return prev + 1
          } else {
            setIsPlaying(false)
            return prev
          }
        })
      }

      animationFrameRef.current = requestAnimationFrame(animate)
    }

    animationFrameRef.current = requestAnimationFrame(animate)

    return () => {
      isActive = false
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [isPlaying, maxSteps, speed, renderCanvas])

  useEffect(() => {
    renderCanvas(1)
  }, [renderCanvas])

  const handlePlay = () => setIsPlaying(true)
  const handlePause = () => setIsPlaying(false)

  const handleReset = () => {
    setIsPlaying(false)
    setCurrentStep(0)
    pathsTakenRef.current = tractorPaths.map(() => new Set())
  }

  const handleStepForward = () => {
    if (currentStep < maxSteps - 1) setCurrentStep(currentStep + 1)
  }

  const handleStepBackward = () => {
    if (currentStep > 0) setCurrentStep(currentStep - 1)
  }

  return (
    <div className="dijkstra-animation">
      <div className="animation-controls-bar">
        <button onClick={handleReset} className="btn-control">⏮ Reset</button>
        <button onClick={handleStepBackward} className="btn-control" disabled={currentStep === 0}>
          ⏪ Atrás
        </button>
        {isPlaying ? (
          <button onClick={handlePause} className="btn-control">⏸ Pausar</button>
        ) : (
          <button onClick={handlePlay} className="btn-control">▶ Reproducir</button>
        )}
        <button onClick={handleStepForward} className="btn-control" disabled={currentStep >= maxSteps - 1}>
          ⏩ Adelante
        </button>
        <div className="animation-progress">
          <span>Paso {currentStep + 1} / {maxSteps}</span>
          <input
            type="range"
            min="0"
            max={maxSteps - 1}
            value={currentStep}
            onChange={(e) => setCurrentStep(parseInt(e.target.value))}
            className="progress-slider"
          />
        </div>
      </div>
      <canvas ref={canvasRef} width={800} height={800} className="animation-canvas" />
    </div>
  )
}

function adjustBrightness(color: string, factor: number): string {
  const hex = color.replace('#', '')
  const r = parseInt(hex.substr(0, 2), 16)
  const g = parseInt(hex.substr(2, 2), 16)
  const b = parseInt(hex.substr(4, 2), 16)

  const newR = Math.max(0, Math.min(255, r + factor * 255))
  const newG = Math.max(0, Math.min(255, g + factor * 255))
  const newB = Math.max(0, Math.min(255, b + factor * 255))

  return `#${Math.round(newR).toString(16).padStart(2, '0')}${Math.round(newG).toString(16).padStart(2, '0')}${Math.round(newB).toString(16).padStart(2, '0')}`
}
