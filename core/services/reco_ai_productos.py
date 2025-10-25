# core/services/reco_ai_productos.py
import hashlib
import logging
from django.db.models import Q
from django.core.cache import cache

from core.models import Producto, Wishlist, ItemEnWishlist
from core.services.openai_client import get_openai_client

logger = logging.getLogger(__name__)


def _build_user_context(user):
    """
    Arma un resumen del gusto del usuario en base a su wishlist o recibidos.
    """
    wl = Wishlist.objects.filter(usuario=user).first()
    nombres = []

    if wl:
        items = ItemEnWishlist.objects.filter(id_wishlist=wl).select_related("id_producto")
        for it in items:
            if it.id_producto:
                nombres.append(it.id_producto.nombre_producto)

    perfil = getattr(user, "perfil", None)
    bio = getattr(perfil, "bio", "") if perfil else ""
    return ", ".join(nombres) + (f". Bio: {bio}" if bio else "")


def recomendar_productos_ia(user, limit=6):
    """
    Usa OpenAI para analizar los gustos del usuario y devolver productos reales
    de la base de datos que encajen con su perfil (por marca, categoría o texto).
    """
    datos = _build_user_context(user)
    if not datos.strip():
        logger.info("[IA Productos] Usuario sin contexto suficiente.")
        return []

    cache_key = f"ia_prods_home_{user.id}_{hashlib.sha1(datos.encode()).hexdigest()}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    # 1️⃣ Extraemos productos candidatos
    candidatos = list(
        Producto.objects.filter(activo=True)
        .select_related("id_marca", "id_categoria")
        .order_by("?")[:60]  # base aleatoria variada
    )
    if not candidatos:
        return []

    # 2️⃣ Preparamos descripción resumida para la IA
    lista_txt = "\n".join(
        [f"- {p.nombre_producto} ({p.id_marca.nombre_marca if p.id_marca else 'Sin marca'})" for p in candidatos]
    )

    prompt = (
        f"Eres GifterAI, experto en regalos y afinidad de productos.\n"
        f"Con base en los gustos de este usuario ({datos}), selecciona hasta {limit} productos "
        f"de la siguiente lista que más le podrían interesar:\n\n{lista_txt}\n\n"
        f"Responde solo con los nombres exactos de los productos más relevantes, uno por línea."
    )

    try:
        client = get_openai_client()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un experto en recomendación de productos."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=250,
            temperature=0.6,
        )
        texto = (resp.choices[0].message.content or "").strip().lower()

        # 3️⃣ Buscar coincidencias en DB según nombres detectados
        recomendados = [
            p for p in candidatos
            if any(p.nombre_producto.lower() in texto or p.id_marca.nombre_marca.lower() in texto for _ in [1])
        ]

        # fallback si la IA no menciona nada reconocible
        if not recomendados:
            recomendados = candidatos[:limit]

        recomendados = recomendados[:limit]
        cache.set(cache_key, recomendados, 60 * 30)  # 30 min cache
        return recomendados

    except Exception as e:
        logger.exception("[IA Productos] Error IA: %s", e)
        return candidatos[:limit]
