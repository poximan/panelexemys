import sqlite3
from datetime import datetime, timedelta
import random
import numpy as np
import os
import config                   # Importa el archivo de configuracion
from . import ddl_esquema       # Importa el modulo para asegurar el esquema
from .dao_grd import grd_dao as dao 

# Rutas de la base de datos usando config.py
DATABASE_DIR = config.DATABASE_DIR
DATABASE_FILE = os.path.join(DATABASE_DIR, config.DATABASE_NAME)

def populate_database_conditionally():
    """
    Puebla la tabla 'historicos' con datos historicos ficticios si config.POBLAR_BD es True.
    Genera un numero de registros basado en HISTORICAL_DAYS_TO_GENERATE y
    HISTORICAL_DATA_INTERVAL_SECONDS, distribuidos entre los GRD_IDs configurados
    en config.GRD_DESCRIPTIONS. Siempre inserta los datos, sin borrar nada si ya existen
    (usa INSERT OR IGNORE).
    """
    # Aseguramos que la tabla exista antes de intentar poblar.
    # Esta llamada ya la hace `app.py` al inicio, pero no esta de mas tenerla aqui
    # por si `bd_poblar.py` se ejecuta de forma independiente.
    ddl_esquema.create_database_schema()

    if config.POBLAR_BD:
        conn = None
        try:
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()

            grd_descriptions_map = config.GRD_DESCRIPTIONS
            num_grd_ids_to_use = len(grd_descriptions_map)

            if num_grd_ids_to_use <= 0:
                print("ADVERTENCIA: config.GRD_DESCRIPTIONS esta vacio. No se pueden generar datos ficticios para GRDs.")
                return

            # Calcular el numero total de entradas deseado
            # Numero de intervalos por dia * numero de dias
            entries_per_day = (24 * 60 * 60) // config.HISTORICAL_DATA_INTERVAL_SECONDS
            total_entries_per_grd = entries_per_day * config.HISTORICAL_DAYS_TO_GENERATE
            total_insertions_desired = total_entries_per_grd * num_grd_ids_to_use

            # Calcular el timestamp de inicio para los datos historicos
            start_time_for_historical_data = datetime.now() - timedelta(days=config.HISTORICAL_DAYS_TO_GENERATE)

            data_to_insert = []
            # Diccionarios para mantener el ultimo estado y la ultima marca de tiempo por cada GRD.
            grd_last_states = {}
            grd_current_timestamps = {} # Usar para seguir el tiempo hacia adelante

            print(f"POBLAR_BD es True. Insertando datos ficticios en la tabla 'historicos' y 'grd'...")
            print(f"Se generaran aproximadamente {total_insertions_desired} entradas ficticias para {num_grd_ids_to_use} GRDs, cubriendo {config.HISTORICAL_DAYS_TO_GENERATE} dias.")

            # Iterar sobre las claves (IDs) y valores (descripciones) de GRD_DESCRIPTIONS
            for grd_id, description in grd_descriptions_map.items():
                # Asegura que el GRD ID exista en la tabla 'grd' con su descripcion
                dao.insert_grd_description(grd_id, description)
                
                # Inicializa el estado y el tiempo para cada GRD desde el pasado
                grd_last_states[grd_id] = bool(random.getrandbits(1))
                grd_current_timestamps[grd_id] = start_time_for_historical_data

                for _ in range(total_entries_per_grd):
                    # Avanza el tiempo segun el intervalo configurado
                    grd_current_timestamps[grd_id] += timedelta(seconds=config.HISTORICAL_DATA_INTERVAL_SECONDS)

                    # Simula un cambio de estado con una probabilidad del 25%
                    if np.random.rand() < 0.25:
                        grd_last_states[grd_id] = not grd_last_states[grd_id]
                    
                    entry_time = grd_current_timestamps[grd_id].strftime('%Y-%m-%d %H:%M:%S')
                    data_to_insert.append((entry_time, grd_id, int(grd_last_states[grd_id])))
            
            # Ordenar los datos por timestamp antes de la insercion masiva
            # Esto ayuda a evitar bloqueos y optimiza la insercion en algunas bases de datos
            data_to_insert.sort(key=lambda x: x[0])

            cursor.executemany(f'''
                INSERT OR IGNORE INTO historicos (timestamp, id_grd, conectado)
                VALUES (?, ?, ?)
            ''', data_to_insert)
            conn.commit()
            print(f"Poblacion completada: {cursor.rowcount} registros insertados en 'historicos'. Los duplicados existentes (si los hubo) fueron ignorados.")
        
        except sqlite3.Error as e:
            print(f"Error al poblar la base de datos con datos ficticios: {e}")
        finally:
            if conn:
                conn.close()
    else:
        print("POBLAR_BD es False. No se poblara la base de datos con datos ficticios.")