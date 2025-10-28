# core/services/recommendations.py
# core/services/recommendations.py
from typing import List, Tuple, Optional
from django.core.cache import cache
from django.db.models import Q, Case, When, Value, IntegerField, F, ExpressionWrapper, Max
from core.models import Producto, Wishlist, ItemEnWishlist, User, RecommendationFeedback

CACHE_TTL = 60 * 5  # 5 minutos

def _already_seen_product_ids(usuario: User) -> List[int]:
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

def _user_preference_vectors(usuario: User) -> Tuple[List[int], List[int]]:
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

    return sorted(marcas), sorted(categorias)

def _stable_offset_queryset(qs, usuario: User, limit: int):
    """
    Fallback per-user: elige una 'ventana' distinta por usuario sin ORDER BY aleatorio.
    """
    total = qs.count()
    if total <= limit:
        return qs
    offset = usuario.id % max(1, total - limit)
    return qs[offset:offset + limit]

def _fingerprint_usuario(usuario: User) -> str:
    """
    Un fingerprint corto que cambia cuando:
    - cambian marcas/categorías inferidas
    - cambia el último item (wishlist/recibido) del usuario
    Esto hace que el caché se invalide automáticamente sin que tengamos que borrarlo a mano.
    """
    marcas_pref, cats_pref = _user_preference_vectors(usuario)
    agg = ItemEnWishlist.objects.filter(id_wishlist__usuario=usuario)\
            .aggregate(maxpk=Max("pk"), maxcomprado=Max("fecha_comprado"))
    max_item_pk = agg.get("maxpk") or 0
    max_fecha_comprado = agg.get("maxcomprado") or "0"
    return f"m:{'-'.join(map(str, marcas_pref))}|c:{'-'.join(map(str, cats_pref))}|pk:{max_item_pk}|rc:{max_fecha_comprado}"

def invalidate_user_reco_cache(usuario: User):
    """
    Útil si quieres invalidar manualmente desde algún view (por ej. toggle wishlist).
    """
    cache.delete(f"ai:reco:v2:{usuario.id}:*")  # si tu backend soporta wildcard, OK
    # si NO soporta wildcard, no pasa nada; el fingerprint ya forzará recálculo.

# --- 👇 AQUÍ ESTÁ LA FUNCIÓN CORREGIDA 👇 ---
def recommend_products_for_user(usuario: User, limit: int = 6, exclude_ids: Optional[List[int]] = None) -> List[Producto]:
    """
    Recomendador con caché inteligente:
    - Acepta una lista externa de IDs a excluir (`exclude_ids`).
    - Excluye vistos (recibidos/wishlist) y productos con 'dislike'.
    - Prioriza match por marca (peso 2) y categoría (peso 1).
    - Cachea con fingerprint (se invalida solo cuando cambian señales o items).
    - Fallback estable por usuario si no hay señales.
    """
    fp = _fingerprint_usuario(usuario)
    cache_key = f"ai:reco:v2:{usuario.id}:{fp}:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    marcas_pref, cats_pref = _user_preference_vectors(usuario)
    
    # --- CAMBIO 1: COMBINAMOS LA LISTA DE EXCLUSIÓN ---
    # Unimos los IDs de la vista (wishlist + dislikes) con los que calcula esta función internamente.
    final_exclude_ids = set(_already_seen_product_ids(usuario))
    if exclude_ids:
        final_exclude_ids.update(exclude_ids)
    
    # --- CAMBIO 2: USAMOS LA LISTA FINAL EN LA CONSULTA ---
    base = Producto.objects.filter(activo=True).exclude(pk__in=final_exclude_ids)

    if marcas_pref or cats_pref:
        candidatos = (base.annotate(
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
            Q(score__gt=0)
        ).order_by("-score", "-pk")
         .select_related("id_marca", "id_categoria")
         .prefetch_related("urls_tienda")[:limit])
        
        result = list(candidatos)
        
        # Si después de filtrar no hay suficientes, rellenamos con el fallback
        if len(result) < limit:
            fallback_qs = base.exclude(pk__in=[p.pk for p in result]).order_by("-pk")
            relleno = list(_stable_offset_queryset(fallback_qs, usuario, limit - len(result)))
            result.extend(relleno)
            
        cache.set(cache_key, result, CACHE_TTL)
        return result

    # --- Fallback sin señales ---
    fallback_qs = base.order_by("-pk").select_related("id_marca", "id_categoria").prefetch_related("urls_tienda")
    result = list(_stable_offset_queryset(fallback_qs, usuario, limit))
    cache.set(cache_key, result, CACHE_TTL)
    return result

def recommend_when_wishlist_empty(usuario: User, limit: int = 3) -> List[Producto]:
    return recommend_products_for_user(usuario, limit=limit)
