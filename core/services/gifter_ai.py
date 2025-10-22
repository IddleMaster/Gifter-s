import re
import logging
from typing import List, Dict
from django.conf import settings
from core.services.openai_client import get_openai_client



logger = logging.getLogger(__name__)
BULLET_RE = re.compile(r"^\s*[-•]\s*(.+)$")

def _parse_bullets(texto: str) -> List[Dict[str, str]]:
    """
    Extrae pares {idea, explicacion} desde líneas tipo:
    - **Idea:** Explicación
    """
    out = []
    for raw in texto.splitlines():
        m = BULLET_RE.match(raw.strip())
        if not m:
            continue
        linea = m.group(1).strip()
        idea, explic = (linea.split(":", 1) + [""])[:2]
        out.append({"idea": idea.replace("**", "").strip(), "explicacion": explic.strip()})
    return [s for s in out if s["idea"]]

def generar_sugerencias_regalo(nombre_usuario: str, datos_para_ia: str, max_tokens: int = 180) -> List[Dict[str, str]]:
    """
    Llama a OpenAI (GPT-4o-mini) y devuelve hasta 3 ideas de regalo con explicación.
    Si falla o no hay datos, retorna [].
    """
    client = get_openai_client()
    if not client or not datos_para_ia:
        logger.info("[GifterAI] Sin cliente o datos; no se generan sugerencias.")
        return []

    prompt_user = (
        f"Eres GifterAI, experto en regalos.\n"
        f"Sugiere 3 ideas de regalos creativas para mi amigo {nombre_usuario}, "
        f"sabiendo esto:\n{datos_para_ia}\n"
        f"Explica brevemente por qué cada idea es buena. "
        f"Usa el formato: '- **[Idea]:** [Explicación].'"
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres GifterAI, experto en regalos."},
                {"role": "user", "content": prompt_user},
            ],
            max_tokens=max_tokens,
            temperature=0.7,
            n=1,
        )
        content = (resp.choices[0].message.content or "").strip()
        return _parse_bullets(content)[:3]
    except Exception as e:
        logger.exception("[GifterAI] Error OpenAI: %s", e)
        return []
