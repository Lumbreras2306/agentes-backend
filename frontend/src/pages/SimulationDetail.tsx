import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { simulationsApi, worldsApi } from '../services/api'
import { Simulation, Agent, BlackboardTask, World } from '../types'
import { SimulationWebSocket } from '../services/websocket'
import SimulationMap from '../components/SimulationMap'
import { useAnimations, ActiveAnimation } from '../hooks/useAnimations'
import './SimulationDetail.css'

export default function SimulationDetail() {
  const { id } = useParams<{ id: string }>()
  const [simulation, setSimulation] = useState<Simulation | null>(null)
  const [world, setWorld] = useState<World | null>(null)
  const [agents, setAgents] = useState<Agent[]>([])
  const [tasks, setTasks] = useState<BlackboardTask[]>([])
  const [loading, setLoading] = useState(true)
  const [wsConnected, setWsConnected] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)
  const wsRef = useRef<SimulationWebSocket | null>(null)
  const { activeAnimations, startAnimation, clearAnimation } = useAnimations()

  useEffect(() => {
    if (id) {
      loadSimulation()
      loadAgents()
      loadTasks()
    }

    // Cleanup: desconectar WebSocket al desmontar
    return () => {
      if (wsRef.current) {
        wsRef.current.disconnect()
        wsRef.current = null
      }
    }
  }, [id])

  // Reconectar WebSocket cuando el estado de la simulación cambia a 'running'
  useEffect(() => {
    if (simulation?.status === 'running' && !wsRef.current) {
      connectWebSocket()
    } else if (simulation?.status !== 'running' && wsRef.current) {
      wsRef.current.disconnect()
      wsRef.current = null
      setWsConnected(false)
    }
  }, [simulation?.status])

  const loadSimulation = async () => {
    try {
      setLoading(true)
      const response = await simulationsApi.get(id!)
      setSimulation(response.data)
      
      // Cargar el mundo de la simulación
      if (response.data.world) {
        // Si el mundo viene incluido en la respuesta, usarlo directamente
        if (typeof response.data.world === 'object' && response.data.world.grid) {
          setWorld(response.data.world)
        } else {
          // Si solo viene el ID, cargar el mundo por separado
          const worldId = typeof response.data.world === 'string' 
            ? response.data.world 
            : response.data.world_id || response.data.world?.id
          if (worldId) {
            try {
              const worldResponse = await worldsApi.get(worldId)
              setWorld(worldResponse.data)
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
  }

  const loadAgents = async () => {
    try {
      const response = await simulationsApi.getAgents(id!)
      setAgents(response.data.results || response.data)
    } catch (error) {
      console.error('Error loading agents:', error)
    }
  }

  const loadTasks = async () => {
    try {
      const response = await simulationsApi.getTasks(id!)
      setTasks(response.data.results || response.data)
    } catch (error) {
      console.error('Error loading tasks:', error)
    }
  }

  const handleStartSimulation = async () => {
    if (!id) return
    
    try {
      setLoading(true)
      const response = await simulationsApi.start(id)
      setSimulation(response.data.simulation)
      // Conectar WebSocket después de iniciar
      if (response.data.simulation.status === 'running') {
        connectWebSocket()
      }
    } catch (error: any) {
      console.error('Error iniciando simulación:', error)
      alert(error.response?.data?.error || 'Error al iniciar la simulación')
    } finally {
      setLoading(false)
    }
  }

  // Funciones de animación con efectos visuales reales
  const animateAgentMove = async (agentId: string, from: [number, number], to: [number, number]): Promise<void> => {
    const animationId = `move-${agentId}-${Date.now()}`
    const duration = 400 // 400ms para movimiento suave y visible
    
    const animation: ActiveAnimation = {
      id: animationId,
      type: 'move',
      agentId,
      startTime: performance.now(),
      duration,
      from,
      to,
    }
    
    startAnimation(animation)
    
    return new Promise(resolve => {
      setTimeout(() => {
        clearAnimation(animationId)
        resolve()
      }, duration)
    })
  }

  const animateFumigation = async (agentId: string, position: [number, number], data: any): Promise<void> => {
    const animationId = `fumigate-${agentId}-${Date.now()}`
    const duration = 500 // 500ms para fumigación
    
    const animation: ActiveAnimation = {
      id: animationId,
      type: 'fumigate',
      agentId,
      startTime: performance.now(),
      duration,
      position,
      data,
    }
    
    startAnimation(animation)
    
    return new Promise(resolve => {
      setTimeout(() => {
        clearAnimation(animationId)
        resolve()
      }, duration)
    })
  }

  const animateAnalysis = async (agentId: string, position: [number, number]): Promise<void> => {
    const animationId = `analyze-${agentId}-${Date.now()}`
    const duration = 400 // 400ms para análisis con ondas
    
    const animation: ActiveAnimation = {
      id: animationId,
      type: 'analyze',
      agentId,
      startTime: performance.now(),
      duration,
      position,
    }
    
    startAnimation(animation)
    
    return new Promise(resolve => {
      setTimeout(() => {
        clearAnimation(animationId)
        resolve()
      }, duration)
    })
  }

  const animateRefill = async (agentId: string, position: [number, number]): Promise<void> => {
    const animationId = `refill-${agentId}-${Date.now()}`
    const duration = 1000 // 1000ms para reabastecimiento
    
    const animation: ActiveAnimation = {
      id: animationId,
      type: 'refill',
      agentId,
      startTime: performance.now(),
      duration,
      position,
    }
    
    startAnimation(animation)
    
    return new Promise(resolve => {
      setTimeout(() => {
        clearAnimation(animationId)
        resolve()
      }, duration)
    })
  }

  const connectWebSocket = () => {
    if (!id || wsRef.current) return

    const ws = new SimulationWebSocket(id)
    wsRef.current = ws

    ws.connect()
      .then(() => {
        setWsConnected(true)
        console.log('WebSocket conectado')
      })
      .catch((error) => {
        console.error('Error conectando WebSocket:', error)
        setWsConnected(false)
      })

    // Escuchar actualizaciones de pasos
    ws.on('step_update', (data) => {
      if (data.step !== undefined) {
        setCurrentStep(data.step)
      }
      
      // Actualizar agentes desde los datos del WebSocket
      if (data.agents) {
        const updatedAgents: Agent[] = data.agents.map((agentData) => ({
          id: agentData.id,
          agent_id: agentData.id,
          world: simulation?.world || '',
          agent_type: agentData.type,
          is_active: true,
          position_x: agentData.position[0],
          position_z: agentData.position[1],
          status: agentData.status,
          tasks_completed: agentData.tasks_completed || 0,
          fields_fumigated: agentData.fields_fumigated || 0,
          metadata: agentData.type === 'fumigator' 
            ? {
                pesticide_level: agentData.pesticide_level || 0,
                pesticide_capacity: agentData.pesticide_capacity || 1000,
                pesticide_percentage: agentData.pesticide_level && agentData.pesticide_capacity
                  ? (agentData.pesticide_level / agentData.pesticide_capacity * 100)
                  : 0
              }
            : {
                fields_analyzed: agentData.fields_analyzed || 0,
                discoveries: agentData.discoveries || 0
              },
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }))
        setAgents(updatedAgents)
      }

      // Actualizar tareas desde los datos del WebSocket
      if (data.tasks) {
        const updatedTasks: BlackboardTask[] = data.tasks.map((taskData) => ({
          id: taskData.id,
          world: simulation?.world || '',
          position_x: taskData.position_x,
          position_z: taskData.position_z,
          infestation_level: taskData.infestation_level,
          priority: taskData.priority as 'low' | 'medium' | 'high' | 'critical',
          status: taskData.status as 'pending' | 'assigned' | 'in_progress' | 'completed' | 'failed',
          assigned_agent_id: taskData.assigned_agent_id || undefined,
          created_at: new Date().toISOString(),
          metadata: {}
        }))
        setTasks(updatedTasks)
      }

      // Actualizar grid de infestación del mundo en tiempo real
      if (data.infestation_grid && world) {
        setWorld({
          ...world,
          infestation_grid: data.infestation_grid
        })
      }

      // Actualizar estadísticas de la simulación en tiempo real
      if (simulation) {
        const totalTasksCompleted = data.agents?.reduce((sum: number, a: any) => sum + (a.tasks_completed || 0), 0) || simulation.tasks_completed
        const totalFieldsFumigated = data.agents?.reduce((sum: number, a: any) => sum + (a.fields_fumigated || 0), 0) || simulation.fields_fumigated
        
        setSimulation({
          ...simulation,
          steps_executed: data.step || simulation.steps_executed,
          tasks_completed: totalTasksCompleted,
          fields_fumigated: totalFieldsFumigated
        })
      }
    })

    // Escuchar inicio de simulación
    ws.on('simulation_started', (data) => {
      console.log('Simulación iniciada:', data)
      if (simulation) {
        setSimulation({ ...simulation, status: 'running' })
      }
    })

    // Escuchar finalización de simulación
    ws.on('simulation_completed', (data) => {
      console.log('Simulación completada:', data)
      if (simulation) {
        setSimulation({
          ...simulation,
          status: 'completed',
          steps_executed: data.step || simulation.steps_executed,
          tasks_completed: data.results?.tasks_completed || simulation.tasks_completed,
          fields_fumigated: data.results?.fields_fumigated || simulation.fields_fumigated
        })
      }
      // Recargar datos finales
      loadSimulation()
      loadAgents()
      loadTasks()
    })

    // Escuchar errores
    ws.on('simulation_error', (data) => {
      console.error('Error en simulación:', data)
      if (simulation) {
        setSimulation({ ...simulation, status: 'failed' })
      }
    })

    // Escuchar comandos de agentes (nuevo sistema)
    ws.on('agent_command', async (data) => {
      if (!data.agent_id || !data.command) return
      
      const agentId = data.agent_id
      const command = data.command
      
      console.log('Comando recibido para agente:', agentId, command)
      
      // Encontrar el agente en el estado actual
      setAgents(prevAgents => {
        const agent = prevAgents.find(a => a.id === agentId)
        if (!agent) {
          // Si no existe el agente, confirmar de todas formas para no bloquear
          wsRef.current?.sendCommandConfirmation(agentId, undefined, false)
          return prevAgents
        }
        
        // Procesar comando de forma asíncrona
        processAgentCommand(agentId, command, agent, prevAgents).catch(error => {
          console.error('Error procesando comando:', error)
          wsRef.current?.sendCommandConfirmation(agentId, undefined, false)
        })
        
        return prevAgents
      })
    })

    // Escuchar conexión
    ws.on('connection', (data) => {
      console.log('Conexión WebSocket establecida:', data)
    })
  }

  // Función para procesar comandos de agentes
  const processAgentCommand = async (
    agentId: string,
    command: any,
    agent: Agent,
    _currentAgents: Agent[]
  ) => {
    try {
      if (command.action === 'move') {
        // Animar movimiento del agente
        await animateAgentMove(agentId, command.from_position!, command.to_position!)
          
          // Si hay fumigación en el camino, procesarla
          if (command.fumigate_on_path && command.fumigation_data) {
            await animateFumigation(agentId, command.fumigation_data.position, command.fumigation_data)
            
            // Actualizar infestación del mundo
            if (world && command.fumigation_data.position) {
              const [x, z] = command.fumigation_data.position
              const newGrid = world.infestation_grid.map((row, rowIdx) =>
                rowIdx === z 
                  ? row.map((cell, colIdx) => {
                      if (colIdx === x) {
                        const newLevel = Math.max(0, cell - command.fumigation_data.pesticide_needed)
                        return newLevel
                      }
                      return cell
                    })
                  : row
              )
              setWorld({ ...world, infestation_grid: newGrid })
            }
            
            // Actualizar pesticida del agente (solo si es fumigador)
            if (agent.agent_type === 'fumigator') {
              setAgents(prevAgents =>
                prevAgents.map(a =>
                  a.id === agentId
                    ? {
                        ...a,
                        metadata: {
                          ...a.metadata,
                          pesticide_level: Math.max(0, (a.metadata?.pesticide_level || 0) - command.fumigation_data.pesticide_needed),
                          pesticide_percentage: a.metadata?.pesticide_capacity
                            ? Math.max(0, ((a.metadata?.pesticide_level || 0) - command.fumigation_data.pesticide_needed) / a.metadata.pesticide_capacity * 100)
                            : 0
                        }
                      }
                    : a
                )
              )
            }
          }
          
          // Si el scout revela infestación al moverse
          if (command.reveal_infestation && agent.agent_type === 'scout' && world) {
            // Revelar infestación en 3 filas alrededor de la posición destino
            // El backend ya creará las tareas, aquí solo esperamos a que lleguen en step_update
            // Pero podemos actualizar visualmente el mapa para mostrar la infestación revelada
            // (Las tareas llegarán en el próximo step_update y se mostrarán automáticamente)
          }
          
          // Actualizar posición del agente en el estado
          setAgents(prevAgents => 
            prevAgents.map(a => 
              a.id === agentId 
                ? { ...a, position_x: command.to_position![0], position_z: command.to_position![1] }
                : a
            )
          )
          
        // Confirmar movimiento completado
        wsRef.current?.sendCommandConfirmation(agentId)
        
      } else if (command.action === 'fumigate') {
        // Animar fumigación
        await animateFumigation(agentId, command.position!, {
            infestation_level: command.infestation_level!,
            pesticide_needed: command.required_pesticide!,
            position: command.position!
          })
          
          // Actualizar infestación del mundo
          if (world && command.position) {
            const [x, z] = command.position
            const newGrid = world.infestation_grid.map((row, rowIdx) =>
              rowIdx === z 
                ? row.map((cell, colIdx) => colIdx === x ? 0 : cell)
                : row
            )
            setWorld({ ...world, infestation_grid: newGrid })
          }
          
          // Actualizar pesticida del agente
          if (agent.agent_type === 'fumigator') {
            setAgents(prevAgents =>
              prevAgents.map(a =>
                a.id === agentId
                  ? {
                      ...a,
                      metadata: {
                        ...a.metadata,
                        pesticide_level: Math.max(0, (a.metadata?.pesticide_level || 0) - (command.required_pesticide || 0)),
                        pesticide_percentage: a.metadata?.pesticide_capacity
                          ? Math.max(0, ((a.metadata?.pesticide_level || 0) - (command.required_pesticide || 0)) / a.metadata.pesticide_capacity * 100)
                          : 0
                      },
                      fields_fumigated: (a.fields_fumigated || 0) + 1,
                      tasks_completed: (a.tasks_completed || 0) + 1
                    }
                  : a
              )
            )
          }
          
          // Actualizar tareas: marcar la tarea en esta posición como completada
          if (command.position) {
            const [x, z] = command.position
            setTasks(prevTasks =>
              prevTasks.map(task =>
                task.position_x === x && task.position_z === z
                  ? { ...task, status: 'completed' as const }
                  : task
              )
            )
          }
          
        // Confirmar fumigación completada
        wsRef.current?.sendCommandConfirmation(agentId)
        
      } else if (command.action === 'analyze') {
        // Animar análisis (scout revelando infestación)
        await animateAnalysis(agentId, command.position!)
          
          // Actualizar estadísticas del scout
          setAgents(prevAgents =>
            prevAgents.map(a =>
              a.id === agentId && a.agent_type === 'scout'
                ? {
                    ...a,
                    metadata: {
                      ...a.metadata,
                      fields_analyzed: (a.metadata?.fields_analyzed || 0) + 1
                    }
                  }
                : a
            )
          )
          
          // Las tareas descubiertas se actualizarán en el próximo step_update del backend
        // Confirmar análisis completado
        wsRef.current?.sendCommandConfirmation(agentId)
        
      } else if (command.action === 'refill') {
        // Animar reabastecimiento
        await animateRefill(agentId, command.position!)
          
          // Actualizar nivel de pesticida del agente
          setAgents(prevAgents =>
            prevAgents.map(a =>
              a.id === agentId && a.agent_type === 'fumigator'
                ? {
                    ...a,
                    metadata: {
                      ...a.metadata,
                      pesticide_level: a.metadata?.pesticide_capacity || 1000,
                      pesticide_percentage: 100
                    }
                  }
                : a
            )
          )
          
        // Confirmar reabastecimiento completado
        wsRef.current?.sendCommandConfirmation(agentId)
      }
    } catch (error) {
      console.error('Error procesando comando:', error)
      // Confirmar con error para no bloquear la simulación
      wsRef.current?.sendCommandConfirmation(agentId, undefined, false)
    }
  }

  if (loading) {
    return <div className="loading">Cargando simulación...</div>
  }

  if (!simulation) {
    return <div className="error">Simulación no encontrada</div>
  }

  const fumigators = agents.filter((a) => a.agent_type === 'fumigator')
  const scouts = agents.filter((a) => a.agent_type === 'scout')

  const tasksByStatus = {
    pending: tasks.filter((t) => t.status === 'pending').length,
    assigned: tasks.filter((t) => t.status === 'assigned').length,
    in_progress: tasks.filter((t) => t.status === 'in_progress').length,
    completed: tasks.filter((t) => t.status === 'completed').length,
    failed: tasks.filter((t) => t.status === 'failed').length,
  }

  return (
    <div className="simulation-detail">
      <div className="simulation-detail-header">
        <Link to="/simulations" className="back-link">← Volver a Simulaciones</Link>
        <div className="simulation-detail-title">
          <h1>Simulación {simulation.id.slice(0, 8)}</h1>
          <div className="status-container">
            <div className={`status-badge ${simulation.status}`}>
              {simulation.status}
            </div>
            {simulation.status === 'running' && (
              <div className={`ws-status ${wsConnected ? 'connected' : 'disconnected'}`}>
                {wsConnected ? '🟢 En tiempo real' : '🟡 Conectando...'}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Botón para iniciar simulación si está pendiente */}
      {simulation.status === 'pending' && (
        <div className="simulation-controls">
          <button 
            className="btn btn-primary btn-large"
            onClick={handleStartSimulation}
            disabled={loading}
          >
            ▶ Iniciar Simulación
          </button>
        </div>
      )}

      {simulation.status === 'running' && (
        <div className="simulation-progress">
          <div className="progress-info">
            <span>Paso actual: {currentStep} / {simulation.max_steps}</span>
            <div className="progress-bar">
              <div 
                className="progress-fill" 
                style={{ width: `${(currentStep / simulation.max_steps) * 100}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Visualización del mapa en tiempo real */}
      {world && (
        <SimulationMap
          world={world}
          agents={agents}
          tasks={tasks}
          showInfestation={true}
          activeAnimations={activeAnimations}
        />
      )}

      <div className="simulation-stats-grid">
        <div className="stat-card">
          <div className="stat-icon">🤖</div>
          <div className="stat-content">
            <div className="stat-value">{simulation.num_agents}</div>
            <div className="stat-label">Agentes Totales</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">🚜</div>
          <div className="stat-content">
            <div className="stat-value">{simulation.num_fumigators}</div>
            <div className="stat-label">Fumigadores</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">🔍</div>
          <div className="stat-content">
            <div className="stat-value">{simulation.num_scouts}</div>
            <div className="stat-label">Scouts</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">📊</div>
          <div className="stat-content">
            <div className="stat-value">{simulation.steps_executed}</div>
            <div className="stat-label">Pasos Ejecutados</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">✅</div>
          <div className="stat-content">
            <div className="stat-value">{simulation.tasks_completed}</div>
            <div className="stat-label">Tareas Completadas</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">🌾</div>
          <div className="stat-content">
            <div className="stat-value">{simulation.fields_fumigated}</div>
            <div className="stat-label">Campos Fumigados</div>
          </div>
        </div>
      </div>

      <div className="simulation-content">
        <div className="simulation-section">
          <h2>Agentes</h2>
          <div className="agents-section">
            <div className="agents-group">
              <h3>Fumigadores ({fumigators.length})</h3>
              <div className="agents-list">
                {fumigators.map((agent) => (
                  <div key={agent.id} className="agent-card">
                    <div className="agent-header">
                      <strong>{agent.agent_id}</strong>
                      <span className={`agent-status-badge ${agent.status}`}>
                        {agent.status}
                      </span>
                    </div>
                    <div className="agent-details">
                      <div className="agent-detail">
                        <span>Posición:</span>
                        <span>
                          {agent.position_x !== null && agent.position_z !== null
                            ? `(${agent.position_x}, ${agent.position_z})`
                            : 'N/A'}
                        </span>
                      </div>
                      <div className="agent-detail">
                        <span>Tareas Completadas:</span>
                        <span>{agent.tasks_completed}</span>
                      </div>
                      <div className="agent-detail">
                        <span>Campos Fumigados:</span>
                        <span>{agent.fields_fumigated}</span>
                      </div>
                      {agent.metadata?.pesticide_level !== undefined && (
                        <div className="agent-detail">
                          <span>Pesticida:</span>
                          <span>
                            {Math.round(agent.metadata.pesticide_level)} / {agent.metadata.pesticide_capacity || 1000}
                            {' '}
                            ({Math.round(agent.metadata.pesticide_percentage || 0)}%)
                          </span>
                          <div className="pesticide-bar">
                            <div 
                              className="pesticide-fill" 
                              style={{ width: `${agent.metadata.pesticide_percentage || 0}%` }}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="agents-group">
              <h3>Scouts ({scouts.length})</h3>
              <div className="agents-list">
                {scouts.map((agent) => (
                  <div key={agent.id} className="agent-card">
                    <div className="agent-header">
                      <strong>{agent.agent_id}</strong>
                      <span className={`agent-status-badge ${agent.status}`}>
                        {agent.status}
                      </span>
                    </div>
                    <div className="agent-details">
                      <div className="agent-detail">
                        <span>Posición:</span>
                        <span>
                          {agent.position_x !== null && agent.position_z !== null
                            ? `(${agent.position_x}, ${agent.position_z})`
                            : 'N/A'}
                        </span>
                      </div>
                      {agent.metadata?.fields_analyzed !== undefined && (
                        <div className="agent-detail">
                          <span>Campos Analizados:</span>
                          <span>{agent.metadata.fields_analyzed}</span>
                        </div>
                      )}
                      {agent.metadata?.discoveries !== undefined && (
                        <div className="agent-detail">
                          <span>Descubrimientos:</span>
                          <span>{agent.metadata.discoveries}</span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="simulation-section">
          <h2>Tareas del Blackboard</h2>
          <div className="tasks-summary">
            <div className="task-summary-item">
              <span className="task-summary-label">Pendientes:</span>
              <span className="task-summary-value">{tasksByStatus.pending}</span>
            </div>
            <div className="task-summary-item">
              <span className="task-summary-label">Asignadas:</span>
              <span className="task-summary-value">{tasksByStatus.assigned}</span>
            </div>
            <div className="task-summary-item">
              <span className="task-summary-label">En Progreso:</span>
              <span className="task-summary-value">{tasksByStatus.in_progress}</span>
            </div>
            <div className="task-summary-item">
              <span className="task-summary-label">Completadas:</span>
              <span className="task-summary-value success">{tasksByStatus.completed}</span>
            </div>
            <div className="task-summary-item">
              <span className="task-summary-label">Fallidas:</span>
              <span className="task-summary-value danger">{tasksByStatus.failed}</span>
            </div>
          </div>
          <div className="tasks-list">
            {tasks.length === 0 ? (
              <p className="empty">No hay tareas</p>
            ) : (
              tasks.map((task) => (
                <div key={task.id} className="task-card">
                  <div className="task-card-header">
                    <div className={`task-priority-indicator ${task.priority}`} />
                    <div>
                      <strong>Posición: ({task.position_x}, {task.position_z})</strong>
                      <span className="task-infestation">
                        Infestación: {task.infestation_level}%
                      </span>
                    </div>
                  </div>
                  <div className="task-card-body">
                    <div className="task-info-row">
                      <span>Estado: {task.status}</span>
                      <span>Prioridad: {task.priority}</span>
                      {task.assigned_agent_id && (
                        <span>Asignado a: {task.assigned_agent_id}</span>
                      )}
                    </div>
                    {task.created_at && (
                      <div className="task-date">
                        Creada: {new Date(task.created_at).toLocaleString()}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

