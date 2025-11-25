from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
import numpy as np
from io import BytesIO
from PIL import Image

from .models import World, WorldTemplate
from .serializers import (
    WorldListSerializer,
    WorldDetailSerializer,
    WorldGenerateSerializer,
    WorldTemplateSerializer
)
from .world_generator import WorldGenerator, TileType, CropType
from .renderers import PNGRenderer, GIFRenderer
from .pathfinding import Pathfinder


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
                'field_growth_rounds': getattr(world.template, 'field_growth_rounds', 10),
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
                'field_growth_rounds': 10,
                'min_fields': 5,
                'min_roads': 10,
                'max_attempts': 30,
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
    
    @action(detail=True, methods=['get'], renderer_classes=[PNGRenderer])
    def visualize(self, request, pk=None):
        """
        Genera una visualización del mundo como imagen PNG
        
        GET /api/worlds/{id}/visualize/
        GET /api/worlds/{id}/visualize/?layer=crop
        GET /api/worlds/{id}/visualize/?layer=infestation
        
        Parámetros:
        - layer: 'tile' (default), 'crop', 'infestation'
        """
        world = self.get_object()
        layer = request.query_params.get('layer', 'tile')
        
        # Configurar colores según el layer
        if layer == 'crop':
            grid_data = world.crop_grid
            colors = {
                int(CropType.NONE): '#1a1a1a',      # Negro para vacío
                int(CropType.WHEAT): '#f4e04d',     # Amarillo para trigo
                int(CropType.CORN): '#95d840',      # Verde claro para maíz
                int(CropType.SOY): '#7eb26d',       # Verde oscuro para soya
            }
            legend_labels = {
                int(CropType.NONE): 'Vacío',
                int(CropType.WHEAT): 'Trigo',
                int(CropType.CORN): 'Maíz',
                int(CropType.SOY): 'Soya',
            }
            title = f'{world.name} - Cultivos'
        elif layer == 'infestation':
            grid_data = world.infestation_grid
            # Para infestación usamos escala de grises/colores
            fig, ax = plt.subplots(figsize=(12, 12))
            im = ax.imshow(grid_data, cmap='RdYlGn_r', interpolation='nearest', vmin=0, vmax=100)
            ax.set_title(f'{world.name} - Nivel de Infestación', fontsize=16, fontweight='bold')
            ax.set_xlabel('X', fontsize=12)
            ax.set_ylabel('Z', fontsize=12)
            ax.grid(True, alpha=0.3)
            
            # Colorbar
            cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            cbar.set_label('Infestación (%)', rotation=270, labelpad=20, fontsize=12)
            
            # Guardar en buffer
            buffer = BytesIO()
            plt.tight_layout()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            image_data = buffer.getvalue()
            plt.close()
            buffer.close()
            
            return HttpResponse(image_data, content_type='image/png')
        else:  # tile (default)
            grid_data = world.grid
            colors = {
                int(TileType.IMPASSABLE): '#2d2d2d',  # Gris oscuro
                int(TileType.ROAD): '#8b7355',        # Café para camino
                int(TileType.FIELD): '#7ec850',       # Verde para campo
                int(TileType.BARN): '#c44536',        # Rojo para granero
            }
            legend_labels = {
                int(TileType.IMPASSABLE): 'Intransitable',
                int(TileType.ROAD): 'Camino',
                int(TileType.FIELD): 'Campo',
                int(TileType.BARN): 'Granero',
            }
            title = f'{world.name} - Terreno'
        
        # Crear la visualización (para tile y crop)
        if layer != 'infestation':
            fig, ax = plt.subplots(figsize=(12, 12))
            
            # Crear matriz de colores RGB (convertir hex a RGB)
            def hex_to_rgb(hex_color):
                """Convierte color hexadecimal a RGB normalizado (0-1)"""
                hex_color = hex_color.lstrip('#')
                return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))
            
            # Convertir grid a matriz RGB
            height = len(grid_data)
            width = len(grid_data[0]) if grid_data else 0
            rgb_grid = np.zeros((height, width, 3))
            
            for i, row in enumerate(grid_data):
                for j, cell in enumerate(row):
                    # Asegurar que cell sea un entero para la comparación
                    cell_value = int(cell) if cell is not None else 0
                    hex_color = colors.get(cell_value, '#000000')
                    rgb_grid[i, j] = hex_to_rgb(hex_color)
            
            # Mostrar la imagen
            ax.imshow(rgb_grid, interpolation='nearest')
            ax.set_title(title, fontsize=16, fontweight='bold')
            ax.set_xlabel('X', fontsize=12)
            ax.set_ylabel('Z', fontsize=12)
            ax.grid(True, alpha=0.3, color='white', linewidth=0.5)
            
            # Agregar leyenda
            patches = [mpatches.Patch(color=color, label=legend_labels[key]) 
                      for key, color in colors.items()]
            ax.legend(handles=patches, loc='upper left', bbox_to_anchor=(1, 1), 
                     fontsize=10, framealpha=0.9)
            
            # Guardar en buffer
            buffer = BytesIO()
            plt.tight_layout()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            image_data = buffer.getvalue()
            plt.close()
            buffer.close()
            
            return HttpResponse(image_data, content_type='image/png')
    
    @action(detail=True, methods=['get'], renderer_classes=[PNGRenderer])
    def visualize_combined(self, request, pk=None):
        """
        Genera una visualización combinada con los 3 layers
        
        GET /api/worlds/{id}/visualize_combined/
        """
        world = self.get_object()
        
        fig, axes = plt.subplots(1, 3, figsize=(20, 7))
        
        # Layer 1: Terreno
        tile_colors = {
            int(TileType.IMPASSABLE): '#2d2d2d',
            int(TileType.ROAD): '#8b7355',
            int(TileType.FIELD): '#7ec850',
            int(TileType.BARN): '#c44536',
        }
        tile_labels = {
            int(TileType.IMPASSABLE): 'Intransitable',
            int(TileType.ROAD): 'Camino',
            int(TileType.FIELD): 'Campo',
            int(TileType.BARN): 'Granero',
        }
        # Convertir tile_grid a RGB
        def hex_to_rgb(hex_color):
            """Convierte color hexadecimal a RGB normalizado (0-1)"""
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))
        
        height = len(world.grid)
        width = len(world.grid[0]) if world.grid else 0
        tile_rgb = np.zeros((height, width, 3))
        for i, row in enumerate(world.grid):
            for j, cell in enumerate(row):
                # Asegurar que cell sea un entero para la comparación
                cell_value = int(cell) if cell is not None else 0
                hex_color = tile_colors.get(cell_value, '#000000')
                tile_rgb[i, j] = hex_to_rgb(hex_color)
        
        axes[0].imshow(tile_rgb, interpolation='nearest')
        axes[0].set_title('Terreno', fontsize=14, fontweight='bold')
        axes[0].set_xlabel('X')
        axes[0].set_ylabel('Z')
        axes[0].grid(True, alpha=0.3, color='white', linewidth=0.5)
        patches = [mpatches.Patch(color=color, label=tile_labels[key]) 
                  for key, color in tile_colors.items()]
        axes[0].legend(handles=patches, loc='upper left', fontsize=8)
        
        # Layer 2: Cultivos
        crop_colors = {
            int(CropType.NONE): '#1a1a1a',
            int(CropType.WHEAT): '#f4e04d',
            int(CropType.CORN): '#95d840',
            int(CropType.SOY): '#7eb26d',
        }
        crop_labels = {
            int(CropType.NONE): 'Vacío',
            int(CropType.WHEAT): 'Trigo',
            int(CropType.CORN): 'Maíz',
            int(CropType.SOY): 'Soya',
        }
        # Convertir crop_grid a RGB
        crop_rgb = np.zeros((height, width, 3))
        for i, row in enumerate(world.crop_grid):
            for j, cell in enumerate(row):
                # Asegurar que cell sea un entero para la comparación
                cell_value = int(cell) if cell is not None else 0
                hex_color = crop_colors.get(cell_value, '#000000')
                crop_rgb[i, j] = hex_to_rgb(hex_color)
        
        axes[1].imshow(crop_rgb, interpolation='nearest')
        axes[1].set_title('Cultivos', fontsize=14, fontweight='bold')
        axes[1].set_xlabel('X')
        axes[1].set_ylabel('Z')
        axes[1].grid(True, alpha=0.3, color='white', linewidth=0.5)
        patches = [mpatches.Patch(color=color, label=crop_labels[key]) 
                  for key, color in crop_colors.items()]
        axes[1].legend(handles=patches, loc='upper left', fontsize=8)
        
        # Layer 3: Infestación
        im = axes[2].imshow(world.infestation_grid, cmap='RdYlGn_r', 
                           interpolation='nearest', vmin=0, vmax=100)
        axes[2].set_title('Infestación', fontsize=14, fontweight='bold')
        axes[2].set_xlabel('X')
        axes[2].set_ylabel('Z')
        axes[2].grid(True, alpha=0.3)
        cbar = plt.colorbar(im, ax=axes[2], fraction=0.046, pad=0.04)
        cbar.set_label('%', rotation=0, labelpad=10)
        
        # Título general
        fig.suptitle(f'{world.name} ({world.width}x{world.height})', 
                    fontsize=16, fontweight='bold')
        
        # Guardar en buffer
        buffer = BytesIO()
        plt.tight_layout()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        image_data = buffer.getvalue()
        plt.close()
        buffer.close()
        
        return HttpResponse(image_data, content_type='image/png')
    
    @action(detail=True, methods=['get'])
    def visualize_dijkstra_animated(self, request, pk=None):
        """
        Retorna datos JSON para animación de múltiples tractores y un dron moviéndose a puntos infestados.
        El frontend se encarga de generar la animación.
        
        GET /api/worlds/{id}/visualize_dijkstra_animated/
        GET /api/worlds/{id}/visualize_dijkstra_animated/?tractors=3
        Parámetros:
        - tractors: Número de tractores (default: 3, rango: 1-5)
        
        Returns:
        JSON con:
        - grid: Grid del mundo
        - width, height: Dimensiones del mundo
        - barn_pos: Posición del granero (x, z)
        - tractor_paths: Lista de caminos, uno por cada tractor
        - destinations: Lista de destinos (x, z), uno por cada tractor
        - simulation_steps: Lista de pasos de simulación (tractores)
        - drone_path: Camino del dron
        - drone_destination: Destino del dron
        - drone_simulation_steps: Pasos de simulación del dron
        - tractor_colors: Lista de colores hex para cada tractor
        - drone_color: Color del dron
        """
        world = self.get_object()
        
        # Obtener número de tractores (máximo 5, uno por celda del granero)
        num_tractors = int(request.query_params.get('tractors', 3))
        num_tractors = max(1, min(5, num_tractors))  # Entre 1 y 5
        
        # Crear pathfinder y encontrar caminos para múltiples tractores a puntos infestados
        pathfinder = Pathfinder(world.grid, world.width, world.height)
        tractor_paths_data = pathfinder.find_paths_to_infested_destinations(
            infestation_grid=world.infestation_grid,
            num_tractors=num_tractors,
            prefer_roads=True
        )
        
        if tractor_paths_data is None or len(tractor_paths_data) == 0:
            return Response(
                {'error': 'No se pudieron encontrar caminos válidos'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Extraer caminos y destinos de tractores
        tractor_paths = [data['path'] for data in tractor_paths_data]
        destinations = [data['end'] for data in tractor_paths_data]
        # Usar la posición central del granero para visualización (primer tractor)
        barn_pos = tractor_paths_data[0]['start']
        
        # Simular movimiento de tractores
        simulation_steps = pathfinder.simulate_tractors(tractor_paths, max_steps=2000)
        
        if not simulation_steps:
            return Response(
                {'error': 'No se pudo simular el movimiento'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Configurar el dron: sobrevuela todo el mapa para analizar infestación
        barn_cells = pathfinder.find_all_barn_cells()
        drone_start = barn_cells[0] if barn_cells else pathfinder.find_barn()
        
        if drone_start is None:
            return Response(
                {'error': 'No se pudo encontrar posición inicial para el dron'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Generar patrón de sobrevuelo para el dron
        drone_path = pathfinder.generate_drone_survey_path(drone_start)
        
        if not drone_path:
            return Response(
                {'error': 'No se pudo generar patrón de sobrevuelo para el dron'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Simular movimiento del dron (más rápido, sin colisiones, revela infestación)
        drone_simulation_steps = pathfinder.simulate_drone(
            drone_path, 
            infestation_grid=world.infestation_grid,
            speed_multiplier=2, 
            max_steps=2000
        )
        
        # El destino del dron es el último punto del sobrevuelo
        drone_destination = drone_path[-1] if drone_path else None
        
        # Colores para cada tractor
        tractor_colors = [
            '#ff0000', '#00ff00', '#0000ff', '#ffff00', '#ff00ff',
            '#00ffff', '#ff8800', '#8800ff', '#88ff00', '#ff0088'
        ]
        
        # Preparar respuesta JSON
        response_data = {
            'grid': world.grid,
            'width': world.width,
            'height': world.height,
            'barn_pos': barn_pos,
            'tractor_paths': tractor_paths,
            'destinations': destinations,
            'simulation_steps': simulation_steps,
            'tractor_colors': tractor_colors[:num_tractors],
            'drone_path': drone_path,
            'drone_destination': drone_destination,
            'drone_simulation_steps': drone_simulation_steps,
            'drone_color': '#00ffff',  # Cyan para el dron
            'infestation_grid': world.infestation_grid,  # Grid completo de infestación
            'tile_colors': {
                'IMPASSABLE': '#2d2d2d',
                'ROAD': '#8b7355',
                'FIELD': '#7ec850',
                'BARN': '#c44536',
            }
        }
        
        return Response(response_data)
