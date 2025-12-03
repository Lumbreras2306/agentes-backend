import { useState, useEffect } from 'react'
import { simulationsApi } from '../services/api'
import { Simulation, SimulationStats } from '../types'
import { Link } from 'react-router-dom'
import './StatsOverview.css'

export default function StatsOverview() {
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState<{
    totalSimulations: number
    completedSimulations: number
    totalFieldsFumigated: number
    totalTasksCompleted: number
    avgEfficiency: number
    avgInfestationReduction: number
    recentStats: SimulationStats[]
  } | null>(null)

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    try {
      setLoading(true)
      const response = await simulationsApi.list()
      const simulations: Simulation[] = response.data.results || response.data

      // Filtrar solo simulaciones completadas
      const completedSimulations = simulations.filter(
        (sim) => sim.status === 'completed'
      )

      // Cargar estadísticas de las simulaciones completadas
      const statsPromises = completedSimulations
        .slice(0, 5) // Solo las 5 más recientes
        .map((sim) =>
          simulationsApi
            .getStats(sim.id)
            .then((res) => res.data)
            .catch(() => null)
        )

      const statsResults = await Promise.all(statsPromises)
      const validStats = statsResults.filter(
        (s): s is SimulationStats => s !== null
      )

      // Calcular estadísticas agregadas
      const totalFieldsFumigated = completedSimulations.reduce(
        (sum, sim) => sum + sim.fields_fumigated,
        0
      )
      const totalTasksCompleted = completedSimulations.reduce(
        (sum, sim) => sum + sim.tasks_completed,
        0
      )

      const efficiencies = validStats
        .map((s) => s.efficiency_score)
        .filter((e): e is number => e !== null && e !== undefined)
      const avgEfficiency =
        efficiencies.length > 0
          ? efficiencies.reduce((a, b) => a + b, 0) / efficiencies.length
          : 0

      const reductions = validStats
        .map((s) => s.infestation_reduction_percentage)
        .filter((r): r is number => r !== null && r !== undefined)
      const avgInfestationReduction =
        reductions.length > 0
          ? reductions.reduce((a, b) => a + b, 0) / reductions.length
          : 0

      setStats({
        totalSimulations: simulations.length,
        completedSimulations: completedSimulations.length,
        totalFieldsFumigated,
        totalTasksCompleted,
        avgEfficiency,
        avgInfestationReduction,
        recentStats: validStats.slice(0, 3),
      })
    } catch (error) {
      console.error('Error loading stats:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatNumber = (value: number) => {
    if (value === 0 || isNaN(value)) return '0'
    return value.toLocaleString('es-ES', { 
      minimumFractionDigits: 0,
      maximumFractionDigits: 2 
    })
  }

  const formatPercentage = (value: number) => {
    if (value === 0 || isNaN(value)) return '0.0%'
    return `${value.toFixed(1)}%`
  }

  const formatEfficiency = (value: number) => {
    if (value === 0 || isNaN(value)) return '0.00'
    return value.toFixed(2)
  }

  if (loading) {
    return (
      <div className="stats-overview">
        <div className="stats-loading">Cargando estadísticas...</div>
      </div>
    )
  }

  if (!stats || stats.completedSimulations === 0) {
    return (
      <div className="stats-overview">
        <div className="stats-empty">
          <p>No hay simulaciones completadas aún</p>
          <Link to="/simulations" className="btn btn-primary">
            Ver Simulaciones
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="stats-overview">
      <div className="stats-header">
        <h2>📊 Estadísticas Generales</h2>
        <Link to="/stats" className="btn-link">
          Ver estadísticas detalladas →
        </Link>
      </div>

      <div className="stats-summary">
        <div className="summary-card">
          <div className="summary-icon">🎯</div>
          <div className="summary-content">
            <div className="summary-value">{stats.completedSimulations}</div>
            <div className="summary-label">Simulaciones Completadas</div>
            <div className="summary-description">
              Número total de simulaciones que han finalizado exitosamente
            </div>
          </div>
        </div>

        <div className="summary-card">
          <div className="summary-icon">🌾</div>
          <div className="summary-content">
            <div className="summary-value">
              {formatNumber(stats.totalFieldsFumigated)}
            </div>
            <div className="summary-label">Campos Fumigados</div>
            <div className="summary-description">
              Total acumulado de campos tratados en todas las simulaciones
            </div>
          </div>
        </div>

        <div className="summary-card">
          <div className="summary-icon">✅</div>
          <div className="summary-content">
            <div className="summary-value">
              {formatNumber(stats.totalTasksCompleted)}
            </div>
            <div className="summary-label">Tareas Completadas</div>
            <div className="summary-description">
              Cantidad total de tareas de fumigación ejecutadas con éxito
            </div>
          </div>
        </div>

        {stats.avgEfficiency > 0 && (
          <div className="summary-card highlight">
            <div className="summary-icon">⚡</div>
            <div className="summary-content">
              <div className="summary-value">
                {formatEfficiency(stats.avgEfficiency)}
              </div>
              <div className="summary-label">Eficiencia Promedio</div>
              <div className="summary-description">
                Campos fumigados por cada paso de simulación ejecutado
              </div>
            </div>
          </div>
        )}

        {stats.avgInfestationReduction > 0 && (
          <div className="summary-card highlight">
            <div className="summary-icon">📉</div>
            <div className="summary-content">
              <div className="summary-value">
                {formatPercentage(stats.avgInfestationReduction)}
              </div>
              <div className="summary-label">Reducción de Infestación</div>
              <div className="summary-description">
                Porcentaje promedio de reducción de plagas en los campos
              </div>
            </div>
          </div>
        )}
      </div>

      {stats.recentStats.length > 0 && (
        <div className="recent-stats">
          <h3>📈 Estadísticas Recientes</h3>
          <div className="recent-stats-grid">
            {stats.recentStats.map((stat, index) => (
              <div key={stat.id} className="recent-stat-card">
                <div className="recent-stat-header">
                  <span className="recent-stat-title">Simulación #{stats.recentStats.length - index}</span>
                </div>
                <div className="recent-stat-item">
                  <span className="recent-stat-label">⚡ Eficiencia:</span>
                  <span className="recent-stat-value">
                    {stat.efficiency_score ? formatEfficiency(stat.efficiency_score) : 'N/A'}
                  </span>
                </div>
                <div className="recent-stat-item">
                  <span className="recent-stat-label">📉 Reducción:</span>
                  <span className="recent-stat-value">
                    {formatPercentage(
                      stat.infestation_reduction_percentage || 0
                    )}
                  </span>
                </div>
                <div className="recent-stat-item">
                  <span className="recent-stat-label">✅ Éxito:</span>
                  <span className="recent-stat-value">
                    {formatPercentage(stat.success_rate || 0)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
