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
        self.stuck_threshold = 2  # Reduced to 2 - detect stuck agents very quickly

        # Track agent positions over time
        self.agent_position_history = {}
        # Track how many times we've tried to fix each agent
        self.recalculation_attempts = {}  # agent_id -> count
        # Track agent target positions to detect bidirectional deadlocks
        self.agent_targets = {}  # agent_id -> target_position

    def check_preconditions(self) -> bool:
        """Check if there are conflicts to resolve"""
        # Check for failed tasks (excluding permanently failed ones)
        failed_tasks = self.kb.get_tasks_by_status('failed')
        # Filter out permanently failed tasks (failure_count >= 5)
        processable_failed_tasks = [t for t in failed_tasks if t.failure_count < 5]
        if processable_failed_tasks:
            return True

        # Check for stuck agents - ALWAYS check this
        stuck_agents = self._detect_stuck_agents()
        if stuck_agents:
            return True

        # Also check for agents in 'waiting' status for too long
        waiting_agents = []
        for agent in self.kb.get_all_agents():
            if agent.status == 'waiting':
                agent_id = agent.agent_id
                # Check if agent has been waiting for a while
                if agent_id not in self.agent_position_history:
                    self.agent_position_history[agent_id] = []
                history = self.agent_position_history[agent_id]
                if len(history) >= self.stuck_threshold:
                    # Been waiting for too long
                    waiting_agents.append(agent_id)
        
        if waiting_agents:
            return True

        return False

    def execute(self):
        """Resolve conflicts"""
        # Handle failed tasks
        self._handle_failed_tasks()

        # Handle stuck agents
        self._handle_stuck_agents()
        
        # Also handle agents stuck in 'waiting' status
        self._handle_waiting_agents()

    def _handle_failed_tasks(self):
        """Re-assign failed tasks"""
        failed_tasks = self.kb.get_tasks_by_status('failed')
        
        # Filter out permanently failed tasks (already have failure_count >= 5)
        # These should not be processed again
        processable_tasks = [t for t in failed_tasks if t.failure_count < 5]

        for task in processable_tasks:
            # Increment failure count
            failure_count = task.failure_count + 1
            
            # If task has failed too many times, mark it as permanently failed
            if failure_count >= 5:  # After 5 failures, give up on this task
                from datetime import datetime
                self.kb.update_task(
                    task.task_id,
                    status='failed',
                    assigned_agent_id=None,
                    failure_count=failure_count,
                    last_failure_at=datetime.now(),
                )
                print(f"Conflict resolved: Task {task.task_id} failed {failure_count} times - marking as permanently failed")
                continue
            
            # Reset task to pending with updated failure count
            from datetime import datetime
            self.kb.update_task(
                task.task_id,
                status='pending',
                assigned_agent_id=None,
                failure_count=failure_count,
                last_failure_at=datetime.now(),
            )

            print(f"Conflict resolved: Task {task.task_id} reset to pending (failure count: {failure_count})")

    def _detect_stuck_agents(self) -> List[str]:
        """Detect agents that haven't moved in a while, including bidirectional deadlocks"""
        stuck_agents = []
        
        # First, detect agents stuck in same position
        for agent in self.kb.get_all_agents():
            agent_id = agent.agent_id

            # Initialize history if needed
            if agent_id not in self.agent_position_history:
                self.agent_position_history[agent_id] = []

            # Add current position
            history = self.agent_position_history[agent_id]
            previous_pos = history[-1] if len(history) > 0 else None
            history.append(agent.position)

            # Keep only recent history
            max_history = self.stuck_threshold * 2
            if len(history) > max_history:
                history.pop(0)
            
            # If agent moved, reset recalculation counter
            if previous_pos is not None and previous_pos != agent.position:
                if agent_id in self.recalculation_attempts:
                    self.recalculation_attempts[agent_id] = 0
                # Clear target tracking on movement
                if agent_id in self.agent_targets:
                    del self.agent_targets[agent_id]

            # Check if stuck (same position for N steps)
            if len(history) >= self.stuck_threshold:
                # Check if all positions are the same (agent hasn't moved)
                if len(set(history)) == 1:
                    # More aggressive detection:
                    # 1. If agent has a task and path but hasn't moved - stuck
                    # 2. If agent is in 'waiting' status - stuck (reduced threshold)
                    # 3. If agent is in 'executing_task' or 'assigned' but not moving - stuck
                    # 4. If agent is returning_to_barn - stuck
                    
                    if agent.current_task_id:
                        # Agent has a task - should be moving
                        if agent.path and len(agent.path) > 0:
                            # Has path but not moving - stuck
                            stuck_agents.append(agent_id)
                            # Track target for bidirectional deadlock detection
                            if agent.path and len(agent.path) > agent.path_index:
                                self.agent_targets[agent_id] = agent.path[agent.path_index]
                        elif agent.status in ['executing_task', 'assigned', 'moving']:
                            # Thinks it's working but not moving - stuck
                            stuck_agents.append(agent_id)
                    elif agent.status == 'waiting':
                        # Been waiting - stuck (reduced threshold, no need for 2x)
                        stuck_agents.append(agent_id)
                    elif agent.status == 'returning_to_barn':
                        # Returning to barn but not moving - stuck
                        stuck_agents.append(agent_id)
                        # Track target (barn position)
                        command = self.kb.get_shared(f'command_{agent_id}')
                        if command and command.get('action') == 'refill_pesticide':
                            barn_pos = command.get('barn_position')
                            if barn_pos:
                                self.agent_targets[agent_id] = tuple(barn_pos)
                    elif agent.status in ['executing_task', 'assigned', 'moving']:
                        # Thinks it's moving but isn't - stuck
                        stuck_agents.append(agent_id)

        # Detect bidirectional deadlocks (agents blocking each other)
        bidirectional_deadlocks = self._detect_bidirectional_deadlocks(stuck_agents)
        if bidirectional_deadlocks:
            print(f"DEBUG: Detected bidirectional deadlock between agents: {bidirectional_deadlocks}")
            # Add all agents in deadlock to stuck list
            for deadlock_group in bidirectional_deadlocks:
                for agent_id in deadlock_group:
                    if agent_id not in stuck_agents:
                        stuck_agents.append(agent_id)

        return stuck_agents
    
    def _detect_bidirectional_deadlocks(self, stuck_agents: List[str]) -> List[List[str]]:
        """
        Detect bidirectional deadlocks where agents are blocking each other.
        
        Returns list of deadlock groups (agents that are mutually blocking).
        """
        deadlocks = []
        checked = set()
        
        for agent_id in stuck_agents:
            if agent_id in checked:
                continue
                
            agent = self.kb.get_agent(agent_id)
            if not agent:
                continue
            
            # Get agent's target position
            target = None
            if agent_id in self.agent_targets:
                target = self.agent_targets[agent_id]
            elif agent.path and len(agent.path) > agent.path_index:
                target = agent.path[agent.path_index]
            elif agent.status == 'returning_to_barn':
                command = self.kb.get_shared(f'command_{agent_id}')
                if command and command.get('action') == 'refill_pesticide':
                    barn_pos = command.get('barn_position')
                    if barn_pos:
                        target = tuple(barn_pos)
            
            if not target:
                continue
            
            # Check if another stuck agent is at our target position
            blocking_agents = []
            for other_id in stuck_agents:
                if other_id == agent_id or other_id in checked:
                    continue
                    
                other_agent = self.kb.get_agent(other_id)
                if not other_agent:
                    continue
                
                # Check if other agent is at our target
                if other_agent.position == target:
                    blocking_agents.append(other_id)
                    
                    # Check if we're blocking them too (bidirectional)
                    other_target = None
                    if other_id in self.agent_targets:
                        other_target = self.agent_targets[other_id]
                    elif other_agent.path and len(other_agent.path) > other_agent.path_index:
                        other_target = other_agent.path[other_agent.path_index]
                    
                    if other_target and agent.position == other_target:
                        # Bidirectional deadlock detected!
                        deadlock_group = [agent_id, other_id]
                        deadlocks.append(deadlock_group)
                        checked.add(agent_id)
                        checked.add(other_id)
                        print(f"DEBUG: Bidirectional deadlock: Agent {agent_id} at {agent.position} wants {target}, Agent {other_id} at {other_agent.position} wants {other_target}")
        
        return deadlocks

    def _handle_stuck_agents(self):
        """Handle agents that are stuck, with special handling for bidirectional deadlocks"""
        stuck_agents = self._detect_stuck_agents()
        
        if stuck_agents:
            print(f"DEBUG: Detected {len(stuck_agents)} stuck agents: {stuck_agents}")
        
        # Check for bidirectional deadlocks first
        bidirectional_deadlocks = self._detect_bidirectional_deadlocks(stuck_agents)
        
        # Handle bidirectional deadlocks aggressively - reset one agent in each deadlock
        for deadlock_group in bidirectional_deadlocks:
            if len(deadlock_group) >= 2:
                # Reset the first agent in the deadlock to break it
                agent_to_reset = deadlock_group[0]
                print(f"DEBUG: Breaking bidirectional deadlock by resetting agent {agent_to_reset}")
                self._force_reset_agent(agent_to_reset)
                # Remove from stuck list to avoid double processing
                if agent_to_reset in stuck_agents:
                    stuck_agents.remove(agent_to_reset)

        for agent_id in stuck_agents:
            agent = self.kb.get_agent(agent_id)

            if not agent:
                continue

            # If agent has a task, mark task as failed and reset agent
            if agent.current_task_id:
                task = self.kb.get_task(agent.current_task_id)

                if task and task.failure_count < 5:  # Only process if not permanently failed
                    # Increment failure count
                    failure_count = task.failure_count + 1
                    
                    # If task has failed too many times, mark as permanently failed
                    if failure_count >= 5:
                        from datetime import datetime
                        self.kb.update_task(
                            task.task_id,
                            status='failed',
                            assigned_agent_id=None,
                            failure_count=failure_count,
                            last_failure_at=datetime.now(),
                        )
                        print(f"Conflict resolved: Task {task.task_id} failed {failure_count} times - marking as permanently failed")
                    else:
                        # Mark task as pending again with updated failure count
                        from datetime import datetime
                        self.kb.update_task(
                            task.task_id,
                            status='pending',
                            assigned_agent_id=None,
                            failure_count=failure_count,
                            last_failure_at=datetime.now(),
                        )
                        print(f"Conflict resolved: Task {task.task_id} reset to pending (failure count: {failure_count})")
                elif task and task.failure_count >= 5:
                    # Task already permanently failed, just clear agent assignment
                    self.kb.update_task(
                        task.task_id,
                        assigned_agent_id=None,
                    )

            # Check how many times we've tried to fix this agent
            if agent_id not in self.recalculation_attempts:
                self.recalculation_attempts[agent_id] = 0
            
            self.recalculation_attempts[agent_id] += 1
            
            # If we've tried too many times (2), give up and reset (reduced from 3)
            if self.recalculation_attempts[agent_id] >= 2:
                print(f"DEBUG: Agent {agent_id} stuck after {self.recalculation_attempts[agent_id]} recalculation attempts - resetting completely")
                # Reset counter
                self.recalculation_attempts[agent_id] = 0
                # Continue to reset logic below
            else:
                # Try to recalculate path first if agent has a task
                if agent.current_task_id:
                    task = self.kb.get_task(agent.current_task_id)
                    if task:
                        # Try to recalculate path using PathPlanner
                        from .path_planner import PathPlannerKS
                        # Create a temporary PathPlanner instance to recalculate
                        path_planner = PathPlannerKS(self.kb)
                        new_path = path_planner.recalculate_path(agent_id)
                        
                        if new_path and len(new_path) > 0:
                            # New path found - reset position history and continue
                            self.agent_position_history[agent_id] = []
                            print(f"Conflict resolved: Stuck agent {agent_id} - recalculated path (attempt {self.recalculation_attempts[agent_id]}), continuing")
                            return  # Don't reset agent, let it continue with new path
                
                # Special handling for agents returning to barn
                if agent.status == 'returning_to_barn':
                    command = self.kb.get_shared(f'command_{agent_id}')
                    if command and command.get('action') == 'refill_pesticide':
                        barn_position = command.get('barn_position')
                        if barn_position:
                            # Try direct movement without pathfinding
                            print(f"DEBUG: Agent {agent_id} stuck returning to barn - trying direct movement")
                            # Calculate simple direction
                            x, z = agent.position
                            bx, bz = barn_position
                            
                            # Try to move one step closer
                            if abs(bx - x) > abs(bz - z):
                                # Move horizontally
                                new_x = x + (1 if bx > x else -1)
                                alt_pos = (new_x, z)
                            else:
                                # Move vertically
                                new_z = z + (1 if bz > z else -1)
                                alt_pos = (x, new_z)
                            
                            # Check if alternative position is free
                            all_agents = self.kb.get_all_agents()
                            position_free = True
                            for other_agent in all_agents:
                                if other_agent.agent_id != agent_id and other_agent.position == alt_pos:
                                    position_free = False
                                    break
                            
                            if position_free:
                                # Move directly
                                self.kb.update_agent(
                                    agent_id,
                                    position=alt_pos,
                                    path=[],
                                    path_index=0,
                                    status='returning_to_barn',
                                )
                                self.agent_position_history[agent_id] = []
                                self.recalculation_attempts[agent_id] = 0
                                print(f"DEBUG: Agent {agent_id} moved directly to {alt_pos}")
                                return
            
            # If path recalculation failed or no task, reset agent to idle
            self.kb.update_agent(
                agent_id,
                status='idle',
                current_task_id=None,
                path=[],
                path_index=0,
            )

            # Clear agent command
            self.kb.delete_shared(f'command_{agent_id}')

            # If agent had a task, mark it as failed
            if agent.current_task_id:
                task = self.kb.get_task(agent.current_task_id)
                if task:
                    failure_count = task.failure_count + 1
                    from datetime import datetime
                    if failure_count >= 5:
                        # Permanently failed
                        self.kb.update_task(
                            agent.current_task_id,
                            status='failed',
                            assigned_agent_id=None,
                            failure_count=failure_count,
                        )
                    else:
                        # Reset to pending with failure count
                        self.kb.update_task(
                            agent.current_task_id,
                            status='pending',
                            assigned_agent_id=None,
                            failure_count=failure_count,
                            last_failure_at=datetime.now(),
                        )

            # Clear position history and reset recalculation counter
            self.agent_position_history[agent_id] = []
            self.recalculation_attempts[agent_id] = 0

            # Emit event
            self.kb.emit_event(EventType.CONFLICT_DETECTED, {
                'type': 'stuck_agent',
                'agent_id': agent_id,
                'resolution': 'reset_to_idle',
            })

            print(f"Conflict resolved: Stuck agent {agent_id} reset to idle")
    
    def _force_reset_agent(self, agent_id: str):
        """Forcefully reset an agent to break deadlocks"""
        agent = self.kb.get_agent(agent_id)
        if not agent:
            return
        
        # Reset agent completely
        self.kb.update_agent(
            agent_id,
            status='idle',
            current_task_id=None,
            path=[],
            path_index=0,
        )
        
        # Clear command
        self.kb.delete_shared(f'command_{agent_id}')
        
        # Clear history and counters
        self.agent_position_history[agent_id] = []
        if agent_id in self.recalculation_attempts:
            self.recalculation_attempts[agent_id] = 0
        if agent_id in self.agent_targets:
            del self.agent_targets[agent_id]
        
        # If had a task, mark it appropriately
        if agent.current_task_id:
            task = self.kb.get_task(agent.current_task_id)
            if task and task.failure_count < 5:
                from datetime import datetime
                failure_count = task.failure_count + 1
                self.kb.update_task(
                    agent.current_task_id,
                    status='pending',
                    assigned_agent_id=None,
                    failure_count=failure_count,
                    last_failure_at=datetime.now(),
                )
        
        print(f"DEBUG: Force reset agent {agent_id} to break deadlock")
    
    def _handle_waiting_agents(self):
        """Handle agents that have been waiting too long (potential deadlock)"""
        waiting_agents = []
        for agent in self.kb.get_all_agents():
            # Check both 'waiting' and 'returning_to_barn' status (deadlock común)
            if agent.status in ['waiting', 'returning_to_barn']:
                agent_id = agent.agent_id
                # Check position history
                if agent_id not in self.agent_position_history:
                    self.agent_position_history[agent_id] = []
                history = self.agent_position_history[agent_id]
                
                # If agent has been in same position for too long
                if len(history) >= self.stuck_threshold:
                    if len(set(history)) == 1:  # Same position
                        waiting_agents.append(agent_id)
        
        for agent_id in waiting_agents:
            agent = self.kb.get_agent(agent_id)
            if not agent:
                continue
            
            print(f"DEBUG: Agent {agent_id} stuck in '{agent.status}' status at {agent.position}")
            
            # Special handling for agents returning to barn
            if agent.status == 'returning_to_barn':
                # Get barn position from command
                command = self.kb.get_shared(f'command_{agent_id}')
                if command and command.get('action') == 'refill_pesticide':
                    barn_position = command.get('barn_position')
                    if barn_position:
                        # Try to recalculate path to barn
                        from .path_planner import PathPlannerKS
                        path_planner = PathPlannerKS(self.kb)
                        new_path = path_planner._calculate_path(agent.position, barn_position, agent.agent_type)
                        
                        if new_path and len(new_path) > 0:
                            # New path found - update agent
                            self.kb.update_agent(
                                agent_id,
                                path=new_path,
                                path_index=0,
                                status='returning_to_barn',
                            )
                            self.agent_position_history[agent_id] = []
                            # Reset recalculation counter on success
                            if agent_id in self.recalculation_attempts:
                                self.recalculation_attempts[agent_id] = 0
                            print(f"DEBUG: Agent {agent_id} returning to barn - recalculated path, continuing")
                            continue
                        
                        # If recalculation failed, try direct movement
                        print(f"DEBUG: Agent {agent_id} returning to barn - path recalculation failed, trying direct movement")
                        # Calculate simple direction
                        x, z = agent.position
                        bx, bz = barn_position
                        
                        # Try to move one step closer
                        if abs(bx - x) > abs(bz - z):
                            # Move horizontally
                            new_x = x + (1 if bx > x else -1)
                            alt_pos = (new_x, z)
                        else:
                            # Move vertically
                            new_z = z + (1 if bz > z else -1)
                            alt_pos = (x, new_z)
                        
                        # Check if alternative position is free
                        all_agents = self.kb.get_all_agents()
                        position_free = True
                        for other_agent in all_agents:
                            if other_agent.agent_id != agent_id and other_agent.position == alt_pos:
                                position_free = False
                                break
                        
                        if position_free:
                            # Move directly
                            self.kb.update_agent(
                                agent_id,
                                position=alt_pos,
                                path=[],
                                path_index=0,
                                status='returning_to_barn',
                            )
                            self.agent_position_history[agent_id] = []
                            if agent_id in self.recalculation_attempts:
                                self.recalculation_attempts[agent_id] = 0
                            print(f"DEBUG: Agent {agent_id} moved directly to {alt_pos}")
                            continue
                
                # If recalculation failed or no command, try to move directly
                if command and command.get('action') == 'refill_pesticide':
                    barn_position = command.get('barn_position')
                    if barn_position:
                        # Try simple direct movement (will be handled by agent next step)
                        self.agent_position_history[agent_id] = []
                        print(f"DEBUG: Agent {agent_id} returning to barn - will try direct movement")
                        continue
            
            # If agent has a task, try to recalculate path or reset
            if agent.current_task_id:
                task = self.kb.get_task(agent.current_task_id)
                if task:
                    # Try to recalculate path
                    from .path_planner import PathPlannerKS
                    path_planner = PathPlannerKS(self.kb)
                    new_path = path_planner.recalculate_path(agent_id)
                    
                    if new_path and len(new_path) > 0:
                        # New path found
                        self.agent_position_history[agent_id] = []
                        print(f"DEBUG: Agent {agent_id} - recalculated path, continuing")
                        continue
            
            # If no path or recalculation failed, reset agent
            self.kb.update_agent(
                agent_id,
                status='idle',
                current_task_id=None,
                path=[],
                path_index=0,
            )
            self.kb.delete_shared(f'command_{agent_id}')
            self.agent_position_history[agent_id] = []
            
            # If had a task, mark it appropriately
            if agent.current_task_id:
                task = self.kb.get_task(agent.current_task_id)
                if task and task.failure_count < 5:
                    from datetime import datetime
                    failure_count = task.failure_count + 1
                    self.kb.update_task(
                        agent.current_task_id,
                        status='pending',
                        assigned_agent_id=None,
                        failure_count=failure_count,
                        last_failure_at=datetime.now(),
                    )
                    print(f"DEBUG: Agent {agent_id} waiting too long - reset task {agent.current_task_id}")

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
