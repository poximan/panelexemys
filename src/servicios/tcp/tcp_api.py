import time
from datetime import datetime
from ..mqtt.mqtt_topic_publisher import MqttTopicPublisher
from .tcp_actividad.method.tcp import tcp
from .tcp_actividad.logs import logs
from src.logger import Logosaurio
from src.utils.paths import update_observar_key
import config

# parametros de backoff
BASE_INTERVAL_SECONDS = 300  # segundos, comportamiento actual por defecto
BACKOFF_INITIAL = 30         # primer espera corta ante fallo
BACKOFF_MAX = 900            # maximo 15 min
BACKOFF_MULTIPLIER = 2

class check_host:
    """
    fachada para ejecutar chequeos tcp sobre check-host.net
    """
    def __init__(self, logger: Logosaurio):
        self.tcp_class = tcp(logger)
        self.logs_class = logs(logger)

    def check_host_run(self, target: str, max_nodes: int) -> bool:
        """
        ejecuta chequeo tcp y retorna True si al menos un nodo conecta
        """
        return self.tcp_class.tcp_run(target=target, max_nodes=max_nodes)

def start_api_monitor(logger: Logosaurio, host: str, port: int, mqtt_manager):
    """
    hilo que monitorea el estado del modem/ruteo y publica su estado en mqtt.
    ademas persiste ip200_estado en observar.json
    """
    publisher = MqttTopicPublisher(logger=logger, manager=mqtt_manager)
    last_payload = None
    failure_sleep = BACKOFF_INITIAL
    check_host_instance = check_host(logger)

    while True:
        try:
            connection_ok = check_host_instance.check_host_run(target=f"{host}:{port}", max_nodes=3)

            current_status = "conectado" if connection_ok else "desconectado"
            logger.log(f"Estado de la conexion: {current_status}", origen="TCP/API")

            # persistencia clave ip200_estado en observar.json
            try:
                update_observar_key("ip200_estado", current_status)
            except Exception as e:
                logger.log(f"ERROR al actualizar ip200_estado en observar.json: {e}", origen="TCP/API")

            # publicacion mqtt con retain
            payload = {
                "estado": current_status,
                "ts": datetime.now().isoformat(timespec="seconds")
            }
            if payload != last_payload:
                publisher.publish_json(
                    config.MQTT_TOPIC_MODEM_CONEXION,
                    payload,
                    qos=config.MQTT_PUBLISH_QOS_STATE,
                    retain=config.MQTT_PUBLISH_RETAIN_STATE
                )
                last_payload = payload
                logger.log(f"Publicado estado de modem en {config.MQTT_TOPIC_MODEM_CONEXION}: {payload}", origen="TCP/API")

            # estrategia de espera
            if connection_ok:
                # exito: resetea backoff y vuelve al intervalo base
                failure_sleep = BACKOFF_INITIAL
                time.sleep(BASE_INTERVAL_SECONDS)
            else:
                # fallo: aplica backoff exponencial con tope
                time.sleep(failure_sleep)
                failure_sleep = min(failure_sleep * BACKOFF_MULTIPLIER, BACKOFF_MAX)

        except Exception as e:
            logger.log(f"Error inesperado en el monitor TCP: {e}", origen="TCP/API")
            # en excepcion tambien aplica backoff
            time.sleep(failure_sleep)
            failure_sleep = min(failure_sleep * BACKOFF_MULTIPLIER, BACKOFF_MAX)
