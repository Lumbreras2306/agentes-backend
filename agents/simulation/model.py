"""
FumigationModel - AgentPy model using the Blackboard system

This is the main simulation model that coordinates:
- Agent creation
- Blackboard system
- Step execution
- State synchronization
"""

import agentpy as ap
from typing import Dict, Tuple
from ..blackboard import Blackboard
from ..agents_core import FumigatorAgent


class FumigationModel(ap.Model):
    """
    Multi-agent fumigation simulation model.

    This model:
    - Creates scout and fumigator agents
    - Initializes the Blackboard system
    - Coordinates step execution
    - Syncs state to Django models
    """

    def setup(self):
        """Initialize the model"""
        # Get parameters
        self.num_fumigators = self.p.get('num_fumigators', 5)
        self.num_scouts = 0  # Scouts eliminados - comenzar directamente con fumigación
        self.world_instance = self.p.get('world_instance')
        self.blackboard_service = self.p.get('blackboard_service')  # Legacy
        self.simulation_id = self.p.get('simulation_id')  # For WebSocket

        if not self.world_instance:
            raise ValueError("world_instance is required")

        # Initialize Blackboard system
        self.blackboard = Blackboard(self.world_instance, self.blackboard_service)

        # Calculate start positions (barn cells)
        self.start_positions = self._calculate_start_positions()

        # Create agents - solo fumigadores
        self.fumigators = ap.AgentList(self, self.num_fumigators, FumigatorAgent)
        # Scouts eliminados - no crear lista de scouts

        # All agents - solo fumigadores
        self.agents = self.fumigators

        # Start the blackboard
        self.blackboard.start()
        
        # Inicializar todas las tareas desde el inicio (sin esperar scouts)
        self._initialize_all_tasks()

        # Statistics
        self.total_steps = 0
        self.total_tasks_completed = 0

    def step(self):
        """Execute one simulation step"""
        # Ensure total_steps is initialized (in case setup() wasn't called)
        if not hasattr(self, 'total_steps'):
            self.total_steps = 0
        
        self.total_steps += 1

        # 1. Execute Blackboard control cycle
        # This activates Knowledge Sources and makes decisions
        self.blackboard.step()

        # 2. Execute agent steps
        # Agents perceive, execute, and report
        for agent in self.agents:
            agent.step()

        # 3. Sync to Django (periodically)
        if self.total_steps % 5 == 0:  # Every 5 steps
            self.blackboard.sync_to_django()

    def end(self):
        """Called when simulation ends"""
        # Final sync to Django
        self.blackboard.sync_to_django()

        # Stop blackboard
        self.blackboard.stop()

        # Collect statistics
        stats = self.blackboard.get_statistics()
        self.total_tasks_completed = stats['completed_tasks']

    def _calculate_start_positions(self) -> Dict[int, Tuple[int, int]]:
        """
        Calculate start positions for all agents (barn cells).

        Returns:
            Dict mapping agent ID to position
        """
        from world.world_generator import TileType

        # Find all barn cells
        barn_cells = []
        for z in range(self.world_instance.height):
            for x in range(self.world_instance.width):
                if self.world_instance.grid[z][x] == TileType.BARN:
                    barn_cells.append((x, z))

        if not barn_cells:
            # No barn found, use center
            center = (self.world_instance.width // 2, self.world_instance.height // 2)
            barn_cells = [center]

        # Assign positions (cycle through barn cells if more agents than cells)
        positions = {}
        total_agents = self.num_fumigators  # Solo fumigadores

        for i in range(total_agents):
            positions[i] = barn_cells[i % len(barn_cells)]

        return positions
    
    def _initialize_all_tasks(self):
        """
        Inicializa todas las tareas desde el inicio basándose en el infestation_grid.
        Todas las celdas están reveladas desde el inicio.
        """
        from world.world_generator import TileType
        from ..blackboard.knowledge_base import TaskState
        import uuid
        
        # Usar min_infestation del parámetro si está disponible, sino usar 10 como valor razonable
        min_infestation = self.p.get('min_infestation', 10)  # Mínimo nivel de infestación para crear tarea
        infestation_grid = self.world_instance.infestation_grid
        grid = self.world_instance.grid
        
        tasks_created = 0
        
        for z in range(self.world_instance.height):
            for x in range(self.world_instance.width):
                # Solo crear tareas para campos (FIELD) con infestación
                if grid[z][x] == TileType.FIELD:
                    infestation = infestation_grid[z][x]
                    if infestation >= min_infestation:
                        # Verificar si ya existe una tarea para esta posición
                        existing_tasks = self.blackboard.knowledge_base.get_all_tasks()
                        task_exists = any(
                            task.position == (x, z) and task.status in ['pending', 'assigned', 'in_progress']
                            for task in existing_tasks
                        )
                        
                        if not task_exists:
                            # Calcular prioridad basada en nivel de infestación
                            if infestation >= 80:
                                priority = 'critical'
                            elif infestation >= 50:
                                priority = 'high'
                            elif infestation >= 20:
                                priority = 'medium'
                            else:
                                priority = 'low'
                            
                            # Crear tarea
                            task_state = TaskState(
                                task_id=str(uuid.uuid4()),
                                position=(x, z),
                                infestation_level=infestation,
                                priority=priority,
                                status='pending',
                                metadata={
                                    'crop_type': self.world_instance.crop_grid[z][x] if hasattr(self.world_instance, 'crop_grid') else 'unknown',
                                    'initialized_at_start': True
                                }
                            )
                            
                            self.blackboard.knowledge_base.create_task(task_state)
                            
                            # También crear en Django para persistencia
                            from agents.models import BlackboardTask, TaskPriority, TaskStatus
                            priority_map = {
                                'low': TaskPriority.LOW,
                                'medium': TaskPriority.MEDIUM,
                                'high': TaskPriority.HIGH,
                                'critical': TaskPriority.CRITICAL,
                            }
                            try:
                                BlackboardTask.objects.create(
                                    id=task_state.task_id,
                                    world=self.world_instance,
                                    position_x=x,
                                    position_z=z,
                                    infestation_level=infestation,
                                    priority=priority_map.get(priority, TaskPriority.MEDIUM),
                                    status=TaskStatus.PENDING,
                                    metadata=task_state.metadata,
                                )
                            except Exception as e:
                                print(f"Error creating Django task: {e}")
                            
                            tasks_created += 1
        
        print(f"✓ Inicializadas {tasks_created} tareas desde el inicio (sin scouts)")

    def get_status(self) -> Dict:
        """Get current simulation status"""
        stats = self.blackboard.get_statistics()

        return {
            'step': self.total_steps,
            'agents': {
                'total': len(self.agents),
                'fumigators': len(self.fumigators),
                'scouts': 0,  # Scouts eliminados
            },
            'tasks': {
                'total': stats['total_tasks'],
                'pending': stats['pending_tasks'],
                'completed': stats['completed_tasks'],
            },
            'progress': {
                'fields_fumigated': stats['total_fields_fumigated'],
                'fields_analyzed': 0,  # Ya no hay scouts
                'total_infestation': stats['total_infestation'],
                'infested_cells': stats['infested_cells'],
            }
        }
