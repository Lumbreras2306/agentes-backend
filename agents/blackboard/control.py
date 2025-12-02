"""
Control Component - Orchestrates Knowledge Sources

The Control Component decides which Knowledge Sources to activate
based on the current state of the KnowledgeBase.
"""

from typing import List, Dict, Set
from .knowledge_base import KnowledgeBase, EventType


class ControlComponent:
    """
    Control Component that orchestrates Knowledge Sources.

    Responsibilities:
    - Monitor KnowledgeBase for changes
    - Decide which Knowledge Sources to activate
    - Manage execution order and priorities
    - Prevent infinite loops
    """

    def __init__(self, knowledge_base: KnowledgeBase):
        """
        Initialize the Control Component.

        Args:
            knowledge_base: The KnowledgeBase to monitor
        """
        self.kb = knowledge_base
        self.knowledge_sources = []
        self.ks_by_trigger = {}  # Map event types to KS that care about them

        # Execution control
        self.max_ks_activations_per_cycle = 10
        self.executed_ks_this_cycle = set()

    def setup(self):
        """
        Set up the Control Component with all Knowledge Sources.
        This is called during Blackboard initialization.
        """
        # Import Knowledge Sources
        from .knowledge_sources import (
            TaskPlannerKS,
            TaskAllocatorKS,
            ResourceManagerKS,
            PathPlannerKS,
            ConflictResolverKS,
        )

        # Initialize Knowledge Sources (ScoutCoordinatorKS eliminado)
        self.knowledge_sources = [
            TaskPlannerKS(self.kb),
            TaskAllocatorKS(self.kb),
            ResourceManagerKS(self.kb),
            PathPlannerKS(self.kb),
            ConflictResolverKS(self.kb),
        ]

        # Build trigger map
        self._build_trigger_map()

    def _build_trigger_map(self):
        """Build a map of event types to interested Knowledge Sources"""
        self.ks_by_trigger = {event_type: [] for event_type in EventType}

        for ks in self.knowledge_sources:
            for event_type in ks.triggers:
                self.ks_by_trigger[event_type].append(ks)

    def execute_cycle(self):
        """
        Execute one cycle of the Control Component.

        This:
        1. Gets recent events from the KnowledgeBase
        2. Determines which KS should be activated
        3. Executes them in priority order
        4. Prevents infinite loops
        """
        self.executed_ks_this_cycle = set()

        # Get recent events (since last cycle)
        recent_events = self.kb.get_recent_events(limit=100)

        # Determine which KS to activate based on events
        ks_to_activate = set()

        for event in recent_events:
            if event.event_type in self.ks_by_trigger:
                for ks in self.ks_by_trigger[event.event_type]:
                    if ks.should_activate(event):
                        ks_to_activate.add(ks)

        # Always run certain KS (periodic checks)
        for ks in self.knowledge_sources:
            if ks.always_run:
                ks_to_activate.add(ks)

        # Sort by priority
        ks_to_activate = sorted(ks_to_activate, key=lambda ks: ks.priority, reverse=True)

        # Execute KS
        activation_count = 0
        for ks in ks_to_activate:
            if activation_count >= self.max_ks_activations_per_cycle:
                break

            # Check if KS was already executed this cycle
            if ks in self.executed_ks_this_cycle:
                continue

            # Check preconditions
            if not ks.check_preconditions():
                continue

            # Execute
            try:
                ks.execute()
                self.executed_ks_this_cycle.add(ks)
                activation_count += 1
            except Exception as e:
                print(f"Error executing {ks.__class__.__name__}: {e}")

    def force_activate(self, ks_class_name: str):
        """
        Force activate a specific Knowledge Source by name.

        Useful for testing or manual intervention.
        """
        for ks in self.knowledge_sources:
            if ks.__class__.__name__ == ks_class_name:
                if ks.check_preconditions():
                    ks.execute()
                    return True
        return False

    def get_status(self) -> Dict:
        """Get status of all Knowledge Sources"""
        return {
            'total_ks': len(self.knowledge_sources),
            'ks_details': [
                {
                    'name': ks.__class__.__name__,
                    'priority': ks.priority,
                    'always_run': ks.always_run,
                    'triggers': [t.value for t in ks.triggers],
                }
                for ks in self.knowledge_sources
            ]
        }
