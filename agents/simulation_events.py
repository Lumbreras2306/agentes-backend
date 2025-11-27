"""
Sistema de eventos granulares para simulación en tiempo real.
Compatible con frontend 2D y Unity 3D.
"""
from typing import Dict, Any, List, Tuple, Optional
from enum import Enum
from dataclasses import dataclass, asdict
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


class EventType(str, Enum):
    """Tipos de eventos que pueden ocurrir en la simulación"""

    # Eventos de simulación
    SIMULATION_INITIALIZED = "simulation_initialized"
    SIMULATION_STEP = "simulation_step"
    SIMULATION_COMPLETED = "simulation_completed"
    SIMULATION_ERROR = "simulation_error"

    # Eventos de agente general
    AGENT_SPAWNED = "agent_spawned"
    AGENT_MOVED = "agent_moved"
    AGENT_IDLE = "agent_idle"
    AGENT_STATUS_CHANGED = "agent_status_changed"

    # Eventos de scout
    SCOUT_ANALYZING = "scout_analyzing"
    INFESTATION_DISCOVERED = "infestation_discovered"
    SCOUT_REVEAL_AREA = "scout_reveal_area"

    # Eventos de fumigador
    FUMIGATION_STARTED = "fumigation_started"
    FUMIGATION_PROGRESS = "fumigation_progress"
    FUMIGATION_COMPLETED = "fumigation_completed"
    AGENT_REFILLING = "agent_refilling"
    AGENT_REFILL_COMPLETED = "agent_refill_completed"
    PESTICIDE_LOW = "pesticide_low"

    # Eventos de tareas
    TASK_CREATED = "task_created"
    TASK_ASSIGNED = "task_assigned"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"

    # Eventos de mundo
    INFESTATION_CHANGED = "infestation_changed"


@dataclass
class SimulationEvent:
    """Clase base para eventos de simulación"""
    event_type: EventType
    simulation_id: str
    step: int
    timestamp: float
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el evento a diccionario para enviar por WebSocket"""
        return {
            'type': self.event_type.value,
            'simulation_id': self.simulation_id,
            'step': self.step,
            'timestamp': self.timestamp,
            **self.data
        }


class EventEmitter:
    """
    Emisor de eventos para la simulación.
    Envía eventos granulares en tiempo real a través de WebSocket.
    """

    def __init__(self, simulation_id: str):
        self.simulation_id = simulation_id
        self.current_step = 0
        self.channel_layer = get_channel_layer()

    def _emit(self, event_type: EventType, data: Dict[str, Any]):
        """Emite un evento a través del WebSocket"""
        if not self.channel_layer:
            return

        try:
            import time
            event = SimulationEvent(
                event_type=event_type,
                simulation_id=self.simulation_id,
                step=self.current_step,
                timestamp=time.time(),
                data=data
            )

            async_to_sync(self.channel_layer.group_send)(
                f'simulation_{self.simulation_id}',
                {
                    'type': 'simulation_event',
                    'event_data': event.to_dict()
                }
            )
        except Exception as e:
            print(f"Error emitiendo evento {event_type}: {e}")

    # ========== Eventos de Simulación ==========

    def emit_simulation_initialized(
        self,
        num_fumigators: int,
        num_scouts: int,
        world_size: Tuple[int, int],
        agents: List[Dict[str, Any]]
    ):
        """Emite evento de simulación inicializada"""
        self._emit(EventType.SIMULATION_INITIALIZED, {
            'num_fumigators': num_fumigators,
            'num_scouts': num_scouts,
            'world_size': list(world_size),
            'agents': agents,
            'message': f'Simulación iniciada con {num_fumigators} fumigadores y {num_scouts} scouts'
        })

    def emit_simulation_step(
        self,
        agents: List[Dict[str, Any]],
        tasks: List[Dict[str, Any]],
        statistics: Dict[str, Any]
    ):
        """Emite evento de paso de simulación (resumen del estado)"""
        self._emit(EventType.SIMULATION_STEP, {
            'agents': agents,
            'tasks': tasks,
            'statistics': statistics
        })

    def emit_simulation_completed(
        self,
        results: Dict[str, Any]
    ):
        """Emite evento de simulación completada"""
        self._emit(EventType.SIMULATION_COMPLETED, {
            'results': results,
            'message': 'Simulación completada exitosamente'
        })

    def emit_simulation_error(self, error_message: str):
        """Emite evento de error en la simulación"""
        self._emit(EventType.SIMULATION_ERROR, {
            'error': error_message
        })

    # ========== Eventos de Agente General ==========

    def emit_agent_spawned(
        self,
        agent_id: str,
        agent_type: str,
        position: Tuple[int, int]
    ):
        """Emite evento de agente creado"""
        self._emit(EventType.AGENT_SPAWNED, {
            'agent_id': agent_id,
            'agent_type': agent_type,
            'position': list(position)
        })

    def emit_agent_moved(
        self,
        agent_id: str,
        agent_type: str,
        from_position: Tuple[int, int],
        to_position: Tuple[int, int],
        path: Optional[List[Tuple[int, int]]] = None
    ):
        """Emite evento de agente movido"""
        self._emit(EventType.AGENT_MOVED, {
            'agent_id': agent_id,
            'agent_type': agent_type,
            'from_position': list(from_position),
            'to_position': list(to_position),
            'path': [list(p) for p in path] if path else None
        })

    def emit_agent_idle(self, agent_id: str, agent_type: str, position: Tuple[int, int]):
        """Emite evento de agente en espera"""
        self._emit(EventType.AGENT_IDLE, {
            'agent_id': agent_id,
            'agent_type': agent_type,
            'position': list(position)
        })

    def emit_agent_status_changed(
        self,
        agent_id: str,
        agent_type: str,
        old_status: str,
        new_status: str,
        position: Tuple[int, int]
    ):
        """Emite evento de cambio de estado de agente"""
        self._emit(EventType.AGENT_STATUS_CHANGED, {
            'agent_id': agent_id,
            'agent_type': agent_type,
            'old_status': old_status,
            'new_status': new_status,
            'position': list(position)
        })

    # ========== Eventos de Scout ==========

    def emit_scout_analyzing(
        self,
        agent_id: str,
        position: Tuple[int, int],
        area_size: Tuple[int, int]
    ):
        """Emite evento de scout analizando área"""
        self._emit(EventType.SCOUT_ANALYZING, {
            'agent_id': agent_id,
            'position': list(position),
            'area_size': list(area_size)
        })

    def emit_infestation_discovered(
        self,
        agent_id: str,
        position: Tuple[int, int],
        infestation_level: int,
        task_id: Optional[str] = None
    ):
        """Emite evento de infestación descubierta"""
        self._emit(EventType.INFESTATION_DISCOVERED, {
            'agent_id': agent_id,
            'position': list(position),
            'infestation_level': infestation_level,
            'task_id': task_id
        })

    def emit_scout_reveal_area(
        self,
        agent_id: str,
        revealed_positions: List[Tuple[int, int]],
        infestation_data: List[Dict[str, Any]]
    ):
        """Emite evento de área revelada por scout"""
        self._emit(EventType.SCOUT_REVEAL_AREA, {
            'agent_id': agent_id,
            'revealed_positions': [list(p) for p in revealed_positions],
            'infestation_data': infestation_data
        })

    # ========== Eventos de Fumigador ==========

    def emit_fumigation_started(
        self,
        agent_id: str,
        position: Tuple[int, int],
        infestation_level: int,
        task_id: Optional[str] = None
    ):
        """Emite evento de fumigación iniciada"""
        self._emit(EventType.FUMIGATION_STARTED, {
            'agent_id': agent_id,
            'position': list(position),
            'infestation_level': infestation_level,
            'task_id': task_id
        })

    def emit_fumigation_progress(
        self,
        agent_id: str,
        position: Tuple[int, int],
        progress: float,
        remaining_infestation: int
    ):
        """Emite evento de progreso de fumigación"""
        self._emit(EventType.FUMIGATION_PROGRESS, {
            'agent_id': agent_id,
            'position': list(position),
            'progress': progress,
            'remaining_infestation': remaining_infestation
        })

    def emit_fumigation_completed(
        self,
        agent_id: str,
        position: Tuple[int, int],
        pesticide_used: int,
        task_id: Optional[str] = None
    ):
        """Emite evento de fumigación completada"""
        self._emit(EventType.FUMIGATION_COMPLETED, {
            'agent_id': agent_id,
            'position': list(position),
            'pesticide_used': pesticide_used,
            'task_id': task_id
        })

    def emit_agent_refilling(
        self,
        agent_id: str,
        position: Tuple[int, int],
        current_pesticide: int,
        capacity: int
    ):
        """Emite evento de agente rellenando pesticida"""
        self._emit(EventType.AGENT_REFILLING, {
            'agent_id': agent_id,
            'position': list(position),
            'current_pesticide': current_pesticide,
            'capacity': capacity
        })

    def emit_agent_refill_completed(
        self,
        agent_id: str,
        position: Tuple[int, int],
        pesticide_level: int
    ):
        """Emite evento de recarga completada"""
        self._emit(EventType.AGENT_REFILL_COMPLETED, {
            'agent_id': agent_id,
            'position': list(position),
            'pesticide_level': pesticide_level
        })

    def emit_pesticide_low(
        self,
        agent_id: str,
        position: Tuple[int, int],
        pesticide_level: int,
        capacity: int
    ):
        """Emite evento de pesticida bajo"""
        self._emit(EventType.PESTICIDE_LOW, {
            'agent_id': agent_id,
            'position': list(position),
            'pesticide_level': pesticide_level,
            'capacity': capacity,
            'percentage': (pesticide_level / capacity * 100) if capacity > 0 else 0
        })

    # ========== Eventos de Tareas ==========

    def emit_task_created(
        self,
        task_id: str,
        position: Tuple[int, int],
        infestation_level: int,
        priority: str,
        discovered_by: Optional[str] = None
    ):
        """Emite evento de tarea creada"""
        self._emit(EventType.TASK_CREATED, {
            'task_id': task_id,
            'position': list(position),
            'infestation_level': infestation_level,
            'priority': priority,
            'discovered_by': discovered_by
        })

    def emit_task_assigned(
        self,
        task_id: str,
        agent_id: str,
        position: Tuple[int, int],
        infestation_level: int
    ):
        """Emite evento de tarea asignada"""
        self._emit(EventType.TASK_ASSIGNED, {
            'task_id': task_id,
            'agent_id': agent_id,
            'position': list(position),
            'infestation_level': infestation_level
        })

    def emit_task_started(
        self,
        task_id: str,
        agent_id: str,
        position: Tuple[int, int]
    ):
        """Emite evento de tarea iniciada"""
        self._emit(EventType.TASK_STARTED, {
            'task_id': task_id,
            'agent_id': agent_id,
            'position': list(position)
        })

    def emit_task_completed(
        self,
        task_id: str,
        agent_id: str,
        position: Tuple[int, int],
        completion_time: float
    ):
        """Emite evento de tarea completada"""
        self._emit(EventType.TASK_COMPLETED, {
            'task_id': task_id,
            'agent_id': agent_id,
            'position': list(position),
            'completion_time': completion_time
        })

    def emit_task_failed(
        self,
        task_id: str,
        agent_id: Optional[str],
        position: Tuple[int, int],
        reason: str
    ):
        """Emite evento de tarea fallida"""
        self._emit(EventType.TASK_FAILED, {
            'task_id': task_id,
            'agent_id': agent_id,
            'position': list(position),
            'reason': reason
        })

    # ========== Eventos de Mundo ==========

    def emit_infestation_changed(
        self,
        position: Tuple[int, int],
        old_level: int,
        new_level: int
    ):
        """Emite evento de cambio en nivel de infestación"""
        self._emit(EventType.INFESTATION_CHANGED, {
            'position': list(position),
            'old_level': old_level,
            'new_level': new_level
        })

    def set_current_step(self, step: int):
        """Actualiza el paso actual de la simulación"""
        self.current_step = step
