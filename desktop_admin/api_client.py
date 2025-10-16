import requests
import json

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
            response = requests.post(f"{self.base_url}/token/", data={
                "email": username,
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

    def get_products(self, page=1):
        """
        Obtiene una lista paginada de productos desde la API.
        """
        if not self.token:
            return None, "No autenticado."
        
        try:
            response = requests.get(f"{self.base_url}/productos/?page={page}", headers=self.headers)
            if response.status_code == 200:
                return response.json(), None
            else:
                return None, f"Error al obtener productos: {response.status_code}"
        except requests.exceptions.RequestException as e:
            return None, f"Error de conexión: {e}"

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
