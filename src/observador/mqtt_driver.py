import paho.mqtt.client as mqtt
import ssl
import threading
from src.logger import Logosaurio
import config

# Nombre del archivo para la comunicacion de estado entre hilos
STATUS_FILE = "./src/componentes/estado_broker.txt"

class MqttDriver:
    """
    Clase para gestionar la conexion de bajo nivel con el broker MQTT.
    Configura el cliente MQTT con opciones de SSL, usuario y contraseña.
    """
    def __init__(self, logger: Logosaurio):
        self.logger = logger
        self.client = None
        self._status = "disconnected"
        self._reconnect_timer = None
        self._intentional_disconnect = False  # Para evitar reconexiones en desconexiones intencionales
        self._write_status_to_file("desconectado") # Estado inicial

    def _write_status_to_file(self, status: str):
        """Escribe el estado actual de la conexion en un archivo."""
        try:
            with open(STATUS_FILE, "w") as f:
                f.write(status)
        except Exception as e:
            self.logger.log(f"MQTT Driver: Error al escribir en el archivo de estado: {e}", origen="OBS/MQTT")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback que se ejecuta cuando el cliente se conecta al broker."""
        # Se cancela el temporizador de reconexión si existía
        if self._reconnect_timer:
            self._reconnect_timer.cancel()
            self._reconnect_timer = None
            
        if rc == 0:
            self.logger.log("MQTT Driver: Conectado exitosamente.", origen="OBS/MQTT")
            self._status = "connected"
            self._write_status_to_file("conectado")
        else:
            self.logger.log(f"MQTT Driver: Fallo en la conexion, codigo: {rc}. Programando reintento...", origen="OBS/MQTT")
            self._status = "disconnected"
            self._write_status_to_file("desconectado")
            
            # En caso de fallo de conexion, se programa un reintento.
            self._schedule_reconnect()

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        """Callback que se ejecuta cuando el cliente se desconecta del broker."""
        self.logger.log("MQTT Driver: Desconectado del broker.", origen="OBS/MQTT")
        self._status = "disconnected"
        self._write_status_to_file("desconectado")
        
        # Si la desconexion no fue intencional, programar un reintento
        if not self._intentional_disconnect:
            self.logger.log("MQTT Driver: Desconexión inesperada. Programando reintento en 10 segundos...", origen="OBS/MQTT")
            self._schedule_reconnect()
        else:
            self.logger.log("MQTT Driver: Desconexión intencional. No se programará un reintento.", origen="OBS/MQTT")

    def _schedule_reconnect(self):
        """Programa un intento de reconexión después de un retraso."""
        # Si ya hay un temporizador de reconexión, lo cancelamos antes de crear uno nuevo.
        if self._reconnect_timer and self._reconnect_timer.is_alive():
            self._reconnect_timer.cancel()
            self.logger.log("MQTT Driver: Se cancela temporizador de reintento anterior.", origen="OBS/MQTT")
            
        # Log del reintento
        self.logger.log("MQTT Driver: Programando reintento de conexión en 10 segundos...", origen="OBS/MQTT")
        
        self._reconnect_timer = threading.Timer(10, self.connect)
        self._reconnect_timer.daemon = True
        self._reconnect_timer.start()

    def connect(self) -> mqtt.Client:
        """
        Intenta conectar el cliente MQTT al broker.
        Retorna la instancia del cliente MQTT si la conexion es exitosa.
        """
        self._intentional_disconnect = False
        
        if self.client and self.client.is_connected():
            self.logger.log("MQTT Driver: Cliente ya conectado.", origen="OBS/MQTT")
            return self.client
            
        self._status = "conectando"
        self._write_status_to_file("conectando")
        
        try:
            self.logger.log(f"MQTT Driver: Intentando conectar a {config.MQTT_BROKER_HOST}:{config.MQTT_BROKER_PORT}...", origen="OBS/MQTT")

            # Creación del cliente y registro de los callbacks antes de conectar
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2) # Usar API v2
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            
            # El bucle de red se inicia aquí para que los callbacks estén activos
            self.client.loop_start()

            # Configuracion de credenciales
            self.client.username_pw_set(config.MQTT_BROKER_USERNAME, config.MQTT_BROKER_PASSWORD)

            # Configuracion de TLS/SSL
            if config.MQTT_USE_TLS:
                # Se utiliza tls_set() sin argumentos para confiar en los certificados CA del sistema
                self.client.tls_set(tls_version=ssl.PROTOCOL_TLSv1_2)
                # Se habilita la verificación del certificado del servidor
                self.client.tls_insecure_set(False)
                self.logger.log("MQTT Driver: TLS/SSL configurado con verificación de certificado.", origen="OBS/MQTT")
            else:
                self.logger.log("MQTT Driver: TLS/SSL deshabilitado.", origen="OBS/MQTT")

            # Conectar al broker
            self.client.connect(config.MQTT_BROKER_HOST, config.MQTT_BROKER_PORT, 60)
            
            return self.client

        except Exception as e:
            self.logger.log(f"MQTT Driver: Error al conectar con el broker MQTT: {e}. Programando reintento...", origen="OBS/MQTT")
            self._status = "disconnected"
            self._write_status_to_file("desconectado")
            # Llamar al reintento si la conexión falla con una excepción
            self._schedule_reconnect()
            return None

    def disconnect(self):
        """
        Desconecta el cliente MQTT del broker.
        """
        self._intentional_disconnect = True
        if self.client and self.client.is_connected():
            # Detener el bucle de red antes de desconectar
            self.client.loop_stop()
            self.client.disconnect()
            self._status = "disconnected"
            self._write_status_to_file("desconectado")
            self.logger.log("MQTT Driver: Desconectado del broker MQTT.", origen="OBS/MQTT")
        else:
            self.logger.log("MQTT Driver: Cliente MQTT no conectado.", origen="OBS/MQTT")

    def get_client(self) -> mqtt.Client:
        """Retorna la instancia del cliente MQTT."""
        return self.client

    def get_connection_status(self) -> str:
        """
        Devuelve el estado actual de la conexión del cliente MQTT.
        Esta funcion es solo para uso interno y no se utiliza para el indicador de Dash.
        """
        return self._status