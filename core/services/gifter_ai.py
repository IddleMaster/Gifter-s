import re
import hashlib
import logging
from typing import List, Dict

from django.conf import settings
from django.core.cache import cache

# Intenta importar tu helper del cliente; si no existe/rompe, seguimos con fallback.
try:
    from core.services.openai_client import get_openai_client  # type: ignore
except Exception:  # pragma: no cover
    get_openai_client = None  # type: ignore


logger = logging.getLogger(__name__)

# ==============================
# Config
# ==============================
BULLET_RE = re.compile(r"^\s*[-•]\s*(.+)$")
CACHE_TTL = getattr(settings, "GIFTER_AI_CACHE_TTL", 60 * 30)  # 30 min por defecto
OPENAI_MODEL = getattr(settings, "GIFTER_AI_MODEL", "gpt-4o-mini")


# ==============================
# Utilidades
# ==============================
def _sanitize(texto: str) -> str:
    return re.sub(r"\s+", " ", (texto or "").strip())


def _parse_bullets(texto: str) -> List[Dict[str, str]]:
    """
    Extrae pares {idea, explicacion} desde líneas tipo:
    - **Idea:** Explicación
    """
    out: List[Dict[str, str]] = []
    for raw in texto.splitlines():
        m = BULLET_RE.match(raw.strip())
        if not m:
            continue
        linea = m.group(1).strip()
        idea, explic = (linea.split(":", 1) + [""])[:2]
        out.append({
            "idea": idea.replace("**", "").strip(),
            "explicacion": _sanitize(explic)
        })
    return [s for s in out if s["idea"]]


def _cache_key(nombre: str, datos: str) -> str:
    """
    Llave de caché depende del usuario + hash de datos (para invalidar cuando cambien).
    """
    h = hashlib.sha1(_sanitize(datos).encode("utf-8")).hexdigest()  # no sensible
    return f"gifter_ai:sug:{nombre}:{h}"


# ==============================
# Fallback local (sin usar OpenAI)
# ==============================
def _fallback_sugerencias(nombre: str, datos: str) -> List[Dict[str, str]]:
    """
    Genera 3 ideas simples usando heurísticas a partir de 'datos' (wishlist/recibidos/bio).
    Está pensado para funcionar cuando no hay API key o la llamada falla.
    """
    base = _sanitize(datos).lower()
    ideas: List[Dict[str, str]] = []

    def add(idea: str, explic: str):
        if idea and len(ideas) < 3:
            ideas.append({"idea": idea, "explicacion": explic})

    # Pistas básicas por palabras clave
    if any(k in base for k in ("zapat", "deport", "nike", "gym", "correr", "running")):
        add("Kit deportivo básico",
            f"Medias técnicas o sandalias deportivas; útil para el día a día de {nombre}.")
    if any(k in base for k in ("billetera", "cartera", "cuero", "tarjetas")):
        add("Porta-tarjetas slim",
            "Complementa su billetera con un organizador compacto y práctico.")
    if any(k in base for k in ("gato", "mascota", "cat", "aren", "rascador")):
        add("Accesorios para su gato",
            "Rascador compacto o snacks premium; encaja con sus gustos.")
    if any(k in base for k in ("café", "cafetera", "espresso", "bialetti")):
        add("Set de café en casa",
            "Filtros, jarra medidora o café de especialidad para potenciar su rutina.")
    if any(k in base for k in ("gaming", "videojuego", "steam", "xbox", "play")):
        add("Tarjeta regalo gaming",
            "Crédito digital para que elija justo el juego/contenido que quiere.")
    if any(k in base for k in ("fortnite", "chocolate", "nestle", "dulce", "snack")):
        add("Box de snacks personalizados",
            "Selección de dulces/barras que vaya con sus preferencias.")

    # Relleno por si no se detectó nada
    while len(ideas) < 3:
        if not any("tarjeta regalo" in i["idea"].lower() for i in ideas):
            add("Tarjeta regalo de su tienda favorita",
                "Flexible y sin margen de error: elige exactamente lo que quiere.")
        elif not any("experiencia" in i["idea"].lower() for i in ideas):
            add("Experiencia corta",
                "Cine, café o streaming por un mes; un detalle que siempre suma.")
        else:
            add("Detalle personalizable",
                "Taza/llavero con su nombre o hobby; pequeño pero significativo.")

    return ideas[:3]


# ==============================
# Llamada a OpenAI (si disponible)
# ==============================
def _usar_openai(nombre_usuario: str, datos_para_ia: str, max_tokens: int) -> List[Dict[str, str]]:
    """
    Llama a OpenAI si hay API key y cliente disponible. Devuelve lista [{idea, explicacion}] (<=3).
    Si algo falla, retorna [] y el caller hace fallback.
    """
    if not getattr(settings, "OPENAI_API_KEY", None):
        logger.info("[GifterAI] OPENAI_API_KEY no configurada; se usará fallback local.")
        return []

    if get_openai_client is None:
        logger.info("[GifterAI] get_openai_client no disponible; se usará fallback local.")
        return []

    try:
        client = get_openai_client()
    except Exception as e:  # pragma: no cover
        logger.exception("[GifterAI] Error creando cliente OpenAI: %s", e)
        return []

    prompt_user = (
        "Eres GifterAI, un asistente simpático y experto en regalos.\n"
        f"Tu tarea es proponer 3 ideas de regalos creativas y útiles para {nombre_usuario}, "
        f"basándote en:\n{datos_para_ia}\n"
        "Responde SOLO con 3 líneas, cada una en el formato EXACTO:\n"
        "- **[Idea]:** [Explicación breve]\n"
        "Evita enumeraciones fuera de ese formato y no añadas texto extra."
    )

    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Eres GifterAI, un asistente experto en regalos."},
                {"role": "user", "content": prompt_user},
            ],
            max_tokens=max_tokens,
            temperature=0.7,
            n=1,
        )
        content = _sanitize(resp.choices[0].message.content or "")
        ideas = _parse_bullets(content)[:3]
        if not ideas:
            logger.info("[GifterAI] OpenAI respondió sin bullets válidos; se usará fallback local.")
        return ideas
    except Exception as e:
        logger.exception("[GifterAI] Error llamando a OpenAI: %s", e)
        return []


# ==============================
# API pública (usada por la vista)
# ==============================
def generar_sugerencias_regalo(
    nombre_usuario: str,
    datos_para_ia: str,
    max_tokens: int = 180
) -> List[Dict[str, str]]:
    """
    Devuelve hasta 3 ideas de regalo con su explicación.

    Flujo:
      1) Si hay caché -> retorna.
      2) Intenta OpenAI.
      3) Si falla, fallback local.
      4) Guarda en caché el resultado final (para no recalcular en cada request).
    """
    datos = _sanitize(datos_para_ia)
    if not datos:
        logger.info("[GifterAI] Sin datos; no se generan sugerencias.")
        return []

    key = _cache_key(nombre_usuario, datos)
    cached = cache.get(key)
    if cached:
        return cached

    # 1) Intenta OpenAI
    ideas = _usar_openai(nombre_usuario, datos, max_tokens)
    if not ideas:
        # 2) Fallback local
        ideas = _fallback_sugerencias(nombre_usuario, datos)

    # 3) Cachear siempre el resultado final (sea IA o fallback)
    try:
        cache.set(key, ideas, CACHE_TTL)
    except Exception:  # cache puede fallar en algunos backends
        pass

    return ideas
