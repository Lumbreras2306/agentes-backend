"""
Servicios para interactuar con el blackboard.
Proporciona una interfaz limpia para que los agentes lean y escriban en el blackboard.
"""
from typing import List, Optional, Dict, Any
from django.db import models
from django.utils import timezone
from .models import BlackboardTask, BlackboardEntry, TaskStatus, TaskPriority


class BlackboardService:
    """Servicio para gestionar el blackboard"""
    
    def __init__(self, world):
        """
        Inicializa el servicio para un mundo específico.
        
        Args:
            world: Instancia del modelo World
        """
        self.world = world
    
    # ========== TAREAS ==========
    
    def create_task(
        self,
        position_x: int,
        position_z: int,
        infestation_level: int,
        priority: str = TaskPriority.MEDIUM,
        metadata: Optional[Dict] = None
    ) -> BlackboardTask:
        """
        Crea una nueva tarea en el blackboard.
        
        Args:
            position_x: Coordenada X del campo
            position_z: Coordenada Z del campo
            infestation_level: Nivel de infestación (0-100)
            priority: Prioridad de la tarea
            metadata: Metadatos adicionales
        
        Returns:
            BlackboardTask creada
        """
        # Determinar prioridad automáticamente si no se especifica
        if priority == TaskPriority.MEDIUM:
            if infestation_level >= 80:
                priority = TaskPriority.CRITICAL
            elif infestation_level >= 50:
                priority = TaskPriority.HIGH
            elif infestation_level >= 20:
                priority = TaskPriority.MEDIUM
            else:
                priority = TaskPriority.LOW
        
        task = BlackboardTask.objects.create(
            world=self.world,
            position_x=position_x,
            position_z=position_z,
            infestation_level=infestation_level,
            priority=priority,
            status=TaskStatus.PENDING,
            metadata=metadata or {}
        )
        return task
    
    def get_available_tasks(
        self,
        limit: Optional[int] = None,
        min_priority: Optional[str] = None
    ) -> List[BlackboardTask]:
        """
        Obtiene tareas disponibles (pendientes) ordenadas por prioridad.
        
        Args:
            limit: Número máximo de tareas a retornar
            min_priority: Prioridad mínima a considerar
        
        Returns:
            Lista de tareas disponibles
        """
        queryset = BlackboardTask.objects.filter(
            world=self.world,
            status=TaskStatus.PENDING
        )
        
        if min_priority:
            priority_order = [p[0] for p in TaskPriority.choices]
            if min_priority in priority_order:
                min_index = priority_order.index(min_priority)
                allowed_priorities = priority_order[min_index:]
                queryset = queryset.filter(priority__in=allowed_priorities)
        
        queryset = queryset.order_by('-priority', '-infestation_level', 'created_at')
        
        if limit:
            queryset = queryset[:limit]
        
        return list(queryset)
    
    def assign_task(self, task: BlackboardTask, agent_id: str) -> bool:
        """
        Asigna una tarea a un agente.
        
        Args:
            task: Tarea a asignar
            agent_id: ID del agente
        
        Returns:
            True si se asignó exitosamente, False si ya estaba asignada
        """
        if task.status != TaskStatus.PENDING:
            return False
        
        task.status = TaskStatus.ASSIGNED
        task.assigned_agent_id = agent_id
        task.assigned_at = timezone.now()
        task.save()
        return True
    
    def start_task(self, task: BlackboardTask) -> bool:
        """
        Marca una tarea como en progreso.
        
        Args:
            task: Tarea a iniciar
        
        Returns:
            True si se inició exitosamente
        """
        if task.status not in [TaskStatus.ASSIGNED, TaskStatus.PENDING]:
            return False
        
        task.status = TaskStatus.IN_PROGRESS
        task.save()
        return True
    
    def complete_task(self, task: BlackboardTask) -> bool:
        """
        Marca una tarea como completada.
        
        Args:
            task: Tarea a completar
        
        Returns:
            True si se completó exitosamente
        """
        if task.status != TaskStatus.IN_PROGRESS:
            return False
        
        task.status = TaskStatus.COMPLETED
        task.completed_at = timezone.now()
        task.save()
        return True
    
    def get_task_by_position(self, position_x: int, position_z: int) -> Optional[BlackboardTask]:
        """
        Obtiene una tarea por su posición.
        
        Args:
            position_x: Coordenada X
            position_z: Coordenada Z
        
        Returns:
            BlackboardTask o None si no existe
        """
        try:
            return BlackboardTask.objects.get(
                world=self.world,
                position_x=position_x,
                position_z=position_z,
                status__in=[TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS]
            )
        except BlackboardTask.DoesNotExist:
            return None
    
    # ========== ENTRADAS DEL BLACKBOARD ==========
    
    def create_entry(
        self,
        entry_type: str,
        content: Dict[str, Any],
        agent_id: Optional[str] = None,
        expires_at: Optional[timezone.datetime] = None
    ) -> BlackboardEntry:
        """
        Crea una nueva entrada en el blackboard.
        
        Args:
            entry_type: Tipo de entrada
            content: Contenido de la entrada
            agent_id: ID del agente que crea la entrada
            expires_at: Cuándo expira la entrada
        
        Returns:
            BlackboardEntry creada
        """
        entry = BlackboardEntry.objects.create(
            world=self.world,
            entry_type=entry_type,
            content=content,
            agent_id=agent_id,
            expires_at=expires_at,
            is_active=True
        )
        return entry
    
    def get_active_entries(
        self,
        entry_type: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[BlackboardEntry]:
        """
        Obtiene entradas activas del blackboard.
        
        Args:
            entry_type: Filtrar por tipo de entrada
            agent_id: Filtrar por agente
            limit: Número máximo de entradas
        
        Returns:
            Lista de entradas activas
        """
        queryset = BlackboardEntry.objects.filter(
            world=self.world,
            is_active=True
        )
        
        # Filtrar por expiración
        now = timezone.now()
        queryset = queryset.filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
        )
        
        if entry_type:
            queryset = queryset.filter(entry_type=entry_type)
        
        if agent_id:
            queryset = queryset.filter(agent_id=agent_id)
        
        queryset = queryset.order_by('-created_at')
        
        if limit:
            queryset = queryset[:limit]
        
        return list(queryset)
    
    def deactivate_entry(self, entry: BlackboardEntry) -> None:
        """
        Desactiva una entrada del blackboard.
        
        Args:
            entry: Entrada a desactivar
        """
        entry.is_active = False
        entry.save()
    
    # ========== MÉTODOS DE UTILIDAD ==========
    
    def initialize_tasks_from_world(self, min_infestation: int = 0) -> int:
        """
        Inicializa tareas en el blackboard basándose en el infestation_grid del mundo.
        
        Args:
            min_infestation: Nivel mínimo de infestación para crear una tarea
        
        Returns:
            Número de tareas creadas
        """
        infestation_grid = self.world.infestation_grid
        grid = self.world.grid
        tasks_created = 0
        
        for z in range(self.world.height):
            for x in range(self.world.width):
                # Solo crear tareas para campos (FIELD) con infestación
                if grid[z][x] == 2:  # TileType.FIELD
                    infestation = infestation_grid[z][x]
                    if infestation >= min_infestation:
                        # Verificar si ya existe una tarea para esta posición
                        existing_task = self.get_task_by_position(x, z)
                        if not existing_task:
                            self.create_task(
                                position_x=x,
                                position_z=z,
                                infestation_level=infestation,
                                metadata={'crop_type': self.world.crop_grid[z][x]}
                            )
                            tasks_created += 1
        
        return tasks_created

