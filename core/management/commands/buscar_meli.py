# Ubicación: core/management/commands/buscar_meli.py

import requests
import csv
import re
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Busca productos de prueba en Fake Store API y genera un CSV'

    def handle(self, *args, **options):
        
        # El CSV se guardará en la raíz del proyecto (donde está manage.py)
        NOMBRE_ARCHIVO = "productos_fake.csv" 
        
        # 1. URL de la API de FakeStore
        url_api = "https://fakestoreapi.com/products"

        self.stdout.write(self.style.SUCCESS(f"Obteniendo productos de prueba desde FakeStoreAPI..."))

        try:
            # 2. Hacer la petición a la API (esta no necesita headers)
            response = requests.get(url_api)
            response.raise_for_status()

            data = response.json()

            # 4. Preparar el archivo CSV
            with open(NOMBRE_ARCHIVO, 'w', newline='', encoding='utf-8') as csvfile:
                # Mismos fieldnames que tu importador espera
                fieldnames = [
                    'nombre_producto', 
                    'descripcion', 
                    'precio', 
                    'imagen_url', 
                    'store_url', 
                    'store_name'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
                writer.writeheader()

                # 5. Recorrer la lista de productos
                for item in data:
                    
                    # 6. Escribir la fila en el CSV
                    writer.writerow({
                        'nombre_producto': item.get('title', 'Sin Título'),
                        'descripcion': item.get('description', ''), 
                        'precio': item.get('price', 0),
                        'imagen_url': item.get('image', ''),
                        # Como no da URL de tienda, usamos la URL de la imagen como placeholder
                        'store_url': item.get('image', ''), 
                        'store_name': 'FakeStore'
                    })

            self.stdout.write(self.style.SUCCESS(f"¡Éxito! Se generó el archivo '{NOMBRE_ARCHIVO}' con {len(data)} productos."))

        except requests.exceptions.RequestException as e:
            self.stderr.write(self.style.ERROR(f"Error al conectar con la API: {e}"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Ocurrió un error inesperado: {e}"))