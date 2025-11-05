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
                pass_hash TEXT NOT NULL
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

    def save_user_hash(self, email, password):
        """
        Guarda (o actualiza) el hash de la contraseña de un usuario
        después de un login online exitoso.
        """
        pass_hash = self._hash_password(password)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # INSERT OR REPLACE (UPSERT)
            cursor.execute("INSERT OR REPLACE INTO users (email, pass_hash) VALUES (?, ?)", 
                           (email.lower(), pass_hash))
            conn.commit()
            conn.close()
            logging.info(f"Hash de contraseña local guardado/actualizado para {email}")
        except Exception as e:
            logging.error(f"Error al guardar hash local para {email}: {e}", exc_info=True)

    def check_offline_password(self, email, password):
        """
        Compara la contraseña ingresada con el hash guardado localmente.
        """
        pass_hash_to_check = self._hash_password(password)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT pass_hash FROM users WHERE email = ?", (email.lower(),))
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0] == pass_hash_to_check:
                logging.info(f"Password offline coincide para {email}")
                return True
            else:
                logging.warning(f"Password offline NO coincide o no existe para {email}")
                return False
        except Exception as e:
            logging.error(f"Error al verificar hash local para {email}: {e}", exc_info=True)
            return False