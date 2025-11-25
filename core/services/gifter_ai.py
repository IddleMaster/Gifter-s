
import re
import hashlib
import logging
import json
from typing import List, Dict

from django.conf import settings
from django.core.cache import cache

# === IA LOCAL (OLLAMA) ===
from core.services.ollama_client import ollama_chat

logger = logging.getLogger(__name__)

# ==============================
# Config
# ==============================
CACHE_TTL = getattr(settings, "GIFTER_AI_CACHE_TTL", 60 * 30)
OLLAMA_MODEL = getattr(settings, "GIFTER_AI_MODEL", "llama3.2:1b")

BULLET_RE = re.compile(r"^\s*[-•]\s*(.+)$")


# ==============================
# Helpers
# ==============================
def _sanitize(texto: str) -> str:
    return re.sub(r"\s+", " ", (texto or "").strip())


def _clean_json_block(raw: str) -> str:
    """
    Limpia casos donde Ollama devuelve:
    ```json
    { ... }
    ```
    """
    raw = raw.strip()

    # quitar bloques tipo ```json ... ```
    raw = re.sub(r"^```json", "", raw, flags=re.IGNORECASE).strip()
    raw = re.sub(r"```$", "", raw).strip()

    # si viene texto antes del JSON -> intentar recortar
    first_brace = raw.find("{")
    if first_brace > 0:
        raw = raw[first_brace:]

    # si termina después del JSON -> recortar
    last_brace = raw.rfind("}")
    if last_brace != -1:
        raw = raw[:last_brace + 1]

    return raw.strip()


def _parse_bullets(texto: str) -> List[Dict[str, str]]:
    out = []
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
    h = hashlib.sha1(_sanitize(datos).encode("utf-8")).hexdigest()
    return f"gifter_ai:sug:{nombre}:{h}"


# ==============================
# Fallback local
# ==============================
def _fallback_sugerencias(nombre: str, datos: str) -> List[Dict[str, str]]:
    base = _sanitize(datos).lower()
    ideas = []

    def add(idea, explic):
        if len(ideas) < 3:
            ideas.append({"idea": idea, "explicacion": explic})

    if any(k in base for k in ("zapat", "deport", "nike", "gym", "running")):
        add("Kit deportivo básico", f"Accesorios deportivos útiles para {nombre}.")
    if any(k in base for k in ("billetera", "cartera", "cuero", "tarjetas")):
        add("Porta-tarjetas slim", "Compacto y elegante para uso diario.")
    if any(k in base for k in ("gato", "mascota", "rascador", "arena")):
        add("Accesorios para su gato", "Snacks o rascador pequeño.")
    if any(k in base for k in ("café", "cafetera", "espresso")):
        add("Set de café en casa", "Filtros o café de especialidad.")
    if any(k in base for k in ("gaming", "videojuego", "steam", "play")):
        add("Tarjeta regalo gaming", "Crédito digital para juegos.")

    while len(ideas) < 3:
        add("Tarjeta regalo general", "Sirve para cualquier ocasión.")

    return ideas[:3]


# ==============================
# IA con OLLAMA
# ==============================
def _usar_ollama(nombre_usuario: str, datos_para_ia: str, max_tokens: int) -> List[Dict[str, str]]:
    prompt = (
        "Eres GifterAI, experto en regalos.\n"
        f"Crea EXACTAMENTE 3 ideas de regalo para {nombre_usuario} basadas en:\n"
        f"{datos_para_ia}\n\n"
        "Responde en JSON válido:\n"
        "{\n"
        "  \"ideas\": [\n"
        "    {\"idea\": \"Texto\", \"explicacion\": \"Texto\"},\n"
        "    ... 3 ítems ...\n"
        "  ]\n"
        "}\n"
        "No agregues nada antes ni después del JSON."
    )

    try:
        raw = ollama_chat(
            messages=[
                {"role": "system", "content": "Eres GifterAI, experto en regalos."},
                {"role": "user", "content": prompt},
            ],
            model=OLLAMA_MODEL,
            temperature=0.5,
        )

        if not raw:
            return []

        # 1) Intentar JSON primero
        cleaned = _clean_json_block(raw)
        try:
            data = json.loads(cleaned)
            ideas_json = data.get("ideas", [])

            ideas_validas = [
                {"idea": i.get("idea", "").strip(), "explicacion": i.get("explicacion", "").strip()}
                for i in ideas_json
                if i.get("idea")
            ]

            if ideas_validas:
                return ideas_validas[:3]

        except Exception:
            pass  # no era JSON → fallback bullets

        # 2) Fallback bullets
        ideas = _parse_bullets(raw)
        return ideas[:3]

    except Exception as e:
        logger.error("[GifterAI] Error usando OLLAMA: %s", e)
        return []


# ==============================
# API pública
# ==============================
def generar_sugerencias_regalo(nombre_usuario: str, datos_para_ia: str, max_tokens: int = 180) -> List[Dict[str, str]]:
    datos = _sanitize(datos_para_ia)
    if not datos:
        return []

    key = _cache_key(nombre_usuario, datos)
    cached = cache.get(key)
    if cached:
        return cached

    ideas = _usar_ollama(nombre_usuario, datos, max_tokens)

    if not ideas:
        ideas = _fallback_sugerencias(nombre_usuario, datos)

    cache.set(key, ideas, CACHE_TTL)
    return ideas
