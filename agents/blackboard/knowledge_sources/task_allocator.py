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
        pending_tasks = self._get_assignable_tasks()

        return len(idle_fumigators) > 0 and len(pending_tasks) > 0
    
    def _get_assignable_tasks(self) -> List[TaskState]:
        """
        Get tasks that can be assigned, filtering out:
        - Tasks that have failed too many times
        - Tasks that failed recently (cooldown period)
        """
        from datetime import datetime, timedelta
        
        pending_tasks = self.kb.get_pending_tasks()
        assignable = []
        
        for task in pending_tasks:
            # Skip tasks that have failed too many times
            if task.failure_count >= 5:
                continue
            
            # Skip tasks that failed recently (cooldown of 10 steps = ~5 seconds)
            if task.last_failure_at:
                time_since_failure = datetime.now() - task.last_failure_at
                # Cooldown: wait at least 5 seconds before retrying
                if time_since_failure < timedelta(seconds=5):
                    continue
            
            # Skip tasks with high failure count unless enough time has passed
            if task.failure_count >= 3:
                if task.last_failure_at:
                    time_since_failure = datetime.now() - task.last_failure_at
                    # For high failure count tasks, wait longer (15 seconds)
                    if time_since_failure < timedelta(seconds=15):
                        continue
            
            assignable.append(task)
        
        return assignable

    def execute(self):
        """Assign pending tasks to idle fumigators optimally"""
        idle_fumigators = self.kb.get_idle_agents('fumigator')
        pending_tasks = self._get_assignable_tasks()

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

        # Get infestation grid for pesticide validation
        infestation_grid = self.kb.world_state.infestation_grid
        grid = self.kb.world_state.grid

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

                    # Check if agent has enough pesticide for the FULL path (not just destination)
                    pesticide_needed = self._estimate_pesticide_needed(
                        agent.position,
                        task.position,
                        grid,
                        infestation_grid,
                        task.infestation_level
                    )
                    
                    # Si no tiene suficiente pesticida, NO asignar - el agente debe regresar al barn
                    if agent.pesticide_level < pesticide_needed:
                        continue  # Skip this assignment - not enough pesticide for full path
                    
                    # Si el pesticida es muy bajo (< 20% del necesario), también evitar asignar
                    # para que el agente regrese a recargar
                    if agent.pesticide_level < pesticide_needed * 1.2:
                        continue  # Very low pesticide - should refill first

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
        - Distance: Estimated path cost considering field weights (prefer roads)
        - Priority: Higher priority tasks have lower cost
        - Resource: Tasks requiring more pesticide than agent has get high cost
        - Pesticide efficiency: Consider pesticide needed along the path

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

        # Get field weights from knowledge base for path estimation
        field_weights = self.kb.world_state.field_weights
        grid = self.kb.world_state.grid

        # Get infestation grid for pesticide calculation
        infestation_grid = self.kb.world_state.infestation_grid

        for agent in agents:
            for task in tasks:
                # Estimate path cost considering field weights
                # Use a heuristic that prefers roads and avoids high-weight fields
                estimated_path_cost = self._estimate_path_cost(
                    agent.position,
                    task.position,
                    grid,
                    field_weights
                )

                # Estimate pesticide needed for the entire path
                # This includes infestation in cells along the path AND the destination
                pesticide_needed = self._estimate_pesticide_needed(
                    agent.position,
                    task.position,
                    grid,
                    infestation_grid,
                    task.infestation_level
                )

                # Get priority weight
                priority_weight = priority_weights.get(task.priority, 2.0)

                # Resource penalty (if agent doesn't have enough pesticide for the full path)
                resource_penalty = 0
                if agent.pesticide_level < pesticide_needed:
                    # Very high cost - agent should refill instead
                    resource_penalty = 50000  # Much higher than path cost
                elif agent.pesticide_level < pesticide_needed * 1.2:
                    # Medium penalty if pesticide is barely enough (risky)
                    resource_penalty = 1000

                # Calculate total cost
                # Cost = path_cost * priority_weight + resource_penalty
                cost = estimated_path_cost * priority_weight + resource_penalty

                cost_matrix[(agent.agent_id, task.task_id)] = cost

        return cost_matrix
    
    def _estimate_path_cost(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        grid: List[List[int]],
        field_weights: Dict[Tuple[int, int], float]
    ) -> float:
        """
        Estimate path cost using a heuristic that considers:
        - Manhattan distance
        - Field weights (avoid high-weight fields)
        - Road preference (roads have low cost)
        
        This is a fast approximation - actual pathfinding happens later.
        """
        from world.world_generator import TileType
        
        # Manhattan distance as base
        manhattan_dist = self._manhattan_distance(start, end)
        
        # Estimate cost along a straight-line path
        # This is a heuristic - actual pathfinding will optimize later
        x0, z0 = start
        x1, z1 = end
        
        # Sample points along the path to estimate field weights
        total_weight = 0.0
        samples = max(1, int(manhattan_dist / 2))  # Sample every 2 cells
        
        for i in range(samples + 1):
            t = i / samples if samples > 0 else 0
            x = int(x0 + (x1 - x0) * t)
            z = int(z0 + (z1 - z0) * t)
            
            # Check bounds
            if 0 <= z < len(grid) and 0 <= x < len(grid[z]):
                tile = grid[z][x]
                
                if tile == TileType.ROAD:
                    # Roads have very low cost
                    total_weight += 1.0
                elif tile == TileType.FIELD:
                    # Fields have base cost + dynamic weight
                    field_weight = field_weights.get((x, z), 0.0)
                    total_weight += 10.0 + field_weight
                else:
                    # Other tiles
                    total_weight += 1.0
        
        # Average weight per cell
        avg_weight = total_weight / (samples + 1) if samples > 0 else 1.0
        
        # Estimated cost = distance * average weight
        return manhattan_dist * avg_weight

    def _estimate_pesticide_needed(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        grid: List[List[int]],
        infestation_grid: List[List[int]],
        destination_infestation: int
    ) -> int:
        """
        Estimate total pesticide needed to complete a task, including:
        - Pesticide needed for cells along the path (if they have infestation >= 10)
        - Pesticide needed for the destination
        
        Args:
            start: Starting position
            end: Destination position
            grid: World grid
            infestation_grid: Infestation levels
            destination_infestation: Infestation level at destination
            
        Returns:
            Total pesticide needed (int)
        """
        from world.world_generator import TileType
        
        total_pesticide = 0
        
        # Add pesticide needed for destination
        total_pesticide += destination_infestation
        
        # Estimate pesticide needed along the path
        # Sample cells along a straight-line path to estimate infestation
        x0, z0 = start
        x1, z1 = end
        
        manhattan_dist = self._manhattan_distance(start, end)
        samples = max(1, int(manhattan_dist / 2))  # Sample every 2 cells
        
        for i in range(samples + 1):
            t = i / samples if samples > 0 else 0
            x = int(x0 + (x1 - x0) * t)
            z = int(z0 + (z1 - z0) * t)
            
            # Skip start and end positions (end already counted)
            if (x, z) == start or (x, z) == end:
                continue
            
            # Check bounds
            if 0 <= z < len(grid) and 0 <= x < len(grid[z]):
                tile = grid[z][x]
                
                # Only count infestation in fields (not roads)
                if tile == TileType.FIELD:
                    if 0 <= z < len(infestation_grid) and 0 <= x < len(infestation_grid[z]):
                        infestation = infestation_grid[z][x]
                        # Only count if infestation is significant (>= 10)
                        if infestation >= 10:
                            total_pesticide += infestation
        
        # Return total with a small safety margin (5%) to account for path variations
        return int(total_pesticide * 1.05)
    
    def _manhattan_distance(self, pos1: Tuple[int, int], pos2: Tuple[int, int]) -> float:
        """Calculate Manhattan distance between two positions"""
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])
