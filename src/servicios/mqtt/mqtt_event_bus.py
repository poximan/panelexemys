# Event bus publish-only limitado a los topicos consumidos por el cliente movil.
# - exemys/estado/grado          (retain): resumen global
# - exemys/estado/grds           (retain): detalle de desconectados
# - exemys/estado/conexion_modem (retain): estado del modem
# - exemys/estado/email          (retain): salud del servidor de correo
# - exemys/estado/proxmox      (retain): snapshot de Proxmox
# - exemys/eventos/email         (no retain): eventos individuales de envio

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
        config.MQTT_TOPIC_GRDS,
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
        config.MQTT_TOPIC_GRADO,
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
        config.MQTT_TOPIC_MODEM_CONEXION,
        json.dumps(obj, ensure_ascii=False),
        qos=config.MQTT_PUBLISH_QOS_STATE,
        retain=config.MQTT_PUBLISH_RETAIN_STATE,
    )

def publish_email_state(payload: dict) -> None:
    """
    Publica el estado agregado del servidor de correo (retain).
    payload: {"smtp":"conectado","ping_local":"conectado","ping_remoto":"desconectado","ts":"..."}
    """
    _safe_publish(
        config.MQTT_TOPIC_EMAIL_ESTADO,
        json.dumps(payload, ensure_ascii=False),
        qos=config.MQTT_PUBLISH_QOS_STATE,
        retain=config.MQTT_PUBLISH_RETAIN_STATE,
    )

def publish_proxmox_state(payload: dict) -> None:
    """
    Publica el snapshot de estado de Proxmox (retain).
    payload: {"ts":"...","status":"online|offline","node":"...","vms":[...],"missing":[...],"error":str|None}
    """
    _safe_publish(
        getattr(config, "MQTT_TOPIC_PROXMOX_ESTADO", "exemys/estado/proxmox"),
        json.dumps(payload, ensure_ascii=False),
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
        config.MQTT_TOPIC_EMAIL_EVENT,
        json.dumps(obj, ensure_ascii=False),
        qos=config.MQTT_PUBLISH_QOS_EVENT,
        retain=config.MQTT_PUBLISH_RETAIN_EVENT,
    )
