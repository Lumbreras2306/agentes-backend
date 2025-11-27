"""
ScoutAgent - Simple reactive scout that scans for infestations

The scout follows commands from the blackboard to explore areas
and reports discoveries back.
"""

from .base_agent import BaseAgent
from ..blackboard.knowledge_base import EventType
from world.world_generator import TileType
from typing import Dict, Any


class ScoutAgent(BaseAgent):
    """
    Scout agent that explores and discovers infestations.

    Commands it responds to:
    - explore_area: Move to a target area and scan
    - move: Move to a specific position

    Behavior:
    - Scans 3 rows (current ± 1) while moving
    - Reports discovered infestations to blackboard
    - Very simple - just executes commands
    """

    def setup(self):
        """Initialize scout agent"""
        super().setup()

        self.agent_type = 'scout'
        self.analyzed_positions = set()

        # Register with blackboard
        from ..blackboard.knowledge_base import AgentState
        agent_state = AgentState(
            agent_id=str(self.id),
            agent_type='scout',
            position=self.position,
            status='idle',
            fields_analyzed=0,
            analyzed_positions=self.analyzed_positions,
        )
        self.blackboard.register_agent(agent_state)

    def execute(self, command: Dict[str, Any]):
        """Execute scout-specific commands"""
        action = command.get('action')

        if action == 'explore_area':
            self._execute_explore(command)
        elif action == 'move':
            self._execute_move(command)
            # Scan while moving
            self._scan_area()
        else:
            # Unknown command
            pass

        # Always scan after any movement
        if self.position:
            self._scan_area()

    def _execute_explore(self, command: Dict[str, Any]):
        """Execute explore command"""
        target = command.get('target_position')

        if not target:
            return

        # Move towards target
        self._move_towards(target)

        # Scan area
        self._scan_area()

        self.status = 'scouting'

    def _move_towards(self, target: tuple):
        """Simple movement towards target"""
        x, z = self.position
        tx, tz = target

        # Move one step closer (Manhattan)
        if abs(tx - x) > abs(tz - z):
            # Move horizontally
            new_x = x + (1 if tx > x else -1)
            new_pos = (new_x, z)
        else:
            # Move vertically
            new_z = z + (1 if tz > z else -1)
            new_pos = (x, new_z)

        # Check if valid
        if self._is_valid_position(new_pos):
            self.position = new_pos

    def _scan_area(self):
        """
        Scan the area around current position.

        Scans 3 rows: current row ± 1
        Reports discoveries to blackboard
        """
        x, z = self.position
        kb = self.blackboard.knowledge_base

        # Scan 3 rows
        for dz in [-1, 0, 1]:
            scan_z = z + dz

            if not (0 <= scan_z < kb.world_state.height):
                continue

            # Scan entire row
            for scan_x in range(kb.world_state.width):
                pos = (scan_x, scan_z)

                # Skip if not a field
                if kb.world_state.grid[scan_z][scan_x] != TileType.FIELD:
                    continue

                # Skip if already analyzed
                if pos in self.analyzed_positions:
                    continue

                # Mark as analyzed
                self.analyzed_positions.add(pos)
                self.fields_analyzed += 1

                # Get infestation level
                infestation = kb.get_infestation(scan_x, scan_z)

                # Report discovery
                if infestation > 0:
                    crop = kb.world_state.crop_grid[scan_z][scan_x]

                    self.blackboard.report_event(
                        EventType.FIELD_DISCOVERED,
                        {
                            'position': (scan_x, scan_z),
                            'infestation': infestation,
                            'crop': crop,
                        },
                        source=str(self.id)
                    )

    def _is_valid_position(self, pos: tuple) -> bool:
        """Check if position is valid and navigable"""
        x, z = pos
        kb = self.blackboard.knowledge_base

        if not (0 <= x < kb.world_state.width and 0 <= z < kb.world_state.height):
            return False

        tile = kb.world_state.grid[z][x]
        return tile != TileType.IMPASSABLE

    def report(self):
        """Report scout state to blackboard"""
        super().report()

        # Update analyzed positions in blackboard
        self.blackboard.knowledge_base.update_agent(
            str(self.id),
            analyzed_positions=self.analyzed_positions,
        )
