import { useEffect, useRef } from 'react'
import { World, Agent, BlackboardTask } from '../types'
import './SimulationMap.css'

interface ActiveAnimation {
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

interface SimulationMapProps {
  world: World
  agents: Agent[]
  tasks: BlackboardTask[]
  showInfestation?: boolean
  activeAnimations?: Map<string, ActiveAnimation>
}

// Colores simplificados y claros
const TILE_COLORS = {
  IMPASSABLE: '#1a1a1a',  // Negro - terreno impasable
  ROAD: '#8b7355',        // Marrón - caminos
  FIELD: '#7ec850',       // Verde - campos
  BARN: '#c44536',        // Rojo - granero
}

// Colores únicos para agentes
const FUMIGATOR_COLOR = '#3b82f6' // Azul - fumigador
const SCOUT_COLOR = '#00ffff'     // Cyan - scout

// Función helper para ajustar brillo
function adjustBrightness(color: string, factor: number): string {
  const hex = color.replace('#', '')
  const r = parseInt(hex.substr(0, 2), 16)
  const g = parseInt(hex.substr(2, 2), 16)
  const b = parseInt(hex.substr(4, 2), 16)
  
  const newR = Math.max(0, Math.min(255, Math.floor(r * (1 + factor))))
  const newG = Math.max(0, Math.min(255, Math.floor(g * (1 + factor))))
  const newB = Math.max(0, Math.min(255, Math.floor(b * (1 + factor))))
  
  return `#${newR.toString(16).padStart(2, '0')}${newG.toString(16).padStart(2, '0')}${newB.toString(16).padStart(2, '0')}`
}

export default function SimulationMap({
  world,
  agents,
  tasks,
  showInfestation = true,
  activeAnimations = new Map(),
}: SimulationMapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const pathsTakenRef = useRef<Map<string, Set<string>>>(new Map())
  const animationFrameRef = useRef<number>()
  const lastFrameTimeRef = useRef<number>(0)

  useEffect(() => {
    // Cancelar animación anterior si existe
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current)
    }

    // Función de renderizado con animaciones
    const render = (currentTime: number) => {
      const canvas = canvasRef.current
      if (!canvas || !world) return

      const ctx = canvas.getContext('2d')
      if (!ctx) return

      lastFrameTimeRef.current = currentTime

      const cellSize = Math.min(
        Math.floor(canvas.width / world.width),
        Math.floor(canvas.height / world.height)
      )

      const offsetX = (canvas.width - world.width * cellSize) / 2
      const offsetZ = (canvas.height - world.height * cellSize) / 2

      // Limpiar canvas
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, canvas.width, canvas.height)

      // Dibujar grid base
      for (let z = 0; z < world.height; z++) {
        for (let x = 0; x < world.width; x++) {
          const tileType = world.grid[z][x]
          let color = TILE_COLORS.IMPASSABLE

          if (tileType === 1) color = TILE_COLORS.ROAD
          else if (tileType === 2) color = TILE_COLORS.FIELD
          else if (tileType === 3) color = TILE_COLORS.BARN

          const xPos = offsetX + x * cellSize
          const zPos = offsetZ + z * cellSize

          ctx.fillStyle = color
          ctx.fillRect(xPos, zPos, cellSize, cellSize)

          // Mostrar infestación SOLO si está descubierta (existe una tarea para esta celda)
          if (showInfestation && world.infestation_grid && world.infestation_grid[z][x] > 0) {
            const isDiscovered = tasks.some(
              task => task.position_x === x && task.position_z === z
            )
            
            if (isDiscovered) {
              const infestationLevel = world.infestation_grid[z][x]
              const intensity = infestationLevel / 100
              const r = Math.floor(255 * intensity)
              const g = Math.floor(255 * (1 - intensity * 0.5))
              const b = 0
              ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.7)`
              ctx.fillRect(xPos, zPos, cellSize, cellSize)
            }
          }

          // Borde sutil
          ctx.strokeStyle = 'rgba(0, 0, 0, 0.1)'
          ctx.strokeRect(xPos, zPos, cellSize, cellSize)
        }
      }

      // Dibujar caminos recorridos por los agentes (trail)
      pathsTakenRef.current.forEach((pathSet, agentId) => {
        const agent = agents.find(a => a.id === agentId)
        if (!agent) return

        const agentColor = agent.agent_type === 'fumigator'
          ? FUMIGATOR_COLOR
          : SCOUT_COLOR

        ctx.fillStyle = agentColor
        ctx.globalAlpha = 0.2

        pathSet.forEach((posStr) => {
          const [px, pz] = posStr.split(',').map(Number)
          // No pintar si es barn
          if (world.grid[pz] && world.grid[pz][px] === 3) return // BARN
          
          const currentAgent = agents.find(a => a.id === agentId)
          if (currentAgent && currentAgent.position_x === px && currentAgent.position_z === pz) return

          const xPos = offsetX + px * cellSize
          const zPos = offsetZ + pz * cellSize
          ctx.fillRect(xPos, zPos, cellSize, cellSize)
        })

        ctx.globalAlpha = 1.0
      })

      // Dibujar tareas (simplificado)
      tasks.forEach((task) => {
        if (task.status === 'completed' || task.status === 'failed') return

        const xPos = offsetX + task.position_x * cellSize
        const zPos = offsetZ + task.position_z * cellSize
        
        // Color según estado
        let taskColor = '#ef4444' // Rojo - Pendiente
        if (task.status === 'assigned' || task.status === 'in_progress') {
          const assignedAgent = agents.find(a => a.id === task.assigned_agent_id)
          if (assignedAgent) {
            taskColor = assignedAgent.agent_type === 'fumigator'
              ? FUMIGATOR_COLOR
              : SCOUT_COLOR
          } else {
            taskColor = '#f59e0b' // Amarillo - Asignada
          }
        }

        // Dibujar tarea
        ctx.fillStyle = taskColor
        ctx.globalAlpha = 0.5
        ctx.fillRect(xPos, zPos, cellSize, cellSize)
        ctx.globalAlpha = 1.0

        ctx.strokeStyle = taskColor
        ctx.lineWidth = 2
        ctx.strokeRect(xPos, zPos, cellSize, cellSize)
      })

      // Dibujar efectos de animación (detrás de agentes)
      activeAnimations.forEach((animation) => {
        const elapsed = currentTime - animation.startTime
        const progress = Math.min(elapsed / animation.duration, 1)
        
        if (animation.type === 'fumigate' && animation.position) {
          // Efecto de fumigación: círculo verde que se expande
          const [x, z] = animation.position
          const xPos = offsetX + x * cellSize + cellSize / 2
          const zPos = offsetZ + z * cellSize + cellSize / 2
          
          const alpha = 1 - progress
          const radius = cellSize * 0.3 * (1 + progress)
          
          ctx.fillStyle = `rgba(34, 197, 94, ${alpha * 0.5})`
          ctx.beginPath()
          ctx.arc(xPos, zPos, radius, 0, Math.PI * 2)
          ctx.fill()
        } else if (animation.type === 'analyze' && animation.position) {
          // Efecto de análisis: ondas concéntricas cyan
          const [x, z] = animation.position
          const xPos = offsetX + x * cellSize + cellSize / 2
          const zPos = offsetZ + z * cellSize + cellSize / 2
          
          const alpha = 1 - progress
          const radius = cellSize * progress * 2
          
          ctx.strokeStyle = `rgba(0, 255, 255, ${alpha})`
          ctx.lineWidth = 2
          ctx.beginPath()
          ctx.arc(xPos, zPos, radius, 0, Math.PI * 2)
          ctx.stroke()
        } else if (animation.type === 'refill' && animation.position) {
          // Efecto de reabastecimiento: barra verde que sube
          const [x, z] = animation.position
          const xPos = offsetX + x * cellSize + cellSize / 2
          const zPos = offsetZ + z * cellSize + cellSize / 2
          
          const height = cellSize * 0.5 * progress
          
          ctx.fillStyle = 'rgba(34, 197, 94, 0.8)'
          ctx.fillRect(xPos - cellSize * 0.15, zPos - height, cellSize * 0.3, height)
        }
      })

      // Dibujar agentes con animación de movimiento
      agents.forEach((agent) => {
        if (agent.position_x === null || agent.position_x === undefined || 
            agent.position_z === null || agent.position_z === undefined) return

        // Verificar si hay una animación de movimiento para este agente
        let displayX = agent.position_x
        let displayZ = agent.position_z
        
        activeAnimations.forEach((animation) => {
          if (animation.agentId === agent.id && animation.type === 'move' && animation.from && animation.to) {
            const elapsed = currentTime - animation.startTime
            const progress = Math.min(elapsed / animation.duration, 1)
            // Interpolación suave (ease-out)
            const easedProgress = 1 - Math.pow(1 - progress, 3)
            
            displayX = animation.from[0] + (animation.to[0] - animation.from[0]) * easedProgress
            displayZ = animation.from[1] + (animation.to[1] - animation.from[1]) * easedProgress
          }
        })

        const xPos = offsetX + displayX * cellSize + cellSize / 2
        const zPos = offsetZ + displayZ * cellSize + cellSize / 2
        const radius = cellSize * 0.35

        // Color según tipo de agente
        let fillColor = agent.agent_type === 'fumigator'
          ? FUMIGATOR_COLOR
          : SCOUT_COLOR

        // Ajustar color según estado
        if (agent.status === 'idle') {
          fillColor = adjustBrightness(fillColor, -0.2)
        } else if (agent.status === 'returning_to_barn' || agent.status === 'refilling') {
          fillColor = adjustBrightness(fillColor, -0.3)
        }

        // Dibujar agente
        if (agent.agent_type === 'scout') {
          // Scout como hexágono
          const size = cellSize * 0.3
          ctx.fillStyle = fillColor
          ctx.beginPath()
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

          ctx.strokeStyle = '#000000'
          ctx.lineWidth = 2
          ctx.stroke()
        } else {
          // Fumigador como círculo
          ctx.fillStyle = fillColor
          ctx.beginPath()
          ctx.arc(xPos, zPos, radius, 0, Math.PI * 2)
          ctx.fill()

          ctx.strokeStyle = '#000000'
          ctx.lineWidth = 2
          ctx.stroke()
        }

        // Actualizar camino recorrido
        const posKey = `${Math.round(displayX)},${Math.round(displayZ)}`
        if (!pathsTakenRef.current.has(agent.id)) {
          pathsTakenRef.current.set(agent.id, new Set())
        }
        pathsTakenRef.current.get(agent.id)!.add(posKey)
      })

      // Dibujar granero (resaltado)
      const barnCells: Array<[number, number]> = []
      for (let z = 0; z < world.height; z++) {
        for (let x = 0; x < world.width; x++) {
          if (world.grid[z][x] === 3) { // BARN
            barnCells.push([x, z])
          }
        }
      }

      barnCells.forEach(([bx, bz]) => {
        const xPos = offsetX + bx * cellSize
        const zPos = offsetZ + bz * cellSize
        ctx.fillStyle = TILE_COLORS.BARN
        ctx.fillRect(xPos, zPos, cellSize, cellSize)
        ctx.strokeStyle = '#8b0000'
        ctx.lineWidth = 2
        ctx.strokeRect(xPos, zPos, cellSize, cellSize)
      })

      // Continuar animación si hay animaciones activas o si hay agentes moviéndose
      if (activeAnimations.size > 0) {
        animationFrameRef.current = requestAnimationFrame(render)
      }
    }

    // Iniciar loop de animación
    lastFrameTimeRef.current = performance.now()
    animationFrameRef.current = requestAnimationFrame(render)

    // Cleanup: cancelar animación al desmontar
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current)
      }
    }
  }, [world, agents, tasks, showInfestation, activeAnimations])

  return (
    <div className="simulation-map">
      <div className="simulation-map-header">
        <h3>Visualización en Tiempo Real</h3>
        <div className="map-legend">
          <div className="legend-section">
            <strong>Agentes:</strong>
            <div className="legend-item">
              <div className="legend-color fumigator" style={{ backgroundColor: FUMIGATOR_COLOR }}></div>
              <span>Fumigador (Azul)</span>
            </div>
            <div className="legend-item">
              <div className="legend-color scout" style={{ backgroundColor: SCOUT_COLOR }}></div>
              <span>Scout (Cyan)</span>
            </div>
          </div>
          <div className="legend-section">
            <strong>Tareas:</strong>
            <div className="legend-item">
              <div className="legend-color task" style={{ backgroundColor: '#ef4444' }}></div>
              <span>Pendiente (Rojo)</span>
            </div>
            <div className="legend-item">
              <div className="legend-color task" style={{ backgroundColor: '#f59e0b' }}></div>
              <span>Asignada (Amarillo)</span>
            </div>
            <div className="legend-item">
              <div className="legend-color task" style={{ backgroundColor: FUMIGATOR_COLOR }}></div>
              <span>En Progreso (Azul)</span>
            </div>
          </div>
          <div className="legend-section">
            <strong>Terreno:</strong>
            <div className="legend-item">
              <div className="legend-color" style={{ backgroundColor: TILE_COLORS.FIELD }}></div>
              <span>Campo (Verde)</span>
            </div>
            <div className="legend-item">
              <div className="legend-color" style={{ backgroundColor: TILE_COLORS.ROAD }}></div>
              <span>Camino (Marrón)</span>
            </div>
            <div className="legend-item">
              <div className="legend-color" style={{ backgroundColor: TILE_COLORS.BARN }}></div>
              <span>Granero (Rojo)</span>
            </div>
          </div>
        </div>
      </div>
      <canvas
        ref={canvasRef}
        width={800}
        height={800}
        className="simulation-map-canvas"
      />
    </div>
  )
}
