
from django.apps import AppConfig



class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        # --- Activar señales del sistema ---
        from . import signals_users  # señales de usuarios
        from core.signals import gifter_ai_signals  # 🔮 nuevas señales GifterAI
        print("Signals imported successfully (users + GifterAI).")
