"""
Base Knowledge Source class

All Knowledge Sources inherit from this class and implement:
- triggers: Which events they respond to
- check_preconditions: Whether they should execute
- execute: Their main logic
"""

from abc import ABC, abstractmethod
from typing import List, Set
from ..knowledge_base import KnowledgeBase, Event, EventType


class KnowledgeSource(ABC):
    """
    Abstract base class for Knowledge Sources.

    A Knowledge Source is a specialist that:
    - Monitors specific aspects of the KnowledgeBase
    - Responds to certain events/triggers
    - Contributes its expertise when activated
    """

    def __init__(self, knowledge_base: KnowledgeBase):
        """
        Initialize the Knowledge Source.

        Args:
            knowledge_base: The KnowledgeBase to read/write
        """
        self.kb = knowledge_base

        # Configuration
        self.priority = 5  # Higher = more important (0-10)
        self.always_run = False  # If True, runs every cycle
        self.triggers: Set[EventType] = set()  # Events this KS responds to

    @abstractmethod
    def check_preconditions(self) -> bool:
        """
        Check if this KS should execute.

        Returns:
            True if preconditions are met, False otherwise
        """
        pass

    @abstractmethod
    def execute(self):
        """
        Execute the main logic of this Knowledge Source.

        This method should:
        1. Read from the KnowledgeBase
        2. Perform its specialized computation
        3. Write results back to the KnowledgeBase
        """
        pass

    def should_activate(self, event: Event) -> bool:
        """
        Determine if this KS should activate based on an event.

        Override this for more complex activation logic.

        Args:
            event: The event that occurred

        Returns:
            True if this KS should activate
        """
        return event.event_type in self.triggers

    def __repr__(self):
        return f"<{self.__class__.__name__} priority={self.priority}>"
