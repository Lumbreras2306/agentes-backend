import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { simulationsApi, worldsApi } from '../services/api'
import { Simulation, World } from '../types'
import { useModal } from '../hooks/useModal'
import Modal from '../components/Modal'
import './Simulations.css'

export default function Simulations() {
  const [simulations, setSimulations] = useState<Simulation[]>([])
  const [worlds, setWorlds] = useState<World[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const { modal, showError, showSuccess, closeModal } = useModal()
  const [formData, setFormData] = useState({
    world_id: '',
    num_fumigators: 5,
    max_steps: 300,
    min_infestation: 10,
  })

  useEffect(() => {
    loadSimulations()
    loadWorlds()
  }, [])

  const loadSimulations = async () => {
    try {
      setLoading(true)
      const response = await simulationsApi.list()
      setSimulations(response.data.results || response.data)
    } catch (error) {
      console.error('Error loading simulations:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadWorlds = async () => {
    try {
      const response = await worldsApi.list()
      const worldsData = response.data.results || response.data
      setWorlds(worldsData)
      if (worldsData.length > 0 && !formData.world_id) {
        setFormData({ ...formData, world_id: worldsData[0].id })
      }
    } catch (error) {
      console.error('Error loading worlds:', error)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await simulationsApi.create(formData)
      setShowCreateForm(false)
      setFormData({
        world_id: worlds[0]?.id || '',
        num_fumigators: 5,
        max_steps: 300,
        min_infestation: 10,
      })
      loadSimulations()
      showSuccess('Simulación creada correctamente')
    } catch (error: any) {
      console.error('Error creating simulation:', error)
      showError(error.response?.data?.error || 'Error al crear la simulación')
    }
  }

  const handleDelete = async (id: string) => {
    if (!window.confirm('¿Estás seguro de eliminar esta simulación?')) return
    try {
      await simulationsApi.delete(id)
      loadSimulations()
      showSuccess('Simulación eliminada correctamente')
    } catch (error) {
      console.error('Error deleting simulation:', error)
      showError('Error al eliminar la simulación')
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'var(--success)'
      case 'running':
        return 'var(--primary)'
      case 'failed':
        return 'var(--danger)'
      default:
        return 'var(--warning)'
    }
  }

  if (loading) {
    return <div className="loading">Cargando simulaciones...</div>
  }

  return (
    <div className="simulations-page">
      <div className="page-header">
        <h1>Simulaciones</h1>
        <button className="btn btn-primary" onClick={() => setShowCreateForm(!showCreateForm)}>
          {showCreateForm ? 'Cancelar' : '+ Crear Simulación'}
        </button>
      </div>

      {showCreateForm && (
        <motion.form
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="create-form"
          onSubmit={handleCreate}
        >
          <h3>Crear Nueva Simulación</h3>
          <div className="form-grid">
            <div className="form-group">
              <label>Mundo</label>
              <select
                value={formData.world_id}
                onChange={(e) => setFormData({ ...formData, world_id: e.target.value })}
                required
              >
                <option value="">Seleccionar mundo...</option>
                {worlds.map((world) => (
                  <option key={world.id} value={world.id}>
                    {world.name} ({world.width}×{world.height})
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>Fumigadores</label>
              <input
                type="number"
                min="1"
                max="10"
                value={formData.num_fumigators}
                onChange={(e) =>
                  setFormData({ ...formData, num_fumigators: parseInt(e.target.value) })
                }
                required
              />
            </div>
            <div className="form-group">
              <label>Máximo de Pasos</label>
              <input
                type="number"
                min="50"
                max="10000"
                step="50"
                value={formData.max_steps}
                onChange={(e) =>
                  setFormData({ ...formData, max_steps: parseInt(e.target.value) })
                }
                required
              />
            </div>
            <div className="form-group">
              <label>Infestación Mínima</label>
              <input
                type="number"
                min="0"
                max="100"
                value={formData.min_infestation}
                onChange={(e) =>
                  setFormData({ ...formData, min_infestation: parseInt(e.target.value) })
                }
                required
              />
            </div>
          </div>
          <button type="submit" className="btn btn-primary">
            Ejecutar Simulación
          </button>
        </motion.form>
      )}

      {simulations.length === 0 ? (
        <div className="empty-state">
          <p>No hay simulaciones creadas aún</p>
        </div>
      ) : (
        <div className="simulations-grid">
          {simulations.map((simulation) => (
            <motion.div
              key={simulation.id}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="simulation-card"
            >
              <div className="simulation-card-header">
                <div className="simulation-status">
                  <span
                    className="status-dot"
                    style={{ background: getStatusColor(simulation.status) }}
                  />
                  <span className="status-text">{simulation.status}</span>
                </div>
                <button
                  className="btn-icon"
                  onClick={() => handleDelete(simulation.id)}
                  title="Eliminar"
                >
                  🗑️
                </button>
              </div>
              <div className="simulation-card-body">
                <p>
                  <strong>Mundo:</strong> {simulation.world}
                </p>
                <div className="simulation-stats">
                  <div className="stat">
                    <span className="stat-label">Agentes:</span>
                    <span className="stat-value">{simulation.num_fumigators} F</span>
                  </div>
                  <div className="stat">
                    <span className="stat-label">Pasos:</span>
                    <span className="stat-value">
                      {simulation.steps_executed} / {simulation.max_steps}
                    </span>
                  </div>
                  <div className="stat">
                    <span className="stat-label">Tareas:</span>
                    <span className="stat-value">{simulation.tasks_completed}</span>
                  </div>
                  <div className="stat">
                    <span className="stat-label">Campos:</span>
                    <span className="stat-value">{simulation.fields_fumigated}</span>
                  </div>
                </div>
                {simulation.started_at && (
                  <p className="simulation-date">
                    Iniciada: {new Date(simulation.started_at).toLocaleString()}
                  </p>
                )}
                {simulation.completed_at && (
                  <p className="simulation-date">
                    Completada: {new Date(simulation.completed_at).toLocaleString()}
                  </p>
                )}
              </div>
              <div className="simulation-card-footer">
                <Link to={`/simulations/${simulation.id}`} className="btn btn-primary">
                  Ver Detalles
                </Link>
              </div>
            </motion.div>
          ))}
        </div>
      )}
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

