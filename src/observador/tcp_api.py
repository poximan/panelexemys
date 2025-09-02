import json
import os
import time
from .tcp_actividad.method.tcp import tcp
from .tcp_actividad.logs import logs
from src.logger import Logosaurio
from .mqtt_topic_publisher import MqttTopicPublisher
from datetime import datetime
import config

class check_host:
    def __init__(self, logger: Logosaurio):
        self.tcp_class = tcp(logger)
        self.logs_class = logs(logger)

    def check_host_run(self, target: str, max_nodes: int) -> bool:
        """
        Ejecuta el chequeo TCP contra check-host.
        """
        return self.tcp_class.tcp_run(target=target, max_nodes=max_nodes)

def start_api_monitor(logger: Logosaurio, host: str, port: int):
    """
    Hilo que monitorea la conexión del módem/ruteo y publica el estado en:
      - config.MQTT_TOPIC_MODEM_CONEXION  (retain, QoS según config)
    """
    publisher = MqttTopicPublisher(logger=logger)
    last_payload = None

    while True:
        try:
            check_host_instance = check_host(logger)
            connection_ok = check_host_instance.check_host_run(target=f"{host}:{port}", max_nodes=3)

            current_status = "conectado" if connection_ok else "desconectado"
            logger.log(f"Estado de la conexión: {current_status}", origen="TCP/API")

            # Persistimos en observar.json (para otras partes del sistema)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            observar_file_path = os.path.join(script_dir, 'observar.json')

            try:
                if os.path.exists(observar_file_path):
                    with open(observar_file_path, 'r') as f:
                        content = f.read().strip()
                        data = json.loads(content) if content else {}
                else:
                    data = {}

                data['ip200_estado'] = current_status

                with open(observar_file_path, 'w') as f:
                    json.dump(data, f, indent=4)

            except (IOError, json.JSONDecodeError) as e:
                logger.log(f"ERROR al guardar el estado en {observar_file_path}: {e}", origen="TCP/API")

            # Publicación MQTT (retain) sólo si cambia o en el primer ciclo
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
                logger.log(f"Publicado estado de módem en {config.MQTT_TOPIC_MODEM_CONEXION}: {payload}", origen="TCP/API")

        except Exception as e:
            logger.log(f"Error inesperado en el monitor TCP: {e}", origen="TCP/API")

        time.sleep(300)