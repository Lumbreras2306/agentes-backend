"""
FumigatorAgent - Simple reactive fumigator that executes tasks

The fumigator follows commands from the blackboard to fumigate fields
and refill pesticide when needed.
"""

from .base_agent import BaseAgent
from ..blackboard.knowledge_base import EventType
from typing import Dict, Any


class FumigatorAgent(BaseAgent):
    """
    Fumigator agent that fumigates infested fields.

    Commands it responds to:
    - execute_task: Execute a fumigation task
    - refill_pesticide: Refill pesticide at barn
    - move: Move to a specific position

    Behavior:
    - Follows path to task
    - Fumigates at destination
    - Refills when commanded
    - Updates field weights when crossing fields
    """

    def setup(self):
        """Initialize fumigator agent"""
        super().setup()

        self.agent_type = 'fumigator'

        # Pesticide system
        self.pesticide_capacity = 1000
        self.pesticide_level = 1000

        # Current task
        self.current_task_id = None

        # Register with blackboard
        from ..blackboard.knowledge_base import AgentState
        agent_state = AgentState(
            agent_id=str(self.id),
            agent_type='fumigator',
            position=self.position,
            status='idle',
            pesticide_level=self.pesticide_level,
            pesticide_capacity=self.pesticide_capacity,
        )
        self.blackboard.register_agent(agent_state)

    def execute(self, command: Dict[str, Any]):
        """Execute fumigator-specific commands"""
        action = command.get('action')

        if action == 'execute_task':
            self._execute_task(command)
        elif action == 'refill_pesticide':
            self._execute_refill(command)
        elif action == 'move':
            self._execute_move(command)
        else:
            # Unknown command
            pass

    def _execute_task(self, command: Dict[str, Any]):
        """Execute a fumigation task"""
        task_id = command.get('task_id')
        task_position = command.get('task_position')

        if not task_id or not task_position:
            return

        self.current_task_id = task_id
        self.status = 'executing_task'

        # Get agent state from blackboard
        agent_state = self.blackboard.knowledge_base.get_agent(str(self.id))

        if not agent_state:
            return

        # Check if we have a path
        if agent_state.path and len(agent_state.path) > agent_state.path_index:
            # Follow path
            next_pos = agent_state.path[agent_state.path_index]

            # Update field weight if crossing a field
            self._update_field_weight(next_pos)

            self.position = next_pos
            self.status = 'moving'

            # Update path index
            self.blackboard.knowledge_base.update_agent(
                str(self.id),
                path_index=agent_state.path_index + 1
            )

            # Check if arrived at destination
            if self.position == tuple(task_position):
                self._fumigate_at_position(task_position, task_id)
        else:
            # No path or reached end - check if at destination
            if self.position == tuple(task_position):
                self._fumigate_at_position(task_position, task_id)
            else:
                # No path and not at destination - something went wrong
                self._on_task_failed(task_id)

    def _fumigate_at_position(self, position: tuple, task_id: str):
        """Fumigate at the current position"""
        x, z = position
        kb = self.blackboard.knowledge_base

        # Get current infestation
        infestation = kb.get_infestation(x, z)

        if infestation <= 0:
            # Already fumigated
            self._on_task_completed(task_id)
            return

        # Check if we have enough pesticide
        if self.pesticide_level < infestation:
            # Not enough pesticide - report failure
            self._on_task_failed(task_id)
            return

        # Fumigate
        kb.update_infestation(x, z, 0)
        self.pesticide_level -= infestation
        self.fields_fumigated += 1

        self.status = 'fumigating'

        # Complete task
        self._on_task_completed(task_id)

    def _on_task_completed(self, task_id: str):
        """Called when task is completed"""
        kb = self.blackboard.knowledge_base

        # Update task status
        kb.update_task(task_id, status='completed')

        # Update agent
        self.current_task_id = None
        self.tasks_completed += 1
        self.status = 'idle'

        # Clear command
        self.blackboard.clear_agent_command(str(self.id))

    def _on_task_failed(self, task_id: str):
        """Called when task fails"""
        kb = self.blackboard.knowledge_base

        # Update task status
        kb.update_task(task_id, status='failed')

        # Update agent
        self.current_task_id = None
        self.status = 'idle'

        # Clear command
        self.blackboard.clear_agent_command(str(self.id))

    def _execute_refill(self, command: Dict[str, Any]):
        """Execute refill command"""
        barn_position = command.get('barn_position')

        if not barn_position:
            return

        # Move towards barn
        if self.position != tuple(barn_position):
            self._move_towards_barn(barn_position)
            self.status = 'returning_to_barn'
        else:
            # At barn, refill
            self.pesticide_level = self.pesticide_capacity
            self.status = 'idle'

            # Emit refill event
            self.blackboard.report_event(
                EventType.AGENT_REFILLED,
                {
                    'agent_id': str(self.id),
                    'pesticide_level': self.pesticide_level,
                },
                source=str(self.id)
            )

            # Clear command
            self.blackboard.clear_agent_command(str(self.id))

    def _move_towards_barn(self, barn_position: tuple):
        """Simple movement towards barn"""
        # Get path from agent state
        agent_state = self.blackboard.knowledge_base.get_agent(str(self.id))

        if agent_state and agent_state.path:
            # Follow path
            if len(agent_state.path) > agent_state.path_index:
                next_pos = agent_state.path[agent_state.path_index]
                self.position = next_pos

                self.blackboard.knowledge_base.update_agent(
                    str(self.id),
                    path_index=agent_state.path_index + 1
                )
        else:
            # No path, move directly (simple)
            x, z = self.position
            bx, bz = barn_position

            if abs(bx - x) > abs(bz - z):
                new_x = x + (1 if bx > x else -1)
                self.position = (new_x, z)
            else:
                new_z = z + (1 if bz > z else -1)
                self.position = (x, new_z)

    def _update_field_weight(self, position: tuple):
        """Update field weight when crossing a field"""
        from world.world_generator import TileType

        x, z = position
        kb = self.blackboard.knowledge_base

        if kb.world_state.grid[z][x] == TileType.FIELD:
            # Increase weight (exponentially)
            current_weight = kb.get_field_weight(x, z)
            new_weight = current_weight * 1.8 if current_weight > 0 else 1.8
            kb.update_field_weight(x, z, new_weight)

    def report(self):
        """Report fumigator state to blackboard"""
        super().report()

        # Update pesticide level
        self.blackboard.knowledge_base.update_agent(
            str(self.id),
            pesticide_level=self.pesticide_level,
            current_task_id=self.current_task_id,
        )
