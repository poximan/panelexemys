import threading
import time
import paho.mqtt.client as mqtt
from src.notificador.mqtt_driver import MqttDriver
from src.logger import Logosaurio
import config

class MqttClientManager:
    """
    Gestiona el cliente MQTT, sus suscripciones y publicaciones.
    """
    def __init__(self, logger: Logosaurio):
        self.logger = logger
        self.mqtt_driver = MqttDriver(logger=self.logger)
        self.client = None
        self._stop_event = threading.Event()

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """
        Callback que se ejecuta cuando el cliente se conecta al broker.
        """
        if rc == 0:
            self.logger.log("MQTT Client Manager: Conectado al broker MQTT exitosamente.", origen="NOTIF/MQTT")
            # Suscribirse al tópico 'estados/' una vez conectado
            self.subscribe(config.MQTT_TOPIC_ESTADOS)
        else:
            self.logger.log(f"MQTT Client Manager: Fallo en la conexión, código: {rc}", origen="NOTIF/MQTT", nivel="ERROR")

    def _on_message(self, client, userdata, msg):
        """
        Callback que se ejecuta cuando se recibe un mensaje de un tópico suscrito.
        """
        self.logger.log(f"MQTT Client Manager: Mensaje recibido - Tópico: {msg.topic}, Payload: {msg.payload.decode()}", origen="NOTIF/MQTT")

        # Lógica para el tópico 'estados/'
        if msg.topic == config.MQTT_TOPIC_ESTADOS:
            # Por ahora, devuelve un texto fijo.
            fixed_response = "Estado recibido: OK. Este es un mensaje de prueba fijo."
            self.logger.log(f"MQTT Client Manager: Respuesta fija para '{config.MQTT_TOPIC_ESTADOS}': {fixed_response}", origen="NOTIF/MQTT")
            # Podrías publicar esta respuesta a otro tópico si fuera necesario, por ejemplo:
            # self.publish("estados/respuesta", fixed_response)
        # Puedes añadir más lógica para otros tópicos aquí

    def subscribe(self, topic: str, qos: int = 0):
        """
        Suscribe el cliente a un tópico específico.
        """
        if self.client and self.client.is_connected():
            result, mid = self.client.subscribe(topic, qos)
            if result == mqtt.MQTT_ERR_SUCCESS:
                self.logger.log(f"MQTT Client Manager: Suscrito al tópico '{topic}' (mid={mid})", origen="NOTIF/MQTT")
            else:
                self.logger.log(f"MQTT Client Manager: Error al suscribirse al tópico '{topic}': {result}", origen="NOTIF/MQTT", nivel="ERROR")
        else:
            self.logger.log("MQTT Client Manager: Cliente no conectado, no se puede suscribir.", origen="NOTIF/MQTT", nivel="ADVERTENCIA")

    def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False):
        """
        Publica un mensaje en un tópico específico.
        """
        if self.client and self.client.is_connected():
            info = self.client.publish(topic, payload, qos, retain)
            info.wait_for_publish() # Espera a que el mensaje sea publicado
            self.logger.log(f"MQTT Client Manager: Mensaje publicado en '{topic}': '{payload}'", origen="NOTIF/MQTT")
        else:
            self.logger.log("MQTT Client Manager: Cliente no conectado, no se puede publicar.", origen="NOTIF/MQTT", nivel="ADVERTENCIA")

    def start_mqtt_loop(self):
        """
        Inicia el bucle de red del cliente MQTT en un hilo separado.
        """
        self.client = self.mqtt_driver.connect()
        if self.client:
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.loop_start() # Inicia el bucle en un hilo separado
            self.logger.log("MQTT Client Manager: Bucle de red MQTT iniciado.", origen="NOTIF/MQTT")
            
            # Mantener el hilo principal vivo mientras el bucle MQTT corre
            # Esto es para que el hilo no muera inmediatamente si no hay otra lógica
            # en este mismo hilo que lo mantenga activo.
            while not self._stop_event.is_set():
                time.sleep(1) # Pequeña pausa para no consumir CPU innecesariamente
            
            self.client.loop_stop() # Detiene el bucle de red
            self.mqtt_driver.disconnect()
            self.logger.log("MQTT Client Manager: Bucle de red MQTT detenido.", origen="NOTIF/MQTT")
        else:
            self.logger.log("MQTT Client Manager: No se pudo iniciar el bucle MQTT, conexión fallida.", origen="NOTIF/MQTT", nivel="ERROR")

    def stop_mqtt_loop(self):
        """
        Detiene el bucle de red del cliente MQTT.
        """
        self._stop_event.set()
        self.logger.log("MQTT Client Manager: Señal de detención enviada al bucle MQTT.", origen="NOTIF/MQTT")