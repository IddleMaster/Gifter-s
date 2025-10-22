# core/signals_users.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.apps import apps
# SE ELIMINÓ: from core.push_utils_v1 import send_webpush_to_user
from core.search import meili
import json # Import json needed for the DB part
from django.utils import timezone # Import timezone needed for the DB part
from django.db import connection # Import connection needed for the DB part

INDEX = "users"
User = get_user_model()

def _doc(u):
    return {
        "id": u.id,
        "nombre": u.nombre or "",
        "apellido": u.apellido or "",
        "nombre_usuario": u.nombre_usuario or "",
        "correo": u.correo or "",
        "is_active": bool(u.is_active),
    }

@receiver(post_save, sender=User)
def meili_user_saved(sender, instance: User, **kwargs):
    try:
        idx = meili().index(INDEX)
        if not instance.is_active:
            idx.delete_documents([instance.id])
            return
        idx.add_documents([_doc(instance)], primary_key="id")
    except Exception:
        # evita romper el flujo si Meili está caído
        pass

@receiver(post_delete, sender=User)
def meili_user_deleted(sender, instance: User, **kwargs):
    try:
        meili().index(INDEX).delete_documents([instance.id])
    except Exception:
        pass

def _pick_users(instance):
    """
    Devuelve (emisor, receptor) según los nombres de campos típicos del modelo:
    - FriendRequest: from_user / to_user
    - SolicitudAmistad: de / para
    """
    for a, b in (("from_user", "to_user"), ("de", "para")):
        if hasattr(instance, a) and hasattr(instance, b):
            return getattr(instance, a), getattr(instance, b)
    # fallback (por si usas otros nombres)
    for a, b in (("emisor", "receptor"),):
        if hasattr(instance, a) and hasattr(instance, b):
            return getattr(instance, a), getattr(instance, b)
    return None, None

def _sender_display(u):
    return getattr(u, "nombre", None) or getattr(u, "first_name", None) or getattr(u, "username", None) or "Alguien"

# Intentar conectar a los modelos relevantes
Model = None # Initialize Model to None outside the loop
for model_name in ("SolicitudAmistad", "FriendRequest"):
    try:
        Model = apps.get_model("core", model_name)
        break # Stop if found
    except LookupError:
        Model = None
    if not Model:
        continue


if Model:
    @receiver(post_save, sender=Model)
    def _notify_new_friend_request(sender, instance, created, **kwargs):
        if not created:
            return


        de, para = _pick_users(instance)
        if not para:
            return

        title = "Nueva solicitud de amistad"
        body = f"{_sender_display(de)} te envió una solicitud de amistad"
        # link = "/amistad/amigos/" # Link no se usa si no hay push
        data = {
            "type": "friend_request",
            "request_id": str(getattr(instance, "pk", "")),
            "from_username": getattr(de, "nombre_usuario", None)
                or getattr(de, "username", "")
                or "",
        }

        # --- SE MANTUVO: Guardar en la tabla interna 'notificaciones' ---
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO notificaciones (tipo, titulo, mensaje, payload, leida, creada_en, usuario_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, [
                    "solicitud_amistad",
                    title,
                    body,
                    json.dumps(data),
                    0,
                    timezone.now(),
                    para.id
                ])
        except Exception as e:
            print("Error guardando notificación local:", e)

     