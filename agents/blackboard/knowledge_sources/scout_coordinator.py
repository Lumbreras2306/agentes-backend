"""
ScoutCoordinatorKS - Coordinates scout exploration

This Knowledge Source directs scout agents to unexplored areas
of the map to maximize coverage.
"""

from .base import KnowledgeSource
from ..knowledge_base import EventType, AgentState
from typing import Tuple, Optional, Set


class ScoutCoordinatorKS(KnowledgeSource):
    """
    ScoutCoordinatorKS coordinates scout exploration patterns.

    Triggers:
    - AGENT_IDLE: When scout becomes idle, give it a new exploration target

    Logic:
    - Tracks analyzed positions across all scouts
    - Identifies unexplored areas
    - Directs scouts to maximize coverage
    - Uses systematic scanning pattern
    """

    def __init__(self, knowledge_base):
        super().__init__(knowledge_base)
        self.priority = 5  # Medium priority
        self.triggers = {EventType.AGENT_IDLE}
        self.always_run = True  # Check every cycle

        # Track globally analyzed positions
        self.analyzed_positions: Set[Tuple[int, int]] = set()

        # Track if exploration is complete
        self.exploration_complete = False

    def check_preconditions(self) -> bool:
        """Check if there are idle scouts"""
        scouts = self.kb.get_agents_by_type('scout')
        idle_scouts = [s for s in scouts if s.status in ['idle', 'scouting']]

        return len(idle_scouts) > 0

    def execute(self):
        """Direct scouts to unexplored areas"""
        scouts = self.kb.get_agents_by_type('scout')

        # Update global analyzed positions
        for scout in scouts:
            self.analyzed_positions.update(scout.analyzed_positions)

        # Check if exploration is complete
        coverage = self.get_coverage_percentage()

        if coverage >= 99.0 and not self.exploration_complete:
            # Exploration complete! Emit event
            self.exploration_complete = True
            self.kb.emit_event(EventType.SCOUT_EXPLORATION_COMPLETE, {
                'coverage': coverage,
                'total_fields_analyzed': len(self.analyzed_positions)
            })

            print(f"🎯 Scout exploration complete! Coverage: {coverage:.1f}%")
            return

        # Direct each idle scout
        for scout in scouts:
            if scout.status in ['idle', 'scouting']:
                target = self._find_exploration_target(scout)

                if target:
                    # Send exploration command
                    self.kb.set_shared(f'command_{scout.agent_id}', {
                        'action': 'explore_area',
                        'target_position': target,
                    })

                    self.kb.update_agent(
                        scout.agent_id,
                        status='scouting'
                    )
                elif not self.exploration_complete:
                    # No more targets but not 99% yet, check coverage
                    if coverage >= 99.0:
                        self.exploration_complete = True
                        self.kb.emit_event(EventType.SCOUT_EXPLORATION_COMPLETE, {
                            'coverage': coverage,
                            'total_fields_analyzed': len(self.analyzed_positions)
                        })
                        print(f"🎯 Scout exploration complete! Coverage: {coverage:.1f}%")

    def _find_exploration_target(self, scout: AgentState) -> Optional[Tuple[int, int]]:
        """
        Find the next exploration target for a scout.

        Strategy:
        - Zigzag/Boustrophedon pattern for maximum efficiency
        - Even rows (0, 2, 4...): sweep left-to-right
        - Odd rows (1, 3, 5...): sweep right-to-left
        - Pattern: (0,0)→(width,0) then (width,1)→(0,1) then (0,2)→(width,2)...
        - This minimizes backtracking and creates the most efficient path

        Args:
            scout: The scout agent

        Returns:
            Target position or None if all explored
        """
        from world.world_generator import TileType

        width = self.kb.world_state.width
        height = self.kb.world_state.height
        grid = self.kb.world_state.grid

        # Zigzag sweep: alternating direction per row
        for z in range(height):
            # Determine scan direction based on row number
            if z % 2 == 0:
                # Even rows: left to right (0 → width-1)
                x_range = range(width)
            else:
                # Odd rows: right to left (width-1 → 0)
                x_range = range(width - 1, -1, -1)

            for x in x_range:
                pos = (x, z)

                # Check if this position needs to be analyzed
                # We only care about FIELD positions
                if grid[z][x] == TileType.FIELD:
                    if pos not in self.analyzed_positions:
                        # Found an unanalyzed field in sweep order
                        # Return navigable position to reach it
                        if grid[z][x] != TileType.IMPASSABLE:
                            return pos
                        else:
                            return self._find_nearest_navigable(x, z)

        # All fields analyzed
        return None

    def _find_nearest_navigable(self, x: int, z: int) -> Tuple[int, int]:
        """Find nearest navigable position to (x, z)"""
        from world.world_generator import TileType

        grid = self.kb.world_state.grid
        width = self.kb.world_state.width
        height = self.kb.world_state.height

        # Check if position itself is navigable
        if grid[z][x] != TileType.IMPASSABLE:
            return (x, z)

        # Search in expanding radius
        for radius in range(1, min(width, height)):
            for dx in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    if abs(dx) + abs(dz) != radius:  # Only check border
                        continue

                    nx, nz = x + dx, z + dz

                    if 0 <= nx < width and 0 <= nz < height:
                        if grid[nz][nx] != TileType.IMPASSABLE:
                            return (nx, nz)

        # Fallback to center
        return (width // 2, height // 2)

    def get_coverage_percentage(self) -> float:
        """Get percentage of fields analyzed"""
        from world.world_generator import TileType

        grid = self.kb.world_state.grid
        width = self.kb.world_state.width
        height = self.kb.world_state.height

        total_fields = 0
        for z in range(height):
            for x in range(width):
                if grid[z][x] == TileType.FIELD:
                    total_fields += 1

        if total_fields == 0:
            return 100.0

        analyzed_fields = len([
            pos for pos in self.analyzed_positions
            if grid[pos[1]][pos[0]] == TileType.FIELD
        ])

        return (analyzed_fields / total_fields) * 100.0
