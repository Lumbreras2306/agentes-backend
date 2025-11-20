from rest_framework import serializers
from .models import Agent, Simulation, AgentType
from .models import BlackboardTask, BlackboardEntry


class AgentSerializer(serializers.ModelSerializer):
    """Serializer para el modelo Agent"""
    agent_type_display = serializers.CharField(source='get_agent_type_display', read_only=True)
    
    class Meta:
        model = Agent
        fields = [
            'id', 'agent_id', 'world', 'agent_type', 'agent_type_display',
            'is_active', 'position_x', 'position_z', 'status',
            'tasks_completed', 'fields_fumigated', 'created_at', 'updated_at', 'metadata'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SimulationSerializer(serializers.ModelSerializer):
    """Serializer para el modelo Simulation"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    world_name = serializers.CharField(source='world.name', read_only=True)
    
    class Meta:
        model = Simulation
        fields = [
            'id', 'world', 'world_name', 'num_agents', 'num_fumigators', 'num_scouts',
            'max_steps', 'status', 'status_display', 'steps_executed', 'tasks_completed',
            'fields_fumigated', 'started_at', 'completed_at', 'created_at', 'results'
        ]
        read_only_fields = [
            'id', 'status', 'steps_executed', 'tasks_completed',
            'fields_fumigated', 'started_at', 'completed_at', 'created_at', 'results'
        ]


class SimulationCreateSerializer(serializers.Serializer):
    """Serializer para crear una nueva simulación"""
    world_id = serializers.UUIDField(required=True)
    num_fumigators = serializers.IntegerField(default=3, min_value=1, max_value=10)
    num_scouts = serializers.IntegerField(default=2, min_value=1, max_value=10)
    max_steps = serializers.IntegerField(default=1000, min_value=1, max_value=10000)
    min_infestation = serializers.IntegerField(default=10, min_value=0, max_value=100)


class BlackboardTaskSerializer(serializers.ModelSerializer):
    """Serializer para tareas del blackboard"""
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = BlackboardTask
        fields = [
            'id', 'world', 'position_x', 'position_z', 'infestation_level',
            'priority', 'priority_display', 'status', 'status_display',
            'assigned_agent_id', 'created_at', 'assigned_at', 'completed_at', 'metadata'
        ]
        read_only_fields = ['id', 'created_at', 'assigned_at', 'completed_at']


class BlackboardEntrySerializer(serializers.ModelSerializer):
    """Serializer para entradas del blackboard"""
    
    class Meta:
        model = BlackboardEntry
        fields = [
            'id', 'world', 'entry_type', 'content', 'agent_id',
            'created_at', 'expires_at', 'is_active'
        ]
        read_only_fields = ['id', 'created_at']

