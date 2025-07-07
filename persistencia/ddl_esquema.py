import sqlite3
import os
import threading
import config # Importa la configuración

# Rutas de la base de datos usando config.py
DATABASE_DIR = config.DATABASE_DIR
DATABASE_FILE = os.path.join(DATABASE_DIR, config.DATABASE_NAME)

# Bloqueo para asegurar la seguridad de los hilos al escribir/leer en la base de datos.
db_lock = threading.Lock()

def create_database_schema():
    """
    Crea el directorio 'data' si no existe y las tablas 'grd' e 'historicos'
    en la base de datos SQLite, incluyendo la clave foránea.
    """
    if not os.path.exists(DATABASE_DIR):
        os.makedirs(DATABASE_DIR)
        print(f"Directorio '{DATABASE_DIR}' creado.")

    conn = None
    with db_lock:
        try:
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()

            # Habilitar el soporte para claves foráneas
            cursor.execute("PRAGMA foreign_keys = ON;")

            # 1. Crear la tabla 'grd'
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grd (
                    id INTEGER PRIMARY KEY,
                    descripcion TEXT
                )
            ''')
            print("Tabla 'grd' asegurada.")

            # 2. Crear la tabla 'historicos' con la clave foránea
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS historicos (
                    timestamp TEXT NOT NULL,
                    id_grd INTEGER NOT NULL,
                    conectado INTEGER,
                    PRIMARY KEY (timestamp, id_grd),
                    FOREIGN KEY (id_grd) REFERENCES grd(id)
                )
            ''')
            print("Tabla 'historicos' asegurada con clave foránea.")

            conn.commit()
            print(f"Esquema de base de datos en {DATABASE_FILE} creado/asegurado.")

        except sqlite3.Error as e:
            print(f"Error al configurar el esquema de la base de datos: {e}")
        finally:
            if conn:
                conn.close()