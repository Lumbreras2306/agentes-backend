import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { simulationsApi } from '../services/api'
import { Simulation, SimulationStats } from '../types'
import './Stats.css'

export default function Stats() {
  const [loading, setLoading] = useState(true)
  const [simulations, setSimulations] = useState<Simulation[]>([])
  const [statsList, setStatsList] = useState<SimulationStats[]>([])
  const [aggregatedStats, setAggregatedStats] = useState<{
    totalSimulations: number
    completedSimulations: number
    totalFieldsFumigated: number
    totalTasksCompleted: number
    avgEfficiency: number
    avgInfestationReduction: number
    avgSuccessRate: number
    avgCompletionPercentage: number
    totalDuration: number
  } | null>(null)

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    try {
      setLoading(true)
      const response = await simulationsApi.list()
      const sims: Simulation[] = response.data.results || response.data

      const completedSimulations = sims.filter(
        (sim) => sim.status === 'completed'
      )

      // Cargar estadísticas de todas las simulaciones completadas
      const statsPromises = completedSimulations.map((sim) =>
        simulationsApi
          .getStats(sim.id)
          .then((res) => res.data)
          .catch(() => null)
      )

      const statsResults = await Promise.all(statsPromises)
      const validStats = statsResults.filter(
        (s): s is SimulationStats => s !== null
      )

      setSimulations(completedSimulations)
      setStatsList(validStats)

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

      const successRates = validStats
        .map((s) => s.success_rate)
        .filter((r): r is number => r !== null && r !== undefined)
      const avgSuccessRate =
        successRates.length > 0
          ? successRates.reduce((a, b) => a + b, 0) / successRates.length
          : 0

      const completionPercentages = validStats
        .map((s) => s.completion_percentage)
        .filter((r): r is number => r !== null && r !== undefined)
      const avgCompletionPercentage =
        completionPercentages.length > 0
          ? completionPercentages.reduce((a, b) => a + b, 0) /
            completionPercentages.length
          : 0

      const durations = validStats
        .map((s) => s.duration_seconds)
        .filter((d): d is number => d !== null && d !== undefined)
      const totalDuration =
        durations.length > 0 ? durations.reduce((a, b) => a + b, 0) : 0

      setAggregatedStats({
        totalSimulations: sims.length,
        completedSimulations: completedSimulations.length,
        totalFieldsFumigated,
        totalTasksCompleted,
        avgEfficiency,
        avgInfestationReduction,
        avgSuccessRate,
        avgCompletionPercentage,
        totalDuration,
      })
    } catch (error) {
      console.error('Error loading stats:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatDuration = (seconds: number) => {
    const hours = Math.floor(seconds / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    const secs = Math.floor(seconds % 60)
    if (hours > 0) {
      return `${hours}h ${mins}m ${secs}s`
    }
    return `${mins}m ${secs}s`
  }

  const formatPercentage = (value: number) => {
    return `${value.toFixed(1)}%`
  }

  if (loading) {
    return (
      <div className="stats-page">
        <div className="loading">Cargando estadísticas...</div>
      </div>
    )
  }

  if (!aggregatedStats || aggregatedStats.completedSimulations === 0) {
    return (
      <div className="stats-page">
        <div className="empty-state">
          <h2>📊 Estadísticas Detalladas</h2>
          <p>No hay simulaciones completadas aún</p>
          <Link to="/simulations" className="btn btn-primary">
            Ver Simulaciones
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="stats-page">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="stats-header"
      >
        <h1>📊 Estadísticas Detalladas</h1>
        <p>Análisis completo del rendimiento de las simulaciones</p>
      </motion.div>

      {/* Estadísticas Principales */}
      <div className="stats-main-grid">
        <motion.div
          initial={{ opacity: 0, y: 30, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ 
            delay: 0.1,
            type: "spring",
            stiffness: 100,
            damping: 15
          }}
          whileHover={{ 
            scale: 1.02,
            transition: { duration: 0.2 }
          }}
          className="stat-card large"
        >
          <div className="stat-card-header">
            <motion.h3
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3 }}
            >
              🎯 Resumen General
            </motion.h3>
          </div>
          <div className="stat-card-content">
            <motion.div 
              className="stat-row"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4 }}
            >
              <span className="stat-label">Simulaciones Completadas:</span>
              <motion.span 
                className="stat-value"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.6, type: "spring", stiffness: 200 }}
              >
                {aggregatedStats.completedSimulations}
              </motion.span>
            </motion.div>
            <motion.div 
              className="stat-row"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.5 }}
            >
              <span className="stat-label">Total de Campos Fumigados:</span>
              <motion.span 
                className="stat-value"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.7, type: "spring", stiffness: 200 }}
              >
                {aggregatedStats.totalFieldsFumigated.toLocaleString('es-ES')}
              </motion.span>
            </motion.div>
            <motion.div 
              className="stat-row"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.6 }}
            >
              <span className="stat-label">Total de Tareas Completadas:</span>
              <motion.span 
                className="stat-value"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.8, type: "spring", stiffness: 200 }}
              >
                {aggregatedStats.totalTasksCompleted.toLocaleString('es-ES')}
              </motion.span>
            </motion.div>
            <motion.div 
              className="stat-row"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.7 }}
            >
              <span className="stat-label">Tiempo Total de Ejecución:</span>
              <motion.span 
                className="stat-value"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.9, type: "spring", stiffness: 200 }}
              >
                {formatDuration(aggregatedStats.totalDuration)}
              </motion.span>
            </motion.div>
          </div>
        </motion.div>

        {/* Gráfico de Eficiencia */}
        <motion.div
          initial={{ opacity: 0, y: 30, rotateX: -10 }}
          animate={{ opacity: 1, y: 0, rotateX: 0 }}
          transition={{ 
            delay: 0.2,
            type: "spring",
            stiffness: 100,
            damping: 15
          }}
          whileHover={{ 
            scale: 1.05,
            rotateY: 2,
            transition: { duration: 0.2 }
          }}
          className="stat-card"
        >
          <div className="stat-card-header">
            <h3>⚡ Eficiencia Promedio</h3>
            <p className="stat-description">
              Campos fumigados por paso de simulación
            </p>
          </div>
          <div className="chart-container">
            <div className="bar-chart">
              <div className="bar-label">Eficiencia</div>
              <div className="bar-wrapper">
                <motion.div
                  className="bar-fill efficiency"
                  initial={{ width: 0, scaleX: 0 }}
                  animate={{
                    width: `${Math.min((aggregatedStats.avgEfficiency / 1.5) * 100, 100)}%`,
                    scaleX: 1,
                  }}
                  transition={{ 
                    duration: 1.5, 
                    delay: 0.8,
                    type: "spring",
                    stiffness: 50
                  }}
                >
                  <motion.span 
                    className="bar-value"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 1.5 }}
                  >
                    {aggregatedStats.avgEfficiency.toFixed(2)}
                  </motion.span>
                </motion.div>
              </div>
              <div className="bar-sublabel">campos/paso</div>
            </div>
          </div>
        </motion.div>

        {/* Gráfico de Reducción de Infestación */}
        <motion.div
          initial={{ opacity: 0, y: 30, rotateX: -10 }}
          animate={{ opacity: 1, y: 0, rotateX: 0 }}
          transition={{ 
            delay: 0.3,
            type: "spring",
            stiffness: 100,
            damping: 15
          }}
          whileHover={{ 
            scale: 1.05,
            rotateY: 2,
            transition: { duration: 0.2 }
          }}
          className="stat-card"
        >
          <div className="stat-card-header">
            <h3>📉 Reducción de Infestación</h3>
            <p className="stat-description">
              Porcentaje promedio de reducción de infestación
            </p>
          </div>
          <div className="chart-container">
            <div className="circular-progress">
              <svg className="progress-ring" width="180" height="180" viewBox="0 0 200 200">
                <circle
                  className="progress-ring-background"
                  cx="100"
                  cy="100"
                  r="80"
                />
                <motion.circle
                  className="progress-ring-fill reduction"
                  cx="100"
                  cy="100"
                  r="80"
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={{
                    pathLength: aggregatedStats.avgInfestationReduction / 100,
                    opacity: 1,
                  }}
                  transition={{ 
                    duration: 2, 
                    delay: 0.8,
                    ease: "easeOut"
                  }}
                />
              </svg>
              <motion.div 
                className="progress-value"
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ 
                  delay: 1.2,
                  type: "spring",
                  stiffness: 200
                }}
              >
                {formatPercentage(aggregatedStats.avgInfestationReduction)}
              </motion.div>
            </div>
          </div>
        </motion.div>

        {/* Gráfico de Tasa de Éxito */}
        <motion.div
          initial={{ opacity: 0, y: 30, rotateX: -10 }}
          animate={{ opacity: 1, y: 0, rotateX: 0 }}
          transition={{ 
            delay: 0.4,
            type: "spring",
            stiffness: 100,
            damping: 15
          }}
          whileHover={{ 
            scale: 1.05,
            rotateY: 2,
            transition: { duration: 0.2 }
          }}
          className="stat-card"
        >
          <div className="stat-card-header">
            <h3>✅ Tasa de Éxito</h3>
            <p className="stat-description">
              Porcentaje de tareas completadas exitosamente
            </p>
          </div>
          <div className="chart-container">
            <div className="circular-progress">
              <svg className="progress-ring" width="180" height="180" viewBox="0 0 200 200">
                <circle
                  className="progress-ring-background"
                  cx="100"
                  cy="100"
                  r="80"
                />
                <motion.circle
                  className="progress-ring-fill success"
                  cx="100"
                  cy="100"
                  r="80"
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={{
                    pathLength: aggregatedStats.avgSuccessRate / 100,
                    opacity: 1,
                  }}
                  transition={{ 
                    duration: 2, 
                    delay: 1.0,
                    ease: "easeOut"
                  }}
                />
              </svg>
              <motion.div 
                className="progress-value"
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ 
                  delay: 1.3,
                  type: "spring",
                  stiffness: 200
                }}
              >
                {formatPercentage(aggregatedStats.avgSuccessRate)}
              </motion.div>
            </div>
          </div>
        </motion.div>

        {/* Gráfico de Completitud */}
        <motion.div
          initial={{ opacity: 0, y: 30, rotateX: -10 }}
          animate={{ opacity: 1, y: 0, rotateX: 0 }}
          transition={{ 
            delay: 0.5,
            type: "spring",
            stiffness: 100,
            damping: 15
          }}
          whileHover={{ 
            scale: 1.05,
            rotateY: 2,
            transition: { duration: 0.2 }
          }}
          className="stat-card"
        >
          <div className="stat-card-header">
            <h3>📊 Completitud</h3>
            <p className="stat-description">
              Porcentaje promedio de campos fumigados
            </p>
          </div>
          <div className="chart-container">
            <div className="circular-progress">
              <svg className="progress-ring" width="180" height="180" viewBox="0 0 200 200">
                <circle
                  className="progress-ring-background"
                  cx="100"
                  cy="100"
                  r="80"
                />
                <motion.circle
                  className="progress-ring-fill completion"
                  cx="100"
                  cy="100"
                  r="80"
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={{
                    pathLength: aggregatedStats.avgCompletionPercentage / 100,
                    opacity: 1,
                  }}
                  transition={{ 
                    duration: 2, 
                    delay: 1.2,
                    ease: "easeOut"
                  }}
                />
              </svg>
              <motion.div 
                className="progress-value"
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ 
                  delay: 1.4,
                  type: "spring",
                  stiffness: 200
                }}
              >
                {formatPercentage(aggregatedStats.avgCompletionPercentage)}
              </motion.div>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Tabla de Simulaciones Individuales */}
      {statsList.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="stats-table-section"
        >
          <h2>📋 Estadísticas por Simulación</h2>
          <div className="stats-table-container">
            <table className="stats-table">
              <thead>
                <tr>
                  <th>Simulación</th>
                  <th>Eficiencia</th>
                  <th>Reducción</th>
                  <th>Éxito</th>
                  <th>Completitud</th>
                  <th>Duración</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {statsList.map((stat, index) => {
                  const sim = simulations.find((s) => s.id === stat.simulation)
                  return (
                    <motion.tr
                      key={stat.id}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.7 + index * 0.1 }}
                    >
                      <td>
                        {sim
                          ? `Simulación ${sim.id.slice(0, 8)}...`
                          : 'N/A'}
                      </td>
                      <td>{stat.efficiency_score?.toFixed(2) || 'N/A'}</td>
                      <td>
                        {formatPercentage(
                          stat.infestation_reduction_percentage || 0
                        )}
                      </td>
                      <td>{formatPercentage(stat.success_rate || 0)}</td>
                      <td>
                        {formatPercentage(stat.completion_percentage || 0)}
                      </td>
                      <td>
                        {stat.duration_seconds
                          ? formatDuration(stat.duration_seconds)
                          : 'N/A'}
                      </td>
                      <td>
                        {sim && (
                          <Link
                            to={`/simulations/${sim.id}`}
                            className="btn-link-small"
                          >
                            Ver →
                          </Link>
                        )}
                      </td>
                    </motion.tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}
    </div>
  )
}
