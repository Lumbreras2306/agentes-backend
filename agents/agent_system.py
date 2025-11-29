"""
Sistema de agentes usando AgentPy que se comunican con el blackboard de Django.
Los agentes coordinan para fumigar campos con infestación.
Sistema basado en comandos: el backend envía comandos y espera confirmaciones del cliente.
"""
import agentpy as ap
from typing import List, Tuple, Optional, Dict, Any
import math
import asyncio
import threading
import time
from collections import defaultdict
from django.db import transaction
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .services import BlackboardService
from .models import BlackboardTask, TaskStatus
from agents.models import Agent as AgentModel
from world.models import World
from world.world_generator import TileType
from world.pathfinding import Pathfinder, DynamicPathfinder

# Diccionario global para almacenar confirmaciones pendientes por simulación
# Formato: {simulation_id: {agent_id: threading.Event}}
pending_confirmations: Dict[str, Dict[str, threading.Event]] = defaultdict(dict)


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
        # El modelo nuevo tiene self.model.blackboard, el legacy tiene self.model.blackboard_service
        self.blackboard = getattr(self.model, 'blackboard', None) or self.model.blackboard_service
        self.grid = self.world_instance.grid
        self.infestation_grid = self.world_instance.infestation_grid
        self.width = self.world_instance.width
        self.height = self.world_instance.height
        
        # Pathfinder para movimiento (puede usar cualquier ruta)
        self.pathfinder = Pathfinder(self.grid, self.width, self.height)
        
        # Lista de campos ya analizados
        self.analyzed_fields = set()
        
        # IMPORTANTE: Registrar el agente en el knowledge_base para que aparezca en el frontend
        # El modelo nuevo tiene model.blackboard.knowledge_base
        if hasattr(self.model, 'blackboard') and hasattr(self.model.blackboard, 'knowledge_base'):
            from agents.blackboard.knowledge_base import AgentState
            agent_state = AgentState(
                agent_id=str(self.id),
                agent_type='scout',
                position=self.position,
                status=self.status,
                fields_analyzed=self.fields_analyzed,
                analyzed_positions=self.analyzed_fields
            )
            self.model.blackboard.knowledge_base.register_agent(agent_state)
        # Si no hay nuevo blackboard, el modelo se encargará de registrar los agentes
    
    def step(self):
        """Ejecuta un paso del agente scout

        Reactive Agent Pattern:
        1. PERCIBIR: Leer comandos del blackboard (ScoutCoordinatorKS)
        2. DECIDIR: Determinar acción basada en comando o estado interno
        3. ACTUAR: Ejecutar movimiento y revelar infestación
        4. REPORTAR: Actualizar estado en blackboard
        """
        # 1. PERCIBIR: Leer comando del blackboard
        # El nuevo blackboard tiene knowledge_base.get_shared, el legacy tiene métodos diferentes
        if hasattr(self.blackboard, 'knowledge_base'):
            command = self.blackboard.knowledge_base.get_shared(f'command_{self.id}')
        elif hasattr(self.blackboard, 'get_shared'):
            command = self.blackboard.get_shared(f'command_{self.id}')
        else:
            command = None

        if command and command.get('action') == 'explore_area':
            # ScoutCoordinatorKS nos envió una posición objetivo
            target = command.get('target_position')

            if target:
                target_tuple = tuple(target) if isinstance(target, list) else target

                # Verificar si ya llegamos al objetivo
                if self.position == target_tuple:
                    # YA ESTAMOS EN EL OBJETIVO
                    # Revelar infestación alrededor
                    self._reveal_infestation_around_position(self.position)

                    # CRÍTICO: Cambiar a 'idle' para recibir siguiente comando
                    self.status = 'idle'

                    # Limpiar comando procesado
                    if hasattr(self.blackboard, 'knowledge_base'):
                        self.blackboard.knowledge_base.set_shared(f'command_{self.id}', None)
                    elif hasattr(self.blackboard, 'set_shared'):
                        self.blackboard.set_shared(f'command_{self.id}', None)

                    print(f"🔍 Scout {self.id}: Llegó a {target_tuple}, revelando área, volviendo a idle")
                else:
                    # AÚN NO LLEGAMOS, MOVERNOS HACIA EL OBJETIVO
                    self._move_towards(target_tuple)
                    self.status = 'scouting'
            else:
                # Comando sin objetivo, cambiar a idle
                self.status = 'idle'
        else:
            # No hay comando del blackboard, usar lógica interna
            # (Fallback para compatibilidad, pero el ScoutCoordinatorKS debería dirigir)
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
        
        # 4. REPORTAR: Siempre actualizar estado en blackboard al final del step
        # Esto asegura que el frontend reciba la posición actualizada
        # Intentar acceder al nuevo blackboard primero
        if hasattr(self.model, 'blackboard') and hasattr(self.model.blackboard, 'knowledge_base'):
            self.model.blackboard.knowledge_base.update_agent(
                str(self.id),
                position=self.position,
                status=self.status,
                fields_analyzed=self.fields_analyzed,
                analyzed_positions=self.analyzed_fields
            )
        # Si no hay nuevo blackboard, el modelo se encargará de actualizar
    
    def _find_unanalyzed_field(self) -> Optional[Tuple[int, int]]:
        """Encuentra un campo no analizado usando exploración sistemática
        
        Estrategia: Escanear todos los campos de manera sistemática,
        fila por fila, sin evitar zonas. Esto evita el comportamiento
        errático de buscar en radios crecientes.
        """
        # Buscar todos los campos no analizados
        unanalyzed_fields = []
        for z in range(self.height):
            for x in range(self.width):
                if (self.grid[z][x] == TileType.FIELD and 
                    (x, z) not in self.analyzed_fields):
                    unanalyzed_fields.append((x, z))
        
        if not unanalyzed_fields:
            return None
        
        # Estrategia: Ir al campo más cercano que no haya sido analizado
        # Esto asegura una exploración más sistemática
        return min(unanalyzed_fields, key=lambda p: self._calculate_distance(self.position, p))
    
    def _move_towards(self, target: Tuple[int, int], wait_confirmation: bool = True):
        """Se mueve hacia el objetivo usando pathfinding o movimiento directo
        
        Si el objetivo es un campo y está cerca, puede moverse directamente.
        Si no, usa pathfinding para evitar zonas IMPASSABLE.
        """
        self.status = 'moving'
        
        # Si el objetivo es un campo y está a distancia Manhattan 1, moverse directamente
        distance = self._calculate_distance(self.position, target)
        if distance == 1 and self.grid[target[1]][target[0]] == TileType.FIELD:
            # Movimiento directo a campo adyacente
            next_pos = target
        else:
            # Usar pathfinding para distancias mayores
            path = self.pathfinder.dijkstra(self.position, target, prefer_roads=False)
            
            if path and len(path) > 1:
                next_pos = path[1]
            elif path and len(path) == 1:
                # Ya estamos en el objetivo
                next_pos = self.position
            else:
                # Pathfinding falló, intentar movimiento directo hacia el objetivo
                # Solo si es un campo y está cerca (distancia <= 2)
                if distance <= 2 and self.grid[target[1]][target[0]] == TileType.FIELD:
                    # Moverse un paso más cerca usando movimiento Manhattan simple
                    x, z = self.position
                    tx, tz = target
                    if abs(tx - x) > abs(tz - z):
                        # Mover horizontalmente
                        new_x = x + (1 if tx > x else -1)
                        next_pos = (new_x, z) if self._is_valid_position((new_x, z)) else self.position
                    else:
                        # Mover verticalmente
                        new_z = z + (1 if tz > z else -1)
                        next_pos = (x, new_z) if self._is_valid_position((x, new_z)) else self.position
                else:
                    # No se puede mover, quedarse en posición actual
                    next_pos = self.position
        
        # Solo moverse si la posición es diferente
        if next_pos != self.position:
            # Si hay confirmaciones habilitadas, enviar comando y esperar
            if wait_confirmation and hasattr(self.model, 'simulation_id'):
                command = {
                    'action': 'move',
                    'from_position': list(self.position),
                    'to_position': list(next_pos),
                    'reveal_infestation': True  # El scout revela infestación al moverse
                }
                
                confirmed = _send_agent_command(
                    str(self.model.simulation_id),
                    str(self.id),
                    command,
                    wait_for_confirmation=True,
                    timeout=5.0
                )
                
                if confirmed:
                    # Solo ejecutar movimiento después de confirmación
                    self.position = next_pos
                    self._reveal_infestation_around_position(next_pos)
                else:
                    # Timeout: ejecutar directamente (fallback)
                    self.position = next_pos
                    self._reveal_infestation_around_position(next_pos)
            else:
                # Modo sin confirmaciones (fallback)
                self.position = next_pos
                self._reveal_infestation_around_position(next_pos)
            
            # IMPORTANTE: Actualizar estado en el knowledge_base para que aparezca en el frontend
            # Intentar acceder al nuevo blackboard primero
            if hasattr(self.model, 'blackboard') and hasattr(self.model.blackboard, 'knowledge_base'):
                self.model.blackboard.knowledge_base.update_agent(
                    str(self.id),
                    position=self.position,
                    status=self.status,
                    fields_analyzed=self.fields_analyzed,
                    analyzed_positions=self.analyzed_fields
                )
            # Si no hay nuevo blackboard, el modelo se encargará de actualizar
    
    def _reveal_infestation_around_position(self, pos: Tuple[int, int]):
        """Revela infestación en un área 3x3 alrededor de la posición actual

        Solo revela células en un radio pequeño para simular el escaneo del dron.
        Esto permite una revelación progresiva del mapa.
        """
        x, z = pos

        # Radio de revelación (1 = área 3x3, 2 = área 5x5)
        reveal_radius = 1

        # Track if we analyzed any new cells
        newly_analyzed = False

        # Analizar celdas en el radio especificado
        for dz in range(-reveal_radius, reveal_radius + 1):
            for dx in range(-reveal_radius, reveal_radius + 1):
                analyze_x = x + dx
                analyze_z = z + dz

                # Verificar límites
                if not (0 <= analyze_x < self.width and 0 <= analyze_z < self.height):
                    continue

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
                newly_analyzed = True

                # Obtener nivel de infestación
                infestation = self.infestation_grid[analyze_z][analyze_x]

                # DEBUG: Log infestation levels
                if infestation > 0:
                    print(f"🐛 Scout {self.id}: Descubrió infestación {infestation}% en ({analyze_x}, {analyze_z})")

                # Si hay infestación significativa, crear tarea en el blackboard
                if infestation >= self.model.min_infestation:
                    # Verificar si ya existe una tarea para este campo
                    existing_task = self.blackboard.get_task_by_position(analyze_x, analyze_z)

                    if not existing_task:
                        # Crear nueva tarea
                        self.blackboard.create_task(
                            position_x=analyze_x,
                            position_z=analyze_z,
                            infestation_level=infestation,
                            metadata={
                                'crop_type': self.world_instance.crop_grid[analyze_z][analyze_x],
                                'discovered_by': str(self.id)
                            }
                        )
                        self.discoveries += 1

        # Actualizar blackboard una sola vez después de procesar todas las celdas
        # El ScoutCoordinatorKS necesita esta información para coordinar la exploración
        if newly_analyzed:
            # Actualizar estado en el knowledge_base
            if hasattr(self.model, 'blackboard') and hasattr(self.model.blackboard, 'knowledge_base'):
                self.model.blackboard.knowledge_base.update_agent(
                    str(self.id),
                    analyzed_positions=self.analyzed_fields,
                    fields_analyzed=self.fields_analyzed,
                    position=self.position,
                    status=self.status
                )
    
    def _analyze_field(self, field_pos: Tuple[int, int]):
        """Analiza un campo para descubrir su nivel de infestación (legacy, ahora usa _reveal_infestation_around_position)"""
        self._reveal_infestation_around_position(field_pos)
        self.status = 'scouting'
    
    def _explore(self):
        """Explora el mundo de manera sistemática"""
        # Buscar todos los campos no analizados
        unanalyzed = []
        for z in range(self.height):
            for x in range(self.width):
                if (self.grid[z][x] == TileType.FIELD and 
                    (x, z) not in self.analyzed_fields):
                    unanalyzed.append((x, z))
        
        if unanalyzed:
            # Ir al más cercano en lugar de aleatorio para exploración sistemática
            target = min(unanalyzed, key=lambda p: self._calculate_distance(self.position, p))
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
        """Verifica si una posición es válida y transitable
        
        Para el scout, solo necesita ser un campo (FIELD) para poder escanearlo.
        Puede moverse a través de cualquier celda transitable para llegar a campos.
        """
        x, z = pos
        if not (0 <= x < self.width and 0 <= z < self.height):
            return False
        
        tile = self.grid[z][x]
        # Scout puede moverse por cualquier celda transitable (no IMPASSABLE)
        # pero solo escanea campos (FIELD)
        return tile != TileType.IMPASSABLE
    
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
            # Marcar como en progreso
            self.blackboard.start_task(best_task)
    
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
                # No tiene suficiente pesticida, cancelar tarea y regresar
                self._cancel_task_and_return_to_barn()
                return
            
            # Enviar comando de fumigación y esperar confirmación
            if hasattr(self.model, 'simulation_id') and self.model.simulation_id:
                command = {
                    'action': 'fumigate',
                    'position': list(target),
                    'infestation_level': infestation_level,
                    'required_pesticide': required_pesticide
                }
                
                confirmed = _send_agent_command(
                    str(self.model.simulation_id),
                    str(self.id),
                    command,
                    wait_for_confirmation=True,
                    timeout=5.0
                )
                
                if confirmed:
                    # Ejecutar fumigación después de confirmación
                    self.status = 'fumigating'
                    self._complete_task()
                else:
                    # Fallback: ejecutar directamente
                    self.status = 'fumigating'
                    self._complete_task()
            else:
                # Modo sin confirmaciones
                self.status = 'fumigating'
                self._complete_task()
        else:
            # Moverse hacia el destino
            self.status = 'moving'
            self._move_towards_target()
    
    def _move_towards_target(self, wait_confirmation: bool = True):
        """Se mueve hacia el objetivo, fumiga celdas en el camino y aumenta peso de campos pisados"""
        if self.path and self.path_index < len(self.path) - 1:
            self.path_index += 1
            next_pos = self.path[self.path_index]
            
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

                # FUMIGACIÓN OPORTUNISTA: Fumigar celdas con tareas en el camino
                # Solo fumigar si:
                # 1. Tiene pesticida disponible
                # 2. La celda tiene una tarea asignada o pendiente en el blackboard
                # 3. La celda tiene infestación > 0
                if self.pesticide_level > 0:
                    # Verificar si hay una tarea para esta posición
                    task_at_position = self.blackboard.get_task_by_position(x, z)

                    if task_at_position and self.infestation_grid[z][x] > 0:
                        # Hay una tarea pendiente o asignada aquí, ¡fumigar!
                        should_fumigate = True
                        infestation_level = self.infestation_grid[z][x]
                        pesticide_needed = min(infestation_level, self.pesticide_level)
                        fumigation_data = {
                            'infestation_level': infestation_level,
                            'pesticide_needed': pesticide_needed,
                            'position': [x, z],
                            'task_id': task_at_position.id if task_at_position else None,
                            'opportunistic': True  # Marcador de fumigación oportunista
                        }
            
            # Si hay confirmaciones habilitadas, enviar comando y esperar
            if wait_confirmation and hasattr(self.model, 'simulation_id') and self.model.simulation_id:
                command = {
                    'action': 'move',
                    'from_position': list(self.position),
                    'to_position': list(next_pos),
                    'fumigate_on_path': should_fumigate,
                    'fumigation_data': fumigation_data
                }
                
                confirmed = _send_agent_command(
                    str(self.model.simulation_id),
                    str(self.id),
                    command,
                    wait_for_confirmation=True,
                    timeout=5.0
                )
                
                if confirmed:
                    # Solo ejecutar movimiento después de confirmación
                    self._execute_move(next_pos, fumigation_data)
                else:
                    # Timeout: ejecutar directamente (fallback)
                    self._execute_move(next_pos, fumigation_data)
            else:
                # Modo sin confirmaciones (fallback)
                self._execute_move(next_pos, fumigation_data)
    
    def _execute_move(self, next_pos: Tuple[int, int], fumigation_data: Optional[Dict[str, Any]]):
        """Ejecuta el movimiento y fumigación si es necesario"""
        x, z = next_pos
        self.position = next_pos

        # Ejecutar fumigación si es necesario
        if fumigation_data:
            infestation_level = fumigation_data['infestation_level']
            pesticide_needed = fumigation_data['pesticide_needed']
            is_opportunistic = fumigation_data.get('opportunistic', False)

            self.pesticide_level -= pesticide_needed
            self.infestation_grid[z][x] = max(0, infestation_level - pesticide_needed)

            # Si se completó la fumigación de esta celda, crear/completar tarea si existe
            if self.infestation_grid[z][x] == 0:
                task = self.blackboard.get_task_by_position(x, z)
                if task:
                    self.blackboard.complete_task(task)
                    self.fields_fumigated += 1

                    # Log de fumigación oportunista para debugging
                    if is_opportunistic:
                        print(f"🎯 Fumigator {self.id}: Fumigación oportunista en ({x}, {z}) - Tarea {task.id} completada")
    
    def _complete_task(self):
        """Completa la tarea actual y consume pesticida"""
        if self.current_task:
            # Obtener nivel de infestación de la tarea
            infestation_level = self.current_task.infestation_level
            
            # Consumir pesticida proporcional a la infestación
            # 1 unidad de pesticida por cada 1% de infestación
            pesticide_used = infestation_level
            self.pesticide_level = max(0, self.pesticide_level - pesticide_used)
            
            # Actualizar infestación en el mundo (reducir a 0)
            self.world_instance.infestation_grid[self.current_task.position_z][self.current_task.position_x] = 0
            
            # Guardar cambios en el mundo
            self.world_instance.save()
            
            # Marcar tarea como completada en el blackboard
            self.blackboard.complete_task(self.current_task)
            
            # Actualizar estadísticas
            self.fields_fumigated += 1
            self.tasks_completed += 1
            
            # Guardar posición completada para buscar siguiente tarea en radio
            completed_pos = (self.current_task.position_x, self.current_task.position_z)
            
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
    
    def _move_towards_barn(self, wait_confirmation: bool = True):
        """Se mueve hacia el granero y aumenta peso de campos pisados exponencialmente"""
        if not self.path or self.path_index >= len(self.path) - 1:
            # Ya llegó al granero
            if hasattr(self.model, 'simulation_id') and self.model.simulation_id:
                command = {
                    'action': 'refill',
                    'position': list(self.barn_position)
                }
                _send_agent_command(
                    str(self.model.simulation_id),
                    str(self.id),
                    command,
                    wait_for_confirmation=wait_confirmation,
                    timeout=5.0
                )
            
            self.status = 'refilling'
            self.path = []
            self.path_index = 0
            return
        
        # Moverse al siguiente paso del camino
        self.path_index += 1
        next_pos = self.path[self.path_index]
        
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
        
        # Si hay confirmaciones habilitadas, enviar comando
        if wait_confirmation and hasattr(self.model, 'simulation_id') and self.model.simulation_id:
            command = {
                'action': 'move',
                'from_position': list(self.position),
                'to_position': list(next_pos),
                'fumigate_on_path': False
            }
            
            confirmed = _send_agent_command(
                str(self.model.simulation_id),
                str(self.id),
                command,
                wait_for_confirmation=True,
                timeout=5.0
            )
            
            if confirmed:
                # Solo ejecutar movimiento después de confirmación
                self.position = next_pos
            else:
                # Timeout: ejecutar directamente (fallback)
                self.position = next_pos
        else:
            self.position = next_pos
        
        # Si llegó al granero, cambiar a estado de reabastecimiento
        if self.position == self.barn_position:
            if hasattr(self.model, 'simulation_id') and self.model.simulation_id:
                command = {
                    'action': 'refill',
                    'position': list(self.barn_position)
                }
                _send_agent_command(
                    str(self.model.simulation_id),
                    str(self.id),
                    command,
                    wait_for_confirmation=wait_confirmation,
                    timeout=5.0
                )
            
            self.status = 'refilling'
            self.path = []
            self.path_index = 0
    
    def _refill_pesticide(self):
        """Reabastece el tanque de pesticida en el granero"""
        # Reabastecer completamente el tanque
        self.pesticide_level = self.pesticide_capacity
        
        # Volver a estado idle para buscar nuevas tareas
        self.status = 'idle'
    
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
        self.simulation_id = self.p.get('simulation_id')  # ID de simulación para comandos
        
        # Inicializar servicio de blackboard
        from .services import BlackboardService
        self.blackboard_service = BlackboardService(self.world_instance)
        
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
        for idx, agent in enumerate(self.agents):
            # Usar módulo para distribuir entre las celdas disponibles
            barn_cell_idx = idx % len(barn_cells)
            assigned_barn_pos = barn_cells[barn_cell_idx]
            
            # Asignar posición inicial
            self.start_positions[agent.id] = assigned_barn_pos
            # Actualizar la posición del agente
            agent.position = assigned_barn_pos
    
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


def _send_simulation_update(simulation_id: str, data: Dict[str, Any]):
    """
    Envía una actualización de simulación a través de WebSocket.
    """
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f'simulation_{simulation_id}',
                {
                    'type': 'simulation_update',
                    'data': data
                }
            )
    except Exception as e:
        # Si falla el envío WebSocket, continuar con la simulación
        print(f"Error enviando actualización WebSocket: {e}")


def _send_agent_command(simulation_id: str, agent_id: str, command: Dict[str, Any], wait_for_confirmation: bool = True, timeout: float = 5.0) -> bool:
    """
    Envía un comando a un agente y espera confirmación del cliente.
    
    Args:
        simulation_id: ID de la simulación
        agent_id: ID del agente
        command: Diccionario con el comando (type, target_position, action, etc.)
        wait_for_confirmation: Si True, espera confirmación antes de retornar
        timeout: Tiempo máximo de espera en segundos
    
    Returns:
        True si se recibió confirmación, False si timeout o error
    """
    try:
        # Crear evento para esperar confirmación
        if wait_for_confirmation:
            confirmation_event = threading.Event()
            pending_confirmations[simulation_id][agent_id] = confirmation_event
        
        # Enviar comando vía WebSocket
        _send_simulation_update(simulation_id, {
            'type': 'agent_command',
            'simulation_id': simulation_id,
            'agent_id': agent_id,
            'command': command
        })
        
        # Esperar confirmación si es necesario
        if wait_for_confirmation:
            confirmed = confirmation_event.wait(timeout=timeout)
            # Limpiar evento después de usarlo
            if agent_id in pending_confirmations[simulation_id]:
                del pending_confirmations[simulation_id][agent_id]
            return confirmed
        
        return True
    except Exception as e:
        print(f"Error enviando comando a agente {agent_id}: {e}")
        return False


def _receive_agent_confirmation(simulation_id: str, agent_id: str):
    """
    Recibe confirmación de que un agente completó su comando.
    Llamado desde el consumer WebSocket cuando llega una confirmación.
    """
    if simulation_id in pending_confirmations and agent_id in pending_confirmations[simulation_id]:
        event = pending_confirmations[simulation_id][agent_id]
        event.set()  # Despertar el thread que está esperando


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
            'min_infestation': min_infestation
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
        tasks_created = 0
        print(f"Simulación iniciada - el scout descubrirá infestación progresivamente")
        
        # Enviar estado inicial
        if emit_updates:
            _send_simulation_update(str(simulation.id), {
                'type': 'simulation_started',
                'simulation_id': str(simulation.id),
                'step': 0,
                'status': 'running',
                'message': f'Simulación iniciada con {tasks_created} tareas iniciales'
            })
        
        # Ejecutar simulación paso a paso
        steps_executed = 0
        
        for step in range(max_steps):
            # Ejecutar un paso del modelo (esto ejecutará los comandos de los agentes)
            model.step()
            model.update()
            steps_executed = step + 1
            
            # Delay para visualización en tiempo real (solo si se emiten actualizaciones)
            # Este delay asegura que cada paso se vea claramente
            if emit_updates and step_delay > 0:
                time.sleep(step_delay)
            
            # Enviar actualización después de cada paso para visualización paso a paso
            if emit_updates:
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
                
                # Obtener grid de infestación actualizado para enviar al frontend
                infestation_grid = world_instance.infestation_grid
                
                _send_simulation_update(str(simulation.id), {
                    'type': 'step_update',
                    'simulation_id': str(simulation.id),
                    'step': steps_executed,
                    'agents': agents_data,
                    'tasks': tasks_data,
                    'infestation_grid': infestation_grid,  # Enviar grid de infestación actualizado
                    'status': 'running'
                })
            
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
        if emit_updates:
            _send_simulation_update(str(simulation.id), {
                'type': 'simulation_completed',
                'simulation_id': str(simulation.id),
                'step': steps_executed,
                'status': 'completed',
                'results': {
                    'tasks_completed': total_tasks_completed,
                    'fields_fumigated': total_fields_fumigated,
                    'fields_analyzed': total_fields_analyzed,
                    'discoveries': total_discoveries
                }
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
