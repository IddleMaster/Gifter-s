import csv
import os
import chardet
from django.core.management.base import BaseCommand
from core.models import Producto, Categoria, Marca, UrlTienda
from django.utils import timezone
import requests
from django.core.files.base import ContentFile
from django.conf import settings # Para obtener BASE_DIR
from django.core.files import File # Para manejar archivos locales

# Define los campos requeridos y los posibles nombres que pueden tener en el CSV.
# Esto hace el script flexible a diferentes formatos de archivo.
REQUIRED_FIELDS = {
    # Cambia 'id_producto': ['id_producto', ...] por:
    'id_producto': ['id', 'id_producto', 'product_id', 'ID', 'SKU'],
    # Cambia 'nombre_producto': ['nombre_producto', ...] por:
    'nombre_producto': ['nombre', 'nombre_producto', 'product_name', 'Title'],
    # 'descripcion' ya está bien si tu CSV usa 'descripcion'
    'descripcion': ['descripcion', 'description', 'cuerpo', 'body'],
    # Cambia 'id_categoria': ['id_categoria', ...] por:
    'id_categoria': ['categoria', 'id_categoria', 'category_id', 'categoría', 'id categoria'],
    # Cambia 'id_marca': ['id_marca', ...] por:
    'id_marca': ['marca', 'id_marca', 'brand_id', 'id marca'],
}

# Define campos opcionales que, si existen, se procesarán.
OPTIONAL_FIELDS = {
    # 'precio' ya está bien si tu CSV usa 'precio'
    'precio': ['precio', 'price', 'valor'],
    # 'url_tienda' no está en tu CSV actual, pero lo dejamos por si acaso
    'url_tienda': ['url_tienda', 'url', 'link', 'product_url'],

    'url_imagen': ['imagen_url', 'url_imagen', 'image_url', 'imagen']
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
            raw_data = file.read(10000) # Leer los primeros 10KB
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
                            try:
                            # Obtener o crear Categoría POR NOMBRE
                            # (Asegúrate de que esta línea y las siguientes dentro del 'try'
                            # estén indentadas UN NIVEL MÁS que el 'try')
                                categoria_nombre = row[mapping['id_categoria']].strip()
                                if not categoria_nombre:
                                    raise ValueError("El nombre de la categoría no puede estar vacío.")
                                categoria, cat_created = Categoria.objects.get_or_create(
                                    nombre_categoria=categoria_nombre,
                                    defaults={'descripcion': f'Importada: {categoria_nombre}'}
                                )
                                if cat_created:
                                    self.stdout.write(f"  -> Creada nueva categoría: {categoria_nombre}")

                                # Obtener o crear Marca POR NOMBRE
                                marca_nombre = row[mapping['id_marca']].strip()
                                if not marca_nombre:
                                    raise ValueError("El nombre de la marca no puede estar vacío.")
                                marca, marca_created = Marca.objects.get_or_create(
                                    nombre_marca=marca_nombre
                                )
                                if marca_created:
                                    self.stdout.write(f"  -> Creada nueva marca: {marca_nombre}")

                            # (Asegúrate de que esta línea 'except' esté AL MISMO NIVEL que el 'try')
                            except KeyError as ke:
                                # (Esta línea y la siguiente indentadas UN NIVEL MÁS que el 'except')
                                raise ValueError(f"Falta la columna necesaria en el CSV: {ke}")
                            # (Asegúrate de que esta línea 'except' esté AL MISMO NIVEL que el 'try' y el 'except' anterior)
                            except ValueError as ve:
                                 # (Esta línea y la siguiente indentadas UN NIVEL MÁS que el 'except')
                                 raise ValueError(f"Error en categoría/marca: {ve}")

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
                            producto_id_val = None
                            if 'id_producto' in mapping and row.get(mapping['id_producto']):
                                 id_str = row[mapping['id_producto']].strip()
                                 if id_str.isdigit():
                                     producto_id_val = int(id_str)
                                 else:
                                     # Si hay un ID pero no es un número, registrar como error y saltar fila
                                     raise ValueError(f"id_producto '{id_str}' no es un número válido.")

                            if producto_id_val is not None:
                                # SI TENEMOS ID VÁLIDO: Usar update_or_create (comportamiento anterior)
                                producto, created = Producto.objects.update_or_create(
                                    id_producto=producto_id_val,
                                    defaults=producto_data
                                )
                                if created:
                                    productos_creados += 1
                                    self.stdout.write(self.style.SUCCESS(f'✓ Creado con ID={producto_id_val}: {producto.nombre_producto}'))
                                else:
                                    productos_actualizados += 1
                                    self.stdout.write(self.style.NOTICE(f'↻ Actualizado ID={producto_id_val}: {producto.nombre_producto}'))
                            else:
                                # SI NO TENEMOS ID VÁLIDO: Crear un nuevo producto (ID automático)
                                # Primero, verificamos si ya existe un producto con el mismo nombre para evitar duplicados simples
                                # (Podrías hacer esta verificación más robusta si lo necesitas)
                                existing_product = Producto.objects.filter(nombre_producto=producto_data['nombre_producto']).first()
                                if existing_product:
                                    producto = existing_product
                                    created = False
                                    # Opcional: Actualizar datos si ya existe por nombre
                                    # for key, value in producto_data.items():
                                    #    setattr(producto, key, value)
                                    # producto.save()
                                    # productos_actualizados += 1
                                    self.stdout.write(self.style.WARNING(f'→ Ya existe producto con nombre "{producto.nombre_producto}" (ID={producto.id_producto}). Fila ignorada (o actualizada, si descomentas el código).'))
                                    # Si decides ignorar, puedes añadir 'continue' aquí para saltar al siguiente
                                else:
                                    # Crear el nuevo producto (Django/DB asignará el ID)
                                    producto = Producto.objects.create(**producto_data)
                                    created = True
                                    productos_creados += 1
                                    self.stdout.write(self.style.SUCCESS(f'✓ Creado con ID automático={producto.id_producto}: {producto.nombre_producto}'))
                            # Manejar URL de tienda (opcional)
                            if 'url_tienda' in mapping and row[mapping['url_tienda']].strip():
                                UrlTienda.objects.update_or_create(
                                    producto=producto,
                                    url=row[mapping['url_tienda']].strip(),
                                    defaults={'nombre_tienda': 'Tienda Principal', 'es_principal': True}
                                )
                            url_imagen = row.get(mapping.get('url_imagen')) # Usamos .get para que no falle si no existe
                            if url_imagen:
                                url_imagen = url_imagen.strip() # Limpiar espacios
                                if url_imagen: # Doble chequeo por si queda vacío después de strip()
                                    try:
                                        # Intentar descargar la imagen desde la URL
                                        # Añadimos timeout y verificación de estado
                                        response = requests.get(url_imagen, stream=True, timeout=15) # Aumentado timeout por si acaso
                                        response.raise_for_status() # Lanza error para respuestas 4xx/5xx

                                        # raise_for_status() ya verifica esto, pero doble chequeo por si acaso
                                        # Obtener el nombre del archivo de la URL
                                        # Limpiamos posibles parámetros como ?s=... o #...
                                        file_name_from_url = url_imagen.split('/')[-1].split('?')[0].split('#')[0]
                                        # Usamos os.path.basename para asegurar un nombre válido
                                        file_name = os.path.basename(file_name_from_url)
                                        if not file_name: # Si la URL termina en / o algo raro
                                            file_name = f"image_{producto.id_producto_or_default}.jpg" # Nombre genérico

                                        # Guardar la imagen descargada usando ContentFile
                                        producto.imagen.save(file_name, ContentFile(response.content), save=True)
                                        self.stdout.write(self.style.SUCCESS(f"  ✓ Imagen descargada para {producto.nombre_producto}"))
                                        # else: # Esta parte ya no es necesaria por raise_for_status
                                            # self.stdout.write(self.style.WARNING(f"  ! Código de estado inesperado..."))

                                    except requests.exceptions.RequestException as req_e:
                                        # Error de conexión, timeout, URL inválida, 404, etc.
                                        self.stdout.write(self.style.WARNING(f"  ! No se pudo descargar la imagen para {producto.nombre_producto} desde {url_imagen}: {req_e}"))
                                        # Opcional: Podrías añadir este error a import_errors.csv si quieres
                                        # error_writer.writerow(list(row.values()) + [f"Error descarga imagen: {req_e}"])
                                    except Exception as img_e:
                                        # Otros errores (ej: al guardar en Django)
                                        self.stdout.write(self.style.WARNING(f"  ! Error al procesar imagen descargada para {producto.nombre_producto}: {img_e}"))
                                        # Opcional: Añadir a import_errors.csv
                                        # error_writer.writerow(list(row.values()) + [f"Error procesando imagen: {img_e}"])
                                else:
                                     self.stdout.write(self.style.NOTICE(f"  - Campo imagen_url vacío para {producto.nombre_producto}."))

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
