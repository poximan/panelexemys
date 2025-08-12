import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from .dao_base import get_db_connection, db_lock
from .dao_grd import grd_dao # Se necesita para la validacion de GRD_ID

class HistoricosDAO:
    def insert_historico_reading(self, grd_id: int, timestamp: str, conectado_value: int):
        """
        Inserta una nueva lectura procesada para un GRD_ID especifico en la tabla 'historicos'.
        Primero verifica que el GRD_ID exista en la tabla 'grd'.
        """
        conn = None
        with db_lock:
            try:
                # Logica de validacion: el GRD_ID debe existir en la tabla 'grd'.
                if not grd_dao.grd_exists(grd_id):
                    print(f"Error: No se pudo insertar el dato para GRD ID {grd_id} ({timestamp}). Equipo desconocido: el ID no existe en la tabla 'grd'.")
                    return # No se procede con la insercion si el GRD no existe

                conn = get_db_connection()
                cursor = conn.cursor()
                
                columns = ['timestamp', 'id_grd', 'conectado']
                values = (timestamp, grd_id, conectado_value)

                cursor.execute(f'''
                    INSERT OR IGNORE INTO historicos ({', '.join(columns)})
                    VALUES ({', '.join(['?']*len(columns))})
                ''', values)
                conn.commit()
                # print(f"Dato insertado: GRD_ID {grd_id} ({timestamp}): Conectado: {conectado_value}") 
            except sqlite3.Error as e:
                print(f"Error al insertar lectura en 'historicos' para GRD ID {grd_id}: {e}")
            finally:
                if conn:
                    conn.close()

    def get_latest_connected_state_for_grd(self, grd_id: int):
        """
        Recupera el ultimo valor 'conectado' (binario) registrado para un GRD_ID especifico.
        Retorna None si no hay datos para ese GRD_ID.
        """
        conn = None
        with db_lock:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT conectado FROM historicos
                    WHERE id_grd = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (grd_id,))
                result = cursor.fetchone()
                return result['conectado'] if result else None
            except sqlite3.Error as e:
                print(f"Error al obtener el ultimo estado 'conectado' para GRD ID {grd_id}: {e}")
                return None
            finally:
                if conn:
                    conn.close()

    def get_latest_states_for_all_grds(self) -> dict: # Agregado 'self'
        """
        Recupera el ultimo estado 'conectado' para cada GRD_ID existente en la tabla 'historicos',
        excluyendo aquellos GRD cuya descripcion en la tabla 'grd' sea 'reserva'.
        Retorna un diccionario donde la clave es el grd_id y el valor es su ultimo estado (0 o 1).
        Si un GRD no tiene registros o es de 'reserva', no estara en el diccionario.
        """
        conn = None
        latest_states = {}
        with db_lock:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT h.id_grd, h.conectado
                    FROM historicos h
                    INNER JOIN (
                        SELECT id_grd, MAX(timestamp) AS max_timestamp
                        FROM historicos
                        GROUP BY id_grd
                    ) AS latest_records ON h.id_grd = latest_records.id_grd 
                        AND h.timestamp = latest_records.max_timestamp
                    INNER JOIN grd g ON h.id_grd = g.id
                    WHERE g.descripcion <> 'reserva'
                        AND g.descripcion <> 'SE - CD45 Murchison';
                """)
                
                rows = cursor.fetchall()
                for row in rows:
                    latest_states[row['id_grd']] = row['conectado']
            except sqlite3.Error as e:
                print(f"Error al obtener los ultimos estados para todos los GRD (excluyendo reservas): {e}")
            finally:
                if conn:
                    conn.close()
        return latest_states

    def get_all_disconnected_grds(self) -> list[dict]: # Agregado 'self'
        """
        Recupera los GRD_ID, sus descripciones y la estampa de tiempo de su ultima desconexion
        para los GRD que estan actualmente desconectados (estado 'conectado' = 0),
        excluyendo aquellos GRD cuya descripcion en la tabla 'grd' sea 'reserva'.
        La estampa de tiempo sera la del registro que indica el estado actual de desconexion.
        
        Esta funcion cumple con:
        1. Traer todos los equipos cuyo ULTIMO estado registrado es 'desconectado' (0).
        2. Excluir equipos cuya descripcion en la tabla 'grd' sea 'reserva'.
        3. Incluir la estampa de tiempo correspondiente a ese ULTIMO registro encontrado.
        Retorna una lista de diccionarios, ordenada por GRD ID.
        """
        conn = None
        disconnected_grds = []
        with db_lock:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT
                        h.id_grd,
                        g.descripcion,
                        h.timestamp AS last_disconnected_timestamp
                    FROM
                        historicos h
                    INNER JOIN (
                        SELECT
                            id_grd,
                            MAX(timestamp) AS max_timestamp
                        FROM
                            historicos
                        GROUP BY
                            id_grd
                    ) AS latest_grd_status ON h.id_grd = latest_grd_status.id_grd AND h.timestamp = latest_grd_status.max_timestamp
                    INNER JOIN
                        grd g ON h.id_grd = g.id
                    WHERE
                        h.conectado = 0 AND g.descripcion <> 'reserva'
                    ORDER BY
                        h.id_grd ASC;
                """)
                
                rows = cursor.fetchall()
                for row in rows:
                    disconnected_grds.append({
                        'id_grd': row['id_grd'],
                        'description': row['descripcion'],
                        'last_disconnected_timestamp': datetime.strptime(row['last_disconnected_timestamp'], '%Y-%m-%d %H:%M:%S') # Convertir a datetime
                    })
            except sqlite3.Error as e:
                print(f"Error al obtener los GRD desconectados con timestamp: {e}")
            finally:
                if conn:
                    conn.close()
        return disconnected_grds

    def get_connected_state_before_timestamp(self, grd_id: int, timestamp: datetime):
        """
        Recupera el valor 'conectado' inmediatamente anterior a un timestamp dado para un GRD_ID.
        Retorna None si no hay datos anteriores.
        """
        conn = None
        with db_lock:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT conectado FROM historicos
                    WHERE id_grd = ? AND timestamp < ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (grd_id, timestamp.strftime('%Y-%m-%d %H:%M:%S')))
                result = cursor.fetchone()
                return result['conectado'] if result else None
            except sqlite3.Error as e:
                print(f"Error al obtener estado anterior para GRD ID {grd_id} y {timestamp}: {e}")
                return None
            finally:
                if conn:
                    conn.close()

    def get_weekly_data_for_grd(self, grd_id: int, reference_date_str: str, page_number: int = 0) -> pd.DataFrame:
        """
        Obtiene los datos historicos de 'conectado' para un GRD_ID y una semana especifica,
        paginado hacia atras desde una fecha de referencia.
        Recupera 'timestamp', 'id_grd' y 'conectado'.
        """
        conn = None
        df = pd.DataFrame()
        with db_lock:
            try:
                conn = get_db_connection()
                
                reference_date = datetime.strptime(reference_date_str, '%Y-%m-%d')
                
                week_end_date = reference_date - timedelta(weeks=page_number)
                week_start_date = week_end_date - timedelta(days=6)

                query = f"""
                    SELECT timestamp, id_grd, conectado
                    FROM historicos
                    WHERE id_grd = ? AND timestamp BETWEEN '{week_start_date.strftime('%Y-%m-%d 00:00:00')}' AND '{week_end_date.strftime('%Y-%m-%d 23:59:59')}'
                    ORDER BY timestamp ASC;
                """
                
                df = pd.read_sql_query(query, conn, params=(grd_id,))
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            except sqlite3.Error as e:
                print(f"Error al obtener datos semanales para GRD ID {grd_id}: {e}")
            finally:
                if conn:
                    conn.close()
        return df

    def get_monthly_data_for_grd(self, grd_id: int, reference_date_str: str, page_number: int = 0) -> pd.DataFrame:
        """
        Obtiene los datos historicos de 'conectado' para un GRD_ID y un mes especifico,
        paginado hacia atras desde una fecha de referencia.
        """
        conn = None
        df = pd.DataFrame()
        with db_lock:
            try:
                conn = get_db_connection()
                
                current_dashboard_date = datetime.strptime(reference_date_str, '%Y-%m-%d')
                
                first_day_of_current_month = current_dashboard_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                
                target_month_first_day = first_day_of_current_month - relativedelta(months=page_number)
                
                target_month_last_day = target_month_first_day + relativedelta(months=1) - timedelta(microseconds=1)

                if page_number == 0:
                    month_end_datetime_for_query = datetime.now()
                else:
                    month_end_datetime_for_query = target_month_last_day 
                
                month_start_datetime_for_query = target_month_first_day 

                query = f"""
                    SELECT timestamp, id_grd, conectado
                    FROM historicos
                    WHERE id_grd = ? AND timestamp BETWEEN '{month_start_datetime_for_query.strftime('%Y-%m-%d %H:%M:%S')}' AND '{month_end_datetime_for_query.strftime('%Y-%m-%d %H:%M:%S')}'
                    ORDER BY timestamp ASC;
                """
                
                df = pd.read_sql_query(query, conn, params=(grd_id,))
                if not df.empty:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
            except sqlite3.Error as e:
                print(f"Error al obtener datos mensuales para GRD ID {grd_id}: {e}")
            finally:
                if conn:
                    conn.close()
        return df

    def get_all_data_for_grd(self, grd_id: int) -> pd.DataFrame:
        """
        Obtiene todos los datos historicos de 'conectado' para un GRD_ID especifico.
        """
        conn = None
        with db_lock:
            try:
                conn = get_db_connection()
                query = f"""
                    SELECT timestamp, id_grd, conectado
                    FROM historicos
                    WHERE id_grd = ?
                    ORDER BY timestamp ASC;
                """
                df = pd.read_sql_query(query, conn, params=(grd_id,))
                if not df.empty:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
            except sqlite3.Error as e:
                print(f"Error al obtener todos los datos para GRD ID {grd_id}: {e}")
            finally:
                if conn:
                    conn.close()
        return df

    def get_total_weeks_for_grd(self, grd_id: int, reference_date_str: str) -> int:
        """
        Calcula el numero total de semanas de datos historicos disponibles para un GRD_ID especifico.
        """
        conn = None
        with db_lock:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT MIN(timestamp) FROM historicos
                    WHERE id_grd = ?
                """, (grd_id,))
                min_ts_str = cursor.fetchone()['MIN(timestamp)'] # Acceder por nombre de columna
                
                if not min_ts_str:
                    return 0

                min_ts = datetime.strptime(min_ts_str, '%Y-%m-%d %H:%M:%S')
                current_time = datetime.now() 

                if current_time.date() < min_ts.date(): 
                    return 0 # Si el primer registro es futuro, no hay semanas "historicas"

                total_days = (current_time.date() - min_ts.date()).days
                total_weeks = (total_days // 7) + 1 
                
                return max(1, total_weeks) # Siempre al menos 1 si hay datos
            except sqlite3.Error as e:
                print(f"Error al calcular el total de semanas: {e}")
                return 0
            finally:
                if conn:
                    conn.close()

    def get_total_months_for_grd(self, grd_id: int, reference_date_str: str) -> int:
        """
        Calcula el numero total de meses de datos historicos disponibles para un GRD_ID especifico.
        """
        conn = None
        with db_lock:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT MIN(timestamp) FROM historicos
                    WHERE id_grd = ?
                """, (grd_id,))
                min_ts_str = cursor.fetchone()['MIN(timestamp)'] # Acceder por nombre de columna
                
                if not min_ts_str:
                    return 0

                min_ts = datetime.strptime(min_ts_str, '%Y-%m-%d %H:%M:%S')
                
                current_date_for_total = datetime.now() 

                if min_ts > current_date_for_total:
                    return 0 

                diff = relativedelta(current_date_for_total, min_ts)
                
                total_months = diff.years * 12 + diff.months + 1 
                
                return total_months
            except sqlite3.Error as e:
                print(f"Error al calcular el total de meses: {e}")
                return 0
            finally:
                if conn:
                    conn.close()

# Instancia de la clase para usar sus metodos
historicos_dao = HistoricosDAO()