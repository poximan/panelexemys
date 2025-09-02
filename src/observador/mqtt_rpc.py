"""
RPC minimalista sobre MQTT.
- El cliente (movil) PUBLICA en "app/req/<accion>" un JSON:
  {
    "reply_to": "estado/exemys" | "estado/sensor" | "estado/email",
    "corr": "uuid-o-id",
    "params": { ... }   # opcional
  }

- El servidor RESPONDE PUBLICANDO en el "reply_to" (que ya esta suscripto por el movil):
  {
    "type": "rpc",
    "action": "<accion>",
    "corr": "<mismo id>",
    "ok": true|false,
    "data": { ... }     # o "error": "..."
  }

Acciones soportadas iniciales (config.MQTT_RPC_ALLOWED_ACTIONS):
  - get_global_status  -> responde con resumen global + ultimos estados por GRD (estado/exemys)
  - get_modem_status   -> responde con estado modem (estado/sensor)
"""

import json
import os
from typing import Tuple, Optional
from datetime import datetime

from src.persistencia.dao_historicos import historicos_dao
from src.logger import Logosaurio
import config

REQ_PREFIX = config.MQTT_RPC_REQ_ROOT  # "app/req"

class MqttRequestRouter:
    def __init__(self, logger: Logosaurio, mqtt_manager, message_queue):
        self.log = logger
        self.manager = mqtt_manager
        self.queue = message_queue
        self._origen = "OBS/RPC"

    def start(self):
        # suscribirse a app/req/# para recibir requests
        self.manager.subscribe(f"{REQ_PREFIX}/#", qos=1)
        self.log.log(f"RPC MQTT: suscripto a {REQ_PREFIX}/#", origen=self._origen)

        while True:
            item = self.queue.get()
            if not item:
                continue
            topic, payload = item
            if not topic.startswith(f"{REQ_PREFIX}/"):
                # mensaje de otra cosa (la UI quizas lo consume tambien)
                continue

            action = topic[len(REQ_PREFIX)+1:]  # luego de "app/req/"
            try:
                req = json.loads(payload)
            except Exception:
                self._emit_error(None, "estado/email", action, "payload JSON invalido")
                continue

            reply_to = req.get("reply_to")
            corr = req.get("corr", "")
            params = req.get("params", {})

            if action not in config.MQTT_RPC_ALLOWED_ACTIONS:
                self._emit_error(corr, reply_to, action, f"accion no soportada: {action}")
                continue

            if reply_to not in config.MQTT_RPC_ALLOWED_REPLY_TO:
                # forzar siempre responder en estado/email si reply_to no es valido
                self._emit_error(corr, config.MQTT_ESTADO_EMAIL, action, "reply_to invalido")
                continue

            # despachar
            if action == "get_global_status":
                self._handle_get_global_status(corr, reply_to)
            elif action == "get_modem_status":
                self._handle_get_modem_status(corr, reply_to)
            else:
                self._emit_error(corr, reply_to, action, "accion no implementada")

    # ----------------- handlers -----------------

    def _handle_get_global_status(self, corr: str, reply_to: str):
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
        # reutilizamos el archivo 'observar.json' (igual que NotifModem/tcp_api)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        observar_file_path = os.path.join(script_dir, 'observar.json')
        estado = "conectado"
        try:
            if os.path.exists(observar_file_path):
                with open(observar_file_path, 'r') as f:
                    content = f.read().strip()
                    data = json.loads(content) if content else {}
                    estado = data.get("ip200_estado", "conectado")
        except Exception:
            pass

        data = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "estado": estado}
        self._emit_ok(corr, reply_to, "get_modem_status", data)

    # ----------------- emisores -----------------

    def _emit_ok(self, corr: Optional[str], reply_to: str, action: str, data: dict):
        msg = {"type": "rpc", "action": action, "corr": corr, "ok": True, "data": data}
        self.manager.publish(
            reply_to,
            json.dumps(msg, ensure_ascii=False),
            qos=config.MQTT_PUBLISH_QOS_STATE if reply_to != config.MQTT_ESTADO_EMAIL else config.MQTT_PUBLISH_QOS_EVENT,
            retain=False,  # las respuestas RPC no se retienen
        )

    def _emit_error(self, corr: Optional[str], reply_to: str, action: str, error: str):
        if reply_to not in config.MQTT_RPC_ALLOWED_REPLY_TO:
            # fallback
            reply_to = config.MQTT_ESTADO_EMAIL
        msg = {"type": "rpc", "action": action, "corr": corr, "ok": False, "error": error}
        self.manager.publish(
            reply_to,
            json.dumps(msg, ensure_ascii=False),
            qos=config.MQTT_PUBLISH_QOS_EVENT,
            retain=False,
        )