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
        self.message_queue = message_queue
        
    def _on_connect_callback(self, client, userdata, flags, rc, properties=None):
        """
        Callback que se ejecuta cuando el cliente se conecta.
        Aquí se manejan las suscripciones y otras acciones de inicio.
        """
        if rc == 0:
            self.logger.log("MQTT Client Manager: Conectado y listo para suscribirse.", origen="OBS/MQTT")
            
            # Suscripciones se realizan ahora, cuando la conexión es exitosa.
            self.subscribe(config.MQTT_ESTADO_EXEMYS)
            self.subscribe(config.MQTT_ESTADO_EMAIL)
            self.subscribe(config.MQTT_TOPIC_SENSOR)
            
            # Ejemplo de publicación que ahora funcionará
            self.publish("estado/sistema", "online")

        else:
            self.logger.log(f"MQTT Client Manager: Fallo en la conexión, código: {rc}", origen="OBS/MQTT")

    def _on_message_callback(self, client, userdata, msg):
        """
        Callback que se ejecuta cuando se recibe un mensaje.
        """
        message = {
            'topic': msg.topic,
            'payload': msg.payload.decode()
        }
        self.message_queue.put(message)
        self.logger.log(f"MQTT Client Manager: Mensaje recibido y encolado - Tópico: {msg.topic}, Payload: {msg.payload.decode()}", origen="OBS/MQTT")

    def subscribe(self, topic: str, qos: int = 0):
        """
        Suscribe el cliente a un tópico específico.
        """
        if self.client and self.client.is_connected():
            result, mid = self.client.subscribe(topic, qos)
            if result == mqtt.MQTT_ERR_SUCCESS:
                self.logger.log(f"MQTT Client Manager: Suscrito al tópico '{topic}' (mid={mid})", origen="OBS/MQTT")
            else:
                self.logger.log(f"MQTT Client Manager: Error al suscribirse al tópico '{topic}': {result}", origen="OBS/MQTT")
        else:
            self.logger.log("MQTT Client Manager: Cliente no conectado, no se puede suscribir.", origen="OBS/MQTT")

    def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False):
        """
        Publica un mensaje en un tópico específico.
        """
        if self.client and self.client.is_connected():
            info = self.client.publish(topic, payload, qos, retain)
            info.wait_for_publish()
            self.logger.log(f"MQTT Client Manager: Mensaje publicado en '{topic}': '{payload}'", origen="OBS/MQTT")
        else:
            self.logger.log("MQTT Client Manager: Cliente no conectado, no se puede publicar.", origen="OBS/MQTT")

    def start(self):
        """
        Inicia el bucle de red del cliente MQTT. Este método es no-bloqueante.
        """
        # El driver ahora maneja la sincronización.
        self.client = self.mqtt_driver.connect()
        if self.client:
            # Asignar los callbacks específicos de este manager
            self.client.on_connect = self._on_connect_callback
            self.client.on_message = self._on_message_callback
            self.logger.log("MQTT Client Manager: Bucle de red MQTT iniciado. Esperando conexión...", origen="OBS/MQTT")
        else:
            self.logger.log("MQTT Client Manager: No se pudo iniciar el bucle MQTT, conexión fallida.", origen="OBS/MQTT")
    
    def stop(self):
        """
        Detiene el bucle de red del cliente MQTT.
        """
        if self.client:
            # El driver se encarga de detener el bucle
            self.mqtt_driver.disconnect()
            self.logger.log("MQTT Client Manager: Bucle de red MQTT detenido.", origen="OBS/MQTT")
        else:
            self.logger.log("MQTT Client Manager: Cliente MQTT no instanciado.", origen="OBS/MQTT")

    def get_connection_status(self) -> str:
        """
        Devuelve el estado actual de la conexión del cliente MQTT,
        delegando la llamada al driver.
        """
        return self.mqtt_driver.get_connection_status()