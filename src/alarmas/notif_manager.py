import datetime
from typing import List
from src.logger import Logosaurio
from ..servicios.mqtt import mqtt_event_bus as bus
from .categorias.notif_global import NotifGlobal
from .categorias.notif_nodo import NotifNodo
from .categorias.notif_modem import NotifModem
from src.persistencia.dao.dao_mensajes_enviados import mensajes_enviados_dao
from src.persistencia.dao.dao_historicos import historicos_dao
from src.servicios.email.mensagelo_client import MensageloClient
import config

class NotifManager:
    """
    Orquestador de notificaciones:
    - Evalua condiciones (global, nodo, modem)
    - Encola email via mensagelo (asincronico, sin esperar entrega)
    - Publica evento en MQTT
    - Registra en DB local el intento de envio
    """
    def __init__(self, logger: Logosaurio, excluded_grd_ids: set):
        self.logger = logger
        self.global_notifier = NotifGlobal(logger)
        self.nodo_notifier = NotifNodo(logger, excluded_grd_ids)
        self.modem_notifier = NotifModem(logger)
        self.mail_client = MensageloClient()

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
            body = (
                f"Conectividad global de los exemys ha caido por debajo del "
                f"{config.GLOBAL_THRESHOLD_ROJO}% ({current_percentage:.2f}%) por mas de "
                f"{config.ALARM_MIN_SUSTAINED_DURATION_MINUTES} minutos.\n"
            )
            self._send_notification_and_log(subject, body, config.ALARM_EMAIL_RECIPIENT)

        grds_to_alert = self.nodo_notifier.evaluate_condition(current_percentage, disconnected_grds)
        for grd_info in grds_to_alert:
            subject = f"{grd_info['description']} sin conexion"
            body = (
                f"GRD {grd_info['description']} sin conexion por mas de "
                f"{config.ALARM_MIN_SUSTAINED_DURATION_MINUTES} minutos, "
                f"con conectividad global por encima del "
                f"{config.GLOBAL_THRESHOLD_ROJO}% ({current_percentage:.2f}%).\n"
            )
            self._send_notification_and_log(subject, body, config.ALARM_EMAIL_RECIPIENT)

        if self.modem_notifier.evaluate_condition():
            subject = "Alarma de ruteo de modem"
            body = (
                f"El modem del ruteo ha estado desconectado por mas de "
                f"{config.ALARM_MIN_SUSTAINED_DURATION_MINUTES} minutos."
            )
            self._send_notification_and_log(subject, body, config.ALARM_EMAIL_RECIPIENT)

    def _send_notification_and_log(self, subject: str, body: str, recipient: List[str]):
        """
        Encola el email en mensagelo y registra el intento en DB local.
        'ok' significa que mensagelo acepto el pedido (no que el SMTP lo haya entregado).
        """
        ok = False
        msg = ""
        try:
            ok, msg = self.mail_client.enqueue_email(
                recipients=recipient,
                subject=f"{config.ALARM_EMAIL_SUBJECT_PREFIX}{subject}",
                body=body,
                message_type="alarm_event",
            )
            if ok:
                self.logger.log(
                    f"ALARMA DISPARADA: {subject}. Pedido aceptado por mensagelo. Destinatarios: {', '.join(recipient)}",
                    origen="ALRM/EXP",
                )
            else:
                self.logger.log(
                    f"ERROR mensagelo no acepto el pedido para: {subject}. Detalle: {msg}",
                    origen="ALRM/EXP",
                )
        except Exception as e:
            self.logger.log(f"ERROR al encolar email de alarma: {e}", origen="ALRM/EXP")

        # Registro local en DB (usa RLock y get_db_connection del dao_base)
        mensajes_enviados_dao.insert_sent_message(
            subject=subject,
            body=body,
            timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            message_type="alarm_event",
            recipients=recipient,
            success=ok
        )

        # Evento SOLO a 'estado/email' (no retain)
        bus.publish_email_event(subject, ok)