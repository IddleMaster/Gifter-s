from .models import Wishlist
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def get_default_wishlist(user):
    """
    Devuelve la wishlist 'Favoritos' del usuario.
    Si no existe, la crea (pública por defecto).
    """
    wl, _ = Wishlist.objects.get_or_create(
        usuario=user,
        nombre_wishlist="Favoritos",
        defaults={"es_publica": True}
    )
    return wl


def _push_inbox(user_ids, payload: dict):
    """
    Envía un evento a la 'bandeja' (inbox) de uno o varios usuarios.
    En el FE, el WS del usuario debe estar suscrito al grupo: f'user_inbox_{user_id}'.
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return
        if not isinstance(user_ids, (list, tuple, set)):
            user_ids = [user_ids]
        for uid in user_ids:
            async_to_sync(channel_layer.group_send)(
                f"user_inbox_{uid}",
                {
                    "type": "inbox.update",  # ← nombre del handler en el consumer
                    "payload": payload,      # lo que el FE necesita para refrescar
                },
            )
    except Exception:
        # No romper el flujo si no hay WS configurado
        pass

