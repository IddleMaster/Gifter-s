import json
import hashlib
from django.core.cache import cache
from django.conf import settings
from core.services.ollama_client import ollama_chat

CACHE_TTL = getattr(settings, "GIFTER_AI_CACHE_TTL", 60 * 30)
MODEL = getattr(settings, "GIFTER_AI_MODEL", "llama3.2:1b")


def _cache_key(lista_productos):
    raw = json.dumps(lista_productos, sort_keys=True)
    h = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return f"gifter_ai:productos:{h}"


def generar_reco_productos(lista_productos):
    """
    lista_productos = [
        {"id": 123, "nombre": "...", "categoria": "...", "precio": 12345},
        ...
    ]
    Devuelve => { "123": "texto recomendado", ... }
    """

    if not lista_productos:
        return {}

    key = _cache_key(lista_productos)
    cached = cache.get(key)
    if cached:
        return cached

    prompt = (
        "Eres GifterAI. Te daré una lista de productos y debes devolver "
        "una recomendación CORTA para cada uno.\n\n"
        "FORMATO EXACTO DE RESPUESTA:\n"
        "[\n"
        "  {\"id\": 123, \"recomendacion\": \"texto breve\"},\n"
        "  ...\n"
        "]\n\n"
        "NO escribas nada antes ni después del JSON.\n\n"
        "Productos:\n"
        f"{json.dumps(lista_productos, ensure_ascii=False)}"
    )

    try:
        raw = ollama_chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )

        cleaned = raw.strip()

        data = json.loads(cleaned)

        out = {str(item["id"]): item["recomendacion"] for item in data if "id" in item}

        cache.set(key, out, CACHE_TTL)
        return out

    except Exception as e:
        print("ERROR en IA productos:", e)
        return {}
