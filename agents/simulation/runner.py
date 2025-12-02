"""
Simulation Runner

This module provides the function to run a simulation using the new
Blackboard-based system.
"""

import threading
import time
from django.utils import timezone

from .model import FumigationModel
from agents.models import Simulation
from agents.services import BlackboardService
from agents.communication.broadcaster import StateBroadcaster


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

    # Update simulation status
    simulation.status = 'running'
    simulation.started_at = timezone.now()
    simulation.save()

    # Initialize blackboard service (for legacy compatibility)
    blackboard_service = BlackboardService(world)

    # Create model parameters
    # Forzar num_scouts a 0 - scouts eliminados
    parameters = {
        'num_fumigators': simulation.num_fumigators,
        'num_scouts': 0,  # Scouts eliminados - comenzar directamente con fumigación
        'world_instance': world,
        'blackboard_service': blackboard_service,
        'simulation_id': str(simulation_id),
    }

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

            # Terminate if no pending tasks and all agents idle
            if stats['pending_tasks'] == 0 and model.total_steps > 50:
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

    broadcaster.send_step_update(
        step=model.total_steps,
        agents=agents_data,
        tasks=tasks_data,
        statistics=stats,
        infestation_grid=model.blackboard.knowledge_base.world_state.infestation_grid,
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
