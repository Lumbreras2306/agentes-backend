# Guía de Integración Unity - Sistema de Simulación Multiagentes

## 📡 Unity Communication Protocol v2.0

Esta guía describe **EXACTAMENTE** cómo Unity debe conectarse y comunicarse con el backend. El protocolo es **IDÉNTICO** al usado por el frontend React.

---

## 🔌 Conexión WebSocket

### URL de Conexión
```
ws://localhost:8000/ws/simulations/{simulation_id}/
```

**Ejemplo:**
```
ws://localhost:8000/ws/simulations/0fa14b06-d84b-4863-b87b-1b462a8cad2c/
```

### Pasos de Conexión

1. **Crear WebSocket**
   ```csharp
   // Unity C#
   string simulationId = "0fa14b06-d84b-4863-b87b-1b462a8cad2c";
   string wsUrl = $"ws://localhost:8000/ws/simulations/{simulationId}/";
   WebSocket ws = new WebSocket(wsUrl);
   ```

2. **Conectar**
   ```csharp
   ws.Connect();
   ```

3. **Recibir Mensaje de Confirmación**
   Unity recibirá inmediatamente:
   ```json
   {
     "type": "connection",
     "message": "Conectado a la simulación",
     "simulation_id": "0fa14b06-d84b-4863-b87b-1b462a8cad2c",
     "timestamp": "2025-12-01T10:30:00.000Z",
     "version": "2.0"
   }
   ```

---

## 📥 Mensajes que Unity RECIBE del Backend

### 1. Connection Message (Conexión Establecida)

**Cuándo:** Inmediatamente después de conectarse

```json
{
  "type": "connection",
  "message": "Conectado a la simulación",
  "simulation_id": "uuid",
  "timestamp": "ISO8601",
  "version": "2.0"
}
```

**Acción en Unity:** Confirmar conexión exitosa, inicializar escena

---

### 2. Step Update (Actualización de Paso)

**Cuándo:** Cada paso de la simulación (cada 0.5 segundos por defecto)

**Formato:**
```json
{
  "type": "step_update",
  "timestamp": "2025-12-01T10:30:01.500Z",
  "version": "2.0",
  "step": 42,
  "agents": [
    {
      "agent_id": "scout_1",
      "agent_type": "scout",
      "position": [12, 5],
      "status": "scouting",
      "fields_analyzed": 150,
      "tasks_completed": 0,
      "fields_fumigated": 0,
      "current_task_id": null,
      "path": [[12, 5], [13, 5], [14, 5]]
    },
    {
      "agent_id": "fumigator_1",
      "agent_type": "fumigator",
      "position": [8, 10],
      "status": "fumigating",
      "pesticide_level": 850,
      "tasks_completed": 5,
      "fields_fumigated": 5,
      "current_task_id": "task_123",
      "path": [[8, 10], [8, 11]]
    }
  ],
  "tasks": [
    {
      "task_id": "task_123",
      "position": [8, 10],
      "infestation_level": 75,
      "priority": "high",
      "status": "in_progress",
      "assigned_agent_id": "fumigator_1",
      "crop_type": "wheat"
    },
    {
      "task_id": "task_124",
      "position": [10, 12],
      "infestation_level": 45,
      "priority": "medium",
      "status": "pending",
      "assigned_agent_id": null,
      "crop_type": "corn"
    }
  ],
  "statistics": {
    "total_tasks": 25,
    "completed_tasks": 5,
    "pending_tasks": 20,
    "active_agents": 6,
    "coverage_percentage": 35.5,
    "average_infestation": 52.3
  },
  "infestation_grid": [
    [0, 0, 45, 78, 12, ...],
    [23, 0, 67, 0, 89, ...],
    ...
  ]
}
```

**Campos Importantes:**

- **`position`**: `[x, z]` - Coordenadas del agente
- **`status`**: Estado actual del agente
  - Scout: `'idle'`, `'scouting'`, `'moving'`
  - Fumigator: `'idle'`, `'moving'`, `'fumigating'`, `'refilling'`, `'returning_to_barn'`
- **`path`**: Array de posiciones futuras del agente
- **`infestation_grid`**: Grid 2D con niveles de infestación (0-100). **`null`** para celdas no reveladas

**Acción en Unity:**
1. Actualizar posición de cada agente
2. Actualizar animaciones según `status`
3. Renderizar grid de infestación
4. Mostrar tareas como markers en el mapa
5. Actualizar UI con estadísticas

---

### 3. Agent Update (Actualización de Agente Individual)

**Cuándo:** Cuando un agente cambia de estado o posición

```json
{
  "type": "agent_update",
  "agent": {
    "agent_id": "fumigator_2",
    "agent_type": "fumigator",
    "position": [15, 8],
    "status": "moving",
    "pesticide_level": 920
  }
}
```

**Acción en Unity:** Actualizar solo ese agente específico

---

### 4. Agent Command (Comando para Agente)

**Cuándo:** Backend envía comando a agente para animación/acción

```json
{
  "type": "agent_command",
  "timestamp": "ISO8601",
  "version": "2.0",
  "agent_id": "fumigator_1",
  "command": "move",
  "command_id": "cmd_12345",
  "parameters": {
    "from_position": [5, 5],
    "to_position": [6, 5],
    "fumigate_on_path": true,
    "fumigation_data": {
      "infestation_level": 45,
      "pesticide_needed": 45,
      "position": [6, 5],
      "task_id": "task_456",
      "opportunistic": true
    }
  }
}
```

**Comandos Posibles:**

**a) Move (Movimiento)**
```json
{
  "command": "move",
  "parameters": {
    "from_position": [x1, z1],
    "to_position": [x2, z2],
    "reveal_infestation": true,  // Si es scout
    "fumigate_on_path": true     // Si es fumigator y hay tarea
  }
}
```

**b) Fumigate (Fumigación)**
```json
{
  "command": "fumigate",
  "parameters": {
    "position": [x, z],
    "infestation_level": 75,
    "required_pesticide": 75
  }
}
```

**c) Scan (Escaneo - Solo Scout)**
```json
{
  "command": "scan",
  "parameters": {
    "position": [x, z],
    "radius": 1  // Radio 3x3
  }
}
```

**d) Refill (Reabastecer - Solo Fumigator)**
```json
{
  "command": "refill",
  "parameters": {
    "position": [x, z],  // Posición del granero
    "amount": 1000
  }
}
```

**Acción en Unity:**
1. Ejecutar animación del comando
2. Mover agente en Unity
3. Renderizar efectos visuales (spray, scan pulse, etc.)
4. **IMPORTANTE:** Enviar confirmación al backend cuando se complete

---

### 5. Task Update (Actualización de Tarea)

**Cuándo:** Cuando una tarea cambia de estado

```json
{
  "type": "task_update",
  "task": {
    "task_id": "task_789",
    "position": [12, 15],
    "infestation_level": 60,
    "priority": "high",
    "status": "completed",
    "assigned_agent_id": "fumigator_3"
  }
}
```

**Acción en Unity:** Actualizar marker de tarea, eliminar si está completed

---

### 6. Simulation Completed (Simulación Terminada)

**Cuándo:** La simulación ha finalizado

```json
{
  "type": "simulation_completed",
  "timestamp": "ISO8601",
  "version": "2.0",
  "simulation_id": "uuid",
  "total_steps": 250,
  "statistics": {
    "total_tasks": 50,
    "completed_tasks": 50,
    "total_fields_fumigated": 50,
    "total_fields_analyzed": 200,
    "coverage_percentage": 100.0,
    "final_infestation": 0
  },
  "results": {
    "success": true,
    "duration_seconds": 125.5,
    "efficiency_score": 95.2
  }
}
```

**Acción en Unity:** Mostrar pantalla de resultados, detener simulación

---

### 7. Simulation Error (Error de Simulación)

**Cuándo:** Ocurre un error en la simulación

```json
{
  "type": "simulation_error",
  "timestamp": "ISO8601",
  "version": "2.0",
  "error": "Agent pathfinding failed",
  "details": {
    "agent_id": "fumigator_2",
    "position": [5, 5],
    "target": [100, 100]
  }
}
```

**Acción en Unity:** Mostrar error en UI, pausar/detener simulación

---

### 8. Pong (Respuesta a Ping)

**Cuándo:** Unity envía ping, backend responde

```json
{
  "type": "pong",
  "timestamp": "2025-12-01T10:30:05.000Z",
  "version": "2.0"
}
```

**Acción en Unity:** Confirmar que conexión está viva

---

## 📤 Mensajes que Unity ENVÍA al Backend

### 1. Ping (Keep-Alive)

**Cuándo:** Cada 30 segundos para mantener conexión viva

```json
{
  "type": "ping",
  "timestamp": "2025-12-01T10:30:05.000Z"
}
```

**Código C#:**
```csharp
void SendPing() {
    var ping = new {
        type = "ping",
        timestamp = DateTime.UtcNow.ToString("o")
    };
    ws.Send(JsonUtility.ToJson(ping));
}
```

---

### 2. Get Status (Solicitar Estado)

**Cuándo:** Unity necesita el estado actual de la simulación

```json
{
  "type": "get_status"
}
```

**Respuesta:** Backend envía `step_update` con estado actual

---

### 3. Command Confirmation (Confirmación de Comando)

**Cuándo:** Unity completó la ejecución de un comando

**CRÍTICO:** Backend espera estas confirmaciones para sincronización

```json
{
  "type": "command_confirmation",
  "agent_id": "fumigator_1",
  "command_id": "cmd_12345",
  "success": true
}
```

**Código C#:**
```csharp
void ConfirmCommand(string agentId, string commandId, bool success) {
    var confirmation = new {
        type = "command_confirmation",
        agent_id = agentId,
        command_id = commandId,
        success = success
    };
    ws.Send(JsonUtility.ToJson(confirmation));
}
```

**Flujo:**
1. Unity recibe `agent_command`
2. Unity ejecuta animación/movimiento
3. Cuando termina, Unity envía `command_confirmation`
4. Backend continúa con siguiente comando

---

## 🎮 Implementación en Unity

### Ejemplo Completo en C#

```csharp
using UnityEngine;
using WebSocketSharp;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

public class SimulationClient : MonoBehaviour
{
    private WebSocket ws;
    private string simulationId = "your-simulation-id";

    void Start() {
        ConnectToSimulation();
    }

    void ConnectToSimulation() {
        string wsUrl = $"ws://localhost:8000/ws/simulations/{simulationId}/";
        ws = new WebSocket(wsUrl);

        ws.OnOpen += (sender, e) => {
            Debug.Log("Connected to simulation");
        };

        ws.OnMessage += (sender, e) => {
            HandleMessage(e.Data);
        };

        ws.OnError += (sender, e) => {
            Debug.LogError($"WebSocket Error: {e.Message}");
        };

        ws.OnClose += (sender, e) => {
            Debug.Log("Disconnected from simulation");
        };

        ws.Connect();
    }

    void HandleMessage(string jsonData) {
        JObject msg = JObject.Parse(jsonData);
        string msgType = msg["type"].ToString();

        switch (msgType) {
            case "connection":
                OnConnection(msg);
                break;

            case "step_update":
                OnStepUpdate(msg);
                break;

            case "agent_command":
                OnAgentCommand(msg);
                break;

            case "simulation_completed":
                OnSimulationCompleted(msg);
                break;

            case "simulation_error":
                OnSimulationError(msg);
                break;

            case "pong":
                OnPong(msg);
                break;

            default:
                Debug.LogWarning($"Unknown message type: {msgType}");
                break;
        }
    }

    void OnConnection(JObject msg) {
        Debug.Log($"Connected to simulation: {msg["simulation_id"]}");
        // Inicializar escena, cargar mundo, etc.
    }

    void OnStepUpdate(JObject msg) {
        int step = msg["step"].ToObject<int>();
        JArray agents = (JArray)msg["agents"];
        JArray tasks = (JArray)msg["tasks"];
        JObject stats = (JObject)msg["statistics"];

        // Actualizar cada agente
        foreach (var agent in agents) {
            UpdateAgent(agent.ToObject<JObject>());
        }

        // Actualizar tareas
        foreach (var task in tasks) {
            UpdateTask(task.ToObject<JObject>());
        }

        // Actualizar UI con estadísticas
        UpdateStatistics(stats);
    }

    void OnAgentCommand(JObject msg) {
        string agentId = msg["agent_id"].ToString();
        string command = msg["command"].ToString();
        string commandId = msg["command_id"].ToString();
        JObject parameters = (JObject)msg["parameters"];

        // Ejecutar comando en Unity
        StartCoroutine(ExecuteCommand(agentId, command, commandId, parameters));
    }

    IEnumerator ExecuteCommand(string agentId, string command, string commandId, JObject parameters) {
        // Obtener GameObject del agente
        GameObject agentObj = GetAgentGameObject(agentId);

        if (command == "move") {
            Vector2Int from = ParsePosition(parameters["from_position"]);
            Vector2Int to = ParsePosition(parameters["to_position"]);

            // Animar movimiento
            yield return StartCoroutine(AnimateMove(agentObj, from, to));

            // Si debe fumigar en el camino
            if (parameters["fumigate_on_path"]?.ToObject<bool>() == true) {
                // Mostrar efecto de fumigación
                ShowFumigationEffect(agentObj, to);
            }
        }
        else if (command == "fumigate") {
            Vector2Int pos = ParsePosition(parameters["position"]);
            int infestationLevel = parameters["infestation_level"].ToObject<int>();

            // Animar fumigación
            yield return StartCoroutine(AnimateFumigate(agentObj, pos, infestationLevel));
        }
        else if (command == "scan") {
            Vector2Int pos = ParsePosition(parameters["position"]);
            int radius = parameters["radius"].ToObject<int>();

            // Animar escaneo
            yield return StartCoroutine(AnimateScan(agentObj, pos, radius));
        }

        // IMPORTANTE: Confirmar comando completado
        SendCommandConfirmation(agentId, commandId, true);
    }

    void SendCommandConfirmation(string agentId, string commandId, bool success) {
        var confirmation = new {
            type = "command_confirmation",
            agent_id = agentId,
            command_id = commandId,
            success = success
        };
        ws.Send(JsonConvert.SerializeObject(confirmation));
    }

    void UpdateAgent(JObject agentData) {
        string agentId = agentData["agent_id"].ToString();
        Vector2Int position = ParsePosition(agentData["position"]);
        string status = agentData["status"].ToString();

        GameObject agentObj = GetAgentGameObject(agentId);
        if (agentObj == null) {
            // Crear nuevo agente si no existe
            agentObj = CreateAgent(agentData);
        }

        // Actualizar posición
        agentObj.transform.position = new Vector3(position.x, 0, position.y);

        // Actualizar animación según status
        Animator animator = agentObj.GetComponent<Animator>();
        switch (status) {
            case "moving":
                animator.SetBool("IsMoving", true);
                break;
            case "fumigating":
                animator.SetTrigger("Fumigate");
                break;
            case "scouting":
                animator.SetBool("IsScanning", true);
                break;
            case "idle":
                animator.SetBool("IsMoving", false);
                animator.SetBool("IsScanning", false);
                break;
        }
    }

    Vector2Int ParsePosition(JToken posToken) {
        JArray pos = (JArray)posToken;
        return new Vector2Int(pos[0].ToObject<int>(), pos[1].ToObject<int>());
    }

    void OnDestroy() {
        if (ws != null && ws.IsAlive) {
            ws.Close();
        }
    }
}
```

---

## 🔄 Flujo Completo de Comunicación

### Inicio de Simulación

```
1. Unity → Backend: WebSocket Connect
2. Backend → Unity: connection message
3. Unity: Inicializar escena
4. Unity → Backend: get_status (opcional)
5. Backend → Unity: step_update (estado inicial)
```

### Durante la Simulación

```
Loop (cada 0.5s):
  1. Backend ejecuta paso de simulación
  2. Backend → Unity: step_update
  3. Unity actualiza agentes, tareas, UI

  Si hay comando para agente:
    4. Backend → Unity: agent_command
    5. Unity ejecuta animación
    6. Unity → Backend: command_confirmation
```

### Finalización

```
1. Backend completa simulación
2. Backend → Unity: simulation_completed
3. Unity muestra resultados
4. Unity puede cerrar WebSocket
```

---

## 📊 Tipos de Datos

### AgentType
- `"scout"`: Dron explorador
- `"fumigator"`: Tractor fumigador

### AgentStatus
- `"idle"`: Inactivo, esperando comando
- `"moving"`: Moviéndose a una posición
- `"scouting"`: Escaneando área (scout)
- `"fumigating"`: Fumigando (fumigator)
- `"refilling"`: Reabasteciendo pesticida (fumigator)
- `"returning_to_barn"`: Regresando al granero (fumigator)

### TaskStatus
- `"pending"`: Tarea pendiente
- `"assigned"`: Tarea asignada a agente
- `"in_progress"`: En ejecución
- `"completed"`: Completada
- `"failed"`: Fallida

### TaskPriority
- `"low"`: Baja prioridad
- `"medium"`: Media prioridad
- `"high"`: Alta prioridad
- `"critical"`: Crítica

---

## 🚨 Consideraciones Importantes

### 1. Sincronización
- Backend espera `command_confirmation` antes de enviar siguiente comando
- Si Unity no confirma, puede haber desfase temporal
- **Siempre confirmar comandos**

### 2. Coordenadas
- `position` es `[x, z]` (2D grid)
- En Unity 3D: `new Vector3(x, y_altura, z)`
- El eje Y es la altura (terreno)

### 3. Infestation Grid
- `null` = celda no revelada (fog of war)
- `0` = sin infestación (revelada)
- `1-100` = nivel de infestación porcentual

### 4. Path Planning
- `path` array puede estar vacío si agente está idle
- Usar para preview de ruta en Unity (línea punteada, etc.)

### 5. Keep-Alive
- Enviar `ping` cada 30 segundos
- Backend cierra conexión después de 60s sin actividad

---

## 🐛 Debugging

### Verificar Mensajes
```csharp
void OnMessage(object sender, MessageEventArgs e) {
    Debug.Log($"Received: {e.Data}");
    // ... resto del código
}
```

### Logs Esperados en Backend
```
🔍 Scout X: Moviendo a posición (0, 0) en patrón zigzag
🔍 Scout X: Llegó a (0, 0), revelando área, volviendo a idle
🐛 Scout X: Descubrió infestación 45% en (5, 2)
🎯 Fumigator Y: Fumigación oportunista en (8, 10) - Tarea task_123 completada
🎯 Scout exploration complete! Coverage: 100.0%
```

### Errores Comunes
- **"WebSocket closed"**: Verificar que backend esté corriendo
- **"Simulation not found"**: `simulation_id` incorrecto
- **"No step_update"**: Simulación no iniciada o pausada
- **Agentes no se mueven**: Falta `command_confirmation`

---

## 📝 Resumen

**Frontend React y Unity usan EXACTAMENTE el mismo protocolo:**

✅ Mismo WebSocket endpoint
✅ Mismos mensajes JSON
✅ Mismo formato de datos
✅ Misma lógica de confirmaciones
✅ Unity Protocol v2.0

**Unity solo necesita:**
1. Conectarse al WebSocket
2. Parsear JSON
3. Renderizar agentes/tareas/grid
4. Confirmar comandos
5. Mostrar resultados

¡El backend ya está listo para Unity! 🎮
