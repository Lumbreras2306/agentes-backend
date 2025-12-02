"""
KnowledgeBase - Central repository of shared knowledge in the Blackboard system

The KnowledgeBase stores all shared information that Knowledge Sources
and agents need to access. It provides a clean API for reading and writing
different types of knowledge.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import threading


class EventType(Enum):
    """Types of events that can occur in the system"""
    FIELD_DISCOVERED = "field_discovered"
    TASK_CREATED = "task_created"
    TASK_ASSIGNED = "task_assigned"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    AGENT_MOVED = "agent_moved"
    AGENT_IDLE = "agent_idle"
    AGENT_LOW_RESOURCE = "agent_low_resource"
    AGENT_REFILLED = "agent_refilled"
    CONFLICT_DETECTED = "conflict_detected"
    PATH_CALCULATED = "path_calculated"
    SCOUT_EXPLORATION_COMPLETE = "scout_exploration_complete"


@dataclass
class Event:
    """Represents an event that occurred in the system"""
    event_type: EventType
    timestamp: datetime
    data: Dict[str, Any]
    source: Optional[str] = None  # Agent or KS that generated the event

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class AgentState:
    """State of an agent at a given moment"""
    agent_id: str
    agent_type: str  # 'scout' or 'fumigator'
    position: Tuple[int, int]
    status: str  # 'idle', 'moving', 'fumigating', 'refilling'

    # Fumigator-specific
    pesticide_level: int = 0
    pesticide_capacity: int = 1000
    current_task_id: Optional[str] = None

    # Scout-specific
    fields_analyzed: int = 0
    analyzed_positions: set = field(default_factory=set)

    # Common stats
    tasks_completed: int = 0
    fields_fumigated: int = 0

    # Current path
    path: List[Tuple[int, int]] = field(default_factory=list)
    path_index: int = 0

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskState:
    """State of a task"""
    task_id: str
    position: Tuple[int, int]
    infestation_level: int
    priority: str  # 'low', 'medium', 'high', 'critical'
    status: str  # 'pending', 'assigned', 'in_progress', 'completed', 'failed'
    assigned_agent_id: Optional[str] = None
    created_at: Optional[datetime] = None
    assigned_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class WorldState:
    """State of the world/environment"""
    width: int
    height: int
    grid: List[List[int]]  # Terrain types
    crop_grid: List[List[int]]  # Crop types
    infestation_grid: List[List[int]]  # Infestation levels (0-100)
    field_weights: Dict[Tuple[int, int], float] = field(default_factory=dict)  # Dynamic weights
    barn_positions: List[Tuple[int, int]] = field(default_factory=list)


class KnowledgeBase:
    """
    Central repository of knowledge for the Blackboard system.

    This class stores:
    - Agent states
    - Task states
    - World state
    - Events history
    - Temporary shared data

    It provides thread-safe access to all knowledge and supports
    subscriptions for change notifications.
    """

    def __init__(self, world_instance):
        """
        Initialize the KnowledgeBase.

        Args:
            world_instance: Django World model instance
        """
        self.world_instance = world_instance
        self._lock = threading.RLock()

        # Initialize world state
        self.world_state = WorldState(
            width=world_instance.width,
            height=world_instance.height,
            grid=world_instance.grid,
            crop_grid=world_instance.crop_grid,
            infestation_grid=[row[:] for row in world_instance.infestation_grid],  # Deep copy
        )

        # Find barn positions
        from world.world_generator import TileType
        for z in range(self.world_state.height):
            for x in range(self.world_state.width):
                if self.world_state.grid[z][x] == TileType.BARN:
                    self.world_state.barn_positions.append((x, z))

        # Agent states
        self._agents: Dict[str, AgentState] = {}

        # Task states
        self._tasks: Dict[str, TaskState] = {}

        # Events history
        self._events: List[Event] = []
        self._max_events = 1000  # Keep last 1000 events

        # Shared data (key-value store for KS communication)
        self._shared_data: Dict[str, Any] = {}

        # Subscribers (for change notifications)
        self._subscribers: Dict[EventType, List[callable]] = {event_type: [] for event_type in EventType}

    # ========== AGENT STATE MANAGEMENT ==========

    def register_agent(self, agent_state: AgentState):
        """Register a new agent in the knowledge base"""
        with self._lock:
            self._agents[agent_state.agent_id] = agent_state

    def update_agent(self, agent_id: str, **updates):
        """Update agent state"""
        with self._lock:
            if agent_id in self._agents:
                agent = self._agents[agent_id]
                for key, value in updates.items():
                    if hasattr(agent, key):
                        setattr(agent, key, value)

                # Emit event if position changed
                if 'position' in updates:
                    self._emit_event(EventType.AGENT_MOVED, {
                        'agent_id': agent_id,
                        'position': updates['position']
                    }, source=agent_id)

                # Emit event if status changed to idle
                if 'status' in updates and updates['status'] == 'idle':
                    self._emit_event(EventType.AGENT_IDLE, {
                        'agent_id': agent_id
                    }, source=agent_id)

    def get_agent(self, agent_id: str) -> Optional[AgentState]:
        """Get agent state by ID"""
        with self._lock:
            return self._agents.get(agent_id)

    def get_all_agents(self) -> List[AgentState]:
        """Get all agent states"""
        with self._lock:
            return list(self._agents.values())

    def get_agents_by_type(self, agent_type: str) -> List[AgentState]:
        """Get all agents of a specific type"""
        with self._lock:
            return [agent for agent in self._agents.values() if agent.agent_type == agent_type]

    def get_idle_agents(self, agent_type: Optional[str] = None) -> List[AgentState]:
        """Get all idle agents, optionally filtered by type"""
        with self._lock:
            agents = self._agents.values()
            if agent_type:
                agents = [a for a in agents if a.agent_type == agent_type]
            return [a for a in agents if a.status == 'idle']

    # ========== TASK STATE MANAGEMENT ==========

    def create_task(self, task_state: TaskState):
        """Create a new task"""
        with self._lock:
            self._tasks[task_state.task_id] = task_state
            self._emit_event(EventType.TASK_CREATED, {
                'task_id': task_state.task_id,
                'position': task_state.position,
                'infestation_level': task_state.infestation_level,
                'priority': task_state.priority
            })

    def update_task(self, task_id: str, **updates):
        """Update task state"""
        with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                old_status = task.status

                for key, value in updates.items():
                    if hasattr(task, key):
                        setattr(task, key, value)

                # Emit events based on status changes
                if 'status' in updates and updates['status'] != old_status:
                    if updates['status'] == 'assigned':
                        self._emit_event(EventType.TASK_ASSIGNED, {
                            'task_id': task_id,
                            'agent_id': task.assigned_agent_id
                        })
                    elif updates['status'] == 'completed':
                        self._emit_event(EventType.TASK_COMPLETED, {
                            'task_id': task_id,
                            'agent_id': task.assigned_agent_id
                        })
                    elif updates['status'] == 'failed':
                        self._emit_event(EventType.TASK_FAILED, {
                            'task_id': task_id,
                            'agent_id': task.assigned_agent_id
                        })

    def get_task(self, task_id: str) -> Optional[TaskState]:
        """Get task by ID"""
        with self._lock:
            return self._tasks.get(task_id)

    def get_tasks_by_status(self, status: str) -> List[TaskState]:
        """Get all tasks with a specific status"""
        with self._lock:
            return [task for task in self._tasks.values() if task.status == status]

    def get_pending_tasks(self) -> List[TaskState]:
        """Get all pending tasks, sorted by priority and infestation"""
        with self._lock:
            tasks = [task for task in self._tasks.values() if task.status == 'pending']
            # Sort by priority (critical > high > medium > low) then by infestation
            priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
            tasks.sort(key=lambda t: (priority_order.get(t.priority, 99), -t.infestation_level))
            return tasks

    def get_all_tasks(self) -> List[TaskState]:
        """Get all tasks"""
        with self._lock:
            return list(self._tasks.values())

    # ========== WORLD STATE MANAGEMENT ==========

    def update_infestation(self, x: int, z: int, new_level: int):
        """Update infestation level at a position"""
        with self._lock:
            if 0 <= x < self.world_state.width and 0 <= z < self.world_state.height:
                self.world_state.infestation_grid[z][x] = new_level

    def update_field_weight(self, x: int, z: int, weight: float):
        """Update dynamic field weight"""
        with self._lock:
            self.world_state.field_weights[(x, z)] = weight

    def get_infestation(self, x: int, z: int) -> int:
        """Get infestation level at a position"""
        with self._lock:
            if 0 <= x < self.world_state.width and 0 <= z < self.world_state.height:
                return self.world_state.infestation_grid[z][x]
            return 0

    def get_field_weight(self, x: int, z: int) -> float:
        """Get field weight at a position"""
        with self._lock:
            return self.world_state.field_weights.get((x, z), 0.0)

    # ========== EVENT MANAGEMENT ==========

    def _emit_event(self, event_type: EventType, data: Dict[str, Any], source: Optional[str] = None):
        """Emit an event (internal use)"""
        event = Event(
            event_type=event_type,
            timestamp=datetime.now(),
            data=data,
            source=source
        )

        # Add to history
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events.pop(0)

        # Notify subscribers
        for callback in self._subscribers[event_type]:
            try:
                callback(event)
            except Exception as e:
                print(f"Error in event subscriber: {e}")

    def emit_event(self, event_type: EventType, data: Dict[str, Any], source: Optional[str] = None):
        """Emit a custom event (public API)"""
        with self._lock:
            self._emit_event(event_type, data, source)

    def subscribe(self, event_type: EventType, callback: callable):
        """Subscribe to an event type"""
        with self._lock:
            self._subscribers[event_type].append(callback)

    def get_recent_events(self, event_type: Optional[EventType] = None, limit: int = 100) -> List[Event]:
        """Get recent events, optionally filtered by type"""
        with self._lock:
            events = self._events
            if event_type:
                events = [e for e in events if e.event_type == event_type]
            return events[-limit:]

    # ========== SHARED DATA ==========

    def set_shared(self, key: str, value: Any):
        """Set shared data"""
        with self._lock:
            self._shared_data[key] = value

    def get_shared(self, key: str, default: Any = None) -> Any:
        """Get shared data"""
        with self._lock:
            return self._shared_data.get(key, default)

    def delete_shared(self, key: str):
        """Delete shared data"""
        with self._lock:
            if key in self._shared_data:
                del self._shared_data[key]

    # ========== STATISTICS ==========

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics"""
        with self._lock:
            total_agents = len(self._agents)
            fumigators = [a for a in self._agents.values() if a.agent_type == 'fumigator']
            scouts = [a for a in self._agents.values() if a.agent_type == 'scout']

            total_tasks = len(self._tasks)
            pending_tasks = len([t for t in self._tasks.values() if t.status == 'pending'])
            completed_tasks = len([t for t in self._tasks.values() if t.status == 'completed'])

            total_fields_fumigated = sum(a.fields_fumigated for a in fumigators)
            total_fields_analyzed = sum(a.fields_analyzed for a in scouts)

            # Calculate total infestation remaining
            total_infestation = 0
            infested_cells = 0
            for z in range(self.world_state.height):
                for x in range(self.world_state.width):
                    level = self.world_state.infestation_grid[z][x]
                    if level > 0:
                        total_infestation += level
                        infested_cells += 1

            return {
                'total_agents': total_agents,
                'fumigators': len(fumigators),
                'scouts': len(scouts),
                'total_tasks': total_tasks,
                'pending_tasks': pending_tasks,
                'completed_tasks': completed_tasks,
                'total_fields_fumigated': total_fields_fumigated,
                'total_fields_analyzed': total_fields_analyzed,
                'total_infestation': total_infestation,
                'infested_cells': infested_cells,
                'avg_infestation': total_infestation / infested_cells if infested_cells > 0 else 0,
            }
