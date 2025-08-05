import sqlite3
import os
import threading
import config # Importa la configuracion

# Rutas de la base de datos usando config.py
DATABASE_DIR = config.DATABASE_DIR
DATABASE_FILE = os.path.join(DATABASE_DIR, config.DATABASE_NAME)

# Bloqueo para asegurar la seguridad de los hilos al escribir/leer en la base de datos.
db_lock = threading.Lock()

def create_database_schema():
    """
    Crea el directorio 'data' si no existe y las tablas 'grd', 'historicos',
    'mensajes_enviados', 'reles' y 'fallas_reles' en la base de datos SQLite,
    incluyendo las claves foraneas.
    """
    if not os.path.exists(DATABASE_DIR):
        os.makedirs(DATABASE_DIR)
        print(f"Directorio '{DATABASE_DIR}' creado.")

    conn = None
    with db_lock:
        try:
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()

            # Habilitar el soporte para claves foraneas
            cursor.execute("PRAGMA foreign_keys = ON;")

            # 1. Crear tabla 'grd'
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grd (
                    id INTEGER PRIMARY KEY,
                    descripcion TEXT
                )
            ''')
            print("Tabla 'grd' asegurada.")

            # 2. Crear tabla 'historicos' con la clave foranea
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS historicos (
                    timestamp TEXT NOT NULL,
                    id_grd INTEGER NOT NULL,
                    conectado INTEGER,
                    PRIMARY KEY (timestamp, id_grd),
                    FOREIGN KEY (id_grd) REFERENCES grd(id)
                )
            ''')
            print("Tabla 'historicos' asegurada con clave foranea.")

            # 3. Crear tabla 'mensajes_enviados'
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mensajes_enviados (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    message_type TEXT, -- 'global_connectivity_alarm', 'individual_grd_alarm_X', etc.
                    recipient TEXT,
                    success INTEGER NOT NULL -- 1 para True, 0 para False
                )
            ''')
            print("Tabla 'mensajes_enviados' asegurada.")

            # 4. Crear tabla 'reles'
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_modbus INTEGER UNIQUE,
                    descripcion TEXT
                )
            ''')
            print("Tabla 'reles' asegurada.")

            # 5. Crear tabla 'fallas_reles'
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fallas_reles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_rele INTEGER NOT NULL,
                    numero_falla INTEGER NOT NULL,
                    timestamp DATETIME NOT NULL,
                    fasea_corr INTEGER,
                    faseb_corr INTEGER,
                    fasec_corr INTEGER,
                    tierra_corr INTEGER,
                    FOREIGN KEY (id_rele) REFERENCES reles(id)
                )
            ''')
            print("Tabla 'fallas_reles' asegurada con clave foranea.")

            conn.commit()
            print(f"Esquema de base de datos en {DATABASE_FILE} creado/asegurado.")

        except sqlite3.Error as e:
            print(f"Error al configurar el esquema de la base de datos: {e}")
        finally:
            if conn:
                conn.close()