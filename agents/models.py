from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


class TaskStatus(models.TextChoices):
    """Estados de una tarea en el blackboard"""
    PENDING = 'pending', 'Pendiente'
    ASSIGNED = 'assigned', 'Asignada'
    IN_PROGRESS = 'in_progress', 'En Progreso'
    COMPLETED = 'completed', 'Completada'
    FAILED = 'failed', 'Fallida'


class TaskPriority(models.TextChoices):
    """Prioridades de tareas"""
    LOW = 'low', 'Baja'
    MEDIUM = 'medium', 'Media'
    HIGH = 'high', 'Alta'
    CRITICAL = 'critical', 'Crítica'


class BlackboardTask(models.Model):
    """
    Representa una tarea en el blackboard que los agentes pueden ver y tomar.
    Las tareas representan campos que necesitan fumigación.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Referencia al mundo y posición del campo
    world = models.ForeignKey('world.World', on_delete=models.CASCADE, related_name='tasks')
    position_x = models.IntegerField(help_text="Coordenada X del campo a fumigar")
    position_z = models.IntegerField(help_text="Coordenada Z del campo a fumigar")
    
    # Información de la tarea
    infestation_level = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Nivel de infestación del campo (0-100)"
    )
    priority = models.CharField(
        max_length=20,
        choices=TaskPriority.choices,
        default=TaskPriority.MEDIUM
    )
    status = models.CharField(
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING
    )
    
    # Asignación
    assigned_agent_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="ID del agente asignado (de AgentPy)"
    )
    
    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, help_text="Información adicional de la tarea")
    
    class Meta:
        ordering = ['-priority', '-infestation_level', 'created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['world', 'status']),
        ]
    
    def __str__(self):
        return f"Tarea {self.id} - Campo ({self.position_x}, {self.position_z}) - Infestación: {self.infestation_level}%"


class BlackboardEntry(models.Model):
    """
    Entradas generales en el blackboard para comunicación entre agentes.
    Permite que los agentes compartan información y coordinen acciones.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Referencia al mundo
    world = models.ForeignKey('world.World', on_delete=models.CASCADE, related_name='blackboard_entries')
    
    # Información de la entrada
    entry_type = models.CharField(
        max_length=50,
        help_text="Tipo de entrada (ej: 'field_discovered', 'agent_status', 'coordination')"
    )
    content = models.JSONField(default=dict, help_text="Contenido de la entrada")
    
    # Autor
    agent_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="ID del agente que creó la entrada"
    )
    
    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Cuándo expira esta entrada")
    is_active = models.BooleanField(default=True, help_text="Si la entrada está activa")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['world', 'entry_type', 'is_active']),
            models.Index(fields=['agent_id', 'is_active']),
        ]
    
    def __str__(self):
        return f"Entrada {self.entry_type} - Agente {self.agent_id or 'Sistema'}"


class AgentType(models.TextChoices):
    """Tipos de agentes disponibles"""
    FUMIGATOR = 'fumigator', 'Fumigador'
    SCOUT = 'scout', 'Explorador'


class Agent(models.Model):
    """
    Representa un agente en una simulación.
    Los agentes reales viven en AgentPy, pero este modelo rastrea su estado en Django.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="ID único del agente en AgentPy"
    )
    
    # Referencia al mundo
    world = models.ForeignKey('world.World', on_delete=models.CASCADE, related_name='agents')
    
    # Tipo y estado
    agent_type = models.CharField(
        max_length=20,
        choices=AgentType.choices,
        default=AgentType.FUMIGATOR
    )
    is_active = models.BooleanField(default=True)
    
    # Posición actual
    position_x = models.IntegerField(null=True, blank=True)
    position_z = models.IntegerField(null=True, blank=True)
    
    # Estado del agente
    status = models.CharField(
        max_length=50,
        default='idle',
        help_text="Estado actual del agente (idle, moving, fumigating, etc.)"
    )
    
    # Estadísticas
    tasks_completed = models.IntegerField(default=0)
    fields_fumigated = models.IntegerField(default=0)
    
    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(default=dict, help_text="Información adicional del agente")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['world', 'is_active']),
            models.Index(fields=['agent_id']),
        ]
    
    def __str__(self):
        return f"Agente {self.agent_id} ({self.agent_type}) - Mundo {self.world.name}"


class Simulation(models.Model):
    """
    Representa una simulación completa de agentes fumigando campos.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Referencia al mundo
    world = models.ForeignKey('world.World', on_delete=models.CASCADE, related_name='simulations')
    
    # Configuración
    num_agents = models.IntegerField(default=6, help_text="Número total de agentes en la simulación")
    num_fumigators = models.IntegerField(default=5, help_text="Número de agentes fumigadores")
    num_scouts = models.IntegerField(default=1, help_text="Número de agentes scouts")
    max_steps = models.IntegerField(default=300, help_text="Número máximo de pasos de simulación")
    
    # Estado
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pendiente'),
            ('running', 'Ejecutándose'),
            ('completed', 'Completada'),
            ('failed', 'Fallida'),
        ],
        default='pending'
    )
    
    # Resultados
    steps_executed = models.IntegerField(default=0)
    tasks_completed = models.IntegerField(default=0)
    fields_fumigated = models.IntegerField(default=0)
    
    # Metadatos
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    results = models.JSONField(default=dict, help_text="Resultados detallados de la simulación")
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Simulación {self.id} - Mundo {self.world.name} - {self.status}"


class SimulationStats(models.Model):
    """
    Estadísticas detalladas de una simulación completada.
    Almacena métricas relevantes para análisis y visualización.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relación con la simulación (OneToOne)
    simulation = models.OneToOneField(
        Simulation,
        on_delete=models.CASCADE,
        related_name='stats',
        help_text="Simulación asociada"
    )
    
    # Duración y tiempo
    duration_seconds = models.FloatField(
        null=True,
        blank=True,
        help_text="Duración total de la simulación en segundos"
    )
    
    # Eficiencia
    efficiency_score = models.FloatField(
        null=True,
        blank=True,
        help_text="Eficiencia: campos fumigados por paso"
    )
    tasks_per_step = models.FloatField(
        null=True,
        blank=True,
        help_text="Tareas completadas por paso"
    )
    
    # Tasa de éxito
    success_rate = models.FloatField(
        null=True,
        blank=True,
        help_text="Porcentaje de tareas completadas (0-100)"
    )
    completion_percentage = models.FloatField(
        null=True,
        blank=True,
        help_text="Porcentaje de campos fumigados (0-100)"
    )
    
    # Estadísticas de infestación
    initial_infested_fields = models.IntegerField(
        default=0,
        help_text="Número de campos con infestación al inicio"
    )
    final_infested_fields = models.IntegerField(
        default=0,
        help_text="Número de campos con infestación al final"
    )
    infestation_reduction_percentage = models.FloatField(
        null=True,
        blank=True,
        help_text="Porcentaje de reducción de infestación (0-100)"
    )
    average_initial_infestation = models.FloatField(
        null=True,
        blank=True,
        help_text="Nivel promedio de infestación inicial"
    )
    average_final_infestation = models.FloatField(
        null=True,
        blank=True,
        help_text="Nivel promedio de infestación final"
    )
    
    # Estadísticas por agente
    avg_tasks_per_agent = models.FloatField(
        null=True,
        blank=True,
        help_text="Promedio de tareas completadas por agente"
    )
    avg_fields_per_agent = models.FloatField(
        null=True,
        blank=True,
        help_text="Promedio de campos fumigados por agente"
    )
    max_tasks_by_agent = models.IntegerField(
        default=0,
        help_text="Máximo de tareas completadas por un solo agente"
    )
    min_tasks_by_agent = models.IntegerField(
        default=0,
        help_text="Mínimo de tareas completadas por un solo agente"
    )
    
    # Tiempo promedio
    avg_time_per_task = models.FloatField(
        null=True,
        blank=True,
        help_text="Tiempo promedio por tarea en segundos"
    )
    
    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(
        default=dict,
        help_text="Información adicional y estadísticas detalladas"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Estadísticas de Simulación'
        verbose_name_plural = 'Estadísticas de Simulaciones'
        indexes = [
            models.Index(fields=['simulation']),
        ]
    
    def __str__(self):
        return f"Stats de Simulación {self.simulation.id} - Eficiencia: {self.efficiency_score:.2f}"
