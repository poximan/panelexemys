import json
import os
import datetime
from typing import Dict, Any
from src.logger import Logosaurio
import config

class NotifModem:
    def __init__(self, logger: Logosaurio):
        self.logger = logger
        self.state: Dict[str, Any] = {
            'start_time': None,
            'triggered': False,
            'description': "Alarma de ruteo de modem"
        }
        
        # Corregir la ruta del archivo
        script_dir = os.path.dirname(os.path.abspath(__file__))
                
        src_dir = os.path.dirname(script_dir)
        self.observar_file_path = os.path.join(src_dir, 'observador', 'observar.json')
    
    def evaluate_condition(self) -> bool:
        """
        Evalúa la condición de alarma del módem.
        Retorna True si la alarma debe ser disparada, False en caso contrario.
        """
        modem_status = self._get_modem_status()
        is_disconnected = modem_status == "desconectado"

        if is_disconnected:
            if self.state['start_time'] is None:
                self.state['start_time'] = datetime.datetime.now()
                self.logger.log("Alarma potencial: Router Modem desconectado. Iniciando conteo.", origen="NOTIF/MODEM")
            
            sustained_duration = datetime.datetime.now() - self.state['start_time']
            min_duration = datetime.timedelta(minutes=config.ALARM_MIN_SUSTAINED_DURATION_MINUTES)
            
            if sustained_duration >= min_duration and not self.state['triggered']:
                self.state['triggered'] = True
                return True
        else:
            if self.state['start_time'] is not None:
                self.logger.log("Alarma de router modem resuelta (reconectado).", origen="NOTIF/MODEM")
            self.state['start_time'] = None
            self.state['triggered'] = False

        return False

    def _get_modem_status(self) -> str:
        """Lee el estado del modem del archivo observar.json."""
        try:
            if not os.path.exists(self.observar_file_path):
                self.logger.log(f"El archivo {self.observar_file_path} no existe. Asumiendo modem conectado.", origen="NOTIF/MODEM")
                return "conectado"
            
            with open(self.observar_file_path, 'r') as f:
                data = json.load(f)
                return data.get('ip200_estado', "conectado")
        except (IOError, json.JSONDecodeError) as e:
            self.logger.log(f"ERROR al leer el estado del modem de observar.json: {e}. Asumiendo conectado.", origen="NOTIF/MODEM")
            return "conectado"