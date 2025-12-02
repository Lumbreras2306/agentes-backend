"""
Blackboard - Main coordinator for the Blackboard system

The Blackboard acts as the central hub that connects the KnowledgeBase
with the Control Component and provides a unified interface for the system.
"""

from typing import Optional, List
from .knowledge_base import KnowledgeBase, AgentState, TaskState, Event, EventType
from .control import ControlComponent


class Blackboard:
    """
    Main Blackboard class that coordinates all components.

    This class:
    - Owns the KnowledgeBase
    - Owns the Control Component
    - Provides high-level API for agents and the simulation
    - Manages the execution cycle
    """

    def __init__(self, world_instance, blackboard_service=None):
        """
        Initialize the Blackboard system.

        Args:
            world_instance: Django World model instance
            blackboard_service: Legacy BlackboardService for compatibility
        """
        self.world_instance = world_instance
        self.blackboard_service = blackboard_service  # For legacy compatibility

        # Initialize KnowledgeBase
        self.knowledge_base = KnowledgeBase(world_instance)

        # Initialize Control Component (will be set up with KS later)
        self.control = ControlComponent(self.knowledge_base)

        # Execution state
        self.is_running = False
        self.step_count = 0

    def setup(self):
        """
        Set up the Blackboard system.
        This should be called after all agents are registered.
        """
        # Initialize Knowledge Sources in the Control Component
        self.control.setup()

    def register_agent(self, agent_state: AgentState):
        """Register an agent in the system"""
        self.knowledge_base.register_agent(agent_state)

    def step(self):
        """
        Execute one step of the Blackboard system.

        This triggers the Control Component to:
        1. Check for changes in the KnowledgeBase
        2. Activate appropriate Knowledge Sources
        3. Execute their logic
        """
        self.step_count += 1
        self.control.execute_cycle()

    def start(self):
        """Start the Blackboard system"""
        self.is_running = True
        self.setup()

    def stop(self):
        """Stop the Blackboard system"""
        self.is_running = False

    # ========== CONVENIENCE METHODS ==========

    def get_agent_command(self, agent_id: str) -> Optional[dict]:
        """
        Get the next command for an agent.

        This is called by agents in their perceive() method.
        """
        return self.knowledge_base.get_shared(f'command_{agent_id}')

    def clear_agent_command(self, agent_id: str):
        """Clear an agent's command after execution"""
        self.knowledge_base.delete_shared(f'command_{agent_id}')

    def report_agent_state(self, agent_id: str, **updates):
        """
        Report agent state updates.

        This is called by agents in their report() method.
        """
        self.knowledge_base.update_agent(agent_id, **updates)

    def report_event(self, event_type: EventType, data: dict, source: str):
        """Report a custom event"""
        self.knowledge_base.emit_event(event_type, data, source)

    # ========== QUERY METHODS ==========

    def get_statistics(self):
        """Get overall system statistics"""
        stats = self.knowledge_base.get_statistics()
        stats['step_count'] = self.step_count
        return stats

    def get_pending_tasks(self) -> List[TaskState]:
        """Get all pending tasks"""
        return self.knowledge_base.get_pending_tasks()

    def get_idle_agents(self, agent_type: Optional[str] = None) -> List[AgentState]:
        """Get all idle agents"""
        return self.knowledge_base.get_idle_agents(agent_type)

    # ========== LEGACY COMPATIBILITY ==========

    def sync_to_django(self):
        """
        Sync the KnowledgeBase state to Django models.

        This is called periodically to keep the database in sync
        with the in-memory state.
        """
        from agents.models import Agent as AgentModel
        from agents.models import BlackboardTask, TaskStatus

        # Update agent models
        for agent_state in self.knowledge_base.get_all_agents():
            try:
                agent_model = AgentModel.objects.get(agent_id=agent_state.agent_id)
                agent_model.position_x = agent_state.position[0]
                agent_model.position_z = agent_state.position[1]
                agent_model.status = agent_state.status
                agent_model.tasks_completed = agent_state.tasks_completed
                agent_model.fields_fumigated = agent_state.fields_fumigated
                agent_model.metadata = {
                    'pesticide_level': agent_state.pesticide_level,
                    'fields_analyzed': agent_state.fields_analyzed,
                    **agent_state.metadata
                }
                agent_model.save()
            except AgentModel.DoesNotExist:
                pass

        # Update task models
        for task_state in self.knowledge_base.get_all_tasks():
            try:
                task_model = BlackboardTask.objects.get(id=task_state.task_id)

                # Map status
                status_map = {
                    'pending': TaskStatus.PENDING,
                    'assigned': TaskStatus.ASSIGNED,
                    'in_progress': TaskStatus.IN_PROGRESS,
                    'completed': TaskStatus.COMPLETED,
                    'failed': TaskStatus.FAILED,
                }
                task_model.status = status_map.get(task_state.status, TaskStatus.PENDING)

                task_model.assigned_agent_id = task_state.assigned_agent_id
                task_model.assigned_at = task_state.assigned_at
                task_model.completed_at = task_state.completed_at
                task_model.save()
            except BlackboardTask.DoesNotExist:
                pass

        # Update world infestation grid
        self.world_instance.infestation_grid = self.knowledge_base.world_state.infestation_grid
        self.world_instance.save()

    def sync_from_django(self):
        """
        Load state from Django models into the KnowledgeBase.

        This is useful for resuming a simulation.
        """
        from agents.models import BlackboardTask

        # Load tasks from Django
        tasks = BlackboardTask.objects.filter(world=self.world_instance)
        for task_model in tasks:
            # Map status
            status_map = {
                'pending': 'pending',
                'assigned': 'assigned',
                'in_progress': 'in_progress',
                'completed': 'completed',
                'failed': 'failed',
            }

            task_state = TaskState(
                task_id=str(task_model.id),
                position=(task_model.position_x, task_model.position_z),
                infestation_level=task_model.infestation_level,
                priority=task_model.priority,
                status=status_map.get(task_model.status, 'pending'),
                assigned_agent_id=task_model.assigned_agent_id,
                created_at=task_model.created_at,
                assigned_at=task_model.assigned_at,
                completed_at=task_model.completed_at,
                metadata=task_model.metadata
            )
            self.knowledge_base.create_task(task_state)
