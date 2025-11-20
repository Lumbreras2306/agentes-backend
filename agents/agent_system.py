"""
Sistema de agentes usando AgentPy que se comunican con el blackboard de Django.
Los agentes coordinan para fumigar campos con infestación.
"""
import agentpy as ap
from typing import List, Tuple, Optional, Dict, Any
import math
from django.db import transaction
from .services import BlackboardService
from .models import BlackboardTask, TaskStatus
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
        self.position = self.model.start_positions[self.id]
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
        """Se mueve hacia el objetivo usando pathfinding"""
        self.status = 'moving'
        
        # Usar pathfinding (el scout puede usar cualquier ruta, no le importa el peso)
        path = self.pathfinder.dijkstra(self.position, target, prefer_roads=False)
        
        if path and len(path) > 1:
            # Moverse al siguiente paso del camino
            self.position = path[1]
    
    def _analyze_field(self, field_pos: Tuple[int, int]):
        """Analiza un campo para descubrir su nivel de infestación"""
        x, z = field_pos
        
        # Obtener nivel de infestación del mundo
        infestation = self.infestation_grid[z][x]
        
        # Marcar como analizado
        self.analyzed_fields.add(field_pos)
        self.fields_analyzed += 1
        
        # Si hay infestación significativa, crear tarea en el blackboard
        if infestation >= self.model.min_infestation:
            # Verificar si ya existe una tarea para este campo
            existing_task = self.blackboard.get_task_by_position(x, z)
            
            if not existing_task:
                # Crear nueva tarea
                self.blackboard.create_task(
                    position_x=x,
                    position_z=z,
                    infestation_level=infestation,
                    metadata={
                        'crop_type': self.world_instance.crop_grid[z][x],
                        'discovered_by': str(self.id)
                    }
                )
                self.discoveries += 1
        
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
    """
    
    def setup(self):
        """Inicializa el agente fumigador"""
        self.position = self.model.start_positions[self.id]
        self.status = 'idle'  # idle, moving, fumigating
        self.current_task = None
        self.path = []
        self.path_index = 0
        self.fields_fumigated = 0
        self.tasks_completed = 0
        
        # Referencias al mundo y blackboard
        self.world_instance = self.model.world_instance
        self.blackboard = self.model.blackboard_service
        self.grid = self.world_instance.grid
        self.width = self.world_instance.width
        self.height = self.world_instance.height
        
        # Pathfinder con pesos dinámicos
        self.pathfinder = Pathfinder(self.grid, self.width, self.height)
        
        # Mapa de pesos dinámicos para campos (aumenta cada vez que se pisa)
        # Formato: {(x, z): peso_adicional}
        self.field_weights = {}
    
    def step(self):
        """Ejecuta un paso del agente"""
        # Si no tiene tarea, buscar una en el blackboard
        if self.current_task is None:
            self._find_task()
        
        # Si tiene tarea, trabajar en ella
        if self.current_task:
            self._work_on_task()
        else:
            # Si no hay tareas, esperar
            self.status = 'idle'
    
    def _find_task(self):
        """Busca una tarea disponible en el blackboard"""
        available_tasks = self.blackboard.get_available_tasks(limit=10)
        
        if not available_tasks:
            return
        
        # Seleccionar la tarea más cercana y de mayor prioridad
        best_task = None
        best_distance = float('inf')
        
        for task in available_tasks:
            # Intentar asignar la tarea
            if self.blackboard.assign_task(task, str(self.id)):
                distance = self._calculate_distance(
                    self.position,
                    (task.position_x, task.position_z)
                )
                if distance < best_distance:
                    best_distance = distance
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
        
        target = (self.current_task.position_x, self.current_task.position_z)
        
        # Si ya está en el destino, fumigar
        if self.position == target:
            self.status = 'fumigating'
            # Simular fumigación (toma algunos pasos)
            if not hasattr(self, 'fumigation_steps'):
                self.fumigation_steps = 0
            
            self.fumigation_steps += 1
            
            # Completar fumigación después de 3 pasos
            if self.fumigation_steps >= 3:
                self._complete_task()
        else:
            # Moverse hacia el destino
            self.status = 'moving'
            self._move_towards_target()
    
    def _move_towards_target(self):
        """Se mueve hacia el objetivo y aumenta peso de campos pisados"""
        if self.path and self.path_index < len(self.path) - 1:
            self.path_index += 1
            next_pos = self.path[self.path_index]
            
            # Verificar si es un campo y aumentar su peso
            x, z = next_pos
            if self.grid[z][x] == TileType.FIELD:
                # Aumentar peso de este campo
                current_weight = self.field_weights.get(next_pos, 0)
                self.field_weights[next_pos] = current_weight + 5.0  # Aumentar peso en 5
            
            self.position = next_pos
    
    def _complete_task(self):
        """Completa la tarea actual"""
        if self.current_task:
            # Actualizar infestación en el mundo (reducir a 0)
            self.world_instance.infestation_grid[self.current_task.position_z][self.current_task.position_x] = 0
            
            # Guardar cambios en el mundo
            self.world_instance.save()
            
            # Marcar tarea como completada en el blackboard
            self.blackboard.complete_task(self.current_task)
            
            # Actualizar estadísticas
            self.fields_fumigated += 1
            self.tasks_completed += 1
            
            # Limpiar
            self.current_task = None
            self.path = []
            self.path_index = 0
            self.status = 'idle'
            if hasattr(self, 'fumigation_steps'):
                delattr(self, 'fumigation_steps')
    
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
        
        # Inicializar servicio de blackboard
        from .services import BlackboardService
        self.blackboard_service = BlackboardService(self.world_instance)
        
        # Encontrar posición inicial (barn)
        self.start_positions = {}
        barn_pos = None
        for z in range(self.world_instance.height):
            for x in range(self.world_instance.width):
                if self.world_instance.grid[z][x] == TileType.BARN:
                    barn_pos = (x, z)
                    break
            if barn_pos:
                break
        
        if not barn_pos:
            # Si no hay barn, usar posición central
            barn_pos = (self.world_instance.width // 2, self.world_instance.height // 2)
        
        # Crear agentes fumigadores
        self.fumigators = ap.AgentList(self, self.num_fumigators, FumigatorAgent)
        
        # Crear agentes scouts
        self.scouts = ap.AgentList(self, self.num_scouts, ScoutAgent)
        
        # Combinar todos los agentes
        self.agents = self.fumigators + self.scouts
        
        # Asignar posiciones iniciales (todos empiezan en el barn)
        for agent in self.agents:
            self.start_positions[agent.id] = barn_pos
    
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
            elif isinstance(agent, ScoutAgent):
                agent_model.metadata = {
                    'fields_analyzed': agent.fields_analyzed,
                    'discoveries': agent.discoveries
                }
            
            agent_model.save()


def run_simulation(
    world_instance: World,
    num_fumigators: int = 3,
    num_scouts: int = 2,
    max_steps: int = 1000,
    min_infestation: int = 10
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
    # Crear agentes en Django
    from agents.models import Agent, Simulation
    from django.utils import timezone
    
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
        
        model = FumigationModel(parameters)
        
        # Ejecutar simulación
        steps_executed = 0
        for step in range(max_steps):
            model.step()
            model.update()
            steps_executed = step + 1
            
            # Verificar si hay tareas pendientes
            available_tasks = model.blackboard_service.get_available_tasks()
            if not available_tasks:
                # Verificar si todos los fumigadores están idle
                all_idle = all(agent.status == 'idle' for agent in model.fumigators)
                if all_idle:
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
