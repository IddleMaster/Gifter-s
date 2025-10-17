# core/signals_users.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from core.search import meili

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
