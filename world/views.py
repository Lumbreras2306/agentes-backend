from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import World, WorldTemplate
from .serializers import (
    WorldListSerializer,
    WorldDetailSerializer,
    WorldGenerateSerializer,
    WorldTemplateSerializer
)
from .world_generator import WorldGenerator


class WorldTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet para templates de generación"""
    queryset = WorldTemplate.objects.all()
    serializer_class = WorldTemplateSerializer


class WorldViewSet(viewsets.ModelViewSet):
    """ViewSet para mundos generados"""
    queryset = World.objects.all()
    
    def get_serializer_class(self):
        if self.action == 'list':
            return WorldListSerializer
        elif self.action == 'generate':
            return WorldGenerateSerializer
        return WorldDetailSerializer
    
    @action(detail=False, methods=['post'])
    def generate(self, request):
        """
        Genera un nuevo mundo
        
        POST /api/worlds/generate/
        {
            "name": "Mi Granja",
            "width": 30,
            "height": 30,
            "seed": 42,
            "template_id": 1
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        world = serializer.save()
        
        output_serializer = WorldDetailSerializer(world)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def regenerate(self, request, pk=None):
        """
        Regenera un mundo existente con nueva seed
        
        POST /api/worlds/{id}/regenerate/
        {
            "seed": 123
        }
        """
        world = self.get_object()
        new_seed = request.data.get('seed')
        
        # Usar parámetros del template o defaults
        if world.template:
            gen_params = {
                'road_branch_chance': world.template.road_branch_chance,
                'max_road_length': world.template.max_road_length,
                'field_chance': world.template.field_chance,
                'field_growth_chance': world.template.field_growth_chance,
                'min_fields': world.template.min_fields,
                'min_roads': world.template.min_roads,
                'max_attempts': world.template.max_attempts,
            }
        else:
            gen_params = {
                'road_branch_chance': 0.6,
                'max_road_length': 10,
                'field_chance': 0.9,
                'field_growth_chance': 0.55,
                'min_fields': 5,
                'min_roads': 10,
                'max_attempts': 20,
            }
        
        generator = WorldGenerator(width=world.width, height=world.height, seed=new_seed)
        success = generator.generate(**gen_params)
        
        if not success:
            return Response(
                {'error': 'No se pudo regenerar el mundo'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        world_data = generator.export()
        world.seed = new_seed
        world.grid = world_data['grid']
        world.crop_grid = world_data['crop_grid']
        world.infestation_grid = world_data['infestation_grid']
        world.metadata = {
            'legend': world_data['legend'],
            'stats': world_data['stats']
        }
        world.save()
        
        serializer = WorldDetailSerializer(world)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """
        Obtiene estadísticas del mundo
        
        GET /api/worlds/{id}/stats/
        """
        world = self.get_object()
        return Response(world.metadata.get('stats', {}))
    
    @action(detail=True, methods=['get'])
    def grid_only(self, request, pk=None):
        """
        Retorna solo los grids sin metadata
        
        GET /api/worlds/{id}/grid_only/
        """
        world = self.get_object()
        return Response({
            'width': world.width,
            'height': world.height,
            'grid': world.grid,
            'crop_grid': world.crop_grid,
            'infestation_grid': world.infestation_grid
        })
