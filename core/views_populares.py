# core/views_populares.py
from datetime import timedelta
import json
from django.http import JsonResponse, HttpResponseServerError
from django.db.models import Count, Q, F
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.core.cache import cache
from django.conf import settings

from .models import Producto

# ======== Config IA ========
AI_MODEL = getattr(settings, "OPENAI_TRENDS_MODEL", "gpt-4.1-mini")
AI_CACHE_TTL = 60 * 10  # 10 min

def _qs_populares_base(window_days=30, limit=50):
    since = timezone.now() - timedelta(days=window_days)
    return (
        Producto.objects.filter(activo=True)
        .select_related("id_categoria", "id_marca")
        .annotate(
            wl_total=Coalesce(Count("en_wishlists", distinct=True), 0),
            wl_recent=Coalesce(Count("en_wishlists",
                                     filter=Q(en_wishlists__fecha_agregado__gte=since),
                                     distinct=True), 0),
            compras=Coalesce(Count("en_wishlists",
                                   filter=Q(en_wishlists__fecha_comprado__isnull=False),
                                   distinct=True), 0),
            regalos=Coalesce(Count("en_wishlists__historial_regalos",
                                   filter=Q(en_wishlists__historial_regalos__fecha_creacion__gte=since),
                                   distinct=True), 0),
        )
        .annotate(score=F("wl_recent")*2 + F("compras")*3 + F("regalos")*4 + F("wl_total"))
        .order_by("-score", "-fecha_creacion")[:limit]
    )

def _build_ai_payload(qs):
    items = []
    for p in qs:
        items.append({
            "id": p.id_producto,
            "nombre": p.nombre_producto,
            "categoria": getattr(p.id_categoria, "nombre_categoria", None),
            "marca": getattr(p.id_marca, "nombre_marca", None),
            "precio": p.precio,
            "img": (p.imagen.url if p.imagen else None),
            "url": p.url,
            "wl_total": getattr(p, "wl_total", 0),
            "wl_recent": getattr(p, "wl_recent", 0),
            "compras": getattr(p, "compras", 0),
            "regalos": getattr(p, "regalos", 0),
            "score": getattr(p, "score", 0),
        })
    return {"window_days": 30, "candidatos": items}

def _ask_openai(payload, k):
    """
    Llama a OpenAI para seleccionar/ordenar qué productos mostrar.
    Usa tu cliente si existe en core.services.openai_client.
    """
    # Cliente compatible
    try:
        from core.services.openai_client import client as oa_client
    except Exception:
        from openai import OpenAI
        oa_client = OpenAI()

    system = (
        "Eres un ranker para un e-commerce social (Gifter’s). "
        "Recibes productos con métricas (wishlist, compras, regalos) y debes decidir "
        f"los {k} mejores para mostrar en 'Productos más populares', garantizando variedad."
    )

    user = f"""
Devuelve SOLO un JSON válido con el esquema:
{{
  "selected_ids": [int],                // máximo {k}
  "badges": [{{"product_id": int, "badge": "Top regalo|Tendencia|Más deseado|Nuevo"}}],
  "section_title": "string",
  "pill": "string"
}}

Reglas:
- Prioriza REGALOS y COMPRAS recientes; luego wishlist recientes.
- Variedad: evita más de 3 de la misma categoría y 2 de la misma marca.
- Si hay duplicados cercanos, elige 1.
- No inventes IDs, usa los que vienen en CANDIDATOS.

CANDIDATOS:
{json.dumps(payload, ensure_ascii=False)}
"""

    resp = oa_client.responses.create(
        model=AI_MODEL,
        input=[{"role":"system","content":system},{"role":"user","content":user}],
    )
    txt = resp.output_text  # debe ser JSON
    return json.loads(txt)

def _fallback_ids(qs, k):
    return [p.id_producto for p in qs[:k]]

@require_GET
def populares_ai(request):
    """
    Endpoint con IA (+fallback). Acepta ?k=6 para limitar la cantidad.
    Cachea el resultado por 10 min.
    """
    k = max(1, min(12, int(request.GET.get("k", "12"))))
    cache_key = f"populares_ai_v3_k{k}"

    cached = cache.get(cache_key)
    if cached:
        return JsonResponse(cached, safe=False)

    try:
        qs = _qs_populares_base()
        payload = _build_ai_payload(qs)

        try:
            ai = _ask_openai(payload, k)
            selected_ids = list(ai.get("selected_ids") or [])[:k]
            badges_raw  = ai.get("badges") or []
            # NUEVO: titulo/pill/rationale opcionales desde IA
            title = (ai.get("section_title") or "Productos más populares").strip()
            pill  = (ai.get("pill") or "TENDENCIAS").strip()
            rationale = (ai.get("rationale") or "").strip()
        except Exception:
            selected_ids = _fallback_ids(qs, k)
            badges_raw, title, pill, rationale = [], "Productos más populares", "TENDENCIAS", ""

        # Sanitizar badges (máx 3, y sólo IDs válidos)
        valid_ids = {p.id_producto for p in qs}
        badges = []
        seen = set()
        for b in badges_raw:
            pid = (b or {}).get("product_id")
            label = (b or {}).get("badge") or ""
            if pid in valid_ids and pid not in seen and label:
                badges.append({"product_id": pid, "badge": label})
                seen.add(pid)
            if len(badges) >= 3:
                break

        prod_map = {p.id_producto: p for p in qs}
        items = []
        for pid in selected_ids:
            p = prod_map.get(pid)
            if not p:
                continue
            items.append({
                "id": p.id_producto,
                "nombre": p.nombre_producto,
                "categoria": getattr(p.id_categoria, "nombre_categoria", None),
                "marca": getattr(p.id_marca, "nombre_marca", None),
                "precio": p.precio,
                "img": (p.imagen.url if p.imagen else None),
                "url": p.url,
            })

        # si la IA devolvió menos, completa con fallback
        if len(items) < k:
            taken = {i["id"] for i in items}
            for pid in _fallback_ids(qs, k*2):
                if pid in taken:
                    continue
                p = prod_map.get(pid)
                if not p:
                    continue
                items.append({
                    "id": p.id_producto,
                    "nombre": p.nombre_producto,
                    "categoria": getattr(p.id_categoria, "nombre_categoria", None),
                    "marca": getattr(p.id_marca, "nombre_marca", None),
                    "precio": p.precio,
                    "img": (p.imagen.url if p.imagen else None),
                    "url": p.url,
                })
                if len(items) >= k:
                    break

        result = {
            "title": title,
            "pill": pill,
            "items": items[:k],
            "badges": badges,        # [{product_id, badge}]
            "rationale": rationale,  # NUEVO
        }
        cache.set(cache_key, result, AI_CACHE_TTL)
        return JsonResponse(result, safe=False)

    except Exception as e:
        return HttpResponseServerError(f"Error tendencias: {e}")

