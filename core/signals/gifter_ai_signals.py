import hashlib
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import Perfil, ItemEnWishlist, Wishlist


def _clear_gifter_ai_cache(user_id: int, extra: str = ""):
    """Borra todas las entradas de caché IA para el usuario indicado."""
    prefix = f"ia_text_user_{user_id}"
    # Si hay hash en la key, solo borramos las que lo contengan
    for key in list(cache._cache.keys()):
        if prefix in key:
            cache.delete(key)


@receiver(post_save, sender=Perfil)
def refresh_ai_on_profile_update(sender, instance, **kwargs):
    """Si el usuario actualiza su bio o perfil, limpiamos IA."""
    if instance and instance.user_id:
        _clear_gifter_ai_cache(instance.user_id)


@receiver(post_save, sender=ItemEnWishlist)
def refresh_ai_on_wishlist_change(sender, instance, **kwargs):
    """Si cambia algo en su wishlist (añade, marca recibido, etc.), limpiamos IA."""
    wl = getattr(instance, "id_wishlist", None)
    if wl and isinstance(wl, Wishlist):
        _clear_gifter_ai_cache(wl.usuario_id)
