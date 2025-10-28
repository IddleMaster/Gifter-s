from django.utils import timezone
from django.db.models import Q, Count
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notificacion, NotificationDevice, PreferenciasUsuario
from .serializers import (
    NotificacionSerializer,
    NotificacionCreateSerializer,
    DeviceSerializer,
    PreferenciasSerializer,
)

# --- Tus vistas ---
class NotificacionListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificacionSerializer

    def get_queryset(self):
        return Notificacion.objects.filter(usuario=self.request.user).order_by('-creada_en')

    def get_serializer_class(self):
        return NotificacionCreateSerializer if self.request.method == 'POST' else NotificacionSerializer

class NotificacionDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificacionSerializer
    lookup_url_kwarg = 'notificacion_id'
    lookup_field = 'notificacion_id'

    def get_queryset(self):
        return Notificacion.objects.filter(usuario=self.request.user)

class MarkAllReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        qs = Notificacion.objects.filter(usuario=request.user, leida=False)
        qs.update(leida=True, leida_en=timezone.now())
        return Response({"updated": qs.count()})

class SummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        total = Notificacion.objects.filter(usuario=request.user, leida=False).count()
        return Response({"total": total})