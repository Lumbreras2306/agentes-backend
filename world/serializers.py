from rest_framework import serializers
from .models import World, WorldTemplate
from .world_generator import WorldGenerator


class WorldTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorldTemplate
        fields = '__all__'


class WorldListSerializer(serializers.ModelSerializer):
    """Serializer ligero para listados"""
    field_count = serializers.SerializerMethodField()
    road_count = serializers.SerializerMethodField()
    template_name = serializers.CharField(source='template.name', read_only=True, allow_null=True)
    
    class Meta:
        model = World
        fields = [
            'id', 'name', 'width', 'height', 'seed',
            'field_count', 'road_count', 'template_name',
            'created_at', 'updated_at'
        ]
    
    def get_field_count(self, obj):
        return obj.metadata.get('stats', {}).get('field_count', 0)
    
    def get_road_count(self, obj):
        return obj.metadata.get('stats', {}).get('road_count', 0)


class WorldDetailSerializer(serializers.ModelSerializer):
    """Serializer completo con los grids"""
    template = WorldTemplateSerializer(read_only=True)
    
    class Meta:
        model = World
        fields = '__all__'


class WorldGenerateSerializer(serializers.Serializer):
    """Serializer para generar un nuevo mundo"""
    name = serializers.CharField(max_length=100)
    template_id = serializers.IntegerField(required=False, allow_null=True)
    width = serializers.IntegerField(default=20, min_value=5, max_value=100)
    height = serializers.IntegerField(default=20, min_value=5, max_value=100)
    seed = serializers.IntegerField(required=False, allow_null=True)
    
    # Parámetros opcionales de generación
    road_branch_chance = serializers.FloatField(required=False, min_value=0.0, max_value=1.0)
    max_road_length = serializers.IntegerField(required=False, min_value=1)
    field_chance = serializers.FloatField(required=False, min_value=0.0, max_value=1.0)
    field_growth_chance = serializers.FloatField(required=False, min_value=0.0, max_value=1.0)
    min_fields = serializers.IntegerField(required=False, min_value=0)
    min_roads = serializers.IntegerField(required=False, min_value=0)
    max_attempts = serializers.IntegerField(required=False, min_value=1, max_value=100)
    
    def validate(self, data):
        """Valida que el template exista si se proporciona"""
        template_id = data.get('template_id')
        if template_id:
            try:
                data['template'] = WorldTemplate.objects.get(id=template_id)
            except WorldTemplate.DoesNotExist:
                raise serializers.ValidationError({
                    'template_id': 'Template no encontrado'
                })
        return data
    
    def create(self, validated_data):
        """Genera y guarda el mundo"""
        template = validated_data.pop('template', None)
        name = validated_data.pop('name')
        width = validated_data.pop('width', 20)
        height = validated_data.pop('height', 20)
        seed = validated_data.pop('seed', None)
        
        # Obtener parámetros de generación
        if template:
            gen_params = {
                'road_branch_chance': template.road_branch_chance,
                'max_road_length': template.max_road_length,
                'field_chance': template.field_chance,
                'field_growth_chance': template.field_growth_chance,
                'min_fields': template.min_fields,
                'min_roads': template.min_roads,
                'max_attempts': template.max_attempts,
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
        
        # Override con parámetros explícitos
        gen_params.update({
            k: v for k, v in validated_data.items() 
            if k in gen_params and v is not None
        })
        
        # Generar mundo
        generator = WorldGenerator(width=width, height=height, seed=seed)
        success = generator.generate(**gen_params)
        
        if not success:
            raise serializers.ValidationError(
                'No se pudo generar un mundo válido con los parámetros dados'
            )
        
        # Exportar datos
        world_data = generator.export()
        
        # Guardar en BD
        world = World.objects.create(
            name=name,
            template=template,
            width=width,
            height=height,
            seed=seed,
            grid=world_data['grid'],
            crop_grid=world_data['crop_grid'],
            infestation_grid=world_data['infestation_grid'],
            metadata={
                'legend': world_data['legend'],
                'stats': world_data['stats']
            }
        )
        
        return world
