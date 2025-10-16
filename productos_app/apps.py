
from django.apps import AppConfig

class ProductosAppConfig(AppConfig):
    name = "productos_app"
    verbose_name = "Productos"

    def ready(self):
        # Conectar señales de forma lazy
        from .signals import connect_signals
        connect_signals()
