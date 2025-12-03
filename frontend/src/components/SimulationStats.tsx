import { useState, useEffect } from 'react'
import { simulationsApi } from '../services/api'
import { SimulationStats as SimulationStatsType } from '../types'
import './SimulationStats.css'

interface SimulationStatsProps {
  simulationId: string
}

export default function SimulationStats({ simulationId }: SimulationStatsProps) {
  const [stats, setStats] = useState<SimulationStatsType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadStats()
  }, [simulationId])

  const loadStats = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await simulationsApi.getStats(simulationId)
      setStats(response.data)
    } catch (err: any) {
      console.error('Error loading stats:', err)
      if (err.response?.status === 404) {
        setError('No se encontraron estadísticas para esta simulación')
      } else {
        setError('Error al cargar las estadísticas')
      }
    } finally {
      setLoading(false)
    }
  }

  const formatDuration = (seconds?: number) => {
    if (!seconds) return 'N/A'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}m ${secs}s`
  }

  const formatPercentage = (value?: number) => {
    if (value === null || value === undefined) return 'N/A'
    return `${value.toFixed(1)}%`
  }

  const formatNumber = (value?: number, decimals: number = 2) => {
    if (value === null || value === undefined) return 'N/A'
    return value.toFixed(decimals)
  }

  if (loading) {
    return <div className="stats-loading">Cargando estadísticas...</div>
  }

  if (error) {
    return <div className="stats-error">{error}</div>
  }

  if (!stats) {
    return <div className="stats-error">No hay estadísticas disponibles</div>
  }

  return (
    <div className="simulation-stats">
      <h3>Estadísticas de la Simulación</h3>
      
      <div className="stats-grid">
        {/* Duración y Eficiencia */}
        <div className="stats-section">
          <h4>⏱️ Duración y Eficiencia</h4>
          <div className="stat-item">
            <span className="stat-label">Duración Total:</span>
            <span className="stat-value">{formatDuration(stats.duration_seconds)}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Eficiencia:</span>
            <span className="stat-value">{formatNumber(stats.efficiency_score)} campos/paso</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Tareas por Paso:</span>
            <span className="stat-value">{formatNumber(stats.tasks_per_step)}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Tiempo Promedio por Tarea:</span>
            <span className="stat-value">{formatDuration(stats.avg_time_per_task)}</span>
          </div>
        </div>

        {/* Tasa de Éxito */}
        <div className="stats-section">
          <h4>✅ Tasa de Éxito</h4>
          <div className="stat-item">
            <span className="stat-label">Tasa de Éxito:</span>
            <span className="stat-value">{formatPercentage(stats.success_rate)}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Completitud:</span>
            <span className="stat-value">{formatPercentage(stats.completion_percentage)}</span>
          </div>
        </div>

        {/* Infestación */}
        <div className="stats-section">
          <h4>🐛 Reducción de Infestación</h4>
          <div className="stat-item">
            <span className="stat-label">Campos Infestados (Inicial):</span>
            <span className="stat-value">{stats.initial_infested_fields}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Campos Infestados (Final):</span>
            <span className="stat-value">{stats.final_infested_fields}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Reducción de Infestación:</span>
            <span className="stat-value highlight">{formatPercentage(stats.infestation_reduction_percentage)}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Infestación Promedio (Inicial):</span>
            <span className="stat-value">{formatNumber(stats.average_initial_infestation, 1)}%</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Infestación Promedio (Final):</span>
            <span className="stat-value">{formatNumber(stats.average_final_infestation, 1)}%</span>
          </div>
        </div>

        {/* Estadísticas por Agente */}
        <div className="stats-section">
          <h4>🤖 Rendimiento por Agente</h4>
          <div className="stat-item">
            <span className="stat-label">Tareas Promedio por Agente:</span>
            <span className="stat-value">{formatNumber(stats.avg_tasks_per_agent)}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Campos Promedio por Agente:</span>
            <span className="stat-value">{formatNumber(stats.avg_fields_per_agent)}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Máximo de Tareas (Agente):</span>
            <span className="stat-value">{stats.max_tasks_by_agent}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Mínimo de Tareas (Agente):</span>
            <span className="stat-value">{stats.min_tasks_by_agent}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

