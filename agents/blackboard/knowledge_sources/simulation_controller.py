"""
SimulationControllerKS - Controls simulation completion and agent return to barn

This Knowledge Source:
- Detects when all tasks are completed
- Sends all agents back to barn
- Monitors when all agents have returned to barn
"""

from .base import KnowledgeSource
from ..knowledge_base import EventType, AgentState
from typing import List, Tuple
from world.world_generator import TileType


class SimulationControllerKS(KnowledgeSource):
    """
    SimulationControllerKS manages simulation completion.
    
    Triggers:
    - TASK_COMPLETED: Check if all tasks are done
    - AGENT_MOVED: Check if agents have returned to barn
    
    Logic:
    - When all tasks are completed, send all agents to barn
    - When all agents are at barn, mark simulation as ready to complete
    """
    
    def __init__(self, knowledge_base):
        super().__init__(knowledge_base)
        self.priority = 9  # High priority - run after task allocation
        self.triggers = {
            EventType.TASK_COMPLETED,
            EventType.AGENT_MOVED,
        }
        self.always_run = True  # Check every cycle
        
        # Track if we've already sent agents to barn
        self.agents_sent_to_barn = False
    
    def check_preconditions(self) -> bool:
        """Check if we need to handle simulation completion"""
        # Check if all tasks are completed
        all_tasks = self.kb.get_all_tasks()
        pending_tasks = [t for t in all_tasks if t.status in ['pending', 'assigned', 'in_progress']]
        
        # If no pending tasks and we haven't sent agents to barn yet
        if len(pending_tasks) == 0 and not self.agents_sent_to_barn:
            return True
        
        # If agents have been sent to barn, check if all are at barn
        if self.agents_sent_to_barn:
            return self._check_all_agents_at_barn()
        
        return False
    
    def execute(self):
        """Handle simulation completion"""
        all_tasks = self.kb.get_all_tasks()
        pending_tasks = [t for t in all_tasks if t.status in ['pending', 'assigned', 'in_progress']]
        
        # If all tasks are completed, send all agents to barn
        if len(pending_tasks) == 0 and not self.agents_sent_to_barn:
            self._send_all_agents_to_barn()
            self.agents_sent_to_barn = True
        
        # Check if all agents are at barn
        if self.agents_sent_to_barn:
            if self._check_all_agents_at_barn():
                # Mark simulation as ready to complete
                self.kb.set_shared('simulation_ready_to_complete', True)
    
    def _send_all_agents_to_barn(self):
        """Send all fumigator agents back to barn"""
        fumigators = self.kb.get_agents_by_type('fumigator')
        barn_positions = self.kb.world_state.barn_positions
        
        if not barn_positions:
            print("Warning: No barn positions found")
            return
        
        print(f"Sending {len(fumigators)} agents back to barn - all tasks completed")
        
        for fumigator in fumigators:
            # Find nearest barn position
            barn_position = self._find_nearest_barn(fumigator.position, barn_positions)
            
            if not barn_position:
                continue
            
            # Cancel any current task
            if fumigator.current_task_id:
                task = self.kb.get_task(fumigator.current_task_id)
                if task:
                    self.kb.update_task(
                        task.task_id,
                        status='pending',
                        assigned_agent_id=None,
                    )
            
            # Update agent status
            self.kb.update_agent(
                fumigator.agent_id,
                status='returning_to_barn',
                current_task_id=None,
                path=[],
                path_index=0,
            )
            
            # Send command to agent
            self.kb.set_shared(f'command_{fumigator.agent_id}', {
                'action': 'refill_pesticide',
                'barn_position': barn_position,
                'urgent': True,
            })
            
            # Trigger path calculation for returning to barn
            # The PathPlannerKS will calculate the path when it sees the command
            self.kb.emit_event(EventType.AGENT_LOW_RESOURCE, {
                'agent_id': fumigator.agent_id,
                'action': 'return_to_barn',
            }, source='simulation_controller')
    
    def _find_nearest_barn(self, position: Tuple[int, int], barn_positions: List[Tuple[int, int]]) -> Tuple[int, int]:
        """Find the nearest barn position"""
        if not barn_positions:
            return None
        
        min_distance = float('inf')
        nearest_barn = barn_positions[0]
        
        for barn_pos in barn_positions:
            distance = abs(position[0] - barn_pos[0]) + abs(position[1] - barn_pos[1])
            if distance < min_distance:
                min_distance = distance
                nearest_barn = barn_pos
        
        return nearest_barn
    
    def _check_all_agents_at_barn(self) -> bool:
        """Check if all agents are at barn positions"""
        fumigators = self.kb.get_agents_by_type('fumigator')
        barn_positions = self.kb.world_state.barn_positions
        
        if not barn_positions:
            return False
        
        # Create set of barn positions for fast lookup
        barn_set = set(barn_positions)
        
        # Check if all fumigators are at barn
        for fumigator in fumigators:
            # Check if agent is at any barn position
            if fumigator.position not in barn_set:
                # Agent is not at barn yet
                return False
            
            # Also check if agent is in returning_to_barn or idle status
            # (they should be idle once they reach the barn)
            if fumigator.status not in ['idle', 'returning_to_barn', 'refilling']:
                return False
        
        return True

