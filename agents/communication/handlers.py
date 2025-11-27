"""
Command Handlers for Unity Communication

Handles commands received from Unity clients.
"""

from typing import Dict, Any, Optional, Callable
import json


class CommandHandler:
    """
    Handles commands received from Unity clients.

    This class routes incoming messages to appropriate handlers.
    """

    def __init__(self):
        """Initialize command handler"""
        self.handlers: Dict[str, Callable] = {
            'ping': self._handle_ping,
            'get_status': self._handle_get_status,
            'command_confirmation': self._handle_command_confirmation,
            'render_complete': self._handle_render_complete,
        }

    def handle_message(self, message_data: Dict[str, Any], context: Optional[Dict] = None) -> Optional[Dict]:
        """
        Handle an incoming message from Unity.

        Args:
            message_data: Parsed message data
            context: Optional context (e.g., simulation_id, consumer instance)

        Returns:
            Response message or None
        """
        message_type = message_data.get('type')

        if not message_type:
            return self._error_response("Missing message type")

        handler = self.handlers.get(message_type)

        if not handler:
            return self._error_response(f"Unknown message type: {message_type}")

        try:
            return handler(message_data, context)
        except Exception as e:
            return self._error_response(f"Handler error: {str(e)}")

    def _handle_ping(self, message_data: Dict, context: Dict) -> Dict:
        """Handle ping message"""
        from .protocol import UnityProtocol

        return UnityProtocol.pong(timestamp=message_data.get('timestamp'))

    def _handle_get_status(self, message_data: Dict, context: Dict) -> Dict:
        """Handle get status request"""
        # This would be implemented by the consumer
        # For now, return placeholder
        return {
            'type': 'status_response',
            'status': 'running',
        }

    def _handle_command_confirmation(self, message_data: Dict, context: Dict) -> Dict:
        """Handle command confirmation from Unity"""
        agent_id = message_data.get('agent_id')
        command_id = message_data.get('command_id')
        success = message_data.get('success', True)

        if not agent_id:
            return self._error_response("Missing agent_id")

        # Trigger confirmation in the backend
        # This would notify the simulation that the command was executed
        if context and 'simulation_id' in context:
            from agents.agent_system import _receive_agent_confirmation
            _receive_agent_confirmation(context['simulation_id'], agent_id)

        return {
            'type': 'confirmation_received',
            'agent_id': agent_id,
            'command_id': command_id,
            'success': success,
        }

    def _handle_render_complete(self, message_data: Dict, context: Dict) -> Dict:
        """Handle render complete notification"""
        # Unity finished rendering a frame
        return {
            'type': 'render_acknowledged',
        }

    def _error_response(self, error: str) -> Dict:
        """Create error response"""
        from .protocol import UnityProtocol

        return UnityProtocol.error(error)

    def register_handler(self, message_type: str, handler: Callable):
        """
        Register a custom handler for a message type.

        Args:
            message_type: The message type to handle
            handler: Function(message_data, context) -> response
        """
        self.handlers[message_type] = handler
