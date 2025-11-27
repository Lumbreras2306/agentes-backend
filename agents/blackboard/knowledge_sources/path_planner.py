"""
PathPlannerKS - Plans optimal paths for agents

This Knowledge Source calculates paths when tasks are assigned,
considering dynamic field weights and traffic.
"""

from .base import KnowledgeSource
from ..knowledge_base import EventType
from typing import Tuple, List, Optional


class PathPlannerKS(KnowledgeSource):
    """
    PathPlannerKS calculates optimal paths for agents.

    Triggers:
    - TASK_ASSIGNED: When a task is assigned, calculate path

    Logic:
    - Uses Dijkstra pathfinding with dynamic weights
    - Considers field weights (increased by previous passes)
    - Stores path in agent state
    - Emits PATH_CALCULATED event
    """

    def __init__(self, knowledge_base):
        super().__init__(knowledge_base)
        self.priority = 6  # Medium priority
        self.triggers = {EventType.TASK_ASSIGNED}

        # Path calculation is expensive, so we cache recent assignments
        self.processed_assignments = set()

    def check_preconditions(self) -> bool:
        """Check if there are new task assignments to process"""
        recent_assignments = self.kb.get_recent_events(EventType.TASK_ASSIGNED, limit=20)

        for event in recent_assignments:
            task_id = event.data.get('task_id')
            agent_id = event.data.get('agent_id')
            key = (agent_id, task_id)

            if key not in self.processed_assignments:
                return True

        return False

    def execute(self):
        """Calculate paths for newly assigned tasks"""
        recent_assignments = self.kb.get_recent_events(EventType.TASK_ASSIGNED, limit=20)

        for event in recent_assignments:
            task_id = event.data.get('task_id')
            agent_id = event.data.get('agent_id')
            key = (agent_id, task_id)

            if key in self.processed_assignments:
                continue

            # Calculate path
            agent = self.kb.get_agent(agent_id)
            task = self.kb.get_task(task_id)

            if not agent or not task:
                continue

            # Calculate path using pathfinding
            path = self._calculate_path(agent.position, task.position, agent.agent_type)

            if path:
                # Update agent with path
                self.kb.update_agent(
                    agent_id,
                    path=path,
                    path_index=0,
                )

                # Update command with path
                command = self.kb.get_shared(f'command_{agent_id}')
                if command:
                    command['path'] = path
                    self.kb.set_shared(f'command_{agent_id}', command)

                # Emit event
                self.kb.emit_event(EventType.PATH_CALCULATED, {
                    'agent_id': agent_id,
                    'task_id': task_id,
                    'path_length': len(path),
                })

            self.processed_assignments.add(key)

    def _calculate_path(
        self,
        start: Tuple[int, int],
        goal: Tuple[int, int],
        agent_type: str
    ) -> List[Tuple[int, int]]:
        """
        Calculate path using Dijkstra algorithm.

        Args:
            start: Start position
            goal: Goal position
            agent_type: Type of agent ('scout' or 'fumigator')

        Returns:
            List of positions forming the path
        """
        from world.pathfinding import DynamicPathfinder

        # Get field weights from KnowledgeBase
        field_weights = self.kb.world_state.field_weights

        # Create pathfinder
        pathfinder = DynamicPathfinder(
            grid=self.kb.world_state.grid,
            width=self.kb.world_state.width,
            height=self.kb.world_state.height,
            field_weights=field_weights
        )

        # Scouts can fly, fumigators prefer roads
        prefer_roads = (agent_type == 'fumigator')

        # Calculate path
        path = pathfinder.dijkstra(start, goal, prefer_roads=prefer_roads)

        return path if path else []

    def recalculate_path(self, agent_id: str) -> Optional[List[Tuple[int, int]]]:
        """
        Recalculate path for an agent (e.g., after a conflict).

        Args:
            agent_id: The agent ID

        Returns:
            New path or None if calculation fails
        """
        agent = self.kb.get_agent(agent_id)

        if not agent or not agent.current_task_id:
            return None

        task = self.kb.get_task(agent.current_task_id)

        if not task:
            return None

        # Calculate new path
        path = self._calculate_path(agent.position, task.position, agent.agent_type)

        if path:
            # Update agent
            self.kb.update_agent(
                agent_id,
                path=path,
                path_index=0,
            )

        return path
