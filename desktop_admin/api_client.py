import requests
import json
import os 
import logging # <-- Importado (ya lo tenías)

# Creamos un logger específico para este módulo, lo que es una buena práctica.
logger = logging.getLogger(__name__)

class ApiClient:
    """
    Gestor de comunicación con La API REST del proyecto xiquillos!
    """
    def __init__(self, base_url="http://127.0.0.1:8000/api"):
        self.base_url = base_url
        self.token = None
        self.headers = {'Content-Type': 'application/json'}
        logger.info(f"ApiClient inicializado con base_url: {base_url}")

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
                logger.info(f"Login exitoso para usuario: {username}")
                return True, "Login exitoso."
            else:
                logger.warning(f"Intento de login fallido para {username}. Status: {response.status_code}, Respuesta: {response.text}")
                return False, f"Error de autenticación: {response.status_code} - {response.text}"
        except requests.exceptions.RequestException as e:
            logger.critical(f"Fallo de conexión en login: {e}") # Error crítico de conexión
            return False, f"No se pudo conectar con el servidor: {e}"

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
            "Is Active": "is_active",
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
        Descarga el reporte CSV, Excel o PDF de productos activos...
        """
        if not self.token:
            logger.warning("download_product_report llamado sin token.")
            return None, "No autenticado."
    
        if report_format == 'pdf':
            report_url = f"{self.base_url}/reports/products/download/pdf/"
        elif report_format == 'excel':
            report_url = f"{self.base_url}/reports/products/download/excel/"
        else: # Default a CSV
            report_url = f"{self.base_url}/reports/products/download/"
        
        try:
            temp_headers = self.headers.copy()
            if 'Content-Type' in temp_headers: del temp_headers['Content-Type']
            if 'Accept' in temp_headers: del temp_headers['Accept']
    
            logger.info(f"Iniciando descarga de reporte: {report_format} desde {report_url}")
            response = requests.get(report_url, headers=temp_headers, stream=True)
            response.raise_for_status()
    
            content_type = response.headers.get('content-type', '').lower()
            if report_format == 'csv':
                expected_content_type = 'csv'
            elif report_format == 'excel':
                expected_content_type = 'spreadsheetml' # Parte del content-type de Excel
            elif report_format == 'pdf':
                expected_content_type = 'pdf'
            else:
                expected_content_type = 'desconocido'
    
            if expected_content_type not in content_type:
                error_detail = f"Respuesta inesperada del servidor (no es {expected_content_type})."
                try:
                    error_data = response.json()
                    error_detail = error_data.get("error", f"Respuesta inesperada (esperaba {report_format.upper()}).")
                except json.JSONDecodeError:
                    pass
                logger.error(f"Error en descarga de reporte: {error_detail}. Content-Type recibido: {content_type}")
                return None, error_detail
    
            logger.info(f"Reporte {report_format} descargado exitosamente ({len(response.content)} bytes).")
            return response.content, None
    
        except requests.exceptions.HTTPError as http_err:
            error_detail = http_err.response.text
            try:
                error_data = http_err.response.json()
                error_detail = error_data.get("error", error_data.get("detail", http_err.response.text))
            except json.JSONDecodeError:
                pass
            logger.error(f"Error HTTP al descargar reporte. Status: {http_err.response.status_code}, Error: {error_detail}", exc_info=True)
            return None, f"Error del servidor ({http_err.response.status_code}): {error_detail}"
        except requests.exceptions.RequestException as e:
            logger.error(f"download_product_report: Error de conexión: {e}", exc_info=True)
            return None, f"Error de conexión: {e}"
        except Exception as e:
            logger.critical(f"Error inesperado en download_product_report: {e}", exc_info=True)
            return None, f"Error inesperado: {str(e)}"
            
    def create_product(self, product_data):
        """
        Envía una petición POST para crear un nuevo producto.
        """
        if not self.token:
            logger.warning("create_product llamado sin token.")
            return None, "No autenticado."
    
        create_url = f"{self.base_url}/productos/"
    
        try:
            if 'precio' in product_data and product_data['precio'] is not None:
                product_data['precio'] = float(str(product_data['precio']).replace(',', '.'))
            if 'id_categoria' in product_data:
                product_data['id_categoria'] = int(product_data['id_categoria'])
            if 'id_marca' in product_data:
                product_data['id_marca'] = int(product_data['id_marca'])
        except (ValueError, TypeError) as e:
            logger.warning(f"create_product: Datos inválidos. Error: {e}, Datos: {product_data}")
            return None, f"Datos inválidos para crear producto: {e}"
    
        try:
            logger.info(f"Intentando POST en {create_url} con datos: {product_data}")
            response = requests.post(create_url, json=product_data, headers=self.headers)
    
            if response.status_code == 201:
                new_product_info = response.json()
                logger.info(f"Producto creado exitosamente. ID: {new_product_info.get('id_producto')}")
                return new_product_info, "Producto creado exitosamente."
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
                logger.error(f"Error al crear producto. Status: {response.status_code}, Error: {error_detail}")
                return None, f"Error al crear producto: {response.status_code} - {error_detail}"
    
        except requests.exceptions.RequestException as e:
            logger.error(f"create_product: Error de conexión: {e}", exc_info=True)
            return None, f"Error de conexión al crear producto: {e}"

    ########################
    #REPORTES DE ACTIVIDAD#
    ########################
    
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
        

    def download_site_reviews_report_pdf(self):
        """
        Descarga el reporte PDF de reseñas del sitio desde la API.
        """
        if not self.token:
            logger.warning("download_site_reviews_report_pdf llamado sin token.")
            return None, "No autenticado."
    
        report_url = f"{self.base_url}/reports/site-reviews/download/pdf/"
    
        try:
            # Preparamos headers sin 'Content-Type' o 'Accept' de JSON
            temp_headers = self.headers.copy()
            if 'Content-Type' in temp_headers: del temp_headers['Content-Type']
            if 'Accept' in temp_headers: del temp_headers['Accept']
    
            logger.info(f"Iniciando descarga de reporte PDF de reseñas desde {report_url}")
            response = requests.get(report_url, headers=temp_headers, stream=True)
            response.raise_for_status()
    
            # Verificar que la respuesta sea un PDF
            content_type = response.headers.get('content-type', '').lower()
            if 'pdf' not in content_type:
                error_detail = "Respuesta inesperada del servidor (no es PDF)."
                try:
                    error_data = response.json()
                    error_detail = error_data.get("error", "Respuesta inesperada (esperaba PDF).")
                except json.JSONDecodeError:
                    pass
                logger.error(f"Error en descarga de reporte PDF: {error_detail}. Content-Type recibido: {content_type}")
                return None, error_detail
    
            logger.info(f"Reporte PDF de reseñas descargado exitosamente ({len(response.content)} bytes).")
            return response.content, None # Devuelve los bytes del PDF
    
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