from django.contrib import admin
from .models import World, WorldTemplate


@admin.register(WorldTemplate)
class WorldTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'width', 'height', 'min_fields', 'min_roads', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name']
    readonly_fields = ['created_at']


@admin.register(World)
class WorldAdmin(admin.ModelAdmin):
    list_display = ['name', 'width', 'height', 'seed', 'template', 'created_at']
    list_filter = ['created_at', 'template']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ['grid', 'crop_grid', 'infestation_grid']
        return self.readonly_fields
