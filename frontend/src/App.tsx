import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import Worlds from './pages/Worlds'
import WorldDetail from './pages/WorldDetail'
import Simulations from './pages/Simulations'
import SimulationDetail from './pages/SimulationDetail'

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/worlds" element={<Worlds />} />
          <Route path="/worlds/:id" element={<WorldDetail />} />
          <Route path="/simulations" element={<Simulations />} />
          <Route path="/simulations/:id" element={<SimulationDetail />} />
        </Routes>
      </Layout>
    </Router>
  )
}

export default App

