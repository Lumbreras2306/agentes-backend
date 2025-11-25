import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { worldsApi } from '../services/api'
import { World } from '../types'
import './Worlds.css'

export default function Worlds() {
  const [worlds, setWorlds] = useState<World[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    width: 30,
    height: 30,
    seed: Math.floor(Math.random() * 10000),
  })

  useEffect(() => {
    loadWorlds()
  }, [])

  const loadWorlds = async () => {
    try {
      setLoading(true)
      const response = await worldsApi.list()
      setWorlds(response.data.results || response.data)
    } catch (error) {
      console.error('Error loading worlds:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await worldsApi.create(formData)
      setShowCreateForm(false)
      setFormData({ name: '', width: 30, height: 30, seed: Math.floor(Math.random() * 10000) })
      loadWorlds()
    } catch (error) {
      console.error('Error creating world:', error)
      alert('Error al crear el mundo')
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('¿Estás seguro de eliminar este mundo?')) return
    try {
      await worldsApi.delete(id)
      loadWorlds()
    } catch (error) {
      console.error('Error deleting world:', error)
      alert('Error al eliminar el mundo')
    }
  }

  if (loading) {
    return <div className="loading">Cargando mundos...</div>
  }

  return (
    <div className="worlds-page">
      <div className="page-header">
        <h1>Mundos</h1>
        <button className="btn btn-primary" onClick={() => setShowCreateForm(!showCreateForm)}>
          {showCreateForm ? 'Cancelar' : '+ Crear Mundo'}
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
          <h3>Crear Nuevo Mundo</h3>
          <div className="form-grid">
            <div className="form-group">
              <label>Nombre</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label>Ancho</label>
              <input
                type="number"
                min="10"
                max="100"
                value={formData.width}
                onChange={(e) => setFormData({ ...formData, width: parseInt(e.target.value) })}
                required
              />
            </div>
            <div className="form-group">
              <label>Alto</label>
              <input
                type="number"
                min="10"
                max="100"
                value={formData.height}
                onChange={(e) => setFormData({ ...formData, height: parseInt(e.target.value) })}
                required
              />
            </div>
            <div className="form-group">
              <label>Seed</label>
              <input
                type="number"
                value={formData.seed}
                onChange={(e) => setFormData({ ...formData, seed: parseInt(e.target.value) })}
              />
            </div>
          </div>
          <button type="submit" className="btn btn-primary">
            Generar Mundo
          </button>
        </motion.form>
      )}

      {worlds.length === 0 ? (
        <div className="empty-state">
          <p>No hay mundos creados aún</p>
        </div>
      ) : (
        <div className="worlds-grid">
          {worlds.map((world) => (
            <motion.div
              key={world.id}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="world-card"
            >
              <div className="world-card-header">
                <h3>{world.name}</h3>
                <button
                  className="btn-icon"
                  onClick={() => handleDelete(world.id)}
                  title="Eliminar"
                >
                  🗑️
                </button>
              </div>
              <div className="world-card-body">
                <p>
                  <strong>Tamaño:</strong> {world.width} × {world.height}
                </p>
                {world.metadata?.stats && (
                  <div className="world-stats">
                    <span>Campos: {world.metadata.stats.total_fields || 0}</span>
                    <span>Caminos: {world.metadata.stats.total_roads || 0}</span>
                    <span>Graneros: {world.metadata.stats.total_barns || 0}</span>
                  </div>
                )}
                <p className="world-date">
                  Creado: {new Date(world.created_at).toLocaleDateString()}
                </p>
              </div>
              <div className="world-card-footer">
                <Link to={`/worlds/${world.id}`} className="btn btn-primary">
                  Ver Detalles
                </Link>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}

