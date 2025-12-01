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
            # Only send new commands when scout is truly idle
            # This prevents sending conflicting commands while scout is moving
            if scout.status == 'idle':
                target = self._find_exploration_target(scout)

                if target:
                    # Send exploration command
                    self.kb.set_shared(f'command_{scout.agent_id}', {
                        'action': 'explore_area',
                        'target_position': target,
                    })

                    # Mark target position as analyzed immediately
                    # This prevents sending the scout to the same position twice
                    self.analyzed_positions.add(target)

                    self.kb.update_agent(
                        scout.agent_id,
                        status='scouting'
                    )

                    print(f"🔍 Scout {scout.agent_id}: Moviendo a posición {target} en patrón zigzag")
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
        - Simple zigzag pattern through ALL positions (not just fields)
        - Returns the FIRST unvisited position in zigzag order
        - Pattern: (0,0)→...→(width-1,0) then (width-1,2)→...→(0,2) then (0,4)→...
        - Scout follows strict sequence creating clean zigzag path

        Args:
            scout: The scout agent

        Returns:
            Target position or None if sweep complete
        """
        from world.world_generator import TileType

        width = self.kb.world_state.width
        height = self.kb.world_state.height
        grid = self.kb.world_state.grid

        # Generate zigzag positions in strict order with step=3
        # Scout has 5x5 revelation radius (covers z-2 to z+2)
        # Row 0: (0,0), (1,0), (2,0), ..., (width-1, 0) - covers z [-2, -1, 0, 1, 2]
        # Row 3: (width-1, 3), (width-2, 3), ..., (0, 3) - covers z [1, 2, 3, 4, 5]
        # Row 6: (0,6), (1,6), ..., (width-1, 6) - covers z [4, 5, 6, 7, 8]
        # etc. - Full coverage with efficient 3-row stepping

        # Escanear cada 3 filas (0, 3, 6, 9...) en lugar de 2
        # El scout con radio 2 (5x5) cubre filas intermedias
        for idx, z in enumerate(range(0, height, 3)):
            # Determine direction for this row
            if idx % 2 == 0:
                # Even iterations: left → right
                x_positions = range(width)
            else:
                # Odd iterations: right → left
                x_positions = range(width - 1, -1, -1)

            # Check each position in this row
            for x in x_positions:
                pos = (x, z)

                # If not yet visited and not impassable
                if pos not in self.analyzed_positions:
                    if grid[z][x] != TileType.IMPASSABLE:
                        return pos

        # All positions in zigzag pattern visited
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
