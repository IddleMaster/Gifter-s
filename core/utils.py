from .models import Wishlist

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
