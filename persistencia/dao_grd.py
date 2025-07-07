import sqlite3
from .dao_base import get_db_connection, db_lock

class GrdDAO:
    def insert_grd_description(self, grd_id: int, description: str):
        """
        Inserta una descripción para un GRD_ID en la tabla 'grd'.
        Usa INSERT OR IGNORE para no insertar si el ID ya existe.
        """
        conn = None
        with db_lock:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO grd (id, descripcion)
                    VALUES (?, ?)
                ''', (grd_id, description))
                conn.commit()
                if cursor.rowcount > 0:
                    print(f"Descripción insertada para GRD ID {grd_id}: '{description}'")
            except sqlite3.Error as e:
                print(f"Error al insertar descripción GRD: {e}")
            finally:
                if conn:
                    conn.close()

    def get_grd_description(self, grd_id: int):
        """
        Obtiene la descripción de un GRD_ID.
        """
        conn = None
        with db_lock:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT descripcion FROM grd WHERE id = ?", (grd_id,))
                result = cursor.fetchone()
                return result['descripcion'] if result else None
            except sqlite3.Error as e:
                print(f"Error al obtener descripción de GRD {grd_id}: {e}")
                return None
            finally:
                if conn:
                    conn.close()

    def grd_exists(self, grd_id: int) -> bool:
        """
        Verifica si un GRD_ID existe en la tabla 'grd'.
        Retorna True si existe, False en caso contrario.
        """
        conn = None
        with db_lock:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()        
                cursor.execute("SELECT 1 FROM grd WHERE id = ?", (grd_id,))
                return cursor.fetchone() is not None
            except sqlite3.Error as e:
                print(f"Error al verificar la existencia de GRD ID {grd_id}: {e}")
                return False
            finally:
                if conn:
                    conn.close()

    def get_all_grds_with_descriptions(self) -> dict:
        """
        Recupera todos los GRD IDs y sus descripciones de la tabla 'grd',
        excluyendo aquellos cuya descripción sea 'reserva'.
        Retorna un diccionario en formato {grd_id: descripcion}.
        """
        conn = None
        grds_data = {}
        with db_lock:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT id, descripcion FROM grd WHERE descripcion <> 'reserva' ORDER BY id ASC;")
                rows = cursor.fetchall()
                for row in rows:
                    grds_data[row['id']] = row['descripcion']
            except sqlite3.Error as e:
                print(f"Error al obtener todos los GRD con descripciones: {e}")
            finally:
                if conn:
                    conn.close()
        return grds_data

# Instancia de la clase para usar sus métodos
grd_dao = GrdDAO()