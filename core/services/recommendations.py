from typing import List, Tuple, Optional
from django.core.cache import cache
from django.db.models import Q, Case, When, Value, IntegerField, F, ExpressionWrapper, Max
from core.models import Producto, Wishlist, ItemEnWishlist, User
import hashlib


CACHE_TTL = 60 * 5  # 5 minutos

# Prefijo para versionar el cache por usuario
USER_RECO_VER_PREFIX = "ai:reco:ver:"


# ------------------------------
# Utils base
# ------------------------------
def _already_seen_product_ids(usuario: User) -> List[int]:
    """Retorna productos que el usuario ya recibió o tiene en wishlist activa."""
    wl = Wishlist.objects.filter(usuario=usuario).first()
    qs = ItemEnWishlist.objects.filter(id_wishlist__usuario=usuario)

    recibidos_ids = qs.filter(fecha_comprado__isnull=False).values_list("id_producto_id", flat=True)
    wl_ids = []

    if wl:
        wl_ids = ItemEnWishlist.objects.filter(
            id_wishlist=wl,
            fecha_comprado__isnull=True
        ).values_list("id_producto_id", flat=True)

    return list(set(list(recibidos_ids) + list(wl_ids)))


def _user_preference_vectors(usuario: User) -> Tuple[List[int], List[int]]:
    """Señales del usuario: marcas/categorías según recibidos > wishlist viva."""
    base = ItemEnWishlist.objects.filter(id_wishlist__usuario=usuario).select_related(
        "id_producto", "id_producto__id_marca", "id_producto__id_categoria"
    )

    recibidos = base.filter(fecha_comprado__isnull=False)
    wishlist_vivos = base.filter(fecha_comprado__isnull=True)

    marcas, categorias = set(), set()

    for it in recibidos:
        if it.id_producto:
            if it.id_producto.id_marca_id:
                marcas.add(it.id_producto.id_marca_id)
            if it.id_producto.id_categoria_id:
                categorias.add(it.id_producto.id_categoria_id)

    if not marcas and not categorias:
        for it in wishlist_vivos:
            if it.id_producto:
                if it.id_producto.id_marca_id:
                    marcas.add(it.id_producto.id_marca_id)
                if it.id_producto.id_categoria_id:
                    categorias.add(it.id_producto.id_categoria_id)

    return sorted(marcas), sorted(categorias)


def _stable_offset_queryset(qs, usuario: User, limit: int):
    """
    Fallback: escoge una ventana estable por usuario sin random().
    """
    total = qs.count()
    if total <= limit:
        return qs
    offset = usuario.id % max(1, total - limit)
    return qs[offset:offset + limit]


def _fingerprint_usuario(usuario: User) -> str:
    """
    Fingerprint que cambia cuando cambian señales del usuario:
    - marcas/categorías
    - último item de wishlist/recibido
    """
    marcas_pref, cats_pref = _user_preference_vectors(usuario)
    agg = ItemEnWishlist.objects.filter(id_wishlist__usuario=usuario).aggregate(
        maxpk=Max("pk"),
        maxcomprado=Max("fecha_comprado")
    )
    max_item_pk = agg.get("maxpk") or 0
    max_fecha_comprado = agg.get("maxcomprado") or "0"

    return f"m:{marcas_pref}|c:{cats_pref}|pk:{max_item_pk}|rc:{max_fecha_comprado}"


def invalidate_user_reco_cache(usuario: User):
    """Incrementa la versión del cache de este usuario."""
    key = f"{USER_RECO_VER_PREFIX}{usuario.id}"

    try:
        if cache.get(key) is None:
            cache.set(key, 1)
        else:
            try:
                cache.incr(key)
            except Exception:
                v = cache.get(key) or 0
                cache.set(key, int(v) + 1)
    except Exception:
        pass


# ------------------------------
# RECOMENDADOR PRINCIPAL
# ------------------------------
def recommend_products_for_user(
    usuario: User,
    limit: int = 6,
    exclude_ids: Optional[List[int]] = None
) -> List[Producto]:

    # Fingerprint + versión
    fp = _fingerprint_usuario(usuario)
    ver = cache.get(f"{USER_RECO_VER_PREFIX}{usuario.id}") or 0

    #  FIX: Hash del fingerprint para evitar warnings
    fp_hash = hashlib.sha1(fp.encode()).hexdigest()

    cache_key = f"ai:reco:v2:{usuario.id}:v{ver}:{fp_hash}:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # Señales
    marcas_pref, cats_pref = _user_preference_vectors(usuario)

    # IDs excluidos (wishlist, recibidos, dislikes, etc.)
    final_exclude_ids = set(_already_seen_product_ids(usuario))
    if exclude_ids:
        final_exclude_ids.update(exclude_ids)

    base = Producto.objects.filter(activo=True).exclude(pk__in=final_exclude_ids)

    # ------------------------------
    # Si hay señales: ranking por score
    # ------------------------------
    if marcas_pref or cats_pref:
        candidatos = (
            base.annotate(
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
            )
            .annotate(score=2 * F("match_marca") + F("match_cat"))
            .filter(score__gt=0)
            .order_by("-score", "-pk")
            .select_related("id_marca", "id_categoria")
            .prefetch_related("urls_tienda")[:limit]
        )

        result = list(candidatos)

        # Si faltan productos, rellenar con fallback
        if len(result) < limit:
            fallback_qs = base.exclude(pk__in=[p.pk for p in result]).order_by("-pk")
            relleno = list(_stable_offset_queryset(fallback_qs, usuario, limit - len(result)))
            result.extend(relleno)

        cache.set(cache_key, result, CACHE_TTL)
        return result

    # ------------------------------
    # Fallback SIN señales
    # ------------------------------
    fallback_qs = base.order_by("-pk").select_related("id_marca", "id_categoria").prefetch_related("urls_tienda")
    result = list(_stable_offset_queryset(fallback_qs, usuario, limit))

    cache.set(cache_key, result, CACHE_TTL)
    return result


def recommend_when_wishlist_empty(usuario: User, limit: int = 3) -> List[Producto]:
    return recommend_products_for_user(usuario, limit=limit)
