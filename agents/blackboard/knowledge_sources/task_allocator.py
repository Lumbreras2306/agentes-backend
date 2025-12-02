"""
TaskAllocatorKS - Optimally assigns tasks to fumigator agents

Uses Hungarian algorithm for optimal task-to-agent assignment
considering distance, priority, and agent capacity.
"""

from .base import KnowledgeSource
from ..knowledge_base import EventType, AgentState, TaskState
from typing import List, Tuple, Dict
import math
from datetime import datetime


class TaskAllocatorKS(KnowledgeSource):
    """
    TaskAllocatorKS assigns pending tasks to idle fumigator agents.

    Triggers:
    - TASK_CREATED: When a new task is created
    - AGENT_IDLE: When an agent becomes idle
    - TASK_COMPLETED: When a task is completed (free up agent)

    Logic:
    - Finds idle fumigators
    - Finds pending tasks
    - Creates cost matrix (distance + priority + resources)
    - Uses Hungarian algorithm for optimal assignment
    - Assigns tasks and updates KnowledgeBase
    """

    def __init__(self, knowledge_base):
        super().__init__(knowledge_base)
        self.priority = 8  # High priority - assign tasks quickly
        self.triggers = {
            EventType.TASK_CREATED,
            EventType.AGENT_IDLE,
            EventType.TASK_COMPLETED,
        }
        self.always_run = True  # Run every cycle to check for assignments

    def check_preconditions(self) -> bool:
        """Check if there are tasks to assign and idle agents"""
        # Ya no esperamos scouts - asignar tareas inmediatamente
        idle_fumigators = self.kb.get_idle_agents('fumigator')
        pending_tasks = self.kb.get_pending_tasks()

        return len(idle_fumigators) > 0 and len(pending_tasks) > 0

    def execute(self):
        """Assign pending tasks to idle fumigators optimally"""
        idle_fumigators = self.kb.get_idle_agents('fumigator')
        pending_tasks = self.kb.get_pending_tasks()

        if not idle_fumigators or not pending_tasks:
            return

        # Filter fumigators that have enough pesticide
        available_fumigators = [
            f for f in idle_fumigators
            if f.pesticide_level >= 10  # Minimum pesticide to take a task
        ]

        if not available_fumigators:
            return

        # Perform optimal assignment
        assignments = self._optimal_assignment(available_fumigators, pending_tasks)

        # Execute assignments
        for agent_id, task_id in assignments:
            agent = self.kb.get_agent(agent_id)
            task = self.kb.get_task(task_id)

            if agent and task:
                # Update task
                self.kb.update_task(
                    task_id,
                    status='assigned',
                    assigned_agent_id=agent_id,
                    assigned_at=datetime.now()
                )

                # Update agent
                self.kb.update_agent(
                    agent_id,
                    current_task_id=task_id,
                    status='assigned'
                )

                # Store assignment command for agent
                self.kb.set_shared(f'command_{agent_id}', {
                    'action': 'execute_task',
                    'task_id': task_id,
                    'task_position': task.position,
                })

    def _optimal_assignment(
        self,
        agents: List[AgentState],
        tasks: List[TaskState]
    ) -> List[Tuple[str, str]]:
        """
        Perform optimal task assignment using Hungarian-like greedy algorithm.

        For simplicity, we use a greedy approach:
        - Sort tasks by priority and infestation
        - For each task, assign to the agent with lowest cost
        - Repeat until no more assignments possible

        Args:
            agents: List of available agents
            tasks: List of pending tasks

        Returns:
            List of (agent_id, task_id) tuples
        """
        assignments = []
        available_agents = set(a.agent_id for a in agents)
        available_tasks = set(t.task_id for t in tasks)

        # Create cost matrix
        cost_matrix = self._calculate_cost_matrix(agents, tasks)

        # Greedy assignment
        while available_agents and available_tasks:
            # Find minimum cost assignment
            min_cost = float('inf')
            best_assignment = None

            for agent in agents:
                if agent.agent_id not in available_agents:
                    continue

                for task in tasks:
                    if task.task_id not in available_tasks:
                        continue

                    cost = cost_matrix[(agent.agent_id, task.task_id)]

                    # Check if agent has enough pesticide
                    if agent.pesticide_level < task.infestation_level:
                        continue  # Skip this assignment

                    if cost < min_cost:
                        min_cost = cost
                        best_assignment = (agent.agent_id, task.task_id)

            if best_assignment:
                assignments.append(best_assignment)
                available_agents.remove(best_assignment[0])
                available_tasks.remove(best_assignment[1])
            else:
                break  # No more valid assignments

        return assignments

    def _calculate_cost_matrix(
        self,
        agents: List[AgentState],
        tasks: List[TaskState]
    ) -> Dict[Tuple[str, str], float]:
        """
        Calculate cost matrix for task assignment.

        Cost factors:
        - Distance: Manhattan distance from agent to task
        - Priority: Higher priority tasks have lower cost
        - Resource: Tasks requiring more pesticide than agent has get high cost

        Returns:
            Dict mapping (agent_id, task_id) to cost
        """
        cost_matrix = {}

        # Priority weights (lower cost = higher priority)
        priority_weights = {
            'critical': 0.5,
            'high': 1.0,
            'medium': 2.0,
            'low': 4.0,
        }

        for agent in agents:
            for task in tasks:
                # Calculate Manhattan distance
                distance = self._manhattan_distance(agent.position, task.position)

                # Get priority weight
                priority_weight = priority_weights.get(task.priority, 2.0)

                # Resource penalty (if agent doesn't have enough pesticide)
                resource_penalty = 0
                if agent.pesticide_level < task.infestation_level:
                    resource_penalty = 10000  # Very high cost

                # Calculate total cost
                # Cost = distance * priority_weight + resource_penalty
                cost = distance * priority_weight + resource_penalty

                cost_matrix[(agent.agent_id, task.task_id)] = cost

        return cost_matrix

    def _manhattan_distance(self, pos1: Tuple[int, int], pos2: Tuple[int, int]) -> float:
        """Calculate Manhattan distance between two positions"""
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])
