"""
ConflictResolverKS - Resolves conflicts between agents

This Knowledge Source detects and resolves conflicts such as:
- Task failures
- Agent collisions
- Stuck agents
"""

from .base import KnowledgeSource
from ..knowledge_base import EventType, AgentState
from typing import List


class ConflictResolverKS(KnowledgeSource):
    """
    ConflictResolverKS detects and resolves conflicts.

    Triggers:
    - TASK_FAILED: When a task fails, reassign it
    - CONFLICT_DETECTED: When a conflict is detected

    Logic:
    - Detects stuck agents (no movement for N steps)
    - Re-assigns failed tasks
    - Resolves resource contention
    """

    def __init__(self, knowledge_base):
        super().__init__(knowledge_base)
        self.priority = 4  # Lower priority - runs after other KS
        self.triggers = {EventType.TASK_FAILED, EventType.CONFLICT_DETECTED}
        self.always_run = True  # Check for conflicts every cycle

        # Track agent positions over time
        self.agent_position_history = {}
        self.stuck_threshold = 5  # Steps without movement = stuck

    def check_preconditions(self) -> bool:
        """Check if there are conflicts to resolve"""
        # Check for failed tasks
        failed_tasks = self.kb.get_tasks_by_status('failed')
        if failed_tasks:
            return True

        # Check for stuck agents
        if self._detect_stuck_agents():
            return True

        return False

    def execute(self):
        """Resolve conflicts"""
        # Handle failed tasks
        self._handle_failed_tasks()

        # Handle stuck agents
        self._handle_stuck_agents()

    def _handle_failed_tasks(self):
        """Re-assign failed tasks"""
        failed_tasks = self.kb.get_tasks_by_status('failed')

        for task in failed_tasks:
            # Reset task to pending
            self.kb.update_task(
                task.task_id,
                status='pending',
                assigned_agent_id=None,
            )

            print(f"Conflict resolved: Task {task.task_id} reset to pending")

    def _detect_stuck_agents(self) -> List[str]:
        """Detect agents that haven't moved in a while"""
        stuck_agents = []

        for agent in self.kb.get_all_agents():
            agent_id = agent.agent_id

            # Initialize history if needed
            if agent_id not in self.agent_position_history:
                self.agent_position_history[agent_id] = []

            # Add current position
            history = self.agent_position_history[agent_id]
            history.append(agent.position)

            # Keep only recent history
            if len(history) > self.stuck_threshold:
                history.pop(0)

            # Check if stuck (same position for N steps)
            if len(history) >= self.stuck_threshold:
                if len(set(history)) == 1 and agent.status not in ['idle', 'refilling']:
                    stuck_agents.append(agent_id)

        return stuck_agents

    def _handle_stuck_agents(self):
        """Handle agents that are stuck"""
        stuck_agents = self._detect_stuck_agents()

        for agent_id in stuck_agents:
            agent = self.kb.get_agent(agent_id)

            if not agent:
                continue

            # If agent has a task, mark task as failed and reset agent
            if agent.current_task_id:
                task = self.kb.get_task(agent.current_task_id)

                if task:
                    # Mark task as pending again
                    self.kb.update_task(
                        task.task_id,
                        status='pending',
                        assigned_agent_id=None,
                    )

            # Reset agent to idle
            self.kb.update_agent(
                agent_id,
                status='idle',
                current_task_id=None,
                path=[],
                path_index=0,
            )

            # Clear agent command
            self.kb.delete_shared(f'command_{agent_id}')

            # Clear position history
            self.agent_position_history[agent_id] = []

            # Emit event
            self.kb.emit_event(EventType.CONFLICT_DETECTED, {
                'type': 'stuck_agent',
                'agent_id': agent_id,
                'resolution': 'reset_to_idle',
            })

            print(f"Conflict resolved: Stuck agent {agent_id} reset to idle")

    def resolve_task_conflict(self, task_id: str):
        """
        Manually resolve a specific task conflict.

        Args:
            task_id: The task ID to resolve
        """
        task = self.kb.get_task(task_id)

        if not task:
            return

        # Reset task
        self.kb.update_task(
            task_id,
            status='pending',
            assigned_agent_id=None,
        )

        # If agent was assigned, reset it
        if task.assigned_agent_id:
            agent = self.kb.get_agent(task.assigned_agent_id)

            if agent:
                self.kb.update_agent(
                    task.assigned_agent_id,
                    status='idle',
                    current_task_id=None,
                )
