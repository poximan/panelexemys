import json
from typing import Any, Optional
from src.observador.mqtt_driver import MqttDriver
import config

class MqttTopicPublisher:
    """
    Publicador simple reutilizable.
    Usa como default los parámetros de publicaciones de 'estado' definidos en config:
      - MQTT_PUBLISH_QOS_STATE
      - MQTT_PUBLISH_RETAIN_STATE
    Se pueden sobreescribir por llamada.
    """
    def __init__(self, logger):
        self.log = logger
        self._origen = "OBS/PUB"
        self.driver = MqttDriver(logger=self.log)
        self._started = False
        self._qos_state = int(getattr(config, "MQTT_PUBLISH_QOS_STATE", 1))
        self._retain_state = bool(getattr(config, "MQTT_PUBLISH_RETAIN_STATE", True))

    def _ensure_started(self) -> bool:
        if self.driver.is_connected():
            return True
        ok = self.driver.connect()
        self._started = ok
        return ok

    def publish(self, topic: str, payload: Any,
                qos: Optional[int] = None, retain: Optional[bool] = None):
        if not self._ensure_started():
            self.log.log(f"No se pudo conectar para publicar en '{topic}'.", origen=self._origen)
            return
        q = self._qos_state if qos is None else int(qos)
        r = self._retain_state if retain is None else bool(retain)
        try:
            self.driver.publish(topic, payload if isinstance(payload, str) else str(payload), qos=q, retain=r)
        except Exception as e:
            self.log.log(f"Error publicando en '{topic}': {e}", origen=self._origen)

    def publish_json(self, topic: str, obj: dict,
                     qos: Optional[int] = None, retain: Optional[bool] = None):
        self.publish(topic, json.dumps(obj, ensure_ascii=False), qos=qos, retain=retain)