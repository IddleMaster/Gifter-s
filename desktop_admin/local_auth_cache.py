import sqlite3
import hashlib
import logging
import os

# Usamos tu carpeta 'logs' para guardar este caché
CACHE_DB = os.path.join("logs", "admin_cache.db")

class LocalAuthCache:
    """
    Gestiona una base de datos SQLite local para guardar un hash
    de la contraseña del administrador, permitiendo el login offline.
    """
    def __init__(self):
        self.db_path = CACHE_DB
        self._init_db()

    def _init_db(self):
        """Asegura que la carpeta 'logs' y la tabla 'users' existan."""
        try:
            # Asegura que el directorio 'logs' exista
            os.makedirs(os.path.dirname(CACHE_DB), exist_ok=True)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # email es la Clave Primaria (UNIQUE)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                password_original TEXT NOT NULL  
            )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error al inicializar la BD de caché local: {e}", exc_info=True)

    def _hash_password(self, password):
        """Crea un hash SHA-256 simple (no salteado) de la contraseña."""
        # Es lo suficientemente seguro para este propósito local.
        return hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    def get_password_original(self, email): # <- RENOMBRADA LA FUNCIÓN
        """
        Recupera la contraseña original (string plano) para re-autenticación.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # Seleccionamos la columna 'password_original'
            cursor.execute("SELECT password_original FROM users WHERE email = ?", (email.lower(),))
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result else None
            
        except Exception as e:
            logging.error(f"Error al obtener contraseña original para {email}: {e}", exc_info=True)
            return None
        
    def save_user_hash(self, email, password): # <- Renombrada para claridad
        """
        Guarda (o actualiza) la contraseña original de un usuario 
        después de un login online exitoso.
        """
        # Ya no hasheamos, guardamos la original (string plano)
        password_original = password 
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # NOTA: Usar 'password_original' en la tabla
            cursor.execute("INSERT OR REPLACE INTO users (email, password_original) VALUES (?, ?)", 
                           (email.lower(), password_original)) 
            conn.commit()
            conn.close()
            logging.info(f"Contraseña original local guardada/actualizada para {email}")
        except Exception as e:
            logging.error(f"Error al guardar contraseña local para {email}: {e}", exc_info=True)

    def check_offline_password(self, email, password):
        """
        Compara la contraseña ingresada (texto plano) con la contraseña
        original guardada localmente (texto plano).
        """
        # La lógica de hashing ya no se usa, ya que la contraseña original 
        # (texto plano) debe ser enviada al endpoint de login para re-autenticar
        # y también para la verificación offline.
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # NOTA: La columna en la base de datos debe llamarse 'password_original' (o similar)
            cursor.execute("SELECT password_original FROM users WHERE email = ?", (email.lower(),))
            stored_password_result = cursor.fetchone()
            conn.close()
            
            stored_password = stored_password_result[0] if stored_password_result else None
            
            # Comparamos la contraseña de texto plano ingresada con la de texto plano almacenada
            if stored_password and stored_password == password:
                logging.info(f"Password offline coincide para {email}")
                return True
            else:
                logging.warning(f"Password offline NO coincide o no existe para {email}")
                return False
        except Exception as e:
            logging.error(f"Error al verificar la contraseña local para {email}: {e}", exc_info=True)
            return False
        