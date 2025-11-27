"""
Sistema de agentes usando AgentPy que se comunican con el blackboard de Django.
Los agentes coordinan para fumigar campos con infestación.
Sistema basado en eventos en tiempo real: el backend emite eventos granulares
que el frontend/Unity pueden escuchar y renderizar.
"""
import agentpy as ap
from typing import List, Tuple, Optional, Dict, Any
import math
import time
from django.db import transaction
from .services import BlackboardService
from .models import BlackboardTask, TaskStatus
from .simulation_events import EventEmitter
from agents.models import Agent as AgentModel
from world.models import World
from world.world_generator import TileType
from world.pathfinding import Pathfinder, DynamicPathfinder


class ScoutAgent(ap.Agent):
    """
    Agente explorador (dron) que analiza campos para descubrir niveles de infestación.
    No daña la tierra y puede moverse libremente.
    """
    
    def setup(self):
        """Inicializa el agente scout"""
        # Obtener posición inicial del modelo, o usar valor por defecto
        self.position = self.model.start_positions.get(
            self.id, 
            (self.model.world_instance.width // 2, self.model.world_instance.height // 2)
        )
        self.status = 'scouting'  # scouting, moving
        self.fields_analyzed = 0
        self.discoveries = 0
        
        # Referencias al mundo y blackboard
        self.world_instance = self.model.world_instance
        self.blackboard = self.model.blackboard_service
        self.grid = self.world_instance.grid
        self.infestation_grid = self.world_instance.infestation_grid
        self.width = self.world_instance.width
        self.height = self.world_instance.height
        
        # Pathfinder para movimiento (puede usar cualquier ruta)
        self.pathfinder = Pathfinder(self.grid, self.width, self.height)
        
        # Lista de campos ya analizados
        self.analyzed_fields = set()
    
    def step(self):
        """Ejecuta un paso del agente scout"""
        # Buscar campos cercanos no analizados
        target_field = self._find_unanalyzed_field()
        
        if target_field:
            # Moverse hacia el campo
            if self.position != target_field:
                self._move_towards(target_field)
            else:
                # Analizar el campo
                self._analyze_field(target_field)
        else:
            # Explorar aleatoriamente
            self._explore()
    
    def _find_unanalyzed_field(self) -> Optional[Tuple[int, int]]:
        """Encuentra un campo cercano no analizado"""
        # Buscar campos en un radio creciente
        for radius in range(1, min(self.width, self.height)):
            candidates = []
            for dx in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    if abs(dx) + abs(dz) == radius:  # Solo borde del radio
                        x = self.position[0] + dx
                        z = self.position[1] + dz
                        pos = (x, z)
                        
                        if (self._is_valid_position(pos) and 
                            self.grid[z][x] == TileType.FIELD and
                            pos not in self.analyzed_fields):
                            candidates.append(pos)
            
            if candidates:
                # Elegir el más cercano
                return min(candidates, key=lambda p: self._calculate_distance(self.position, p))
        
        return None
    
    def _move_towards(self, target: Tuple[int, int]):
        """Se mueve hacia el objetivo usando pathfinding y revela infestación al pasar"""
        old_status = self.status
        self.status = 'moving'

        if old_status != self.status:
            self.model.event_emitter.emit_agent_status_changed(
                str(self.id), 'scout', old_status, self.status, self.position
            )

        # Usar pathfinding (el scout puede usar cualquier ruta, no le importa el peso)
        path = self.pathfinder.dijkstra(self.position, target, prefer_roads=False)

        if path and len(path) > 1:
            # Moverse al siguiente paso del camino
            next_pos = path[1]
            from_pos = self.position

            # Emitir evento de movimiento
            self.model.event_emitter.emit_agent_moved(
                str(self.id), 'scout', from_pos, next_pos, path
            )

            # Ejecutar movimiento
            self.position = next_pos
            self._reveal_infestation_around_position(next_pos)
    
    def _reveal_infestation_around_position(self, pos: Tuple[int, int]):
        """Revela infestación en la posición actual y las filas arriba y abajo (3 filas total)"""
        x, z = pos

        # Recopilar todas las posiciones reveladas para emitir un solo evento
        revealed_positions = []
        infestation_data = []

        # Analizar la fila actual y una arriba y una abajo
        for dz in [-1, 0, 1]:
            analyze_z = z + dz
            if 0 <= analyze_z < self.height:
                # Analizar toda la fila
                for analyze_x in range(self.width):
                    field_pos = (analyze_x, analyze_z)

                    # Solo analizar campos (no caminos ni granero)
                    if self.grid[analyze_z][analyze_x] != TileType.FIELD:
                        continue

                    # Si ya fue analizado, saltar
                    if field_pos in self.analyzed_fields:
                        continue

                    # Marcar como analizado
                    self.analyzed_fields.add(field_pos)
                    self.fields_analyzed += 1
                    revealed_positions.append(field_pos)

                    # Obtener nivel de infestación
                    infestation = self.infestation_grid[analyze_z][analyze_x]

                    # Agregar datos de infestación
                    infestation_data.append({
                        'position': [analyze_x, analyze_z],
                        'infestation_level': infestation
                    })

                    # Si hay infestación significativa, crear tarea en el blackboard
                    if infestation >= self.model.min_infestation:
                        # Verificar si ya existe una tarea para este campo
                        existing_task = self.blackboard.get_task_by_position(analyze_x, analyze_z)

                        if not existing_task:
                            # Crear nueva tarea
                            task = self.blackboard.create_task(
                                position_x=analyze_x,
                                position_z=analyze_z,
                                infestation_level=infestation,
                                metadata={
                                    'crop_type': self.world_instance.crop_grid[analyze_z][analyze_x],
                                    'discovered_by': str(self.id)
                                }
                            )
                            self.discoveries += 1

                            # Emitir evento de infestación descubierta
                            self.model.event_emitter.emit_infestation_discovered(
                                str(self.id), field_pos, infestation, str(task.id)
                            )

                            # Emitir evento de tarea creada
                            self.model.event_emitter.emit_task_created(
                                str(task.id), field_pos, infestation,
                                task.priority, str(self.id)
                            )

        # Emitir evento de área revelada (consolidado)
        if revealed_positions:
            self.model.event_emitter.emit_scout_reveal_area(
                str(self.id), revealed_positions, infestation_data
            )
    
    def _analyze_field(self, field_pos: Tuple[int, int]):
        """Analiza un campo para descubrir su nivel de infestación (legacy, ahora usa _reveal_infestation_around_position)"""
        self._reveal_infestation_around_position(field_pos)
        self.status = 'scouting'
    
    def _explore(self):
        """Explora el mundo cuando no hay campos cercanos"""
        # Moverse aleatoriamente hacia campos no analizados
        unanalyzed = []
        for z in range(self.height):
            for x in range(self.width):
                if (self.grid[z][x] == TileType.FIELD and 
                    (x, z) not in self.analyzed_fields):
                    unanalyzed.append((x, z))
        
        if unanalyzed:
            # Elegir uno aleatorio
            target = self.random.choice(unanalyzed)
            self._move_towards(target)
        else:
            # Todos los campos analizados, moverse aleatoriamente
            neighbors = self._get_neighbors(self.position)
            if neighbors:
                self.position = self.random.choice(neighbors)
    
    def _get_neighbors(self, pos: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Obtiene vecinos transitables"""
        x, z = pos
        neighbors = []
        for dx, dz in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            neighbor = (x + dx, z + dz)
            if self._is_valid_position(neighbor):
                neighbors.append(neighbor)
        return neighbors
    
    def _is_valid_position(self, pos: Tuple[int, int]) -> bool:
        """Verifica si una posición es válida y transitable"""
        x, z = pos
        if not (0 <= x < self.width and 0 <= z < self.height):
            return False
        
        tile = self.grid[z][x]
        return tile in (TileType.ROAD, TileType.FIELD, TileType.BARN)
    
    def _calculate_distance(self, pos1: Tuple[int, int], pos2: Tuple[int, int]) -> float:
        """Calcula distancia Manhattan entre dos posiciones"""
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])


class FumigatorAgent(ap.Agent):
    """
    Agente fumigador (tractor pesado) que busca y fumiga campos con infestación.
    Evita pisar campos cuando es posible y aumenta el peso de los campos que pisa.
    Tiene un tanque de pesticida que se consume al fumigar y debe regresar al granero para reabastecerse.
    """
    
    def setup(self):
        """Inicializa el agente fumigador"""
        # Obtener posición inicial del modelo, o usar valor por defecto
        self.position = self.model.start_positions.get(
            self.id,
            (self.model.world_instance.width // 2, self.model.world_instance.height // 2)
        )
        self.status = 'idle'  # idle, moving, fumigating, returning_to_barn, refilling
        self.current_task = None
        self.path = []
        self.path_index = 0
        self.fields_fumigated = 0
        self.tasks_completed = 0
        
        # Sistema de pesticida
        # Capacidad máxima: 1000 unidades (puede fumigar 10 celdas al 100% de infestación)
        self.pesticide_capacity = 1000
        self.pesticide_level = 1000  # Inicia con tanque lleno
        
        # Referencias al mundo y blackboard
        self.world_instance = self.model.world_instance
        self.blackboard = self.model.blackboard_service
        self.grid = self.world_instance.grid
        self.width = self.world_instance.width
        self.height = self.world_instance.height
        
        # Pathfinder con pesos dinámicos
        self.pathfinder = Pathfinder(self.grid, self.width, self.height)
        
        # Encontrar posición del granero (celda inicial)
        self.barn_position = self.position
        # Buscar todas las celdas del granero para poder regresar a cualquiera
        barn_cells = self.pathfinder.find_all_barn_cells()
        if barn_cells:
            # Usar la celda del granero más cercana a la posición inicial
            # Calcular distancia Manhattan directamente
            min_distance = float('inf')
            for barn_cell in barn_cells:
                distance = abs(self.position[0] - barn_cell[0]) + abs(self.position[1] - barn_cell[1])
                if distance < min_distance:
                    min_distance = distance
                    self.barn_position = barn_cell
        
        # Mapa de pesos dinámicos para campos (aumenta cada vez que se pisa)
        # Formato: {(x, z): peso_adicional}
        self.field_weights = {}
    
    def step(self):
        """Ejecuta un paso del agente"""
        # Verificar si necesita regresar al granero para reabastecerse
        if self.pesticide_level <= 0 and self.status != 'returning_to_barn' and self.status != 'refilling':
            self._return_to_barn()
            return
        
        # Si está regresando al granero, continuar el movimiento
        if self.status == 'returning_to_barn':
            self._move_towards_barn()
            return
        
        # Si está reabasteciéndose en el granero
        if self.status == 'refilling':
            self._refill_pesticide()
            return
        
        # Si no tiene tarea y tiene pesticida suficiente, buscar una en el blackboard
        if self.current_task is None:
            # Solo buscar tareas si tiene pesticida suficiente (al menos 10 unidades)
            if self.pesticide_level >= 10:
                self._find_task()
        
        # Si tiene tarea, trabajar en ella
        if self.current_task:
            self._work_on_task()
        else:
            # Si no hay tareas, esperar
            self.status = 'idle'
    
    def _find_task(self):
        """Busca la tarea más infestada disponible en el blackboard"""
        available_tasks = self.blackboard.get_available_tasks(limit=50)

        if not available_tasks:
            if self.status != 'idle':
                self.status = 'idle'
                self.model.event_emitter.emit_agent_idle(
                    str(self.id), 'fumigator', self.position
                )
            return

        # Seleccionar la tarea más infestada que pueda completar
        best_task = None
        max_infestation = -1

        for task in available_tasks:
            # Verificar si tiene suficiente pesticida para esta tarea
            required_pesticide = task.infestation_level
            if self.pesticide_level < required_pesticide:
                continue  # No tiene suficiente pesticida, saltar esta tarea

            # Seleccionar la más infestada
            if task.infestation_level > max_infestation:
                # Intentar asignar la tarea
                if self.blackboard.assign_task(task, str(self.id)):
                    max_infestation = task.infestation_level
                    best_task = task

        if best_task:
            self.current_task = best_task
            self._calculate_path_to_task()

            # Emitir evento de tarea asignada
            self.model.event_emitter.emit_task_assigned(
                str(best_task.id), str(self.id),
                (best_task.position_x, best_task.position_z),
                best_task.infestation_level
            )

            # Marcar como en progreso
            self.blackboard.start_task(best_task)

            # Emitir evento de tarea iniciada
            self.model.event_emitter.emit_task_started(
                str(best_task.id), str(self.id),
                (best_task.position_x, best_task.position_z)
            )
    
    def _calculate_path_to_task(self):
        """Calcula el camino hacia la tarea actual usando pathfinding con pesos dinámicos"""
        if not self.current_task:
            return
        
        target = (self.current_task.position_x, self.current_task.position_z)
        
        # Crear un pathfinder personalizado con pesos dinámicos
        pathfinder = DynamicPathfinder(
            self.grid, 
            self.width, 
            self.height,
            self.field_weights
        )
        
        path = pathfinder.dijkstra(self.position, target, prefer_roads=True)
        
        if path:
            self.path = path
            self.path_index = 0
        else:
            # Si no hay camino, limpiar tarea
            self.current_task = None
    
    def _work_on_task(self):
        """Trabaja en la tarea actual"""
        if not self.current_task:
            return

        # Verificar si tiene pesticida suficiente antes de continuar
        if self.pesticide_level <= 0:
            # Emitir evento de pesticida bajo
            self.model.event_emitter.emit_pesticide_low(
                str(self.id), self.position, 0, self.pesticide_capacity
            )
            # Cancelar tarea y regresar al granero
            self._cancel_task_and_return_to_barn()
            return

        target = (self.current_task.position_x, self.current_task.position_z)

        # Si ya está en el destino, fumigar
        if self.position == target:
            # Verificar pesticida antes de fumigar
            infestation_level = self.current_task.infestation_level
            required_pesticide = infestation_level  # 1 unidad por cada 1% de infestación

            if self.pesticide_level < required_pesticide:
                # Emitir evento de pesticida bajo
                self.model.event_emitter.emit_pesticide_low(
                    str(self.id), self.position,
                    self.pesticide_level, self.pesticide_capacity
                )
                # No tiene suficiente pesticida, cancelar tarea y regresar
                self._cancel_task_and_return_to_barn()
                return

            # Emitir evento de fumigación iniciada
            self.model.event_emitter.emit_fumigation_started(
                str(self.id), target, infestation_level, str(self.current_task.id)
            )

            # Ejecutar fumigación
            self.status = 'fumigating'
            self._complete_task()
        else:
            # Moverse hacia el destino
            old_status = self.status
            self.status = 'moving'
            if old_status != self.status:
                self.model.event_emitter.emit_agent_status_changed(
                    str(self.id), 'fumigator', old_status, self.status, self.position
                )
            self._move_towards_target()
    
    def _move_towards_target(self):
        """Se mueve hacia el objetivo, fumiga celdas en el camino y aumenta peso de campos pisados"""
        if self.path and self.path_index < len(self.path) - 1:
            self.path_index += 1
            next_pos = self.path[self.path_index]
            from_pos = self.position

            # Verificar si es un campo y aumentar su peso exponencialmente
            x, z = next_pos
            should_fumigate = False
            fumigation_data = None

            if self.grid[z][x] == TileType.FIELD:
                # Aumentar peso exponencialmente cada vez que se pisa
                current_weight = self.field_weights.get(next_pos, 0.0)

                if current_weight == 0.0:
                    self.field_weights[next_pos] = 5.0
                else:
                    exponential_factor = 1.8
                    self.field_weights[next_pos] = current_weight * exponential_factor

                # Verificar si necesita fumigar la celda (mientras se mueve)
                if self.infestation_grid[z][x] > 0 and self.pesticide_level > 0:
                    should_fumigate = True
                    infestation_level = self.infestation_grid[z][x]
                    pesticide_needed = min(infestation_level, self.pesticide_level)
                    fumigation_data = {
                        'infestation_level': infestation_level,
                        'pesticide_needed': pesticide_needed,
                        'position': [x, z]
                    }

            # Emitir evento de movimiento
            self.model.event_emitter.emit_agent_moved(
                str(self.id), 'fumigator', from_pos, next_pos, self.path
            )

            # Ejecutar movimiento y fumigación si corresponde
            self._execute_move(next_pos, fumigation_data)
    
    def _execute_move(self, next_pos: Tuple[int, int], fumigation_data: Optional[Dict[str, Any]]):
        """Ejecuta el movimiento y fumigación si es necesario"""
        x, z = next_pos
        self.position = next_pos

        # Ejecutar fumigación si es necesario
        if fumigation_data:
            infestation_level = fumigation_data['infestation_level']
            pesticide_needed = fumigation_data['pesticide_needed']
            old_infestation = self.infestation_grid[z][x]

            # Emitir evento de fumigación en camino
            self.model.event_emitter.emit_fumigation_started(
                str(self.id), next_pos, old_infestation, None
            )

            self.pesticide_level -= pesticide_needed
            self.infestation_grid[z][x] = max(0, infestation_level - pesticide_needed)
            new_infestation = self.infestation_grid[z][x]

            # Emitir evento de cambio de infestación
            self.model.event_emitter.emit_infestation_changed(
                next_pos, old_infestation, new_infestation
            )

            # Si se completó la fumigación de esta celda, crear/completar tarea si existe
            if self.infestation_grid[z][x] == 0:
                task = self.blackboard.get_task_by_position(x, z)
                if task:
                    self.blackboard.complete_task(task)
                    self.fields_fumigated += 1

                    # Emitir evento de fumigación completada
                    self.model.event_emitter.emit_fumigation_completed(
                        str(self.id), next_pos, pesticide_needed, str(task.id)
                    )
    
    def _complete_task(self):
        """Completa la tarea actual y consume pesticida"""
        if self.current_task:
            # Obtener nivel de infestación de la tarea
            infestation_level = self.current_task.infestation_level
            task_id = str(self.current_task.id)
            position = (self.current_task.position_x, self.current_task.position_z)

            # Consumir pesticida proporcional a la infestación
            # 1 unidad de pesticida por cada 1% de infestación
            pesticide_used = infestation_level
            self.pesticide_level = max(0, self.pesticide_level - pesticide_used)

            # Actualizar infestación en el mundo (reducir a 0)
            old_infestation = self.world_instance.infestation_grid[self.current_task.position_z][self.current_task.position_x]
            self.world_instance.infestation_grid[self.current_task.position_z][self.current_task.position_x] = 0

            # Emitir evento de cambio de infestación
            self.model.event_emitter.emit_infestation_changed(
                position, old_infestation, 0
            )

            # Guardar cambios en el mundo
            self.world_instance.save()

            # Marcar tarea como completada en el blackboard
            import time
            completion_time = time.time()
            self.blackboard.complete_task(self.current_task)

            # Emitir evento de fumigación completada
            self.model.event_emitter.emit_fumigation_completed(
                str(self.id), position, pesticide_used, task_id
            )

            # Emitir evento de tarea completada
            self.model.event_emitter.emit_task_completed(
                task_id, str(self.id), position, completion_time
            )

            # Actualizar estadísticas
            self.fields_fumigated += 1
            self.tasks_completed += 1

            # Guardar posición completada para buscar siguiente tarea en radio
            completed_pos = position

            # Limpiar
            self.current_task = None
            self.path = []
            self.path_index = 0

            if hasattr(self, 'fumigation_steps'):
                delattr(self, 'fumigation_steps')

            # Si se quedó sin pesticida, regresar al granero
            if self.pesticide_level <= 0:
                self._return_to_barn()
            else:
                # Buscar siguiente tarea en radio de 3 celdas desde la posición completada
                self._find_task_in_radius(completed_pos, radius=3)
    
    def _return_to_barn(self):
        """Inicia el regreso al granero para reabastecerse"""
        self.status = 'returning_to_barn'
        
        # Cancelar tarea actual si existe
        if self.current_task:
            # Liberar la tarea en el blackboard
            self.current_task.status = 'pending'
            self.current_task.assigned_agent_id = None
            self.current_task.save()
            self.current_task = None
        
        # Calcular camino al granero
        pathfinder = DynamicPathfinder(
            self.grid,
            self.width,
            self.height,
            self.field_weights
        )
        
        path = pathfinder.dijkstra(self.position, self.barn_position, prefer_roads=True)
        
        if path:
            self.path = path
            self.path_index = 0
        else:
            # Si no hay camino, intentar moverse directamente
            self.path = [self.position, self.barn_position]
            self.path_index = 0
    
    def _move_towards_barn(self):
        """Se mueve hacia el granero y aumenta peso de campos pisados exponencialmente"""
        if not self.path or self.path_index >= len(self.path) - 1:
            # Ya llegó al granero
            old_status = self.status
            self.status = 'refilling'
            if old_status != self.status:
                self.model.event_emitter.emit_agent_status_changed(
                    str(self.id), 'fumigator', old_status, self.status, self.position
                )

            # Emitir evento de recarga iniciada
            self.model.event_emitter.emit_agent_refilling(
                str(self.id), self.barn_position,
                self.pesticide_level, self.pesticide_capacity
            )

            self.path = []
            self.path_index = 0
            return

        # Moverse al siguiente paso del camino
        self.path_index += 1
        next_pos = self.path[self.path_index]
        from_pos = self.position

        # Verificar si es un campo y aumentar su peso exponencialmente
        x, z = next_pos
        if self.grid[z][x] == TileType.FIELD:
            # Aumentar peso exponencialmente cada vez que se pisa
            current_weight = self.field_weights.get(next_pos, 0.0)

            if current_weight == 0.0:
                self.field_weights[next_pos] = 5.0
            else:
                exponential_factor = 1.8
                self.field_weights[next_pos] = current_weight * exponential_factor

        # Emitir evento de movimiento
        self.model.event_emitter.emit_agent_moved(
            str(self.id), 'fumigator', from_pos, next_pos, self.path
        )

        # Ejecutar movimiento
        self.position = next_pos

        # Si llegó al granero, cambiar a estado de reabastecimiento
        if self.position == self.barn_position:
            old_status = self.status
            self.status = 'refilling'
            if old_status != self.status:
                self.model.event_emitter.emit_agent_status_changed(
                    str(self.id), 'fumigator', old_status, self.status, self.position
                )

            # Emitir evento de recarga iniciada
            self.model.event_emitter.emit_agent_refilling(
                str(self.id), self.barn_position,
                self.pesticide_level, self.pesticide_capacity
            )

            self.path = []
            self.path_index = 0
    
    def _refill_pesticide(self):
        """Reabastece el tanque de pesticida en el granero"""
        # Reabastecer completamente el tanque
        old_pesticide = self.pesticide_level
        self.pesticide_level = self.pesticide_capacity

        # Emitir evento de recarga completada
        self.model.event_emitter.emit_agent_refill_completed(
            str(self.id), self.barn_position, self.pesticide_level
        )

        # Volver a estado idle para buscar nuevas tareas
        old_status = self.status
        self.status = 'idle'
        if old_status != self.status:
            self.model.event_emitter.emit_agent_status_changed(
                str(self.id), 'fumigator', old_status, self.status, self.position
            )
    
    def _cancel_task_and_return_to_barn(self):
        """Cancela la tarea actual y regresa al granero"""
        if self.current_task:
            # Liberar la tarea en el blackboard
            self.current_task.status = 'pending'
            self.current_task.assigned_agent_id = None
            self.current_task.save()
            self.current_task = None
        
        self.path = []
        self.path_index = 0
        self._return_to_barn()
    
    def _find_task_in_radius(self, center_pos: Tuple[int, int], radius: int = 3):
        """Busca la tarea más infestada en un radio de N celdas desde la posición central"""
        cx, cz = center_pos
        
        # Obtener todas las tareas disponibles
        available_tasks = self.blackboard.get_available_tasks(limit=100)
        
        if not available_tasks:
            self.status = 'idle'
            return
        
        # Filtrar tareas dentro del radio
        tasks_in_radius = []
        for task in available_tasks:
            distance = abs(task.position_x - cx) + abs(task.position_z - cz)
            if distance <= radius:
                # Verificar si tiene suficiente pesticida
                if self.pesticide_level >= task.infestation_level:
                    tasks_in_radius.append((task, distance))
        
        if not tasks_in_radius:
            # No hay tareas en el radio, buscar la más infestada globalmente
            self._find_task()
            return
        
        # Seleccionar la más infestada dentro del radio
        best_task = max(tasks_in_radius, key=lambda t: t[0].infestation_level)[0]
        
        # Intentar asignar la tarea
        if self.blackboard.assign_task(best_task, str(self.id)):
            self.current_task = best_task
            self._calculate_path_to_task()
            self.blackboard.start_task(best_task)
        else:
            self.status = 'idle'
    
    def _calculate_distance(self, pos1: Tuple[int, int], pos2: Tuple[int, int]) -> float:
        """Calcula distancia Manhattan entre dos posiciones"""
        return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])


class FumigationModel(ap.Model):
    """
    Modelo AgentPy que simula agentes fumigadores y scouts coordinándose a través del blackboard.
    """
    
    def setup(self):
        """
        Inicializa el modelo.
        Los parámetros se pasan a través de self.p.
        """
        # Obtener parámetros
        self.world_instance = self.p.world_instance
        self.num_fumigators = self.p.num_fumigators
        self.num_scouts = self.p.num_scouts
        self.min_infestation = self.p.min_infestation
        self.simulation_id = self.p.get('simulation_id')  # ID de simulación para eventos

        # Inicializar servicio de blackboard
        from .services import BlackboardService
        self.blackboard_service = BlackboardService(self.world_instance)

        # Inicializar emisor de eventos
        self.event_emitter = EventEmitter(str(self.simulation_id)) if self.simulation_id else None
        
        # Encontrar todas las celdas del granero (5 celdas en línea)
        pathfinder_temp = Pathfinder(self.world_instance.grid, self.world_instance.width, self.world_instance.height)
        barn_cells = pathfinder_temp.find_all_barn_cells()
        
        if not barn_cells:
            # Si no hay barn, usar posición central
            barn_cells = [(self.world_instance.width // 2, self.world_instance.height // 2)]
        
        # IMPORTANTE: Inicializar start_positions ANTES de crear los agentes
        # porque AgentPy llama a setup() de cada agente inmediatamente al crearlo
        # Pre-asignar posiciones del barn a los agentes que se crearán
        self.start_positions = {}
        
        # Crear agentes fumigadores
        # AgentPy llamará a setup() de cada agente inmediatamente
        self.fumigators = ap.AgentList(self, self.num_fumigators, FumigatorAgent)
        
        # Crear agentes scouts
        # AgentPy llamará a setup() de cada agente inmediatamente
        self.scouts = ap.AgentList(self, self.num_scouts, ScoutAgent)
        
        # Combinar todos los agentes
        self.agents = self.fumigators + self.scouts
        
        # Asignar cada agente a una celda diferente del granero
        # Distribuir los agentes entre las 5 celdas del barn
        agents_data = []
        for idx, agent in enumerate(self.agents):
            # Usar módulo para distribuir entre las celdas disponibles
            barn_cell_idx = idx % len(barn_cells)
            assigned_barn_pos = barn_cells[barn_cell_idx]

            # Asignar posición inicial
            self.start_positions[agent.id] = assigned_barn_pos
            # Actualizar la posición del agente
            agent.position = assigned_barn_pos

            # Recopilar datos del agente para evento de inicialización
            agent_type = 'scout' if isinstance(agent, ScoutAgent) else 'fumigator'
            agents_data.append({
                'id': str(agent.id),
                'type': agent_type,
                'position': list(agent.position)
            })

            # Emitir evento de agente creado
            if self.event_emitter:
                self.event_emitter.emit_agent_spawned(
                    str(agent.id), agent_type, agent.position
                )

        # Emitir evento de simulación inicializada
        if self.event_emitter:
            self.event_emitter.emit_simulation_initialized(
                self.num_fumigators,
                self.num_scouts,
                (self.world_instance.width, self.world_instance.height),
                agents_data
            )
    
    def step(self):
        """Ejecuta un paso de la simulación"""
        # Los agentes ejecutan sus pasos automáticamente
        pass
    
    def update(self):
        """Actualiza el estado del modelo después de cada paso"""
        # Sincronizar posiciones de agentes con Django
        for agent in self.agents:
            agent_id_str = str(agent.id)
            agent_type = 'scout' if isinstance(agent, ScoutAgent) else 'fumigator'
            
            agent_model, created = AgentModel.objects.get_or_create(
                agent_id=agent_id_str,
                world=self.world_instance,
                defaults={
                    'agent_type': agent_type,
                    'is_active': True
                }
            )
            
            # Actualizar estado del agente
            agent_model.position_x = agent.position[0]
            agent_model.position_z = agent.position[1]
            agent_model.status = agent.status
            
            if isinstance(agent, FumigatorAgent):
                agent_model.tasks_completed = agent.tasks_completed
                agent_model.fields_fumigated = agent.fields_fumigated
                agent_model.metadata = {
                    'pesticide_level': agent.pesticide_level,
                    'pesticide_capacity': agent.pesticide_capacity,
                    'pesticide_percentage': (agent.pesticide_level / agent.pesticide_capacity * 100) if agent.pesticide_capacity > 0 else 0
                }
            elif isinstance(agent, ScoutAgent):
                agent_model.metadata = {
                    'fields_analyzed': agent.fields_analyzed,
                    'discoveries': agent.discoveries
                }
            
            agent_model.save()




def run_simulation(
    world_instance: World,
    num_fumigators: int = 5,
    num_scouts: int = 1,
    max_steps: int = 300,
    min_infestation: int = 10,
    simulation_id: Optional[str] = None,
    emit_updates: bool = True,
    step_delay: float = 0.5  # Delay entre pasos para visualización (segundos) - aumentado para ver paso a paso
) -> Dict[str, Any]:
    """
    Ejecuta una simulación de agentes fumigadores y scouts.
    
    Args:
        world_instance: Instancia del modelo World
        num_fumigators: Número de agentes fumigadores
        num_scouts: Número de agentes scouts
        max_steps: Número máximo de pasos
        min_infestation: Nivel mínimo de infestación para crear tareas
    
    Returns:
        Diccionario con resultados de la simulación
    """
    # Obtener o crear simulación
    from agents.models import Agent, Simulation
    from django.utils import timezone
    
    if simulation_id:
        # Si se proporciona un ID, obtener la simulación existente
        simulation = Simulation.objects.get(id=simulation_id)
    else:
        # Si no, crear una nueva
        simulation = Simulation.objects.create(
            world=world_instance,
            num_agents=num_fumigators + num_scouts,
            num_fumigators=num_fumigators,
            num_scouts=num_scouts,
            max_steps=max_steps,
            status='running',
            started_at=timezone.now()
        )
    
    try:
        # Crear y ejecutar modelo AgentPy
        parameters = {
            'world_instance': world_instance,
            'num_fumigators': num_fumigators,
            'num_scouts': num_scouts,
            'min_infestation': min_infestation,
            'simulation_id': str(simulation.id)  # Agregar simulation_id a parámetros
        }
        
        # Crear modelo AgentPy
        # En AgentPy, los parámetros se pasan como diccionario y se acceden vía self.p
        # AgentPy llama automáticamente a setup() durante la inicialización
        import traceback
        
        try:
            # Verificar que los parámetros sean válidos
            if not world_instance:
                raise ValueError("world_instance no puede ser None")
            if num_fumigators < 0 or num_scouts < 0:
                raise ValueError(f"El número de agentes debe ser positivo. Fumigadores: {num_fumigators}, Scouts: {num_scouts}")
            
            model = FumigationModel(parameters)
            
            # Verificar que el modelo se haya inicializado correctamente
            # AgentPy debería haber llamado a setup() automáticamente
            if not hasattr(model, 'agents'):
                # Si no tiene agents, algo salió mal en setup()
                # Intentar llamar setup() manualmente
                try:
                    model.setup()
                except Exception as setup_error:
                    error_trace = traceback.format_exc()
                    raise RuntimeError(
                        f"Error al inicializar el modelo AgentPy en setup(): {str(setup_error)}\n"
                        f"Traceback: {error_trace}"
                    ) from setup_error
            
            # Verificar que los agentes se crearon correctamente
            if not model.agents or len(model.agents) == 0:
                raise RuntimeError(
                    f"El modelo no creó agentes correctamente. "
                    f"Agentes esperados: {num_fumigators + num_scouts}, "
                    f"Agentes encontrados: {len(model.agents) if hasattr(model, 'agents') else 0}"
                )
        except RuntimeError:
            # Re-lanzar RuntimeError tal cual
            raise
        except ValueError as ve:
            # Errores de validación
            raise RuntimeError(f"Error de validación: {str(ve)}") from ve
        except Exception as e:
            # Cualquier otro error durante la creación del modelo
            error_trace = traceback.format_exc()
            error_type = type(e).__name__
            error_message = str(e) if str(e) else repr(e)
            raise RuntimeError(
                f"Error al crear el modelo AgentPy ({error_type}): {error_message}\n"
                f"Traceback: {error_trace}"
            ) from e
        
        # NO inicializar tareas automáticamente - el scout las descubrirá progresivamente
        # Las tareas se crearán cuando el scout revele infestación
        print(f"Simulación iniciada - el scout descubrirá infestación progresivamente")
        
        # Ejecutar simulación paso a paso
        steps_executed = 0
        
        for step in range(max_steps):
            # Actualizar paso actual en el event emitter
            if model.event_emitter:
                model.event_emitter.set_current_step(step + 1)

            # Ejecutar un paso del modelo (esto ejecutará los comandos de los agentes)
            model.step()
            model.update()
            steps_executed = step + 1

            # Delay para visualización en tiempo real (solo si se emiten actualizaciones)
            # Este delay asegura que cada paso se vea claramente
            if emit_updates and step_delay > 0:
                time.sleep(step_delay)

            # Enviar actualización de paso (resumen del estado)
            if emit_updates and model.event_emitter:
                # Obtener estado actual de los agentes
                agents_data = []
                # Verificar que los agentes existan antes de iterar
                if hasattr(model, 'agents') and model.agents:
                    for agent in model.agents:
                        agent_data = {
                            'id': str(agent.id),
                            'type': 'scout' if isinstance(agent, ScoutAgent) else 'fumigator',
                            'position': list(agent.position),
                            'status': agent.status
                        }

                        if isinstance(agent, FumigatorAgent):
                            agent_data.update({
                                'pesticide_level': agent.pesticide_level,
                                'pesticide_capacity': agent.pesticide_capacity,
                                'tasks_completed': agent.tasks_completed,
                                'fields_fumigated': agent.fields_fumigated,
                                'current_task': {
                                    'position_x': agent.current_task.position_x,
                                    'position_z': agent.current_task.position_z,
                                    'infestation_level': agent.current_task.infestation_level
                                } if agent.current_task else None
                            })
                        elif isinstance(agent, ScoutAgent):
                            agent_data.update({
                                'fields_analyzed': agent.fields_analyzed,
                                'discoveries': agent.discoveries
                            })

                        agents_data.append(agent_data)

                # Obtener tareas del blackboard
                available_tasks = model.blackboard_service.get_available_tasks(limit=50)
                tasks_data = [{
                    'id': str(task.id),
                    'position_x': task.position_x,
                    'position_z': task.position_z,
                    'infestation_level': task.infestation_level,
                    'priority': task.priority,
                    'status': task.status,
                    'assigned_agent_id': task.assigned_agent_id
                } for task in available_tasks]

                # Calcular estadísticas
                total_tasks_completed = sum(agent.tasks_completed for agent in model.fumigators)
                total_fields_fumigated = sum(agent.fields_fumigated for agent in model.fumigators)
                total_fields_analyzed = sum(agent.fields_analyzed for agent in model.scouts)

                statistics = {
                    'tasks_completed': total_tasks_completed,
                    'fields_fumigated': total_fields_fumigated,
                    'fields_analyzed': total_fields_analyzed
                }

                # Emitir evento de paso de simulación
                model.event_emitter.emit_simulation_step(
                    agents_data, tasks_data, statistics
                )
            
            # Verificar condiciones de terminación
            # Solo terminar si:
            # 1. No hay tareas pendientes Y
            # 2. Todos los fumigadores están idle Y
            # 3. Todos los scouts han terminado de explorar (opcional, o después de un mínimo de pasos)
            available_tasks = model.blackboard_service.get_available_tasks()
            
            # Esperar al menos algunos pasos para que los scouts descubran infestación
            min_steps_for_scouts = 50
            
            if steps_executed >= min_steps_for_scouts:
                if not available_tasks:
                    # Verificar si todos los fumigadores están idle
                    all_fumigators_idle = all(
                        agent.status == 'idle' or agent.status == 'returning_to_barn' or agent.status == 'refilling'
                        for agent in model.fumigators
                    )
                    if all_fumigators_idle:
                        # Verificar si hay tareas en progreso usando el modelo directamente
                        from .models import BlackboardTask, TaskStatus
                        tasks_in_progress = BlackboardTask.objects.filter(
                            world=world_instance,
                            status__in=[TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS]
                        ).exists()
                        if not tasks_in_progress:
                            break
        
        # Actualizar simulación
        simulation.status = 'completed'
        simulation.completed_at = timezone.now()
        simulation.steps_executed = steps_executed
        
        # Calcular estadísticas
        total_tasks_completed = sum(agent.tasks_completed for agent in model.fumigators)
        total_fields_fumigated = sum(agent.fields_fumigated for agent in model.fumigators)
        total_fields_analyzed = sum(agent.fields_analyzed for agent in model.scouts)
        total_discoveries = sum(agent.discoveries for agent in model.scouts)
        
        simulation.tasks_completed = total_tasks_completed
        simulation.fields_fumigated = total_fields_fumigated
        
        simulation.results = {
            'fumigators': [
                {
                    'id': str(agent.id),
                    'tasks_completed': agent.tasks_completed,
                    'fields_fumigated': agent.fields_fumigated
                }
                for agent in model.fumigators
            ],
            'scouts': [
                {
                    'id': str(agent.id),
                    'fields_analyzed': agent.fields_analyzed,
                    'discoveries': agent.discoveries
                }
                for agent in model.scouts
            ],
            'steps': steps_executed
        }
        
        simulation.save()

        # Enviar actualización final
        if emit_updates and model.event_emitter:
            model.event_emitter.emit_simulation_completed({
                'tasks_completed': total_tasks_completed,
                'fields_fumigated': total_fields_fumigated,
                'fields_analyzed': total_fields_analyzed,
                'discoveries': total_discoveries,
                'steps_executed': steps_executed
            })
        
        return {
            'simulation_id': str(simulation.id),
            'status': 'completed',
            'steps_executed': steps_executed,
            'tasks_completed': total_tasks_completed,
            'fields_fumigated': total_fields_fumigated,
            'fields_analyzed': total_fields_analyzed,
            'discoveries': total_discoveries,
            'fumigators': [
                {
                    'id': str(agent.id),
                    'tasks_completed': agent.tasks_completed,
                    'fields_fumigated': agent.fields_fumigated
                }
                for agent in model.fumigators
            ],
            'scouts': [
                {
                    'id': str(agent.id),
                    'fields_analyzed': agent.fields_analyzed,
                    'discoveries': agent.discoveries
                }
                for agent in model.scouts
            ]
        }
    
    except Exception as e:
        simulation.status = 'failed'
        simulation.completed_at = timezone.now()
        simulation.results = {'error': str(e)}
        simulation.save()
        raise
