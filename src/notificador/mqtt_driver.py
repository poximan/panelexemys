import paho.mqtt.client as mqtt
import ssl
from src.logger import Logosaurio
import config

class MqttDriver:
    """
    Clase para gestionar la conexion de bajo nivel con el broker MQTT.
    Configura el cliente MQTT con opciones de SSL, usuario y contraseña.
    """
    def __init__(self, logger: Logosaurio):
        self.logger = logger
        self.client = None
        self._is_connected = False

    def connect(self) -> mqtt.Client:
        """
        Intenta conectar el cliente MQTT al broker.
        Retorna la instancia del cliente MQTT si la conexion es exitosa.
        """
        if self._is_connected and self.client and self.client.is_connected():
            self.logger.log("MQTT Driver: Cliente ya conectado.", origen="NOTIF/MQTT")
            return self.client

        try:
            self.logger.log(f"MQTT Driver: Intentando conectar a {config.MQTT_BROKER_HOST}:{config.MQTT_BROKER_PORT}...", origen="NOTIF/MQTT")
            
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2) # Usar API v2

            # Configuracion de credenciales
            self.client.username_pw_set(config.MQTT_BROKER_USERNAME, config.MQTT_BROKER_PASSWORD)

            # Configuracion de TLS/SSL
            if config.MQTT_USE_TLS:
                self.client.tls_set(tls_version=ssl.PROTOCOL_TLSv1_2) # Forzar TLSv1.2 para HiveMQ Cloud
                self.logger.log("MQTT Driver: TLS/SSL configurado.", origen="NOTIF/MQTT")
            else:
                self.logger.log("MQTT Driver: TLS/SSL deshabilitado.", origen="NOTIF/MQTT")

            # Conectar al broker
            self.client.connect(config.MQTT_BROKER_HOST, config.MQTT_BROKER_PORT, 60) # Keepalive de 60 segundos
            self._is_connected = True
            self.logger.log("MQTT Driver: Conexion exitosa con el broker MQTT.", origen="NOTIF/MQTT")
            return self.client

        except Exception as e:
            self.logger.log(f"MQTT Driver: Error al conectar con el broker MQTT: {e}", origen="NOTIF/MQTT")
            self._is_connected = False
            return None

    def disconnect(self):
        """
        Desconecta el cliente MQTT del broker.
        """
        if self.client and self.client.is_connected():
            self.client.disconnect()
            self._is_connected = False
            self.logger.log("MQTT Driver: Desconectado del broker MQTT.", origen="NOTIF/MQTT")
        else:
            self.logger.log("MQTT Driver: Cliente MQTT no conectado.", origen="NOTIF/MQTT")

    def get_client(self) -> mqtt.Client:
        """
        Retorna la instancia del cliente MQTT.
        """
        return self.client

    def is_connected(self) -> bool:
        """
        Verifica si el cliente MQTT esta conectado.
        """
        return self._is_connected and self.client and self.client.is_connected()