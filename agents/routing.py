"""
WebSocket routing para simulaciones en tiempo real.
"""
from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/simulations/<uuid:simulation_id>/', consumers.SimulationConsumer.as_asgi()),
]
