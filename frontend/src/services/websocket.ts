/**
 * Servicio WebSocket para simulaciones en tiempo real
 * Compatible con React frontend y Unity
 */

export type SimulationUpdateType =
  | 'connection'
  | 'simulation_started'
  | 'step_update'
  | 'simulation_completed'
  | 'simulation_error'
  | 'agent_command'
  | 'pong'

export interface SimulationUpdate {
  type: SimulationUpdateType
  simulation_id?: string
  step?: number
  status?: string
  agents?: Array<{
    id: string
    type: 'scout' | 'fumigator'
    position: [number, number]
    status: string
    pesticide_level?: number
    pesticide_capacity?: number
    tasks_completed?: number
    fields_fumigated?: number
    current_task?: {
      position_x: number
      position_z: number
      infestation_level: number
    } | null
    fields_analyzed?: number
    discoveries?: number
  }>
  tasks?: Array<{
    id: string
    position_x: number
    position_z: number
    infestation_level: number
    priority: string
    status: string
    assigned_agent_id: string | null
  }>
  infestation_grid?: number[][] // Grid de infestación actualizado en tiempo real
  // Comando de agente (nuevo sistema)
  agent_id?: string
  command?: {
    action: 'move' | 'fumigate' | 'analyze' | 'refill'
    from_position?: [number, number]
    to_position?: [number, number]
    position?: [number, number]
    fumigate_on_path?: boolean
    fumigation_data?: {
      infestation_level: number
      pesticide_needed: number
      position: [number, number]
    }
    infestation_level?: number
    required_pesticide?: number
    reveal_infestation?: boolean
  }
  results?: {
    tasks_completed?: number
    fields_fumigated?: number
    fields_analyzed?: number
    discoveries?: number
  }
  message?: string
  timestamp?: number
}

export class SimulationWebSocket {
  private ws: WebSocket | null = null
  private simulationId: string
  private url: string
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 3000
  private listeners: Map<string, Set<(data: SimulationUpdate) => void>> = new Map()
  private pingInterval: number | null = null

  constructor(simulationId: string) {
    this.simulationId = simulationId
    
    // Determinar la URL del WebSocket según el entorno
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = import.meta.env.VITE_API_URL?.replace(/^https?:\/\//, '') || 'localhost:8000'
    this.url = `${protocol}//${host}/ws/simulations/${simulationId}/`
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url)

        this.ws.onopen = () => {
          console.log(`WebSocket conectado a simulación ${this.simulationId}`)
          this.reconnectAttempts = 0
          
          // Iniciar ping periódico para mantener la conexión viva
          this.pingInterval = window.setInterval(() => {
            this.ping()
          }, 30000) // Ping cada 30 segundos
          
          resolve()
        }

        this.ws.onmessage = (event) => {
          try {
            const data: SimulationUpdate = JSON.parse(event.data)
            this.handleMessage(data)
          } catch (error) {
            console.error('Error parseando mensaje WebSocket:', error)
          }
        }

        this.ws.onerror = (error) => {
          console.error('Error en WebSocket:', error)
          reject(error)
        }

        this.ws.onclose = () => {
          console.log('WebSocket desconectado')
          
          if (this.pingInterval) {
            clearInterval(this.pingInterval)
            this.pingInterval = null
          }
          
          // Intentar reconectar si no fue un cierre intencional
          if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++
            console.log(`Intentando reconectar (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`)
            setTimeout(() => {
              this.connect().catch(console.error)
            }, this.reconnectDelay)
          }
        }
      } catch (error) {
        reject(error)
      }
    })
  }

  disconnect(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
    
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    
    this.listeners.clear()
  }

  private handleMessage(data: SimulationUpdate): void {
    // Notificar a todos los listeners del tipo específico
    const typeListeners = this.listeners.get(data.type)
    if (typeListeners) {
      typeListeners.forEach((callback) => callback(data))
    }

    // Notificar a todos los listeners generales ('*')
    const allListeners = this.listeners.get('*')
    if (allListeners) {
      allListeners.forEach((callback) => callback(data))
    }
  }

  on(type: SimulationUpdateType | '*', callback: (data: SimulationUpdate) => void): () => void {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set())
    }
    this.listeners.get(type)!.add(callback)

    // Retornar función para desuscribirse
    return () => {
      const listeners = this.listeners.get(type)
      if (listeners) {
        listeners.delete(callback)
      }
    }
  }

  private ping(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'ping',
        timestamp: Date.now()
      }))
    }
  }

  send(message: any): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket no está conectado')
    }
  }

  sendCommandConfirmation(agentId: string, commandId?: string, success: boolean = true): void {
    // Envía confirmación de que un comando fue completado
    this.send({
      type: 'command_confirmation',
      agent_id: agentId,
      command_id: commandId,
      success: success
    })
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }
}
