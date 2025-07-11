import sqlite3
from .dao_base import get_db_connection, db_lock # Importa las funciones y variables de dao_base

class FallasRelesDAO:
    """
    Clase DAO para interactuar con la tabla 'fallas_reles' en la base de datos SQLite.
    """
    def __init__(self):
        pass

    def insert_falla_rele(self, id_rele: int, numero_falla: int, timestamp: str,
                          fasea_corr: int | None, faseb_corr: int | None,
                          fasec_corr: int | None, tierra_corr: int | None):
        """
        Inserta un registro de falla de rele en la tabla 'fallas_reles'.
        """
        conn = None
        with db_lock:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                # PRAGMA foreign_keys = ON; se asume que ya se maneja en get_db_connection o ddl_esquema

                cursor.execute('''
                    INSERT INTO fallas_reles (id_rele, numero_falla, timestamp,
                                              fasea_corr, faseb_corr, fasec_corr, tierra_corr)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (id_rele, numero_falla, timestamp,
                      fasea_corr, faseb_corr, fasec_corr, tierra_corr))
                conn.commit()
                print(f"Falla (Nº {numero_falla}) para Rele interno ID {id_rele} registrada en DB.")
            except sqlite3.Error as e:
                print(f"ERROR al insertar falla de rele en la base de datos: {e}")
            finally:
                if conn:
                    conn.close()

    def falla_exists(self, id_rele: int, numero_falla: int, timestamp: str) -> bool:
        """
        Verifica si ya existe una falla con la misma combinacion de id_rele, numero_falla y timestamp.
        Retorna True si existe, False en caso contrario.
        """
        conn = None
        with db_lock:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 1 FROM fallas_reles
                    WHERE id_rele = ? AND numero_falla = ? AND timestamp = ?
                ''', (id_rele, numero_falla, timestamp))
                return cursor.fetchone() is not None
            except sqlite3.Error as e:
                print(f"ERROR al verificar existencia de falla en la base de datos: {e}")
                return False
            finally:
                if conn:
                    conn.close()

# Instancia global del DAO para fallas de reles
fallas_reles_dao = FallasRelesDAO()