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

    def step(self):
        """
        Override step to add systematic sweep exploration.
        """
        # 1. Perceive
        command = self.perceive()

        # 2. Execute
        if command:
            self.execute(command)
        else:
            # No command, usar patrón de barrido sistemático
            self._sweep_pattern()

        # 3. Report
        self.report()

    def execute(self, command: Dict[str, Any]):
        """Execute scout-specific commands"""
        action = command.get('action') if command else None

        if action == 'explore_area':
            self._execute_explore(command)
        elif action == 'move':
            self._execute_move(command)
            # Scan while moving
            self._scan_area()
        else:
            # Unknown command o comando vacío - usar patrón de barrido sistemático
            self._sweep_pattern()
            # _sweep_pattern ya escanea el área, no necesitamos escanear de nuevo

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
        """Simple movement towards target - puede moverse a cualquier celda
        
        Retorna True si se movió, False si no pudo moverse o ya está en el objetivo.
        """
        x, z = self.position
        tx, tz = target

        # Si ya estamos en el objetivo, no moverse
        if (x, z) == target:
            return False

        # Move one step closer (Manhattan)
        if abs(tx - x) > abs(tz - z):
            # Move horizontally
            new_x = x + (1 if tx > x else -1)
            new_pos = (new_x, z)
        else:
            # Move vertically
            new_z = z + (1 if tz > z else -1)
            new_pos = (x, new_z)

        # Check if valid (ahora acepta cualquier celda dentro de los límites)
        if self._is_valid_position(new_pos):
            self.position = new_pos
            self.status = 'scouting'
            return True
        else:
            # Intentar el otro eje si el primero falló
            if abs(tx - x) > abs(tz - z):
                # Intentar vertical
                new_z = z + (1 if tz > z else -1)
                alt_pos = (x, new_z)
            else:
                # Intentar horizontal
                new_x = x + (1 if tx > x else -1)
                alt_pos = (new_x, z)
            
            if self._is_valid_position(alt_pos):
                self.position = alt_pos
                self.status = 'scouting'
                return True
        
        return False

    def _scan_area(self):
        """
        Scan the area around current position (área 3x3).

        Solo revela celdas si son campos (FIELD). Si no son campos, no hace nada.
        Esto simplifica el comportamiento: el scout se mueve por todas las celdas
        pero solo revela información de cultivos.
        """
        x, z = self.position
        kb = self.blackboard.knowledge_base

        # Radio de escaneo (1 = área 3x3)
        scan_radius = 1

        # Escanear área alrededor del scout
        for dz in range(-scan_radius, scan_radius + 1):
            for dx in range(-scan_radius, scan_radius + 1):
                scan_x = x + dx
                scan_z = z + dz

                # Verificar límites
                if not (0 <= scan_x < kb.world_state.width and 0 <= scan_z < kb.world_state.height):
                    continue

                pos = (scan_x, scan_z)

                # IMPORTANTE: Solo procesar si es un campo (FIELD)
                # Si no es un campo, ignorar completamente
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
        """Check if position is valid and navigable
        
        El scout puede moverse por CUALQUIER celda, incluso IMPASSABLE.
        Esto simplifica el movimiento para permitir barrido completo.
        """
        x, z = pos
        kb = self.blackboard.knowledge_base

        # Solo verificar límites del mapa
        return 0 <= x < kb.world_state.width and 0 <= z < kb.world_state.height
    
    def _sweep_pattern(self):
        """
        Patrón de barrido sistemático: va a la esquina superior izquierda (0,0)
        y barre el mapa fila por fila de izquierda a derecha.
        
        Estrategia:
        1. Si no está en (0,0), moverse hacia allí
        2. Una vez en (0,0), comenzar barrido fila por fila
        3. En cada posición, escanear el área (solo revela si es FIELD)
        4. Moverse a la siguiente celda en el patrón de barrido
        """
        kb = self.blackboard.knowledge_base
        x, z = self.position
        width = kb.world_state.width
        height = kb.world_state.height
        
        # Si no está en la esquina superior izquierda, moverse hacia allí
        if x != 0 or z != 0:
            # Moverse hacia (0, 0)
            if x > 0:
                # Moverse hacia la izquierda
                self.position = (x - 1, z)
            elif z > 0:
                # Moverse hacia arriba
                self.position = (x, z - 1)
            else:
                # Ya está en (0, 0) o muy cerca
                self.position = (0, 0)
            
            self.status = 'scouting'
            # Escanear área en la nueva posición
            self._scan_area()
            return
        
        # Ya está en (0, 0) o cerca - comenzar barrido sistemático
        # Calcular siguiente posición en el patrón de barrido
        next_x = x + 1
        
        if next_x >= width:
            # Fin de fila, pasar a la siguiente fila
            next_x = 0
            next_z = z + 1
            
            if next_z >= height:
                # Fin del mapa, volver al inicio
                next_x = 0
                next_z = 0
        else:
            next_z = z
        
        # Moverse a la siguiente posición
        self.position = (next_x, next_z)
        self.status = 'scouting'
        
        # Escanear área en la nueva posición (solo revela si es FIELD)
        self._scan_area()

    def report(self):
        """Report scout state to blackboard"""
        super().report()

        # Update analyzed positions in blackboard
        self.blackboard.knowledge_base.update_agent(
            str(self.id),
            analyzed_positions=self.analyzed_positions,
        )
