import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Worlds API
export const worldsApi = {
  list: () => api.get('/worlds/'),
  get: (id: string) => api.get(`/worlds/${id}/`),
  create: (data: any) => api.post('/worlds/generate/', data),
  update: (id: string, data: any) => api.patch(`/worlds/${id}/`, data),
  delete: (id: string) => api.delete(`/worlds/${id}/`),
  regenerate: (id: string, seed?: number) => 
    api.post(`/worlds/${id}/regenerate/`, { seed }),
  stats: (id: string) => api.get(`/worlds/${id}/stats/`),
  gridOnly: (id: string) => api.get(`/worlds/${id}/grid_only/`),
  visualize: (id: string, layer: 'tile' | 'crop' | 'infestation' = 'tile') =>
    `${API_BASE_URL}/worlds/${id}/visualize/?layer=${layer}`,
  visualizeCombined: (id: string) =>
    `${API_BASE_URL}/worlds/${id}/visualize_combined/`,
  visualizeDijkstra: (id: string, tractors: number = 3) =>
    api.get(`/worlds/${id}/visualize_dijkstra_animated/`, { params: { tractors } }),
}

// Agents API
export const agentsApi = {
  list: (worldId?: string) => {
    const params = worldId ? { world_id: worldId } : {}
    return api.get('/agents/', { params })
  },
  get: (id: string) => api.get(`/agents/${id}/`),
}

// Simulations API
export const simulationsApi = {
  list: () => api.get('/simulations/'),
  get: (id: string) => api.get(`/simulations/${id}/`),
  create: (data: any) => api.post('/simulations/', data),
  update: (id: string, data: any) => api.patch(`/simulations/${id}/`, data),
  delete: (id: string) => api.delete(`/simulations/${id}/`),
  getAgents: (id: string) => api.get(`/simulations/${id}/agents/`),
  getTasks: (id: string) => api.get(`/simulations/${id}/tasks/`),
}

// Blackboard API
export const blackboardApi = {
  getWorldTasks: (worldId: string, filters?: { status?: string; priority?: string }) => {
    const params = filters || {}
    return api.get(`/blackboard/world/${worldId}/tasks/`, { params })
  },
  getWorldEntries: (worldId: string, filters?: { entry_type?: string }) => {
    const params = filters || {}
    return api.get(`/blackboard/world/${worldId}/entries/`, { params })
  },
  initializeTasks: (worldId: string, minInfestation: number = 10) =>
    api.post(`/blackboard/world/${worldId}/initialize-tasks/`, { min_infestation: minInfestation }),
}

export default api

