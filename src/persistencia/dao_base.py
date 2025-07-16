import sqlite3
import threading
import os
import config # Importa la configuración

# Rutas de la base de datos usando config.py
DATABASE_DIR = config.DATABASE_DIR
DATABASE_FILE = os.path.join(DATABASE_DIR, config.DATABASE_NAME)

# Bloqueo para asegurar la seguridad de los hilos al escribir/leer en la base de datos.
db_lock = threading.RLock()                     # Usar RLock para permitir bloqueos anidados

def get_db_connection():
    """Crea y retorna una conexión a la base de datos."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row              # Permite acceder a columnas por nombre
    conn.execute("PRAGMA foreign_keys = ON;")   # Asegura que las FK estén habilitadas en cada conexión
    return conn