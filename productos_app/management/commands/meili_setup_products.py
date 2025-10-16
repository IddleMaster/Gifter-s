from django.core.management.base import BaseCommand
from django.core.management.base import BaseCommand
from django.conf import settings
from core.search import meili

class Command(BaseCommand):
    help = "Crea/configura el índice Meilisearch para productos"

    def handle(self, *args, **kwargs):
        if not settings.USE_MEILI:
            self.stdout.write(self.style.WARNING("USE_MEILI=False → saltando configuración"))
            return

        idx = meili().index("products")
        idx.update_settings({
            "searchableAttributes": ["nombre_producto", "descripcion"],
            "filterableAttributes": ["id_categoria_id", "id_marca_id", "precio", "activo"],
            "sortableAttributes": ["precio"]
        })
        self.stdout.write(self.style.SUCCESS("Índice 'products' configurado"))

