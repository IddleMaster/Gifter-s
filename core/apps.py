# core/apps.py
from django.apps import AppConfig

# Ya no se necesitan las importaciones de settings, firebase_admin ni credentials

class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        # --- SE ELIMINÓ EL CÓDIGO DE FIREBASE ADMIN ---
        
        # importa para registrar los receivers (esto ya lo tenías)
        from . import signals_users
        print("Signals imported successfully.")