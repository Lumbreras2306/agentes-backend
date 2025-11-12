from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WorldViewSet, WorldTemplateViewSet

router = DefaultRouter()
router.register(r'worlds', WorldViewSet, basename='world')
router.register(r'templates', WorldTemplateViewSet, basename='worldtemplate')

urlpatterns = [
    path('', include(router.urls)),
]
