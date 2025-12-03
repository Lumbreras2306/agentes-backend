import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { simulationsApi, worldsApi } from '../services/api'
import { Simulation, Agent, BlackboardTask, World } from '../types'
import { SimulationWebSocket } from '../services/websocket'
import SimulationMapImproved from '../components/SimulationMapImproved'
import './SimulationDetail.css'

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

export default function SimulationDetail() {
  const { id } = useParams<{ id: string }>()
  const [simulation, setSimulation] = useState<Simulation | null>(null)
  const [world, setWorld] = useState<World | null>(null)
  const [agents, setAgents] = useState<Agent[]>([])
  const [tasks, setTasks] = useState<BlackboardTask[]>([])
  const [loading, setLoading] = useState(true)
  const [wsConnected, setWsConnected] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)
  const [currentPhase, setCurrentPhase] = useState<'fumigation' | 'completed'>('fumigation')
  const [revealedCells, setRevealedCells] = useState<Set<string>>(new Set())
  const [infestationGrid, setInfestationGrid] = useState<number[][] | null>(null)
  const [activeAnimations, setActiveAnimations] = useState<Map<string, ActiveAnimation>>(new Map())

  const wsRef = useRef<SimulationWebSocket | null>(null)
  const animationTimeoutRef = useRef<Map<string, number>>(new Map())
  const cellsInitializedRef = useRef<boolean>(false)

  const loadSimulation = useCallback(async () => {
    if (!id) return
    try {
      setLoading(true)
      const response = await simulationsApi.get(id)
      setSimulation(response.data)

      if (response.data.world) {
        if (typeof response.data.world === 'object' && response.data.world.grid) {
          setWorld(response.data.world)
          setInfestationGrid(response.data.world.infestation_grid)
        } else {
          const worldId = typeof response.data.world === 'string'
            ? response.data.world
            : response.data.world_id || response.data.world?.id
          if (worldId) {
            try {
              const worldResponse = await worldsApi.get(worldId)
              setWorld(worldResponse.data)
              setInfestationGrid(worldResponse.data.infestation_grid)
            } catch (worldError) {
              console.error('Error loading world:', worldError)
            }
          }
        }
      }
    } catch (error) {
      console.error('Error loading simulation:', error)
    } finally {
      setLoading(false)
    }
  }, [id])

  const loadAgents = useCallback(async () => {
    if (!id) return
    try {
      const response = await simulationsApi.getAgents(id)
      setAgents(response.data.results || response.data)
    } catch (error) {
      console.error('Error loading agents:', error)
    }
  }, [id])

  const loadTasks = useCallback(async () => {
    if (!id) return
    try {
      const response = await simulationsApi.getTasks(id)
      setTasks(response.data.results || response.data)
    } catch (error) {
      console.error('Error loading tasks:', error)
    }
  }, [id])

  useEffect(() => {
    if (id) {
      loadSimulation()
      loadAgents()
      loadTasks()
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.disconnect()
        wsRef.current = null
      }
      // Clear all animation timeouts
      animationTimeoutRef.current.forEach(timeout => clearTimeout(timeout))
    }
  }, [id, loadSimulation, loadAgents, loadTasks])

  const handleStartSimulation = async () => {
    if (!id) return

    try {
      setLoading(true)
      const response = await simulationsApi.start(id)
      setSimulation(response.data.simulation)
      if (response.data.simulation.status === 'running') {
        connectWebSocket()
      }
    } catch (error: any) {
      console.error('Error starting simulation:', error)
      alert(error.response?.data?.error || 'Error al iniciar la simulación')
    } finally {
      setLoading(false)
    }
  }

  const startAnimation = useCallback((animation: ActiveAnimation) => {
    setActiveAnimations(prev => {
      const newMap = new Map(prev)
      newMap.set(animation.id, animation)
      return newMap
    })

    // Auto-clear animation after duration
    const timeout = setTimeout(() => {
      setActiveAnimations(prev => {
        const newMap = new Map(prev)
        newMap.delete(animation.id)
        return newMap
      })
      animationTimeoutRef.current.delete(animation.id)
    }, animation.duration)

    animationTimeoutRef.current.set(animation.id, timeout)
  }, [])

  const handleStepUpdate = useCallback((data: any) => {
    setCurrentStep(data.step || 0)

    // Update agents
    if (data.agents && Array.isArray(data.agents)) {
      setAgents(prevAgents => {
        const updatedAgents = data.agents
          .map((agentData: any) => {
            // El backend envía 'agent_id' y 'agent_type', pero también puede enviar 'id' y 'type'
            const agentId = agentData.agent_id || agentData.id
            const agentType = agentData.agent_type || 'fumigator'
            const existingAgent = prevAgents.find(a => a.agent_id === agentId || a.id === agentId)

            // Create animation for movement
            if (existingAgent &&
                existingAgent.position_x !== undefined &&
                existingAgent.position_z !== undefined &&
                agentData.position &&
                Array.isArray(agentData.position) &&
                agentData.position.length >= 2 &&
                (existingAgent.position_x !== agentData.position[0] ||
                 existingAgent.position_z !== agentData.position[1])) {
              const animation: ActiveAnimation = {
                id: `move-${agentId}-${Date.now()}`,
                type: 'move',
                agentId: agentId,
                startTime: performance.now(),
                duration: 800, // Aumentado de 400 a 800ms para animación más fluida
                from: [existingAgent.position_x, existingAgent.position_z],
                to: agentData.position,
              }
              startAnimation(animation)
            }

            // Scouts eliminados - todas las celdas están reveladas desde el inicio
            // La inicialización se hace en el useEffect cuando se carga el mundo

            // Create fumigation animation
            if (agentType === 'fumigator' && agentData.status === 'fumigating') {
              const animation: ActiveAnimation = {
                id: `fumigate-${agentId}-${Date.now()}`,
                type: 'fumigate',
                agentId: agentId,
                startTime: performance.now(),
                duration: 1200, // Aumentado de 800 a 1200ms
                position: agentData.position,
              }
              startAnimation(animation)
            }

            const existingAgentData = existingAgent || prevAgents.find(a => a.agent_id === agentId || a.id === agentId)
        
        // Asegurar que tenemos posición válida
        if (!agentData.position || !Array.isArray(agentData.position) || agentData.position.length < 2) {
          console.warn('Agent data missing position:', { agentId, agentType, agentData })
          // Si no hay posición pero hay un agente existente, mantenerlo
          if (existingAgentData) {
            return existingAgentData
          }
          return null
        }
        
        // Si no hay agentId, no podemos procesar este agente
        if (!agentId) {
          console.warn('Agent data missing ID:', agentData)
          return null
        }
        
        return {
          id: agentId,
          agent_id: agentId,
          world: existingAgentData?.world || '',
          agent_type: agentType,
          is_active: existingAgentData?.is_active ?? true,
          position_x: agentData.position[0],
          position_z: agentData.position[1],
          status: agentData.status || 'idle',
          tasks_completed: agentData.tasks_completed || 0,
          fields_fumigated: agentData.fields_fumigated || 0,
          metadata: {
            pesticide_level: agentData.pesticide_level || 0,
          },
          created_at: existingAgentData?.created_at || new Date().toISOString(),
          updated_at: new Date().toISOString(),
        } as Agent
      })
      .filter((agent: Agent | null): agent is Agent => agent !== null)
      
      return updatedAgents
      })
    }

    // Update tasks
    if (data.tasks && Array.isArray(data.tasks)) {
      const updatedTasks = data.tasks.map((taskData: any) => ({
        id: taskData.task_id,
        position_x: taskData.position[0],
        position_z: taskData.position[1],
        infestation_level: taskData.infestation_level,
        priority: taskData.priority,
        status: taskData.status,
        assigned_agent_id: taskData.assigned_agent_id,
      } as BlackboardTask))

      setTasks(updatedTasks)
    }

    // Update infestation grid
    if (data.infestation_grid) {
      setInfestationGrid(data.infestation_grid)
    }

    // Fase siempre es fumigation desde el inicio (scouts eliminados)
    setCurrentPhase(prev => {
      if (prev !== 'fumigation' && prev !== 'completed') {
        return 'fumigation'
      }
      return prev
    })
  }, [startAnimation])

  const connectWebSocket = useCallback(() => {
    if (!id) return
    if (wsRef.current) return // Ya hay una conexión activa

    const ws = new SimulationWebSocket(id)

    ws.on('connection', (data) => {
      console.log('WebSocket connected:', data)
      setWsConnected(true)
    })

    ws.on('step_update', (data) => {
      console.log('Step update:', data)
      handleStepUpdate(data)
    })

    ws.on('simulation_completed', (data) => {
      console.log('Simulation completed:', data)
      setCurrentPhase('completed')
      setSimulation(prev => prev ? { ...prev, status: 'completed' } : null)
    })

    // Usar listeners genéricos para eventos no tipados
    ws.on('*', (data) => {
      const dataType = (data as any).type || data.type
      if (dataType === 'error') {
        console.error('WebSocket error:', data)
      }
      if (dataType === 'close') {
        console.log('WebSocket disconnected')
        setWsConnected(false)
      }
    })

    ws.connect().catch((error) => {
      console.error('Error connecting WebSocket:', error)
      setWsConnected(false)
    })
    wsRef.current = ws
  }, [id, handleStepUpdate])

  useEffect(() => {
    if (simulation?.status === 'running' && !wsRef.current) {
      connectWebSocket()
    } else if (simulation?.status !== 'running' && wsRef.current) {
      wsRef.current.disconnect()
      wsRef.current = null
      setWsConnected(false)
    }
  }, [simulation?.status, connectWebSocket])

  // Inicializar todas las celdas como reveladas desde el inicio (solo una vez)
  useEffect(() => {
    if (world && !cellsInitializedRef.current) {
      const allCells = new Set<string>()
      for (let z = 0; z < world.height; z++) {
        for (let x = 0; x < world.width; x++) {
          allCells.add(`${x},${z}`)
        }
      }
      setRevealedCells(allCells)
      cellsInitializedRef.current = true
    }
  }, [world])

  if (loading && !simulation) {
    return (
      <div className="container">
        <div className="loading">Cargando simulación...</div>
      </div>
    )
  }

  if (!simulation) {
    return (
      <div className="container">
        <div className="error">Simulación no encontrada</div>
      </div>
    )
  }

  const fumigatorAgents = agents.filter(a => a.agent_type === 'fumigator')
  const completedTasks = tasks.filter(t => t.status === 'completed').length
  const totalTasks = tasks.length

  return (
    <div className="container simulation-detail">
      {/* Header */}
      <div className="header">
        <Link to="/simulations" className="back-link">← Volver a Simulaciones</Link>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <h1>Simulación: {simulation.id}</h1>
          <div className={`status-badge status-${simulation.status}`}>{simulation.status}</div>
        </div>
      </div>

      {/* Control Panel */}
      {simulation.status === 'pending' && (
        <div className="control-panel">
          <button
            onClick={handleStartSimulation}
            disabled={loading}
            className="btn btn-primary"
          >
            {loading ? 'Iniciando...' : '▶ Iniciar Simulación'}
          </button>
        </div>
      )}

      {/* Simulation Map - Main Focus */}
      {world && (
        <SimulationMapImproved
          world={world}
          agents={agents}
          tasks={tasks}
          showInfestation={true}
          activeAnimations={activeAnimations}
          infestationGrid={infestationGrid || undefined}
          revealedCells={revealedCells}
        />
      )}

      {/* Status and Info Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem', marginTop: '2rem' }}>
        {/* Simulation Status Panel */}
        <div className="simulation-status">
          <h3>Estado de la Simulación</h3>

          <div className={`phase-indicator ${currentPhase}`}>
            {currentPhase === 'fumigation' && '🚜 Fase de Fumigación'}
            {currentPhase === 'completed' && '✓ Simulación Completada'}
          </div>

          <div className="status-grid">
            <div className="status-item">
              <span className="status-label">Paso Actual</span>
              <span className="status-value">{currentStep} / {simulation.max_steps}</span>
            </div>
            <div className="status-item">
              <span className="status-label">Fumigadores Activos</span>
              <span className="status-value fumigator">
                {fumigatorAgents.filter(a => a.status !== 'idle').length} / {fumigatorAgents.length}
              </span>
            </div>
            <div className="status-item">
              <span className="status-label">Tareas Completadas</span>
              <span className="status-value completed">
                {completedTasks} / {totalTasks}
              </span>
            </div>
            <div className="status-item">
              <span className="status-label">WebSocket</span>
              <span className={`status-value ${wsConnected ? 'connected' : 'disconnected'}`}>
                {wsConnected ? '✓ Conectado' : '✗ Desconectado'}
              </span>
            </div>
          </div>
        </div>

        {/* Agents List */}
        <div className="agents-section">
          <h3>Agentes ({agents.length})</h3>
          <div className="agents-list">
            {agents
              .filter(agent => agent.agent_type === 'fumigator') // Solo mostrar fumigadores
              .map(agent => (
              <div key={agent.id} className={`agent-card agent-${agent.agent_type}`}>
                <div className="agent-header">
                  <span className="agent-icon">🚜</span>
                  <span className="agent-id">{agent.agent_id}</span>
                  <span className={`agent-status status-${agent.status}`}>
                    {agent.status}
                  </span>
                </div>
                <div className="agent-stats">
                  <div><strong>Posición:</strong> ({agent.position_x ?? '?'}, {agent.position_z ?? '?'})</div>
                  <div><strong>Tareas:</strong> {agent.tasks_completed}</div>
                  <div><strong>Pesticida:</strong> {agent.metadata?.pesticide_level || 0}%</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
