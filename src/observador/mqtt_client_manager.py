import threading
import paho.mqtt.client as mqtt
from queue import Queue
from .mqtt_driver import MqttDriver
from src.logger import Logosaurio
import config

class MqttClientManager:
    """
    Gestiona el cliente MQTT, sus suscripciones y publicaciones.
    Modificado para ser usado en una aplicacion Dash con un hilo de fondo.
    """
    def __init__(self, logger: Logosaurio, message_queue: Queue):
        self.logger = logger
        self.mqtt_driver = MqttDriver(logger=self.logger)
        self.client = None
        self._stop_event = threading.Event()
        self.message_queue = message_queue  # Cola para mensajes recibidos

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """
        Callback que se ejecuta cuando el cliente se conecta al broker.
        Se usa para suscribirse a los tópicos.
        """
        if rc == 0:
            self.logger.log("MQTT Client Manager: Conectado al broker MQTT exitosamente.", origen="OBS/MQTT")
            # Suscribirse a los topicos definidos una vez conectado
            self.subscribe(config.MQTT_ESTADO_EXEMYS)
            self.subscribe(config.MQTT_ESTADO_EMAIL)
            self.subscribe(config.MQTT_TOPIC_SENSOR)
        else:
            self.logger.log(f"MQTT Client Manager: Fallo en la conexion, codigo: {rc}", origen="OBS/MQTT")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback que se ejecuta cuando el cliente se desconecta del broker."""
        self.logger.log("MQTT Client Manager: Desconectado del broker.", origen="OBS/MQTT")

    def _on_message(self, client, userdata, msg):
        """
        Callback que se ejecuta cuando se recibe un mensaje de un topico suscrito.
        Almacena el mensaje en la cola para que la app Dash pueda procesarlo.
        """
        message = {
            'topic': msg.topic,
            'payload': msg.payload.decode()
        }
        self.message_queue.put(message)
        self.logger.log(f"MQTT Client Manager: Mensaje recibido y encolado - Topico: {msg.topic}, Payload: {msg.payload.decode()}", origen="OBS/MQTT")

    def subscribe(self, topic: str, qos: int = 0):
        """
        Suscribe el cliente a un topico especifico.
        """
        if self.client and self.client.is_connected():
            result, mid = self.client.subscribe(topic, qos)
            if result == mqtt.MQTT_ERR_SUCCESS:
                self.logger.log(f"MQTT Client Manager: Suscrito al topico '{topic}' (mid={mid})", origen="OBS/MQTT")
            else:
                self.logger.log(f"MQTT Client Manager: Error al suscribirse al topico '{topic}': {result}", origen="OBS/MQTT")
        else:
            self.logger.log("MQTT Client Manager: Cliente no conectado, no se puede suscribir.", origen="OBS/MQTT")

    def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False):
        """
        Publica un mensaje en un topico especifico.
        """
        if self.client and self.client.is_connected():
            info = self.client.publish(topic, payload, qos, retain)
            info.wait_for_publish()
            self.logger.log(f"MQTT Client Manager: Mensaje publicado en '{topic}': '{payload}'", origen="OBS/MQTT")
        else:
            self.logger.log("MQTT Client Manager: Cliente no conectado, no se puede publicar.", origen="OBS/MQTT")

    def start(self):
        """
        Inicia el bucle de red del cliente MQTT. Este metodo es no-bloqueante.
        """
        self.client = self.mqtt_driver.connect()
        if self.client:
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            self.client.loop_start()
            self.logger.log("MQTT Client Manager: Bucle de red MQTT iniciado en un hilo de fondo.", origen="OBS/MQTT")
        else:
            self.logger.log("MQTT Client Manager: No se pudo iniciar el bucle MQTT, conexion fallida.", origen="OBS/MQTT")
    
    def stop(self):
        """
        Detiene el bucle de red del cliente MQTT.
        """
        if self.client:
            self.client.loop_stop()
            self.mqtt_driver.disconnect()
            self.logger.log("MQTT Client Manager: Bucle de red MQTT detenido.", origen="OBS/MQTT")

    def get_connection_status(self) -> str:
        """
        Devuelve el estado actual de la conexión del cliente MQTT,
        delegando la llamada al driver.
        Los estados posibles son: 'connecting', 'connected', 'disconnected'.
        """
        return self.mqtt_driver.get_connection_status()