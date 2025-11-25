# core/views_populares.py
from datetime import timedelta
import json
from django.http import JsonResponse
from django.db.models import Count, Q, F
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.views.decorators.http import require_GET

from django.conf import settings
from .models import Producto


# ================================================================
# HELPER REAL: Imagen segura (versión FINAL)
# ================================================================
def safe_image(img):
    """
    Devuelve SOLO el nombre de archivo o la URL externa.
    El FRONTEND se encarga de poner /media/... automáticamente.
    """
    if not img:
        return None

    # ImageField => devolver SOLO el filename, NO .url
    try:
        return img.name
    except Exception:
        pass

    img = str(img)

    # Imagen externa por URL
    if img.startswith("http"):
        return img

    # Nombre de archivo local como string
    return img


# ================================================================
# QUERY PRINCIPAL: productos populares por señales recientes
# ================================================================
def _qs_populares_base(days=30, limit=50):
    since = timezone.now() - timedelta(days=days)

    return (
        Producto.objects.filter(activo=True)
        .select_related("id_categoria", "id_marca")
        .annotate(
            wl_total=Coalesce(Count("en_wishlists", distinct=True), 0),
            wl_recent=Coalesce(
                Count(
                    "en_wishlists",
                    filter=Q(en_wishlists__fecha_agregado__gte=since),
                    distinct=True
                ),
                0,
            ),
            compras=Coalesce(
                Count(
                    "en_wishlists",
                    filter=Q(en_wishlists__fecha_comprado__isnull=False),
                    distinct=True
                ),
                0,
            ),
            regalos=Coalesce(
                Count(
                    "en_wishlists__historial_regalos",
                    filter=Q(en_wishlists__historial_regalos__fecha_creacion__gte=since),
                    distinct=True
                ),
                0,
            ),
        )
        .annotate(
            score=(
                F("wl_recent") * 2 +
                F("compras") * 3 +
                F("regalos") * 4 +
                F("wl_total")
            )
        )
        .order_by("-score", "-fecha_creacion")[:limit]
    )


# ================================================================
# ENDPOINT FINAL SIN IA (ESTABLE, RÁPIDO, PERFECTO)
# ================================================================
@require_GET
def populares_ai(request):
    """
    Endpoint estable con IA.
    IA solo agrega contexto, NO modifica pill/title/subtitle.
    """

    k = max(1, min(12, int(request.GET.get("k", "12"))))

    qs = _qs_populares_base(days=30, limit=k)

    items = []
    for p in qs:
        items.append({
            "id": p.id_producto,
            "nombre": p.nombre_producto,
            "categoria": getattr(p.id_categoria, "nombre_categoria", None),
            "marca": getattr(p.id_marca, "nombre_marca", None),
            "precio": p.precio,
            "img": safe_image(p.imagen),
            "url": p.url,
        })

    # ============================
    # 🚀 IA OLLAMA (NUEVO)
    # ============================
    try:
        prompt = (
            "Analiza estos productos populares y dame un resumen cuidadoso, "
            "breve, profesional y positivo. Explica por qué podrían estar "
            f"destacando. Lista de productos:\n{json.dumps(items, ensure_ascii=False)}"
        )

        response = requests.post(
            "http://ollama:11434/api/generate",
            json={"model": "llama3.1", "prompt": prompt},
            timeout=20
        )

        ai_output = response.json().get("response", "").strip()

    except Exception:
        ai_output = "Tendencias basadas en actividad reciente de los usuarios."

    # ============================
    # 🔥 Respuesta final
    # ============================
    return JsonResponse({
        "title": "Productos más populares",
        "pill": "TENDENCIAS",
        "rationale": "Lo que más guardan y reciben los usuarios.",
        "ai_reason": ai_output,  # ≤ NUEVO (no afecta diseño)
        "items": items,
        "badges": [],
    })
