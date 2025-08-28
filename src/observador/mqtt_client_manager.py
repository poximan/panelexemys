import queue
from typing import List, Tuple, Optional
from src.observador.mqtt_driver import MqttDriver
import config

class MqttClientManager:
    """
    Manager que orquesta el driver MQTT.
    Correcciones realizadas:
      - Si el segundo parametro 'subscriptions' es en realidad una Queue (instanciacion erronea),
        se detecta y se usa como msg_queue en lugar de romper la iteracion de subscriptions.
      - Se aporta get_connection_status() para que la vista pueda consultar el estado con strings.
      - Se expone msg_queue para que broker_view y manager compartan la misma cola.
    """

    def __init__(self, logger, subscriptions: Optional[List[Tuple[str, int]]] = None):
        self.log = logger
        self._origen = "OBS/MQTT"

        # Crear driver
        self.driver = MqttDriver(logger=self.log)

        # Mensajes entrantes: por defecto una cola nueva
        self.msg_queue: "queue.Queue[Tuple[str, str]]" = queue.Queue()

        # Detectar si se paso la Queue en lugar de la lista de suscripciones (instanciacion erronea)
        if isinstance(subscriptions, queue.Queue):
            # Si detectamos una Queue, la usamos como msg_queue y dejamos subscriptions a None
            self.msg_queue = subscriptions
            subscriptions = None

        # Suscripciones por defecto (si no se dieron)
        if subscriptions is None:
            subscriptions = [
                ("estado/exemys", 0),
                ("estado/email", 0),
                ("estado/sensor", 0),
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

        # Publica estado inicial si corresponde
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
        # Re-suscribir en cada reconexion; aqui esperamos que self.subscriptions sea iterable de tuples
        self.log.log("MQTT Client Manager: on_connect OK. Suscribiendo topicos...", origen=self._origen)
        try:
            for topic, qos in self.subscriptions:
                # subscribe no bloquea si el driver esta conectado; driver hace log internamente
                self.driver.subscribe(topic, qos)
        except TypeError:
            # Proteccion adicional: si por alguna razon subscriptions no es iterable,
            # loggeamos y no propagamos la excepcion para no romper el hilo de callbacks
            self.log.log("MQTT Client Manager: subscriptions no es iterable en _on_driver_connect.", origen=self._origen)

    def _on_driver_disconnect(self, client, userdata, rc):
        # no hay logica extra, paho maneja reintentos en connect_async + loop_start
        pass

    def _on_driver_message(self, client, userdata, msg):
        # Decodificar y encolar el mensaje para el resto del sistema
        try:
            payload = msg.payload.decode(errors="replace")
        except Exception:
            payload = str(msg.payload)

        # Log liviano
        self.log.log(f"Mensaje en {msg.topic}: {payload}", origen=self._origen)

        try:
            self.msg_queue.put_nowait((msg.topic, payload))
        except queue.Full:
            # descartar si la cola esta llena; no queremos lanzar excepciones en callbacks
            pass

    # ----------------- API hacia el resto del sistema
    def publish(self, topic: str, payload, qos: int = 0, retain: bool = False):
        self.driver.publish(topic, payload, qos=qos, retain=retain)

    def subscribe(self, topic: str, qos: int = 0):
        # Agregar suscripcion dinamica y suscribir en el driver si ya conectado
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
        """
        Retorna 'conectado' si el driver indica conectado, 'conectando' si start() fue llamado
        y aun no hay conexion, o 'desconectado' en otro caso.
        Esta funcion facilita la integracion con la UI que espera strings.
        """
        if self.driver.is_connected():
            return 'conectado'
        if self._started:
            return 'conectando'
        return 'desconectado'

    def set_message_queue(self, q: "queue.Queue[Tuple[str,str]]"):
        """
        Permite inyectar/exponer una cola externa para que la vista y el manager usen la misma cola.
        Evita errores si la inicializacion en otro lugar paso la cola por error.
        """
        if isinstance(q, queue.Queue):
            self.msg_queue = q