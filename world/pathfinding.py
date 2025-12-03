"""
Módulo de pathfinding para encontrar caminos en el mundo.
Implementa Dijkstra con prioridad para caminos (ROAD) y luego campos (FIELD).
"""
import heapq
import random
from typing import List, Tuple, Optional, Dict, Set
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
        Encuentra la posición central del barn en el grid.
        El barn tiene 5 casillas en línea, retorna la posición central.
        
        Returns:
            Tupla (x, z) con la posición central del barn, o None si no se encuentra
        """
        barn_positions = []
        for z in range(self.height):
            for x in range(self.width):
                if self.grid[z][x] == TileType.BARN:
                    barn_positions.append((x, z))
        
        if not barn_positions:
            return None
        
        # Si hay múltiples casillas de granero (5 en línea), encontrar la central
        if len(barn_positions) > 1:
            # Ordenar las posiciones para encontrar la central
            # Si están en línea horizontal, ordenar por x
            # Si están en línea vertical, ordenar por z
            sorted_by_x = sorted(barn_positions, key=lambda p: p[0])
            sorted_by_z = sorted(barn_positions, key=lambda p: p[1])
            
            # Verificar si están en línea horizontal (misma z)
            if len(set(z for x, z in barn_positions)) == 1:
                # Línea horizontal: la central es la del medio
                return sorted_by_x[len(sorted_by_x) // 2]
            # Si están en línea vertical (misma x)
            elif len(set(x for x, z in barn_positions)) == 1:
                # Línea vertical: la central es la del medio
                return sorted_by_z[len(sorted_by_z) // 2]
            else:
                # Forma irregular, usar centroide
                avg_x = sum(x for x, z in barn_positions) // len(barn_positions)
                avg_z = sum(z for x, z in barn_positions) // len(barn_positions)
                center_pos = min(barn_positions, 
                               key=lambda pos: abs(pos[0] - avg_x) + abs(pos[1] - avg_z))
                return center_pos
        
        # Si solo hay una casilla, retornarla
        return barn_positions[0]
    
    def find_all_barn_cells(self) -> List[Tuple[int, int]]:
        """
        Encuentra todas las celdas del granero (5 celdas en línea).
        
        Returns:
            Lista de tuplas (x, z) con todas las posiciones del granero, ordenadas
        """
        barn_positions = []
        for z in range(self.height):
            for x in range(self.width):
                if self.grid[z][x] == TileType.BARN:
                    barn_positions.append((x, z))
        
        if not barn_positions:
            return []
        
        # Ordenar las posiciones: primero por z, luego por x
        # Esto asegura que si están en línea horizontal, estén ordenadas de izquierda a derecha
        # Si están en línea vertical, estén ordenadas de arriba a abajo
        barn_positions.sort(key=lambda p: (p[1], p[0]))
        
        return barn_positions
    
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
    
    def find_top_infested_positions(
        self, 
        infestation_grid: List[List[int]], 
        count: int
    ) -> List[Tuple[int, int]]:
        """
        Encuentra las N celdas con mayor nivel de infestación.
        
        Args:
            infestation_grid: Matriz 2D con niveles de infestación (0-100)
            count: Número de posiciones a encontrar
        
        Returns:
            Lista de tuplas (x, z) ordenadas por nivel de infestación (mayor a menor)
        """
        infested_positions = []
        
        for z in range(self.height):
            for x in range(self.width):
                if self._is_passable(x, z) and infestation_grid[z][x] > 0:
                    infested_positions.append((x, z, infestation_grid[z][x]))
        
        # Ordenar por nivel de infestación (mayor a menor)
        infested_positions.sort(key=lambda item: item[2], reverse=True)
        
        # Retornar solo las posiciones (sin el nivel)
        return [(x, z) for x, z, _ in infested_positions[:count]]
    
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
        # Limitar a máximo 5 tractores (uno por celda del granero)
        num_tractors = min(5, num_tractors)
        
        # Encontrar todas las celdas del granero
        barn_cells = self.find_all_barn_cells()
        if not barn_cells or len(barn_cells) < num_tractors:
            # Si no hay suficientes celdas, usar la posición central
            barn_pos = self.find_barn()
            if barn_pos is None:
                return None
            # Usar la misma posición para todos
            barn_start_positions = [barn_pos] * num_tractors
        else:
            # Asignar una celda diferente del granero a cada tractor
            barn_start_positions = barn_cells[:num_tractors]
        
        # Encontrar destinos evitando conflictos (destinos en el mismo camino)
        results = []
        used_destinations = set()
        used_path_positions = set()  # Posiciones ya usadas en caminos de otros tractores
        max_attempts_per_tractor = 30
        
        for tractor_id in range(num_tractors):
            path_found = False
            for attempt in range(max_attempts_per_tractor):
                # Encontrar un destino aleatorio que no haya sido usado
                candidate_destinations = self.find_random_passable_cells(10)
                if not candidate_destinations:
                    break
                
                # Filtrar destinos ya usados
                available_destinations = [d for d in candidate_destinations if d not in used_destinations]
                if not available_destinations:
                    break
                
                dest = random.choice(available_destinations)
                
                # Calcular el camino desde la celda asignada del granero
                start_pos = barn_start_positions[tractor_id]
                path = self.dijkstra(start_pos, dest, prefer_roads=prefer_roads, capture_steps=False)
                if path is None:
                    continue
                
                # Optimizar el camino
                optimized_path = self._optimize_path_with_straight_lines(path)
                
                # Asegurar que el camino empiece en la posición inicial del tractor
                if optimized_path and optimized_path[0] != start_pos:
                    optimized_path = [start_pos] + optimized_path
                
                # Verificar conflictos: el destino no debe estar en el camino de otro tractor
                # (excepto el destino final de otros tractores)
                conflicts = False
                for existing_result in results:
                    existing_path = existing_result['path']
                    existing_dest = existing_result['end']
                    
                    # Verificar si el nuevo destino está en el camino de otro tractor (no en su destino final)
                    if dest in existing_path[:-1]:  # Excluir el último punto (destino final)
                        conflicts = True
                        break
                    
                    # Verificar si algún punto del nuevo camino (excepto destino) está en el destino de otro tractor
                    for path_pos in optimized_path[:-1]:  # Excluir el destino final
                        if path_pos == existing_dest:
                            conflicts = True
                            break
                    
                    if conflicts:
                        break
                
                if not conflicts:
                    results.append({
                        'path': optimized_path,
                        'start': start_pos,  # Usar la celda específica del granero
                        'end': dest
                    })
                    used_destinations.add(dest)
                    path_found = True
                    break
            
            # Si no se encontró un camino sin conflictos después de varios intentos,
            # usar el mejor disponible (aunque pueda tener conflictos menores)
            if not path_found:
                candidate_destinations = self.find_random_passable_cells(10)
                available_destinations = [d for d in candidate_destinations if d not in used_destinations]
                if available_destinations:
                    dest = random.choice(available_destinations)
                    start_pos = barn_start_positions[tractor_id]
                    path = self.dijkstra(start_pos, dest, prefer_roads=prefer_roads, capture_steps=False)
                    if path is not None:
                        optimized_path = self._optimize_path_with_straight_lines(path)
                        # Asegurar que el camino empiece en la posición inicial del tractor
                        if optimized_path and optimized_path[0] != start_pos:
                            optimized_path = [start_pos] + optimized_path
                        results.append({
                            'path': optimized_path,
                            'start': start_pos,  # Usar la celda específica del granero
                            'end': dest
                        })
                        used_destinations.add(dest)
        
        return results if results else None
    
    def find_paths_to_infested_destinations(
        self,
        infestation_grid: List[List[int]],
        num_tractors: int,
        prefer_roads: bool = True
    ) -> Optional[List[Dict]]:
        """
        Encuentra caminos desde el barn hasta los puntos más infestados del mapa.
        
        Args:
            infestation_grid: Matriz 2D con niveles de infestación (0-100)
            num_tractors: Número de tractores (y destinos)
            prefer_roads: Si True, prioriza caminos sobre campos
        
        Returns:
            Lista de diccionarios, cada uno con:
            - 'path': Lista de tuplas (x, z) del camino
            - 'start': Tupla (x, z) del barn
            - 'end': Tupla (x, z) del destino
            - 'infestation': Nivel de infestación del destino
            O None si no se puede encontrar
        """
        # Limitar a máximo 5 tractores (uno por celda del granero)
        num_tractors = min(5, num_tractors)
        
        # Encontrar todas las celdas del granero
        barn_cells = self.find_all_barn_cells()
        if not barn_cells or len(barn_cells) < num_tractors:
            # Si no hay suficientes celdas, usar la posición central
            barn_pos = self.find_barn()
            if barn_pos is None:
                return None
            # Usar la misma posición para todos
            barn_start_positions = [barn_pos] * num_tractors
        else:
            # Asignar una celda diferente del granero a cada tractor
            barn_start_positions = barn_cells[:num_tractors]
        
        # Encontrar los puntos más infestados
        infested_positions = self.find_top_infested_positions(infestation_grid, num_tractors * 2)
        if len(infested_positions) < num_tractors:
            return None
        
        # Asignar destinos evitando conflictos
        results = []
        used_destinations = set()
        
        for tractor_id in range(num_tractors):
            path_found = False
            for infested_pos in infested_positions:
                if infested_pos in used_destinations:
                    continue
                
                dest = infested_pos
                start_pos = barn_start_positions[tractor_id]
                
                # Calcular el camino desde la celda asignada del granero
                path = self.dijkstra(start_pos, dest, prefer_roads=prefer_roads, capture_steps=False)
                if path is None:
                    continue
                
                # Optimizar el camino
                optimized_path = self._optimize_path_with_straight_lines(path)
                
                # Asegurar que el camino empiece en la posición inicial del tractor
                if optimized_path and optimized_path[0] != start_pos:
                    optimized_path = [start_pos] + optimized_path
                
                # Verificar conflictos: el destino no debe estar en el camino de otro tractor
                conflicts = False
                for existing_result in results:
                    existing_path = existing_result['path']
                    existing_dest = existing_result['end']
                    
                    # Verificar si el nuevo destino está en el camino de otro tractor
                    if dest in existing_path[:-1]:
                        conflicts = True
                        break
                    
                    # Verificar si algún punto del nuevo camino está en el destino de otro tractor
                    for path_pos in optimized_path[:-1]:
                        if path_pos == existing_dest:
                            conflicts = True
                            break
                    
                    if conflicts:
                        break
                
                if not conflicts:
                    results.append({
                        'path': optimized_path,
                        'start': start_pos,
                        'end': dest,
                        'infestation': infestation_grid[dest[1]][dest[0]]
                    })
                    used_destinations.add(dest)
                    path_found = True
                    break
            
            if not path_found:
                # Si no se encontró un destino sin conflictos, usar el siguiente más infestado disponible
                for infested_pos in infested_positions:
                    if infested_pos not in used_destinations:
                        dest = infested_pos
                        start_pos = barn_start_positions[tractor_id]
                        path = self.dijkstra(start_pos, dest, prefer_roads=prefer_roads, capture_steps=False)
                        if path is not None:
                            optimized_path = self._optimize_path_with_straight_lines(path)
                            if optimized_path and optimized_path[0] != start_pos:
                                optimized_path = [start_pos] + optimized_path
                            results.append({
                                'path': optimized_path,
                                'start': start_pos,
                                'end': dest,
                                'infestation': infestation_grid[dest[1]][dest[0]]
                            })
                            used_destinations.add(dest)
                            break
        
        return results if results else None

    def simulate_tractors(
        self,
        tractor_paths: List[List[Tuple[int, int]]],
        max_steps: int = 1000
    ) -> List[List[Dict]]:
        """
        Simula el movimiento de múltiples tractores con detección de colisiones.
        Los tractores que llegaron a su destino bloquean físicamente y los demás
        deben recalcular su ruta si su camino está bloqueado.
        
        Args:
            tractor_paths: Lista de caminos, uno por cada tractor
            max_steps: Número máximo de pasos de simulación
        
        Returns:
            Lista de listas, donde cada lista interna contiene los estados de un tractor
            en cada paso. Cada estado es un dict con:
            - 'position': (x, z) posición actual
            - 'path_index': índice en el camino (o -1 si se recalculó)
            - 'waiting': bool si está esperando por colisión
            - 'path_recalculated': bool si se recalculó el camino
        """
        num_tractors = len(tractor_paths)
        if num_tractors == 0:
            return []
        
        # Inicializar posiciones: cada tractor empieza en su celda asignada del granero
        # (el primer elemento de su camino es su posición inicial)
        tractor_positions = [0] * num_tractors  # Índice en el camino de cada tractor
        # Mantener los caminos originales y los recalculados
        current_paths = [path[:] for path in tractor_paths]  # Copia de los caminos
        simulation_steps = []
        
        # Colores para cada tractor (para visualización)
        tractor_colors = [
            '#ff0000', '#00ff00', '#0000ff', '#ffff00', '#ff00ff',
            '#00ffff', '#ff8800', '#8800ff', '#88ff00', '#ff0088'
        ]
        
        # Agregar paso inicial: todos los tractores en sus posiciones iniciales del granero
        initial_step = []
        for tractor_id in range(num_tractors):
            path = current_paths[tractor_id]
            if path and len(path) > 0:
                initial_pos = path[0]  # Primera celda del camino = celda del granero asignada
                initial_step.append({
                    'position': initial_pos,
                    'path_index': 0,
                    'waiting': False,
                    'arrived': False,
                    'path_recalculated': False,
                    'color': tractor_colors[tractor_id % len(tractor_colors)]
                })
        simulation_steps.append(initial_step)
        
        for step in range(max_steps):
            step_state = []
            # Diccionario: posición -> lista de tractor_ids en esa posición
            # Incluye TODOS los tractores (los que llegaron también bloquean)
            all_tractor_positions = {}
            
            # Registrar TODAS las posiciones actuales (incluyendo tractores que llegaron)
            for tractor_id in range(num_tractors):
                path = current_paths[tractor_id]
                current_index = tractor_positions[tractor_id]
                
                if current_index < len(path):
                    current_pos = path[current_index]
                    if current_pos not in all_tractor_positions:
                        all_tractor_positions[current_pos] = []
                    all_tractor_positions[current_pos].append(tractor_id)
            
            # Primera pasada: calcular todos los movimientos deseados
            desired_moves = {}  # posición -> lista de (tractor_id, current_pos, next_pos)
            tractor_states = {}  # tractor_id -> estado temporal
            
            for tractor_id in range(num_tractors):
                path = current_paths[tractor_id]
                current_index = tractor_positions[tractor_id]
                
                if current_index >= len(path) - 1:
                    # Tractor ya llegó a su destino - SÍ bloquea físicamente
                    tractor_states[tractor_id] = {
                        'position': path[-1],
                        'path_index': len(path) - 1,
                        'waiting': False,
                        'arrived': True,
                        'path_recalculated': False,
                        'color': tractor_colors[tractor_id % len(tractor_colors)],
                        'can_move': False
                    }
                    continue
                
                next_index = current_index + 1
                next_pos = path[next_index]
                current_pos = path[current_index]
                
                # Verificar si la siguiente posición está bloqueada
                # (por cualquier tractor, incluyendo los que ya llegaron)
                next_pos_blocked = (
                    next_pos in all_tractor_positions and 
                    len(all_tractor_positions[next_pos]) > 0
                )
                
                # Si está bloqueado, verificar si es un bloqueo permanente (tractor que ya llegó)
                # o temporal (otro tractor en movimiento)
                is_permanent_block = False
                if next_pos_blocked:
                    blocking_tractors = all_tractor_positions[next_pos]
                    for blocking_id in blocking_tractors:
                        if blocking_id != tractor_id:
                            blocking_path = current_paths[blocking_id]
                            blocking_index = tractor_positions[blocking_id]
                            # Si el tractor que bloquea ya llegó a su destino, es bloqueo permanente
                            if blocking_index >= len(blocking_path) - 1:
                                is_permanent_block = True
                                break
                
                if is_permanent_block:
                    # Bloqueo permanente: recalcular camino desde posición actual
                    destination = path[-1]  # Destino original
                    
                    # Crear un grid temporal con las posiciones bloqueadas como intransitables
                    blocked_positions = set()
                    for other_id in range(num_tractors):
                        if other_id != tractor_id:
                            other_path = current_paths[other_id]
                            other_index = tractor_positions[other_id]
                            if other_index >= len(other_path) - 1:
                                # Tractor que ya llegó bloquea su posición
                                blocked_positions.add(other_path[-1])
                    
                    # Recalcular camino evitando posiciones bloqueadas
                    new_path = self._dijkstra_with_blocked(
                        current_pos, 
                        destination, 
                        blocked_positions,
                        prefer_roads=True
                    )
                    
                    if new_path and len(new_path) > 1:
                        # Actualizar el camino del tractor
                        # El nuevo camino debe empezar desde la posición actual
                        # (el primer elemento del nuevo camino debería ser current_pos)
                        if new_path[0] != current_pos:
                            # Si el nuevo camino no empieza en la posición actual, ajustarlo
                            new_path = [current_pos] + [p for p in new_path if p != current_pos]
                        
                        current_paths[tractor_id] = new_path
                        tractor_positions[tractor_id] = 0  # Empezar desde el inicio del nuevo camino
                        
                        tractor_states[tractor_id] = {
                            'position': current_pos,
                            'path_index': -1,  # Indica que se recalculó
                            'waiting': False,
                            'arrived': False,
                            'path_recalculated': True,
                            'color': tractor_colors[tractor_id % len(tractor_colors)],
                            'can_move': False
                        }
                    else:
                        # No se pudo encontrar camino alternativo, esperar
                        tractor_states[tractor_id] = {
                            'position': current_pos,
                            'path_index': current_index,
                            'waiting': True,
                            'arrived': False,
                            'path_recalculated': False,
                            'color': tractor_colors[tractor_id % len(tractor_colors)],
                            'can_move': False
                        }
                elif next_pos_blocked:
                    # Bloqueo temporal: esperar (otro tractor en movimiento)
                    tractor_states[tractor_id] = {
                        'position': current_pos,
                        'path_index': current_index,
                        'waiting': True,
                        'arrived': False,
                        'path_recalculated': False,
                        'color': tractor_colors[tractor_id % len(tractor_colors)],
                        'can_move': False
                    }
                else:
                    # Puede avanzar - registrar movimiento deseado
                    if next_pos not in desired_moves:
                        desired_moves[next_pos] = []
                    desired_moves[next_pos].append((tractor_id, current_pos, next_pos))
                    tractor_states[tractor_id] = {
                        'position': current_pos,
                        'path_index': current_index,
                        'waiting': False,
                        'arrived': False,
                        'path_recalculated': False,
                        'color': tractor_colors[tractor_id % len(tractor_colors)],
                        'can_move': True,
                        'next_pos': next_pos,
                        'next_index': next_index
                    }
            
            # Segunda pasada: resolver conflictos - solo un tractor por celda
            occupied_positions = set()  # Posiciones ya ocupadas en este paso
            
            # Primero, procesar tractores que ya llegaron (bloquean sus posiciones)
            for tractor_id in range(num_tractors):
                if tractor_id in tractor_states and not tractor_states[tractor_id].get('can_move', True):
                    pos = tractor_states[tractor_id]['position']
                    occupied_positions.add(pos)
            
            # Luego, procesar movimientos deseados, dando prioridad al primer tractor que quiere moverse
            for next_pos, movers in desired_moves.items():
                if next_pos in occupied_positions:
                    # La celda ya está ocupada, todos los que quieren moverse ahí deben esperar
                    for tractor_id, current_pos, _ in movers:
                        tractor_states[tractor_id] = {
                            'position': current_pos,
                            'path_index': tractor_states[tractor_id]['path_index'],
                            'waiting': True,
                            'arrived': False,
                            'path_recalculated': False,
                            'color': tractor_colors[tractor_id % len(tractor_colors)],
                            'can_move': False
                        }
                else:
                    # Solo el primer tractor puede moverse a esta celda
                    tractor_id, current_pos, _ = movers[0]
                    next_index = tractor_states[tractor_id]['next_index']
                    tractor_positions[tractor_id] = next_index
                    tractor_states[tractor_id] = {
                        'position': next_pos,
                        'path_index': next_index,
                        'waiting': False,
                        'arrived': False,
                        'path_recalculated': False,
                        'color': tractor_colors[tractor_id % len(tractor_colors)],
                        'can_move': False
                    }
                    occupied_positions.add(next_pos)
                    
                    # Los demás deben esperar
                    for other_tractor_id, other_current_pos, _ in movers[1:]:
                        tractor_states[other_tractor_id] = {
                            'position': other_current_pos,
                            'path_index': tractor_states[other_tractor_id]['path_index'],
                            'waiting': True,
                            'arrived': False,
                            'path_recalculated': False,
                            'color': tractor_colors[other_tractor_id % len(tractor_colors)],
                            'can_move': False
                        }
            
            # Agregar todos los estados al paso
            for tractor_id in range(num_tractors):
                if tractor_id in tractor_states:
                    state = tractor_states[tractor_id].copy()
                    # Remover campos internos antes de agregar al paso
                    state.pop('can_move', None)
                    state.pop('next_pos', None)
                    state.pop('next_index', None)
                    step_state.append(state)
            
            simulation_steps.append(step_state)
            
            # Verificar si todos llegaron
            all_arrived = all(
                tractor_positions[i] >= len(current_paths[i]) - 1
                for i in range(num_tractors)
            )
            if all_arrived:
                break
        
        return simulation_steps
    
    def _dijkstra_with_blocked(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        blocked_positions: Set[Tuple[int, int]],
        prefer_roads: bool = True
    ) -> Optional[List[Tuple[int, int]]]:
        """
        Implementa Dijkstra evitando posiciones bloqueadas.
        
        Args:
            start: Posición inicial
            end: Posición destino
            blocked_positions: Conjunto de posiciones bloqueadas (intransitables temporalmente)
            prefer_roads: Si True, prioriza caminos
        
        Returns:
            Lista de tuplas (x, z) del camino, o None si no hay camino
        """
        if not self._is_passable(*start) or not self._is_passable(*end):
            return None
        
        if start in blocked_positions or end in blocked_positions:
            return None
        
        # Cola de prioridad: (costo_acumulado, x, z)
        pq = [(0, start[0], start[1])]
        
        # Diccionario para guardar el costo mínimo a cada celda
        costs = {start: 0}
        
        # Diccionario para reconstruir el camino
        came_from = {start: None}
        
        visited = set()
        
        while pq:
            current_cost, x, z = heapq.heappop(pq)
            current = (x, z)
            
            if current in visited:
                continue
            
            visited.add(current)
            
            # Si llegamos al destino
            if current == end:
                # Reconstruir el camino
                path = []
                node = end
                while node is not None:
                    path.append(node)
                    node = came_from[node]
                path.reverse()
                return path
            
            # Explorar vecinos
            for neighbor in self._get_neighbors(x, z):
                if neighbor in visited or neighbor in blocked_positions:
                    continue
                
                if not self._is_passable(*neighbor):
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
        
        IMPORTANTE: 
        - Los caminos (ROAD) siempre tienen costo bajo y NO se les aplica peso dinámico.
        - Los campos (FIELD) tienen pesos dinámicos pero con límite máximo para evitar bloqueos.
        - Si es necesario pasar por un campo con peso alto, se puede hacer (no es infinito).
        """
        base_cost = super()._get_cost(x, z, prefer_roads)
        
        # Si es un campo, agregar peso dinámico (que aumenta cuando se pisa)
        if self.grid[z][x] == TileType.FIELD:
            dynamic_weight = self.field_weights.get((x, z), 0.0)
            # El peso dinámico ya está limitado a 100.0 en _update_field_weight
            # Pero aquí también aplicamos un límite de seguridad
            effective_weight = min(dynamic_weight, 100.0)
            return base_cost + effective_weight
        
        # Para ROAD y BARN, retornar el costo base sin modificar
        # Esto asegura que los caminos siempre tengan prioridad
        return base_cost
