from typing import List
from django.db.models import Q, Case, When, Value, IntegerField, F, ExpressionWrapper
from core.models import Producto, Wishlist, ItemEnWishlist

def _already_seen_product_ids(usuario) -> List[int]:
    """Productos que el usuario ya recibió o tiene en wishlist activa."""
    wl = Wishlist.objects.filter(usuario=usuario).first()
    qs = ItemEnWishlist.objects.filter(id_wishlist__usuario=usuario)

    recibidos_ids = qs.filter(fecha_comprado__isnull=False).values_list("id_producto_id", flat=True)
    wl_ids = []
    if wl:
        wl_ids = ItemEnWishlist.objects.filter(
            id_wishlist=wl, fecha_comprado__isnull=True
        ).values_list("id_producto_id", flat=True)

    return list(set(list(recibidos_ids) + list(wl_ids)))

def _user_preference_vectors(usuario):
    """
    Señales del usuario: marcas y categorías según recibidos > wishlist viva.
    """
    base = ItemEnWishlist.objects.filter(id_wishlist__usuario=usuario) \
        .select_related("id_producto", "id_producto__id_marca", "id_producto__id_categoria")

    recibidos = base.filter(fecha_comprado__isnull=False)
    wishlist_vivos = base.filter(fecha_comprado__isnull=True)

    marcas = set()
    categorias = set()

    for it in recibidos:
        if it.id_producto and it.id_producto.id_marca_id:
            marcas.add(it.id_producto.id_marca_id)
        if it.id_producto and getattr(it.id_producto, "id_categoria_id", None):
            categorias.add(it.id_producto.id_categoria_id)

    if not marcas and not categorias:
        for it in wishlist_vivos:
            if it.id_producto and it.id_producto.id_marca_id:
                marcas.add(it.id_producto.id_marca_id)
            if it.id_producto and getattr(it.id_producto, "id_categoria_id", None):
                categorias.add(it.id_producto.id_categoria_id)

    return list(marcas), list(categorias)

def _stable_offset_queryset(qs, usuario, limit):
    """
    Fallback per-user: elige una 'ventana' distinta por usuario sin ORDER BY aleatorio.
    """
    total = qs.count()
    if total <= limit:
        return qs
    # offset estable por usuario (puedes cambiar a hash si prefieres)
    offset = usuario.id % max(1, total - limit)
    # Nota: slicing preserva el orden
    return qs[offset:offset + limit]

def recommend_products_for_user(usuario, limit=6):
    """
    Recomendador:
    - Si hay señales (marca/categoría): rankea por score y devuelve top.
    - Si NO hay señales: fallback per-user para evitar que todos vean lo mismo.
    - Siempre excluye productos ya vistos (recibidos/wishlist).
    """
    marcas_pref, cats_pref = _user_preference_vectors(usuario)
    exclude_ids = _already_seen_product_ids(usuario)

    base = Producto.objects.filter(activo=True).exclude(pk__in=exclude_ids)

    if marcas_pref or cats_pref:
        candidatos = base.annotate(
            match_marca=Case(
                When(id_marca_id__in=marcas_pref, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
            match_cat=Case(
                When(id_categoria_id__in=cats_pref, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
        ).annotate(
            score=ExpressionWrapper(2 * F("match_marca") + F("match_cat"), output_field=IntegerField())
        ).filter(
            Q(score__gt=0)  # solo los que matchean algo
        ).order_by("-score", "-pk") \
         .select_related("id_marca", "id_categoria") \
         .prefetch_related("urls_tienda")[:limit]
        return list(candidatos)

    # --- Fallback sin señales: per-user estable ---
    fallback_qs = base.order_by("-pk").select_related("id_marca", "id_categoria").prefetch_related("urls_tienda")
    fallback_qs = _stable_offset_queryset(fallback_qs, usuario, limit)
    return list(fallback_qs)

def recommend_when_wishlist_empty(usuario, limit=3):
    return recommend_products_for_user(usuario, limit=limit)
