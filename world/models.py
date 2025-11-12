from django.db import models
import uuid


class WorldTemplate(models.Model):
    """Plantilla de configuración para generar mundos"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    width = models.IntegerField(default=20)
    height = models.IntegerField(default=20)
    road_branch_chance = models.FloatField(default=0.6)
    max_road_length = models.IntegerField(default=10)
    field_chance = models.FloatField(default=0.9)
    field_growth_chance = models.FloatField(default=0.55)
    min_fields = models.IntegerField(default=5)
    min_roads = models.IntegerField(default=10)
    max_attempts = models.IntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class World(models.Model):
    """Mundo generado con su grid 2D"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    template = models.ForeignKey(WorldTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    width = models.IntegerField()
    height = models.IntegerField()
    grid = models.JSONField()
    crop_grid = models.JSONField()
    infestation_grid = models.JSONField()
    seed = models.IntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.width}x{self.height})"
