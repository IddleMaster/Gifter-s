from django.utils import timezone
from django.db.models import Q, Count
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from core.services.social import fof_con_senales, sugerencias_qs, amigos_qs
from core.models import BloqueoDeUsuario
from django.conf import settings
from core.services.ai_recommender import rerank_fof
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
import logging
from core.models import Seguidor
from .models import Notificacion, NotificationDevice, PreferenciasUsuario
from .serializers import (
    NotificacionSerializer,
    NotificacionCreateSerializer,
    DeviceSerializer,
    PreferenciasSerializer,
)




logger = logging.getLogger(__name__)

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

class AmigosRecomendadosView(APIView):
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def _avatar(self, u):
        p = getattr(u, "perfil", None)
        try:
            if p and p.profile_picture:
                return p.profile_picture.url
        except Exception:
            pass
        return "/static/img/Gifters/favicongift.png"

    def get(self, request):
        import logging, time
        from django.contrib.auth import get_user_model
        from django.db.models import Count
        from core.models import Seguidor
        from core.services.social import fof_con_senales, sugerencias_qs
        from core.services.ai_recommender import rerank_fof

        t0 = time.time()
        user = request.user
        User = get_user_model()

        # 0) sets básicos
        sigo_ids = set(Seguidor.objects.filter(seguidor=user).values_list("seguido_id", flat=True))
        excluir_ids = sigo_ids | {user.id}

        debug_meta = {"sigo": len(sigo_ids), "paso": "init"}

        # 1) FoF con re-rank
        try:
            candidatos = fof_con_senales(user, limit=60) or []
        except Exception as e:
            logging.warning("fof_con_senales error: %s", e)
            candidatos = []

        debug_meta["fof_raw"] = len(candidatos)
        ranked = []

        if candidatos:
            try:
                ranked = rerank_fof(user, candidatos, take=30)[:12]
            except Exception as e:
                logging.warning("rerank_fof fallback: %s", e)
                ranked = sorted(
                    candidatos,
                    key=lambda x: (x.get("mutual_count", 0), x.get("last_login_ts", 0)),
                    reverse=True
                )[:12]

        debug_meta["fof_ranked"] = len(ranked)
        debug_meta["paso"] = "fof"

        # 2) Fallback populares
        if not ranked:
            pop_qs = sugerencias_qs(user, limit=12)
            if pop_qs.exists():
                ranked = [{
                    "id": u.id,
                    "username": u.nombre_usuario or str(u.id),
                    "full_name": f"{(u.nombre or '').strip()} {(u.apellido or '').strip()}".strip() or (u.nombre_usuario or str(u.id)),
                    "mutual_count": 0,
                    "mutual_names": [],
                    "last_login_ts": int(u.last_login.timestamp()) if u.last_login else 0,
                    "reason": "",
                } for u in pop_qs]

        debug_meta["populares"] = len(ranked)
        debug_meta["paso"] = "populares"

        # 3) Fallback FINAL: recientes (garantizado)
        if not ranked:
            recientes = (
                User.objects.exclude(id__in=excluir_ids)
                .select_related("perfil")
                .order_by("-last_login", "-token_created_at", "-id")[:12]
            )

            # si last_login está muy vacío en tu data, cae a -id
            if not recientes:
                recientes = (
                    User.objects.exclude(id__in=excluir_ids)
                    .select_related("perfil")
                    .order_by("-id")[:12]
                )

            ranked = [{
                "id": u.id,
                "username": (u.nombre_usuario or "").strip() or str(u.id),
                "full_name": (f"{(u.nombre or '').strip()} {(u.apellido or '').strip()}".strip() 
                              or (u.nombre_usuario or str(u.id))),
                "mutual_count": 0,
                "mutual_names": [],
                "last_login_ts": int(u.last_login.timestamp()) if u.last_login else 0,
                "reason": "Recién llegados a Gifter’s",
            } for u in recientes]

        debug_meta["recentes"] = len(ranked)
        debug_meta["paso"] = "recientes"

        # 4) Armar payload final
        ids = [c["id"] for c in ranked[:12]]
        users = {u.id: u for u in User.objects.filter(id__in=ids).select_related("perfil")}

        payload = []
        for c in ranked[:12]:
            u = users.get(c["id"])
            payload.append({
                "id": c["id"],
                "username": c["username"],
                "full_name": c["full_name"],
                "avatar": self._avatar(u) if u else "/static/img/Gifters/favicongift.png",
                "mutual_count": c.get("mutual_count", 0),
                "reason": c.get("reason") or (f"{c.get('mutual_count',0)} amigos en común" if c.get("mutual_count") else "Sugerencia"),
            })

        debug_meta["ms"] = int((time.time() - t0) * 1000)

        # En DEBUG te devuelvo meta para inspeccionar rápido en la network tab
        if getattr(settings, "DEBUG", False):
            return Response({"results": payload, "meta": debug_meta}, status=status.HTTP_200_OK)

        return Response({"results": payload}, status=status.HTTP_200_OK)


