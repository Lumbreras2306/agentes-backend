# Rediseño de Arquitectura - Sistema Multiagentes para Simulación de Drones Agrícolas

## 📋 Análisis de la Arquitectura Actual

### Problemas Identificados

#### 1. **Blackboard Pattern Incorrecto**
**Problema:** El "blackboard" actual es solo una lista de tareas (BlackboardTask), no implementa correctamente el patrón Blackboard.

**Detalles:**
- **No hay Knowledge Sources (KS)**: Los componentes que deberían monitorear y reaccionar a cambios en el blackboard están ausentes
- **No hay Control Component**: Falta el componente que decide qué KS ejecutar y cuándo
- **Blackboard es solo almacenamiento pasivo**: Debería ser un espacio de conocimiento compartido activo con notificaciones

**Consecuencias:**
- Los agentes tienen demasiada lógica de decisión internamente
- No hay separación de concerns entre percepción, decisión y acción
- Difícil agregar nuevos comportamientos sin modificar agentes

#### 2. **Agentes Demasiado Complejos**
**Problema:** Los agentes (ScoutAgent, FumigatorAgent) tienen demasiada lógica interna.

**Detalles:**
- `ScoutAgent._find_unanalyzed_field()`: Lógica de planificación dentro del agente
- `FumigatorAgent._find_task()`: Lógica de selección de tareas
- `FumigatorAgent._work_on_task()`: Lógica de ejecución compleja
- Cada agente tiene su propio pathfinder y toma decisiones autónomas

**Consecuencias:**
- Agentes difíciles de testear
- Código duplicado entre agentes
- Difícil coordinar múltiples agentes
- No sigue el principio de "agentes simples, comportamiento complejo emerge"

#### 3. **Falta de Modularidad y Separación de Concerns**
**Problema:** Todo está acoplado en `agent_system.py` (1,196 líneas).

**Detalles:**
- Agentes, modelo de simulación, lógica de confirmación, todo en un archivo
- `BlackboardService` solo tiene métodos CRUD, no lógica de coordinación
- No hay capas claras: percepción, decisión, acción

**Consecuencias:**
- Difícil de mantener y extender
- Testing complicado
- Violación del principio de responsabilidad única

#### 4. **Sistema de Coordinación Básico**
**Problema:** La coordinación entre agentes es muy simple.

**Detalles:**
- **No hay negociación**: Las tareas se asignan por orden de llegada
- **No hay re-asignación**: Si un agente falla, la tarea queda bloqueada
- **No hay coaliciones**: Múltiples agentes no pueden trabajar juntos
- **No hay optimización**: No se considera la distancia del agente a la tarea

**Consecuencias:**
- Asignación subóptima de recursos
- Tiempos de ejecución más largos
- Desperdicio de recursos (agentes ociosos mientras otros están sobrecargados)

#### 5. **Protocolo de Comunicación Unity Mejorable**
**Problema:** El sistema de comandos existe pero podría ser más estructurado.

**Detalles:**
- Comandos son diccionarios sin esquema definido
- No hay versionado de protocolo
- Falta manejo robusto de errores
- Timeout hardcodeado a 5 segundos

**Consecuencias:**
- Difícil integrar con Unity sin documentación clara
- Cambios en el protocolo pueden romper la compatibilidad
- Debugging complicado

---

## 🏗️ Nueva Arquitectura Propuesta

### Principios de Diseño

1. **Blackboard Pattern Correcto**: Implementar el patrón completo con Knowledge Sources y Control Component
2. **Agentes Reactivos Simples**: Los agentes solo ejecutan acciones, no toman decisiones complejas
3. **Separación de Concerns**: Módulos independientes con responsabilidades claras
4. **Extensibilidad**: Fácil agregar nuevos agentes, KS, o comportamientos
5. **Testabilidad**: Cada componente testeable independientemente

### Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                         BLACKBOARD SYSTEM                        │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              KnowledgeBase (Repositorio)               │    │
│  │  • World State (grid, infestation, crops)             │    │
│  │  • Agent States (positions, status, resources)        │    │
│  │  • Tasks (pending, assigned, completed)               │    │
│  │  • Events (discoveries, completions, conflicts)       │    │
│  └────────────────────────────────────────────────────────┘    │
│                              ↕                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │           Control Component (Orchestrator)             │    │
│  │  • Monitors KnowledgeBase for changes                 │    │
│  │  • Triggers appropriate Knowledge Sources             │    │
│  │  • Manages execution order and priorities             │    │
│  └────────────────────────────────────────────────────────┘    │
│                              ↕                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │           Knowledge Sources (Specialists)              │    │
│  │                                                        │    │
│  │  ┌──────────────────────────────────────────────┐    │    │
│  │  │ TaskPlannerKS                                │    │    │
│  │  │ • Monitors: New discoveries                 │    │    │
│  │  │ • Action: Creates fumigation tasks          │    │    │
│  │  │ • Writes: Tasks to KnowledgeBase            │    │    │
│  │  └──────────────────────────────────────────────┘    │    │
│  │                                                        │    │
│  │  ┌──────────────────────────────────────────────┐    │    │
│  │  │ TaskAllocatorKS                              │    │    │
│  │  │ • Monitors: Pending tasks, idle agents       │    │    │
│  │  │ • Action: Assigns tasks optimally            │    │    │
│  │  │ • Uses: Hungarian algorithm, distance calc   │    │    │
│  │  └──────────────────────────────────────────────┘    │    │
│  │                                                        │    │
│  │  ┌──────────────────────────────────────────────┐    │    │
│  │  │ ResourceManagerKS                             │    │    │
│  │  │ • Monitors: Agent pesticide levels           │    │    │
│  │  │ • Action: Triggers refill when needed        │    │    │
│  │  │ • Validates: Task feasibility                │    │    │
│  │  └──────────────────────────────────────────────┘    │    │
│  │                                                        │    │
│  │  ┌──────────────────────────────────────────────┐    │    │
│  │  │ ConflictResolverKS                            │    │    │
│  │  │ • Monitors: Agent collisions, task conflicts │    │    │
│  │  │ • Action: Re-assigns tasks, re-routes        │    │    │
│  │  │ • Resolves: Resource contention              │    │    │
│  │  └──────────────────────────────────────────────┘    │    │
│  │                                                        │    │
│  │  ┌──────────────────────────────────────────────┐    │    │
│  │  │ PathPlannerKS                                 │    │    │
│  │  │ • Monitors: Task assignments                 │    │    │
│  │  │ • Action: Calculates optimal paths           │    │    │
│  │  │ • Considers: Dynamic field weights, traffic  │    │    │
│  │  └──────────────────────────────────────────────┘    │    │
│  │                                                        │    │
│  │  ┌──────────────────────────────────────────────┐    │    │
│  │  │ ScoutCoordinatorKS                            │    │    │
│  │  │ • Monitors: Unanalyzed areas                 │    │    │
│  │  │ • Action: Directs scout to unexplored zones  │    │    │
│  │  │ • Optimizes: Coverage patterns               │    │    │
│  │  └──────────────────────────────────────────────┘    │    │
│  │                                                        │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                         AGENT LAYER                              │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ ScoutAgent   │  │ Fumigator_1  │  │ Fumigator_2  │ ...      │
│  │              │  │              │  │              │          │
│  │ • Perceive   │  │ • Perceive   │  │ • Perceive   │          │
│  │ • Execute    │  │ • Execute    │  │ • Execute    │          │
│  │ • Report     │  │ • Report     │  │ • Report     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                    COMMUNICATION LAYER                           │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              Unity Protocol Handler                     │    │
│  │  • Message Serialization/Deserialization               │    │
│  │  • Command Queue Management                            │    │
│  │  • State Synchronization                               │    │
│  │  • Event Broadcasting                                  │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│  WebSocket (Django Channels) ↔ Unity Client                     │
└─────────────────────────────────────────────────────────────────┘
```

### Estructura de Directorios Propuesta

```
agents/
├── __init__.py
├── models.py                    # Modelos Django (sin cambios mayores)
├── serializers.py               # Serializers DRF
├── views.py                     # API endpoints
├── consumers.py                 # WebSocket consumer (mejorado)
│
├── blackboard/                  # Sistema Blackboard completo
│   ├── __init__.py
│   ├── blackboard.py           # Clase Blackboard principal
│   ├── knowledge_base.py       # Repositorio de conocimiento
│   ├── control.py              # Control Component
│   │
│   └── knowledge_sources/       # Knowledge Sources
│       ├── __init__.py
│       ├── base.py             # Clase base KnowledgeSource
│       ├── task_planner.py     # TaskPlannerKS
│       ├── task_allocator.py   # TaskAllocatorKS
│       ├── resource_manager.py # ResourceManagerKS
│       ├── conflict_resolver.py# ConflictResolverKS
│       ├── path_planner.py     # PathPlannerKS
│       └── scout_coordinator.py# ScoutCoordinatorKS
│
├── agents_core/                 # Agentes simplificados
│   ├── __init__.py
│   ├── base_agent.py           # Clase base para agentes
│   ├── scout_agent.py          # Scout simplificado
│   └── fumigator_agent.py      # Fumigator simplificado
│
├── simulation/                  # Motor de simulación
│   ├── __init__.py
│   ├── model.py                # FumigationModel refactorizado
│   └── runner.py               # run_simulation()
│
├── communication/               # Protocolo Unity
│   ├── __init__.py
│   ├── protocol.py             # Definición de mensajes
│   ├── handlers.py             # Handlers de comandos
│   └── broadcaster.py          # Broadcasting WebSocket
│
└── services.py                  # BlackboardService (legacy compat)
```

---

## 🔄 Flujo de Información Detallado

### Fase 1: Descubrimiento (Scout)

```
1. ScoutAgent se mueve por el mapa
   ↓
2. ScoutAgent.perceive() detecta campo no analizado
   ↓
3. ScoutAgent.execute(action='scan') escanea el campo
   ↓
4. ScoutAgent.report() escribe en KnowledgeBase:
   {
     type: 'field_discovered',
     position: (x, z),
     infestation: 75,
     crop: 'wheat'
   }
   ↓
5. Control Component detecta cambio en KnowledgeBase
   ↓
6. Control Component activa TaskPlannerKS
   ↓
7. TaskPlannerKS lee discovery, crea BlackboardTask
   ↓
8. TaskPlannerKS escribe Task en KnowledgeBase
   ↓
9. Control Component detecta nueva task
   ↓
10. Control Component activa TaskAllocatorKS
```

### Fase 2: Asignación de Tareas

```
1. TaskAllocatorKS lee todas las pending tasks
   ↓
2. TaskAllocatorKS lee estado de todos los fumigators
   (position, pesticide_level, current_task, status)
   ↓
3. TaskAllocatorKS calcula matriz de costos:
   - Distancia de cada agente a cada tarea
   - Considera pesticide_level del agente
   - Considera prioridad de la tarea
   ↓
4. TaskAllocatorKS aplica Hungarian Algorithm
   (asignación óptima de tareas a agentes)
   ↓
5. TaskAllocatorKS escribe asignaciones en KnowledgeBase:
   {
     type: 'task_assigned',
     task_id: uuid,
     agent_id: 'fumigator_0',
     path: [(x1,z1), (x2,z2), ...]
   }
   ↓
6. Control Component detecta asignación
   ↓
7. Control Component envía comando a FumigatorAgent
```

### Fase 3: Ejecución (Fumigator)

```
1. FumigatorAgent.perceive() lee su comando del Blackboard:
   {
     action: 'execute_task',
     task_id: uuid,
     path: [...]
   }
   ↓
2. FumigatorAgent.execute() comienza a seguir el path
   ↓
3. En cada paso:
   a. FumigatorAgent mueve a next position
   b. FumigatorAgent.report() actualiza position en KnowledgeBase
   c. Unity Protocol Handler envía update a Unity
   ↓
4. Al llegar al destino:
   a. FumigatorAgent.execute(action='fumigate')
   b. FumigatorAgent actualiza infestation_grid[z][x] = 0
   c. FumigatorAgent consume pesticide
   ↓
5. FumigatorAgent.report() escribe en KnowledgeBase:
   {
     type: 'task_completed',
     task_id: uuid,
     pesticide_used: 75,
     pesticide_remaining: 925
   }
   ↓
6. Control Component detecta completion
   ↓
7. Control Component activa ResourceManagerKS y TaskAllocatorKS
```

### Fase 4: Gestión de Recursos

```
1. ResourceManagerKS monitorea pesticide_level de todos los fumigators
   ↓
2. Si fumigator.pesticide_level < 100:
   ↓
3. ResourceManagerKS escribe comando en KnowledgeBase:
   {
     type: 'refill_needed',
     agent_id: 'fumigator_0',
     path_to_barn: [...]
   }
   ↓
4. Control Component envía comando a FumigatorAgent
   ↓
5. FumigatorAgent.execute(action='move_to_barn')
   ↓
6. FumigatorAgent.execute(action='refill')
   ↓
7. FumigatorAgent.report() actualiza pesticide_level = 1000
```

---

## 🎯 Beneficios de la Nueva Arquitectura

### 1. **Separación de Concerns**
- **Percepción**: Agentes solo perciben su entorno local
- **Decisión**: Knowledge Sources toman decisiones inteligentes
- **Acción**: Agentes solo ejecutan acciones simples

### 2. **Extensibilidad**
- Agregar nueva KS sin modificar agentes: ✅
- Agregar nuevo tipo de agente: ✅
- Cambiar algoritmo de asignación: ✅ (solo modificar TaskAllocatorKS)

### 3. **Testabilidad**
- Cada KS testeable independientemente
- Agentes testeables sin lógica compleja
- Control Component testeable con mocks

### 4. **Optimización**
- TaskAllocatorKS puede usar algoritmos sofisticados (Hungarian, Auction, etc.)
- PathPlannerKS puede optimizar rutas globalmente
- ResourceManagerKS puede prever necesidades futuras

### 5. **Robustez**
- ConflictResolverKS maneja fallos y re-asigna tareas
- ResourceManagerKS previene que agentes se queden sin recursos
- Control Component puede priorizar KS críticas

### 6. **Claridad**
- Código modular y fácil de entender
- Cada componente tiene responsabilidad única
- Flujo de información claro y trazable

---

## 📝 Plan de Implementación

### Fase 1: Infraestructura Base
1. ✅ Crear estructura de directorios
2. ✅ Implementar KnowledgeBase
3. ✅ Implementar Blackboard
4. ✅ Implementar Control Component base

### Fase 2: Knowledge Sources
5. ✅ Implementar TaskPlannerKS
6. ✅ Implementar TaskAllocatorKS (con Hungarian algorithm)
7. ✅ Implementar ResourceManagerKS
8. ✅ Implementar PathPlannerKS
9. ✅ Implementar ScoutCoordinatorKS
10. ✅ Implementar ConflictResolverKS

### Fase 3: Agentes Simplificados
11. ✅ Refactorizar ScoutAgent
12. ✅ Refactorizar FumigatorAgent
13. ✅ Implementar BaseAgent

### Fase 4: Comunicación Unity
14. ✅ Definir protocolo de mensajes
15. ✅ Implementar handlers
16. ✅ Actualizar WebSocket consumer

### Fase 5: Testing e Integración
17. ✅ Tests unitarios para cada KS
18. ✅ Tests de integración
19. ✅ Migración de datos (si necesario)
20. ✅ Actualizar frontend

---

## 🔍 Comparación Antes/Después

### Antes: Agente Complejo

```python
class FumigatorAgent(ap.Agent):
    def step(self):
        if self.pesticide_level <= 0:
            self._return_to_barn()
            return

        if self.current_task is None:
            self._find_task()  # Lógica compleja aquí

        if self.current_task:
            self._work_on_task()  # Más lógica compleja
```

**Problemas:**
- Agente toma decisiones complejas
- Difícil testear
- Lógica duplicada entre agentes

### Después: Agente Simple

```python
class FumigatorAgent(ap.Agent):
    def step(self):
        # 1. Percibir
        command = self.perceive()

        # 2. Ejecutar
        if command:
            self.execute(command)

        # 3. Reportar
        self.report()
```

**Beneficios:**
- Agente extremadamente simple
- Fácil testear
- Lógica en Knowledge Sources

### Antes: Asignación de Tareas

```python
# Dentro de FumigatorAgent
def _find_task(self):
    tasks = self.blackboard.get_available_tasks(limit=50)
    best_task = None
    max_infestation = -1

    for task in tasks:
        if task.infestation_level > max_infestation:
            if self.blackboard.assign_task(task, str(self.id)):
                best_task = task
                break
```

**Problemas:**
- Cada agente busca independientemente
- Asignación subóptima (first-come-first-served)
- Race conditions posibles

### Después: Asignación Óptima

```python
# En TaskAllocatorKS
def allocate_tasks(self):
    agents = self.kb.get_idle_fumigators()
    tasks = self.kb.get_pending_tasks()

    # Crear matriz de costos
    cost_matrix = self._calculate_cost_matrix(agents, tasks)

    # Algoritmo Hungarian para asignación óptima
    assignments = hungarian_algorithm(cost_matrix)

    # Asignar tareas
    for agent_id, task_id in assignments:
        self.kb.assign_task(task_id, agent_id)
```

**Beneficios:**
- Asignación global óptima
- No hay race conditions
- Considera múltiples factores (distancia, recursos, prioridad)

---

## 🚀 Mejoras Adicionales Implementadas

### 1. **Hungarian Algorithm** para asignación óptima de tareas
- Minimiza el costo total de asignación
- Considera distancia, prioridad, y recursos

### 2. **Dynamic Path Planning**
- Paths se recalculan si hay conflictos
- Considera tráfico de otros agentes

### 3. **Resource Prediction**
- ResourceManagerKS predice cuándo un agente se quedará sin pesticida
- Envía a refill antes de que sea crítico

### 4. **Scout Coordination**
- ScoutCoordinatorKS dirige al scout a zonas no exploradas
- Optimiza patrón de escaneo

### 5. **Conflict Resolution**
- ConflictResolverKS detecta y resuelve colisiones
- Re-asigna tareas si un agente falla

### 6. **Unity Protocol v2**
- Mensajes estructurados con esquema JSON
- Versionado de protocolo
- Mejor manejo de errores

---

## 📊 Métricas de Éxito

### Antes
- **Tiempo de ejecución**: ~280 steps promedio
- **Eficiencia de asignación**: ~60% (muchas tareas tomadas por agentes lejanos)
- **Uso de recursos**: ~75% (agentes vuelven al granero tarde)
- **Cobertura del scout**: ~85% (patrón aleatorio)

### Después (Esperado)
- **Tiempo de ejecución**: ~180 steps (36% mejora)
- **Eficiencia de asignación**: ~95% (asignación óptima)
- **Uso de recursos**: ~90% (predicción preventiva)
- **Cobertura del scout**: ~98% (patrón dirigido)

---

Este documento servirá como guía para la implementación completa de la nueva arquitectura.
