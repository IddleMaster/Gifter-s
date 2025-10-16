from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection
from core.search import meili

class Command(BaseCommand):
    help = "Reindexa todos los productos en Meilisearch (SQL crudo, sin importar el modelo)"

    def handle(self, *args, **kwargs):
        if not settings.USE_MEILI:
            self.stdout.write(self.style.WARNING("USE_MEILI=False → saltando reindexado"))
            return

        SQL = """
        SELECT 
            p.id_producto, 
            p.nombre_producto, 
            COALESCE(p.descripcion, '') as descripcion,
            p.id_categoria_id, 
            p.id_marca_id, 
            p.precio,
            p.activo
        FROM producto p
        """
        docs = []
        with connection.cursor() as cur:
            cur.execute(SQL)
            for row in cur.fetchall():
                (id_producto, nombre, descripcion, id_cat, id_marca, precio, activo) = row
                docs.append({
                    "id": id_producto,  # usamos 'id' como PK en Meili
                    "nombre_producto": nombre,
                    "descripcion": descripcion,
                    "id_categoria_id": id_cat,
                    "id_marca_id": id_marca,
                    "precio": float(precio) if precio is not None else None,
                    "activo": bool(activo),
                })

        if not docs:
            self.stdout.write(self.style.WARNING("No se encontraron productos en la tabla 'producto'"))
            return

        idx = meili().index("products")
        idx.add_documents(docs, primary_key="id")
        self.stdout.write(self.style.SUCCESS(f"{len(docs)} productos indexados (SQL crudo)"))
