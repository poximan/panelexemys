import os
import sqlite3
from .dao.dao_base import db_lock, get_db_connection, DATABASE_DIR, DATABASE_FILE

def create_database_schema():
    """
    Asegura directorio y tablas SQLite:
    - grd
    - historicos
    - mensajes_enviados
    - reles
    - fallas_reles
    Usa el mismo RLock (db_lock) y get_db_connection() de dao_base.
    """
    if not os.path.exists(DATABASE_DIR):
        os.makedirs(DATABASE_DIR, exist_ok=True)
        print(f"Directorio '{DATABASE_DIR}' creado.")

    with db_lock:
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # 1) Tabla 'grd'
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS grd (
                    id INTEGER PRIMARY KEY,
                    descripcion TEXT
                )
            """)
            print("Tabla 'grd' asegurada.")

            # 2) Tabla 'historicos'
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS historicos (
                    timestamp TEXT NOT NULL,
                    id_grd INTEGER NOT NULL,
                    conectado INTEGER,
                    PRIMARY KEY (timestamp, id_grd),
                    FOREIGN KEY (id_grd) REFERENCES grd(id)
                )
            """)
            print("Tabla 'historicos' asegurada.")

            # 3) Tabla 'mensajes_enviados'
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mensajes_enviados (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    message_type TEXT,
                    recipient TEXT,
                    success INTEGER NOT NULL
                )
            """)
            print("Tabla 'mensajes_enviados' asegurada.")

            # 4) Tabla 'reles'
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_modbus INTEGER UNIQUE,
                    descripcion TEXT
                )
            """)
            print("Tabla 'reles' asegurada.")

            # 5) Tabla 'fallas_reles'
            cursor.execute("""
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
            """)
            print("Tabla 'fallas_reles' asegurada.")

            conn.commit()
            print(f"Esquema de base de datos en {DATABASE_FILE} creado/asegurado.")
        except sqlite3.Error as e:
            print(f"Error al configurar el esquema de la base de datos: {e}")
        finally:
            if conn:
                conn.close()