"""
Communication Layer for Unity Integration

Handles the protocol for communicating with Unity clients via WebSocket.
"""

from .protocol import UnityProtocol, MessageType, CommandType
from .handlers import CommandHandler
from .broadcaster import StateBroadcaster

__all__ = ['UnityProtocol', 'MessageType', 'CommandType', 'CommandHandler', 'StateBroadcaster']
