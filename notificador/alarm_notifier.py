import time
from datetime import datetime, timedelta
from persistencia.dao_historicos import historicos_dao
from persistencia.dao_mensajes_enviados import mensajes_enviados_dao
from . import email_sender
import config
import os # Importar el módulo os para manejar rutas de archivos

# Diccionarios para mantener el estado de las alarmas en memoria
# Formato: {'alarm_key': {'start_time': datetime, 'triggered': bool, 'last_check_state': any}}
global_connectivity_alarm_state = {
    'start_time': None,
    'triggered': False,
    'last_check_state': None # Almacena el porcentaje de conectividad
}

individual_grd_alarm_states = {}
# Formato: {grd_id: {'start_time': datetime, 'triggered': bool, 'description': str}}

# Variable global para almacenar los GRD IDs excluidos
EXCLUDED_GRD_IDS = set()

def _load_excluded_grd_ids(file_path):
    """
    Carga los IDs de GRD de un archivo de texto en la lista de exclusión.
    Cada línea del archivo debe contener un GRD ID.
    """
    global EXCLUDED_GRD_IDS
    EXCLUDED_GRD_IDS.clear() # Limpiar la lista existente antes de recargar
    if not os.path.exists(file_path):
        print(f"Advertencia: El archivo de exclusión '{file_path}' no existe. No se aplicarán exclusiones de GRD.")
        return

    try:
        with open(file_path, 'r') as f:
            for line in f:
                grd_id = line.strip()
                if grd_id: # Asegurarse de que la línea no esté vacía
                    EXCLUDED_GRD_IDS.add(grd_id)
        print(f"GRD IDs excluidos cargados desde '{file_path}': {EXCLUDED_GRD_IDS}")
    except Exception as e:
        print(f"ERROR al cargar los IDs de GRD excluidos desde '{file_path}': {e}")

def _check_global_connectivity_alarm(current_percentage: float):
    """
    Verifica la condición de alarma de conectividad global.
    Si cae por debajo del umbral y se sostiene por el tiempo mínimo, activa la alarma.
    """
    global global_connectivity_alarm_state

    # Condición 1: Grado de conectividad cae por debajo del 40%
    if current_percentage < config.GLOBAL_THRESHOLD_ROJO:
        if global_connectivity_alarm_state['start_time'] is None:
            # Si la condición se acaba de cumplir, registra el inicio
            global_connectivity_alarm_state['start_time'] = datetime.now()
            global_connectivity_alarm_state['triggered'] = False # Reinicia el flag de disparo
            print(f"Alarma potencial: Conectividad global ({current_percentage:.2f}%) por debajo del {config.GLOBAL_THRESHOLD_ROJO}% - Iniciando conteo.")
        else:
            # Si la condición ya está activa, verifica la duración
            sustained_duration = datetime.now() - global_connectivity_alarm_state['start_time']
            min_duration = timedelta(minutes=config.ALARM_MIN_SUSTAINED_DURATION_MINUTES)

            if sustained_duration >= min_duration and not global_connectivity_alarm_state['triggered']:
                # Si la duración mínima se alcanzó y no se ha disparado aún, envía el email
                subject = "Middleware sin conexión"
                body = (f"Conectividad global de los exemys ha caído por debajo del "
                                f"{config.GLOBAL_THRESHOLD_ROJO}% "
                                f"({current_percentage:.2f}%) por más de "
                                f"{config.ALARM_MIN_SUSTAINED_DURATION_MINUTES} minutos.\n"
                                f"Inicio de condición: {global_connectivity_alarm_state['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
                
                # --- MODIFICACIÓN CLAVE: Intentar enviar y persistir ---
                sent_successfully = False # Valor por defecto
                try:
                    email_sender.send_alarm_email(config.ALARM_EMAIL_RECIPIENT, subject, body)
                    sent_successfully = True
                    print("ALARMA DISPARADA: Conectividad global crítica (Middleware sin conexión). Email enviado.")
                except Exception as e:
                    print(f"ERROR al enviar email de alarma global: {e}")
                
                # Persistir el intento de envío en la base de datos usando el DAO específico
                mensajes_enviados_dao.insert_sent_message(
                    subject, 
                    body, 
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'), # Estampa de tiempo de la inserción
                    'global_connectivity_alarm', # Tipo de mensaje para identificarlo
                    config.ALARM_EMAIL_RECIPIENT,
                    sent_successfully
                )
                # --- FIN MODIFICACIÓN CLAVE ---

                global_connectivity_alarm_state['triggered'] = True # Marca como disparada
    else:
        # Si la condición ya no se cumple (conectividad por encima del umbral)
        if global_connectivity_alarm_state['start_time'] is not None:
            print(f"Alarma de conectividad global resuelta. Conectividad actual: {current_percentage:.2f}%.")
        # Reinicia el estado de la alarma
        global_connectivity_alarm_state['start_time'] = None
        global_connectivity_alarm_state['triggered'] = False

    global_connectivity_alarm_state['last_check_state'] = current_percentage


def _check_individual_grd_alarms(current_percentage: float, disconnected_grds: list):
    """
    Verifica las condiciones de alarma para GRDs individuales.
    Si un equipo está desconectado y la conectividad global es mayor al 40%,
    y la condición se sostiene, activa la alarma individual.
    """
    global individual_grd_alarm_states
    global EXCLUDED_GRD_IDS # Acceder a la variable global de GRD excluidos

    # Crear un set de GRDs desconectados actualmente para una búsqueda eficiente
    current_disconnected_ids = {grd['id_grd'] for grd in disconnected_grds}

    # Procesar GRDs que actualmente están desconectados.
    for grd_info in disconnected_grds:
        grd_id = grd_info['id_grd']
        grd_description = grd_info['description']
        
        # Condición 2: Equipo particular sin conexión Y conectividad global > 40%
        if current_percentage >= config.GLOBAL_THRESHOLD_ROJO:
            if grd_id in EXCLUDED_GRD_IDS:
                print(f"GRD {grd_id} ({grd_description}) está en la lista de exclusión. No se enviará alarma individual.")
                # Si el GRD está excluido, asegúrate de que no tenga un estado activo de alarma individual
                if grd_id in individual_grd_alarm_states:
                    del individual_grd_alarm_states[grd_id]
                continue # Saltar al siguiente GRD

            if grd_id not in individual_grd_alarm_states:
                # Si es la primera vez que detectamos esta desconexión bajo esta condición
                individual_grd_alarm_states[grd_id] = {
                    'start_time': datetime.now(),
                    'triggered': False,
                    'description': grd_description
                }
                print(f"Alarma potencial: GRD {grd_id} ({grd_description}) desconectado con conectividad global > {config.GLOBAL_THRESHOLD_ROJO}%. Iniciando conteo.")
            else:
                # Si la condición ya está activa para este GRD, verifica la duración
                sustained_duration = datetime.now() - individual_grd_alarm_states[grd_id]['start_time']
                min_duration = timedelta(minutes=config.ALARM_MIN_SUSTAINED_DURATION_MINUTES)

                if sustained_duration >= min_duration and not individual_grd_alarm_states[grd_id]['triggered']:
                    # Si la duración mínima se alcanzó y no se ha disparado, envía el email
                    subject = f"{grd_description} sin conexión"

                    body = (f"GRD {grd_id} ({grd_description}) sin conexión "
                                            f"por más de {config.ALARM_MIN_SUSTAINED_DURATION_MINUTES} minutos, "
                                            f"con conectividad global por encima del "
                                            f"{config.GLOBAL_THRESHOLD_ROJO}% "
                                            f"({current_percentage:.2f}%).\n"
                                            f"Inicio de condición: {individual_grd_alarm_states[grd_id]['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    sent_successfully = False # Valor por defecto
                    try:
                        email_sender.send_alarm_email(config.ALARM_EMAIL_RECIPIENT, subject, body)
                        sent_successfully = True
                        print(f"ALARMA DISPARADA: GRD {grd_id} ({grd_description}) desconectado. Email enviado.")
                    except Exception as e:
                        sent_successfully = False
                        print(f"ERROR al enviar email de alarma individual para GRD {grd_id}: {e}")
                    
                    # Persistir el intento de envío en la base de datos usando el DAO específico
                    mensajes_enviados_dao.insert_sent_message(
                        subject, 
                        body, 
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'), # Estampa de tiempo de la inserción
                        f'individual_grd_alarm_{grd_id}', # Tipo de mensaje específico para este GRD
                        config.ALARM_EMAIL_RECIPIENT,
                        sent_successfully
                    )

                    individual_grd_alarm_states[grd_id]['triggered'] = True # Marca como disparada
        else:
            # Si la conectividad global cae por debajo del 40%, o el GRD se reconecta,
            # resetea la alarma individual para este GRD (si existe)
            if grd_id in individual_grd_alarm_states:
                print(f"Alarma individual para GRD {grd_id} ({individual_grd_alarm_states[grd_id]['description']}) resuelta. Razones: conectividad global {current_percentage:.2f}% (debajo del umbral) o reconexión.")
                del individual_grd_alarm_states[grd_id]
        
    # Eliminar GRDs del estado de alarma individual si ya no están en la lista de desconectados
    # (porque se reconectaron) y la conectividad global NO ha caído (se mantiene por encima del ROJO)
    grds_to_remove_from_state = []
    # Usar list() para evitar RuntimeError: dictionary changed size during iteration si se modifica el diccionario
    for grd_id in list(individual_grd_alarm_states.keys()): 
        if grd_id not in current_disconnected_ids and \
           current_percentage >= config.GLOBAL_THRESHOLD_ROJO: # Solo si se reconectó y la conectividad global es buena
            print(f"Alarma individual para GRD {grd_id} ({individual_grd_alarm_states[grd_id]['description']}) resuelta (equipo reconectado).")
            grds_to_remove_from_state.append(grd_id)
        elif current_percentage < config.GLOBAL_THRESHOLD_ROJO and \
             individual_grd_alarm_states[grd_id]['start_time'] is not None:
             # Si la conectividad global ha caído, la condición de la alarma individual no se cumple
             # y también se considera "resuelta"
            print(f"Alarma individual para GRD {grd_id} ({individual_grd_alarm_states[grd_id]['description']}) resuelta (conectividad global baja).")
            grds_to_remove_from_state.append(grd_id)
    
    for grd_id in grds_to_remove_from_state:
        del individual_grd_alarm_states[grd_id]


def start_alarm_observer():
    """
    Inicia el bucle principal del observador de alarmas.
    """
    print("Iniciando observador de alarmas...")
    # Cargar la lista de GRD excluidos al iniciar el observador
    _load_excluded_grd_ids('./notificador/grd_exclusion_list.txt') # Puedes hacer que esta ruta sea configurable

    while True:
        try:
            # Obtener estado actual de conectividad global usando el DAO de historicos
            latest_states_from_db = historicos_dao.get_latest_states_for_all_grds()
            total_grds_for_kpi = len(latest_states_from_db)
            connected_grds_count = sum(1 for state in latest_states_from_db.values() if state == 1)

            current_percentage = 0
            if total_grds_for_kpi > 0:
                current_percentage = (connected_grds_count / total_grds_for_kpi) * 100

            # Verificar alarmas de conectividad global
            _check_global_connectivity_alarm(current_percentage)

            # Obtener GRDs actualmente desconectados usando el DAO de historicos
            disconnected_grds_data = historicos_dao.get_all_disconnected_grds()
            
            filtered_disconnected_grds = disconnected_grds_data 

            # Verificar alarmas de GRDs individuales
            _check_individual_grd_alarms(current_percentage, filtered_disconnected_grds)

        except Exception as e:
            print(f"ERROR en el observador de alarmas: {e}")
            # Considerar un tiempo de espera más largo en caso de error grave

        # Esperar el intervalo configurado antes de la próxima verificación
        time.sleep(config.ALARM_CHECK_INTERVAL_SECONDS)