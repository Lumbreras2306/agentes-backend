import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { worldsApi, agentsApi, blackboardApi } from '../services/api'
import { World, Agent, BlackboardTask } from '../types'
import { useModal } from '../hooks/useModal'
import Modal from '../components/Modal'
import WorldVisualization from '../components/WorldVisualization'
import DijkstraAnimation from '../components/DijkstraAnimation'
import './WorldDetail.css'

interface AnimationData {
  grid: number[][]
  width: number
  height: number
  barn_pos: number[]
  tractor_paths: number[][][]
  destinations: number[][]
  simulation_steps: Array<Array<{
    position: number[]
    path_index: number
    waiting: boolean
    arrived: boolean
    color: string
  }>>
  tractor_colors: string[]
  drone_path?: number[][]
  drone_destination?: number[]
  drone_simulation_steps?: Array<{
    position: number[]
    path_index: number
    arrived: boolean
    color: string
    revealed_infestation?: Record<string, number> // { "x,z": nivel }
  }>
  drone_color?: string
  infestation_grid?: number[][]
  tile_colors: {
    IMPASSABLE: string
    ROAD: string
    FIELD: string
    BARN: string
  }
}

export default function WorldDetail() {
  const { id } = useParams<{ id: string }>()
  const [world, setWorld] = useState<World | null>(null)
  const [agents, setAgents] = useState<Agent[]>([])
  const [tasks, setTasks] = useState<BlackboardTask[]>([])
  const [loading, setLoading] = useState(true)
  const [activeLayer, setActiveLayer] = useState<'tile' | 'crop' | 'infestation'>('tile')
  const [showAnimation, setShowAnimation] = useState(false)
  const [animationTractors, setAnimationTractors] = useState(3)
  const [animationSpeed, setAnimationSpeed] = useState(300)
  const [animationData, setAnimationData] = useState<AnimationData | null>(null)
  const [loadingAnimation, setLoadingAnimation] = useState(false)
  const { modal, showError, showSuccess, closeModal } = useModal()

  useEffect(() => {
    if (id) {
      loadWorld()
      loadAgents()
      loadTasks()
    }
  }, [id])

  const loadWorld = async () => {
    try {
      setLoading(true)
      const response = await worldsApi.get(id!)
      setWorld(response.data)
    } catch (error) {
      console.error('Error loading world:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadAgents = async () => {
    try {
      const response = await agentsApi.list(id)
      setAgents(response.data.results || response.data)
    } catch (error) {
      console.error('Error loading agents:', error)
    }
  }

  const loadTasks = async () => {
    try {
      const response = await blackboardApi.getWorldTasks(id!)
      setTasks(response.data.results || response.data)
    } catch (error) {
      console.error('Error loading tasks:', error)
    }
  }

  const handleRegenerate = async () => {
    if (!confirm('¿Regenerar este mundo con una nueva seed?')) return
    try {
      const seed = Math.floor(Math.random() * 10000)
      await worldsApi.regenerate(id!, seed)
      loadWorld()
    } catch (error) {
      console.error('Error regenerating world:', error)
      showError('Error al regenerar el mundo')
    }
  }

  const handleInitializeTasks = async () => {
    try {
      await blackboardApi.initializeTasks(id!, 10)
      loadTasks()
      showSuccess('Tareas inicializadas correctamente')
    } catch (error) {
      console.error('Error initializing tasks:', error)
      showError('Error al inicializar tareas')
    }
  }

  const loadAnimationData = async () => {
    if (!id) return
    try {
      setLoadingAnimation(true)
      const response = await worldsApi.visualizeDijkstra(id, animationTractors)
      setAnimationData(response.data)
    } catch (error) {
      console.error('Error loading animation data:', error)
      showError('Error al cargar datos de animación')
    } finally {
      setLoadingAnimation(false)
    }
  }

  useEffect(() => {
    if (showAnimation && !animationData) {
      loadAnimationData()
    }
  }, [showAnimation, animationTractors])

  useEffect(() => {
    if (showAnimation && animationData && animationTractors !== animationData.tractor_colors.length) {
      loadAnimationData()
    }
  }, [animationTractors])

  if (loading) {
    return <div className="loading">Cargando mundo...</div>
  }

  if (!world) {
    return <div className="error">Mundo no encontrado</div>
  }

  const agentColors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']
  const visualizationAgents = agents
    .filter((a) => a.position_x !== null && a.position_z !== null)
    .map((agent, idx) => ({
      x: agent.position_x!,
      z: agent.position_z!,
      color: agentColors[idx % agentColors.length],
      label: agent.agent_type === 'fumigator' ? 'F' : 'S',
    }))

  const visualizationTasks = tasks
    .filter((t) => t.status !== 'completed')
    .map((task) => ({
      x: task.position_x,
      z: task.position_z,
      level: task.infestation_level,
    }))

  return (
    <div className="world-detail">
      <div className="world-detail-header">
        <Link to="/worlds" className="back-link">← Volver a Mundos</Link>
        <div className="world-detail-title">
          <h1>{world.name}</h1>
          <div className="world-detail-actions">
            <button className="btn btn-secondary" onClick={handleRegenerate}>
              🔄 Regenerar
            </button>
            <button className="btn btn-primary" onClick={handleInitializeTasks}>
              📋 Inicializar Tareas
            </button>
          </div>
        </div>
        <div className="world-info">
          <span>Tamaño: {world.width} × {world.height}</span>
          {world.metadata?.stats && (
            <>
              <span>Campos: {world.metadata.stats.total_fields || 0}</span>
              <span>Caminos: {world.metadata.stats.total_roads || 0}</span>
              <span>Graneros: {world.metadata.stats.total_barns || 0}</span>
            </>
          )}
        </div>
      </div>

      <div className="world-detail-content">
        <div className="world-controls">
          <div className="layer-selector">
            <h3>Capas</h3>
            <div className="layer-buttons">
              <button
                className={`layer-btn ${activeLayer === 'tile' ? 'active' : ''}`}
                onClick={() => setActiveLayer('tile')}
              >
                Terreno
              </button>
              <button
                className={`layer-btn ${activeLayer === 'crop' ? 'active' : ''}`}
                onClick={() => setActiveLayer('crop')}
              >
                Cultivos
              </button>
              <button
                className={`layer-btn ${activeLayer === 'infestation' ? 'active' : ''}`}
                onClick={() => setActiveLayer('infestation')}
              >
                Infestación
              </button>
            </div>
          </div>

          <div className="animation-controls">
            <h3>Animación Dijkstra</h3>
            <div className="animation-form">
              <div className="form-group">
                <label>Tractores: {animationTractors} (máximo 5, uno por celda del granero)</label>
                <input
                  type="range"
                  min="1"
                  max="5"
                  value={animationTractors}
                  onChange={(e) => setAnimationTractors(parseInt(e.target.value))}
                />
              </div>
              <div className="form-group">
                <label>Velocidad: {animationSpeed}ms</label>
                <input
                  type="range"
                  min="100"
                  max="1000"
                  step="100"
                  value={animationSpeed}
                  onChange={(e) => setAnimationSpeed(parseInt(e.target.value))}
                />
              </div>
              <button
                className="btn btn-primary"
                onClick={() => setShowAnimation(!showAnimation)}
              >
                {showAnimation ? 'Ocultar' : 'Mostrar'} Animación
              </button>
            </div>
          </div>
        </div>

        <div className="world-visualization-container">
          {showAnimation ? (
            <div className="animation-container">
              {loadingAnimation ? (
                <div className="loading">Cargando datos de animación...</div>
              ) : animationData ? (
                <DijkstraAnimation
                  grid={animationData.grid}
                  width={animationData.width}
                  height={animationData.height}
                  barnPos={animationData.barn_pos}
                  tractorPaths={animationData.tractor_paths}
                  destinations={animationData.destinations}
                  simulationSteps={animationData.simulation_steps}
                  tractorColors={animationData.tractor_colors}
                  dronePath={animationData.drone_path}
                  droneDestination={animationData.drone_destination}
                  droneSimulationSteps={animationData.drone_simulation_steps}
                  droneColor={animationData.drone_color}
                  infestationGrid={animationData.infestation_grid}
                  tileColors={animationData.tile_colors}
                  speed={animationSpeed}
                />
              ) : (
                <div className="error">No se pudieron cargar los datos de animación</div>
              )}
            </div>
          ) : (
            <WorldVisualization
              world={world}
              layer={activeLayer}
              showAgents={visualizationAgents}
              showTasks={visualizationTasks}
            />
          )}
        </div>

        <div className="world-sidebar">
          <div className="sidebar-section">
            <h3>Agentes ({agents.length})</h3>
            <div className="agents-list">
              {agents.length === 0 ? (
                <p className="empty">No hay agentes activos</p>
              ) : (
                agents.map((agent, idx) => (
                  <div key={agent.id} className="agent-item">
                    <div
                      className="agent-color"
                      style={{ background: agentColors[idx % agentColors.length] }}
                    />
                    <div className="agent-info">
                      <strong>{agent.agent_type === 'fumigator' ? 'Fumigador' : 'Scout'}</strong>
                      <span>
                        {agent.position_x !== null && agent.position_z !== null
                          ? `(${agent.position_x}, ${agent.position_z})`
                          : 'Sin posición'}
                      </span>
                      <span className="agent-status">Estado: {agent.status}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="sidebar-section">
            <h3>Tareas ({tasks.length})</h3>
            <div className="tasks-list">
              {tasks.length === 0 ? (
                <p className="empty">No hay tareas</p>
              ) : (
                tasks.slice(0, 10).map((task) => (
                  <div key={task.id} className="task-item">
                    <div className={`task-priority ${task.priority}`} />
                    <div className="task-info">
                      <strong>Posición: ({task.position_x}, {task.position_z})</strong>
                      <span>Infestación: {task.infestation_level}%</span>
                      <span className={`task-status ${task.status}`}>
                        {task.status}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
      <Modal
        isOpen={modal.isOpen}
        onClose={closeModal}
        title={modal.title}
        message={modal.message}
        type={modal.type}
      />
    </div>
  )
}

