"""
FumigatorAgent - Simple reactive fumigator that executes tasks

The fumigator follows commands from the blackboard to fumigate fields
and refill pesticide when needed.
"""

from .base_agent import BaseAgent
from ..blackboard.knowledge_base import EventType
from typing import Dict, Any


class FumigatorAgent(BaseAgent):
    """
    Fumigator agent that fumigates infested fields.

    Commands it responds to:
    - execute_task: Execute a fumigation task
    - refill_pesticide: Refill pesticide at barn
    - move: Move to a specific position

    Behavior:
    - Follows path to task
    - Fumigates at destination
    - Refills when commanded
    - Updates field weights when crossing fields
    """

    def setup(self):
        """Initialize fumigator agent"""
        super().setup()

        self.agent_type = 'fumigator'

        # Pesticide system
        self.pesticide_capacity = 1000
        self.pesticide_level = 1000

        # Current task
        self.current_task_id = None
        
        # Track waiting time to avoid deadlocks
        self.waiting_steps = 0
        self.max_waiting_steps = 2  # Reduced from 3 to 2 - resolve deadlocks faster

        # Register with blackboard
        from ..blackboard.knowledge_base import AgentState
        agent_state = AgentState(
            agent_id=str(self.id),
            agent_type='fumigator',
            position=self.position,
            status='idle',
            pesticide_level=self.pesticide_level,
            pesticide_capacity=self.pesticide_capacity,
        )
        self.blackboard.register_agent(agent_state)

    def execute(self, command: Dict[str, Any]):
        """Execute fumigator-specific commands"""
        action = command.get('action')

        if action == 'execute_task':
            self._execute_task(command)
        elif action == 'refill_pesticide':
            self._execute_refill(command)
        elif action == 'move':
            self._execute_move(command)
        else:
            # Unknown command
            pass

    def _execute_task(self, command: Dict[str, Any]):
        """Execute a fumigation task"""
        task_id = command.get('task_id')
        task_position = command.get('task_position')

        if not task_id or not task_position:
            return

        self.current_task_id = task_id
        self.status = 'executing_task'

        # Get agent state from blackboard
        agent_state = self.blackboard.knowledge_base.get_agent(str(self.id))

        if not agent_state:
            return

        # Check if we have a path
        if agent_state.path and len(agent_state.path) > agent_state.path_index:
            # Follow path
            next_pos = agent_state.path[agent_state.path_index]

            # Check for collision with other agents
            if self._check_collision(next_pos):
                # Collision detected - wait this step, don't move
                self.waiting_steps += 1
                self.status = 'waiting'
                
                # Si hemos estado esperando mucho tiempo, intentar recalcular ruta o buscar alternativa
                if self.waiting_steps >= self.max_waiting_steps:
                    # Intentar encontrar una ruta alternativa o esperar más
                    # Por ahora, avanzar el path_index para intentar saltar la posición bloqueada
                    # en el siguiente paso
                    new_path_index = agent_state.path_index + 1
                    if new_path_index < len(agent_state.path):
                        # Hay más posiciones en el path, avanzar
                        self.blackboard.knowledge_base.update_agent(
                            str(self.id),
                            path_index=new_path_index
                        )
                        self.waiting_steps = 0  # Reset counter
                        # Continuar en el siguiente paso - si la siguiente posición está libre, avanzar
                    else:
                        # No hay más posiciones en el path - estamos atascados
                        # Marcar tarea como fallida para que se reasigne
                        print(f"DEBUG: Agent {self.id} stuck - path exhausted at position {self.position}, target {task_position}")
                        self._on_task_failed(task_id)
                    return
                
                return

            # Fumigar durante el camino - fumigar TODO lo que se pueda en cada paso
            # Si no alcanza el pesticida, cancelar tarea y buscar otra o regresar
            if not self._fumigate_all_possible_in_path():
                # No hay suficiente pesticida - cancelar tarea y regresar
                self._cancel_task_and_return_to_barn()
                return

            # Reset waiting counter on successful move
            self.waiting_steps = 0
            
            # Update field weight if crossing a field (solo campos, no caminos)
            self._update_field_weight(next_pos)

            self.position = next_pos
            self.status = 'moving'

            # Update path index
            self.blackboard.knowledge_base.update_agent(
                str(self.id),
                path_index=agent_state.path_index + 1
            )

            # Check if arrived at destination
            if self.position == tuple(task_position):
                self._fumigate_at_position(task_position, task_id)
        else:
            # No path or reached end - check if at destination
            if self.position == tuple(task_position):
                self._fumigate_at_position(task_position, task_id)
            else:
                # No path and not at destination - something went wrong
                self._on_task_failed(task_id)

    def _fumigate_all_possible_in_path(self) -> bool:
        """
        Fumiga TODO lo posible en el camino actual.
        Retorna True si hay suficiente pesticida para continuar, False si no.
        """
        kb = self.blackboard.knowledge_base
        agent_state = kb.get_agent(str(self.id))
        
        if not agent_state or not agent_state.path:
            return True  # No path, continue
        
        # Calcular pesticida necesario para todo el camino restante
        remaining_path = agent_state.path[agent_state.path_index:] if agent_state.path_index < len(agent_state.path) else []
        task = kb.get_task(self.current_task_id) if self.current_task_id else None
        
        total_pesticide_needed = 0
        
        # Contar pesticida necesario en el camino restante
        from world.world_generator import TileType
        for path_pos in remaining_path:
            px, pz = path_pos
            if (0 <= pz < len(kb.world_state.grid) and 
                0 <= px < len(kb.world_state.grid[pz]) and
                kb.world_state.grid[pz][px] == TileType.FIELD):
                infestation = kb.get_infestation(px, pz)
                if infestation >= 10:
                    total_pesticide_needed += infestation
        
        # Agregar pesticida del destino
        if task:
            total_pesticide_needed += task.infestation_level
        
        # Si no tenemos suficiente pesticida, retornar False
        if self.pesticide_level < total_pesticide_needed:
            return False
        
        # Fumigar en la posición actual si hay infestación
        x, z = self.position
        infestation = kb.get_infestation(x, z)
        if infestation >= 10 and self.pesticide_level >= infestation:
            kb.update_infestation(x, z, 0)
            self.pesticide_level -= infestation
            self.fields_fumigated += 1
            
            # Si había una tarea en esta posición, completarla
            task_at_pos = kb.get_task_by_position(x, z)
            if task_at_pos and task_at_pos.status in ['pending', 'assigned', 'in_progress']:
                kb.update_task(task_at_pos.task_id, status='completed')
                if self.current_task_id == task_at_pos.task_id:
                    self._on_task_completed(task_at_pos.task_id)
        
        return True
    
    def _cancel_task_and_return_to_barn(self):
        """Cancela la tarea actual y regresa al granero"""
        kb = self.blackboard.knowledge_base
        
        if self.current_task_id:
            task = kb.get_task(self.current_task_id)
            if task:
                kb.update_task(self.current_task_id, status='pending', assigned_agent_id=None)
        
        self.current_task_id = None
        self.status = 'returning_to_barn'
        
        # Limpiar path actual
        kb.update_agent(str(self.id), path=[], path_index=0)
        
        # Encontrar granero más cercano
        barn_positions = kb.world_state.barn_positions
        if barn_positions:
            barn_position = min(barn_positions, 
                              key=lambda b: abs(self.position[0] - b[0]) + abs(self.position[1] - b[1]))
            
            # Enviar comando para regresar usando set_shared
            kb.set_shared(f'command_{self.id}', {
                'action': 'refill_pesticide',
                'barn_position': barn_position,
                'urgent': True,
            })
    
    def _fumigate_if_possible(self, position: tuple):
        """
        Fumiga en la posición actual si hay infestación y hay suficiente pesticida.
        Se usa durante el movimiento para fumigar celdas en el camino.
        
        IMPORTANTE: Solo fumiga si tiene suficiente pesticida para:
        1. Fumigar la celda actual
        2. Llegar al destino y fumigarlo
        """
        x, z = position
        kb = self.blackboard.knowledge_base

        # Get current infestation
        infestation = kb.get_infestation(x, z)

        # Solo fumigar si hay infestación significativa (>= 10)
        if infestation < 10:
            return
        
        # Si tenemos una tarea asignada, verificar que tengamos suficiente pesticida
        # para fumigar esta celda Y llegar al destino
        if self.current_task_id:
            task = kb.get_task(self.current_task_id)
            if task:
                # Calcular pesticida necesario para el destino
                destination_pesticide = task.infestation_level
                
                # Estimar pesticida necesario para el resto del camino
                # Usar una estimación más realista basada en el pathfinding real
                agent_state = kb.get_agent(str(self.id))
                if agent_state and agent_state.path:
                    remaining_path = agent_state.path[agent_state.path_index:] if agent_state.path_index < len(agent_state.path) else []
                    
                    # Calcular pesticida real en el camino restante
                    # Solo contar celdas de campo con infestación >= 10
                    estimated_path_pesticide = 0
                    from world.world_generator import TileType
                    
                    for path_pos in remaining_path:
                        px, pz = path_pos
                        # Verificar si es un campo
                        if (0 <= pz < len(kb.world_state.grid) and 
                            0 <= px < len(kb.world_state.grid[pz]) and
                            kb.world_state.grid[pz][px] == TileType.FIELD):
                            # Obtener infestación real
                            path_infestation = kb.get_infestation(px, pz)
                            if path_infestation >= 10:
                                estimated_path_pesticide += path_infestation
                else:
                    estimated_path_pesticide = 0
                
                # Total necesario: celda actual + destino + camino restante
                # Agregar un margen de seguridad del 10%
                total_needed = int((infestation + destination_pesticide + estimated_path_pesticide) * 1.1)
                
                # Solo fumigar si tenemos suficiente pesticida para todo
                if self.pesticide_level < total_needed:
                    # No fumigar ahora - conservar pesticida para el destino
                    return
        
        # Si llegamos aquí, podemos fumigar
        if self.pesticide_level >= infestation:
            # Fumigate
            kb.update_infestation(x, z, 0)
            self.pesticide_level -= infestation
            self.fields_fumigated += 1
            
            # Si había una tarea en esta posición, completarla
            task = kb.get_task_by_position(x, z)
            if task and task.status in ['pending', 'assigned', 'in_progress']:
                kb.update_task(task.task_id, status='completed')
                if self.current_task_id == task.task_id:
                    self._on_task_completed(task.task_id)

    def _fumigate_at_position(self, position: tuple, task_id: str):
        """Fumigate at the current position"""
        x, z = position
        kb = self.blackboard.knowledge_base

        # Get current infestation
        infestation = kb.get_infestation(x, z)

        if infestation <= 0:
            # Already fumigated
            self._on_task_completed(task_id)
            return

        # Check if we have enough pesticide
        if self.pesticide_level < infestation:
            # Not enough pesticide - report failure
            self._on_task_failed(task_id)
            return

        # Fumigate
        kb.update_infestation(x, z, 0)
        self.pesticide_level -= infestation
        self.fields_fumigated += 1

        self.status = 'fumigating'

        # Complete task
        self._on_task_completed(task_id)

    def _on_task_completed(self, task_id: str):
        """Called when task is completed"""
        kb = self.blackboard.knowledge_base

        # Update task status
        kb.update_task(task_id, status='completed')

        # Update agent
        self.current_task_id = None
        self.tasks_completed += 1
        self.status = 'idle'

        # Clear command
        self.blackboard.clear_agent_command(str(self.id))

    def _on_task_failed(self, task_id: str):
        """Called when task fails"""
        kb = self.blackboard.knowledge_base

        # Get task to increment failure count
        task = kb.get_task(task_id)
        if task:
            failure_count = task.failure_count + 1
            from datetime import datetime
            # Update task status with failure count
            kb.update_task(
                task_id, 
                status='failed',
                failure_count=failure_count,
                last_failure_at=datetime.now()
            )
        else:
            # Task doesn't exist, just mark as failed
            kb.update_task(task_id, status='failed')

        # Update agent
        self.current_task_id = None
        self.status = 'idle'

        # Clear command
        self.blackboard.clear_agent_command(str(self.id))

    def _execute_refill(self, command: Dict[str, Any]):
        """Execute refill command"""
        barn_position = command.get('barn_position')

        if not barn_position:
            return

        # Move towards barn
        if self.position != tuple(barn_position):
            self._move_towards_barn(barn_position)
            self.status = 'returning_to_barn'
        else:
            # At barn, refill
            self.pesticide_level = self.pesticide_capacity
            self.status = 'idle'

            # Emit refill event
            self.blackboard.report_event(
                EventType.AGENT_REFILLED,
                {
                    'agent_id': str(self.id),
                    'pesticide_level': self.pesticide_level,
                },
                source=str(self.id)
            )

            # Clear command
            self.blackboard.clear_agent_command(str(self.id))

    def _move_towards_barn(self, barn_position: tuple):
        """
        Move towards barn - NO fumigate during return journey.
        Priority is to get back to barn quickly.
        """
        # Get path from agent state
        agent_state = self.blackboard.knowledge_base.get_agent(str(self.id))

        if agent_state and agent_state.path:
            # Follow path
            if len(agent_state.path) > agent_state.path_index:
                next_pos = agent_state.path[agent_state.path_index]
                
                # Check for collision
                if self._check_collision(next_pos):
                    # Collision - wait but don't block forever
                    self.waiting_steps += 1
                    self.status = 'waiting'
                    
                    # Si esperamos mucho, intentar soluciones alternativas
                    if self.waiting_steps >= self.max_waiting_steps:
                        # Opción 1: Intentar avanzar el path_index (saltar posición bloqueada)
                        new_path_index = agent_state.path_index + 1
                        if new_path_index < len(agent_state.path):
                            next_next_pos = agent_state.path[new_path_index]
                            if not self._check_collision(next_next_pos):
                                # La siguiente posición está libre, saltar
                                self.blackboard.knowledge_base.update_agent(
                                    str(self.id),
                                    path_index=new_path_index
                                )
                                self.position = next_next_pos
                                self.status = 'returning_to_barn'
                                self.waiting_steps = 0
                                self.blackboard.knowledge_base.update_agent(
                                    str(self.id),
                                    path_index=new_path_index + 1
                                )
                                return
                        
                        # Opción 2: Recalcular ruta completa (evitar deadlock)
                        print(f"DEBUG: Agent {self.id} stuck returning to barn - recalculating path")
                        from agents.blackboard.knowledge_sources.path_planner import PathPlannerKS
                        path_planner = PathPlannerKS(self.blackboard.knowledge_base)
                        new_path = path_planner._calculate_path(self.position, barn_position, 'fumigator')
                        
                        if new_path and len(new_path) > 0:
                            # Nueva ruta encontrada
                            self.blackboard.knowledge_base.update_agent(
                                str(self.id),
                                path=new_path,
                                path_index=0
                            )
                            # Intentar moverse con la nueva ruta
                            if len(new_path) > 0:
                                new_next_pos = new_path[0]
                                if not self._check_collision(new_next_pos):
                                    self.position = new_next_pos
                                    self.status = 'returning_to_barn'
                                    self.waiting_steps = 0
                                    self.blackboard.knowledge_base.update_agent(
                                        str(self.id),
                                        path_index=1
                                    )
                                    return
                        
                        # Opción 3: Avanzar path_index de todas formas (último recurso)
                        if new_path_index < len(agent_state.path):
                            self.blackboard.knowledge_base.update_agent(
                                str(self.id),
                                path_index=new_path_index
                            )
                            self.waiting_steps = 0
                        else:
                            # Path agotado - intentar movimiento directo
                            self.waiting_steps = 0
                            # Continuar con lógica de movimiento directo abajo
                    else:
                        return  # Aún esperando, no hacer nada
                
                # Reset waiting counter on successful move
                self.waiting_steps = 0
                
                # Move to next position - NO fumigation during return
                self.position = next_pos
                self.status = 'returning_to_barn'

                self.blackboard.knowledge_base.update_agent(
                    str(self.id),
                    path_index=agent_state.path_index + 1
                )
        else:
            # No path, move directly (simple) - prefer roads if possible
            x, z = self.position
            bx, bz = barn_position

            # Calculate next position
            if abs(bx - x) > abs(bz - z):
                new_x = x + (1 if bx > x else -1)
                next_pos = (new_x, z)
            else:
                new_z = z + (1 if bz > z else -1)
                next_pos = (x, new_z)
            
            # Check for collision before moving
            if self._check_collision(next_pos):
                # Collision detected - wait this step
                self.waiting_steps += 1
                self.status = 'waiting'
                
                # Si esperamos mucho, intentar moverse en otra dirección
                if self.waiting_steps >= self.max_waiting_steps:
                    # Intentar moverse en la dirección alternativa
                    if abs(bx - x) > abs(bz - z):
                        # Intentar vertical
                        new_z = z + (1 if bz > z else -1)
                        alt_pos = (x, new_z)
                    else:
                        # Intentar horizontal
                        new_x = x + (1 if bx > x else -1)
                        alt_pos = (new_x, z)
                    
                    if not self._check_collision(alt_pos):
                        self.position = alt_pos
                        self.waiting_steps = 0
                        self.status = 'returning_to_barn'
                        return
                    else:
                        self.waiting_steps = 0  # Reset and try again next step
                return
            
            # Reset waiting counter on successful move
            self.waiting_steps = 0
            
            # Move - NO fumigation
            self.position = next_pos
            self.status = 'returning_to_barn'

    def _update_field_weight(self, position: tuple):
        """
        Update field weight when crossing a field (only for fields, not roads).
        Los pesos aumentan pero NO bloquean completamente - si es necesario pasar, se pasa.
        """
        from world.world_generator import TileType

        x, z = position
        kb = self.blackboard.knowledge_base

        # Solo actualizar peso para campos, NO para caminos
        # Los caminos deben mantener peso bajo para ser siempre preferidos
        if kb.world_state.grid[z][x] == TileType.FIELD:
            # Increase weight (exponentially) pero con un límite máximo
            # Esto evita que los campos se vuelvan completamente intransitables
            current_weight = kb.get_field_weight(x, z)
            new_weight = current_weight * 1.5 if current_weight > 0 else 1.5
            
            # Límite máximo de peso para evitar bloqueos completos
            # Si el peso es muy alto, los agentes aún pueden pasar pero con mayor costo
            max_weight = 100.0  # Peso máximo - después de esto, el costo se estabiliza
            if new_weight > max_weight:
                new_weight = max_weight
            
            kb.update_field_weight(x, z, new_weight)
        # Si es ROAD o BARN, no hacer nada - mantienen su peso bajo por defecto

    def report(self):
        """Report fumigator state to blackboard"""
        super().report()

        # Update pesticide level
        self.blackboard.knowledge_base.update_agent(
            str(self.id),
            pesticide_level=self.pesticide_level,
            current_task_id=self.current_task_id,
        )
