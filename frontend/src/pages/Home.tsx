import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import StatsOverview from '../components/StatsOverview'
import './Home.css'

export default function Home() {
  return (
    <div className="home">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="hero"
      >
        <h1>Sistema de Agentes de Fumigación</h1>
        <p>
          Visualiza y gestiona simulaciones de agentes coordinados para fumigar campos
          con infestación usando algoritmos de pathfinding y blackboard.
        </p>
      </motion.div>

      <div className="features">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="feature-card"
        >
          <div className="feature-icon">🌍</div>
          <h3>Gestión de Mundos</h3>
          <p>Crea y visualiza mundos con campos, caminos y niveles de infestación</p>
          <Link to="/worlds" className="btn btn-primary">
            Ver Mundos
          </Link>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="feature-card"
        >
          <div className="feature-icon">🤖</div>
          <h3>Simulaciones</h3>
          <p>Ejecuta simulaciones con tractores fumigadores coordinados</p>
          <Link to="/simulations" className="btn btn-primary">
            Ver Simulaciones
          </Link>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="feature-card"
        >
          <div className="feature-icon">📊</div>
          <h3>Estadísticas</h3>
          <p>Visualiza estadísticas detalladas y métricas de rendimiento de las simulaciones</p>
          <Link to="/stats" className="btn btn-primary">
            Ver Estadísticas
          </Link>
        </motion.div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="stats-section"
      >
        <StatsOverview />
      </motion.div>
    </div>
  )
}

