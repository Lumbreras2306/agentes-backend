import { Link, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import './Layout.css'

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()

  const navItems = [
    { path: '/', label: 'Inicio' },
    { path: '/worlds', label: 'Mundos' },
    { path: '/simulations', label: 'Simulaciones' },
  ]

  return (
    <div className="layout">
      <header className="header">
        <div className="container">
          <h1 className="logo">🌾 Sistema de Agentes</h1>
          <nav className="nav">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`nav-link ${location.pathname === item.path ? 'active' : ''}`}
              >
                {item.label}
                {location.pathname === item.path && (
                  <motion.div
                    className="nav-indicator"
                    layoutId="nav-indicator"
                    initial={false}
                    transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                  />
                )}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <main className="main">
        <div className="container">{children}</div>
      </main>
    </div>
  )
}

