# Sistema de Eventos de Simulación en Tiempo Real

## Introducción

El sistema de simulación ha sido refactorizado para emitir eventos granulares en tiempo real a través de WebSocket. Este diseño está preparado para:

- **Frontend 2D (React)**: Visualización en 2D con renderizado paso a paso
- **Unity 3D**: Renderizado 3D con animaciones fluidas y sincronización perfecta

## Arquitectura

### Backend (Django + Channels)

```
┌─────────────────────────────────────────────────────────────┐
│                   Simulation System                          │
│                                                              │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │ ScoutAgent   │      │FumigatorAgent│                    │
│  └──────┬───────┘      └──────┬───────┘                    │
│         │                     │                             │
│         └────────┬────────────┘                             │
│                  │                                          │
│         ┌────────▼────────┐                                 │
│         │  EventEmitter   │                                 │
│         └────────┬────────┘                                 │
│                  │                                          │
│         ┌────────▼────────────┐                             │
│         │  Django Channels    │                             │
│         │  (WebSocket Layer)  │                             │
│         └────────┬────────────┘                             │
└──────────────────┼──────────────────────────────────────────┘
                   │
    ┌──────────────┴──────────────┐
    │                             │
┌───▼─────┐                  ┌───▼─────┐
│Frontend │                  │  Unity  │
│  2D     │                  │   3D    │
└─────────┘                  └─────────┘
```

## Tipos de Eventos

### 1. Eventos de Simulación

#### `simulation_initialized`
Se emite cuando la simulación se inicializa.

```json
{
  "type": "simulation_initialized",
  "simulation_id": "uuid",
  "step": 0,
  "timestamp": 1234567890.123,
  "num_fumigators": 5,
  "num_scouts": 1,
  "world_size": [50, 50],
  "agents": [
    {
      "id": "1",
      "type": "fumigator",
      "position": [25, 25]
    }
  ],
  "message": "Simulación iniciada con 5 fumigadores y 1 scouts"
}
```

#### `simulation_step`
Se emite al final de cada paso de la simulación con un resumen del estado.

```json
{
  "type": "simulation_step",
  "simulation_id": "uuid",
  "step": 42,
  "timestamp": 1234567890.123,
  "agents": [...],
  "tasks": [...],
  "statistics": {
    "tasks_completed": 10,
    "fields_fumigated": 15,
    "fields_analyzed": 200
  }
}
```

#### `simulation_completed`
Se emite cuando la simulación termina.

```json
{
  "type": "simulation_completed",
  "simulation_id": "uuid",
  "step": 150,
  "timestamp": 1234567890.123,
  "results": {
    "tasks_completed": 50,
    "fields_fumigated": 75,
    "fields_analyzed": 2500,
    "discoveries": 50,
    "steps_executed": 150
  },
  "message": "Simulación completada exitosamente"
}
```

### 2. Eventos de Agente General

#### `agent_spawned`
Se emite cuando se crea un agente.

```json
{
  "type": "agent_spawned",
  "simulation_id": "uuid",
  "step": 0,
  "timestamp": 1234567890.123,
  "agent_id": "1",
  "agent_type": "fumigator",
  "position": [25, 25]
}
```

#### `agent_moved`
Se emite cuando un agente se mueve de una posición a otra.

```json
{
  "type": "agent_moved",
  "simulation_id": "uuid",
  "step": 10,
  "timestamp": 1234567890.123,
  "agent_id": "1",
  "agent_type": "fumigator",
  "from_position": [25, 25],
  "to_position": [26, 25],
  "path": [[25, 25], [26, 25], [27, 25]]  // Camino completo (opcional)
}
```

**Uso en Unity**: Animar el movimiento del agente desde `from_position` a `to_position`. Si `path` está presente, puede seguir el camino completo.

#### `agent_idle`
Se emite cuando un agente está esperando (sin tareas).

```json
{
  "type": "agent_idle",
  "simulation_id": "uuid",
  "step": 50,
  "timestamp": 1234567890.123,
  "agent_id": "1",
  "agent_type": "fumigator",
  "position": [25, 25]
}
```

**Uso en Unity**: Reproducir animación de idle.

#### `agent_status_changed`
Se emite cuando cambia el estado de un agente.

```json
{
  "type": "agent_status_changed",
  "simulation_id": "uuid",
  "step": 15,
  "timestamp": 1234567890.123,
  "agent_id": "1",
  "agent_type": "fumigator",
  "old_status": "idle",
  "new_status": "moving",
  "position": [25, 25]
}
```

Estados posibles:
- Scout: `scouting`, `moving`
- Fumigator: `idle`, `moving`, `fumigating`, `returning_to_barn`, `refilling`

### 3. Eventos de Scout

#### `scout_reveal_area`
Se emite cuando un scout revela un área (3 filas de campos).

```json
{
  "type": "scout_reveal_area",
  "simulation_id": "uuid",
  "step": 5,
  "timestamp": 1234567890.123,
  "agent_id": "6",
  "revealed_positions": [[10, 5], [11, 5], [12, 5]],
  "infestation_data": [
    {
      "position": [10, 5],
      "infestation_level": 75
    },
    {
      "position": [11, 5],
      "infestation_level": 0
    }
  ]
}
```

**Uso en Unity**: Revelar niebla de guerra (fog of war) en las posiciones indicadas, mostrando niveles de infestación.

#### `infestation_discovered`
Se emite cuando un scout descubre infestación significativa.

```json
{
  "type": "infestation_discovered",
  "simulation_id": "uuid",
  "step": 5,
  "timestamp": 1234567890.123,
  "agent_id": "6",
  "position": [10, 5],
  "infestation_level": 75,
  "task_id": "task-uuid"
}
```

**Uso en Unity**: Destacar visualmente el campo infestado (ej. partículas rojas, warning icon).

### 4. Eventos de Fumigador

#### `fumigation_started`
Se emite cuando comienza la fumigación de un campo.

```json
{
  "type": "fumigation_started",
  "simulation_id": "uuid",
  "step": 20,
  "timestamp": 1234567890.123,
  "agent_id": "1",
  "position": [10, 5],
  "infestation_level": 75,
  "task_id": "task-uuid"
}
```

**Uso en Unity**: Iniciar animación de fumigación (spray de pesticida, efectos de partículas).

#### `fumigation_completed`
Se emite cuando se completa la fumigación de un campo.

```json
{
  "type": "fumigation_completed",
  "simulation_id": "uuid",
  "step": 21,
  "timestamp": 1234567890.123,
  "agent_id": "1",
  "position": [10, 5],
  "pesticide_used": 75,
  "task_id": "task-uuid"
}
```

**Uso en Unity**: Finalizar animación, mostrar campo limpio (cambio de color verde).

#### `agent_refilling`
Se emite cuando un agente comienza a recargar pesticida en el granero.

```json
{
  "type": "agent_refilling",
  "simulation_id": "uuid",
  "step": 35,
  "timestamp": 1234567890.123,
  "agent_id": "1",
  "position": [25, 25],
  "current_pesticide": 50,
  "capacity": 1000
}
```

**Uso en Unity**: Iniciar animación de recarga (tubo conectándose, barra de progreso).

#### `agent_refill_completed`
Se emite cuando un agente termina de recargar pesticida.

```json
{
  "type": "agent_refill_completed",
  "simulation_id": "uuid",
  "step": 36,
  "timestamp": 1234567890.123,
  "agent_id": "1",
  "position": [25, 25],
  "pesticide_level": 1000
}
```

**Uso en Unity**: Finalizar animación de recarga.

#### `pesticide_low`
Se emite cuando el nivel de pesticida de un agente está bajo.

```json
{
  "type": "pesticide_low",
  "simulation_id": "uuid",
  "step": 30,
  "timestamp": 1234567890.123,
  "agent_id": "1",
  "position": [15, 20],
  "pesticide_level": 100,
  "capacity": 1000,
  "percentage": 10.0
}
```

**Uso en Unity**: Mostrar warning visual (icon de tanque bajo, efecto rojo parpadeante).

### 5. Eventos de Tareas

#### `task_created`
Se emite cuando se crea una nueva tarea de fumigación.

```json
{
  "type": "task_created",
  "simulation_id": "uuid",
  "step": 5,
  "timestamp": 1234567890.123,
  "task_id": "task-uuid",
  "position": [10, 5],
  "infestation_level": 75,
  "priority": "high",
  "discovered_by": "6"
}
```

**Uso en Unity**: Crear marker/waypoint visual en el campo (ej. bandera roja).

#### `task_assigned`
Se emite cuando una tarea es asignada a un agente.

```json
{
  "type": "task_assigned",
  "simulation_id": "uuid",
  "step": 6,
  "timestamp": 1234567890.123,
  "task_id": "task-uuid",
  "agent_id": "1",
  "position": [10, 5],
  "infestation_level": 75
}
```

**Uso en Unity**: Cambiar color del marker (amarillo = asignada), mostrar línea de conexión entre agente y tarea.

#### `task_started`
Se emite cuando un agente comienza a trabajar en una tarea.

```json
{
  "type": "task_started",
  "simulation_id": "uuid",
  "step": 15,
  "timestamp": 1234567890.123,
  "task_id": "task-uuid",
  "agent_id": "1",
  "position": [10, 5]
}
```

**Uso en Unity**: Cambiar color del marker (azul = en progreso).

#### `task_completed`
Se emite cuando una tarea se completa exitosamente.

```json
{
  "type": "task_completed",
  "simulation_id": "uuid",
  "step": 21,
  "timestamp": 1234567890.123,
  "task_id": "task-uuid",
  "agent_id": "1",
  "position": [10, 5],
  "completion_time": 1234567890.123
}
```

**Uso en Unity**: Remover marker, mostrar efecto de completado (checkmark verde, partículas).

### 6. Eventos de Mundo

#### `infestation_changed`
Se emite cuando cambia el nivel de infestación de un campo.

```json
{
  "type": "infestation_changed",
  "simulation_id": "uuid",
  "step": 21,
  "timestamp": 1234567890.123,
  "position": [10, 5],
  "old_level": 75,
  "new_level": 0
}
```

**Uso en Unity**: Actualizar visualización del campo (cambio gradual de color rojo → verde).

## Integración con Unity 3D

### Ejemplo de Cliente Unity (C#)

```csharp
using UnityEngine;
using WebSocketSharp;
using Newtonsoft.Json;
using System.Collections.Generic;

public class SimulationClient : MonoBehaviour
{
    private WebSocket ws;
    private Dictionary<string, GameObject> agents = new Dictionary<string, GameObject>();

    void Start()
    {
        string simulationId = "your-simulation-uuid";
        ws = new WebSocket($"ws://localhost:8000/ws/simulations/{simulationId}/");

        ws.OnMessage += (sender, e) =>
        {
            var data = JsonConvert.DeserializeObject<SimulationEvent>(e.Data);
            HandleEvent(data);
        };

        ws.Connect();
    }

    void HandleEvent(SimulationEvent evt)
    {
        switch (evt.type)
        {
            case "agent_spawned":
                SpawnAgent(evt.agent_id, evt.agent_type, evt.position);
                break;

            case "agent_moved":
                MoveAgent(evt.agent_id, evt.from_position, evt.to_position);
                break;

            case "fumigation_started":
                StartFumigationAnimation(evt.agent_id, evt.position);
                break;

            case "fumigation_completed":
                StopFumigationAnimation(evt.agent_id);
                UpdateFieldColor(evt.position, Color.green);
                break;

            case "scout_reveal_area":
                RevealArea(evt.revealed_positions, evt.infestation_data);
                break;

            // ... otros eventos
        }
    }

    void SpawnAgent(string id, string type, float[] pos)
    {
        GameObject prefab = type == "fumigator" ? fumigatorPrefab : scoutPrefab;
        GameObject agent = Instantiate(prefab, new Vector3(pos[0], 0, pos[1]), Quaternion.identity);
        agents[id] = agent;
    }

    void MoveAgent(string id, float[] from, float[] to)
    {
        GameObject agent = agents[id];
        StartCoroutine(SmoothMove(agent, new Vector3(to[0], 0, to[1]), 0.5f));
    }

    // ... más métodos
}
```

## Integración con Frontend 2D (React)

### Ejemplo de uso

```typescript
import { SimulationWebSocket, SimulationUpdate } from './services/websocket'

function SimulationView({ simulationId }: { simulationId: string }) {
  const [agents, setAgents] = useState<Map<string, AgentState>>(new Map())
  const wsRef = useRef<SimulationWebSocket>()

  useEffect(() => {
    const ws = new SimulationWebSocket(simulationId)
    wsRef.current = ws

    // Suscribirse a eventos específicos
    ws.on('agent_spawned', (data) => {
      console.log('Agent spawned:', data.agent_id, data.position)
      // Agregar agente al mapa
    })

    ws.on('agent_moved', (data) => {
      console.log('Agent moved:', data.agent_id, data.from_position, '→', data.to_position)
      // Animar movimiento
    })

    ws.on('fumigation_started', (data) => {
      console.log('Fumigation started at:', data.position)
      // Mostrar animación de spray
    })

    ws.on('task_created', (data) => {
      console.log('New task:', data.task_id, 'at', data.position)
      // Agregar marker visual
    })

    // O suscribirse a todos los eventos
    ws.on('*', (data) => {
      console.log('Event:', data.type, data)
    })

    ws.connect()

    return () => ws.disconnect()
  }, [simulationId])

  return <div>...</div>
}
```

## Diferencias con el Sistema Anterior

### Antes (Sistema de Comandos)
- Backend enviaba comandos → cliente confirmaba → backend continuaba
- Un solo evento `step_update` con todo el estado
- Alto acoplamiento entre backend y cliente
- Latencia por espera de confirmaciones

### Ahora (Sistema de Eventos)
- Backend emite eventos granulares en tiempo real
- Cliente solo escucha y renderiza
- Eventos específicos para cada acción
- Sin confirmaciones → Sin latencia
- Perfecto para Unity y frontend 2D

## Notas Importantes

1. **Todos los eventos incluyen**: `simulation_id`, `step`, `timestamp`
2. **Los eventos son unidireccionales**: Backend → Cliente (no se requieren confirmaciones)
3. **El frontend puede escuchar eventos específicos** o todos (`'*'`)
4. **Unity puede pausar/acelerar** renderizado sin afectar la simulación
5. **El sistema mantiene compatibilidad** con eventos legacy (`step_update`, etc.)

## Próximos Pasos

Para futuras mejoras:
- [ ] Agregar evento `simulation_paused` / `simulation_resumed`
- [ ] Agregar soporte para replay (guardar eventos en BD)
- [ ] Agregar compresión de eventos para reducir bandwidth
- [ ] Agregar eventos de colisiones entre agentes
- [ ] Agregar eventos de clima/ambiente

## Referencias

- Código del EventEmitter: `agents/simulation_events.py`
- Código del Consumer: `agents/consumers.py`
- Sistema de Agentes: `agents/agent_system.py`
- Cliente TypeScript: `frontend/src/services/websocket.ts`
