"""
State Broadcaster for Unity Communication

Broadcasts simulation state updates to Unity clients via WebSocket.
"""

from typing import Dict, Any, List
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .protocol import UnityProtocol, MessageType


class StateBroadcaster:
    """
    Broadcasts simulation state to Unity clients.

    This class provides methods to send different types of updates
    to connected Unity clients via WebSocket.
    """

    def __init__(self, simulation_id: str):
        """
        Initialize broadcaster.

        Args:
            simulation_id: The simulation ID
        """
        self.simulation_id = str(simulation_id)
        self.channel_layer = get_channel_layer()
        self.group_name = f'simulation_{self.simulation_id}'

    def send_step_update(
        self,
        step: int,
        agents: List[Dict],
        tasks: List[Dict],
        statistics: Dict,
        infestation_grid: List[List[int]] = None
    ):
        """
        Send step update to all connected clients.

        Args:
            step: Current step number
            agents: List of agent states
            tasks: List of task states
            statistics: Simulation statistics
            infestation_grid: Optional infestation grid
        """
        message = UnityProtocol.step_update(
            step=step,
            agents=agents,
            tasks=tasks,
            statistics=statistics,
            infestation_grid=infestation_grid
        )

        self._send_to_group({
            'type': 'simulation_update',
            'data': message,
        })

    def send_agent_update(self, agent_data: Dict):
        """
        Send update for a specific agent.

        Args:
            agent_data: Agent state data
        """
        message = {
            'type': MessageType.AGENT_UPDATE.value,
            'agent': agent_data,
        }

        self._send_to_group({
            'type': 'simulation_update',
            'data': message,
        })

    def send_task_update(self, task_data: Dict):
        """
        Send update for a specific task.

        Args:
            task_data: Task state data
        """
        message = {
            'type': MessageType.TASK_UPDATE.value,
            'task': task_data,
        }

        self._send_to_group({
            'type': 'simulation_update',
            'data': message,
        })

    def send_simulation_completed(
        self,
        total_steps: int,
        statistics: Dict,
        results: Dict
    ):
        """
        Send simulation completed message.

        Args:
            total_steps: Total steps executed
            statistics: Final statistics
            results: Final results
        """
        message = UnityProtocol.simulation_completed(
            simulation_id=self.simulation_id,
            total_steps=total_steps,
            statistics=statistics,
            results=results
        )

        self._send_to_group({
            'type': 'simulation_status',
            'data': message,
        })

    def send_error(self, error: str, **details):
        """
        Send error message.

        Args:
            error: Error message
            **details: Additional error details
        """
        message = UnityProtocol.error(error, **details)

        self._send_to_group({
            'type': 'simulation_error',
            'data': message,
        })

    def send_agent_command(
        self,
        agent_id: str,
        command: str,
        **parameters
    ):
        """
        Send command to a specific agent.

        Args:
            agent_id: Agent ID
            command: Command type
            **parameters: Command parameters
        """
        from .protocol import CommandType

        try:
            cmd_type = CommandType(command)
        except ValueError:
            # Invalid command, send as string
            cmd_type = command

        message = {
            'type': MessageType.AGENT_COMMAND.value,
            'agent_id': agent_id,
            'command': command,
            'parameters': parameters,
        }

        self._send_to_group({
            'type': 'simulation_update',
            'data': message,
        })

    def _send_to_group(self, message: Dict[str, Any]):
        """
        Send message to the simulation group.

        Args:
            message: Message to send
        """
        if not self.channel_layer:
            return

        async_to_sync(self.channel_layer.group_send)(
            self.group_name,
            message
        )

    def send_custom_message(self, message_type: str, data: Dict[str, Any]):
        """
        Send a custom message.

        Args:
            message_type: Custom message type
            data: Message data
        """
        message = {
            'type': message_type,
            **data,
        }

        self._send_to_group({
            'type': 'simulation_update',
            'data': message,
        })
