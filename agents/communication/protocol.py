"""
Unity Communication Protocol v2

Defines structured messages for communication between Django backend and Unity client.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime


class MessageType(Enum):
    """Types of messages that can be sent"""
    # Connection
    CONNECTION = "connection"
    PING = "ping"
    PONG = "pong"

    # Simulation control
    SIMULATION_STARTED = "simulation_started"
    SIMULATION_PAUSED = "simulation_paused"
    SIMULATION_RESUMED = "simulation_resumed"
    SIMULATION_COMPLETED = "simulation_completed"
    SIMULATION_ERROR = "simulation_error"

    # Real-time updates
    STEP_UPDATE = "step_update"
    AGENT_UPDATE = "agent_update"
    TASK_UPDATE = "task_update"
    WORLD_UPDATE = "world_update"

    # Commands (Backend → Unity)
    AGENT_COMMAND = "agent_command"
    CAMERA_COMMAND = "camera_command"
    RENDER_COMMAND = "render_command"

    # Confirmations (Unity → Backend)
    COMMAND_CONFIRMATION = "command_confirmation"
    RENDER_COMPLETE = "render_complete"

    # Status
    GET_STATUS = "get_status"
    STATUS_RESPONSE = "status_response"


class CommandType(Enum):
    """Types of commands for agents"""
    MOVE = "move"
    FUMIGATE = "fumigate"
    SCAN = "scan"
    REFILL = "refill"
    IDLE = "idle"


class AgentType(Enum):
    """Types of agents"""
    FUMIGATOR = "fumigator"
    SCOUT = "scout"


@dataclass
class Message:
    """Base message class"""
    type: str
    timestamp: str
    # Mark version as init=False to avoid ordering issues in subclasses that add
    # required fields after this defaulted value.
    version: str = field(default="2.0", init=False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class ConnectionMessage(Message):
    """Connection established message"""
    simulation_id: str
    message: str = "Connected to simulation"

    def __init__(self, simulation_id: str, **kwargs):
        super().__init__(
            type=MessageType.CONNECTION.value,
            timestamp=datetime.now().isoformat(),
            **kwargs
        )
        self.simulation_id = simulation_id


@dataclass
class AgentState:
    """State of an agent"""
    agent_id: str
    agent_type: str
    position: List[int]  # [x, z]
    status: str
    pesticide_level: Optional[int] = None
    tasks_completed: int = 0
    fields_fumigated: int = 0
    fields_analyzed: int = 0
    current_task_id: Optional[str] = None
    path: Optional[List[List[int]]] = None


@dataclass
class TaskState:
    """State of a task"""
    task_id: str
    position: List[int]  # [x, z]
    infestation_level: int
    priority: str
    status: str
    assigned_agent_id: Optional[str] = None
    crop_type: Optional[str] = None


@dataclass
class StepUpdateMessage(Message):
    """Step update message"""
    step: int
    agents: List[Dict[str, Any]]
    tasks: List[Dict[str, Any]]
    statistics: Dict[str, Any]
    infestation_grid: Optional[List[List[int]]] = None

    def __init__(self, step: int, agents: List, tasks: List, statistics: Dict, **kwargs):
        super().__init__(
            type=MessageType.STEP_UPDATE.value,
            timestamp=datetime.now().isoformat(),
            **kwargs
        )
        self.step = step
        self.agents = agents
        self.tasks = tasks
        self.statistics = statistics
        self.infestation_grid = kwargs.get('infestation_grid')


@dataclass
class AgentCommandMessage(Message):
    """Command for an agent"""
    agent_id: str
    command: str  # CommandType
    parameters: Dict[str, Any]
    command_id: Optional[str] = None

    def __init__(self, agent_id: str, command: str, parameters: Dict, **kwargs):
        super().__init__(
            type=MessageType.AGENT_COMMAND.value,
            timestamp=datetime.now().isoformat(),
            **kwargs
        )
        self.agent_id = agent_id
        self.command = command
        self.parameters = parameters
        self.command_id = kwargs.get('command_id', f"{agent_id}_{datetime.now().timestamp()}")


@dataclass
class SimulationCompletedMessage(Message):
    """Simulation completed message"""
    simulation_id: str
    total_steps: int
    statistics: Dict[str, Any]
    results: Dict[str, Any]

    def __init__(self, simulation_id: str, total_steps: int, statistics: Dict, results: Dict, **kwargs):
        super().__init__(
            type=MessageType.SIMULATION_COMPLETED.value,
            timestamp=datetime.now().isoformat(),
            **kwargs
        )
        self.simulation_id = simulation_id
        self.total_steps = total_steps
        self.statistics = statistics
        self.results = results


@dataclass
class ErrorMessage(Message):
    """Error message"""
    error: str
    details: Optional[Dict[str, Any]] = None

    def __init__(self, error: str, **kwargs):
        super().__init__(
            type=MessageType.SIMULATION_ERROR.value,
            timestamp=datetime.now().isoformat(),
            **kwargs
        )
        self.error = error
        self.details = kwargs.get('details')


class UnityProtocol:
    """
    Unity Protocol v2

    Provides methods to create structured messages for Unity communication.
    """

    VERSION = "2.0"

    @staticmethod
    def connection(simulation_id: str) -> Dict[str, Any]:
        """Create connection message"""
        msg = ConnectionMessage(simulation_id)
        return msg.to_dict()

    @staticmethod
    def step_update(
        step: int,
        agents: List[Dict],
        tasks: List[Dict],
        statistics: Dict,
        infestation_grid: Optional[List[List[int]]] = None
    ) -> Dict[str, Any]:
        """Create step update message"""
        msg = StepUpdateMessage(step, agents, tasks, statistics, infestation_grid=infestation_grid)
        return msg.to_dict()

    @staticmethod
    def agent_command(
        agent_id: str,
        command: CommandType,
        **parameters
    ) -> Dict[str, Any]:
        """Create agent command message"""
        msg = AgentCommandMessage(agent_id, command.value, parameters)
        return msg.to_dict()

    @staticmethod
    def simulation_completed(
        simulation_id: str,
        total_steps: int,
        statistics: Dict,
        results: Dict
    ) -> Dict[str, Any]:
        """Create simulation completed message"""
        msg = SimulationCompletedMessage(simulation_id, total_steps, statistics, results)
        return msg.to_dict()

    @staticmethod
    def error(error: str, **details) -> Dict[str, Any]:
        """Create error message"""
        msg = ErrorMessage(error, details=details)
        return msg.to_dict()

    @staticmethod
    def pong(timestamp: Optional[str] = None) -> Dict[str, Any]:
        """Create pong response"""
        return {
            'type': MessageType.PONG.value,
            'timestamp': timestamp or datetime.now().isoformat(),
            'version': UnityProtocol.VERSION,
        }

    @staticmethod
    def status_response(simulation_id: str, status: Dict) -> Dict[str, Any]:
        """Create status response message"""
        return {
            'type': MessageType.STATUS_RESPONSE.value,
            'simulation_id': simulation_id,
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'version': UnityProtocol.VERSION,
        }
