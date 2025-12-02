"""
Simulation Engine

Manages the execution of the multi-agent simulation using AgentPy
and the Blackboard system.
"""

from .model import FumigationModel
from .runner import run_simulation

__all__ = ['FumigationModel', 'run_simulation']
