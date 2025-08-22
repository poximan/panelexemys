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
        self._status = "desconectado"
        self._write_status_to_file("desconectado")
        self._connection_event = threading.Event()  # Evento para sincronizar la conexion

    def _write_status_to_file(self, status: str):
        """Escribe el estado actual de la conexion en un archivo."""
        try:
            with open(STATUS_FILE, "w") as f:
                f.write(status)
        except Exception as e:
            self.logger.log(f"MQTT Driver: Error al escribir en el archivo de estado: {e}", origen="OBS/MQTT")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback que se ejecuta cuando el cliente se conecta al broker."""
        if rc == 0:
            self.logger.log("MQTT Driver: Conectado exitosamente.", origen="OBS/MQTT")
            self._status = "conectado"
            self._write_status_to_file("conectado")
            # Disparar el evento de conexión para desbloquear el hilo principal
            self._connection_event.set()
        else:
            self.logger.log(f"MQTT Driver: Fallo en la conexion, codigo: {rc}. Reintentando...", origen="OBS/MQTT")
            self._status = "desconectado"
            self._write_status_to_file("desconectado")
            # En caso de fallo, limpiar el evento para que la proxima llamada espere
            self._connection_event.clear()

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        """Callback que se ejecuta cuando el cliente se desconecta del broker."""
        self.logger.log(f"MQTT Driver: Desconectado del broker. Codigo: {rc}.", origen="OBS/MQTT")
        self._status = "desconectado"
        self._write_status_to_file("desconectado")

    def connect(self) -> mqtt.Client:
        """
        Intenta conectar el cliente MQTT al broker y espera hasta que la conexion se confirme.
        """
        # Limpiar el evento para una nueva conexión
        self._connection_event.clear()

        # Si el cliente ya existe y está conectado, no hacer nada
        if self.client and self.client.is_connected():
            self.logger.log("MQTT Driver: Cliente ya conectado.", origen="OBS/MQTT")
            return self.client
        
        self.logger.log(f"MQTT Driver: Intentando conectar a {config.MQTT_BROKER_HOST}:{config.MQTT_BROKER_PORT}...", origen="OBS/MQTT")
        self._status = "conectando"
        self._write_status_to_file("conectando")
        
        try:
            self.client = mqtt.Client(
                client_id="panelexemys", 
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2
            )
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            
            # Configuracion de credenciales
            self.client.username_pw_set(config.MQTT_BROKER_USERNAME, config.MQTT_BROKER_PASSWORD)

            # Configuracion de TLS/SSL
            if config.MQTT_USE_TLS:
                self.client.tls_set(tls_version=ssl.PROTOCOL_TLSv1_2)
                self.client.tls_insecure_set(False)
                self.logger.log("MQTT Driver: TLS/SSL configurado con verificación de certificado.", origen="OBS/MQTT")
            else:
                self.logger.log("MQTT Driver: TLS/SSL deshabilitado.", origen="OBS/MQTT")
                
            # Deshabilitar la reconexión automática de la biblioteca
            # para controlarla manualmente si es necesario
            self.client.reconnect_delay_set(min_delay=5, max_delay=30)

            # Iniciar el bucle de red ANTES de la conexión
            self.client.loop_start()

            # Conectar al broker
            self.client.connect(config.MQTT_BROKER_HOST, config.MQTT_BROKER_PORT, 120)
            
            # Esperar hasta que el callback _on_connect sea llamado y la conexión se establezca
            if self._connection_event.wait(timeout=30):
                return self.client
            else:
                self.logger.log("MQTT Driver: Tiempo de espera agotado para la conexión.", origen="OBS/MQTT")
                self.client.loop_stop()
                return None
        except Exception as e:
            self.logger.log(f"MQTT Driver: Error critico al conectar: {e}.", origen="OBS/MQTT")
            self._status = "desconectado"
            self._write_status_to_file("desconectado")
            return None

    def disconnect(self):
        """
        Desconecta el cliente MQTT del broker.
        """
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self._status = "desconectado"
            self._write_status_to_file("desconectado")
            self.logger.log("MQTT Driver: Desconectado del broker MQTT.", origen="OBS/MQTT")
        else:
            self.logger.log("MQTT Driver: Cliente MQTT no instanciado.", origen="OBS/MQTT")

    def get_client(self) -> mqtt.Client | None:
        """Retorna la instancia del cliente MQTT."""
        return self.client

    def get_connection_status(self) -> str:
        """
        Devuelve el estado actual de la conexión del cliente MQTT.
        """
        return self._status