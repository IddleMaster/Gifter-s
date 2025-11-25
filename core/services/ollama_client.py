import requests
from django.conf import settings

BASE_URL = getattr(settings, "OLLAMA_URL", "http://ollama:11434")


def _extract_content(data: dict) -> str:
    """
    Extrae el texto de respuesta desde cualquier formato posible de Ollama.
    """
    # Formato estándar de /api/chat
    if "message" in data and "content" in data["message"]:
        return data["message"]["content"]

    # Algunos modelos devuelven "messages": [...]
    if "messages" in data and isinstance(data["messages"], list):
        for m in data["messages"]:
            if "content" in m:
                return m["content"]

    # Algunos devuelven "response"
    if "response" in data:
        return data["response"]

    # A veces viene plano con "content"
    if "content" in data:
        return data["content"]

    # Multimodal o versiones muy nuevas
    if "output_text" in data:
        return data["output_text"]

    return ""


def ollama_chat(messages, model="llama3.2:1b", temperature=0.6):
    """
    Cliente universal y robusto para el endpoint /api/chat de Ollama.
    Siempre retorna solo el texto de respuesta.
    """
    url = f"{BASE_URL}/api/chat"

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }

    try:
        r = requests.post(url, json=payload, timeout=35)
        r.raise_for_status()
        data = r.json()
        return _extract_content(data).strip()

    except Exception as e:
        print("[OLLAMA ERROR]", e)
        return ""
