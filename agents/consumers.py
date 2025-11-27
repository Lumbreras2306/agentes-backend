"""
Consumidor WebSocket para simulaciones en tiempo real.
Permite que los clientes (frontend React y Unity) se conecten y reciban actualizaciones
de la simulación en tiempo real.
"""
import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.shortcuts import get_object_or_404
from .models import Simulation


class SimulationConsumer(AsyncWebsocketConsumer):
    """
    Consumidor WebSocket para simulaciones.
    Los clientes se conectan a /ws/simulations/{simulation_id}/
    y reciben actualizaciones en tiempo real del estado de la simulación.
    """
    
    async def connect(self):
        """Se ejecuta cuando un cliente se conecta"""
        self.simulation_id = self.scope['url_route']['kwargs']['simulation_id']
        self.room_group_name = f'simulation_{self.simulation_id}'
        
        # Verificar que la simulación existe
        try:
            await self.get_simulation(self.simulation_id)
        except Exception as e:
            await self.close()
            return
        
        # Unirse al grupo de la simulación
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Enviar mensaje de conexión exitosa
        await self.send(text_data=json.dumps({
            'type': 'connection',
            'message': 'Conectado a la simulación',
            'simulation_id': str(self.simulation_id)
        }))
    
    async def disconnect(self, close_code):
        """Se ejecuta cuando un cliente se desconecta"""
        # Salir del grupo
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Se ejecuta cuando se recibe un mensaje del cliente"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'ping':
                # Responder a ping con pong
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': data.get('timestamp')
                }))
            elif message_type == 'get_status':
                # Enviar estado actual de la simulación
                simulation = await self.get_simulation(self.simulation_id)
                await self.send_simulation_status(simulation)
            elif message_type == 'command_confirmation':
                # Confirmación de que un agente completó un comando
                agent_id = data.get('agent_id')
                command_id = data.get('command_id')
                success = data.get('success', True)
                
                if agent_id:
                    # Notificar al sistema de simulación que el comando fue confirmado
                    from .agent_system import _receive_agent_confirmation
                    _receive_agent_confirmation(self.simulation_id, agent_id)
                    
                    await self.send(text_data=json.dumps({
                        'type': 'confirmation_received',
                        'agent_id': agent_id,
                        'command_id': command_id,
                        'success': success
                    }))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Formato JSON inválido'
            }))
    
    # Handler para mensajes del grupo
    async def simulation_update(self, event):
        """Envía actualización de la simulación al cliente"""
        await self.send(text_data=json.dumps(event['data']))
    
    async def simulation_status(self, event):
        """Envía estado de la simulación al cliente"""
        await self.send(text_data=json.dumps(event['data']))
    
    async def simulation_error(self, event):
        """Envía error de la simulación al cliente"""
        await self.send(text_data=json.dumps(event['data']))
    
    @database_sync_to_async
    def get_simulation(self, simulation_id):
        """Obtiene la simulación de la base de datos"""
        return get_object_or_404(Simulation, id=simulation_id)
    
    async def send_simulation_status(self, simulation):
        """Envía el estado actual de la simulación"""
        from .serializers import SimulationSerializer
        
        serializer = SimulationSerializer(simulation)
        await self.send(text_data=json.dumps({
            'type': 'simulation_status',
            'data': serializer.data
        }))
