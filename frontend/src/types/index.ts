export interface World {
  id: string
  name: string
  width: number
  height: number
  grid: number[][]
  crop_grid: number[][]
  infestation_grid: number[][]
  seed?: number
  metadata: {
    legend?: any
    stats?: {
      total_fields?: number
      total_roads?: number
      total_barns?: number
    }
  }
  created_at: string
  updated_at: string
}

export interface Agent {
  id: string
  agent_id: string
  world: string
  agent_type: 'fumigator'
  is_active: boolean
  position_x?: number
  position_z?: number
  status: string
  tasks_completed: number
  fields_fumigated: number
  metadata: Record<string, any>
  created_at: string
  updated_at: string
}

export interface Simulation {
  id: string
  world: string
  num_agents: number
  num_fumigators: number
  num_scouts?: number
  max_steps: number
  status: 'pending' | 'running' | 'completed' | 'failed'
  steps_executed: number
  tasks_completed: number
  fields_fumigated: number
  started_at?: string
  completed_at?: string
  created_at: string
  results: Record<string, any>
}

export interface BlackboardTask {
  id: string
  world: string
  position_x: number
  position_z: number
  infestation_level: number
  priority: 'low' | 'medium' | 'high' | 'critical'
  status: 'pending' | 'assigned' | 'in_progress' | 'completed' | 'failed'
  assigned_agent_id?: string
  created_at: string
  assigned_at?: string
  completed_at?: string
  metadata: Record<string, any>
}

export interface WorldTemplate {
  id: string
  name: string
  width: number
  height: number
  road_branch_chance: number
  max_road_length: number
  field_chance: number
  field_growth_chance: number
  min_fields: number
  min_roads: number
  max_attempts: number
}

