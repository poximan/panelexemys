# src/notificador/alarm_notifier.py

import os
import time
from datetime import datetime
from src.logger import Logosaurio
import config
from src.persistencia.dao_historicos import historicos_dao
from .notif_manager import NotifManager # <-- Importamos el nuevo orquestador

class AlarmNotifier:
    def __init__(self, logger: Logosaurio):
        self.logger = logger
        self.excluded_grd_ids: set = set()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.exclusion_file_path = os.path.join(script_dir, 'grd_exclusion_list.txt')
        self.notifier = NotifManager(self.logger, self.excluded_grd_ids)

    def _load_excluded_grd_ids(self):
        """Carga los IDs de GRD de un archivo de texto en la lista de exclusion."""
        self.excluded_grd_ids.clear()
        if not os.path.exists(self.exclusion_file_path):
            self.logger.log(f"El archivo de exclusion '{self.exclusion_file_path}' no existe.", origen="NOTIF/ORQ")
            return
        try:
            with open(self.exclusion_file_path, 'r') as f:
                for line in f:
                    grd_id = line.strip()
                    if grd_id:
                        self.excluded_grd_ids.add(grd_id)
            self.logger.log(f"GRD IDs excluidos cargados: {self.excluded_grd_ids}", origen="NOTIF/ORQ")
        except Exception as e:
            self.logger.log(f"ERROR al cargar los IDs de GRD excluidos: {e}", origen="NOTIF/ORQ")

    def start_observer_loop(self):
        """
        Inicia el bucle principal del observador de alarmas, delegando la lógica.
        """
        self.logger.log("Iniciando observador de alarmas...", origen="NOTIF/ORQ")
        self._load_excluded_grd_ids()

        while True:
            try:
                latest_states_from_db = historicos_dao.get_latest_states_for_all_grds()
                total_grds_for_kpi = len(latest_states_from_db)
                connected_grds_count = sum(1 for state in latest_states_from_db.values() if state == 1)
                
                current_percentage = 0
                if total_grds_for_kpi > 0:
                    current_percentage = (connected_grds_count / total_grds_for_kpi) * 100
                
                disconnected_grds_data = historicos_dao.get_all_disconnected_grds()
                
                # Delegamos la lógica de evaluación y notificación al NotifManager
                self.notifier.process_alarms(current_percentage, disconnected_grds_data)

            except Exception as e:
                self.logger.log(f"ERROR en el observador de alarmas: {e}", origen="NOTIF/ORQ")

            time.sleep(config.ALARM_CHECK_INTERVAL_SECONDS)