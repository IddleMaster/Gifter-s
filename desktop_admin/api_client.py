import requests
import json
import os # <-- AÑADIR ESTA LÍNEA

class ApiClient:
    """
    Gestor de comunicación con La API REST del proyecto xiquillos!
    """
    def __init__(self, base_url="http://127.0.0.1:8000/api"):
        self.base_url = base_url
        self.token = None
        self.headers = {'Content-Type': 'application/json'}

    def login(self, username, password):
        """
        Autenticación al administrador contra la API y guarda el token JWT.
        """
        try:
            # Asumimos que tienes un endpoint de token como el de JWT o SimpleJWT
            # CAMBIO CLAVE: Usa 'json=' en lugar de 'data='
            response = requests.post(f"{self.base_url}/token/", json={
                "correo": username,
                "password": password
            })

            if response.status_code == 200:
                self.token = response.json().get('access')
                if not self.token:
                    return False, "La respuesta de la API no contiene un token de acceso."
                
                # A partir de ahora, todas las peticiones incluirán el token
                self.headers['Authorization'] = f'Bearer {self.token}'
                return True, "Login exitoso."
            else:
                return False, f"Error de autenticación: {response.status_code} - {response.text}"
        except requests.exceptions.RequestException as e:
            return False, f"No se pudo conectar con el servidor: {e}"

    # ... (el resto del archivo no necesita cambios)
    def get_products(self):
        """
        Obtiene TODOS los productos desde la API, manejando paginación
        o una lista plana si no hay paginación.
        """
        if not self.token:
            return None, "No autenticado."
        
        all_products = []
        page = 1
        first_request = True # Flag to check response type only once
        
        while True: 
            try:
                url = f"{self.base_url}/productos/?page={page}" 
                self.headers['Accept'] = 'application/json' 
                response = requests.get(url, headers=self.headers)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # --- Check if response is paginated (dictionary) or flat (list) ---
                    if isinstance(data, dict): # Paginated Case
                        products_on_page = data.get('results', []) 
                        all_products.extend(products_on_page)
                        if data.get('next') is None:
                            break 
                        else:
                            page += 1 
                    elif isinstance(data, list) and first_request: # Flat List Case (only on first request)
                        all_products = data # The whole list was returned at once
                        break # No more pages to fetch
                    elif first_request: # Unexpected format on first request
                         return None, f"Formato de respuesta inesperado de la API: {type(data)}"
                    else: # If it was paginated before, it shouldn't suddenly become a list
                        break # Assume end of pages if format changes unexpectedly after page 1

                elif response.status_code == 404:
                     # If 404 on the very first page, the endpoint is wrong.
                     if page == 1:
                         return None, f"Error al obtener productos: {response.status_code} - Not Found. ¿La URL {self.base_url}/productos/ es correcta?"
                     # If 404 on subsequent pages, it means we've reached the end.
                     else:
                         break
                else:
                    error_detail = response.text
                    try: 
                        error_detail = response.json().get('detail', response.text)
                    except json.JSONDecodeError:
                        pass 
                    return None, f"Error al obtener productos (página {page}): {response.status_code} - {error_detail}"
            except requests.exceptions.RequestException as e:
                return None, f"Error de conexión: {e}"
            except json.JSONDecodeError as e:
                return None, f"Error al decodificar JSON de la API: {e} - Respuesta recibida: {response.text}"
            
            first_request = False # No longer the first request after the first loop iteration

        return all_products, None

    def upload_products_csv(self, file_path):
        """
        Sube un archivo CSV al endpoint de importación de la API.
        """
        if not self.token:
            return False, "No autenticado."
        
        # Necesitaremos un endpoint específico para esto en Django
        # Por ahora, solo preparamos la lógica del cliente
        upload_url = f"{self.base_url}/admin/upload-csv/" 
        
        try:
            with open(file_path, 'rb') as f:
                # Usamos 'multipart/form-data' para enviar archivos
                files = {'csv_file': (os.path.basename(file_path), f, 'text/csv')}
                # No enviamos el header de JSON, 'requests' lo gestiona
                auth_header = {'Authorization': self.headers['Authorization']}
                
                response = requests.post(upload_url, files=files, headers=auth_header)

            if response.status_code == 200 or response.status_code == 201:
                return True, "Archivo CSV subido. La importación ha comenzado."
            else:
                return False, f"Error al subir el archivo: {response.status_code} - {response.text}"
        except FileNotFoundError:
            return False, "Archivo no encontrado en la ruta especificada."
        except requests.exceptions.RequestException as e:
            return False, f"Error de conexión: {e}"
    def update_product(self, product_id, field_name, new_value):
        """
        Envía una actualización parcial (PATCH) para un producto específico a la API.
        """
        if not self.token:
            return False, "No autenticado."

        update_url = f"{self.base_url}/productos/{product_id}/" # URL para actualizar un producto específico

        # Mapear el nombre de la columna de la tabla al nombre del campo en la API/Modelo
        # Asegúrate de que estos nombres coincidan con los campos en tu ProductoSerializer
        field_mapping = {
            "Nombre": "nombre_producto",
            "Precio": "precio",
            "Categoría": "id_categoria", # O 'categoria_nombre' si la API lo permite
            "Marca": "id_marca",         # O 'marca_nombre' si la API lo permite
            # Añade otros campos si es necesario
        }

        api_field_name = field_mapping.get(field_name)
        if not api_field_name:
            return False, f"Campo '{field_name}' no es editable o no está mapeado."

        # Preparar los datos a enviar (solo el campo que cambió)
        data_to_send = {
            api_field_name: new_value
        }

        # Validar y convertir tipos si es necesario (ej. Precio a número)
        if api_field_name == 'precio':
            try:
                data_to_send[api_field_name] = float(new_value.replace(',', '.')) # Intenta convertir a float
            except ValueError:
                return False, f"Valor de precio inválido: '{new_value}'. Debe ser un número."
        # Podrías necesitar validaciones similares para ID de categoría/marca si editas esos

        try:
            # Usamos PATCH para actualizaciones parciales
            response = requests.patch(update_url, json=data_to_send, headers=self.headers)

            if response.status_code == 200:
                return True, "Producto actualizado correctamente."
            else:
                # Intentar obtener un mensaje de error más detallado del JSON
                error_detail = response.text
                try:
                    error_data = response.json()
                    # DRF a menudo devuelve errores por campo
                    if isinstance(error_data, dict):
                         error_detail = "; ".join([f"{k}: {v[0]}" for k, v in error_data.items()])
                    elif isinstance(error_data.get('detail'), str):
                         error_detail = error_data['detail']
                except json.JSONDecodeError:
                    pass # Usar el texto plano si no es JSON

                return False, f"Error al actualizar producto: {response.status_code} - {error_detail}"
        except requests.exceptions.RequestException as e:
            return False, f"Error de conexión al actualizar: {e}"
        
    def get_users(self):
        """
        Obtiene TODOS los usuarios desde la API /api/users/, manejando paginación
        o una lista plana si no hay paginación.
        """
        if not self.token:
            return None, "No autenticado."
        
        all_users = []
        page = 1
        first_request = True 
        
        while True: 
            try:
                # Usa la nueva URL para usuarios
                url = f"{self.base_url}/users/?page={page}" 
                self.headers['Accept'] = 'application/json' 
                response = requests.get(url, headers=self.headers)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if isinstance(data, dict): # Caso paginado
                        users_on_page = data.get('results', []) 
                        all_users.extend(users_on_page)
                        if data.get('next') is None:
                            break 
                        else:
                            page += 1 
                    elif isinstance(data, list) and first_request: # Caso lista plana
                        all_users = data 
                        break 
                    elif first_request: 
                         return None, f"Formato de respuesta inesperado de la API de usuarios: {type(data)}"
                    else: 
                        break 

                elif response.status_code == 404:
                     if page == 1:
                         return None, f"Error al obtener usuarios: {response.status_code} - Not Found. ¿La URL {self.base_url}/users/ es correcta?"
                     else:
                         break # Fin de las páginas
                else:
                    error_detail = response.text
                    try: 
                        error_detail = response.json().get('detail', response.text)
                    except json.JSONDecodeError:
                        pass 
                    return None, f"Error al obtener usuarios (página {page}): {response.status_code} - {error_detail}"
            except requests.exceptions.RequestException as e:
                return None, f"Error de conexión: {e}"
            except json.JSONDecodeError as e:
                return None, f"Error al decodificar JSON de la API de usuarios: {e} - Respuesta recibida: {response.text}"
            
            first_request = False

        return all_users, None

    def update_user(self, user_id, field_name, new_value):
        """
        Envía una actualización parcial (PATCH) para un usuario específico a la API.
        """
        if not self.token:
            return False, "No autenticado."
            
        # Usa la URL de detalle para usuarios
        update_url = f"{self.base_url}/users/{user_id}/" 
        
        # Mapear columnas de tabla a campos de API (del AdminUserSerializer)
        field_mapping = {
            "Nombre": "nombre",
            "Apellido": "apellido",
            "Username": "nombre_usuario", # Asumiendo que quieres editar 'nombre_usuario'
            "Es Admin": "es_admin",       # Tu campo personalizado
            "Is Staff": "is_staff",       # Campo de Django admin
            "Is Active": "is_active",     # Para activar/desactivar
        }
        
        api_field_name = field_mapping.get(field_name)
        if not api_field_name:
            # Si el campo no está en el mapeo, no es editable (como ID o Correo)
            return False, f"Campo '{field_name}' no es editable."

        # Preparar datos (solo el campo cambiado)
        data_to_send = {
            api_field_name: new_value
        }

        # Validar y convertir booleanos (is_active, is_staff, es_admin)
        if api_field_name in ['is_active', 'is_staff', 'es_admin']:
            # Aceptar "True", "true", "1", "Verdadero", "Sí" como verdadero
            if isinstance(new_value, str) and new_value.lower() in ['true', '1', 'verdadero', 'sí', 'si']:
                 data_to_send[api_field_name] = True
            # Aceptar "False", "false", "0", "Falso", "No" como falso
            elif isinstance(new_value, str) and new_value.lower() in ['false', '0', 'falso', 'no']:
                 data_to_send[api_field_name] = False
            # Si ya es booleano, está bien
            elif isinstance(new_value, bool):
                 data_to_send[api_field_name] = new_value
            else:
                 return False, f"Valor inválido para '{field_name}'. Use True/False, 1/0, etc."

        try:
            response = requests.patch(update_url, json=data_to_send, headers=self.headers)

            if response.status_code == 200:
                return True, "Usuario actualizado correctamente."
            else:
                error_detail = response.text
                try:
                    error_data = response.json()
                    if isinstance(error_data, dict):
                         error_detail = "; ".join([f"{k}: {v[0]}" for k, v in error_data.items()])
                    elif isinstance(error_data.get('detail'), str):
                         error_detail = error_data['detail']
                except json.JSONDecodeError:
                    pass 
                return False, f"Error al actualizar usuario: {response.status_code} - {error_detail}"
        except requests.exceptions.RequestException as e:
            return False, f"Error de conexión al actualizar usuario: {e}"
    def delete_product(self, product_id):
        """
        Envía una petición DELETE para borrar un producto específico a la API.
        """
        if not self.token:
            return False, "No autenticado."
    
        delete_url = f"{self.base_url}/productos/{product_id}/" # Misma URL que para actualizar/ver detalle
    
        try:
            response = requests.delete(delete_url, headers=self.headers)
    
            # DELETE exitoso usualmente devuelve 204 No Content
            if response.status_code == 204:
                return True, "Producto borrado correctamente."
            elif response.status_code == 404:
                 return False, f"Error al borrar: Producto con ID {product_id} no encontrado."
            else:
                # Intentar obtener un mensaje de error más detallado
                error_detail = response.text
                try:
                    error_data = response.json()
                    if isinstance(error_data.get('detail'), str):
                         error_detail = error_data['detail']
                except json.JSONDecodeError:
                    pass
                return False, f"Error al borrar producto: {response.status_code} - {error_detail}"
        except requests.exceptions.RequestException as e:
            return False, f"Error de conexión al borrar: {e}"    
        
    def download_product_report(self, report_format='csv'): # cite: Sex.txt
        """
        Descarga el reporte CSV o PDF de productos activos desde la API,
        llamando a la URL específica para cada formato.
        """
        if not self.token: # cite: Sex.txt
            return None, "No autenticado." # cite: Sex.txt

        # --- Elegir la URL correcta ---
        if report_format == 'pdf':
            report_url = f"{self.base_url}/reports/products/download/pdf/" # URL para PDF
        else: # Default a CSV
            report_url = f"{self.base_url}/reports/products/download/" # URL para CSV (sin ?format=)
        # -----------------------------

        try:
            temp_headers = self.headers.copy() # cite: Sex.txt
            if 'Content-Type' in temp_headers: del temp_headers['Content-Type'] # cite: Sex.txt
            if 'Accept' in temp_headers: del temp_headers['Accept'] # cite: Sex.txt

            response = requests.get(report_url, headers=temp_headers, stream=True) # cite: Sex.txt
            response.raise_for_status() # cite: Sex.txt

            # Verificar Content-Type esperado (CSV o PDF)
            content_type = response.headers.get('content-type', '').lower() # cite: Sex.txt
            expected_content_type = 'csv' if report_format == 'csv' else 'pdf' # cite: Sex.txt

            if expected_content_type not in content_type: # cite: Sex.txt
                 try: # cite: Sex.txt
                     error_data = response.json() # cite: Sex.txt
                     error_detail = error_data.get("error", f"Respuesta inesperada (esperaba {report_format.upper()}).") # cite: Sex.txt
                 except json.JSONDecodeError: # cite: Sex.txt
                     error_detail = f"Respuesta inesperada del servidor (no es {expected_content_type})." # cite: Sex.txt
                 return None, error_detail # cite: Sex.txt

            return response.content, None # cite: Sex.txt

        # --- Manejo de errores (igual que antes) ---
        except requests.exceptions.HTTPError as http_err: # cite: Sex.txt
             # ... (código existente) ...
             error_detail = http_err.response.text # cite: Sex.txt
             try: # cite: Sex.txt
                 error_data = http_err.response.json() # cite: Sex.txt
                 error_detail = error_data.get("error", error_data.get("detail", http_err.response.text)) # cite: Sex.txt
             except json.JSONDecodeError: # cite: Sex.txt
                 pass # cite: Sex.txt
             return None, f"Error del servidor ({http_err.response.status_code}): {error_detail}" # cite: Sex.txt
        except requests.exceptions.RequestException as e: # cite: Sex.txt
            return None, f"Error de conexión: {e}" # cite: Sex.txt
        except Exception as e: # cite: Sex.txt
             return None, f"Error inesperado: {str(e)}" # cite: Sex.txt
         
    def create_product(self, product_data):
        """
        Envía una petición POST para crear un nuevo producto.
        product_data debe ser un diccionario con los campos:
        'nombre_producto', 'descripcion', 'precio', 'id_categoria', 'id_marca'
        """
        if not self.token:
            return None, "No autenticado."
    
        create_url = f"{self.base_url}/productos/" # URL de la lista/creación
    
        # Validar y convertir tipos (similar a update_product)
        try:
            if 'precio' in product_data and product_data['precio'] is not None:
                product_data['precio'] = float(str(product_data['precio']).replace(',', '.'))
            if 'id_categoria' in product_data:
                product_data['id_categoria'] = int(product_data['id_categoria'])
            if 'id_marca' in product_data:
                product_data['id_marca'] = int(product_data['id_marca'])
        except (ValueError, TypeError) as e:
            return None, f"Datos inválidos para crear producto: {e}"
    
        try:
            response = requests.post(create_url, json=product_data, headers=self.headers)
    
            # POST exitoso usualmente devuelve 201 Created
            if response.status_code == 201:
                new_product_info = response.json() # La API devuelve los datos del producto creado
                return new_product_info, "Producto creado exitosamente."
            else:
                # Intentar obtener mensaje de error detallado
                error_detail = response.text
                try:
                    error_data = response.json()
                    if isinstance(error_data, dict):
                         # Errores por campo de DRF
                         error_detail = "; ".join([f"{k}: {v[0]}" for k, v in error_data.items()])
                    elif isinstance(error_data.get('detail'), str):
                         error_detail = error_data['detail']
                except json.JSONDecodeError:
                    pass
                return None, f"Error al crear producto: {response.status_code} - {error_detail}"
    
        except requests.exceptions.RequestException as e:
            return None, f"Error de conexión al crear producto: {e}"
    # Puedes añadir más métodos según las necesidades de tu aplicación