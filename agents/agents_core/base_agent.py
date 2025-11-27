"""
BaseAgent - Simple reactive agent following perceive-execute-report cycle

All agents in the system inherit from this class and follow a simple pattern:
1. Perceive: Read command from blackboard
2. Execute: Perform the action
3. Report: Update state in blackboard
"""

import agentpy as ap
from typing import Optional, Dict, Any, Tuple


class BaseAgent(ap.Agent):
    """
    Base class for all agents in the system.

    Agents are simple and reactive:
    - They do NOT make complex decisions
    - They execute commands from the Blackboard
    - They report their state back to the Blackboard

    This follows the principle: "Simple agents, complex emergent behavior"
    """

    def setup(self):
        """
        Initialize the agent.

        This should be called by subclasses after setting up their own state.
        """
        # Get initial position from model
        self.position = self.model.start_positions.get(
            self.id,
            self._get_default_position()
        )

        # Reference to blackboard
        self.blackboard = self.model.blackboard

        # Agent state
        self.status = 'idle'
        self.current_command = None

        # Statistics
        self.tasks_completed = 0
        self.fields_fumigated = 0  # For fumigators
        self.fields_analyzed = 0  # For scouts

    def _get_default_position(self) -> Tuple[int, int]:
        """Get default starting position (barn center)"""
        # Use model.blackboard directly since self.blackboard may not be set yet
        barn_positions = self.model.blackboard.knowledge_base.world_state.barn_positions
        if barn_positions:
            return barn_positions[0]
        # Fallback to center
        return (
            self.model.world_instance.width // 2,
            self.model.world_instance.height // 2
        )

    def step(self):
        """
        Main agent step following the perceive-execute-report cycle.

        1. Perceive: Get command from blackboard
        2. Execute: Perform the action
        3. Report: Update blackboard with new state
        """
        # 1. Perceive
        command = self.perceive()

        # 2. Execute
        if command:
            self.execute(command)
        else:
            # No command, execute default behavior
            self.idle()

        # 3. Report
        self.report()

    def perceive(self) -> Optional[Dict[str, Any]]:
        """
        Perceive the environment and get next command.

        Returns:
            Command dict from blackboard or None
        """
        command = self.blackboard.get_agent_command(str(self.id))

        if command:
            self.current_command = command
            return command

        return None

    def execute(self, command: Dict[str, Any]):
        """
        Execute a command.

        Subclasses should override this to handle specific commands.

        Args:
            command: Command dictionary from blackboard
        """
        action = command.get('action')

        if action == 'move':
            self._execute_move(command)
        else:
            # Unknown command
            pass

    def idle(self):
        """
        Default behavior when no command is available.

        Subclasses can override this.
        """
        self.status = 'idle'

    def report(self):
        """
        Report current state to the blackboard.

        This updates the agent's state in the KnowledgeBase.
        """
        self.blackboard.report_agent_state(
            str(self.id),
            position=self.position,
            status=self.status,
            tasks_completed=self.tasks_completed,
            fields_fumigated=self.fields_fumigated,
            fields_analyzed=self.fields_analyzed,
        )

    # ========== BASIC ACTIONS ==========

    def _execute_move(self, command: Dict[str, Any]):
        """Execute a move command"""
        # Get path from command or agent state
        agent_state = self.blackboard.knowledge_base.get_agent(str(self.id))

        if agent_state and agent_state.path and len(agent_state.path) > agent_state.path_index:
            # Move along path
            next_pos = agent_state.path[agent_state.path_index]
            self.position = next_pos

            # Update path index
            self.blackboard.knowledge_base.update_agent(
                str(self.id),
                path_index=agent_state.path_index + 1
            )

            self.status = 'moving'

            # Check if reached end of path
            if agent_state.path_index + 1 >= len(agent_state.path):
                self._on_path_completed()
        else:
            # No path, try to move to target directly
            target = command.get('to_position') or command.get('target_position')

            if target:
                self.position = tuple(target)
                self.status = 'moving'

    def _on_path_completed(self):
        """Called when agent completes its path"""
        # Clear command
        self.blackboard.clear_agent_command(str(self.id))
        self.current_command = None
        self.status = 'idle'

    def _is_at_position(self, position: Tuple[int, int]) -> bool:
        """Check if agent is at a specific position"""
        return self.position == position
