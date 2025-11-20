from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AgentViewSet, SimulationViewSet, BlackboardViewSet

router = DefaultRouter()
router.register(r'agents', AgentViewSet, basename='agent')
router.register(r'simulations', SimulationViewSet, basename='simulation')
router.register(r'blackboard', BlackboardViewSet, basename='blackboard')

urlpatterns = [
    path('', include(router.urls)),
]

