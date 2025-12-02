import requests
import json
import os 
import logging

from local_auth_cache import LocalAuthCache

# Creamos un logger específico para este módulo, lo que es una buena práctica.
logger = logging.getLogger(__name__)

class ApiClient:
    """
    Gestor de comunicación con La API REST del proyecto xiquillos!
    """
    def __init__(self, base_url="http://127.0.0.1:8000/api", local_auth_cache=None, timeout_seconds=10):
        self.base_url = base_url
        self.token = None
        # Mantenemos self.headers para compatibilidad, pero la función _get_auth_headers es la fuente de verdad.
        self.headers = {'Content-Type': 'application/json'} 
        self.local_auth_cache = local_auth_cache 
        self.logger = logger 
        
        # <<< --- SOLUCIÓN: Definir self.timeout --- >>>
        self.timeout = timeout_seconds  # <-- Soluciona el error 'no attribute timeout'
        # <<< ------------------------------------- >>>
        
        self.logger.info(f"ApiClient inicializado con base_url: {base_url}")
        

    def login(self, username, password):
        """
        Autenticación al administrador contra la API y guarda el token JWT.
        """
        try:
            response = requests.post(f"{self.base_url}/token/", json={
                "correo": username,
                "password": password
            })

            if response.status_code == 200:
                self.token = response.json().get('access')
                if not self.token:
                    logger.error("Login exitoso (200) pero no se encontró 'access' token en la respuesta.")
                    return False, "La respuesta de la API no contiene un token de acceso."
                
                self.headers['Authorization'] = f'Bearer {self.token}'
                if self.local_auth_cache:
                    try:
                        self.local_auth_cache.save_user_hash(username, password)
                    except Exception as e:
                        logging.error(f"No se pudo guardar el hash de la contraseña en caché: {e}")
                logger.info(f"Login exitoso para usuario: {username}")
                return True, "Login exitoso."
            else:
                logger.warning(f"Intento de login fallido para {username}. Status: {response.status_code}, Respuesta: {response.text}")
                return False, f"Error de autenticación: {response.status_code} - {response.text}"
        except requests.exceptions.RequestException as e:
            logger.critical(f"Fallo de conexión en login: {e}") # Error crítico de conexión
            return False, f"No se pudo conectar con el servidor: {e}"

    def get_product_detail(self, product_id):
        """
        Obtiene los detalles completos de un producto por su ID (GET /productos/{id}/).
        """
        if not self.token:
            logger.warning("get_product_detail llamado sin token.")
            return None, "No autenticado."
        
        detail_url = f"{self.base_url}/productos/{product_id}/"
        
        try:
            response = requests.get(detail_url, headers=self.headers)
            response.raise_for_status()
            logger.info(f"Detalles del producto {product_id} cargados exitosamente.")
            return response.json(), None
        except requests.exceptions.HTTPError as http_err:
            error_detail = http_err.response.text
            try:
                error_data = http_err.response.json()
                error_detail = error_data.get("detail", error_detail)
            except json.JSONDecodeError:
                pass
            logger.error(f"Error HTTP al obtener detalle del producto {product_id}. Status: {response.status_code}, Error: {error_detail}")
            return None, f"Error al cargar detalle: {response.status_code} - {error_detail}"
        except requests.exceptions.RequestException as e:
            logger.error(f"get_product_detail: Error de conexión: {e}", exc_info=True)
            return None, f"Error de conexión: {e}"


    def update_product_full(self, product_id, data):
        """
        Envía una actualización completa (PATCH) a un producto con el diccionario de datos.
        data debe contener: nombre_producto, descripcion, id_categoria, id_marca, imagen, etc.
        """
        if not self.token:
            logger.warning("update_product_full llamado sin token.")
            return False, "No autenticado."
        
        update_url = f"{self.base_url}/productos/{product_id}/" 
        
        try:
            logger.info(f"Intentando PATCH COMPLETO en {update_url} con {len(data)} campos.")
            response = requests.patch(update_url, json=data, headers=self.headers)

            if response.status_code == 200:
                logger.info(f"Producto {product_id} actualizado completamente.")
                return True, "Producto actualizado correctamente."
            else:
                error_detail = response.text
                try:
                    error_data = response.json()
                    if isinstance(error_data, dict):
                        # Manejo de errores de validación de DRF
                        error_detail = "; ".join([f"{k}: {v[0]}" for k, v in error_data.items()])
                    elif isinstance(error_data.get('detail'), str):
                        error_detail = error_data['detail']
                except json.JSONDecodeError:
                    pass 
                
                logger.error(f"Error al actualizar producto {product_id}. Status: {response.status_code}, Error: {error_detail}")
                return False, f"Error al actualizar producto: {response.status_code} - {error_detail}"
        except requests.exceptions.RequestException as e:
            logger.error(f"update_product_full: Error de conexión: {e}", exc_info=True)
            return False, f"Error de conexión al actualizar: {e}"
    def get_products(self):
        """
        Obtiene TODOS los productos desde la API...
        """
        if not self.token:
            logger.warning("get_products llamado sin token de autenticación.")
            return None, "No autenticado."
        
        all_products = []
        page = 1
        first_request = True
        
        while True: 
            try:
                url = f"{self.base_url}/productos/?page={page}" 
                self.headers['Accept'] = 'application/json' 
                response = requests.get(url, headers=self.headers)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if isinstance(data, dict): # Paginated Case
                        products_on_page = data.get('results', []) 
                        all_products.extend(products_on_page)
                        if data.get('next') is None:
                            break 
                        else:
                            page += 1 
                    elif isinstance(data, list) and first_request: # Flat List Case
                        all_products = data
                        break 
                    elif first_request: 
                        logger.error(f"get_products: Formato de respuesta inesperado. Tipo: {type(data)}")
                        return None, f"Formato de respuesta inesperado de la API: {type(data)}"
                    else: 
                        break 

                elif response.status_code == 404:
                    if page == 1:
                        logger.error(f"get_products falló (404) en la página 1. URL: {url}")
                        return None, f"Error al obtener productos: {response.status_code} - Not Found. ¿La URL {self.base_url}/productos/ es correcta?"
                    else:
                        break # Fin de las páginas
                else:
                    error_detail = response.text
                    try: 
                        error_detail = response.json().get('detail', response.text)
                    except json.JSONDecodeError:
                        pass 
                    logger.error(f"Error al obtener productos (página {page}): {response.status_code} - {error_detail}")
                    return None, f"Error al obtener productos (página {page}): {response.status_code} - {error_detail}"
            except requests.exceptions.RequestException as e:
                logger.error(f"get_products: Error de conexión: {e}")
                return None, f"Error de conexión: {e}"
            except json.JSONDecodeError as e:
                logger.error(f"get_products: Error al decodificar JSON. Respuesta: {response.text}", exc_info=True)
                return None, f"Error al decodificar JSON de la API: {e} - Respuesta recibida: {response.text}"
            
            first_request = False 

        logger.info(f"get_products: Se cargaron {len(all_products)} productos exitosamente.")
        return all_products, None

    def upload_products_csv(self, file_path):
        """
        Sube un archivo CSV al endpoint...
        """
        if not self.token:
            logger.warning("upload_products_csv llamado sin token.")
            return False, "No autenticado."
        
        upload_url = f"{self.base_url}/admin/upload-csv/" 
        
        try:
            with open(file_path, 'rb') as f:
                files = {'csv_file': (os.path.basename(file_path), f, 'text/csv')}
                auth_header = {'Authorization': self.headers['Authorization']}
                
                logger.info(f"Iniciando subida de CSV: {file_path}")
                response = requests.post(upload_url, files=files, headers=auth_header)

            if response.status_code == 200 or response.status_code == 201:
                logger.info(f"CSV {file_path} subido exitosamente.")
                return True, "Archivo CSV subido. La importación ha comenzado."
            else:
                logger.error(f"Error al subir CSV {file_path}. Status: {response.status_code}, Respuesta: {response.text}")
                return False, f"Error al subir el archivo: {response.status_code} - {response.text}"
        except FileNotFoundError:
            logger.error(f"upload_products_csv: Archivo no encontrado en {file_path}")
            return False, "Archivo no encontrado en la ruta especificada."
        except requests.exceptions.RequestException as e:
            logger.error(f"upload_products_csv: Error de conexión: {e}", exc_info=True)
            return False, f"Error de conexión: {e}"

    def update_product(self, product_id, field_name, new_value):
        """
        Envía una actualización parcial (PATCH) para un producto...
        """
        if not self.token:
            logger.warning("update_product llamado sin token.")
            return False, "No autenticado."

        update_url = f"{self.base_url}/productos/{product_id}/" 
        
        field_mapping = {
            "Nombre": "nombre_producto",
            "Precio": "precio",
            "Categoría": "id_categoria",
            "Marca": "id_marca",
        }

        api_field_name = field_mapping.get(field_name)
        if not api_field_name:
            logger.warning(f"update_product: Intento de editar campo no mapeado '{field_name}'.")
            return False, f"Campo '{field_name}' no es editable o no está mapeado."

        data_to_send = { api_field_name: new_value }

        if api_field_name == 'precio':
            try:
                data_to_send[api_field_name] = float(new_value.replace(',', '.'))
            except ValueError:
                logger.warning(f"update_product: Valor de precio inválido '{new_value}' para ID {product_id}.")
                return False, f"Valor de precio inválido: '{new_value}'. Debe ser un número."
        
        try:
            logger.info(f"Intentando PATCH en {update_url} con datos: {data_to_send}")
            response = requests.patch(update_url, json=data_to_send, headers=self.headers)

            if response.status_code == 200:
                logger.info(f"Producto {product_id} actualizado exitosamente.")
                return True, "Producto actualizado correctamente."
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
                logger.error(f"Error al actualizar producto {product_id}. Status: {response.status_code}, Error: {error_detail}")
                return False, f"Error al actualizar producto: {response.status_code} - {error_detail}"
        except requests.exceptions.RequestException as e:
            logger.error(f"update_product: Error de conexión: {e}", exc_info=True)
            return False, f"Error de conexión al actualizar: {e}"
        
    def get_users(self):
        """
        Obtiene TODOS los usuarios desde la API...
        """
        if not self.token:
            logger.warning("get_users llamado sin token.")
            return None, "No autenticado."
        
        all_users = []
        page = 1
        first_request = True 
        
        while True: 
            try:
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
                        logger.error(f"get_users: Formato de respuesta inesperado. Tipo: {type(data)}")
                        return None, f"Formato de respuesta inesperado de la API de usuarios: {type(data)}"
                    else: 
                        break 

                elif response.status_code == 404:
                    if page == 1:
                        logger.error(f"get_users falló (404) en la página 1. URL: {url}")
                        return None, f"Error al obtener usuarios: {response.status_code} - Not Found. ¿La URL {self.base_url}/users/ es correcta?"
                    else:
                        break # Fin de las páginas
                else:
                    error_detail = response.text
                    try: 
                        error_detail = response.json().get('detail', response.text)
                    except json.JSONDecodeError:
                        pass 
                    logger.error(f"Error al obtener usuarios (página {page}): {response.status_code} - {error_detail}")
                    return None, f"Error al obtener usuarios (página {page}): {response.status_code} - {error_detail}"
            except requests.exceptions.RequestException as e:
                logger.error(f"get_users: Error de conexión: {e}", exc_info=True)
                return None, f"Error de conexión: {e}"
            except json.JSONDecodeError as e:
                logger.error(f"get_users: Error al decodificar JSON. Respuesta: {response.text}", exc_info=True)
                return None, f"Error al decodificar JSON de la API de usuarios: {e} - Respuesta recibida: {response.text}"
            
            first_request = False

        logger.info(f"get_users: Se cargaron {len(all_users)} usuarios exitosamente.")
        return all_users, None

    def update_user(self, user_id, field_name, new_value):
        """
        Envía una actualización parcial (PATCH) para un usuario...
        """
        if not self.token:
            logger.warning("update_user llamado sin token.")
            return False, "No autenticado."
            
        update_url = f"{self.base_url}/users/{user_id}/" 
        
        field_mapping = {
            "Nombre": "nombre",
            "Apellido": "apellido",
            "Username": "nombre_usuario",
            "Es Admin": "es_admin",
            "Is Staff": "is_staff",
            "Está Activa": "is_active",
        }
        
        api_field_name = field_mapping.get(field_name)
        if not api_field_name:
            logger.warning(f"update_user: Intento de editar campo no mapeado '{field_name}'.")
            return False, f"Campo '{field_name}' no es editable."

        data_to_send = { api_field_name: new_value }

        if api_field_name in ['is_active', 'is_staff', 'es_admin']:
            if isinstance(new_value, str) and new_value.lower() in ['true', '1', 'verdadero', 'sí', 'si']:
                data_to_send[api_field_name] = True
            elif isinstance(new_value, str) and new_value.lower() in ['false', '0', 'falso', 'no']:
                data_to_send[api_field_name] = False
            elif isinstance(new_value, bool):
                data_to_send[api_field_name] = new_value
            else:
                logger.warning(f"update_user: Valor booleano inválido '{new_value}' para ID {user_id}.")
                return False, f"Valor inválido para '{field_name}'. Use True/False, 1/0, etc."

        try:
            logger.info(f"Intentando PATCH en {update_url} con datos: {data_to_send}")
            response = requests.patch(update_url, json=data_to_send, headers=self.headers)

            if response.status_code == 200:
                logger.info(f"Usuario {user_id} actualizado exitosamente.")
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
                logger.error(f"Error al actualizar usuario {user_id}. Status: {response.status_code}, Error: {error_detail}")
                return False, f"Error al actualizar usuario: {response.status_code} - {error_detail}"
        except requests.exceptions.RequestException as e:
            logger.error(f"update_user: Error de conexión: {e}", exc_info=True)
            return False, f"Error de conexión al actualizar usuario: {e}"

    def delete_product(self, product_id):
        """
        Envía una petición DELETE para borrar un producto...
        """
        if not self.token:
            logger.warning("delete_product llamado sin token.")
            return False, "No autenticado."
    
        delete_url = f"{self.base_url}/productos/{product_id}/" 
    
        try:
            logger.info(f"Intentando DELETE en {delete_url}")
            response = requests.delete(delete_url, headers=self.headers)
    
            if response.status_code == 204:
                logger.info(f"Producto {product_id} borrado exitosamente.")
                return True, "Producto borrado correctamente."
            elif response.status_code == 404:
                logger.warning(f"Intento de borrar producto {product_id} falló (404 Not Found).")
                return False, f"Error al borrar: Producto con ID {product_id} no encontrado."
            else:
                error_detail = response.text
                try:
                    error_data = response.json()
                    if isinstance(error_data.get('detail'), str):
                        error_detail = error_data['detail']
                except json.JSONDecodeError:
                    pass
                logger.error(f"Error al borrar producto {product_id}. Status: {response.status_code}, Error: {error_detail}")
                return False, f"Error al borrar producto: {response.status_code} - {error_detail}"
        except requests.exceptions.RequestException as e:
            logger.error(f"delete_product: Error de conexión: {e}", exc_info=True)
            return False, f"Error de conexión al borrar: {e}"
            
    def download_product_report(self, report_format='csv'):
        """
        Descarga el reporte CSV, Excel o PDF de productos activos.
        """
        if not self.token:
            self.logger.warning("download_product_report llamado sin token.")
            return None, "No autenticado."
    
        if report_format == 'pdf':
            # Ruta para PDF
            report_url = f"{self.base_url}/reports/products/download/pdf/"
        elif report_format == 'excel':
            # Ruta para Excel
            report_url = f"{self.base_url}/reports/products/download/excel/"
        else:
            # Ruta para CSV (default)
            report_url = f"{self.base_url}/reports/products/download/"
        
        try:
            # Creamos una copia de los encabezados, EXCLUYENDO Content-Type si existe, 
            # ya que vamos a recibir un archivo binario.
            temp_headers = self.headers.copy()
            if 'Content-Type' in temp_headers: 
                del temp_headers['Content-Type']
            if 'Accept' in temp_headers:
                del temp_headers['Accept'] # No forzamos JSON
    
            self.logger.info(f"Iniciando descarga de reporte: {report_format} desde {report_url}")
            
            # Hacemos la petición con los encabezados limpios
            response = requests.get(report_url, headers=temp_headers, stream=True, timeout=self.timeout)
            response.raise_for_status()
    
            # Validación de contenido (para saber si falló y nos devolvió JSON de error)
            content_type = response.headers.get('content-type', '').lower()
            if 'json' in content_type and response.text:
                 # Si devuelve JSON, asumimos que es un error del servidor (400, 500, etc.)
                error_data = response.json()
                error_detail = error_data.get('detail', error_data.get('error', response.text))
                self.logger.error(f"Error en descarga: Servidor devolvió JSON de error. Detalle: {error_detail}")
                return None, f"Error del servidor ({response.status_code}): {error_detail}"

            # Si no es JSON, asumimos que es el archivo
            self.logger.info(f"Reporte {report_format} descargado exitosamente ({len(response.content)} bytes).")
            return response.content, None
    
        except requests.exceptions.RequestException as e:
            self.logger.error(f"download_product_report: Error de conexión: {e}", exc_info=True)
            return None, f"Error de conexión: {e}"
        except Exception as e:
            self.logger.critical(f"Error inesperado en download_product_report: {e}", exc_info=True)
            return None, f"Error inesperado: {str(e)}"
            
    # desktop_admin/api_client.py (REEMPLAZAR create_product)

    def create_product(self, name, description, category_id, brand_id, image_file_path=None):
        """
        Crea un nuevo producto en la API. Envía la imagen como una URL (string)
        en el cuerpo JSON para satisfacer la validación actual del servidor.
        """
        endpoint = f"{self.base_url}/productos/" # URL CORREGIDA
        headers = self._get_auth_headers()
        
        # Usamos las claves en ESPAÑOL que el serializador de Django espera
        data = {
            "nombre_producto": name,      
            "descripcion": description,
            "id_categoria": category_id,  
            "id_marca": brand_id          
        }
        
        # Enviamos la imagen como un string para pasar la validación de URL del backend
        if image_file_path:
            # ADVERTENCIA: Esta ruta DEBE ser una URL válida (http://...) para que Django la acepte.
            data['imagen'] = image_file_path 

        # Configuramos para enviar JSON
        if 'Content-Type' not in headers:
             headers['Content-Type'] = 'application/json' 
        
        # Ya no usamos 'files' ni lógica multipart/form-data
        files = {} 

        try:
            # Usamos json=data para enviar el cuerpo como JSON
            response = requests.post(endpoint, headers=headers, json=data, timeout=self.timeout) 

            response.raise_for_status() 
            return True, "Producto creado exitosamente."
            
        except requests.exceptions.HTTPError as http_err:
            
            error_detail = "El servidor devolvió un error HTTP."
            
            if response.text:
                try:
                    error_data = response.json() 
                    if isinstance(error_data, dict):
                        # Formato amigable para errores de validación
                        error_detail = "; ".join([f"{k}: {v[0]}" for k, v in error_data.items()])
                    else:
                         error_detail = error_data.get('detail', str(error_data))
                except requests.exceptions.JSONDecodeError:
                    error_detail = f"Respuesta no JSON: {response.text[:100]}..." 
            else:
                error_detail = f"Respuesta vacía del servidor. Status: {response.status_code}"
            
            self.logger.error(f"HTTP error creating product: {http_err} - {error_detail}")
            
            return False, f"Error HTTP: {response.status_code} - {error_detail}"
            
        except requests.exceptions.RequestException as req_err:
            self.logger.error(f"Error de conexión o timeout: {req_err}")
            return False, f"Un error de conexión/timeout inesperado ocurrió: {req_err}"
            
        except Exception as e:
            self.logger.error(f"General error creating product: {e}")
            return False, f"Un error inesperado ocurrió: {e}"
    ########################
    #REPORTES DE ACTIVIDAD#
    ########################
    def _get_auth_headers(self):
        """
        [IMPLEMENTACIÓN FINAL] Devuelve los encabezados necesarios para la autenticación JWT.
        """
        # 1. Crear el diccionario base
        headers = {'Content-Type': 'application/json'}
        
        # 2. Añadir el token si existe
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        else:
            self.logger.warning("Intento de acceder a la API sin token JWT.")
            
        return headers
    
    
    
    def _get_report_data(self, endpoint_name, report_url):
        """Helper genérico para obtener datos de reportes."""
        if not self.token:
            logger.warning(f"{endpoint_name} llamado sin token.")
            return None, "No autenticado."
        
        try:
            logger.info(f"Solicitando reporte: {endpoint_name} desde {report_url}")
            response = requests.get(report_url, headers=self.headers)
            response.raise_for_status() # Lanza error en 4xx/5xx
            logger.info(f"Reporte {endpoint_name} obtenido exitosamente.")
            return response.json(), None
        except requests.exceptions.HTTPError as http_err:
            error_detail = http_err.response.text
            try:
                error_data = http_err.response.json()
                error_detail = error_data.get("error", error_data.get("detail", error_detail))
            except json.JSONDecodeError:
                pass
            logger.error(f"Error HTTP en {endpoint_name}. Status: {http_err.response.status_code}, Error: {error_detail}", exc_info=True)
            return None, f"Error del servidor ({http_err.response.status_code}): {error_detail}"
        except requests.exceptions.RequestException as e:
            logger.error(f"{endpoint_name}: Error de conexión: {e}", exc_info=True)
            return None, f"Error de conexión: {e}"
        except json.JSONDecodeError as e:
            logger.error(f"{endpoint_name}: Error al decodificar JSON. Respuesta: {response.text}", exc_info=True)
            return None, f"Error al decodificar JSON de la API: {e} - Respuesta recibida: {response.text}"

    def get_moderation_report(self):
        """Obtiene el reporte de moderación."""
        return self._get_report_data(
            "get_moderation_report", 
            f"{self.base_url}/reports/moderation/"
        )

    def get_popular_search_report(self):
        """Obtiene el reporte de búsquedas populares."""
        return self._get_report_data(
            "get_popular_search_report",
            f"{self.base_url}/reports/popular-searches/"
        )

    def get_site_reviews_report(self):
        """Obtiene el reporte de reseñas del sitio."""
        return self._get_report_data(
            "get_site_reviews_report",
            f"{self.base_url}/reports/site-reviews/"
        )

    def get_top_active_users_report(self):
        """Obtiene el reporte de top 10 usuarios activos."""
        return self._get_report_data(
            "get_top_active_users_report",
            f"{self.base_url}/reports/top-active-users/"
        )

    def get_user_activity_detail(self, user_id):
        """Obtiene el reporte de actividad detallado para un usuario."""
        return self._get_report_data(
            "get_user_activity_detail",
            f"{self.base_url}/reports/user-activity/{user_id}/"
        )
        
    def get_web_logs(self):
        """Obtiene los logs del servidor web desde la API."""
        # Reutilizamos el helper _get_report_data que ya maneja 
        # la autenticación y los errores de conexión.
        return self._get_report_data(
            "get_web_logs",
            f"{self.base_url}/admin/logs/"
        )
        
    def download_top_users_report_pdf(self):
        """
        Descarga el reporte PDF de Top Usuarios Activos desde la API.
        """
        if not self.token:
            self.logger.warning("download_top_users_report_pdf llamado sin token.")
            return None, "No autenticado."
    
        # URL mapeada en urls.py
        report_url = f"{self.base_url}/reports/top-active-users/download/pdf/"
    
        try:
            temp_headers = self.headers.copy()
            if 'Content-Type' in temp_headers: del temp_headers['Content-Type']
            if 'Accept' in temp_headers: del temp_headers['Accept']
    
            self.logger.info(f"Iniciando descarga de reporte PDF de Top Usuarios desde {report_url}")
            response = requests.get(report_url, headers=temp_headers, stream=True, timeout=self.timeout)
            response.raise_for_status()
    
            content_type = response.headers.get('content-type', '').lower()
            if 'pdf' not in content_type:
                error_detail = "Respuesta inesperada del servidor (no es PDF)."
                try: error_data = response.json(); error_detail = error_data.get("error", error_data.get("detail", error_detail))
                except json.JSONDecodeError: pass
                self.logger.error(f"Error en descarga de reporte PDF: {error_detail}. Content-Type recibido: {content_type}")
                return None, error_detail
    
            self.logger.info(f"Reporte PDF de Top Usuarios descargado exitosamente.")
            return response.content, None
    
        except requests.exceptions.RequestException as e:
            self.logger.error(f"download_top_users_report_pdf: Error de conexión: {e}", exc_info=True)
            return None, f"Error de conexión: {e}"
    
    
    def download_site_reviews_report_pdf(self):
        """
        Descarga el reporte PDF de reseñas del sitio desde la API.
        Asumimos que el endpoint correcto es /reports/site-reviews/download/pdf/
        """
        if not self.token:
            logger.warning("download_site_reviews_report_pdf llamado sin token.")
            return None, "No autenticado."
    
        # <<< CORRECCIÓN: Usar la ruta completa y corregida, manteniendo la extensión. >>>
        # Si la ruta no está en tu urls.py (como parece), tu backend no está listo.
        # Pero intentaremos la ruta estándar:
        report_url = f"{self.base_url}/reports/site-reviews/download/pdf/"
        
        # ... (el resto del código sigue igual, usando _download_report_file) ...

        try:
            # Preparamos headers sin 'Content-Type' o 'Accept' de JSON
            temp_headers = self.headers.copy()
            if 'Content-Type' in temp_headers: del temp_headers['Content-Type']
            if 'Accept' in temp_headers: del temp_headers['Accept']
    
            logger.info(f"Iniciando descarga de reporte PDF de reseñas desde {report_url}")
            response = requests.get(report_url, headers=temp_headers, stream=True, timeout=self.timeout) # Añadí timeout
            response.raise_for_status()
            
            # ... (manejo de Content-Type y errores sigue igual) ...
            
            # Verificar que la respuesta sea un PDF
            content_type = response.headers.get('content-type', '').lower()
            if 'pdf' not in content_type:
                # Si el servidor responde con HTML, Django lo reporta como 404 (como en la imagen)
                error_detail = "Respuesta inesperada del servidor (no es PDF)."
                try:
                    error_data = response.json()
                    error_detail = error_data.get("error", "Respuesta inesperada (esperaba PDF).")
                except json.JSONDecodeError:
                    pass
                logger.error(f"Error en descarga de reporte PDF: {error_detail}. Content-Type recibido: {content_type}")
                return None, error_detail
    
            logger.info(f"Reporte PDF de reseñas descargado exitosamente ({len(response.content)} bytes).")
            return response.content, None
    
        except requests.exceptions.HTTPError as http_err:
            error_detail = http_err.response.text
            try:
                error_data = http_err.response.json()
                error_detail = error_data.get("error", error_data.get("detail", http_err.response.text))
            except json.JSONDecodeError:
                pass
            logger.error(f"Error HTTP al descargar reporte de reseñas. Status: {http_err.response.status_code}, Error: {error_detail}", exc_info=True)
            return None, f"Error del servidor ({http_err.response.status_code}): {error_detail}"
        except requests.exceptions.RequestException as e:
            logger.error(f"download_site_reviews_report_pdf: Error de conexión: {e}", exc_info=True)
            return None, f"Error de conexión: {e}"
        except Exception as e:
            logger.critical(f"Error inesperado en download_site_reviews_report_pdf: {e}", exc_info=True)
            return None, f"Error inesperado: {str(e)}"
        
    
    
    
    def get_current_user_profile(self):
        """
        Obtiene el perfil del usuario logueado (incluye la bandera 'must_change_password').
        Asume un endpoint /users/me/ en el backend.
        """
        if not self.token:
            return None, "No autenticado."
            
        user_me_url = f"{self.base_url}/users/me/" 
        try:
            response = requests.get(user_me_url, headers=self.headers)
            if response.status_code == 200:
                return response.json(), None
            else:
                return None, f"Error al obtener perfil: {response.status_code}"
        except requests.exceptions.RequestException as e:
            return None, f"Error de conexión: {e}"


    def change_password_forced(self, user_id, new_password):
        """
        Envía la nueva contraseña y resetea la bandera 'must_change_password'.
        Asume un endpoint dedicado para esta acción.
        """
        if not self.token:
            return False, "No autenticado."
            
        # Asume que esta ruta existe en el backend y maneja la validación y el reseteo de la bandera.
        update_url = f"{self.base_url}/users/{user_id}/change-password-forced/" 
        payload = {'new_password': new_password} 
        
        try:
            response = requests.patch(update_url, json=payload, headers=self.headers)
            if response.status_code == 200:
                return True, "Contraseña actualizada exitosamente."
            else:
                error_detail = response.json().get('detail', response.text)
                return False, f"Error: {error_detail}"
        except requests.exceptions.RequestException as e:
            return False, f"Error de conexión: {e}"
        


        
    def get_categories(self):
        """
        Obtiene la lista completa de categorías desde la API.
        """
        if not self.token:
            logger.warning("get_categories llamado sin token.")
            return None, "No autenticado."
        
        # Llama al helper _get_report_data que ya tienes
        # (Usa 'List' en lugar de 'Report' para el nombre del log)
        return self._get_report_data(
            "get_categories_list",
            f"{self.base_url}/categorias/"
        )

    def get_brands(self):
        """
        Obtiene la lista completa de marcas desde la API.
        """
        if not self.token:
            logger.warning("get_brands llamado sin token.")
            return None, "No autenticado."
        
        return self._get_report_data(
            "get_brands_list",
            f"{self.base_url}/marcas/"
        )    
    def download_popular_search_report_pdf(self):
        """
        Descarga el reporte PDF de búsquedas populares desde la API.
        """
        if not self.token:
            logger.warning("download_popular_search_report_pdf llamado sin token.")
            return None, "No autenticado."
    
        report_url = f"{self.base_url}/reports/popular-searches/download/pdf/"
    
        try:
            temp_headers = self.headers.copy()
            if 'Content-Type' in temp_headers: del temp_headers['Content-Type']
            if 'Accept' in temp_headers: del temp_headers['Accept']
    
            logger.info(f"Iniciando descarga de reporte PDF de búsquedas desde {report_url}")
            response = requests.get(report_url, headers=temp_headers, stream=True)
            response.raise_for_status()
    
            content_type = response.headers.get('content-type', '').lower()
            if 'pdf' not in content_type:
                error_detail = "Respuesta inesperada del servidor (no es PDF)."
                try:
                    error_data = response.json()
                    error_detail = error_data.get("error", "Respuesta inesperada (esperaba PDF).")
                except json.JSONDecodeError:
                    pass
                logger.error(f"Error en descarga de reporte PDF búsquedas: {error_detail}. Content-Type recibido: {content_type}")
                return None, error_detail
    
            logger.info(f"Reporte PDF de búsquedas descargado exitosamente ({len(response.content)} bytes).")
            return response.content, None
    
        except requests.exceptions.HTTPError as http_err:
            error_detail = http_err.response.text
            try:
                error_data = http_err.response.json()
                error_detail = error_data.get("error", error_data.get("detail", http_err.response.text))
            except json.JSONDecodeError:
                pass
            logger.error(f"Error HTTP al descargar reporte de búsquedas. Status: {http_err.response.status_code}, Error: {error_detail}", exc_info=True)
            return None, f"Error del servidor ({http_err.response.status_code}): {error_detail}"
        except requests.exceptions.RequestException as e:
            logger.error(f"download_popular_search_report_pdf: Error de conexión: {e}", exc_info=True)
            return None, f"Error de conexión: {e}"
        
    
    
    def delete_user(self, user_id):
        """
        Envía una petición DELETE para borrar un usuario específico a la API.
        """
        if not self.token:
            logger.warning("delete_user llamado sin token.")
            return False, "No autenticado."
    
        delete_url = f"{self.base_url}/users/{user_id}/" 
    
        try:
            logger.info(f"Intentando DELETE en {delete_url} (Usuario ID: {user_id})")
            response = requests.delete(delete_url, headers=self.headers)
    
            # DELETE exitoso devuelve 204 No Content
            if response.status_code == 204:
                logger.info(f"Usuario {user_id} borrado exitosamente.")
                return True, "Usuario borrado correctamente."
            elif response.status_code == 404:
                logger.warning(f"Intento de borrar usuario {user_id} falló (404 Not Found).")
                return False, f"Error al borrar: Usuario con ID {user_id} no encontrado."
            else:
                error_detail = response.text
                try:
                    error_data = response.json()
                    if isinstance(error_data.get('detail'), str):
                        error_detail = error_data['detail']
                except json.JSONDecodeError:
                    pass
                logger.error(f"Error al borrar usuario {user_id}. Status: {response.status_code}, Error: {error_detail}")
                return False, f"Error al borrar usuario: {response.status_code} - {error_detail}"
        except requests.exceptions.RequestException as e:
            logger.error(f"delete_user: Error de conexión: {e}", exc_info=True)
            return False, f"Error de conexión al borrar: {e}"
    
    def send_user_warning(self, user_id, motivo):
        """
        Envía una petición POST para mandar una advertencia por email a un usuario.
        """
        if not self.token:
            logger.warning("send_user_warning llamado sin token.")
            return False, "No autenticado."
    
        url = f"{self.base_url}/admin/send-warning/"
        payload = {
            "user_id": user_id,
            "motivo": motivo
        }
        
        try:
            logger.info(f"Enviando advertencia a user_id: {user_id} por: {motivo}")
            response = requests.post(url, json=payload, headers=self.headers)
    
            if response.status_code == 200:
                logger.info(f"Advertencia enviada a {user_id} exitosamente.")
                return True, response.json().get("message", "Advertencia enviada.")
            else:
                error_detail = response.text
                try: error_detail = response.json().get('detail', error_detail)
                except json.JSONDecodeError: pass
                logger.error(f"Error al enviar advertencia a {user_id}. Status: {response.status_code}, Error: {error_detail}")
                return False, f"Error: {error_detail}"
        except requests.exceptions.RequestException as e:
            logger.error(f"send_user_warning: Error de conexión: {e}", exc_info=True)
            return False, f"Error de conexión: {e}"
    
        
    def create_category(self, category_data):
        """
        Envía una petición POST para crear una nueva categoría.
        category_data debe ser un diccionario: {'nombre_categoria': '...'}
        """
        if not self.token:
            logger.warning("create_category llamado sin token.")
            return None, "No autenticado."
    
        create_url = f"{self.base_url}/categorias/"
        
        try:
            logger.info(f"Intentando POST en {create_url} con datos: {category_data}")
            response = requests.post(create_url, json=category_data, headers=self.headers)
    
            if response.status_code == 201: # 201 Created
                new_category = response.json()
                logger.info(f"Categoría creada exitosamente. ID: {new_category.get('id_categoria')}")
                return new_category, "Categoría creada exitosamente."
            else:
                # Manejar error
                error_detail = response.text
                try:
                    error_data = response.json()
                    error_detail = "; ".join([f"{k}: {v[0]}" for k, v in error_data.items()])
                except (json.JSONDecodeError, AttributeError):
                    pass
                logger.error(f"Error al crear categoría. Status: {response.status_code}, Error: {error_detail}")
                return None, f"Error al crear categoría: {response.status_code} - {error_detail}"
    
        except requests.exceptions.RequestException as e:
            logger.error(f"create_category: Error de conexión: {e}", exc_info=True)
            return None, f"Error de conexión al crear categoría: {e}"
        
    def create_brand(self, brand_data):
        """
        Envía una petición POST para crear una nueva marca.
        brand_data debe ser un diccionario: {'nombre_marca': '...'}
        """
        if not self.token:
            logger.warning("create_brand llamado sin token.")
            return None, "No autenticado."
    
        create_url = f"{self.base_url}/marcas/"
        
        try:
            logger.info(f"Intentando POST en {create_url} con datos: {brand_data}")
            response = requests.post(create_url, json=brand_data, headers=self.headers)
    
            if response.status_code == 201:
                new_brand = response.json()
                logger.info(f"Marca creada exitosamente. ID: {new_brand.get('id_marca')}")
                return new_brand, "Marca creada exitosamente."
            else:
                # Manejar error
                error_detail = response.text
                try:
                    error_data = response.json()
                    error_detail = "; ".join([f"{k}: {v[0]}" for k, v in error_data.items()])
                except (json.JSONDecodeError, AttributeError):
                    pass
                logger.error(f"Error al crear marca. Status: {response.status_code}, Error: {error_detail}")
                return None, f"Error al crear marca: {response.status_code} - {error_detail}"
    
        except requests.exceptions.RequestException as e:
            logger.error(f"create_brand: Error de conexión: {e}", exc_info=True)
            return None, f"Error de conexión al crear marca: {e}"
        
    def initiate_password_reset(self, email):
        """
        [SOBREESCRITO] Envía una petición al endpoint que genera la contraseña temporal
        y la notifica al admin para que él se contacte con el usuario.
        """
        reset_url = f"{self.base_url}/admin/reset-request/"
        payload = {'email': email} 
        
        try:
            logger.info(f"Iniciando solicitud de reset para admin: {email}")
            temp_headers = {'Content-Type': 'application/json'}
            
            response = requests.post(reset_url, json=payload, headers=temp_headers)
            
            # <<< --- MODIFICACIÓN CLAVE AQUÍ --- >>>
            if not response.text:
                logger.error(f"Respuesta vacía recibida del servidor. Status: {response.status_code}")
                return False, f"Respuesta vacía del servidor (Status: {response.status_code})."
            
            try:
                data = response.json()
            except json.JSONDecodeError:
                logger.error(f"Respuesta inválida de la API. Contenido: {response.text[:100]}...")
                return False, f"La API devolvió una respuesta inválida (No es JSON)."
            # <<< --- FIN MODIFICACIÓN CLAVE --- >>>


            if response.status_code == 200:
                # Si es 200, usamos el JSON que ya decodificamos en 'data'
                return True, data.get("message", "Contraseña temporal GENERADA. Se ha enviado una notificación...")
            
            elif response.status_code == 500:
                # Si es 500, intentamos obtener el detalle del error del JSON
                error_detail = data.get('detail', 'Error interno del servidor.')
                if data.get('error_code') == "EMAIL_FAIL":
                    return False, f"ERROR CRÍTICO: La contraseña temporal fue GENERADA, pero falló el envío de la notificación por correo al administrador. Revisa la configuración SMTP."
                return False, f"Error del servidor. Status: 500. Detalle: {error_detail}"

            else:
                # Otros errores HTTP (400, 403, 404)
                error_detail = data.get('detail', response.text)
                return False, f"Error de la API: Status: {response.status_code}. Detalle: {error_detail}"

        except requests.exceptions.RequestException as e:
            logger.error(f"Error de conexión al iniciar reset: {e}")
            return False, f"Error de conexión: {e}"
    
        
    def delete_category(self, category_id):
        """Envía una petición DELETE para borrar una categoría."""
        if not self.token:
            logger.warning("delete_category llamado sin token.")
            return False, "No autenticado."
    
        delete_url = f"{self.base_url}/categorias/{category_id}/" 
        try:
            logger.info(f"Intentando DELETE en {delete_url}")
            response = requests.delete(delete_url, headers=self.headers)
    
            if response.status_code == 204: # Éxito
                logger.info(f"Categoría {category_id} borrada exitosamente.")
                return True, "Categoría borrada correctamente."
            elif response.status_code == 404:
                logger.warning(f"Intento de borrar categoría {category_id} falló (404 Not Found).")
                return False, f"Error: Categoría con ID {category_id} no encontrada."
            else:
                # Captura otros errores (ej. 403 si intenta borrar "Sin Categoría")
                error_detail = response.text
                try: error_detail = response.json().get('detail', error_detail)
                except json.JSONDecodeError: pass
                logger.error(f"Error al borrar categoría {category_id}. Status: {response.status_code}, Error: {error_detail}")
                return False, f"Error al borrar: {error_detail}"
        except requests.exceptions.RequestException as e:
            logger.error(f"delete_category: Error de conexión: {e}", exc_info=True)
            return False, f"Error de conexión al borrar: {e}"

    def delete_brand(self, brand_id):
        """Envía una petición DELETE para borrar una marca."""
        if not self.token:
            logger.warning("delete_brand llamado sin token.")
            return False, "No autenticado."
    
        delete_url = f"{self.base_url}/marcas/{brand_id}/" 
        try:
            logger.info(f"Intentando DELETE en {delete_url}")
            response = requests.delete(delete_url, headers=self.headers)
    
            if response.status_code == 204:
                logger.info(f"Marca {brand_id} borrada exitosamente.")
                return True, "Marca borrada correctamente."
            elif response.status_code == 404:
                logger.warning(f"Intento de borrar marca {brand_id} falló (404 Not Found).")
                return False, f"Error: Marca con ID {brand_id} no encontrada."
            else:
                error_detail = response.text
                try: error_detail = response.json().get('detail', error_detail)
                except json.JSONDecodeError: pass
                logger.error(f"Error al borrar marca {brand_id}. Status: {response.status_code}, Error: {error_detail}")
                return False, f"Error al borrar: {error_detail}"
        except requests.exceptions.RequestException as e:
            logger.error(f"delete_brand: Error de conexión: {e}", exc_info=True)
            return False, f"Error de conexión al borrar: {e}"    
    
    def update_category(self, category_id, data):
        """
        Envía una petición PATCH para actualizar una categoría.
        data debe ser: {'nombre_categoria': 'Nuevo Nombre'}
        """
        if not self.token:
            logger.warning("update_category llamado sin token.")
            return False, "No autenticado."
    
        update_url = f"{self.base_url}/categorias/{category_id}/" 
        try:
            logger.info(f"Intentando PATCH en {update_url} con datos: {data}")
            response = requests.patch(update_url, json=data, headers=self.headers)

            if response.status_code == 200:
                logger.info(f"Categoría {category_id} actualizada exitosamente.")
                return True, "Categoría actualizada correctamente."
            else:
                error_detail = response.text
                try: error_detail = response.json().get('detail', error_detail)
                except json.JSONDecodeError: pass
                logger.error(f"Error al actualizar categoría {category_id}. Status: {response.status_code}, Error: {error_detail}")
                return False, f"Error al actualizar: {error_detail}"
        except requests.exceptions.RequestException as e:
            logger.error(f"update_category: Error de conexión: {e}", exc_info=True)
            return False, f"Error de conexión al actualizar: {e}"

    def update_brand(self, brand_id, data):
        """
        Envía una petición PATCH para actualizar una marca.
        data debe ser: {'nombre_marca': 'Nuevo Nombre'}
        """
        if not self.token:
            logger.warning("update_brand llamado sin token.")
            return False, "No autenticado."
    
        update_url = f"{self.base_url}/marcas/{brand_id}/" 
        try:
            logger.info(f"Intentando PATCH en {update_url} con datos: {data}")
            response = requests.patch(update_url, json=data, headers=self.headers)

            if response.status_code == 200:
                logger.info(f"Marca {brand_id} actualizada exitosamente.")
                return True, "Marca actualizada correctamente."
            else:
                error_detail = response.text
                try: error_detail = response.json().get('detail', error_detail)
                except json.JSONDecodeError: pass
                logger.error(f"Error al actualizar marca {brand_id}. Status: {response.status_code}, Error: {error_detail}")
                return False, f"Error al actualizar: {error_detail}"
        except requests.exceptions.RequestException as e:
            logger.error(f"update_brand: Error de conexión: {e}", exc_info=True)
            return False, f"Error de conexión al actualizar: {e}"
        
    