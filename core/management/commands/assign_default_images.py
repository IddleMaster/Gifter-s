import os
import random
from django.core.management.base import BaseCommand
from django.core.files import File
from django.db import models
from core.models import Producto
from django.conf import settings

class Command(BaseCommand):
    help = 'Asigna imágenes por defecto a productos sin imagen'

    def get_available_images(self):
        """Obtiene todas las imágenes disponibles en core/static/img/Gifters/"""
        images_dir = os.path.join(settings.BASE_DIR, 'core', 'static', 'img', 'Gifters')
        available_images = []
        
        self.stdout.write(f"🔍 Buscando imágenes en: {images_dir}")
        
        if os.path.exists(images_dir):
            for filename in os.listdir(images_dir):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    available_images.append(filename)
                    self.stdout.write(f"   ✅ Encontrada: {filename}")
        else:
            self.stdout.write(f"❌ No se encontró la carpeta: {images_dir}")
            return []
            
        self.stdout.write(f"📸 Total de imágenes encontradas: {len(available_images)}")
        return available_images

    def get_image_for_product(self, product_name, available_images):
        """Asigna una imagen basada en el nombre del producto"""
        product_name_lower = product_name.lower()
        
        # Mapeo de palabras clave a imágenes específicas
        keyword_mapping = {
            'peluche': 'favicongift.png',
            'chocolate': 'trencito1.png', 
            'mascota': 'masterdogs.png',
            'lego': 'nissan-lego.png',
            'lentes': 'rayban.png',
            'polera': 'polera-lisa.png',
            'dron': 'dron-sonic.png',
            'maquillaje': 'maquillaje-lumi.png',
            'pelota': 'pelota-futbol.png',
            'reloj': 'reloj-festina.png',
            'auriculares': 'dron-sonic.png',
            'bufanda': 'polera-lisa.png',
            'gorro': 'polera-lisa.png',
            'manta': 'polera-lisa.png',
            'lampara': 'favicongift.png',
            'botella': 'favicongift.png',
            'kit': 'favicongift.png',
            'set': 'nissan-lego.png',
            'juego': 'nissan-lego.png',
            'caja': 'trencito1.png',
            'ramo': 'favicongift.png',
            'perfume': 'maquillaje-lumi.png',
            'velas': 'favicongift.png',
            'marco': 'favicongift.png',
            'agenda': 'favicongift.png',
            'vino': 'favicongift.png',
            'pulsera': 'reloj-festina.png',
            'collar': 'reloj-festina.png',
            'figura': 'nissan-lego.png',
        }
        
        # Buscar coincidencias de palabras clave
        for keyword, image_name in keyword_mapping.items():
            if keyword in product_name_lower and image_name in available_images:
                return image_name
        
        # Si no hay coincidencia, usar una imagen aleatoria
        if available_images:
            return random.choice(available_images)
        
        return 'favicongift.png'

    def handle(self, *args, **options):
        # VERIFICAR Y CREAR CARPETA MEDIA SI NO EXISTE
        media_dir = os.path.join(settings.BASE_DIR, 'media', 'productos')
        os.makedirs(media_dir, exist_ok=True)
        self.stdout.write(f"📁 Carpeta media verificada/creada: {media_dir}")
        
        # Obtener imágenes disponibles
        available_images = self.get_available_images()
        
        if not available_images:
            self.stdout.write(self.style.ERROR("❌ No se encontraron imágenes disponibles"))
            return

        # ENCONTRAR PRODUCTOS QUE REALMENTE NECESITAN IMAGEN
        productos_reales_sin_imagen = []
        
        for producto in Producto.objects.all():
            necesita_imagen = False
            
            if not producto.imagen:  # No tiene referencia en BD
                necesita_imagen = True
                self.stdout.write(f"🔍 {producto.nombre_producto}: Sin referencia en BD")
            else:  # Tiene referencia, verificar si el archivo existe
                try:
                    if not producto.imagen.storage.exists(producto.imagen.name):
                        necesita_imagen = True
                        self.stdout.write(f"🔍 {producto.nombre_producto}: Referencia existe pero archivo NO - {producto.imagen.name}")
                    else:
                        self.stdout.write(f"✅ {producto.nombre_producto}: Tiene imagen válida")
                except Exception as e:
                    necesita_imagen = True
                    self.stdout.write(f"⚠️ {producto.nombre_producto}: Error verificando archivo - {e}")
            
            if necesita_imagen:
                productos_reales_sin_imagen.append(producto)
        
        self.stdout.write(f"📦 Productos que necesitan imagen: {len(productos_reales_sin_imagen)}")
        
        if len(productos_reales_sin_imagen) == 0:
            self.stdout.write(self.style.SUCCESS("✅ Todos los productos ya tienen imagen válida"))
            return

        # ASIGNAR IMÁGENES A LOS PRODUCTOS QUE LAS NECESITAN
        for producto in productos_reales_sin_imagen:
            try:
                # Obtener imagen apropiada para el producto
                image_name = self.get_image_for_product(producto.nombre_producto, available_images)
                image_path = os.path.join(settings.BASE_DIR, 'core', 'static', 'img', 'Gifters', image_name)
                
                self.stdout.write(f"🖼️ Asignando '{image_name}' a: {producto.nombre_producto}")
                
                if os.path.exists(image_path):
                    # Si ya tiene una referencia corrupta, limpiarla primero
                    if producto.imagen:
                        try:
                            producto.imagen.delete(save=False)
                        except:
                            pass  # Ignorar errores al eliminar archivo corrupto
                    
                    with open(image_path, 'rb') as f:
                        filename = f"producto_{producto.id_producto}.png"
                        producto.imagen.save(filename, File(f), save=True)
                    
                    # Verificar que se creó correctamente
                    if producto.imagen and producto.imagen.storage.exists(producto.imagen.name):
                        self.stdout.write(f"   ✅ Imagen asignada y verificada: {producto.imagen.name}")
                    else:
                        self.stdout.write(f"   ❌ Error: Imagen no se guardó correctamente")
                else:
                    self.stdout.write(f"   ❌ Imagen no encontrada: {image_path}")
                    
            except Exception as e:
                self.stdout.write(f"❌ Error con {producto.nombre_producto}: {e}")

        # VERIFICACIÓN FINAL
        productos_con_imagen_valida = 0
        for producto in Producto.objects.all():
            if producto.imagen and producto.imagen.storage.exists(producto.imagen.name):
                productos_con_imagen_valida += 1
        
        self.stdout.write(self.style.SUCCESS(
            f"🎉 Proceso completado. {len(productos_reales_sin_imagen)} productos actualizados"
        ))
        self.stdout.write(f"📊 Resumen final: {productos_con_imagen_valida}/{Producto.objects.count()} productos con imagen válida")