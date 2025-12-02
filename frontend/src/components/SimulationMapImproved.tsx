import { useEffect, useRef, useState } from 'react'
import { World, Agent, BlackboardTask } from '../types'
import './SimulationMap.css'

interface ActiveAnimation {
  id: string
  type: 'move' | 'fumigate' | 'analyze' | 'refill' | 'scan'
  agentId: string
  startTime: number
  duration: number
  from?: [number, number]
  to?: [number, number]
  position?: [number, number]
  data?: any
}

interface SimulationMapProps {
  world: World
  agents: Agent[]
  tasks: BlackboardTask[]
  showInfestation?: boolean
  activeAnimations?: Map<string, ActiveAnimation>
  infestationGrid?: number[][]  // Grid de infestación actualizado en tiempo real
  revealedCells?: Set<string>   // Celdas reveladas (todas visibles desde el inicio sin scout)
}

// Colores para tipos de terreno
const TILE_COLORS = {
  IMPASSABLE: '#1a1a1a',  // Negro
  ROAD: '#8b7355',        // Marrón
  FIELD: '#7ec850',       // Verde
  BARN: '#c44536',        // Rojo
}

// Colores para agentes
const COMPLETED_COLOR = '#10b981' // Verde oscuro para celdas fumigadas

// Colores diferentes para cada fumigador
const FUMIGATOR_COLORS = [
  '#3b82f6', // Azul
  '#ef4444', // Rojo
  '#10b981', // Verde
  '#f59e0b', // Amarillo/Naranja
  '#8b5cf6', // Púrpura
  '#ec4899', // Rosa
  '#06b6d4', // Cyan
  '#84cc16', // Lima
]

// Función para obtener color del fumigador basado en su ID
const getFumigatorColor = (agentId: string, index: number): string => {
  // Usar el índice o hash del ID para obtener un color consistente
  const hash = agentId.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
  return FUMIGATOR_COLORS[(hash + index) % FUMIGATOR_COLORS.length]
}

export default function SimulationMap({
  world,
  agents,
  tasks,
  showInfestation = true,
  activeAnimations = new Map(),
  infestationGrid,
  revealedCells = new Set(),
}: SimulationMapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animationFrameRef = useRef<number>()
  const [completedCells, setCompletedCells] = useState<Set<string>>(new Set())

  // Actualizar celdas completadas cuando las tareas se completan
  useEffect(() => {
    const newCompleted = new Set<string>()
    tasks.forEach(task => {
      if (task.status === 'completed') {
        newCompleted.add(`${task.position_x},${task.position_z}`)
      }
    })
    setCompletedCells(newCompleted)
  }, [tasks])

  useEffect(() => {
    // Función de renderizado con animaciones
    const render = (currentTime: number) => {
      const canvas = canvasRef.current
      if (!canvas || !world) return

      const ctx = canvas.getContext('2d')
      if (!ctx) return

      const cellSize = Math.min(
        Math.floor(canvas.width / world.width),
        Math.floor(canvas.height / world.height)
      )

      const offsetX = (canvas.width - world.width * cellSize) / 2
      const offsetZ = (canvas.height - world.height * cellSize) / 2

      // Limpiar canvas
      ctx.fillStyle = '#f0f0f0'
      ctx.fillRect(0, 0, canvas.width, canvas.height)

      // Dibujar grid base - todas las celdas están reveladas desde el inicio
      for (let z = 0; z < world.height; z++) {
        for (let x = 0; x < world.width; x++) {
          const tileType = world.grid[z][x]
          const isCompleted = completedCells.has(`${x},${z}`)

          let color = TILE_COLORS.IMPASSABLE

          if (tileType === 1) color = TILE_COLORS.ROAD
          else if (tileType === 2) color = TILE_COLORS.FIELD
          else if (tileType === 3) color = TILE_COLORS.BARN

          const xPos = offsetX + x * cellSize
          const zPos = offsetZ + z * cellSize

          // Dibujar tile base
          ctx.fillStyle = color
          ctx.fillRect(xPos, zPos, cellSize, cellSize)

          // Si está completada (fumigada), mostrar en verde con check
          if (isCompleted) {
            ctx.fillStyle = COMPLETED_COLOR
            ctx.globalAlpha = 0.8
            ctx.fillRect(xPos, zPos, cellSize, cellSize)
            ctx.globalAlpha = 1.0

            // Checkmark
            ctx.strokeStyle = '#ffffff'
            ctx.lineWidth = 3
            ctx.lineCap = 'round'
            ctx.lineJoin = 'round'
            ctx.beginPath()
            ctx.moveTo(xPos + cellSize * 0.25, zPos + cellSize * 0.5)
            ctx.lineTo(xPos + cellSize * 0.4, zPos + cellSize * 0.65)
            ctx.lineTo(xPos + cellSize * 0.75, zPos + cellSize * 0.35)
            ctx.stroke()
          }
          // Mostrar infestación (todas las celdas están reveladas desde el inicio)
          else if (showInfestation) {
            const gridToUse = infestationGrid || world.infestation_grid
            if (gridToUse && gridToUse[z] && gridToUse[z][x] > 0) {
              const infestationLevel = gridToUse[z][x]
              const intensity = infestationLevel / 100

              // Gradiente de amarillo a rojo
              const r = 255
              const g = Math.floor(255 * (1 - intensity))
              const b = 0

              ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.7)`
              ctx.fillRect(xPos, zPos, cellSize, cellSize)

              // Mostrar número de infestación
              ctx.fillStyle = '#000'
              ctx.font = `bold ${cellSize * 0.4}px Arial`
              ctx.textAlign = 'center'
              ctx.textBaseline = 'middle'
              ctx.fillText(`${infestationLevel}`, xPos + cellSize / 2, zPos + cellSize / 2)
            }
          }

          // Borde de celda
          ctx.strokeStyle = 'rgba(0, 0, 0, 0.15)'
          ctx.lineWidth = 1
          ctx.strokeRect(xPos, zPos, cellSize, cellSize)
        }
      }

      // Dibujar indicadores de tareas asignadas/en progreso
      tasks.forEach((task) => {
        if (task.status === 'completed' || task.status === 'failed') return

        const xPos = offsetX + task.position_x * cellSize
        const zPos = offsetZ + task.position_z * cellSize

        // Borde según estado
        if (task.status === 'assigned' || task.status === 'in_progress') {
          ctx.strokeStyle = FUMIGATOR_COLORS[0] // Usar primer color para tareas
          ctx.lineWidth = 3
          ctx.strokeRect(xPos, zPos, cellSize, cellSize)

          // Flecha indicando que hay un agente en camino
          if (task.status === 'assigned') {
            ctx.fillStyle = FUMIGATOR_COLORS[0] // Usar primer color para tareas
            ctx.font = `${cellSize * 0.5}px Arial`
            ctx.textAlign = 'center'
            ctx.textBaseline = 'middle'
            ctx.fillText('→', xPos + cellSize / 2, zPos + cellSize / 2)
          }
        }
      })

      // Dibujar efectos de animación
      activeAnimations.forEach((animation) => {
        const elapsed = currentTime - animation.startTime
        const progress = Math.min(elapsed / animation.duration, 1)

        // Animación de escaneo eliminada (scouts eliminados)

        if (animation.type === 'fumigate' && animation.position) {
          // Efecto de fumigación: círculos concéntricos verdes
          const [x, z] = animation.position
          const xPos = offsetX + x * cellSize + cellSize / 2
          const zPos = offsetZ + z * cellSize + cellSize / 2

          for (let i = 0; i < 3; i++) {
            const radius = Math.max(0, cellSize * (0.3 + 0.3 * i + progress * 0.5)) // Asegurar radio positivo
            const alpha = Math.max(0, Math.min(1, 0.4 * (1 - progress) * (1 - i * 0.3))) // Asegurar alpha entre 0 y 1

            if (radius > 0 && alpha > 0) {
              ctx.strokeStyle = `rgba(16, 185, 129, ${alpha})`
              ctx.lineWidth = 2
              ctx.beginPath()
              ctx.arc(xPos, zPos, radius, 0, Math.PI * 2)
              ctx.stroke()
            }
          }
        }
      })

      // Dibujar agentes (encima de todo)
      agents.forEach((agent, index) => {
        let x = agent.position_x ?? 0
        let z = agent.position_z ?? 0

        // Si hay animación de movimiento, interpolar posición
        const moveAnimation = Array.from(activeAnimations.values()).find(
          a => a.type === 'move' && (a.agentId === agent.id || a.agentId === agent.agent_id)
        )

        if (moveAnimation && moveAnimation.from && moveAnimation.to) {
          const elapsed = currentTime - moveAnimation.startTime
          const progress = Math.min(elapsed / moveAnimation.duration, 1)

          x = moveAnimation.from[0] + (moveAnimation.to[0] - moveAnimation.from[0]) * progress
          z = moveAnimation.from[1] + (moveAnimation.to[1] - moveAnimation.from[1]) * progress
        }

        const xPos = offsetX + x * cellSize + cellSize / 2
        const zPos = offsetZ + z * cellSize + cellSize / 2

        // Asegurar que cellSize es válido antes de dibujar
        if (cellSize <= 0) return

        const agentColor = getFumigatorColor(agent.agent_id, index)

        const agentRadius = Math.max(1, cellSize * 0.35) // Asegurar radio mínimo de 1

        // Sombra del agente
        ctx.fillStyle = 'rgba(0, 0, 0, 0.3)'
        ctx.beginPath()
        ctx.arc(xPos + 2, zPos + 2, agentRadius, 0, Math.PI * 2)
        ctx.fill()

        // Cuerpo del agente
        ctx.fillStyle = agentColor
        ctx.beginPath()
        ctx.arc(xPos, zPos, agentRadius, 0, Math.PI * 2)
        ctx.fill()

        // Borde del agente
        ctx.strokeStyle = '#ffffff'
        ctx.lineWidth = 2
        ctx.stroke()

        // Icono - solo tractores
        ctx.fillStyle = '#ffffff'
        ctx.font = `bold ${cellSize * 0.3}px Arial`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText('🚜', xPos, zPos)

        // Estado del agente (si está activo)
        if (agent.status !== 'idle') {
          ctx.fillStyle = agentColor
          ctx.font = `${cellSize * 0.25}px Arial`
          ctx.textAlign = 'center'
          ctx.fillText(agent.status, xPos, zPos + cellSize * 0.6)
        }
      })

      // Continuar animación
      animationFrameRef.current = requestAnimationFrame(render)
    }

    animationFrameRef.current = requestAnimationFrame(render)

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [world, agents, tasks, activeAnimations, infestationGrid, revealedCells, completedCells, showInfestation])

  return (
    <div className="simulation-map-container">
      <canvas
        ref={canvasRef}
        width={800}
        height={600}
        className="simulation-map-canvas"
      />
      <div className="simulation-map-legend">
        <h4>Leyenda</h4>
        <div className="legend-item">
          <div className="legend-color" style={{ backgroundColor: FUMIGATOR_COLORS[0] }}></div>
          <span>🚜 Fumigador (Tractor)</span>
        </div>
        <div className="legend-item">
          <div className="legend-color" style={{ backgroundColor: COMPLETED_COLOR }}></div>
          <span>✓ Campo Fumigado</span>
        </div>
        <div className="legend-item">
          <div className="legend-color infestation"></div>
          <span>🦠 Infestación (amarillo→rojo)</span>
        </div>
      </div>
    </div>
  )
}
