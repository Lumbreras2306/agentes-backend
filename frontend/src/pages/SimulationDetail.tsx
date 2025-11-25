import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { simulationsApi } from '../services/api'
import { Simulation, Agent, BlackboardTask } from '../types'
import './SimulationDetail.css'

export default function SimulationDetail() {
  const { id } = useParams<{ id: string }>()
  const [simulation, setSimulation] = useState<Simulation | null>(null)
  const [agents, setAgents] = useState<Agent[]>([])
  const [tasks, setTasks] = useState<BlackboardTask[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (id) {
      loadSimulation()
      loadAgents()
      loadTasks()
    }
  }, [id])

  const loadSimulation = async () => {
    try {
      setLoading(true)
      const response = await simulationsApi.get(id!)
      setSimulation(response.data)
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
          <div className={`status-badge ${simulation.status}`}>
            {simulation.status}
          </div>
        </div>
      </div>

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

