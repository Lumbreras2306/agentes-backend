"""
ResourceManagerKS - Manages agent resources (pesticide)

This Knowledge Source monitors pesticide levels and triggers
refill operations when agents are running low.
"""

from .base import KnowledgeSource
from ..knowledge_base import EventType, AgentState
from typing import List


class ResourceManagerKS(KnowledgeSource):
    """
    ResourceManagerKS manages fumigator pesticide levels.

    Triggers:
    - TASK_COMPLETED: After completing a task, check pesticide
    - AGENT_MOVED: During movement, check if getting low

    Logic:
    - Monitors pesticide_level of all fumigators
    - When level < threshold, sends refill command
    - Prevents agents from taking tasks they can't complete
    """

    def __init__(self, knowledge_base):
        super().__init__(knowledge_base)
        self.priority = 7  # Medium-high priority
        self.triggers = {
            EventType.TASK_COMPLETED,
            EventType.AGENT_MOVED,
        }
        self.always_run = True  # Check every cycle

        # Configuration
        self.low_pesticide_threshold = 100  # When to trigger refill
        self.critical_pesticide_threshold = 10  # Force refill immediately

    def check_preconditions(self) -> bool:
        """Check if any fumigators need attention"""
        fumigators = self.kb.get_agents_by_type('fumigator')

        for fumigator in fumigators:
            if fumigator.pesticide_level < self.low_pesticide_threshold:
                return True

        return False

    def execute(self):
        """Check and manage pesticide levels"""
        fumigators = self.kb.get_agents_by_type('fumigator')

        for fumigator in fumigators:
            # Critical level - immediate refill
            if fumigator.pesticide_level <= self.critical_pesticide_threshold:
                self._trigger_refill(fumigator, urgent=True)

            # Low level - refill if idle or after completing current task
            elif fumigator.pesticide_level < self.low_pesticide_threshold:
                if fumigator.status in ['idle', 'completed']:
                    self._trigger_refill(fumigator, urgent=False)

            # Also check if agent has a task but not enough pesticide
            if fumigator.current_task_id:
                task = self.kb.get_task(fumigator.current_task_id)
                if task and fumigator.pesticide_level < task.infestation_level:
                    # Cancel task and send to refill
                    self._cancel_task_and_refill(fumigator, task)

    def _trigger_refill(self, fumigator: AgentState, urgent: bool = False):
        """
        Trigger refill operation for a fumigator.

        Args:
            fumigator: The fumigator agent
            urgent: If True, refill immediately; if False, refill when idle
        """
        # Find nearest barn position
        barn_position = self._find_nearest_barn(fumigator.position)

        if not barn_position:
            print(f"Warning: No barn found for fumigator {fumigator.agent_id}")
            return

        # Update agent status
        self.kb.update_agent(
            fumigator.agent_id,
            status='returning_to_barn'
        )

        # Send command to agent
        self.kb.set_shared(f'command_{fumigator.agent_id}', {
            'action': 'refill_pesticide',
            'barn_position': barn_position,
            'urgent': urgent,
        })

        # Emit event
        self.kb.emit_event(EventType.AGENT_LOW_RESOURCE, {
            'agent_id': fumigator.agent_id,
            'pesticide_level': fumigator.pesticide_level,
            'urgent': urgent,
        }, source=fumigator.agent_id)

    def _cancel_task_and_refill(self, fumigator: AgentState, task):
        """Cancel current task and send agent to refill"""
        # Update task to pending
        self.kb.update_task(
            task.task_id,
            status='pending',
            assigned_agent_id=None,
        )

        # Update agent
        self.kb.update_agent(
            fumigator.agent_id,
            current_task_id=None,
        )

        # Trigger refill
        self._trigger_refill(fumigator, urgent=True)

    def _find_nearest_barn(self, position) -> tuple:
        """Find the nearest barn position"""
        barn_positions = self.kb.world_state.barn_positions

        if not barn_positions:
            return None

        min_distance = float('inf')
        nearest_barn = barn_positions[0]

        for barn_pos in barn_positions:
            distance = abs(position[0] - barn_pos[0]) + abs(position[1] - barn_pos[1])
            if distance < min_distance:
                min_distance = distance
                nearest_barn = barn_pos

        return nearest_barn

    def validate_task_feasibility(self, agent_id: str, task_id: str) -> bool:
        """
        Validate if an agent can complete a task with current resources.

        Args:
            agent_id: The agent ID
            task_id: The task ID

        Returns:
            True if agent can complete task, False otherwise
        """
        agent = self.kb.get_agent(agent_id)
        task = self.kb.get_task(task_id)

        if not agent or not task:
            return False

        # Check if agent has enough pesticide
        if agent.pesticide_level < task.infestation_level:
            return False

        # Check if agent can reach task and return to barn
        # (This is a simplified check - in reality would use pathfinding)
        distance_to_task = abs(agent.position[0] - task.position[0]) + abs(agent.position[1] - task.position[1])

        # Find nearest barn
        barn_pos = self._find_nearest_barn(task.position)
        if barn_pos:
            distance_to_barn = abs(task.position[0] - barn_pos[0]) + abs(task.position[1] - barn_pos[1])
        else:
            distance_to_barn = 0

        # Estimate pesticide needed
        pesticide_needed = task.infestation_level

        return agent.pesticide_level >= pesticide_needed

    def get_refill_priority(self, fumigator: AgentState) -> int:
        """
        Calculate refill priority for a fumigator.

        Returns:
            Priority level (0-10, higher = more urgent)
        """
        pesticide_percent = (fumigator.pesticide_level / fumigator.pesticide_capacity) * 100

        if pesticide_percent <= 1:
            return 10  # Critical
        elif pesticide_percent <= 5:
            return 8  # Very urgent
        elif pesticide_percent <= 10:
            return 6  # Urgent
        elif pesticide_percent <= 20:
            return 4  # Medium
        else:
            return 0  # Not urgent
