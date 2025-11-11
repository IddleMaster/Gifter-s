import asyncio
import json
from django.core.management.base import BaseCommand
from core.models import ProductoExterno
from datetime import datetime
import os
import importlib.util

class Command(BaseCommand):
    help = "Importa productos desde Falabella usando el scraper local"

    def handle(self, *args, **options):
        self.stdout.write("🛍️  Iniciando scraping de Falabella...")

        # === 1. Cargar dinámicamente el scraper existente ===
        scraper_path = os.path.join(os.getcwd(), "falabella_scraper.py")
        spec = importlib.util.spec_from_file_location("falabella_scraper", scraper_path)
        scraper_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scraper_module)

        url = "https://www.falabella.com/falabella-cl/category/cat202303/Consolas?f.product.brandName=sony"

        # === 2. Ejecutar el scraper y obtener los datos ===
        data = asyncio.run(scraper_module.scrape_falabella(url))

        if not data:
            self.stdout.write(self.style.WARNING("⚠️ No se encontraron productos."))
            return

        nuevos = 0
        actualizados = 0

        # === 3. Guardar o actualizar productos ===
        for item in data:
            obj, created = ProductoExterno.objects.update_or_create(
                url=item.get("url"),
                defaults={
                    "nombre": item.get("name", "").strip()[:255],
                    "precio": item.get("price"),
                    "marca": item.get("brand"),
                    "categoria": item.get("category"),
                    "imagen": item.get("image"),
                    "fuente": "Falabella",
                    "fecha_extraccion": datetime.now(),
                },
            )
            if created:
                nuevos += 1
            else:
                actualizados += 1

        self.stdout.write(self.style.SUCCESS(f"✅ {nuevos} nuevos productos, {actualizados} actualizados."))
