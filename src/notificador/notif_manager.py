import datetime
from typing import List
from src.logger import Logosaurio
from .notif_global import NotifGlobal
from .notif_nodo import NotifNodo
from .notif_modem import NotifModem
from . import email_sender
from src.persistencia.dao_mensajes_enviados import mensajes_enviados_dao
from src.persistencia.dao_historicos import historicos_dao
from src.observador import mqtt_event_bus as bus
import config

class NotifManager:
    def __init__(self, logger: Logosaurio, excluded_grd_ids: set):
        self.logger = logger
        self.global_notifier = NotifGlobal(logger)
        self.nodo_notifier = NotifNodo(logger, excluded_grd_ids)
        self.modem_notifier = NotifModem(logger)

    def run_alarm_processing(self):
        latest = historicos_dao.get_latest_states_for_all_grds()
        total = len(latest)
        conectados = sum(1 for v in latest.values() if v == 1)
        connection_percentage = (conectados / total) * 100 if total > 0 else 0

        disconnected = historicos_dao.get_all_disconnected_grds()
        self._process_alarms(connection_percentage, disconnected)

    def _process_alarms(self, current_percentage: float, disconnected_grds: list):
        if self.global_notifier.evaluate_condition(current_percentage):
            subject = "Middleware sin conexion"
            body = (f"Conectividad global de los exemys ha caido por debajo del "
                    f"{config.GLOBAL_THRESHOLD_ROJO}% ({current_percentage:.2f}%) por mas de "
                    f"{config.ALARM_MIN_SUSTAINED_DURATION_MINUTES} minutos.\n")
            self._send_notification_and_log(subject, body, config.ALARM_EMAIL_RECIPIENT)

        grds_to_alert = self.nodo_notifier.evaluate_condition(current_percentage, disconnected_grds)
        for grd_info in grds_to_alert:
            subject = f"{grd_info['description']} sin conexion"
            body = (f"GRD {grd_info['description']} sin conexion por mas de "
                    f"{config.ALARM_MIN_SUSTAINED_DURATION_MINUTES} minutos, "
                    f"con conectividad global por encima del "
                    f"{config.GLOBAL_THRESHOLD_ROJO}% ({current_percentage:.2f}%).\n")
            self._send_notification_and_log(subject, body, config.ALARM_EMAIL_RECIPIENT)

        if self.modem_notifier.evaluate_condition():
            subject = "Alarma de ruteo de modem"
            body = (f"El modem del ruteo ha estado desconectado por mas de "
                    f"{config.ALARM_MIN_SUSTAINED_DURATION_MINUTES} minutos.")
            self._send_notification_and_log(subject, body, config.ALARM_EMAIL_RECIPIENT)

    def _send_notification_and_log(self, subject: str, body: str, recipient: List[str]):
        ok = False
        try:
            email_sender.send_alarm_email(recipient, subject, body)
            ok = True
            self.logger.log(f"ALARMA DISPARADA: {subject}. Email enviado a: {', '.join(recipient)}", origen="ALRM/EXP")
        except Exception as e:
            self.logger.log(f"ERROR al enviar email de alarma a {', '.join(recipient)}: {e}", origen="ALRM/EXP")
        
        mensajes_enviados_dao.insert_sent_message(
            subject, 
            body, 
            datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "alarm_event",
            recipient,
            ok
        )

        # Evento SOLO a 'estado/email' (no retain)
        bus.publish_email_event(subject, ok)