# core/services/profanity_filter.py
from openai import OpenAI

client = OpenAI()  # Usa OPENAI_API_KEY del entorno


SYSTEM_PROMPT = (
    "Eres un filtro de malas palabras para una red social en español y ingles. "
    "Tu trabajo es devolver el MISMO texto que recibes, pero con las "
    "malas palabras, garabatos e insultos fuertes censurados.\n\n"
    "Reglas:\n"
    "- Mantén el texto igual (mismos espacios, emojis y signos).\n"
    "- Cuando detectes una mala palabra, reemplaza sus letras centrales "
    "por asteriscos, dejando la primera y la última.\n"
    "  Ejemplos:\n"
    '  "weon" -> "w**n"\n'
    '  "qlo" -> "q*o"\n'
    '  "culiao" -> "c****o"\n'
    '  "fuck" -> "f*ck"\n'
    "- No agregues comentarios, explicaciones ni texto extra. "
    "Solo devuelve el texto censurado."
)


def censurar_con_openai(texto: str) -> str:
    if not texto:
        return texto

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",  # o el modelo que ya estés usando
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": texto},
        ],
    )

    return resp.choices[0].message.content.strip()
