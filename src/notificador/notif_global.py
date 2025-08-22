import datetime
from typing import Dict, Any
from src.logger import Logosaurio
import config

class NotifGlobal:
    def __init__(self, logger: Logosaurio):
        self.logger = logger
        self.state: Dict[str, Any] = {
            'start_time': None,
            'triggered': False,
            'last_check_state': None
        }

    def evaluate_condition(self, current_percentage: float) -> bool:
        """
        Evalúa la condición de alarma global.
        Retorna True si la alarma debe ser disparada, False en caso contrario.
        """
        is_below_threshold = current_percentage < config.GLOBAL_THRESHOLD_ROJO

        if is_below_threshold:
            if self.state['start_time'] is None:
                self.state['start_time'] = datetime.datetime.now()
                self.logger.log(
                    f"Alarma potencial: Conectividad global ({current_percentage:.2f}%) por debajo del {config.GLOBAL_THRESHOLD_ROJO}% - Iniciando conteo.", 
                    origen="NOTIF/GBL"
                )
            sustained_duration = datetime.datetime.now() - self.state['start_time']
            min_duration = datetime.timedelta(minutes=config.ALARM_MIN_SUSTAINED_DURATION_MINUTES)
            
            if sustained_duration >= min_duration and not self.state['triggered']:
                self.state['triggered'] = True
                return True
        else:
            if self.state['start_time'] is not None:
                self.logger.log(
                    f"Alarma de conectividad global resuelta. Conectividad actual: {current_percentage:.2f}%.", 
                    origen="NOTIF/GBL"
                )
            self.state['start_time'] = None
            self.state['triggered'] = False

        self.state['last_check_state'] = current_percentage
        return False