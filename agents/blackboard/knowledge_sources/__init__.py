"""
Knowledge Sources for the Blackboard System

Each Knowledge Source is a specialist that monitors specific aspects
of the KnowledgeBase and contributes its expertise when triggered.
"""

from .base import KnowledgeSource
from .task_planner import TaskPlannerKS
from .task_allocator import TaskAllocatorKS
from .resource_manager import ResourceManagerKS
from .conflict_resolver import ConflictResolverKS
from .path_planner import PathPlannerKS
from .scout_coordinator import ScoutCoordinatorKS

__all__ = [
    'KnowledgeSource',
    'TaskPlannerKS',
    'TaskAllocatorKS',
    'ResourceManagerKS',
    'ConflictResolverKS',
    'PathPlannerKS',
    'ScoutCoordinatorKS',
]
