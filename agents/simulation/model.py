"""
FumigationModel - AgentPy model using the Blackboard system

This is the main simulation model that coordinates:
- Agent creation
- Blackboard system
- Step execution
- State synchronization
"""

import agentpy as ap
from typing import Dict, Tuple
from ..blackboard import Blackboard
from ..agents_core import ScoutAgent, FumigatorAgent


class FumigationModel(ap.Model):
    """
    Multi-agent fumigation simulation model.

    This model:
    - Creates scout and fumigator agents
    - Initializes the Blackboard system
    - Coordinates step execution
    - Syncs state to Django models
    """

    def setup(self):
        """Initialize the model"""
        # Get parameters
        self.num_fumigators = self.p.get('num_fumigators', 5)
        self.num_scouts = self.p.get('num_scouts', 1)
        self.world_instance = self.p.get('world_instance')
        self.blackboard_service = self.p.get('blackboard_service')  # Legacy
        self.simulation_id = self.p.get('simulation_id')  # For WebSocket

        if not self.world_instance:
            raise ValueError("world_instance is required")

        # Initialize Blackboard system
        self.blackboard = Blackboard(self.world_instance, self.blackboard_service)

        # Calculate start positions (barn cells)
        self.start_positions = self._calculate_start_positions()

        # Create agents
        self.fumigators = ap.AgentList(self, self.num_fumigators, FumigatorAgent)
        self.scouts = ap.AgentList(self, self.num_scouts, ScoutAgent)

        # All agents
        self.agents = self.fumigators + self.scouts

        # Start the blackboard
        self.blackboard.start()

        # Statistics
        self.total_steps = 0
        self.total_tasks_completed = 0

    def step(self):
        """Execute one simulation step"""
        # Ensure total_steps is initialized (in case setup() wasn't called)
        if not hasattr(self, 'total_steps'):
            self.total_steps = 0
        
        self.total_steps += 1

        # 1. Execute Blackboard control cycle
        # This activates Knowledge Sources and makes decisions
        self.blackboard.step()

        # 2. Execute agent steps
        # Agents perceive, execute, and report
        for agent in self.agents:
            agent.step()

        # 3. Sync to Django (periodically)
        if self.total_steps % 5 == 0:  # Every 5 steps
            self.blackboard.sync_to_django()

    def end(self):
        """Called when simulation ends"""
        # Final sync to Django
        self.blackboard.sync_to_django()

        # Stop blackboard
        self.blackboard.stop()

        # Collect statistics
        stats = self.blackboard.get_statistics()
        self.total_tasks_completed = stats['completed_tasks']

    def _calculate_start_positions(self) -> Dict[int, Tuple[int, int]]:
        """
        Calculate start positions for all agents (barn cells).

        Returns:
            Dict mapping agent ID to position
        """
        from world.world_generator import TileType

        # Find all barn cells
        barn_cells = []
        for z in range(self.world_instance.height):
            for x in range(self.world_instance.width):
                if self.world_instance.grid[z][x] == TileType.BARN:
                    barn_cells.append((x, z))

        if not barn_cells:
            # No barn found, use center
            center = (self.world_instance.width // 2, self.world_instance.height // 2)
            barn_cells = [center]

        # Assign positions (cycle through barn cells if more agents than cells)
        positions = {}
        total_agents = self.num_fumigators + self.num_scouts

        for i in range(total_agents):
            positions[i] = barn_cells[i % len(barn_cells)]

        return positions

    def get_status(self) -> Dict:
        """Get current simulation status"""
        stats = self.blackboard.get_statistics()

        return {
            'step': self.total_steps,
            'agents': {
                'total': len(self.agents),
                'fumigators': len(self.fumigators),
                'scouts': len(self.scouts),
            },
            'tasks': {
                'total': stats['total_tasks'],
                'pending': stats['pending_tasks'],
                'completed': stats['completed_tasks'],
            },
            'progress': {
                'fields_fumigated': stats['total_fields_fumigated'],
                'fields_analyzed': stats['total_fields_analyzed'],
                'total_infestation': stats['total_infestation'],
                'infested_cells': stats['infested_cells'],
            }
        }
