"""
Blackboard System for Multi-Agent Coordination

This package implements a proper Blackboard architecture pattern with:
- KnowledgeBase: Central repository of shared knowledge
- Control Component: Orchestrates Knowledge Sources
- Knowledge Sources: Specialized modules that read/write to the blackboard
"""

from .blackboard import Blackboard
from .knowledge_base import KnowledgeBase
from .control import ControlComponent

__all__ = ['Blackboard', 'KnowledgeBase', 'ControlComponent']
