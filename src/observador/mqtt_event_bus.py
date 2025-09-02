# Event bus publish-only limitado a los 3 topicos del cliente movil.
# - estado/exemys   (retain): cambios por GRD y resumen global
# - estado/sensor   (retain): estado del "modem" (red)
# - estado/email    (no-retain): eventos de envio/alerta de email

import json
from typing import Any
import config

_manager = None  # instancia de MqttClientManager

def set_manager(manager) -> None:
    global _manager
    _manager = manager

def _safe_publish(topic: str, payload: Any, qos: int, retain: bool) -> None:
    if _manager is None:
        return
    try:
        _manager.publish(topic, payload, qos=qos, retain=retain)
    except Exception:
        pass

# ---------------- estados (retain=True) ----------------

def publish_exemys_grd_change(grd_id: int, value: int, ts: str) -> None:
    """
    Envia un mensaje de cambio puntual de un GRD.
    payload: {"type":"grd_state","id":<int>,"value":0|1,"ts":"YYYY-mm-dd HH:MM:SS"}
    """
    obj = {"type": "grd_state", "id": int(grd_id), "value": int(value), "ts": ts}
    _safe_publish(
        config.MQTT_ESTADO_EXEMYS,
        json.dumps(obj, ensure_ascii=False),
        qos=config.MQTT_PUBLISH_QOS_STATE,
        retain=config.MQTT_PUBLISH_RETAIN_STATE,
    )

def publish_exemys_global_summary(porcentaje: float, total: int, conectados: int) -> None:
    """
    Resumen global de conectividad (mismo topico).
    payload: {"type":"global","porcentaje":..,"total":..,"conectados":..}
    """
    obj = {"type": "global", "porcentaje": round(float(porcentaje), 2), "total": int(total), "conectados": int(conectados)}
    _safe_publish(
        config.MQTT_ESTADO_EXEMYS,
        json.dumps(obj, ensure_ascii=False),
        qos=config.MQTT_PUBLISH_QOS_STATE,
        retain=config.MQTT_PUBLISH_RETAIN_STATE,
    )

def publish_sensor_modem_state(estado: str) -> None:
    """
    Estado del modem/routeo (retain).
    payload: {"type":"modem","estado":"conectado"|"desconectado"}
    """
    obj = {"type": "modem", "estado": str(estado)}
    _safe_publish(
        config.MQTT_TOPIC_SENSOR,
        json.dumps(obj, ensure_ascii=False),
        qos=config.MQTT_PUBLISH_QOS_STATE,
        retain=config.MQTT_PUBLISH_RETAIN_STATE,
    )

# ---------------- eventos (retain=False) ----------------

def publish_email_event(subject: str, ok: bool) -> None:
    """
    Evento de envio de email/alarma (no retain).
    payload: {"type":"email","subject":"...","ok":true|false}
    """
    obj = {"type": "email", "subject": subject, "ok": bool(ok)}
    _safe_publish(
        config.MQTT_ESTADO_EMAIL,
        json.dumps(obj, ensure_ascii=False),
        qos=config.MQTT_PUBLISH_QOS_EVENT,
        retain=config.MQTT_PUBLISH_RETAIN_EVENT,
    )