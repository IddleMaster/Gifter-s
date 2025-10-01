from django.core.management.base import BaseCommand
from core.models import Categoria

class Command(BaseCommand):
    help = 'Actualiza las categorías con nombres y descripciones reales'

    def handle(self, *args, **options):
        # Diccionario con categorías reales
        categorias_reales = {
            1: {
                'nombre': 'Tecnología',
                'descripcion': 'Dispositivos electrónicos, gadgets y accesorios tecnológicos'
            },
            2: {
                'nombre': 'Moda y Accesorios',
                'descripcion': 'Ropa, calzado, joyería y complementos de moda'
            },
            3: {
                'nombre': 'Hogar y Decoración',
                'descripcion': 'Artículos para el hogar, decoración y muebles'
            },
            4: {
                'nombre': 'Deportes y Aire Libre',
                'descripcion': 'Equipamiento deportivo, camping y actividades al aire libre'
            },
            5: {
                'nombre': 'Juguetes y Juegos',
                'descripcion': 'Juguetes, juegos de mesa y entretenimiento familiar'
            },
            6: {
                'nombre': 'Belleza y Cuidado Personal',
                'descripcion': 'Cosméticos, skincare y productos de cuidado personal'
            },
            7: {
                'nombre': 'Libros y Entretenimiento',
                'descripcion': 'Libros, música, películas y medios de entretenimiento'
            },
            8: {
                'nombre': 'Alimentos y Bebidas',
                'descripcion': 'Comidas gourmet, bebidas y productos alimenticios especiales'
            },
            9: {
                'nombre': 'Salud y Bienestar',
                'descripcion': 'Productos para la salud, fitness y bienestar general'
            },
            10: {
                'nombre': 'Viajes y Experiencias',
                'descripcion': 'Kits de viaje, experiencias y accesorios para viajeros'
            },
            11: {
                'nombre': 'Papeleria',
                'descripcion': 'Todo lo que tenga que ver con cuadernos, lápices, bolígrafos, planners, stickers, etc.'
            },
            12: {
                'nombre': 'Aficiones y Estilo de Vida',
                'descripcion': 'Todo lo que tenga que ver con Aficiones y Estilo de Vida'
            },
            
            # Agrega más según necesites
        }

        for cat_id, cat_data in categorias_reales.items():
            try:
                categoria, created = Categoria.objects.get_or_create(
                    id_categoria=cat_id,
                    defaults={
                        'nombre_categoria': cat_data['nombre'],
                        'descripcion': cat_data['descripcion']
                    }
                )
                
                if not created:
                    # Actualizar categoría existente
                    categoria.nombre_categoria = cat_data['nombre']
                    categoria.descripcion = cat_data['descripcion']
                    categoria.save()
                    self.stdout.write(f"✅ Actualizada: {cat_data['nombre']}")
                else:
                    self.stdout.write(f"✅ Creada: {cat_data['nombre']}")
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Error con categoría {cat_id}: {e}"))

        self.stdout.write(self.style.SUCCESS("🎉 Categorías actualizadas correctamente"))