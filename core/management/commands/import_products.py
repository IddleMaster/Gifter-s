import csv
import os
import chardet
from django.core.management.base import BaseCommand
from core.models import Producto, Categoria, Marca, UrlTienda
from django.utils import timezone

class Command(BaseCommand):
    help = 'Importa productos desde un archivo CSV'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Ruta al archivo CSV a importar')

    def detect_encoding(self, file_path):
        """Detecta la codificación del archivo"""
        with open(file_path, 'rb') as file:
            raw_data = file.read()
            result = chardet.detect(raw_data)
            encoding = result['encoding']
            confidence = result['confidence']
            self.stdout.write(f"Codificación detectada: {encoding} (confianza: {confidence:.2f})")
            return encoding

    def detect_delimiter(self, file_path, encoding):
        """Detecta el delimitador del CSV"""
        with open(file_path, 'r', encoding=encoding) as file:
            first_line = file.readline()
            
        # Contar ocurrencias de delimitadores comunes
        delimiters = [';', ',', '\t', '|']
        counts = {delim: first_line.count(delim) for delim in delimiters}
        
        # Elegir el delimitador con más ocurrencias
        detected_delimiter = max(counts, key=counts.get)
        self.stdout.write(f"Delimitador detectado: '{detected_delimiter}' (ocurrencias: {counts[detected_delimiter]})")
        
        return detected_delimiter

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        
        if not os.path.exists(csv_file_path):
            self.stdout.write(self.style.ERROR(f'El archivo {csv_file_path} no existe'))
            return

        try:
            # Detectar codificación
            encoding = self.detect_encoding(csv_file_path)
            used_encoding = encoding if encoding else 'latin-1'
            self.stdout.write(f"Procesando con codificación: {used_encoding}")

            # Detectar delimitador
            delimiter = self.detect_delimiter(csv_file_path, used_encoding)
            
            with open(csv_file_path, 'r', encoding=used_encoding) as file:
                # Usar el delimitador detectado
                csv_reader = csv.DictReader(file, delimiter=delimiter)
                
                self.stdout.write("COLUMNAS ENCONTRADAS EN EL CSV:")
                self.stdout.write(f"{csv_reader.fieldnames}")
                
                productos_creados = 0
                productos_actualizados = 0
                errores = []

                for row_num, row in enumerate(csv_reader, start=2):
                    try:
                        # Limpiar los datos
                        cleaned_row = {k: v.strip() if isinstance(v, str) else v for k, v in row.items()}
                        
                        self.stdout.write(f"Procesando fila {row_num}: {cleaned_row.get('nombre_producto', 'N/A')}")

                        # Obtener o crear categoría
                        categoria_id = cleaned_row['id_categoria']
                        if not categoria_id:
                            raise ValueError("id_categoria está vacío")
                            
                        categoria, cat_created = Categoria.objects.get_or_create(
                            id_categoria=int(categoria_id),
                            defaults={
                                'nombre_categoria': f'Categoría {categoria_id}',
                                'descripcion': 'Importada desde CSV'
                            }
                        )

                        # Obtener o crear marca
                        marca_id = cleaned_row['id_marca']
                        if not marca_id:
                            raise ValueError("id_marca está vacío")
                            
                        marca, mar_created = Marca.objects.get_or_create(
                            id_marca=int(marca_id),
                            defaults={
                                'nombre_marca': f'Marca {marca_id}'
                            }
                        )

                        # Preparar datos del producto
                        producto_data = {
                            'nombre_producto': cleaned_row['nombre_producto'],
                            'descripcion': cleaned_row['descripcion'],
                            'id_categoria': categoria,
                            'id_marca': marca,
                            'activo': True,
                            'fecha_actualizacion': timezone.now()
                        }

                        # Manejar precio
                        precio_str = cleaned_row.get('precio', '')
                        if precio_str and precio_str.strip():
                            try:
                                precio_limpio = precio_str.replace('$', '').replace(',', '.').strip()
                                producto_data['precio'] = float(precio_limpio)
                            except ValueError:
                                self.stdout.write(
                                    self.style.WARNING(f'Fila {row_num}: Precio inválido "{precio_str}", usando NULL')
                                )
                                producto_data['precio'] = None
                        else:
                            producto_data['precio'] = None

                        # Verificar si el producto ya existe
                        producto_id = cleaned_row['id_producto']
                        if not producto_id:
                            raise ValueError("id_producto está vacío")
                            
                        producto_existente = Producto.objects.filter(id_producto=int(producto_id)).first()

                        if producto_existente:
                            # Actualizar producto existente
                            for key, value in producto_data.items():
                                setattr(producto_existente, key, value)
                            producto_existente.save()
                            productos_actualizados += 1
                            producto = producto_existente
                            self.stdout.write(self.style.WARNING(f'↻ Actualizado: {producto.nombre_producto}'))
                        else:
                            # Crear nuevo producto
                            producto_data['id_producto'] = int(producto_id)
                            producto = Producto.objects.create(**producto_data)
                            productos_creados += 1
                            self.stdout.write(self.style.SUCCESS(f'✓ Creado: {producto.nombre_producto}'))

                        # Manejar URL de tienda
                        url_tienda = cleaned_row.get('url_tienda', '')
                        if url_tienda and url_tienda.strip():
                            UrlTienda.objects.get_or_create(
                                producto=producto,
                                url=url_tienda,
                                defaults={
                                    'nombre_tienda': 'Tienda Principal',
                                    'es_principal': True,
                                    'activo': True
                                }
                            )

                    except Exception as e:
                        product_name = cleaned_row.get('nombre_producto', 'N/A')
                        error_msg = f'Fila {row_num}: Error procesando "{product_name}" - {str(e)}'
                        errores.append(error_msg)
                        self.stdout.write(self.style.ERROR(error_msg))
                        import traceback
                        self.stdout.write(self.style.ERROR(traceback.format_exc()))
                        continue

            # Resumen final
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n--- RESUMEN DE IMPORTACIÓN ---\n'
                    f'Productos creados: {productos_creados}\n'
                    f'Productos actualizados: {productos_actualizados}\n'
                    f'Errores: {len(errores)}\n'
                    f'Total procesado: {productos_creados + productos_actualizados + len(errores)}'
                )
            )

            if errores:
                self.stdout.write(self.style.WARNING('\n--- ERRORES DETALLADOS ---'))
                for error in errores:
                    self.stdout.write(self.style.ERROR(error))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error general al procesar el archivo: {str(e)}'))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))