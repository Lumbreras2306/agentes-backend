from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction

from .models import Agent, Simulation, SimulationStats
from .serializers import (
    AgentSerializer,
    SimulationSerializer,
    SimulationCreateSerializer,
    BlackboardTaskSerializer,
    BlackboardEntrySerializer,
    SimulationStatsSerializer
)
from .simulation.runner import run_simulation_async
from world.models import World
from .models import BlackboardTask, BlackboardEntry
from .services import BlackboardService


class AgentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para ver agentes"""
    queryset = Agent.objects.all()
    serializer_class = AgentSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        world_id = self.request.query_params.get('world_id')
        if world_id:
            queryset = queryset.filter(world_id=world_id)
        return queryset


class SimulationViewSet(viewsets.ModelViewSet):
    """ViewSet para simulaciones"""
    queryset = Simulation.objects.all()
    serializer_class = SimulationSerializer
    
    def get_serializer_class(self):
        if self.action == 'create':
            return SimulationCreateSerializer
        return SimulationSerializer
    
    @transaction.atomic
    def create(self, request):
        """
        Crea y ejecuta una nueva simulación.
        
        POST /api/simulations/
        {
            "world_id": "uuid-del-mundo",
            "num_agents": 3,
            "max_steps": 1000,
            "min_infestation": 10
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        world_id = serializer.validated_data['world_id']
        num_fumigators = serializer.validated_data.get('num_fumigators', 3)
        # Scouts eliminados: forzamos 0 y calculamos agentes solo con fumigadores
        num_scouts = 0
        max_steps = serializer.validated_data.get('max_steps', 1000)
        min_infestation = serializer.validated_data.get('min_infestation', 10)
        
        # Obtener el mundo
        world = get_object_or_404(World, id=world_id)
        
        # Crear la simulación primero (en estado 'running')
        from agents.models import Simulation
        from django.utils import timezone
        
        simulation = Simulation.objects.create(
            world=world,
            num_agents=num_fumigators,
            num_fumigators=num_fumigators,
            num_scouts=num_scouts,
            max_steps=max_steps,
            status='pending',  # Cambiar a 'pending' para que no se inicie automáticamente
            started_at=None  # No iniciar todavía
        )
        
        # Retornar simulación creada (sin iniciar)
        output_serializer = SimulationSerializer(simulation)
        return Response({
            'simulation': output_serializer.data,
            'message': 'Simulación creada. Usa el endpoint /start/ para iniciarla.'
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def agents(self, request, pk=None):
        """
        Obtiene los agentes de una simulación.
        
        GET /api/simulations/{id}/agents/
        """
        simulation = self.get_object()
        agents = Agent.objects.filter(world=simulation.world, is_active=True)
        serializer = AgentSerializer(agents, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def tasks(self, request, pk=None):
        """
        Obtiene las tareas del blackboard para el mundo de la simulación.
        
        GET /api/simulations/{id}/tasks/
        """
        simulation = self.get_object()
        tasks = BlackboardTask.objects.filter(world=simulation.world)
        serializer = BlackboardTaskSerializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """
        Obtiene las estadísticas de una simulación.
        
        GET /api/simulations/{id}/stats/
        """
        simulation = self.get_object()
        
        # Intentar obtener estadísticas existentes
        try:
            stats = simulation.stats
            serializer = SimulationStatsSerializer(stats)
            return Response(serializer.data)
        except SimulationStats.DoesNotExist:
            # Si no existen estadísticas, retornar error 404
            return Response({
                'error': 'No se encontraron estadísticas para esta simulación. La simulación debe estar completada.'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """
        Inicia una simulación que está en estado 'pending'.
        
        POST /api/simulations/{id}/start/
        """
        simulation = self.get_object()
        
        if simulation.status != 'pending':
            return Response({
                'error': f'La simulación ya está en estado "{simulation.status}". Solo se pueden iniciar simulaciones pendientes.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Obtener parámetros de la simulación
        world = simulation.world
        num_fumigators = simulation.num_fumigators
        max_steps = simulation.max_steps
        min_infestation = 10  # Valor por defecto
        
        # Actualizar estado a 'running'
        from django.utils import timezone
        simulation.status = 'running'
        simulation.started_at = timezone.now()
        simulation.save()
        
        # Ejecutar simulación en background usando el nuevo sistema
        run_simulation_async(
            simulation_id=str(simulation.id),
            max_steps=max_steps,
            step_delay=0.5,
            send_updates=True
        )
        
        output_serializer = SimulationSerializer(simulation)
        return Response({
            'simulation': output_serializer.data,
            'message': 'Simulación iniciada. Conéctate al WebSocket para ver actualizaciones en tiempo real.'
        }, status=status.HTTP_200_OK)


class BlackboardViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para interactuar con el blackboard"""
    
    @action(detail=False, methods=['get'], url_path='world/(?P<world_id>[^/.]+)/tasks')
    def world_tasks(self, request, world_id=None):
        """
        Obtiene todas las tareas del blackboard para un mundo.
        
        GET /api/blackboard/world/{world_id}/tasks/
        """
        world = get_object_or_404(World, id=world_id)
        tasks = BlackboardTask.objects.filter(world=world)
        
        # Filtros opcionales
        status_filter = request.query_params.get('status')
        if status_filter:
            tasks = tasks.filter(status=status_filter)
        
        priority_filter = request.query_params.get('priority')
        if priority_filter:
            tasks = tasks.filter(priority=priority_filter)
        
        serializer = BlackboardTaskSerializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='world/(?P<world_id>[^/.]+)/entries')
    def world_entries(self, request, world_id=None):
        """
        Obtiene todas las entradas del blackboard para un mundo.
        
        GET /api/blackboard/world/{world_id}/entries/
        """
        world = get_object_or_404(World, id=world_id)
        entries = BlackboardEntry.objects.filter(world=world, is_active=True)
        
        # Filtros opcionales
        entry_type = request.query_params.get('entry_type')
        if entry_type:
            entries = entries.filter(entry_type=entry_type)
        
        serializer = BlackboardEntrySerializer(entries, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], url_path='world/(?P<world_id>[^/.]+)/initialize-tasks')
    def initialize_tasks(self, request, world_id=None):
        """
        Inicializa tareas en el blackboard basándose en el infestation_grid del mundo.
        
        POST /api/blackboard/world/{world_id}/initialize-tasks/
        {
            "min_infestation": 10
        }
        """
        world = get_object_or_404(World, id=world_id)
        min_infestation = request.data.get('min_infestation', 10)
        
        blackboard_service = BlackboardService(world)
        tasks_created = blackboard_service.initialize_tasks_from_world(min_infestation=min_infestation)
        
        return Response({
            'message': f'Se crearon {tasks_created} tareas en el blackboard',
            'tasks_created': tasks_created
        })
