import { useEffect, useRef, useState } from 'react'
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
  dronePath?: number[][]
  droneDestination?: number[]
  droneSimulationSteps?: Array<{
    position: number[]
    path_index: number
    arrived: boolean
    color: string
    revealed_infestation?: Record<string, number> // { "x,z": nivel }
  }>
  droneColor?: string
  infestationGrid?: number[][]
  tileColors: {
    IMPASSABLE: string
    ROAD: string
    FIELD: string
    BARN: string
  }
  speed?: number
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
  dronePath,
  droneDestination,
  droneSimulationSteps,
  droneColor = '#00ffff',
  infestationGrid,
  tileColors,
  speed = 300,
}: DijkstraAnimationProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [currentStep, setCurrentStep] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const animationRef = useRef<number>()
  const pathsTakenRef = useRef<Array<Set<string>>>([])

  useEffect(() => {
    pathsTakenRef.current = tractorPaths.map(() => new Set())
  }, [tractorPaths])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Calcular tamaño de celda
    const cellSize = Math.min(
      Math.floor(canvas.width / width),
      Math.floor(canvas.height / height)
    )

    const offsetX = (canvas.width - width * cellSize) / 2
    const offsetZ = (canvas.height - height * cellSize) / 2

    // Limpiar canvas
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)

    // Calcular el máximo de pasos para mapear el paso del dron
    const maxStepsForDrone = droneSimulationSteps && droneSimulationSteps.length > 0
      ? droneSimulationSteps.length
      : simulationSteps.length

    // Obtener infestación revelada por el dron hasta el paso actual
    let revealedInfestation: Record<string, number> = {}
    if (droneSimulationSteps && droneSimulationSteps.length > 0) {
      // Mapear currentStep al paso del dron
      // Si maxStepsForDrone es igual a la longitud de droneSimulationSteps, usar currentStep directamente
      let droneStep: number
      if (maxStepsForDrone === droneSimulationSteps.length) {
        // Mapeo directo: currentStep corresponde directamente al paso del dron
        // Asegurar que cuando currentStep = 0, droneStep = 0 (granero)
        droneStep = Math.min(Math.max(0, currentStep), droneSimulationSteps.length - 1)
      } else {
        // Mapeo proporcional
        droneStep = Math.min(
          Math.max(0, Math.floor((currentStep / maxStepsForDrone) * droneSimulationSteps.length)),
          droneSimulationSteps.length - 1
        )
      }
      const droneState = droneSimulationSteps[droneStep]
      if (droneState?.revealed_infestation) {
        revealedInfestation = droneState.revealed_infestation
      }
    }

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

        // Si el dron ha revelado la infestación de esta celda, dibujarla
        const cellKey = `${x},${z}`
        if (revealedInfestation[cellKey] !== undefined && infestationGrid) {
          const infestationLevel = revealedInfestation[cellKey]
          if (infestationLevel > 0) {
            // Escala de colores: verde (bajo) -> amarillo -> rojo (alto)
            const intensity = infestationLevel / 100
            const r = Math.floor(255 * intensity)
            const g = Math.floor(255 * (1 - intensity * 0.5))
            const b = 0
            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.6)`
            ctx.fillRect(xPos, zPos, cellSize, cellSize)
          }
        }

        // Borde sutil
        ctx.strokeStyle = 'rgba(0, 0, 0, 0.1)'
        ctx.strokeRect(xPos, zPos, cellSize, cellSize)
      }
    }

      // Dibujar caminos recorridos hasta el paso actual
    if (currentStep < simulationSteps.length) {
      const step = simulationSteps[currentStep]

      // Actualizar caminos recorridos
      step.forEach((tractorState, tractorId) => {
        const pathIndex = tractorState.path_index
        const path = tractorPaths[tractorId]
        if (path) {
          for (let i = 0; i <= Math.min(pathIndex, path.length - 1); i++) {
            const pos = path[i]
            if (pos && pos.length >= 2) {
              const [px, pz] = pos
              pathsTakenRef.current[tractorId].add(`${px},${pz}`)
            }
          }
        }
      })

      // Dibujar caminos recorridos (más tenues)
      pathsTakenRef.current.forEach((pathSet, tractorId) => {
        const color = tractorColors[tractorId]
        ctx.fillStyle = color
        ctx.globalAlpha = 0.3

        pathSet.forEach((posStr) => {
          const [px, pz] = posStr.split(',').map(Number)
          const [bx, bz] = barnPos
          const isDest = destinations.some((dest) => dest[0] === px && dest[1] === pz)

          // No pintar si es barn, destino, o posición actual del tractor
          if (!(px === bx && pz === bz) && !isDest) {
            const currentTractorPos = step[tractorId]?.position
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
        const [dx, dz] = dest
        const color = tractorColors[idx]
        const xPos = offsetX + dx * cellSize
        const zPos = offsetZ + dz * cellSize

        // Destino con borde más brillante
        ctx.fillStyle = color
        ctx.globalAlpha = 0.8
        ctx.fillRect(xPos, zPos, cellSize, cellSize)
        ctx.globalAlpha = 1.0

        ctx.strokeStyle = color
        ctx.lineWidth = 3
        ctx.strokeRect(xPos, zPos, cellSize, cellSize)
      }
    })

    // Dibujar tractores en el paso actual
    if (currentStep < simulationSteps.length) {
      const step = simulationSteps[currentStep]
      step.forEach((tractorState) => {
        if (tractorState.position && tractorState.position.length >= 2) {
          const [tx, tz] = tractorState.position
          const xPos = offsetX + tx * cellSize + cellSize / 2
          const zPos = offsetZ + tz * cellSize + cellSize / 2
          const radius = cellSize * 0.35

          // Determinar color según estado
          let fillColor = tractorState.color
          if (tractorState.arrived) {
            // Tractor que llegó - color normal pero más opaco
            fillColor = adjustBrightness(tractorState.color, 0.1)
          } else if (tractorState.path_recalculated) {
            // Tractor que recalculó camino - color amarillo/naranja para indicar
            fillColor = '#ffaa00'
          } else if (tractorState.waiting) {
            // Tractor esperando - color más oscuro
            fillColor = adjustBrightness(tractorState.color, -0.3)
          }

          ctx.fillStyle = fillColor
          ctx.beginPath()
          ctx.arc(xPos, zPos, radius, 0, Math.PI * 2)
          ctx.fill()

          // Si recalculó, agregar borde especial
          if (tractorState.path_recalculated) {
            ctx.strokeStyle = '#ff6600'
            ctx.lineWidth = 3
          } else {
            ctx.strokeStyle = '#000000'
            ctx.lineWidth = 2
          }
          ctx.stroke()
        }
      })
    }

    // Dibujar dron en el paso actual (si existe)
    if (droneSimulationSteps && droneSimulationSteps.length > 0) {
      // Mapear currentStep al paso del dron
      // Si maxStepsForDrone es igual a la longitud de droneSimulationSteps, usar currentStep directamente
      // De lo contrario, mapear proporcionalmente
      let droneStep: number
      if (maxStepsForDrone === droneSimulationSteps.length) {
        // Mapeo directo: currentStep corresponde directamente al paso del dron
        // Asegurar que cuando currentStep = 0, droneStep = 0 (granero)
        droneStep = Math.min(Math.max(0, currentStep), droneSimulationSteps.length - 1)
      } else {
        // Mapeo proporcional
        droneStep = Math.min(
          Math.max(0, Math.floor((currentStep / maxStepsForDrone) * droneSimulationSteps.length)),
          droneSimulationSteps.length - 1
        )
      }
      const droneState = droneSimulationSteps[droneStep]
      
      if (droneState && droneState.position && droneState.position.length >= 2) {
        const [dx, dz] = droneState.position
        const xPos = offsetX + dx * cellSize + cellSize / 2
        const zPos = offsetZ + dz * cellSize + cellSize / 2
        
        // Dibujar dron como un hexágono (forma de dron)
        const size = cellSize * 0.3
        ctx.fillStyle = droneColor
        ctx.beginPath()
        // Hexágono apuntando hacia arriba
        for (let i = 0; i < 6; i++) {
          const angle = (Math.PI / 3) * i - Math.PI / 2
          const px = xPos + size * Math.cos(angle)
          const pz = zPos + size * Math.sin(angle)
          if (i === 0) {
            ctx.moveTo(px, pz)
          } else {
            ctx.lineTo(px, pz)
          }
        }
        ctx.closePath()
        ctx.fill()
        
        // Borde del dron
        ctx.strokeStyle = '#000000'
        ctx.lineWidth = 2
        ctx.stroke()
        
        // Indicador de que está volando (líneas pequeñas alrededor)
        if (!droneState.arrived) {
          ctx.strokeStyle = droneColor
          ctx.lineWidth = 1
          ctx.globalAlpha = 0.5
          for (let i = 0; i < 8; i++) {
            const angle = (Math.PI / 4) * i
            const startDist = size + 2
            const endDist = size + 6
            ctx.beginPath()
            ctx.moveTo(
              xPos + startDist * Math.cos(angle),
              zPos + startDist * Math.sin(angle)
            )
            ctx.lineTo(
              xPos + endDist * Math.cos(angle),
              zPos + endDist * Math.sin(angle)
            )
            ctx.stroke()
          }
          ctx.globalAlpha = 1.0
        }
      }
      
      // Dibujar destino del dron
      if (droneDestination && droneDestination.length >= 2) {
        const [ddx, ddz] = droneDestination
        const destX = offsetX + ddx * cellSize
        const destZ = offsetZ + ddz * cellSize
        
        // Destino del dron con estilo diferente
        ctx.fillStyle = droneColor
        ctx.globalAlpha = 0.6
        ctx.fillRect(destX, destZ, cellSize, cellSize)
        ctx.globalAlpha = 1.0
        
        ctx.strokeStyle = droneColor
        ctx.lineWidth = 3
        ctx.setLineDash([5, 5])
        ctx.strokeRect(destX, destZ, cellSize, cellSize)
        ctx.setLineDash([])
      }
    }

    // Dibujar todas las celdas del granero (5 celdas)
    // Encontrar todas las celdas del granero en el grid
    const barnCells: Array<[number, number]> = []
    for (let z = 0; z < height; z++) {
      for (let x = 0; x < width; x++) {
        if (grid[z][x] === 3) { // TileType.BARN
          barnCells.push([x, z])
        }
      }
    }
    
    // Dibujar cada celda del granero
    barnCells.forEach(([bx, bz]) => {
      const barnX = offsetX + bx * cellSize
      const barnZ = offsetZ + bz * cellSize
      ctx.fillStyle = tileColors.BARN
      ctx.fillRect(barnX, barnZ, cellSize, cellSize)
      ctx.strokeStyle = '#000000'
      ctx.lineWidth = 3
      ctx.strokeRect(barnX, barnZ, cellSize, cellSize)
    })
  }, [grid, width, height, barnPos, tractorPaths, destinations, simulationSteps, tractorColors, dronePath, droneDestination, droneSimulationSteps, droneColor, infestationGrid, tileColors, currentStep])

  // Calcular el máximo de pasos: usar el dron si existe, sino los tractores
  // El dron tiene más pasos porque sobrevuela todo el mapa, así que usamos su longitud completa
  const maxSteps = droneSimulationSteps && droneSimulationSteps.length > 0
    ? droneSimulationSteps.length
    : simulationSteps.length

  useEffect(() => {
    if (isPlaying && currentStep < maxSteps - 1) {
      animationRef.current = window.setTimeout(() => {
        setCurrentStep((prev) => {
          if (prev < maxSteps - 1) {
            return prev + 1
          } else {
            setIsPlaying(false)
            return prev
          }
        })
      }, speed)
    }

    return () => {
      if (animationRef.current) {
        clearTimeout(animationRef.current)
      }
    }
  }, [isPlaying, currentStep, maxSteps, speed])

  const handlePlay = () => {
    setIsPlaying(true)
  }

  const handlePause = () => {
    setIsPlaying(false)
  }

  const handleReset = () => {
    setIsPlaying(false)
    setCurrentStep(0)
    pathsTakenRef.current = tractorPaths.map(() => new Set())
  }

  const handleStepForward = () => {
    if (currentStep < maxSteps - 1) {
      setCurrentStep(currentStep + 1)
    }
  }

  const handleStepBackward = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1)
    }
  }

  return (
    <div className="dijkstra-animation">
      <div className="animation-controls-bar">
        <button onClick={handleReset} className="btn-control">⏮ Reset</button>
        <button onClick={handleStepBackward} className="btn-control" disabled={currentStep === 0}>
          ⏪ Atrás
        </button>
        {isPlaying ? (
          <button onClick={handlePause} className="btn-control">
            ⏸ Pausar
          </button>
        ) : (
          <button onClick={handlePlay} className="btn-control">
            ▶ Reproducir
          </button>
        )}
        <button
          onClick={handleStepForward}
          className="btn-control"
          disabled={currentStep >= maxSteps - 1}
        >
          ⏩ Adelante
        </button>
        <div className="animation-progress">
          <span>
            Paso {currentStep + 1} / {maxSteps}
          </span>
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

  return `#${Math.round(newR).toString(16).padStart(2, '0')}${Math.round(newG)
    .toString(16)
    .padStart(2, '0')}${Math.round(newB).toString(16).padStart(2, '0')}`
}

