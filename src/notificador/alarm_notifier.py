import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any
from . import email_sender
from src.persistencia.dao_historicos import historicos_dao
from src.persistencia.dao_mensajes_enviados import mensajes_enviados_dao
from src.logger import Logosaurio
import config

class AlarmNotifier:
    """
    Clase principal para monitorear y notificar sobre el estado de las alarmas.
    Encapsula la lógica de verificación de alarmas globales e individuales de GRD.
    """

    def __init__(self, logger: Logosaurio):
        self.logger = logger
        self.global_connectivity_alarm_state: Dict[str, Any] = {
            'start_time': None,
            'triggered': False,
            'last_check_state': None
        }
        self.individual_grd_alarm_states: Dict[int, Dict[str, Any]] = {}
        self.excluded_grd_ids: set = set()
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.exclusion_file_path = os.path.join(script_dir, 'grd_exclusion_list.txt')
    
    def _load_excluded_grd_ids(self):
        """Carga los IDs de GRD de un archivo de texto en la lista de exclusión."""
        self.excluded_grd_ids.clear()
        if not os.path.exists(self.exclusion_file_path):
            self.logger.log(
                f"El archivo de exclusion '{self.exclusion_file_path}' no existe. No se aplicaran exclusiones de GRD.", 
                origen="NOTIF"
            )
            return

        try:
            with open(self.exclusion_file_path, 'r') as f:
                for line in f:
                    grd_id = line.strip()
                    if grd_id:
                        self.excluded_grd_ids.add(grd_id)
            self.logger.log(f"GRD IDs excluidos cargados desde '{self.exclusion_file_path}': {self.excluded_grd_ids}", origen="NOTIF")
        except Exception as e:
            self.logger.log(
                f"ERROR al cargar los IDs de GRD excluidos desde '{self.exclusion_file_path}': {e}", 
                origen="NOTIF"
            )

    def _check_global_connectivity_alarm(self, current_percentage: float):
        """Verifica la condición de alarma de conectividad global."""
        if current_percentage < config.GLOBAL_THRESHOLD_ROJO:
            if self.global_connectivity_alarm_state['start_time'] is None:
                self.global_connectivity_alarm_state['start_time'] = datetime.now()
                self.global_connectivity_alarm_state['triggered'] = False
                self.logger.log(
                    f"Alarma potencial: Conectividad global ({current_percentage:.2f}%) por debajo del {config.GLOBAL_THRESHOLD_ROJO}% - Iniciando conteo.", 
                    origen="NOTIF"
                )
            else:
                sustained_duration = datetime.now() - self.global_connectivity_alarm_state['start_time']
                min_duration = timedelta(minutes=config.ALARM_MIN_SUSTAINED_DURATION_MINUTES)
                
                if sustained_duration >= min_duration and not self.global_connectivity_alarm_state['triggered']:
                    subject = "Middleware sin conexion"
                    body = (f"Conectividad global de los exemys ha caido por debajo del "
                                f"{config.GLOBAL_THRESHOLD_ROJO}% "
                                f"({current_percentage:.2f}%) por mas de "
                                f"{config.ALARM_MIN_SUSTAINED_DURATION_MINUTES} minutos.\n"
                                f"Inicio de condicion: {self.global_connectivity_alarm_state['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    sent_successfully = False
                    try:
                        email_sender.send_alarm_email(config.ALARM_EMAIL_RECIPIENT, subject, body)
                        sent_successfully = True
                        self.logger.log("ALARMA DISPARADA: Conectividad global critica (Middleware sin conexion). Email enviado.", origen="NOTIF")
                    except Exception as e:
                        self.logger.log(f"ERROR al enviar email de alarma global: {e}", origen="NOTIF")
                    
                    mensajes_enviados_dao.insert_sent_message(
                        subject, 
                        body, 
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'global_connectivity_alarm',
                        config.ALARM_EMAIL_RECIPIENT,
                        sent_successfully
                    )
                    self.global_connectivity_alarm_state['triggered'] = True
        else:
            if self.global_connectivity_alarm_state['start_time'] is not None:
                self.logger.log(
                    f"Alarma de conectividad global resuelta. Conectividad actual: {current_percentage:.2f}%.", 
                    origen="NOTIF"
                )
            self.global_connectivity_alarm_state['start_time'] = None
            self.global_connectivity_alarm_state['triggered'] = False

        self.global_connectivity_alarm_state['last_check_state'] = current_percentage

    def _check_individual_grd_alarms(self, current_percentage: float, disconnected_grds: list):
        """Verifica las condiciones de alarma para GRDs individuales."""
        current_disconnected_ids = {grd['id_grd'] for grd in disconnected_grds}

        for grd_info in disconnected_grds:
            grd_id = grd_info['id_grd']
            grd_description = grd_info['description']
            
            if current_percentage >= config.GLOBAL_THRESHOLD_ROJO:
                if grd_id in self.excluded_grd_ids:
                    self.logger.log(
                        f"GRD {grd_id} ({grd_description}) esta en la lista de exclusion. No se enviara alarma individual.", 
                        origen="NOTIF"
                    )
                    if grd_id in self.individual_grd_alarm_states:
                        del self.individual_grd_alarm_states[grd_id]
                    continue

                if grd_id not in self.individual_grd_alarm_states:
                    self.individual_grd_alarm_states[grd_id] = {
                        'start_time': datetime.now(),
                        'triggered': False,
                        'description': grd_description
                    }
                    self.logger.log(
                        f"Alarma potencial: GRD {grd_id} ({grd_description}) desconectado con conectividad global > {config.GLOBAL_THRESHOLD_ROJO}%. Iniciando conteo.", 
                        origen="NOTIF"
                    )
                else:
                    sustained_duration = datetime.now() - self.individual_grd_alarm_states[grd_id]['start_time']
                    min_duration = timedelta(minutes=config.ALARM_MIN_SUSTAINED_DURATION_MINUTES)

                    if sustained_duration >= min_duration and not self.individual_grd_alarm_states[grd_id]['triggered']:
                        subject = f"{grd_description} sin conexion"
                        body = (f"GRD {grd_id} ({grd_description}) sin conexion "
                                    f"por mas de {config.ALARM_MIN_SUSTAINED_DURATION_MINUTES} minutos, "
                                    f"con conectividad global por encima del "
                                    f"{config.GLOBAL_THRESHOLD_ROJO}% "
                                    f"({current_percentage:.2f}%).\n"
                                    f"Inicio de condicion: {self.individual_grd_alarm_states[grd_id]['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
                        
                        sent_successfully = False
                        try:
                            email_sender.send_alarm_email(config.ALARM_EMAIL_RECIPIENT, subject, body)
                            sent_successfully = True
                            self.logger.log(f"ALARMA DISPARADA: GRD {grd_id} ({grd_description}) desconectado. Email enviado.", origen="NOTIF")
                        except Exception as e:
                            self.logger.log(f"ERROR al enviar email de alarma individual para GRD {grd_id}: {e}", origen="NOTIF")
                        
                        mensajes_enviados_dao.insert_sent_message(
                            subject, 
                            body, 
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            f'individual_grd_alarm_{grd_id}',
                            config.ALARM_EMAIL_RECIPIENT,
                            sent_successfully
                        )
                        self.individual_grd_alarm_states[grd_id]['triggered'] = True
            else:
                if grd_id in self.individual_grd_alarm_states:
                    self.logger.log(
                        f"Alarma individual para GRD {grd_id} ({self.individual_grd_alarm_states[grd_id]['description']}) resuelta. Razones: conectividad global {current_percentage:.2f}% (debajo del umbral) o reconexion.", 
                        origen="NOTIF"
                    )
                    del self.individual_grd_alarm_states[grd_id]
        
        grds_to_remove_from_state = []
        for grd_id in list(self.individual_grd_alarm_states.keys()):
            if grd_id not in current_disconnected_ids and \
               current_percentage >= config.GLOBAL_THRESHOLD_ROJO:
                self.logger.log(
                    f"Alarma individual para GRD {grd_id} ({self.individual_grd_alarm_states[grd_id]['description']}) resuelta (equipo reconectado).", 
                    origen="NOTIF"
                )
                grds_to_remove_from_state.append(grd_id)
            elif current_percentage < config.GLOBAL_THRESHOLD_ROJO and \
                 self.individual_grd_alarm_states[grd_id]['start_time'] is not None:
                self.logger.log(
                    f"Alarma individual para GRD {grd_id} ({self.individual_grd_alarm_states[grd_id]['description']}) resuelta (conectividad global baja).", 
                    origen="NOTIF"
                )
                grds_to_remove_from_state.append(grd_id)
        
        for grd_id in grds_to_remove_from_state:
            del self.individual_grd_alarm_states[grd_id]

    def start_observer_loop(self):
        """
        Inicia el bucle principal del observador de alarmas.
        """
        self.logger.log("Iniciando observador de alarmas...", origen="NOTIF")
        self._load_excluded_grd_ids()

        while True:
            try:
                latest_states_from_db = historicos_dao.get_latest_states_for_all_grds()
                total_grds_for_kpi = len(latest_states_from_db)
                connected_grds_count = sum(1 for state in latest_states_from_db.values() if state == 1)

                current_percentage = 0
                if total_grds_for_kpi > 0:
                    current_percentage = (connected_grds_count / total_grds_for_kpi) * 100
                
                self._check_global_connectivity_alarm(current_percentage)
                
                disconnected_grds_data = historicos_dao.get_all_disconnected_grds()
                
                self._check_individual_grd_alarms(current_percentage, disconnected_grds_data)

            except Exception as e:
                self.logger.log(f"ERROR en el observador de alarmas: {e}", origen="NOTIF")

            time.sleep(config.ALARM_CHECK_INTERVAL_SECONDS)