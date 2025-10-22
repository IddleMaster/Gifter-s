# core/services/openai_client.py
from django.conf import settings
from openai import OpenAI

def get_openai_client(timeout_seconds: int = 8):
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        return None
    return OpenAI(api_key=api_key).with_options(timeout=timeout_seconds)
