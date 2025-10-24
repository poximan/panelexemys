"""
RPC minimalista sobre MQTT.
- El cliente publica en "app/req/<accion>" con reply_to y corr.
- El servidor responde publicando en reply_to uno de los 3 topicos del movil.
"""

import json
import queue
from typing import Optional, Tuple
from datetime import datetime
from src.persistencia.dao.dao_historicos import historicos_dao
from src.logger import Logosaurio
from src.utils.paths import load_observar_key
import config

REQ_PREFIX = config.MQTT_RPC_REQ_ROOT

class MqttRequestRouter:
    """
    enrutador simple de requests rpc sobre mqtt basado en topicos
    """
    def __init__(self, logger: Logosaurio, mqtt_manager, message_queue=None):
        self.log = logger
        self.manager = mqtt_manager
        self.queue = message_queue  # mantenido por compatibilidad (no se consume)
        self._listener_queue: "queue.Queue[Tuple[str, str]]" = queue.Queue()
        self._listener = None
        self._origen = "OBS/RPC"

    def start(self):
        """
        inicia suscripcion a requests y procesa mensajes entrantes
        """
        self.manager.subscribe(f"{REQ_PREFIX}/#", qos=1)
        if self._listener is None:
            def _enqueue(topic: str, payload: str) -> None:
                self._listener_queue.put((topic, payload))
            self._listener = _enqueue
            self.manager.register_prefix_listener(f"{REQ_PREFIX}/", self._listener)
        self.log.log(f"RPC MQTT: suscripto a {REQ_PREFIX}/#", origen=self._origen)

        while True:
            topic, payload = self._listener_queue.get()

            action = topic[len(REQ_PREFIX) + 1:]

            try:
                req = json.loads(payload)
            except Exception:
                self._emit_error(None, config.MQTT_TOPIC_GRDS, action, "payload JSON invalido")
                continue

            reply_to = req.get("reply_to")
            corr = req.get("corr", "")
            params = req.get("params", {})

            if action not in config.MQTT_RPC_ALLOWED_ACTIONS:
                self._emit_error(corr, reply_to, action, f"accion no soportada: {action}")
                continue

            if reply_to not in config.MQTT_RPC_ALLOWED_REPLY_TO:
                self._emit_error(corr, config.MQTT_TOPIC_GRDS, action, "reply_to invalido")
                continue

            if action == "get_global_status":
                self._handle_get_global_status(corr, reply_to)
            elif action == "get_modem_status":
                self._handle_get_modem_status(corr, reply_to)
            else:
                self._emit_error(corr, reply_to, action, "accion no implementada")

    # ----------------- handlers -----------------

    def _handle_get_global_status(self, corr: str, reply_to: str):
        """
        arma resumen global de conectividad y estados actuales por grd
        """
        latest_states = historicos_dao.get_latest_states_for_all_grds()
        total = len(latest_states)
        conectados = sum(1 for v in latest_states.values() if v == 1)
        pct = (conectados * 100.0 / total) if total > 0 else 0.0

        data = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {"porcentaje": round(pct, 2), "total": total, "conectados": conectados},
            "states": latest_states
        }
        self._emit_ok(corr, reply_to, "get_global_status", data)

    def _handle_get_modem_status(self, corr: str, reply_to: str):
        """
        devuelve estado del modem desde observar.json -> ip200_estado
        """
        estado = str(load_observar_key("ip200_estado", "conectado"))
        data = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "estado": estado}
        self._emit_ok(corr, reply_to, "get_modem_status", data)

    # ----------------- emisores -----------------

    def _emit_ok(self, corr: Optional[str], reply_to: str, action: str, data: dict):
        """
        publica respuesta ok en el topico reply_to
        """
        msg = {"type": "rpc", "action": action, "corr": corr, "ok": True, "data": data}
        self.manager.publish(
            reply_to,
            json.dumps(msg, ensure_ascii=False),
            qos=config.MQTT_PUBLISH_QOS_STATE,
            retain=False,
        )

    def _emit_error(self, corr: Optional[str], reply_to: str, action: str, error: str):
        """
        publica respuesta de error en reply_to valido o en GRDS como fallback
        """
        if reply_to not in config.MQTT_RPC_ALLOWED_REPLY_TO:
            reply_to = config.MQTT_TOPIC_GRDS
        msg = {"type": "rpc", "action": action, "corr": corr, "ok": False, "error": error}
        self.manager.publish(
            reply_to,
            json.dumps(msg, ensure_ascii=False),
            qos=config.MQTT_PUBLISH_QOS_STATE,
            retain=False,
        )
