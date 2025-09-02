import queue
from typing import List, Tuple, Optional
from src.observador.mqtt_driver import MqttDriver
import config

class MqttClientManager:
    """
    Manager que orquesta el driver MQTT.
    - Suscripciones por defecto 100% tomadas de config (sin hardcode).
    - Expone publish() para UI (broker_view) con QoS/retain que le pida la UI.
    """

    def __init__(self, logger, subscriptions: Optional[List[Tuple[str, int]]] = None):
        self.log = logger
        self._origen = "OBS/MQTT"

        # Crear driver
        self.driver = MqttDriver(logger=self.log)

        # Mensajes entrantes: por defecto una cola nueva
        self.msg_queue: "queue.Queue[Tuple[str, str]]" = queue.Queue()

        # Si erróneamente nos pasan una Queue en 'subscriptions', la tomamos como msg_queue
        if isinstance(subscriptions, queue.Queue):
            self.msg_queue = subscriptions
            subscriptions = None

        # Suscripciones por defecto (si no se dieron) — TODO desde config
        if subscriptions is None:
            subscriptions = [
                (config.MQTT_TOPIC_GRADO, 0),
                (config.MQTT_TOPIC_GRDS, 0),
                (config.MQTT_TOPIC_MODEM_CONEXION, 0),
            ]
        self.subscriptions = subscriptions

        # Registrar callbacks del driver hacia metodos del manager
        self.driver.register_on_connect(self._on_driver_connect)
        self.driver.register_on_disconnect(self._on_driver_disconnect)
        self.driver.set_on_message(self._on_driver_message)

        # Estado interno
        self._started = False

    # ----------------- Ciclo de vida
    def start(self) -> bool:
        if self._started:
            return True

        ok = self.driver.connect()
        if not ok:
            self.log.log("MQTT Client Manager: No se pudo establecer conexion inicial.", origen=self._origen)
            return False

        # Publica estado inicial si corresponde (online)
        online_topic = getattr(config, "MQTT_ONLINE_TOPIC", None)
        online_payload = getattr(config, "MQTT_ONLINE_PAYLOAD", "online")
        online_qos = int(getattr(config, "MQTT_ONLINE_QOS", 1))
        online_retain = bool(getattr(config, "MQTT_ONLINE_RETAIN", True))
        if online_topic:
            self.driver.publish(online_topic, online_payload, qos=online_qos, retain=online_retain)

        self._started = True
        self.log.log("MQTT Client Manager: Conexion establecida correctamente.", origen=self._origen)
        return True

    def stop(self):
        offline_topic = getattr(config, "MQTT_OFFLINE_TOPIC", None)
        offline_payload = getattr(config, "MQTT_OFFLINE_PAYLOAD", "offline")
        offline_qos = int(getattr(config, "MQTT_OFFLINE_QOS", 1))
        offline_retain = bool(getattr(config, "MQTT_OFFLINE_RETAIN", True))
        if offline_topic and self.driver.is_connected():
            self.driver.publish(offline_topic, offline_payload, qos=offline_qos, retain=offline_retain)

        self.driver.disconnect()
        self._started = False

    # ----------------- Callbacks encadenados del driver
    def _on_driver_connect(self, client, userdata, flags, rc):
        self.log.log("MQTT Client Manager: on_connect OK. Suscribiendo topicos...", origen=self._origen)
        try:
            for topic, qos in self.subscriptions:
                self.driver.subscribe(topic, qos)
        except TypeError:
            self.log.log("MQTT Client Manager: subscriptions no es iterable en _on_driver_connect.", origen=self._origen)

    def _on_driver_disconnect(self, client, userdata, rc):
        # paho maneja reconexiones desde MqttDriver
        pass

    def _on_driver_message(self, client, userdata, msg):
        # Decodificar y encolar el mensaje para el resto del sistema
        try:
            payload = msg.payload.decode(errors="replace")
        except Exception:
            payload = str(msg.payload)

        self.log.log(f"Mensaje en {msg.topic}: {payload}", origen=self._origen)

        try:
            self.msg_queue.put_nowait((msg.topic, payload))
        except queue.Full:
            pass

    # ----------------- API hacia el resto del sistema
    def publish(self, topic: str, payload, qos: int = 0, retain: bool = False):
        self.driver.publish(topic, payload, qos=qos, retain=retain)

    def subscribe(self, topic: str, qos: int = 0):
        self.subscriptions.append((topic, qos))
        if self.driver.is_connected():
            self.driver.subscribe(topic, qos)

    def get_message(self, timeout: Optional[float] = None):
        try:
            return self.msg_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def is_connected(self) -> bool:
        return self.driver.is_connected()

    def get_connection_status(self) -> str:
        if self.driver.is_connected():
            return 'conectado'
        if self._started:
            return 'conectando'
        return 'desconectado'

    def set_message_queue(self, q: "queue.Queue[Tuple[str,str]]"):
        if isinstance(q, queue.Queue):
            self.msg_queue = q