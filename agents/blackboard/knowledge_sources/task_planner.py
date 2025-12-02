"""
TaskPlannerKS - Creates fumigation tasks from discovered infestations

This Knowledge Source monitors field discoveries and creates
appropriate fumigation tasks in the KnowledgeBase.
"""

from .base import KnowledgeSource
from ..knowledge_base import EventType, TaskState
import uuid
from datetime import datetime


class TaskPlannerKS(KnowledgeSource):
    """
    TaskPlannerKS creates fumigation tasks when infestations are discovered.

    Triggers:
    - FIELD_DISCOVERED: When scout discovers an infested field

    Logic:
    - Checks if task already exists for the position
    - Calculates priority based on infestation level
    - Creates TaskState in KnowledgeBase
    """

    def __init__(self, knowledge_base):
        super().__init__(knowledge_base)
        self.priority = 9  # High priority - create tasks quickly
        self.triggers = {EventType.FIELD_DISCOVERED}
        self.min_infestation = 1  # Minimum infestation to create task

    def check_preconditions(self) -> bool:
        """Check if there are field discoveries to process"""
        # Check recent FIELD_DISCOVERED events
        recent_discoveries = self.kb.get_recent_events(EventType.FIELD_DISCOVERED, limit=50)

        # Filter out already processed ones
        unprocessed = []
        for event in recent_discoveries:
            position = event.data.get('position')
            if position and not self._task_exists_for_position(position):
                unprocessed.append(event)

        return len(unprocessed) > 0

    def execute(self):
        """Create tasks for discovered infestations"""
        # Get recent field discoveries
        recent_discoveries = self.kb.get_recent_events(EventType.FIELD_DISCOVERED, limit=50)

        for event in recent_discoveries:
            position = event.data.get('position')
            infestation = event.data.get('infestation', 0)
            crop = event.data.get('crop')

            if not position or infestation < self.min_infestation:
                continue

            # Check if task already exists
            if self._task_exists_for_position(position):
                continue

            # Calculate priority based on infestation level
            if infestation >= 80:
                priority = 'critical'
            elif infestation >= 50:
                priority = 'high'
            elif infestation >= 20:
                priority = 'medium'
            else:
                priority = 'low'

            # Create task
            task_state = TaskState(
                task_id=str(uuid.uuid4()),
                position=tuple(position),
                infestation_level=infestation,
                priority=priority,
                status='pending',
                metadata={
                    'crop_type': crop,
                    'discovered_by': event.source,
                    'discovered_at': event.timestamp.isoformat(),
                }
            )

            self.kb.create_task(task_state)

            # Also create in Django (for persistence)
            self._create_django_task(task_state)

    def _task_exists_for_position(self, position) -> bool:
        """Check if a task already exists for this position"""
        x, z = position
        for task in self.kb.get_all_tasks():
            if task.position == (x, z) and task.status in ['pending', 'assigned', 'in_progress']:
                return True
        return False

    def _create_django_task(self, task_state: TaskState):
        """Create task in Django database for persistence"""
        from agents.models import BlackboardTask, TaskPriority, TaskStatus

        # Map priority
        priority_map = {
            'low': TaskPriority.LOW,
            'medium': TaskPriority.MEDIUM,
            'high': TaskPriority.HIGH,
            'critical': TaskPriority.CRITICAL,
        }

        try:
            BlackboardTask.objects.create(
                id=task_state.task_id,
                world=self.kb.world_instance,
                position_x=task_state.position[0],
                position_z=task_state.position[1],
                infestation_level=task_state.infestation_level,
                priority=priority_map.get(task_state.priority, TaskPriority.MEDIUM),
                status=TaskStatus.PENDING,
                metadata=task_state.metadata,
            )
        except Exception as e:
            print(f"Error creating Django task: {e}")
