import random
from enum import IntEnum
from typing import List, Tuple, Set, Optional, Dict, Any


class TileType(IntEnum):
    """Tipos de celda en el grid"""
    IMPASSABLE = 0
    ROAD = 1
    FIELD = 2
    BARN = 3


class CropType(IntEnum):
    """Tipos de cultivo"""
    NONE = 0
    WHEAT = 1
    CORN = 2
    SOY = 3


class WorldGenerator:
    """Generador optimizado de mundos 2D"""

    def __init__(self, width: int, height: int, seed: Optional[int] = None):
        self.width = width
        self.height = height
        self.seed = seed
        
        if seed is not None:
            random.seed(seed)
        
        # Grids principales
        self.grid: List[List[int]] = []
        self.crop_grid: List[List[int]] = []
        self.infestation_grid: List[List[int]] = []
        
        # Estadísticas
        self.stats = {
            'field_count': 0,
            'road_count': 0,
            'total_cells': width * height
        }

    def _reset(self) -> None:
        """Reinicia todos los grids"""
        # Inicializar como None (vacío) en lugar de IMPASSABLE
        # Los intransitables se agregarán al final
        self.grid = [[None for _ in range(self.width)] for _ in range(self.height)]
        self.crop_grid = [[CropType.NONE for _ in range(self.width)] for _ in range(self.height)]
        self.infestation_grid = [[0 for _ in range(self.width)] for _ in range(self.height)]

    def _in_bounds(self, x: int, z: int) -> bool:
        """Verifica si las coordenadas están dentro de los límites"""
        return 0 <= x < self.width and 0 <= z < self.height

    def _is_free(self, x: int, z: int) -> bool:
        """Verifica si una celda está libre (None/vacía, como CellModels)"""
        return self._in_bounds(x, z) and self.grid[z][x] is None

    def _get_neighbors(self, x: int, z: int) -> List[Tuple[int, int]]:
        """Retorna las coordenadas de los 4 vecinos directos"""
        neighbors = []
        for dx, dz in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, nz = x + dx, z + dz
            if self._in_bounds(nx, nz):
                neighbors.append((nx, nz))
        return neighbors

    def _place_barn(self) -> Tuple[int, int]:
        """
        Coloca el granero de 5 casillas en línea (horizontal o vertical) y lo rodea de camino.
        Retorna la posición central (tercera casilla) del granero.
        """
        # Margen necesario: 2 casillas para el granero + 1 para el camino alrededor
        margin = 3
        
        # Decidir si será horizontal o vertical
        is_horizontal = random.choice([True, False])
        
        # Intentar colocar el granero en una posición válida
        max_attempts = 50
        for _ in range(max_attempts):
            if is_horizontal:
                # Granero horizontal: 5 casillas en fila
                # Necesitamos espacio: 5 casillas + 2 de margen = 7 mínimo
                if self.width < 7:
                    is_horizontal = False
                    continue
                
                start_x = random.randint(margin, self.width - margin - 5)
                center_z = random.randint(margin, self.height - margin - 1)
                
                # Posiciones del granero en línea horizontal
                barn_positions = [
                    (start_x, center_z),
                    (start_x + 1, center_z),
                    (start_x + 2, center_z),  # Centro
                    (start_x + 3, center_z),
                    (start_x + 4, center_z),
                ]
                center_x = start_x + 2
            else:
                # Granero vertical: 5 casillas en columna
                # Necesitamos espacio: 5 casillas + 2 de margen = 7 mínimo
                if self.height < 7:
                    is_horizontal = True
                    continue
                
                center_x = random.randint(margin, self.width - margin - 1)
                start_z = random.randint(margin, self.height - margin - 5)
                
                # Posiciones del granero en línea vertical
                barn_positions = [
                    (center_x, start_z),
                    (center_x, start_z + 1),
                    (center_x, start_z + 2),  # Centro
                    (center_x, start_z + 3),
                    (center_x, start_z + 4),
                ]
                center_z = start_z + 2
            
            # Verificar que todas las posiciones del granero estén libres
            if all(self._is_free(x, z) for x, z in barn_positions):
                # Colocar las 5 casillas del granero
                for x, z in barn_positions:
                    self.grid[z][x] = TileType.BARN
                
                # Rodearlo completamente de camino (8 direcciones alrededor de cada casilla del granero)
                road_positions = set()
                for bx, bz in barn_positions:
                    # Agregar los 8 vecinos de cada casilla del granero
                    for dx in [-1, 0, 1]:
                        for dz in [-1, 0, 1]:
                            if dx == 0 and dz == 0:
                                continue  # Saltar la casilla del granero misma
                            rx, rz = bx + dx, bz + dz
                            # Solo agregar si está libre y dentro de los límites
                            if self._is_free(rx, rz) and self._in_bounds(rx, rz):
                                road_positions.add((rx, rz))
                
                # Colocar los caminos alrededor del granero
                for rx, rz in road_positions:
                    self.grid[rz][rx] = TileType.ROAD
                
                return center_x, center_z
        
        # Si no se pudo colocar después de varios intentos, usar posición por defecto
        center_x = self.width // 2
        center_z = self.height // 2
        
        # Intentar horizontal primero
        if self.width >= 7:
            start_x = max(2, center_x - 2)
            start_x = min(start_x, self.width - 5)
            barn_positions = [
                (start_x, center_z),
                (start_x + 1, center_z),
                (start_x + 2, center_z),
                (start_x + 3, center_z),
                (start_x + 4, center_z),
            ]
            center_x = start_x + 2
        else:
            # Usar vertical si no hay espacio horizontal
            start_z = max(2, center_z - 2)
            start_z = min(start_z, self.height - 5)
            barn_positions = [
                (center_x, start_z),
                (center_x, start_z + 1),
                (center_x, start_z + 2),
                (center_x, start_z + 3),
                (center_x, start_z + 4),
            ]
            center_z = start_z + 2
        
        # Colocar el granero
        for x, z in barn_positions:
            if self._in_bounds(x, z):
                self.grid[z][x] = TileType.BARN
        
        # Rodearlo de camino
        road_positions = set()
        for bx, bz in barn_positions:
            if self._in_bounds(bx, bz):
                for dx in [-1, 0, 1]:
                    for dz in [-1, 0, 1]:
                        if dx == 0 and dz == 0:
                            continue
                        rx, rz = bx + dx, bz + dz
                        if self._in_bounds(rx, rz) and self.grid[rz][rx] != TileType.BARN:
                            road_positions.add((rx, rz))
        
        for rx, rz in road_positions:
            self.grid[rz][rx] = TileType.ROAD
        
        return center_x, center_z

    def _generate_roads(
        self, 
        start_x: int, 
        start_z: int, 
        branch_chance: float, 
        max_length: int
    ) -> Set[Tuple[int, int]]:
        """
        Genera caminos con sistema de ramificación desde el granero.
        Incluye los caminos que ya rodean al granero.
        """
        road_cells: Set[Tuple[int, int]] = set()
        
        # Primero, agregar los caminos que ya rodean al granero
        # (estos fueron colocados en _place_barn)
        barn_positions = [
            (start_x, start_z),
            (start_x, start_z - 1),
            (start_x, start_z + 1),
            (start_x - 1, start_z),
            (start_x + 1, start_z),
        ]
        
        for bx, bz in barn_positions:
            if self._in_bounds(bx, bz):
                # Agregar los 8 vecinos de cada casilla del granero que sean caminos
                for dx in [-1, 0, 1]:
                    for dz in [-1, 0, 1]:
                        if dx == 0 and dz == 0:
                            continue
                        rx, rz = bx + dx, bz + dz
                        if self._in_bounds(rx, rz) and self.grid[rz][rx] == TileType.ROAD:
                            road_cells.add((rx, rz))
        
        # Ahora generar caminos ramificados desde las casillas de camino alrededor del granero
        # Usar las 4 direcciones principales desde el centro del granero
        stack = []
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        
        # Agregar puntos de inicio desde los caminos alrededor del granero
        for bx, bz in barn_positions:
            if self._in_bounds(bx, bz):
                for dx, dz in directions:
                    rx, rz = bx + dx, bz + dz
                    if self._in_bounds(rx, rz) and self.grid[rz][rx] == TileType.ROAD:
                        stack.append((rx, rz))
        
        # Generar caminos ramificados
        while stack:
            x, z = stack.pop()
            
            for dx, dz in directions:
                if random.random() < branch_chance:
                    length = random.randint(2, max_length)
                    cx, cz = x, z
                    
                    for _ in range(length):
                        cx += dx
                        cz += dz
                        
                        if not self._is_free(cx, cz):
                            break
                        
                        self.grid[cz][cx] = TileType.ROAD
                        road_cells.add((cx, cz))
                        
                        # Chance de crear una rama adicional
                        if random.random() < 0.1:
                            stack.append((cx, cz))
        
        return road_cells

    def _place_initial_fields(
        self, 
        road_cells: Set[Tuple[int, int]], 
        field_chance: float
    ) -> Set[Tuple[int, int]]:
        """Coloca campos iniciales adyacentes a los caminos (similar a CellModels)"""
        field_cells: Set[Tuple[int, int]] = set()
        crop_types = [CropType.WHEAT, CropType.CORN, CropType.SOY]
        
        # Iterar sobre todas las celdas libres
        for z in range(self.height):
            for x in range(self.width):
                # Solo considerar celdas libres (intransitables)
                if not self._is_free(x, z):
                    continue
                
                # Verificar si tiene vecino camino
                has_road_neighbor = any(
                    (nx, nz) in road_cells 
                    for nx, nz in self._get_neighbors(x, z)
                )
                
                if has_road_neighbor and random.random() < field_chance:
                    self.grid[z][x] = TileType.FIELD
                    self.crop_grid[z][x] = random.choice(crop_types)
                    self.infestation_grid[z][x] = random.randint(0, 100)
                    field_cells.add((x, z))
        
        return field_cells

    def _grow_fields(
        self, 
        field_cells: Set[Tuple[int, int]], 
        growth_chance: float, 
        rounds: int = 4
    ) -> None:
        """Expande los campos hacia celdas vacías adyacentes"""
        crop_types = [CropType.WHEAT, CropType.CORN, CropType.SOY]
        
        for _ in range(rounds):
            new_fields: Set[Tuple[int, int]] = set()
            
            # Iterar sobre todas las celdas libres (solo intransitables)
            for z in range(self.height):
                for x in range(self.width):
                    # Solo considerar celdas que están libres (intransitables)
                    if not self._is_free(x, z):
                        continue
                    
                    # Verificar si tiene vecino campo
                    has_field_neighbor = any(
                        (nx, nz) in field_cells 
                        for nx, nz in self._get_neighbors(x, z)
                    )
                    
                    if has_field_neighbor and random.random() < growth_chance:
                        self.grid[z][x] = TileType.FIELD
                        self.crop_grid[z][x] = random.choice(crop_types)
                        self.infestation_grid[z][x] = random.randint(0, 100)
                        new_fields.add((x, z))
            
            # Actualizar el conjunto de campos con los nuevos
            field_cells.update(new_fields)

    def _count_connected_fields(self) -> int:
        """Cuenta grupos de campos conectados usando BFS"""
        visited: Set[Tuple[int, int]] = set()
        field_groups = 0
        
        for z in range(self.height):
            for x in range(self.width):
                if self.grid[z][x] != TileType.FIELD or (x, z) in visited:
                    continue
                
                # BFS para marcar todo el grupo
                queue = [(x, z)]
                field_groups += 1
                
                while queue:
                    cx, cz = queue.pop(0)
                    
                    if (cx, cz) in visited:
                        continue
                    
                    visited.add((cx, cz))
                    
                    for nx, nz in self._get_neighbors(cx, cz):
                        if (self.grid[nz][nx] == TileType.FIELD and 
                            (nx, nz) not in visited):
                            queue.append((nx, nz))
        
        return field_groups

    def _calculate_stats(self) -> None:
        """Calcula estadísticas del mundo generado"""
        road_count = sum(1 for z in range(self.height) for x in range(self.width) 
                        if self.grid[z][x] == TileType.ROAD)
        field_count = self._count_connected_fields()
        field_cells = sum(1 for z in range(self.height) for x in range(self.width) 
                         if self.grid[z][x] == TileType.FIELD)
        barn_cells = sum(1 for z in range(self.height) for x in range(self.width) 
                        if self.grid[z][x] == TileType.BARN)
        
        # Estadísticas por tipo de cultivo
        crop_stats = {
            'wheat': 0,
            'corn': 0,
            'soy': 0
        }
        
        total_infestation = 0
        for z in range(self.height):
            for x in range(self.width):
                if self.grid[z][x] == TileType.FIELD:
                    crop_type = self.crop_grid[z][x]
                    if crop_type == CropType.WHEAT:
                        crop_stats['wheat'] += 1
                    elif crop_type == CropType.CORN:
                        crop_stats['corn'] += 1
                    elif crop_type == CropType.SOY:
                        crop_stats['soy'] += 1
                    total_infestation += self.infestation_grid[z][x]
        
        avg_infestation = total_infestation / field_cells if field_cells > 0 else 0
        
        self.stats = {
            'total_cells': self.width * self.height,
            'road_count': road_count,
            'field_count': field_count,
            'field_cells': field_cells,
            'barn_cells': barn_cells,
            'total_barns': 1,  # Siempre hay un granero
            'impassable_cells': self.width * self.height - road_count - field_cells - barn_cells,
            'crop_distribution': crop_stats,
            'average_infestation': round(avg_infestation, 2)
        }

    def generate(
        self,
        road_branch_chance: float = 0.6,  # Más caminos para mejor distribución
        max_road_length: int = 10,  # Caminos más largos
        field_chance: float = 0.9,  # Alta probabilidad de campos iniciales
        field_growth_chance: float = 0.55,  # Mayor crecimiento
        field_growth_rounds: int = 10,  # Número de rondas de crecimiento de campos
        min_fields: int = 5,
        min_roads: int = 10,
        max_attempts: int = 30
    ) -> bool:
        """
        Genera el mundo con reintentos hasta cumplir requisitos mínimos.
        Si después de varios intentos no se cumplen los requisitos, acepta el mejor resultado.
        
        Returns:
            bool: True si se generó exitosamente
        """
        best_attempt = None
        best_score = -1
        
        for attempt in range(max_attempts):
            self._reset()
            
            # 1. Colocar granero
            bx, bz = self._place_barn()
            
            # 2. Generar caminos ramificados
            road_cells = self._generate_roads(bx, bz, road_branch_chance, max_road_length)
            
            # 3. Colocar campos iniciales
            field_cells = self._place_initial_fields(road_cells, field_chance)
            
            # 4. Expandir campos
            self._grow_fields(field_cells, field_growth_chance, rounds=field_growth_rounds)
            
            # 5. Llenar espacios vacíos con intransitables
            for z in range(self.height):
                for x in range(self.width):
                    if self.grid[z][x] is None:
                        self.grid[z][x] = TileType.IMPASSABLE
            
            # 6. Calcular estadísticas
            self._calculate_stats()
            
            # Verificar requisitos mínimos
            if self.stats['field_count'] >= min_fields and self.stats['road_count'] >= min_roads:
                print(f"✅ Mundo generado en intento {attempt + 1}: "
                      f"{self.stats['field_count']} campos, {self.stats['road_count']} caminos")
                return True
            
            # Calcular score para guardar el mejor intento
            # Score = campos + caminos (priorizando que ambos estén cerca de los mínimos)
            field_score = min(self.stats['field_count'] / min_fields, 1.0) if min_fields > 0 else 0
            road_score = min(self.stats['road_count'] / min_roads, 1.0) if min_roads > 0 else 0
            current_score = field_score * 0.5 + road_score * 0.5
            
            if current_score > best_score:
                best_score = current_score
                # Convertir None a IMPASSABLE antes de guardar
                grid_copy = []
                for row in self.grid:
                    grid_copy.append([TileType.IMPASSABLE if cell is None else cell for cell in row])
                best_attempt = {
                    'grid': grid_copy,
                    'crop_grid': [row[:] for row in self.crop_grid],
                    'infestation_grid': [row[:] for row in self.infestation_grid],
                    'stats': self.stats.copy()
                }
            
            # Después de la mitad de los intentos, si tenemos un resultado razonable, aceptarlo
            if attempt >= max_attempts // 2 and best_attempt:
                # Aceptar si tenemos al menos 70% de los requisitos mínimos
                if (self.stats['field_count'] >= min_fields * 0.7 and 
                    self.stats['road_count'] >= min_roads * 0.7):
                    print(f"⚠️ Aceptando resultado parcial en intento {attempt + 1}: "
                          f"{self.stats['field_count']} campos, {self.stats['road_count']} caminos")
                    return True
            
            if attempt < 10 or (attempt + 1) % 5 == 0:
                print(f"⚠️ Intento {attempt + 1}: "
                      f"{self.stats['field_count']} campos, {self.stats['road_count']} caminos")
        
        # Si llegamos aquí, usar el mejor intento guardado
        if best_attempt:
            self.grid = best_attempt['grid']
            self.crop_grid = best_attempt['crop_grid']
            self.infestation_grid = best_attempt['infestation_grid']
            self.stats = best_attempt['stats']
            print(f"⚠️ Usando mejor resultado encontrado: "
                  f"{self.stats['field_count']} campos, {self.stats['road_count']} caminos")
            return True
        
        print(f"❌ No se pudo generar un mundo válido en {max_attempts} intentos")
        return False

    def export(self) -> Dict[str, Any]:
        """Exporta el mundo a un diccionario con las matrices"""
        return {
            'width': self.width,
            'height': self.height,
            'seed': self.seed,
            'grid': self.grid,
            'crop_grid': self.crop_grid,
            'infestation_grid': self.infestation_grid,
            'legend': {
                'tile_types': {
                    'IMPASSABLE': TileType.IMPASSABLE,
                    'ROAD': TileType.ROAD,
                    'FIELD': TileType.FIELD,
                    'BARN': TileType.BARN
                },
                'crop_types': {
                    'NONE': CropType.NONE,
                    'WHEAT': CropType.WHEAT,
                    'CORN': CropType.CORN,
                    'SOY': CropType.SOY
                }
            },
            'stats': self.stats
        }
