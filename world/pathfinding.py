"""
Módulo de pathfinding para encontrar caminos en el mundo.
Implementa Dijkstra con prioridad para caminos (ROAD) y luego campos (FIELD).
"""
import heapq
import random
from typing import List, Tuple, Optional, Dict
from .world_generator import TileType


class Pathfinder:
    """Pathfinder que usa Dijkstra con prioridad para caminos"""
    
    def __init__(self, grid: List[List[int]], width: int, height: int):
        """
        Inicializa el pathfinder con el grid del mundo.
        
        Args:
            grid: Matriz 2D con tipos de tiles (TileType)
            width: Ancho del grid
            height: Alto del grid
        """
        self.grid = grid
        self.width = width
        self.height = height
    
    def _in_bounds(self, x: int, z: int) -> bool:
        """Verifica si las coordenadas están dentro de los límites"""
        return 0 <= x < self.width and 0 <= z < self.height
    
    def _is_passable(self, x: int, z: int) -> bool:
        """Verifica si una celda es transitable (ROAD, FIELD o BARN)"""
        if not self._in_bounds(x, z):
            return False
        tile = self.grid[z][x]
        return tile in (TileType.ROAD, TileType.FIELD, TileType.BARN)
    
    def _get_neighbors(self, x: int, z: int) -> List[Tuple[int, int]]:
        """Retorna las coordenadas de los 4 vecinos directos"""
        neighbors = []
        for dx, dz in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, nz = x + dx, z + dz
            if self._in_bounds(nx, nz):
                neighbors.append((nx, nz))
        return neighbors
    
    def _straight_line_path(
        self, 
        start: Tuple[int, int], 
        end: Tuple[int, int]
    ) -> List[Tuple[int, int]]:
        """
        Genera un camino en línea recta usando el algoritmo de Bresenham.
        Solo incluye celdas transitables (ROAD, FIELD, BARN).
        
        Args:
            start: Tupla (x, z) con la posición inicial
            end: Tupla (x, z) con la posición destino
        
        Returns:
            Lista de tuplas (x, z) representando el camino en línea recta
        """
        x0, z0 = start
        x1, z1 = end
        
        path = []
        dx = abs(x1 - x0)
        dy = abs(z1 - z0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if z0 < z1 else -1
        err = dx - dy
        
        x, z = x0, z0
        
        while True:
            # Solo agregar si es transitable
            if self._is_passable(x, z):
                path.append((x, z))
            
            if x == x1 and z == z1:
                break
            
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                z += sy
        
        return path
    
    def _get_cost(self, x: int, z: int, prefer_roads: bool = True) -> float:
        """
        Calcula el costo de moverse a una celda.
        Caminos tienen costo menor, campos tienen costo mayor.
        
        Args:
            x: Coordenada X
            z: Coordenada Z
            prefer_roads: Si True, los caminos tienen costo muy bajo
        
        Returns:
            Costo de moverse a la celda (float)
        """
        if not self._in_bounds(x, z):
            return float('inf')
        
        tile = self.grid[z][x]
        
        if tile == TileType.ROAD:
            # Caminos tienen costo muy bajo para priorizarlos
            return 1.0
        elif tile == TileType.FIELD:
            # Campos tienen costo mayor
            return 10.0 if prefer_roads else 1.0
        elif tile == TileType.BARN:
            # El barn es transitable
            return 1.0
        else:
            # Intransitables
            return float('inf')
    
    def find_barn(self) -> Optional[Tuple[int, int]]:
        """
        Encuentra la posición del barn en el grid.
        
        Returns:
            Tupla (x, z) con la posición del barn, o None si no se encuentra
        """
        for z in range(self.height):
            for x in range(self.width):
                if self.grid[z][x] == TileType.BARN:
                    return (x, z)
        return None
    
    def find_max_infestation(self, infestation_grid: List[List[int]]) -> Optional[Tuple[int, int]]:
        """
        Encuentra la celda con mayor nivel de infestación.
        
        Args:
            infestation_grid: Matriz 2D con niveles de infestación (0-100)
        
        Returns:
            Tupla (x, z) con la posición de máxima infestación, o None si no hay
        """
        max_infestation = -1
        max_pos = None
        
        for z in range(self.height):
            for x in range(self.width):
                if self._is_passable(x, z) and infestation_grid[z][x] > max_infestation:
                    max_infestation = infestation_grid[z][x]
                    max_pos = (x, z)
        
        return max_pos
    
    def dijkstra(
        self, 
        start: Tuple[int, int], 
        end: Tuple[int, int],
        prefer_roads: bool = True,
        capture_steps: bool = False
    ) -> Optional[List[Tuple[int, int]]]:
        """
        Implementa el algoritmo de Dijkstra para encontrar el camino más corto.
        Prioriza caminos sobre campos cuando prefer_roads=True.
        
        Args:
            start: Tupla (x, z) con la posición inicial
            end: Tupla (x, z) con la posición destino
            prefer_roads: Si True, prioriza caminos sobre campos
            capture_steps: Si True, captura los estados intermedios para animación
        
        Returns:
            Lista de tuplas (x, z) representando el camino, o None si no hay camino
            Si capture_steps=True, retorna tupla (path, steps) donde steps es lista de estados
        """
        if not self._is_passable(*start) or not self._is_passable(*end):
            return None
        
        # Cola de prioridad: (costo_acumulado, x, z)
        pq = [(0, start[0], start[1])]
        
        # Diccionario para guardar el costo mínimo a cada celda
        costs = {start: 0}
        
        # Diccionario para reconstruir el camino
        came_from = {start: None}
        
        visited = set()
        steps = [] if capture_steps else None
        
        while pq:
            current_cost, x, z = heapq.heappop(pq)
            current = (x, z)
            
            if current in visited:
                continue
            
            visited.add(current)
            
            # Capturar estado para animación (solo cada N pasos para optimizar)
            if capture_steps:
                # Capturar solo cada 5 pasos para reducir cantidad de frames
                # Pero siempre capturar el primero y cuando llegamos al destino
                should_capture = (
                    len(visited) == 1 or  # Primer paso
                    len(visited) % 5 == 0 or  # Cada 5 nodos visitados
                    current == end  # Cuando llegamos al destino
                )
                
                if should_capture:
                    # Obtener nodos en la cola de prioridad (frontier) - limitado
                    frontier = [(cx, cz) for _, cx, cz in pq[:min(100, len(pq))]]
                    # Solo guardar visited como lista (no set) para serialización
                    steps.append({
                        'visited': list(visited),
                        'current': current,
                        'frontier': frontier
                        # No guardar came_from completo para ahorrar memoria
                    })
            
            # Si llegamos al destino
            if current == end:
                # Reconstruir el camino
                path = []
                node = end
                while node is not None:
                    path.append(node)
                    node = came_from[node]
                path.reverse()
                
                if capture_steps:
                    # Agregar paso final con el camino completo (si no se agregó ya)
                    if not steps or steps[-1].get('current') != end:
                        steps.append({
                            'visited': list(visited),
                            'current': end,
                            'frontier': [],
                            'path': path
                        })
                    return (path, steps)
                return path
            
            # Explorar vecinos
            for neighbor in self._get_neighbors(x, z):
                if neighbor in visited or not self._is_passable(*neighbor):
                    continue
                
                # Calcular nuevo costo
                move_cost = self._get_cost(*neighbor, prefer_roads=prefer_roads)
                new_cost = current_cost + move_cost
                
                # Si encontramos un camino más corto o es la primera vez que visitamos
                if neighbor not in costs or new_cost < costs[neighbor]:
                    costs[neighbor] = new_cost
                    came_from[neighbor] = current
                    heapq.heappush(pq, (new_cost, neighbor[0], neighbor[1]))
        
        # No se encontró camino
        return None
    
    def find_path_to_max_infestation(
        self, 
        infestation_grid: List[List[int]],
        prefer_roads: bool = True,
        capture_steps: bool = False
    ) -> Optional[Dict]:
        """
        Encuentra el camino desde el barn hasta la celda con mayor infestación.
        
        Estrategia:
        1. Primero intenta usar Dijkstra que prioriza caminos (ROAD)
        2. Si el camino encontrado usa solo caminos, lo retorna
        3. Si el camino usa campos, verifica si hay una sección sin caminos
        4. Para secciones sin caminos, usa línea recta a través de campos
        
        Args:
            infestation_grid: Matriz 2D con niveles de infestación
            prefer_roads: Si True, prioriza caminos sobre campos
            capture_steps: Si True, captura los estados intermedios para animación
        
        Returns:
            Diccionario con:
            - 'path': Lista de tuplas (x, z) del camino
            - 'start': Tupla (x, z) del barn
            - 'end': Tupla (x, z) del destino
            - 'infestation': Nivel de infestación del destino
            - 'steps': (opcional) Lista de estados intermedios si capture_steps=True
            O None si no se puede encontrar
        """
        # Encontrar barn
        barn_pos = self.find_barn()
        if barn_pos is None:
            return None
        
        # Encontrar destino con mayor infestación
        max_inf_pos = self.find_max_infestation(infestation_grid)
        if max_inf_pos is None:
            return None
        
        # Primero intentar Dijkstra que prioriza caminos
        result = self.dijkstra(barn_pos, max_inf_pos, prefer_roads=prefer_roads, capture_steps=capture_steps)
        
        if result is None:
            return None
        
        if capture_steps:
            path, steps = result
        else:
            path = result
            steps = None
        
        if path is None:
            return None
        
        # Optimizar el camino: si hay secciones sin caminos, usar línea recta
        optimized_path = self._optimize_path_with_straight_lines(path)
        
        result_dict = {
            'path': optimized_path,
            'start': barn_pos,
            'end': max_inf_pos,
            'infestation': infestation_grid[max_inf_pos[1]][max_inf_pos[0]]
        }
        
        if steps is not None:
            result_dict['steps'] = steps
        
        return result_dict
    
    def _optimize_path_with_straight_lines(
        self, 
        path: List[Tuple[int, int]]
    ) -> List[Tuple[int, int]]:
        """
        Optimiza el camino reemplazando secciones sin caminos con líneas rectas.
        
        Estrategia:
        - Mantiene el camino mientras haya caminos (ROAD) disponibles
        - Cuando se acaban los caminos, usa línea recta hasta el destino
        
        Args:
            path: Camino original
        
        Returns:
            Camino optimizado
        """
        if len(path) <= 2:
            return path
        
        optimized = []
        last_road_index = -1
        
        # Encontrar el último punto que está en un camino
        for i in range(len(path) - 1, -1, -1):
            x, z = path[i]
            if self.grid[z][x] == TileType.ROAD:
                last_road_index = i
                break
        
        # Si todo el camino está en caminos, retornar el original
        if last_road_index == len(path) - 1:
            return path
        
        # Agregar la parte del camino que usa caminos
        if last_road_index >= 0:
            optimized.extend(path[:last_road_index + 1])
            # Desde el último camino, usar línea recta hasta el destino
            straight_path = self._straight_line_path(path[last_road_index], path[-1])
            # Agregar todos los puntos de la línea recta excepto el primero (ya está)
            optimized.extend(straight_path[1:])
        else:
            # No hay caminos en absoluto, usar línea recta completa
            straight_path = self._straight_line_path(path[0], path[-1])
            optimized = straight_path
        
        return optimized
    
    def find_random_passable_cells(self, count: int) -> List[Tuple[int, int]]:
        """
        Encuentra celdas transitables aleatorias en el grid.
        
        Args:
            count: Número de celdas a encontrar
        
        Returns:
            Lista de tuplas (x, z) con posiciones transitables
        """
        passable_cells = []
        for z in range(self.height):
            for x in range(self.width):
                if self._is_passable(x, z) and self.grid[z][x] != TileType.BARN:
                    passable_cells.append((x, z))
        
        if len(passable_cells) < count:
            return passable_cells
        
        return random.sample(passable_cells, count)
    
    def find_paths_to_random_destinations(
        self,
        num_tractors: int,
        prefer_roads: bool = True
    ) -> Optional[List[Dict]]:
        """
        Encuentra caminos desde el barn hasta múltiples destinos aleatorios.
        
        Args:
            num_tractors: Número de tractores (y destinos)
            prefer_roads: Si True, prioriza caminos sobre campos
        
        Returns:
            Lista de diccionarios, cada uno con:
            - 'path': Lista de tuplas (x, z) del camino
            - 'start': Tupla (x, z) del barn
            - 'end': Tupla (x, z) del destino
            O None si no se puede encontrar
        """
        # Encontrar barn
        barn_pos = self.find_barn()
        if barn_pos is None:
            return None
        
        # Encontrar destinos aleatorios
        destinations = self.find_random_passable_cells(num_tractors)
        if len(destinations) < num_tractors:
            return None
        
        results = []
        for dest in destinations:
            path = self.dijkstra(barn_pos, dest, prefer_roads=prefer_roads, capture_steps=False)
            if path is not None:
                optimized_path = self._optimize_path_with_straight_lines(path)
                results.append({
                    'path': optimized_path,
                    'start': barn_pos,
                    'end': dest
                })
        
        return results if results else None
    
    def simulate_tractors(
        self,
        tractor_paths: List[List[Tuple[int, int]]],
        max_steps: int = 1000
    ) -> List[List[Dict]]:
        """
        Simula el movimiento de múltiples tractores con detección de colisiones.
        
        Args:
            tractor_paths: Lista de caminos, uno por cada tractor
            max_steps: Número máximo de pasos de simulación
        
        Returns:
            Lista de listas, donde cada lista interna contiene los estados de un tractor
            en cada paso. Cada estado es un dict con:
            - 'position': (x, z) posición actual
            - 'path_index': índice en el camino
            - 'waiting': bool si está esperando por colisión
        """
        num_tractors = len(tractor_paths)
        if num_tractors == 0:
            return []
        
        # Inicializar posiciones: todos empiezan en el barn
        tractor_positions = [0] * num_tractors  # Índice en el camino de cada tractor
        simulation_steps = []
        
        # Colores para cada tractor (para visualización)
        tractor_colors = [
            '#ff0000', '#00ff00', '#0000ff', '#ffff00', '#ff00ff',
            '#00ffff', '#ff8800', '#8800ff', '#88ff00', '#ff0088'
        ]
        
        for step in range(max_steps):
            step_state = []
            # Diccionario: posición -> lista de tractor_ids en esa posición
            # Permite múltiples tractores en la misma posición (como al inicio en el barn)
            position_to_tractors = {}
            
            # Primero, registrar todas las posiciones actuales
            for tractor_id in range(num_tractors):
                path = tractor_paths[tractor_id]
                current_index = tractor_positions[tractor_id]
                if current_index < len(path):
                    current_pos = path[current_index]
                    if current_pos not in position_to_tractors:
                        position_to_tractors[current_pos] = []
                    position_to_tractors[current_pos].append(tractor_id)
            
            # Procesar tractores en orden (permite salida ordenada del barn)
            for tractor_id in range(num_tractors):
                path = tractor_paths[tractor_id]
                current_index = tractor_positions[tractor_id]
                
                if current_index >= len(path) - 1:
                    # Tractor ya llegó a su destino
                    step_state.append({
                        'position': path[-1],
                        'path_index': len(path) - 1,
                        'waiting': False,
                        'arrived': True,
                        'color': tractor_colors[tractor_id % len(tractor_colors)]
                    })
                    continue
                
                next_index = current_index + 1
                next_pos = path[next_index]
                current_pos = path[current_index]
                
                # Verificar colisión: si la posición objetivo ya está ocupada
                # (y no es solo este tractor moviéndose)
                next_pos_occupied = next_pos in position_to_tractors and len(position_to_tractors[next_pos]) > 0
                
                # Si la posición objetivo está ocupada, verificar si es solo porque
                # otro tractor ya se movió ahí en este mismo paso
                if next_pos_occupied:
                    # Hay colisión, esperar (mantener posición actual)
                    step_state.append({
                        'position': current_pos,
                        'path_index': current_index,
                        'waiting': True,
                        'arrived': False,
                        'color': tractor_colors[tractor_id % len(tractor_colors)]
                    })
                else:
                    # Puede avanzar - actualizar posiciones
                    # Remover de posición actual
                    if current_pos in position_to_tractors:
                        position_to_tractors[current_pos].remove(tractor_id)
                        if len(position_to_tractors[current_pos]) == 0:
                            del position_to_tractors[current_pos]
                    
                    # Agregar a nueva posición
                    if next_pos not in position_to_tractors:
                        position_to_tractors[next_pos] = []
                    position_to_tractors[next_pos].append(tractor_id)
                    
                    tractor_positions[tractor_id] = next_index
                    step_state.append({
                        'position': next_pos,
                        'path_index': next_index,
                        'waiting': False,
                        'arrived': False,
                        'color': tractor_colors[tractor_id % len(tractor_colors)]
                    })
            
            simulation_steps.append(step_state)
            
            # Verificar si todos llegaron
            all_arrived = all(
                state.get('arrived', False) or 
                tractor_positions[i] >= len(tractor_paths[i]) - 1
                for i, state in enumerate(step_state)
            )
            if all_arrived:
                break
        
        return simulation_steps


class DynamicPathfinder(Pathfinder):
    """
    Pathfinder que usa pesos dinámicos para campos.
    Extiende el Pathfinder base para considerar pesos adicionales.
    Útil para agentes que deben evitar pisar campos repetidamente.
    """
    
    def __init__(self, grid: List[List[int]], width: int, height: int, field_weights: Dict[Tuple[int, int], float]):
        """
        Inicializa el pathfinder con pesos dinámicos.
        
        Args:
            grid: Grid del mundo
            width: Ancho del grid
            height: Alto del grid
            field_weights: Diccionario de pesos adicionales por posición de campo
        """
        super().__init__(grid, width, height)
        self.field_weights = field_weights
    
    def _get_cost(self, x: int, z: int, prefer_roads: bool = True) -> float:
        """
        Calcula el costo de moverse a una celda, incluyendo pesos dinámicos.
        """
        base_cost = super()._get_cost(x, z, prefer_roads)
        
        # Si es un campo, agregar peso dinámico
        if self.grid[z][x] == TileType.FIELD:
            dynamic_weight = self.field_weights.get((x, z), 0.0)
            return base_cost + dynamic_weight
        
        return base_cost
