"""
Simulation Runner

This module provides the function to run a simulation using the new
Blackboard-based system.
"""

import threading
import time
import logging
from django.utils import timezone

from .model import FumigationModel
from agents.models import Simulation
from agents.services import BlackboardService
from agents.communication.broadcaster import StateBroadcaster

logger = logging.getLogger(__name__)


def run_simulation(
    simulation_id: str,
    max_steps: int = 300,
    step_delay: float = 0.5,
    send_updates: bool = True
):
    """
    Run a multi-agent fumigation simulation.

    Args:
        simulation_id: UUID of the simulation
        max_steps: Maximum number of steps
        step_delay: Delay between steps (seconds)
        send_updates: Whether to send WebSocket updates

    Returns:
        Simulation results dict
    """
    # Get simulation from database
    try:
        simulation = Simulation.objects.get(id=simulation_id)
    except Simulation.DoesNotExist:
        return {'error': 'Simulation not found'}

    world = simulation.world
    
    # Forzar refresh desde la base de datos para asegurar que tenemos los datos más recientes
    world.refresh_from_db()

    # Debug: verificar infestation_grid del mundo
    logger.info(f"DEBUG: World ID: {world.id}, Name: {world.name}, infestation_grid type: {type(world.infestation_grid)}")
    print(f"DEBUG: World ID: {world.id}, Name: {world.name}, infestation_grid type: {type(world.infestation_grid)}")
    
    # Verificar también el grid para ver si hay campos
    field_count = 0
    if world.grid:
        for row in world.grid:
            field_count += sum(1 for cell in row if cell == 2)  # TileType.FIELD = 2
    
    logger.info(f"DEBUG: World has {field_count} FIELD cells")
    print(f"DEBUG: World has {field_count} FIELD cells")
    
    if world and world.infestation_grid:
        if isinstance(world.infestation_grid, list):
            # Verificar estructura
            if len(world.infestation_grid) > 0 and isinstance(world.infestation_grid[0], list):
                flat_grid = [val for row in world.infestation_grid for val in row]
                max_val = max(flat_grid) if flat_grid else 0
                non_zero_count = sum(1 for val in flat_grid if val > 0)
                
                # Verificar valores en celdas de campo específicamente
                field_infestation_values = []
                if world.grid and len(world.grid) == len(world.infestation_grid):
                    for z in range(len(world.grid)):
                        if z < len(world.infestation_grid):
                            for x in range(len(world.grid[z])):
                                if x < len(world.infestation_grid[z]):
                                    if world.grid[z][x] == 2:  # FIELD
                                        field_infestation_values.append(world.infestation_grid[z][x])
                
                field_max = max(field_infestation_values) if field_infestation_values else 0
                field_non_zero = sum(1 for val in field_infestation_values if val > 0)
                
                logger.info(f"DEBUG: World infestation_grid - Rows: {len(world.infestation_grid)}, Cols: {len(world.infestation_grid[0])}, Max: {max_val}, Non-zero: {non_zero_count}/{len(flat_grid)}")
                logger.info(f"DEBUG: Field cells infestation - Max: {field_max}, Non-zero: {field_non_zero}/{len(field_infestation_values)}")
                print(f"DEBUG: World infestation_grid - Rows: {len(world.infestation_grid)}, Cols: {len(world.infestation_grid[0])}, Max: {max_val}, Non-zero: {non_zero_count}/{len(flat_grid)}")
                print(f"DEBUG: Field cells infestation - Max: {field_max}, Non-zero: {field_non_zero}/{len(field_infestation_values)}")
            else:
                logger.warning(f"DEBUG: infestation_grid structure invalid - first element type: {type(world.infestation_grid[0]) if world.infestation_grid else 'empty'}")
                print(f"DEBUG: infestation_grid structure invalid - first element type: {type(world.infestation_grid[0]) if world.infestation_grid else 'empty'}")
        else:
            logger.warning(f"DEBUG: World infestation_grid is not a list: {type(world.infestation_grid)}")
            print(f"DEBUG: World infestation_grid is not a list: {type(world.infestation_grid)}")
    else:
        logger.warning("DEBUG: World or infestation_grid is None")
        print("DEBUG: World or infestation_grid is None")

    # Update simulation status
    simulation.status = 'running'
    simulation.started_at = timezone.now()
    simulation.save()

    # Initialize blackboard service (for legacy compatibility)
    blackboard_service = BlackboardService(world)

    # Create model parameters
    # Forzar num_scouts a 0 - scouts eliminados
    # Usar min_infestation de 10 como valor razonable (en lugar de 1)
    # Esto evita crear tareas para niveles de infestación muy bajos
    min_infestation = 10  # Solo crear tareas para infestación >= 10
    parameters = {
        'num_fumigators': simulation.num_fumigators,
        'num_scouts': 0,  # Scouts eliminados - comenzar directamente con fumigación
        'world_instance': world,
        'blackboard_service': blackboard_service,
        'simulation_id': str(simulation_id),
        'min_infestation': min_infestation,  # Pasar min_infestation al modelo
    }
    
    logger.info(f"DEBUG: Using min_infestation: {min_infestation}")
    print(f"DEBUG: Using min_infestation: {min_infestation}")

    # Create and run model
    model = FumigationModel(parameters)
    
    # Ensure setup() was called (AgentPy should call it automatically, but verify)
    if not hasattr(model, 'total_steps'):
        # If setup() wasn't called, call it manually
        model.setup()

    # Broadcaster to send Unity-compatible messages via WebSocket
    broadcaster = StateBroadcaster(simulation_id) if send_updates else None

    try:
        # Run simulation
        for step in range(max_steps):
            # Execute step
            model.step()

            # Send WebSocket update
            if broadcaster:
                _send_step_update(broadcaster, model)

            # Update simulation in database
            simulation.steps_executed = model.total_steps
            simulation.save()

            # Check termination conditions
            stats = model.blackboard.get_statistics()

            # Check if simulation is ready to complete (all agents at barn)
            simulation_ready = model.blackboard.knowledge_base.get_shared('simulation_ready_to_complete')
            
            # Terminate if:
            # 1. No pending tasks
            # 2. All agents are at barn (simulation_ready_to_complete is True)
            # 3. Minimum steps executed (to avoid premature termination)
            if stats['pending_tasks'] == 0 and simulation_ready and model.total_steps > 50:
                # Verify all agents are at barn
                all_agents_at_barn = True
                barn_positions = model.blackboard.knowledge_base.world_state.barn_positions
                if barn_positions:
                    barn_set = set(barn_positions)
                    for agent in model.agents:
                        agent_state = model.blackboard.knowledge_base.get_agent(str(agent.id))
                        if agent_state:
                            if agent_state.position not in barn_set:
                                all_agents_at_barn = False
                                break
                            if agent_state.status not in ['idle', 'returning_to_barn', 'refilling']:
                                all_agents_at_barn = False
                                break
                
                if all_agents_at_barn:
                    print(f"Simulation completed: All tasks done and all agents returned to barn")
                    break
            
            # Fallback: Terminate if no pending tasks and all agents idle (old behavior)
            # This is kept as a safety net
            elif stats['pending_tasks'] == 0 and model.total_steps > 50:
                idle_agents = model.blackboard.knowledge_base.get_idle_agents()
                if len(idle_agents) == len(model.agents):
                    print(f"Simulation completed: No pending tasks and all agents idle")
                    break

            # Delay between steps
            time.sleep(step_delay)

        # End simulation
        model.end()

        # Update simulation status
        simulation.status = 'completed'
        simulation.completed_at = timezone.now()
        simulation.steps_executed = model.total_steps

        # Get final statistics
        stats = model.get_status()

        simulation.tasks_completed = stats['tasks']['completed']
        simulation.fields_fumigated = stats['progress']['fields_fumigated']
        simulation.results = stats
        simulation.save()

        # Send completion message
        if broadcaster:
            _send_completion(broadcaster, model, simulation)

        return stats

    except Exception as e:
        # Error occurred
        simulation.status = 'failed'
        simulation.save()

        # Send error message
        if broadcaster:
            _send_error(broadcaster, str(e))

        raise


def run_simulation_async(simulation_id: str, **kwargs):
    """
    Run simulation in a background thread.

    Args:
        simulation_id: UUID of the simulation
        **kwargs: Additional arguments for run_simulation
    """
    thread = threading.Thread(
        target=run_simulation,
        args=(simulation_id,),
        kwargs=kwargs,
        daemon=True
    )
    thread.start()
    return thread


def _send_step_update(broadcaster: StateBroadcaster, model: FumigationModel):
    """Send step update via WebSocket using the Unity-compatible protocol."""
    stats = model.get_status()

    # Get agent states
    agents_data = []
    for agent in model.agents:
        agent_state = model.blackboard.knowledge_base.get_agent(str(agent.id))
        if agent_state:
            agents_data.append({
                'agent_id': str(agent.id),
                'agent_type': agent_state.agent_type,
                'position': list(agent_state.position),
                'status': agent_state.status,
                'pesticide_level': agent_state.pesticide_level if agent_state.agent_type == 'fumigator' else 0,
                'tasks_completed': agent_state.tasks_completed,
            })

    # Get task states
    tasks_data = []
    for task in model.blackboard.knowledge_base.get_all_tasks():
        tasks_data.append({
            'task_id': str(task.task_id),
            'position': list(task.position),
            'infestation_level': task.infestation_level,
            'priority': task.priority,
            'status': task.status,
            'assigned_agent_id': task.assigned_agent_id,
        })

    # Debug: verificar infestation_grid antes de enviar
    infestation_grid_to_send = model.blackboard.knowledge_base.world_state.infestation_grid
    if infestation_grid_to_send:
        flat_grid = [val for row in infestation_grid_to_send for val in row]
        max_val = max(flat_grid) if flat_grid else 0
        non_zero_count = sum(1 for val in flat_grid if val > 0)
        if model.total_steps == 1:  # Solo log en el primer paso para no spamear
            logger.info(f"DEBUG: Sending infestation_grid - Max: {max_val}, Non-zero: {non_zero_count}/{len(flat_grid)}")
            print(f"DEBUG: Sending infestation_grid - Max: {max_val}, Non-zero: {non_zero_count}/{len(flat_grid)}")
    else:
        if model.total_steps == 1:
            logger.warning("DEBUG: infestation_grid_to_send is None")
            print("DEBUG: infestation_grid_to_send is None")
    
    broadcaster.send_step_update(
        step=model.total_steps,
        agents=agents_data,
        tasks=tasks_data,
        statistics=stats,
        infestation_grid=infestation_grid_to_send,
    )


def _send_completion(broadcaster: StateBroadcaster, model: FumigationModel, simulation):
    """Send completion message via WebSocket using the Unity-compatible protocol."""
    stats = model.get_status()

    broadcaster.send_simulation_completed(
        total_steps=model.total_steps,
        statistics=stats,
        results=simulation.results,
    )


def _send_error(broadcaster: StateBroadcaster, error_message: str):
    """Send error message via WebSocket using the Unity-compatible protocol."""
    broadcaster.send_error(error_message)
