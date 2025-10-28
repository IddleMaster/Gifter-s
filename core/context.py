from django.conf import settings

from datetime import date, timedelta
from django.db import transaction
from .models import Notificacion, Evento, Seguidor, User

def _amigos_de(user):
    # Tus “amigos” = follow mutuo (ya lo tienes en SeguidorQuerySet)
    try:
        return User.objects.filter(
            seguidores__seguidor=user,
            siguiendo__seguido=user,
        ).distinct()
    except Exception:
        return User.objects.none()

def _sync_eventos_a_notifs(user, dias=30):
    """
    Crea Notificacion(tipo='evento_proximo') para eventos de AMIGOS
    que caen entre hoy y hoy+N días y que aún no fueron creadas.
    Se ejecuta al renderizar cualquier página (rápido y seguro).
    """
    if not user.is_authenticated:
        return

    hoy = date.today()
    hasta = hoy + timedelta(days=dias)

    amigos_ids = list(_amigos_de(user).values_list("id", flat=True))
    if not amigos_ids:
        return

    eventos = (Evento.objects
               .filter(id_usuario__in=amigos_ids,
                       fecha_evento__gte=hoy,
                       fecha_evento__lte=hasta)
               .only("evento_id", "id_usuario", "titulo", "fecha_evento"))

    # Evitar duplicados: si ya existe una notif para ese (evento, usuario), no crear otra.
    ya_creadas = set(
        Notificacion.objects.filter(
            usuario=user,
            tipo=Notificacion.Tipo.EVENTO_PROXIMO,
            payload__evento_id__in=list(eventos.values_list("evento_id", flat=True))
        ).values_list("payload__evento_id", flat=True)
    )

    nuevos = []
    for ev in eventos:
        if ev.evento_id in ya_creadas:
            continue
        nuevos.append(Notificacion(
            usuario=user,
            tipo=Notificacion.Tipo.EVENTO_PROXIMO,
            titulo="Evento importante",
            mensaje=f"{ev.titulo} — {ev.fecha_evento.strftime('%d %b')}",
            payload={
                "evento_id": ev.evento_id,
                "owner_id": ev.id_usuario_id,
                "fecha": ev.fecha_evento.isoformat(),
                "titulo": ev.titulo,
            }
        ))

    if nuevos:
        with transaction.atomic():
            Notificacion.objects.bulk_create(nuevos, ignore_conflicts=True)

def navbar_notifications(request):
    """
    Context processor: inyecta en todas las plantillas:
    - notif_count: cantidad NO leídas
    - notif_items: últimas 8 notificaciones (mezcladas) mostrando especialmente eventos
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"notif_count": 0, "notif_items": []}

    # sincroniza eventos → notificaciones (rápido)
    try:
        _sync_eventos_a_notifs(user, dias=30)
    except Exception:
        # si algo falla, no rompe el render
        pass

    # Trae últimas 8
    items = (Notificacion.objects
             .filter(usuario=user)
             .order_by("-creada_en")
             .values("notificacion_id", "tipo", "titulo", "mensaje", "payload", "leida", "creada_en")[:8])

    unread = sum(1 for i in items if not i["leida"])

    return {
        "notif_count": unread,
        "notif_items": list(items),
    }