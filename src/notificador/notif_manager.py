import datetime
from src.logger import Logosaurio
import config
from .notif_global import NotifGlobal
from .notif_nodo import NotifNodo
from .notif_modem import NotifModem
from . import email_sender
from src.persistencia.dao_mensajes_enviados import mensajes_enviados_dao

class NotifManager:
    def __init__(self, logger: Logosaurio, excluded_grd_ids: set):
        self.logger = logger
        self.global_notifier = NotifGlobal(logger)
        self.nodo_notifier = NotifNodo(logger, excluded_grd_ids)
        self.modem_notifier = NotifModem(logger)

    def process_alarms(self, current_percentage: float, disconnected_grds: list):
        """
        Procesa todas las condiciones de alarma y dispara las notificaciones correspondientes.
        """
        # Evaluar alarma global
        if self.global_notifier.evaluate_condition(current_percentage):
            subject = "Middleware sin conexion"
            body = (f"Conectividad global de los exemys ha caido por debajo del "
                    f"{config.GLOBAL_THRESHOLD_ROJO}% "
                    f"({current_percentage:.2f}%) por mas de "
                    f"{config.ALARM_MIN_SUSTAINED_DURATION_MINUTES} minutos.\n")
            self._send_notification_and_log(subject, body, 'global_connectivity_alarm', config.ALARM_EMAIL_RECIPIENT)

        # Evaluar alarmas de nodos individuales
        grds_to_alert = self.nodo_notifier.evaluate_condition(current_percentage, disconnected_grds)
        for grd_info in grds_to_alert:
            subject = f"{grd_info['description']} sin conexion"
            body = (f"GRD {grd_info['description']} sin conexion por mas de "
                    f"{config.ALARM_MIN_SUSTAINED_DURATION_MINUTES} minutos, "
                    f"con conectividad global por encima del "
                    f"{config.GLOBAL_THRESHOLD_ROJO}% ({current_percentage:.2f}%).\n")
            self._send_notification_and_log(subject, body, f"individual_grd_alarm_{grd_info['description']}", config.ALARM_EMAIL_RECIPIENT)

        # Evaluar alarma del modem
        if self.modem_notifier.evaluate_condition():
            subject = "Alarma de ruteo de modem"
            body = (f"El modem del ruteo ha estado desconectado por mas de "
                    f"{config.ALARM_MIN_SUSTAINED_DURATION_MINUTES} minutos.")
            self._send_notification_and_log(subject, body, 'modem_connectivity_alarm', config.ALARM_EMAIL_RECIPIENT)

    def _send_notification_and_log(self, subject: str, body: str, alarm_type: str, recipient: str):
        """Envía el email y registra el mensaje en la base de datos."""
        sent_successfully = False
        try:
            email_sender.send_alarm_email(recipient, subject, body)
            sent_successfully = True
            self.logger.log(f"ALARMA DISPARADA: {subject}. Email enviado.", origen="ALRM/EXP")
        except Exception as e:
            self.logger.log(f"ERROR al enviar email de alarma: {e}", origen="ALRM/EXP")
        
        mensajes_enviados_dao.insert_sent_message(
            subject, 
            body, 
            datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            alarm_type,
            recipient,
            sent_successfully
        )