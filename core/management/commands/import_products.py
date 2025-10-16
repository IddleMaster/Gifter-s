import csv
import os
import chardet
from django.core.management.base import BaseCommand
from core.models import Producto, Categoria, Marca, UrlTienda
from django.utils import timezone
import requests
from django.core.files.base import ContentFile

# Define los campos requeridos y los posibles nombres que pueden tener en el CSV.
# Esto hace el script flexible a diferentes formatos de archivo.
REQUIRED_FIELDS = {
    'id_producto': ['id_producto', 'product_id', 'ID', 'SKU'],
    'nombre_producto': ['nombre_producto', 'nombre', 'product_name', 'Title'],
    'descripcion': ['descripcion', 'description', 'cuerpo', 'body'],
    'id_categoria': ['id_categoria', 'category_id', 'categoría', 'id categoria'],
    'id_marca': ['id_marca', 'brand_id', 'marca', 'id marca'],
}

# Define campos opcionales que, si existen, se procesarán.
OPTIONAL_FIELDS = {
    'precio': ['precio', 'price', 'valor'],
    'url_tienda': ['url_tienda', 'url', 'link', 'product_url'],
    'url_imagen': ['url_imagen', 'imagen_url', 'image_url', 'imagen']
}


class Command(BaseCommand):
    help = 'Importa productos desde un archivo CSV de forma inteligente y robusta.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Ruta al archivo CSV a importar')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Valida el archivo CSV, el mapeo de columnas y los datos sin guardarlos en la base de datos.'
        )

    def detect_encoding(self, file_path):
        """Detecta la codificación del archivo para evitar errores de lectura."""
        with open(file_path, 'rb') as file:
            raw_data = file.read(10000) # Leer solo los primeros 10KB es suficiente
            result = chardet.detect(raw_data)
            encoding = result['encoding']
            self.stdout.write(f"Codificación detectada: {encoding} (confianza: {result['confidence']:.2f})")
            return encoding

    def detect_delimiter(self, file_path, encoding):
        """Detecta el delimitador (coma o punto y coma) analizando la primera línea."""
        with open(file_path, 'r', encoding=encoding) as file:
            first_line = file.readline()
        delimiters = [';', ',', '\t', '|']
        counts = {delim: first_line.count(delim) for delim in delimiters}
        detected_delimiter = max(counts, key=counts.get)
        self.stdout.write(f"Delimitador detectado: '{detected_delimiter}'")
        return detected_delimiter

    def find_column_mapping(self, csv_headers):
        """Analiza las cabeceras del CSV y las mapea a los campos definidos en el script."""
        mapping = {}
        missing_fields = []
        all_fields = {**REQUIRED_FIELDS, **OPTIONAL_FIELDS}
        
        # Normalizar cabeceras del CSV para una comparación robusta
        normalized_headers = {h.lower().strip(): h for h in csv_headers}

        for field, possible_names in all_fields.items():
            found = False
            for name in possible_names:
                if name.lower() in normalized_headers:
                    mapping[field] = normalized_headers[name.lower()]
                    found = True
                    break
            
            if not found and field in REQUIRED_FIELDS:
                missing_fields.append(field)
        
        return mapping, missing_fields

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        
        if not os.path.exists(csv_file_path):
            self.stdout.write(self.style.ERROR(f'El archivo {csv_file_path} no existe'))
            return

        try:
            encoding = self.detect_encoding(csv_file_path) or 'utf-8'
            delimiter = self.detect_delimiter(csv_file_path, encoding)
            
            with open(csv_file_path, 'r', encoding=encoding) as file:
                # Usamos csv.reader para obtener solo las cabeceras primero
                temp_reader = csv.reader(file, delimiter=delimiter)
                try:
                    headers = next(temp_reader)
                except StopIteration:
                    self.stdout.write(self.style.ERROR("El archivo CSV está vacío."))
                    return
                
                # Volvemos al inicio del archivo para usar DictReader después
                file.seek(0)
                
                mapping, missing = self.find_column_mapping(headers)

                if missing:
                    self.stdout.write(self.style.ERROR(f"¡Validación fallida! Faltan columnas requeridas: {', '.join(missing)}"))
                    self.stdout.write(f"Cabeceras encontradas en el CSV: {headers}")
                    return

                self.stdout.write(self.style.SUCCESS("✓ Mapeo de columnas exitoso:"))
                for key, value in mapping.items():
                    self.stdout.write(f"  - Campo '{key}' se leerá de la columna '{value}'")

                if options['dry_run']:
                    self.stdout.write(self.style.WARNING("\nModo --dry-run activado. No se realizarán cambios en la base de datos."))
                    # Aquí podrías agregar una validación de las primeras N filas si quisieras
                    return

                # --- INICIO DE LA LÓGICA DE PROCESAMIENTO ---
                csv_reader = csv.DictReader(file, delimiter=delimiter)
                
                productos_creados = 0
                productos_actualizados = 0
                errores = []
                error_file_path = 'import_errors.csv'
                
                # Abrir archivo de errores
                with open(error_file_path, 'w', newline='', encoding='utf-8') as error_file:
                    error_writer = csv.writer(error_file)
                    error_writer.writerow(headers + ['error_detalle'])

                    for row_num, row in enumerate(csv_reader, start=2):
                        try:
                            # Obtener o crear Categoría
                            categoria_id_val = row[mapping['id_categoria']].strip()
                            if not categoria_id_val.isdigit():
                                raise ValueError(f"id_categoria '{categoria_id_val}' no es un número válido.")
                            categoria, _ = Categoria.objects.get_or_create(
                                id_categoria=int(categoria_id_val),
                                defaults={'nombre_categoria': f'Categoría {categoria_id_val}', 'descripcion': 'Importada desde CSV'}
                            )

                            # Obtener o crear Marca
                            marca_id_val = row[mapping['id_marca']].strip()
                            if not marca_id_val.isdigit():
                                raise ValueError(f"id_marca '{marca_id_val}' no es un número válido.")
                            marca, _ = Marca.objects.get_or_create(
                                id_marca=int(marca_id_val),
                                defaults={'nombre_marca': f'Marca {marca_id_val}'}
                            )

                            # Preparar datos del producto
                            producto_data = {
                                'nombre_producto': row[mapping['nombre_producto']].strip(),
                                'descripcion': row[mapping['descripcion']].strip(),
                                'id_categoria': categoria,
                                'id_marca': marca,
                            }
                            
                            # Manejar precio (opcional)
                            if 'precio' in mapping:
                                precio_str = row[mapping['precio']].strip()
                                if precio_str:
                                    precio_limpio = precio_str.replace('$', '').replace('.', '').replace(',', '.').strip()
                                    try:
                                        producto_data['precio'] = float(precio_limpio)
                                    except (ValueError, TypeError):
                                        self.stdout.write(self.style.WARNING(f'Fila {row_num}: Precio inválido "{precio_str}", se dejará en blanco.'))
                                        producto_data['precio'] = None

                            # Crear o actualizar producto
                            producto_id_val = row[mapping['id_producto']].strip()
                            if not producto_id_val.isdigit():
                                raise ValueError(f"id_producto '{producto_id_val}' no es un número válido.")

                            producto, created = Producto.objects.update_or_create(
                                id_producto=int(producto_id_val),
                                defaults=producto_data
                            )

                            if created:
                                productos_creados += 1
                                self.stdout.write(self.style.SUCCESS(f'✓ Creado: {producto.nombre_producto}'))
                            else:
                                productos_actualizados += 1
                                self.stdout.write(self.style.NOTICE(f'↻ Actualizado: {producto.nombre_producto}'))

                            # Manejar URL de tienda (opcional)
                            if 'url_tienda' in mapping and row[mapping['url_tienda']].strip():
                                UrlTienda.objects.update_or_create(
                                    producto=producto,
                                    url=row[mapping['url_tienda']].strip(),
                                    defaults={'nombre_tienda': 'Tienda Principal', 'es_principal': True}
                                )
                            url_imagen = cleaned_row.get(mapping.get('url_imagen')) # Usamos .get para que no falle si no existe
                            if url_imagen:
                                try:
                                    response = requests.get(url_imagen, stream=True)
                                    if response.status_code == 200:
                                                                    # Obtener el nombre del archivo de la URL
                                        file_name = url_imagen.split('/')[-1]
                                        producto.imagen.save(file_name, ContentFile(response.content), save=True)
                                        self.stdout.write(self.style.SUCCESS(f"  ✓ Imagen descargada para {producto.nombre_producto}"))
                                except Exception as img_e:
                                    self.stdout.write(self.style.WARNING(f"  ! No se pudo descargar la imagen para {producto.nombre_producto}: {img_e}"))
                           
                        except Exception as e:
                            error_msg = f'Fila {row_num}: {str(e)}'
                            errores.append(error_msg)
                            self.stdout.write(self.style.ERROR(error_msg))
                            # Escribir la fila con error en el archivo de errores
                            error_writer.writerow(list(row.values()) + [str(e)])
                            continue

                # Resumen final
                self.stdout.write(self.style.SUCCESS(f'\n--- RESUMEN DE IMPORTACIÓN ---'))
                self.stdout.write(f'Productos creados: {productos_creados}')
                self.stdout.write(f'Productos actualizados: {productos_actualizados}')
                self.stdout.write(f'Errores: {len(errores)}')

                if errores:
                    self.stdout.write(self.style.WARNING(f'\nSe ha generado un archivo "{error_file_path}" con el detalle de los errores.'))

        except FileNotFoundError:
             self.stdout.write(self.style.ERROR(f"El archivo {csv_file_path} no fue encontrado."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error general al procesar el archivo: {str(e)}'))
