from django.contrib import admin
from .models import Agent, Simulation, BlackboardTask, BlackboardEntry


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ['agent_id', 'world', 'agent_type', 'status', 'position_x', 
                    'position_z', 'tasks_completed', 'fields_fumigated', 'is_active']
    list_filter = ['agent_type', 'status', 'is_active', 'world', 'created_at']
    search_fields = ['agent_id', 'world__name']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(Simulation)
class SimulationAdmin(admin.ModelAdmin):
    list_display = ['id', 'world', 'num_agents', 'status', 'steps_executed', 
                    'tasks_completed', 'fields_fumigated', 'created_at']
    list_filter = ['status', 'world', 'created_at']
    search_fields = ['id', 'world__name']
    readonly_fields = ['id', 'created_at', 'started_at', 'completed_at']


@admin.register(BlackboardTask)
class BlackboardTaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'world', 'position_x', 'position_z', 'infestation_level', 
                    'priority', 'status', 'assigned_agent_id', 'created_at']
    list_filter = ['status', 'priority', 'world', 'created_at']
    search_fields = ['id', 'assigned_agent_id', 'world__name']
    readonly_fields = ['id', 'created_at', 'assigned_at', 'completed_at']


@admin.register(BlackboardEntry)
class BlackboardEntryAdmin(admin.ModelAdmin):
    list_display = ['id', 'world', 'entry_type', 'agent_id', 'is_active', 'created_at']
    list_filter = ['entry_type', 'is_active', 'world', 'created_at']
    search_fields = ['id', 'agent_id', 'entry_type', 'world__name']
    readonly_fields = ['id', 'created_at']
