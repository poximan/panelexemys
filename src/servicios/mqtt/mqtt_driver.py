import ssl
import threading
from typing import Callable, List, Optional
import paho.mqtt.client as mqtt
import config

class MqttDriver:
    """
    Capa delgada sobre paho-mqtt.
    Mantener cambios al minimo; este modulo expone connect/ disconnect/ publish/ subscribe/ callbacks.
    """

    def __init__(self, logger):
        self.log = logger
        self._origen = "OBS/MQTT"

        client_id = getattr(config, "MQTT_CLIENT_ID", "")
        clean_session = getattr(config, "MQTT_CLEAN_SESSION", True)

        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=client_id, clean_session=clean_session)
        except TypeError:
            self.client = mqtt.Client(client_id=client_id, clean_session=clean_session)

        username = getattr(config, "MQTT_BROKER_USERNAME", None)
        password = getattr(config, "MQTT_BROKER_PASSWORD", None)
        if username is not None:
            self.client.username_pw_set(username, password)

        will_topic = getattr(config, "MQTT_WILL_TOPIC", None)
        will_payload = getattr(config, "MQTT_WILL_PAYLOAD", "offline")
        will_qos = getattr(config, "MQTT_WILL_QOS", 1)
        will_retain = getattr(config, "MQTT_WILL_RETAIN", True)
        if will_topic:
            self.client.will_set(will_topic, payload=will_payload, qos=will_qos, retain=will_retain)

        if getattr(config, "MQTT_BROKER_USE_TLS", False):
            ca = getattr(config, "MQTT_BROKER_CA_CERT", None)
            certfile = getattr(config, "MQTT_CLIENT_CERTFILE", None)
            keyfile = getattr(config, "MQTT_CLIENT_KEYFILE", None)
            tls_insecure = getattr(config, "MQTT_TLS_INSECURE", False)
            self.client.tls_set(
                ca_certs=ca,
                certfile=certfile,
                keyfile=keyfile,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
            )
            self.client.tls_insecure_set(tls_insecure)
            self.log.log(f"TLS configurado (insecure={tls_insecure}).", origen=self._origen)

        self.keepalive = int(getattr(config, "MQTT_BROKER_KEEPALIVE", 60))
        min_delay = int(getattr(config, "MQTT_RECONNECT_DELAY_MIN", 2))
        max_delay = int(getattr(config, "MQTT_RECONNECT_DELAY_MAX", 60))
        try:
            self.client.reconnect_delay_set(min_delay=min_delay, max_delay=max_delay)
        except AttributeError:
            pass

        self.client.on_connect = self._on_connect_internal
        self.client.on_disconnect = self._on_disconnect_internal
        self.client.on_message = self._on_message_internal

        self._extra_on_connect: List[Callable] = []
        self._extra_on_disconnect: List[Callable] = []
        self._extra_on_message: Optional[Callable] = None

        self._connected_event = threading.Event()
        self._connected = False
        self._loop_started = False

    def _on_connect_internal(self, client, userdata, flags, rc, *args):
        if rc == 0:
            self._connected = True
            self._connected_event.set()
            self.log.log("MQTT Driver: on_connect OK (rc=0).", origen=self._origen)
        else:
            self._connected = False
            self.log.log(f"MQTT Driver: on_connect con error (rc={rc}).", origen=self._origen)

        for cb in self._extra_on_connect:
            try:
                cb(client, userdata, flags, rc)
            except Exception as e:
                self.log.log(f"MQTT Driver: error en callback externo on_connect: {e}", origen=self._origen)

    def _on_disconnect_internal(self, client, userdata, rc, *args):
        self._connected = False
        self._connected_event.clear()
        self.log.log(f"MQTT Client Manager: on_disconnect (rc={rc}).", origen=self._origen)

        for cb in self._extra_on_disconnect:
            try:
                cb(client, userdata, rc)
            except Exception as e:
                self.log.log(f"MQTT Driver: error en callback externo on_disconnect: {e}", origen=self._origen)

    def _on_message_internal(self, client, userdata, msg):
        if self._extra_on_message is not None:
            try:
                self._extra_on_message(client, userdata, msg)
                return
            except Exception as e:
                self.log.log(f"MQTT Driver: error en callback externo on_message: {e}", origen=self._origen)
        try:
            payload = msg.payload.decode(errors="replace")
        except Exception:
            payload = str(msg.payload)
        self.log.log(f"MQTT mensaje: {msg.topic} -> {payload}", origen=self._origen)

    def register_on_connect(self, cb: Callable):
        self._extra_on_connect.append(cb)

    def register_on_disconnect(self, cb: Callable):
        self._extra_on_disconnect.append(cb)

    def set_on_message(self, cb: Callable):
        self._extra_on_message = cb

    def connect(self) -> bool:
        host = getattr(config, "MQTT_BROKER_HOST", "localhost")
        port = int(getattr(config, "MQTT_BROKER_PORT", 1883))
        timeout = int(getattr(config, "MQTT_CONNECT_TIMEOUT", 15))

        self.log.log(
            f"MQTT Driver: Intentando conectar a {host}:{port} (keepalive={self.keepalive})",
            origen=self._origen,
        )

        try:
            self.client.connect_async(host, port, keepalive=self.keepalive)
        except Exception as e:
            self.log.log(f"MQTT Driver: excepcion en connect_async: {e}", origen=self._origen)
            return False

        if not self._loop_started:
            self.client.loop_start()
            self._loop_started = True

        if self._connected_event.wait(timeout=timeout):
            self.log.log("MQTT Driver: Conexión confirmada por callback dentro del timeout.", origen=self._origen)
            return True

        self.log.log("MQTT Driver: Timeout esperando confirmacion de conexion.", origen=self._origen)
        return False

    def disconnect(self):
        try:
            self.client.disconnect()
        except Exception as e:
            self.log.log(f"MQTT Driver: error en disconnect(): {e}", origen=self._origen)
        finally:
            if self._loop_started:
                self.client.loop_stop()
                self._loop_started = False
            self._connected = False
            self._connected_event.clear()

    def publish(self, topic: str, payload, qos: int = 0, retain: bool = False):
        if not self._connected:
            self.log.log(f"MQTT Driver: publish abortado; cliente desconectado (topic={topic}).", origen=self._origen)
            return
        try:
            res = self.client.publish(topic, payload, qos=qos, retain=retain)
            self.log.log(f"MQTT Driver: publish('{topic}') -> {res.rc}", origen=self._origen)
        except Exception as e:
            self.log.log(f"MQTT Driver: error publicando en '{topic}': {e}", origen=self._origen)

    def subscribe(self, topic: str, qos: int = 0):
        if not self._connected:
            self.log.log(f"MQTT Driver: subscribe abortado; cliente desconectado (topic={topic}).", origen=self._origen)
            return
        try:
            res = self.client.subscribe(topic, qos=qos)
            self.log.log(f"MQTT Client Manager: subscribe('{topic}') -> {res}", origen=self._origen)
        except Exception as e:
            self.log.log(f"MQTT Driver: error al suscribirse a '{topic}': {e}", origen=self._origen)

    def is_connected(self) -> bool:
        return self._connected