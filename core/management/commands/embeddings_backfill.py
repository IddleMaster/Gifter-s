from django.core.management.base import BaseCommand
from core.models import Producto
from core.services.ai_recommender import ensure_product_embeddings

BATCH = 100  # ajusta si quieres

class Command(BaseCommand):
    help = "Genera embeddings para productos activos que aún no los tienen."

    def handle(self, *args, **options):
        qs = Producto.objects.filter(activo=True, embedding__isnull=True).order_by("pk")
        total = qs.count()
        self.stdout.write(f"Productos a embedir: {total}")

        start = 0
        while True:
            chunk = list(qs[start:start + BATCH])
            if not chunk:
                break
            ensure_product_embeddings(chunk)
            start += BATCH
            self.stdout.write(f"Progreso: {min(start, total)}/{total}")

        self.stdout.write(self.style.SUCCESS("Embeddings listos ✅"))
