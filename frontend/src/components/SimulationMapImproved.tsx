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
  revealedCells?: Set<string>   // Celdas reveladas por el scout
}

// Colores para tipos de terreno
const TILE_COLORS = {
  IMPASSABLE: '#1a1a1a',  // Negro
  ROAD: '#8b7355',        // Marrón
  FIELD: '#7ec850',       // Verde
  BARN: '#c44536',        // Rojo
}

// Colores para agentes
const FUMIGATOR_COLOR = '#3b82f6' // Azul
const SCOUT_COLOR = '#00ffff'     // Cyan
const COMPLETED_COLOR = '#10b981' // Verde oscuro para celdas fumigadas

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

      // Dibujar grid base y revelación progresiva
      for (let z = 0; z < world.height; z++) {
        for (let x = 0; x < world.width; x++) {
          const tileType = world.grid[z][x]
          const cellKey = `${x},${z}`
          const isRevealed = revealedCells.has(cellKey)
          const isCompleted = completedCells.has(cellKey)

          let color = TILE_COLORS.IMPASSABLE

          if (tileType === 1) color = TILE_COLORS.ROAD
          else if (tileType === 2) color = TILE_COLORS.FIELD
          else if (tileType === 3) color = TILE_COLORS.BARN

          const xPos = offsetX + x * cellSize
          const zPos = offsetZ + z * cellSize

          // Dibujar tile base
          ctx.fillStyle = color
          ctx.fillRect(xPos, zPos, cellSize, cellSize)

          // Si la celda NO está revelada, dibujar niebla de guerra
          if (tileType === 2 && !isRevealed) { // Solo en campos
            ctx.fillStyle = 'rgba(40, 40, 40, 0.7)'
            ctx.fillRect(xPos, zPos, cellSize, cellSize)

            // Símbolo de pregunta para celdas no reveladas
            ctx.fillStyle = 'rgba(255, 255, 255, 0.3)'
            ctx.font = `${cellSize * 0.6}px bold`
            ctx.textAlign = 'center'
            ctx.textBaseline = 'middle'
            ctx.fillText('?', xPos + cellSize / 2, zPos + cellSize / 2)
          }

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
          // Si está revelada y tiene infestación, mostrar nivel
          else if (isRevealed && showInfestation) {
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
          ctx.strokeStyle = FUMIGATOR_COLOR
          ctx.lineWidth = 3
          ctx.strokeRect(xPos, zPos, cellSize, cellSize)

          // Flecha indicando que hay un agente en camino
          if (task.status === 'assigned') {
            ctx.fillStyle = FUMIGATOR_COLOR
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

        if (animation.type === 'scan' && animation.position) {
          // Efecto de escaneo del scout: onda que se expande
          const [x, z] = animation.position
          const xPos = offsetX + x * cellSize + cellSize / 2
          const zPos = offsetZ + z * cellSize + cellSize / 2

          const radius = cellSize * 2 * progress
          const alpha = 0.5 * (1 - progress)

          ctx.strokeStyle = `rgba(0, 255, 255, ${alpha})`
          ctx.lineWidth = 3
          ctx.beginPath()
          ctx.arc(xPos, zPos, radius, 0, Math.PI * 2)
          ctx.stroke()
        }

        if (animation.type === 'fumigate' && animation.position) {
          // Efecto de fumigación: círculos concéntricos verdes
          const [x, z] = animation.position
          const xPos = offsetX + x * cellSize + cellSize / 2
          const zPos = offsetZ + z * cellSize + cellSize / 2

          for (let i = 0; i < 3; i++) {
            const radius = cellSize * (0.3 + 0.3 * i + progress * 0.5)
            const alpha = 0.4 * (1 - progress) * (1 - i * 0.3)

            ctx.strokeStyle = `rgba(16, 185, 129, ${alpha})`
            ctx.lineWidth = 2
            ctx.beginPath()
            ctx.arc(xPos, zPos, radius, 0, Math.PI * 2)
            ctx.stroke()
          }
        }
      })

      // Dibujar agentes (encima de todo)
      agents.forEach((agent) => {
        let x = agent.position_x
        let z = agent.position_z

        // Si hay animación de movimiento, interpolar posición
        const moveAnimation = Array.from(activeAnimations.values()).find(
          a => a.type === 'move' && a.agentId === agent.id
        )

        if (moveAnimation && moveAnimation.from && moveAnimation.to) {
          const elapsed = currentTime - moveAnimation.startTime
          const progress = Math.min(elapsed / moveAnimation.duration, 1)

          x = moveAnimation.from[0] + (moveAnimation.to[0] - moveAnimation.from[0]) * progress
          z = moveAnimation.from[1] + (moveAnimation.to[1] - moveAnimation.from[1]) * progress
        }

        const xPos = offsetX + x * cellSize + cellSize / 2
        const zPos = offsetZ + z * cellSize + cellSize / 2

        const agentColor = agent.agent_type === 'fumigator' ? FUMIGATOR_COLOR : SCOUT_COLOR

        // Sombra del agente
        ctx.fillStyle = 'rgba(0, 0, 0, 0.3)'
        ctx.beginPath()
        ctx.arc(xPos + 2, zPos + 2, cellSize * 0.35, 0, Math.PI * 2)
        ctx.fill()

        // Cuerpo del agente
        ctx.fillStyle = agentColor
        ctx.beginPath()
        ctx.arc(xPos, zPos, cellSize * 0.35, 0, Math.PI * 2)
        ctx.fill()

        // Borde del agente
        ctx.strokeStyle = '#ffffff'
        ctx.lineWidth = 2
        ctx.stroke()

        // Icono según tipo
        ctx.fillStyle = '#ffffff'
        ctx.font = `bold ${cellSize * 0.3}px Arial`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        const icon = agent.agent_type === 'fumigator' ? '🚜' : '🔍'
        ctx.fillText(icon, xPos, zPos)

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
          <div className="legend-color" style={{ backgroundColor: SCOUT_COLOR }}></div>
          <span>🔍 Scout (Dron Explorador)</span>
        </div>
        <div className="legend-item">
          <div className="legend-color" style={{ backgroundColor: FUMIGATOR_COLOR }}></div>
          <span>🚜 Fumigador (Tractor)</span>
        </div>
        <div className="legend-item">
          <div className="legend-color" style={{ backgroundColor: COMPLETED_COLOR }}></div>
          <span>✓ Campo Fumigado</span>
        </div>
        <div className="legend-item">
          <div className="legend-color fog"></div>
          <span>? Campo No Revelado</span>
        </div>
        <div className="legend-item">
          <div className="legend-color infestation"></div>
          <span>🦠 Infestación (amarillo→rojo)</span>
        </div>
      </div>
    </div>
  )
}
