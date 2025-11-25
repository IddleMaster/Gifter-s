# core/services/reco_ai_productos.py
import hashlib
import logging
from django.core.cache import cache
from core.models import Producto, Wishlist, ItemEnWishlist
from core.services.ollama_client import ollama_chat   # IA local

logger = logging.getLogger(__name__)


def _build_user_context(user):
    """
    Resume gustos del usuario usando wishlist, recibidos y bio.
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
    IA local: Usa OLLAMA para elegir productos recomendados
    sin depender de OpenAI.
    """
    datos = _build_user_context(user)
    if not datos.strip():
        logger.info("[IA Productos] Usuario sin contexto suficiente.")
        return []

    # Cache
    cache_key = f"ia_prods_home_{user.id}_{hashlib.sha1(datos.encode()).hexdigest()}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    #  Candidatos reales
    candidatos = list(
        Producto.objects.filter(activo=True)
        .select_related("id_marca", "id_categoria")
        .order_by("?")[:60]
    )
    if not candidatos:
        return []

    #  Texto para IA
    lista_txt = "\n".join(
        f"- {p.nombre_producto} (marca {p.id_marca.nombre_marca if p.id_marca else 'Sin marca'})"
        for p in candidatos
    )

    prompt = (
        "Eres GifterAI, experto en afinidad de productos.\n"
        f"Gustos del usuario:\n{datos}\n\n"
        f"Debes seleccionar EXACTAMENTE {limit} productos de la siguiente lista.\n"
        "Responde SOLO con los nombres EXACTOS de los productos, uno por línea.\n"
        "No agregues descripciones, guiones, ni texto adicional.\n\n"
        f"{lista_txt}"
    )

    #  IA local
    try:
        respuesta = ollama_chat(
            messages=[
                {"role": "system", "content": "Eres un experto en recomendación de productos."},
                {"role": "user", "content": prompt},
            ],
            model="llama3.2:1b",
            temperature=0.2,
        )

        if not respuesta:
            logger.warning("[IA Productos] Ollama devolvió vacío. Fallback.")
            return candidatos[:limit]

        # Normalizamos la respuesta
        texto = respuesta.lower().strip()
        lineas = [l.strip("-• ").strip() for l in texto.split("\n") if l.strip()]

        #  Match más robusto
        recomendados = []
        for linea in lineas:
            for p in candidatos:
                nombre_norm = p.nombre_producto.lower().strip()
                marca_norm = (p.id_marca.nombre_marca.lower().strip()
                              if p.id_marca else "")

                #  Matching inteligente
                if (
                    nombre_norm == linea
                    or nombre_norm in linea
                    or linea in nombre_norm
                    or marca_norm and marca_norm in linea
                ):
                    if p not in recomendados:
                        recomendados.append(p)

        # si no hubo match → fallback
        if not recomendados:
            recomendados = candidatos[:limit]

        recomendados = recomendados[:limit]
        cache.set(cache_key, recomendados, 60 * 30)
        return recomendados

    except Exception as e:
        logger.exception("[IA Productos] Error con OLLAMA: %s", e)
        return candidatos[:limit]
