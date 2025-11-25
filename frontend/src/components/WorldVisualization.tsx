import { useEffect, useRef } from 'react'
import { World } from '../types'
import './WorldVisualization.css'

interface WorldVisualizationProps {
  world: World
  layer?: 'tile' | 'crop' | 'infestation'
  showAgents?: Array<{ x: number; z: number; color: string; label?: string }>
  showTasks?: Array<{ x: number; z: number; level: number }>
}

const TILE_COLORS: Record<number, string> = {
  0: '#2d2d2d', // IMPASSABLE
  1: '#8b7355', // ROAD
  2: '#7ec850', // FIELD
  3: '#c44536', // BARN
}

const CROP_COLORS: Record<number, string> = {
  0: '#1a1a1a', // NONE
  1: '#f4e04d', // WHEAT
  2: '#95d840', // CORN
  3: '#7eb26d', // SOY
}

export default function WorldVisualization({
  world,
  layer = 'tile',
  showAgents = [],
  showTasks = [],
}: WorldVisualizationProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const cellSize = Math.min(
      Math.floor(canvas.width / world.width),
      Math.floor(canvas.height / world.height)
    )

    const offsetX = (canvas.width - world.width * cellSize) / 2
    const offsetZ = (canvas.height - world.height * cellSize) / 2

    // Limpiar canvas
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)

    // Dibujar grid según el layer
    const grid = layer === 'tile' ? world.grid : layer === 'crop' ? world.crop_grid : world.infestation_grid
    const colors = layer === 'tile' ? TILE_COLORS : layer === 'crop' ? CROP_COLORS : null

    for (let z = 0; z < world.height; z++) {
      for (let x = 0; x < world.width; x++) {
        const value = grid[z][x]
        const xPos = offsetX + x * cellSize
        const zPos = offsetZ + z * cellSize

        if (layer === 'infestation') {
          // Escala de grises para infestación
          const intensity = value / 100
          const gray = Math.floor(255 * (1 - intensity))
          ctx.fillStyle = `rgb(${255 - gray}, ${gray}, 0)`
        } else {
          ctx.fillStyle = colors?.[value] || '#000000'
        }

        ctx.fillRect(xPos, zPos, cellSize, cellSize)

        // Borde sutil
        ctx.strokeStyle = 'rgba(0, 0, 0, 0.1)'
        ctx.strokeRect(xPos, zPos, cellSize, cellSize)
      }
    }

    // Dibujar tareas
    showTasks.forEach((task) => {
      const xPos = offsetX + task.x * cellSize
      const zPos = offsetZ + task.z * cellSize
      ctx.fillStyle = `rgba(239, 68, 68, ${Math.min(task.level / 100, 1)})`
      ctx.fillRect(xPos, zPos, cellSize, cellSize)
      ctx.strokeStyle = '#ef4444'
      ctx.lineWidth = 2
      ctx.strokeRect(xPos, zPos, cellSize, cellSize)
    })

    // Dibujar agentes
    showAgents.forEach((agent) => {
      const xPos = offsetX + agent.x * cellSize + cellSize / 2
      const zPos = offsetZ + agent.z * cellSize + cellSize / 2
      const radius = cellSize * 0.3

      ctx.fillStyle = agent.color
      ctx.beginPath()
      ctx.arc(xPos, zPos, radius, 0, Math.PI * 2)
      ctx.fill()

      ctx.strokeStyle = '#000000'
      ctx.lineWidth = 2
      ctx.stroke()

      if (agent.label) {
        ctx.fillStyle = '#000000'
        ctx.font = `${cellSize * 0.3}px Arial`
        ctx.textAlign = 'center'
        ctx.fillText(agent.label, xPos, zPos + cellSize * 0.4)
      }
    })
  }, [world, layer, showAgents, showTasks])

  return (
    <div className="world-visualization">
      <canvas
        ref={canvasRef}
        width={800}
        height={800}
        className="world-canvas"
      />
    </div>
  )
}

